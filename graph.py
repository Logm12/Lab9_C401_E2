"""
graph.py — Supervisor Orchestrator
Sprint 1: Implement AgentState, supervisor_node, route_decision và kết nối graph.

Kiến trúc:
    Input → Supervisor → [retrieval_worker | policy_tool_worker | human_review] → synthesis → Output

Chạy thử:
    python graph.py
"""

import json
import os
import sys
from datetime import datetime
from typing import TypedDict, Literal, Optional

# Đảm bảo console output hỗ trợ tiếng Việt trên Windows
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())



# ─────────────────────────────────────────────
# 1. Shared State — dữ liệu đi xuyên toàn graph
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    # Input
    task: str                           # Câu hỏi đầu vào từ user

    # Supervisor decisions
    supervisor_route: str               # Worker được chọn bởi supervisor
    route_reason: str                   # Lý do route sang worker nào
    risk_high: bool                     # True → cần HITL hoặc human_review
    needs_tool: bool                    # True → cần gọi external tool qua MCP
    hitl_triggered: bool                # True → đã pause cho human review

    # Worker outputs
    retrieved_chunks: list              # Output từ retrieval_worker
    retrieved_sources: list             # Danh sách nguồn tài liệu
    policy_result: dict                 # Output từ policy_tool_worker
    mcp_tools_used: list                # Danh sách MCP tools đã gọi

    # Final output
    final_answer: str                   # Câu trả lời tổng hợp
    sources: list                       # Sources được cite
    confidence: float                   # Mức độ tin cậy (0.0 - 1.0)

    # Trace & history
    history: list                       # Lịch sử các bước đã qua
    workers_called: list                # Danh sách workers đã được gọi
    latency_ms: Optional[int]           # Thời gian xử lý (ms)
    run_id: str                         # ID của run này


def make_initial_state(task: str) -> AgentState:
    """Khởi tạo state cho một run mới."""
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "workers_called": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    }


# ─────────────────────────────────────────────
# 2. Supervisor Node — quyết định route
# ─────────────────────────────────────────────

def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor phân tích task và quyết định:
    1. Route sang worker nào
    2. Có cần MCP tool không
    3. Có risk cao cần HITL không
    """
    task = state["task"].lower()
    state["history"].append(f"[supervisor] received task: {state['task'][:80]}")

    # 1. Khởi tạo mặc định
    route = "retrieval_worker"
    route_reason = "Default routing to retrieval_worker"
    needs_tool = False
    risk_high = False

    # 2. Keyword-based Routing (TIP-001)
    # "hoàn tiền", "refund" -> policy_tool_worker
    policy_keywords = ["hoàn tiền", "refund", "chính sách", "policy"]
    if any(kw in task for kw in policy_keywords):
        route = "policy_tool_worker"
        route_reason = "Phát hiện từ khóa policy/refund -> Chuyển sang policy_tool_worker"
        needs_tool = True

    # 3. HITL & Risk Triggers (TIP-001)
    # Intents: "tạo", "xóa", "gửi" (Irreversible actions)
    irreversible_intents = ["tạo", "xóa", "gửi", "create", "delete", "send"]
    # Error codes: "ERR-"
    error_code_trigger = "err-"
    # Risk keywords: "không chắc", "khẩn cấp"
    risk_keywords = ["không chắc", "khẩn cấp", "emergency", "urgent"]

    if any(intent in task for intent in irreversible_intents):
        risk_high = True
        route_reason = f"Phát hiện intent thực hiện hành động ({[i for i in irreversible_intents if i in task][0]}) -> Cần HITL phê duyệt"
    elif error_code_trigger in task:
        risk_high = True
        route_reason = "Phát hiện mã lỗi hệ thống (ERR-) -> Cần Human Review để phân tích sâu"
    elif any(kw in task for kw in risk_keywords):
        risk_high = True
        route_reason += " | Cảnh báo: Task có độ rủi ro cao/khẩn cấp"

    # Ghi nhận kết quả
    state["supervisor_route"] = route
    state["route_reason"] = route_reason
    state["needs_tool"] = needs_tool
    state["risk_high"] = risk_high
    state["history"].append(f"[supervisor] route={route} reason={route_reason} risk={risk_high}")

    return state


# ─────────────────────────────────────────────
# 3. Route Decision — conditional edge (TIP-007)
# ─────────────────────────────────────────────

def route_decision(state: AgentState) -> str:
    """
    Quyết định trạm tiếp theo: Human Review hoặc Worker tương ứng.
    """
    # Nếu có rủi ro cao và chưa qua HITL -> Chuyển đến Human Review
    if state.get("risk_high") and not any(w == "human_review" for w in state.get("workers_called", [])):
        return "human_review"
    
    # Nếu không có rủi ro hoặc đã qua HITL -> Đi đến worker được Supervisor chỉ định
    route = state.get("supervisor_route", "retrieval_worker")
    return route


# ─────────────────────────────────────────────
# 4. Human Review Node — HITL placeholder (TIP-007)
# ─────────────────────────────────────────────

def human_review_node(state: AgentState) -> AgentState:
    """
    HITL node: pause và chờ human approval.
    """
    state["hitl_triggered"] = True
    if "[human_review] HITL triggered" not in "".join(state["history"]):
        state["history"].append("[human_review] HITL triggered — awaiting human input")
    
    if "human_review" not in state["workers_called"]:
        state["workers_called"].append("human_review")

    # Placeholder: tự động approve để pipeline tiếp tục
    print(f"\nHITL TRIGGERED")
    print(f"   Task: {state['task']}")
    print(f"   Reason: {state['route_reason']}")
    print(f"   Action: Auto-approving in lab mode (set hitl_triggered=True)\n")

    # [FIX TIP-007] TUYỆT ĐỐI KHÔNG gán cứng retrieval_worker.
    # Logic tiếp theo sẽ do route_decision quyết định dựa trên supervisor_route ban đầu.
    state["route_reason"] += " | human approved"

    return state


# ─────────────────────────────────────────────
# 5. Import Workers
# ─────────────────────────────────────────────

from workers.retrieval import run as retrieval_run
from workers.policy_tool import run as policy_tool_run
from workers.synthesis import run as synthesis_run


def retrieval_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi retrieval worker."""
    return retrieval_run(state)


def policy_tool_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi policy/tool worker."""
    return policy_tool_run(state)


def synthesis_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi synthesis worker."""
    return synthesis_run(state)


# ─────────────────────────────────────────────
# 6. Build Graph (TIP-007 LangGraph)
# ─────────────────────────────────────────────

from langgraph.graph import StateGraph, START, END

def build_graph():
    """
    Xây dựng graph sử dụng LangGraph StateGraph (TIP-007).
    """
    workflow = StateGraph(AgentState)

    # Thêm các nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("retrieval_worker", retrieval_worker_node)
    workflow.add_node("policy_tool_worker", policy_tool_worker_node)
    workflow.add_node("synthesis_worker", synthesis_worker_node)

    # Thiết lập START
    workflow.add_edge(START, "supervisor")

    # Conditional Edges từ Supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_decision,
        {
            "human_review": "human_review",
            "retrieval_worker": "retrieval_worker",
            "policy_tool_worker": "policy_tool_worker"
        }
    )

    # Sau khi Human Review xong, quay lại Route Decision để đi đến worker ban đầu
    workflow.add_conditional_edges(
        "human_review",
        route_decision,
        {
            "retrieval_worker": "retrieval_worker",
            "policy_tool_worker": "policy_tool_worker"
        }
    )

    # Các worker đều dẫn về Synthesis
    workflow.add_edge("retrieval_worker", "synthesis_worker")
    workflow.add_edge("policy_tool_worker", "synthesis_worker")
    
    # Synthesis kết thúc graph
    workflow.add_edge("synthesis_worker", END)

    # Compile app
    app = workflow.compile()
    
    def run(state: AgentState) -> AgentState:
        import time
        start = time.time()
        
        # Chạy LangGraph invoke
        result = app.invoke(state)
        
        result["latency_ms"] = int((time.time() - start) * 1000)
        result["history"].append(f"[graph] LangGraph execution completed in {result['latency_ms']}ms")
        return result

    return run


# ─────────────────────────────────────────────
# 7. Public API
# ─────────────────────────────────────────────

_graph = build_graph()


def run_graph(task: str) -> AgentState:
    """
    Entry point: nhận câu hỏi, trả về AgentState với full trace.

    Args:
        task: Câu hỏi từ user

    Returns:
        AgentState với final_answer, trace, routing info, v.v.
    """
    state = make_initial_state(task)
    result = _graph(state)
    return result


def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    """Lưu trace ra file JSON."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/{state['run_id']}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return filename


# ─────────────────────────────────────────────
# 8. Manual Test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Day 09 Lab — TIP-001: Scaffold, Supervisor & HITL")
    print("=" * 60)

    # Acceptance Criteria
    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
        "Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?",
    ]

    for query in test_queries:
        print(f"\n> Testing Query: {query}")
        result = run_graph(query)
        print(f"  Route     : {result['supervisor_route']}")
        print(f"  Risk High : {result['risk_high']}")
        print(f"  Logic Reason: {result['route_reason']}")
        print(f"  Trace File: artifacts/traces/{result['run_id']}.json")

        # Lưu trace
        save_trace(result)

    print("\nReady for Sprint 2.")
