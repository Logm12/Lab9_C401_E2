# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Helpdesk Orchestrator Team  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Nguyễn Doãn Hiếu | Supervisor Owner | chihieu3603@gmail.com |
| Cao Chí Hải | Worker Owner | caochihai1710@gmail.com |
| Mạc Phạm Thiên Long | MCP Owner | longmac321@gmail.com |
| Bùi Hữu Huấn | Trace & Docs Owner | anhhuanvg02@gmail.com |

**Ngày nộp:** 2026-04-14  
**Repo:** https://github.com/Logm12/Lab9_C401_E2.git
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Kiến trúc nhóm đã xây dựng

Nhóm xây dựng hệ thống Multi-Agent Orchestration dựa trên LangGraph và `graph.py`. Hệ thống gồm 5 nodes chính: Supervisor, Human Review (HITL), Retrieval Worker, Policy Tool Worker và Synthesis Worker.

Supervisor đọc `task`, ghi `supervisor_route`, `route_reason`, và đánh giá `risk_high`. `retrieval_worker` tìm evidence từ ChromaDB. `policy_tool_worker` kiểm tra policy, gọi MCP tools và trả về `policy_result`. `synthesis_worker` tổng hợp câu trả lời cuối cùng từ chunks và policy result. `human_review` là placeholder HITL khi task bị đánh dấu rủi ro.

**Routing logic cốt lõi:**
- Mặc định route sang `retrieval_worker`.
- Nếu task chứa keywords như "hoàn tiền", "refund", "chính sách", "policy" thì supervisor chuyển sang `policy_tool_worker`.
- Nếu task chứa intent "tạo", "xóa", "gửi", mã lỗi "ERR-" hoặc từ khóa khẩn cấp thì `risk_high=True`, và `route_reason` mở rộng để thể hiện HITL.

Đây là logic nằm trong `graph.py` line 101–133. `policy_keywords`, `irreversible_intents`, `error_code_trigger` và `risk_keywords` được dùng để phân loại task trước khi worker thực thi.

**MCP tools đã tích hợp:**
- `search_kb`: semantic search trong MCP Server, trả về chunks evidence.
- `get_ticket_info`: tra cứu chi tiết ticket P1/SLA.
- `check_access_permission`: kiểm tra cấp quyền Level 2/3 theo SOP.

**Ví dụ trace:**
Trace `artifacts/traces/run_20260413_225959.json` cho task "Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?". Supervisor route sang `policy_tool_worker` với `route_reason = "task contains policy/access keyword | risk_high flagged"`, rồi gọi `policy_tool_worker`, `retrieval_worker`, `synthesis_worker`.

---

## 2. Quyết định kỹ thuật quan trọng nhất

**Quyết định:** Chọn kiến trúc Supervisor-Worker thay vì giữ Single Agent.

**Vấn đề:**
Day 08 sử dụng Single Agent gặp khó khi xử lý multi-hop và policy-heavy tasks. Agent monolithic dễ hallucinate và thiếu minh bạch khi debug.

**Các phương án cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Single Agent tối ưu prompt | Triển khai nhanh | Hallucination cao, khó mở rộng |
| LLM classifier routing | Route chính xác hơn | Tăng latency/token, khó giải thích |
| Supervisor-Worker + HITL | Minh bạch, dễ debug, dễ mở rộng | Thêm overhead latency và token |

**Lý do chọn:**
Nhóm ưu tiên correctness và traceability. Supervisor-Worker giúp tách biệt nhiệm vụ: supervisor điều phối, worker xử lý domain riêng, synthesis tổng hợp. `route_reason` và trace log làm cho lỗi dễ khoanh vùng hơn.

**Bằng chứng code/trace:**
- `graph.py` line 101–130: `policy_keywords = ["hoàn tiền", "refund", "chính sách", "policy"]`.
- Trace `artifacts/traces/run_20260413_225959.json`: `supervisor_route = "policy_tool_worker"`, `route_reason = "task contains policy/access keyword | risk_high flagged"`.
- Trace `artifacts/traces/run_20260414_142701.json`: `route_reason = "Phát hiện intent thực hiện hành động (gửi) -> Cần HITL phê duyệt | human approved → retrieval"`.

---

## 3. Kết quả grading questions

**Tổng điểm raw ước tính:** 85 / 96 (88.5%).

**Câu xử lý tốt nhất:**
- `gq01` — "SLA ticket P1 là bao lâu?" route đúng sang `retrieval_worker`, tìm đúng chunk từ `sla_p1_2026.txt`, synthesis trả lời chính xác.

**Câu gặp khó khăn:**
- `gq07` — pipeline chưa abstain tốt, dẫn đến hallucination về "mức phạt tài chính". Nguyên nhân: evidence thiếu và policy_result không đủ thông tin.

**Khắc phục:**
- Bổ sung logic abstain trong `workers/synthesis.py`: nếu `confidence < 0.7` hoặc không có evidence phù hợp thì trả về "Không đủ thông tin".

**Câu multi-hop khó nhất:**
- `gq09` — trace cho thấy supervisor điều phối `policy_tool_worker` và `retrieval_worker`, rồi `synthesis_worker` tổng hợp hai nguồn. Điều này chứng tỏ multi-agent xử lý tốt các câu hỏi kết hợp SLA và access control.

---

## 4. So sánh Day 08 vs Day 09

Dựa vào `docs/single_vs_multi_comparison.md`, nhóm quan sát được:
- Accuracy tăng từ **6.5/10** lên **8.8/10**.
- Latency tăng từ **5.200 ms** lên **8.500 ms**.
- Multi-hop accuracy tăng từ **40%** lên **90%**.
- Abstain rate tăng từ **5%** lên **10%**.

**Quan sát:**
Multi-agent cải thiện độ chính xác và visibility, nhưng tăng latency vì thêm supervisor và HITL step.

**Khi multi-agent không cần thiết:**
Task đơn giản như "SLA P1 là bao lâu?" vẫn có thể chạy nhanh hơn với Single Agent. Overhead supervisor + HITL chỉ hợp lý khi task có nhiều yếu tố hoặc rủi ro.

---

## 5. Phân công và đánh giá nhóm

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Nguyễn Doãn Hiếu | Supervisor, `graph.py`, routing logic | Sprint 1 |
| Cao Chí Hải | `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py` | Sprint 2 |
| Mạc Phạm Thiên Long | `mcp_server.py`, MCP tool integration | Sprint 3 |
| Bùi Hữu Huấn | Trace analysis, docs, report | Sprint 4 |

**Điểm tốt:**
Phân công rõ ràng và có trace evidence. `contracts/worker_contracts.yaml` giúp làm rõ trách nhiệm của supervisor và worker.

**Điểm chưa tốt:**
Còn xảy ra chồng chéo khi cập nhật rule routing giữa `graph.py` và contract.

**Nếu làm lại:**
Sẽ dùng GitHub Issues và daily standup 15 phút để đồng bộ nhanh hơn khi thay đổi route logic hoặc MCP tools.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì?

**Ưu tiên cải tiến:**
- Hoàn thiện UX HITL để human review thật sự thay vì auto-approve lab mode.
- Mở rộng routing rule hoặc kết hợp classifier để giảm false positive cho `policy_tool_worker`.

**Lý do:**
Trace `run_20260414_142701.json` và `run_20260414_145841.json` cho thấy HITL flow đã trigger đúng nhưng vẫn cần giảm latency và tăng tính thực tế bằng human approval.
