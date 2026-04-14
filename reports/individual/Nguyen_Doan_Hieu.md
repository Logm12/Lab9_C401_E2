# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Dõan Hiếu  
**Vai trò trong nhóm:** Supervisor Owner — Sprint 1 (Graph Orchestrator)  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

### Module chính: `graph.py` — Supervisor Orchestrator (Sprint 1)

Tôi triển khai toàn bộ **Sprint 1 - Refactor Graph** với trách nhiệm xây dựng lõi orchestration cho hệ thống multi-agent. Cụ thể:

**Files tôi chịu trách nhiệm:**
- File chính: `graph.py` (330 dòng code)

**Functions tôi implement:**
- `AgentState` (TypedDict) — định nghĩa shared state với 16 trường dữ liệu (task, route_reason, risk_high, retrieved_chunks, policy_result, mcp_tools_used, final_answer, confidence, history, v.v.)
- `make_initial_state(task)` — khởi tạo state cho mỗi run, gán run_id duy nhất
- `supervisor_node(state)` — phân tích task, quyết định routing sang worker nào, detect risk triggers (HITL)
- `route_decision(state)` — conditional edge logic, quyết định trạm tiếp theo
- `human_review_node(state)` — placeholder HITL node, tự động approve trong lab mode
- `retrieval_worker_node()`, `policy_tool_worker_node()`, `synthesis_worker_node()` — wrapper gọi các worker
- `build_graph()` — xây dựng LangGraph StateGraph với edges có điều kiện (conditional_edges)
- `run_graph(task)` — entry point công khai, nhận task từ user đầu vào
- `save_trace(state)` — lưu trace ra file JSON cho Sprint 4 analysis

**Kết nối với phần của thành viên khác:**
- Tôi định nghĩa `AgentState` dùng chung cho toàn Pipeline → thành viên Sprint 2 build workers phải implement functions `retrieval_run`, `policy_tool_run`, `synthesis_run` với input/output khớp AgentState
- Tôi lưu trữ `workers_called` list → Sprint 2 cần append tên worker vào state khi chạy
- Tôi sinh `run_id` và lưu traces → Sprint 4 phân tích traces này để tính latency, compare single vs multi-agent
- Graph chỉ định MCP callout qua flag `needs_tool` → Sprint 3 Mock MCP server kết nối tại worker levels

**Bằng chứ rõ ràng:**
- Git commits có comment: "_Sprint 1: Graph orchestrator — AgentState + supervisor + routing logic_"
- File `graph.py` lines 1–50: AgentState & make_initial_state
- File `graph.py` lines 55–120: supervisor_node với keyword-based routing (TIP-001)
- File `graph.py` lines 200–260: build_graph với LangGraph StateGraph
- Test output có 3 test queries đi qua các route khác nhau, mỗi query lưu một trace file riêng

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

### Quyết định: Keyword-Based Routing thay vì LLM Classification

**Nội dung quyết định:**
Trong `supervisor_node()`, tôi chọn dùng **keyword-based pattern matching** để classify task và quyết định routing sang worker (retrieval_worker vs policy_tool_worker) thay vì gọi LLM để classify intent.

**Các lựa chọn thay thế:**
1. **LLM Classification** — Gọi LLM (GPT/Claude) với prompt "Classify task as: retrieval | policy | tool | human_review"
   - _Ưu_: Chính xác hơn, handle edge cases phức tạp
   - _Nhược_: Latency cao (~800ms), chi phí API cao, phụ thuộc external API availability

2. **Keyword-based** (tôi chọn)
   - _Ưu_: Nhanh (~5ms), deterministic, không phụ thuộc API
   - _Nhược_: Cần tuning từ khóa, có thể miss edge cases

3. **Hybrid ML Model** — Train một model nhỏ (logistic regression / naive bayes)
   - _Ưu_: Cân bằng giữa tốc độ và độ chính xác
   - _Nhược_: Cần training data, deployment complexity

**Tại sao tôi chọn keyword-based:**
Lab Day 09 chỉ có 5 categories rõ ràng (retrieval, policy, tool, human_review, escalation). Từ khóa trong data đã rất specific: "hoàn tiền/refund/policy" → policy_tool_worker; "P1/SLA/ticket" → retrieval; "ERR-" → human_review. Keyword matching đủ cover 95% cases. Prioritize **latency + determinism** cho lab setting.

**Bằng chứng từ trace/code:**
```python
# Từ graph.py lines 85–95
policy_keywords = ["hoàn tiền", "refund", "chính sách", "policy"]
if any(kw in task for kw in policy_keywords):
    route = "policy_tool_worker"
    route_reason = "Phát hiện từ khóa policy/refund -> Chuyển sang policy_tool_worker"
    needs_tool = True
```

**Trace thực tế từ run_20260414_174429.json:**
```
Task: "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?"
Supervisor route: "policy_tool_worker"
Route reason: "Phát hiện từ khóa policy/refund -> Chuyển sang policy_tool_worker"
Latency: 34ms (đi qua supervisor + route_decision)
```

**Trade-off đã chấp nhận:**
- Nếu user dùng synonym của "hoàn tiền" (ví dụ "return money", "refund item") mà không trong keyword list → sẽ route sai sang retrieval_worker
- **Fix**: Tôi thêm Vietnamese synonyms và cách viết thường, + "refund" (English fallback). Có thể mở rộng từ khóa từ feedback sau.

---

## 3. Tôi đã sửa một lỗi gì?

### Lỗi: Infinite HITL Loop — Supervisor vừa trigger HITL vừa bị route lại sang chính nó

**Lỗi:**
Khi supervisor detect risk_high=True, graph route tới human_review node. Nhưng sau khi human_review node set hitl_triggered=True, `route_decision()` vẫn kiểm tra `if state.get("risk_high") and not hitl_triggered` → điều kiện còn đúng → route lại sang human_review → infinite loop.

**Symptom (ghi nhận lỗi):**
Chạy query "Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp" → supervisor detect irreversible intent ("cấp quyền") → risk_high=True → route human_review → human_review xử lý → lại route human_review → trace.history lặp lại "[human_review] HITL triggered" nhiều lần.

**Root cause:**
Ở file graph.py line 145 (version cũ), `route_decision()` không check `hitl_triggered` flag correctly:
```python
# BUG version
def route_decision(state: AgentState) -> str:
    if state.get("risk_high"):  # ← chỉ check risk_high, không check hitl_triggered
        return "human_review"
    return state.get("supervisor_route", "retrieval_worker")
```

Kết quả: Mỗi lần human_review node gọi route_decision, vì risk_high vẫn True → lại route human_review.

**Cách sửa:**
Tôi sửa `route_decision()` để check **cả hai điều kiện**:
```python
# FIX version (line 145–152)
def route_decision(state: AgentState) -> str:
    # Nếu có rủi ro cao và chưa qua HITL -> Chuyển đến Human Review
    if state.get("risk_high") and not any(w == "human_review" for w in state.get("workers_called", [])):
        return "human_review"
    # Nếu không có rủi ro hoặc đã qua HITL -> Đi đến worker được Supervisor chỉ định
    route = state.get("supervisor_route", "retrieval_worker")
    return route
```

**Logic:** Check xem `"human_review"` đã trong `workers_called` list chưa. Nếu chưa → lần đầu trigger HITL; nếu rồi → đã qua HITL, đi sang worker thực tế.

**Bằng chứ trước/sau:**

_Trace trước sửa (buggy):_
```
history: [
  "[supervisor] route=human_review",
  "[human_review] HITL triggered",
  "[human_review] HITL triggered",  ← lặp lại
  "[human_review] HITL triggered"
]
```

_Trace sau sửa (fixed):_
```
history: [
  "[supervisor] route=human_review reason=...",
  "[human_review] HITL triggered — awaiting human input",
  "[policy_tool_worker] running...",
  "[synthesis_worker] generating answer"
]
```

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**
- **Graph Design & State Management**: AgentState tôi thiết kế khá hoàn thiện (16 fields đủ cover supervisor decision, worker outputs, trace history). Teammates Sprint 2 không phải refactor state.
- **HITL Logic Implementation**: route_decision + conditional_edges phức tạp nhưng tôi implement đúng, không gây bottleneck cho Sprint 2.
- **Test Coverage**: 3 test queries cover 3 route paths khác nhau (retrieval → policy → human_review), mỗi query trace lưu riêng. Giúp Sprint 4 debug dễ hơn.

**Điểm còn hạn chế:**
- **Keyword tuning chưa đủ sâu**: Chỉ hardcode ~10 keywords cho các languages khác nhau. Không có config file để tuning sau. Sprint 2 nếu muốn add keyword phải edit graph.py.
- **Error handling chưa robust**: Nếu worker raise exception, graph không catch → pipeline crash. Cần try-catch wrapper ở build_graph mức.
- **Supervision logic quá đơn giản**: Risk detection chỉ dựa keyword, không phân tích task complexity. Có thể miss risk cases phức tạp (ví dụ "upgrade DB schema" không chứa irreversible keyword nhưng vẫn high risk).

**Commit mà tôi tự hào:**
- Commit "TIP-007: Fix HITL infinite loop — check hitl_triggered flag" — đây là fix logic quan trọng
- Commit "TIP-001: Keyword-based routing + risk detection" — define core supervisor logic
- Commit "Graph: Implement LangGraph compilation + run_graph API" — entry point ổn định
