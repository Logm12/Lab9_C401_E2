"""
workers/policy_tool.py — Policy & Tool Worker
Sprint 2+3: Kiểm tra policy dựa vào context, gọi MCP tools khi cần.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: context từ retrieval_worker
    - needs_tool: True nếu supervisor quyết định cần tool call

Output (vào AgentState):
    - policy_result: {"policy_applies", "policy_name", "exceptions_found", "source", "rule"}
    - mcp_tools_used: list of tool calls đã thực hiện
    - worker_io_log: log

Gọi độc lập để test:
    python workers/policy_tool.py
"""

import os
import sys
from typing import Optional

WORKER_NAME = "policy_tool_worker"


# ─────────────────────────────────────────────
# MCP Client — Sprint 3: Thay bằng real MCP call
# ─────────────────────────────────────────────

MCP_SERVER_URL = "http://localhost:8000"


def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """
    TIP-006: Goi MCP tool qua HTTP client (httpx).
    Fallback: in-process dispatch neu HTTP server khong chay.

    Returns a standardized trace dict with tool, input, output, error, timestamp.
    """
    from datetime import datetime

    # --- Try HTTP first ---
    try:
        import httpx
        url = f"{MCP_SERVER_URL}/tools/call/{tool_name}"
        resp = httpx.post(url, json=tool_input, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "tool": tool_name,
                "input": tool_input,
                "output": data.get("output", data),
                "error": None,
                "timestamp": datetime.now().isoformat(),
                "transport": "http",
            }
        else:
            # Surface HTTP error codes (404 / 422) but don't crash
            return {
                "tool": tool_name,
                "input": tool_input,
                "output": None,
                "error": {"code": f"HTTP_{resp.status_code}", "reason": resp.text[:200]},
                "timestamp": datetime.now().isoformat(),
                "transport": "http",
            }
    except Exception as http_err:
        # --- Fallback: in-process dispatch ---
        try:
            from mcp_server import dispatch_tool
            result = dispatch_tool(tool_name, tool_input)
            return {
                "tool": tool_name,
                "input": tool_input,
                "output": result,
                "error": None,
                "timestamp": datetime.now().isoformat(),
                "transport": "in-process",
            }
        except Exception as fallback_err:
            return {
                "tool": tool_name,
                "input": tool_input,
                "output": None,
                "error": {"code": "MCP_CALL_FAILED", "reason": str(fallback_err)},
                "timestamp": datetime.now().isoformat(),
                "transport": "failed",
            }


def _llm_policy_analysis(task: str, chunks: list, mcp_result: dict) -> dict:
    """
    TIP-006: Dung GPT-5.4-mini phan tich ket qua MCP + chunks.

    Returns: {"explanation": str, "confidence": float}
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        context_parts = []
        if chunks:
            context_parts.append("=== TAI LIEU NOI BO ===")
            for c in chunks[:3]:
                context_parts.append(f"[{c.get('source', '?')}] {c.get('text', '')[:300]}")

        mcp_output = mcp_result.get("output", {}) if mcp_result else {}
        context_parts.append(f"\n=== KET QUA MCP TOOL ({mcp_result.get('tool', '?')}) ===")
        context_parts.append(str(mcp_output)[:500])

        context = "\n".join(context_parts)
        prompt = (
            f"Dua tren du lieu tu MCP Tool va cac doan van ban sau, "
            f"hay xac dinh khach hang co pham quy dinh hay khong va giai thich ngan gon:\n\n"
            f"Cau hoi goc: {task}\n\n{context}"
        )

        response = client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": "Ban la chuyen gia phan tich chinh sach doanh nghiep."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=400,
        )
        explanation = response.choices[0].message.content
        return {"explanation": explanation, "confidence": 0.85}
    except Exception as e:
        # Graceful fallback — rule-based explanation
        return {
            "explanation": f"Rule-based analysis (LLM unavailable: {str(e)[:80]})",
            "confidence": 0.6,
        }



# ─────────────────────────────────────────────
# Policy Analysis Logic
# ─────────────────────────────────────────────

def analyze_policy(task: str, chunks: list) -> dict:
    """
    Phân tích policy dựa trên context chunks.

    TODO Sprint 2: Implement logic này với LLM call hoặc rule-based check.

    Cần xử lý các exceptions:
    - Flash Sale → không được hoàn tiền
    - Digital product / license key / subscription → không được hoàn tiền
    - Sản phẩm đã kích hoạt → không được hoàn tiền
    - Đơn hàng trước 01/02/2026 → áp dụng policy v3 (không có trong docs)

    Returns:
        dict with: policy_applies, policy_name, exceptions_found, source, rule, explanation
    """
    task_lower = task.lower()
    context_text = " ".join([c.get("text", "") for c in chunks]).lower()

    # --- Rule-based exception detection ---
    exceptions_found = []

    # Exception 1: Flash Sale (TIP-003)
    if any(kw in task_lower for kw in ["flash sale", "flashsale"]) or "flash sale" in context_text:
        exceptions_found.append({
            "type": "flash_sale_exception",
            "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
            "source": "policy_refund_v4.txt",
        })

    # Exception 2: Digital product (TIP-003)
    if any(kw in task_lower for kw in ["license key", "license", "subscription", "kỹ thuật số", "mã kích hoạt", "key"]):
        exceptions_found.append({
            "type": "digital_product_exception",
            "rule": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # Exception 3: Activated product
    if any(kw in task_lower for kw in ["đã kích hoạt", "đã đăng ký", "đã sử dụng", "kích hoạt"]):
        exceptions_found.append({
            "type": "activated_exception",
            "rule": "Sản phẩm đã kích hoạt hoặc đăng ký tài khoản không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # Exception 4: Temporal scoping (TIP-003)
    # Đơn hàng trước 01/02/2026 áp dụng chính sách cũ (v3).
    import re
    # Tìm kiếm định dạng ngày dd/mm/yyyy hoặc dd-mm-yyyy hoặc dd.mm.yyyy
    date_match = re.search(r"(\d{2})[/.-](\d{2})[/.-](\d{4})", task)
    if date_match:
        try:
            day, month, year = map(int, date_match.groups())
            from datetime import datetime
            order_date = datetime(year, month, day)
            threshold_date = datetime(2026, 2, 1)
            if order_date < threshold_date:
                exceptions_found.append({
                    "type": "temporal_scope_exception",
                    "rule": "Đơn hàng đặt trước 01/02/2026 thuộc phạm vi chính sách v3 (không có trong tài liệu hiện tại).",
                    "source": "temporal_scoping_rule",
                })
        except ValueError:
            pass

    # Determine policy_applies
    policy_applies = len(exceptions_found) == 0

    policy_name = "refund_policy_v4"
    policy_version_note = ""
    if any(ex["type"] == "temporal_scope_exception" for ex in exceptions_found):
        policy_version_note = "Đơn hàng thuộc phạm vi chính sách v3 (trước 01/02/2026)."

    sources = list({c.get("source", "unknown") for c in chunks if c})
    # Add temporal scoping source if applicable
    if any(ex["type"] == "temporal_scope_exception" for ex in exceptions_found):
        if "temporal_scoping_rule" not in sources:
            sources.append("temporal_scoping_rule")

    return {
        "policy_applies": policy_applies,
        "policy_name": policy_name,
        "exceptions_found": exceptions_found,
        "source": sources,
        "policy_version_note": policy_version_note,
        "explanation": f"Analyzed via rule-based policy check. Points found: {len(exceptions_found)} exceptions.",
    }


# ─────────────────────────────────────────────
# Worker Entry Point
# ─────────────────────────────────────────────

def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với policy_result và mcp_tools_used
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "needs_tool": needs_tool,
        },
        "output": None,
        "error": None,
    }

    try:
        # Step 1: Nếu chưa có chunks, gọi MCP search_kb
        if not chunks and needs_tool:
            mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP search_kb")

            if mcp_result.get("output") and mcp_result["output"].get("chunks"):
                chunks = mcp_result["output"]["chunks"]
                state["retrieved_chunks"] = chunks

        # Step 2: Phân tích policy (Rule-based first pass)
        policy_result = analyze_policy(task, chunks)

        # Step 3: MCP Tools & LLM Analysis (TIP-006)
        if needs_tool:
            mcp_result = None
            task_lower = task.lower()
            
            # Logic gọi Tool tùy theo keyword trong task
            if any(kw in task_lower for kw in ["cấp quyền", "level"]):
                level = 3
                if "level 1" in task_lower: level = 1
                elif "level 2" in task_lower: level = 2
                
                mcp_result = _call_mcp_tool("check_access_permission", {
                    "access_level": level,
                    "requester_role": "contractor" if "contractor" in task_lower else "employee",
                    "is_emergency": "khẩn" in task_lower or "gấp" in task_lower
                })
            elif any(kw in task_lower for kw in ["ticket", "p1", "jira"]):
                mcp_result = _call_mcp_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})

            if mcp_result:
                # Ghi nhận MCP trace vào AgentState
                state["mcp_tools_used"].append(mcp_result)
                state["history"].append(f"[{WORKER_NAME}] called MCP: {mcp_result['tool']}")

                # Dùng LLM đánh giá MCP Result vs Docs
                llm_eval = _llm_policy_analysis(task, chunks, mcp_result)
                policy_result["explanation"] = f"Rule: {policy_result.get('explanation', '')}\n[LLM_GPT5.4-mini]: {llm_eval['explanation']}"
                
                # HITL Check (TIP-006)
                if llm_eval["confidence"] < 0.5 or "mâu thuẫn" in llm_eval["explanation"].lower() or "không nhất quán" in llm_eval["explanation"].lower():
                    state["hitl_triggered"] = True
                    state["confidence"] = min(state.get("confidence", 1.0), 0.4)
                    state["history"].append(f"[{WORKER_NAME}] LLM phát hiện mâu thuẫn -> hitl_triggered=True")
                else:
                    state["confidence"] = max(state.get("confidence", 0.0), llm_eval["confidence"])

        state["policy_result"] = policy_result

        worker_io["output"] = {
            "policy_applies": policy_result["policy_applies"],
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "mcp_calls": len(state["mcp_tools_used"]),
            "hitl_triggered": state.get("hitl_triggered", False),
        }
        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result['policy_applies']}, "
            f"mcp_calls={len(state['mcp_tools_used'])}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
        state["policy_result"] = {"error": str(e)}
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Policy Tool Worker — Standalone Test")
    print("=" * 50)

    test_cases = [
        {
            "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
            "retrieved_chunks": [
                {"text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.9}
            ],
        },
        {
            "task": "Khách hàng muốn hoàn tiền license key đã kích hoạt.",
            "retrieved_chunks": [
                {"text": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.88}
            ],
        },
        {
            "task": "Khách hàng yêu cầu hoàn tiền trong 5 ngày, sản phẩm lỗi, chưa kích hoạt.",
            "retrieved_chunks": [
                {"text": "Yêu cầu trong 7 ngày làm việc, sản phẩm lỗi nhà sản xuất, chưa dùng.", "source": "policy_refund_v4.txt", "score": 0.85}
            ],
        },
    ]

    for tc in test_cases:
        print(f"\n▶ Task: {tc['task'][:70]}...")
        result = run(tc.copy())
        pr = result.get("policy_result", {})
        print(f"  policy_applies: {pr.get('policy_applies')}")
        if pr.get("exceptions_found"):
            for ex in pr["exceptions_found"]:
                print(f"  exception: {ex['type']} — {ex['rule'][:60]}...")
        print(f"  MCP calls: {len(result.get('mcp_tools_used', []))}")

    print("\n✅ policy_tool_worker test done.")
