# System Architecture — Lab Day 09

**Nhóm:** Helpdesk Orchestrator Team
**Ngày:** 14/04/2026
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

Hệ thống được thiết kế theo mô hình **Multi-Agent Orchestration** sử dụng **LangGraph**. Thay vì sử dụng một Single Agent duy nhất để xử lý mọi yêu cầu, chúng tôi phân tách logic thành các Worker chuyên biệt được điều phối bởi một Supervisor trung tâm.

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**
- **Khả năng kiểm soát**: Supervisor có thể đánh giá rủi ro (Risk Assessment) trước khi chuyển việc cho Worker, cho phép kích hoạt Human-In-The-Loop (HITL) một cách linh hoạt.
- **Độ chính xác**: Mỗi Worker được tối ưu hóa với prompt và tool riêng (ví dụ: Policy Tool xử lý tập trung vào luật lệ, Retrieval chỉ tập trung vào tìm kiếm evidence).
- **Khả năng mở rộng**: Dễ dàng thêm các Worker mới (ví dụ: Worker xử lý riêng cho Technical Debugging) mà không làm loãng prompt của hệ thống chính.

---

## 2. Sơ đồ Pipeline

Hệ thống sử dụng **LangGraph StateGraph** để quản lý luồng trạng thái.

**Sơ đồ thực tế của nhóm (Mermaid raw code):**

<p align="center">
  <img src="Architechture Diagram.png" width="400">
</p>

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích intent của người dùng và đánh giá rủi ro tiềm ẩn. |
| **Input** | Câu hỏi thô từ người dùng (`task`). |
| **Output** | `supervisor_route`, `route_reason`, `risk_high`. |
| **Routing logic** | Sử dụng LLM (gpt-4o-mini) để phân loại vào `policy_tool_worker` (nếu liên quan đến hoàn tiền/quy định) hoặc `retrieval_worker` (thông tin chung). |
| **HITL condition** | Kích hoạt khi phát hiện mã lỗi (ERR-), yêu cầu xóa/tạo dữ liệu, hoặc yêu cầu quyền truy cập mức độ cao (Level 3). |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Tìm kiếm thông tin liên quan trong cơ sở dữ liệu tri thức. |
| **Embedding model** | `text-embedding-3-small` (OpenAI). |
| **Top-k** | 3 - 5 đoạn văn bản (chunks). |
| **Stateless?** | Yes |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Thực hiện các kiểm tra nghiệp vụ phức tạp (Refund, Access Control). |
| **MCP tools gọi** | `search_kb`, `get_ticket_info`, `check_access_permission`. |
| **Exception cases xử lý** | Đơn hàng Flash Sale, đơn hàng ngoài phạm vi thời gian (Temporal Scoping). |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | `gpt-4o-mini` (Pure OpenAI). |
| **Temperature** | 0.0 (Đảm bảo tính chính xác và bám sát tài liệu). |
| **Grounding strategy** | Chỉ trả lời dựa trên `retrieved_chunks` và `policy_result`, trích dẫn nguồn bằng [file_name]. |
| **Abstain condition** | Trả lời "Không đủ thông tin" nếu context trống hoặc không liên quan. |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| search_kb | query, top_k | chunks, sources |
| get_ticket_info | ticket_id | Chi tiết ticket Jira |
| check_access_permission | access_level, requester_role | Kết quả can_grant và danh sách người duyệt |
| create_ticket | priority, title, desc | ID ticket mới tạo |

---

## 4. Shared State Schema

Sử dụng `TypedDict` để quản lý trạng thái luân chuyển giữa các node.

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| task | str | Câu hỏi đầu vào của người dùng | Supervisor đọc |
| supervisor_route | str | Định danh worker được chọn để xử lý | Supervisor ghi, Router đọc |
| route_reason | str | Giải thích lý do lựa chọn routing | Supervisor ghi |
| risk_high | bool | Cờ đánh dấu rủi ro để kích hoạt HITL | Supervisor ghi |
| retrieved_chunks | list | Danh sách evidence tìm được | Retrieval ghi, Synthesis đọc |
| policy_result | dict | Kết quả phân tích luật lệ | Policy ghi, Synthesis đọc |
| final_answer | str | Câu trả lời cuối cùng đã format | Synthesis ghi |
| confidence | float | Độ tin cậy của câu trả lời | Synthesis ghi |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — phải đọc lại toàn bộ prompt dài và xem log LLM mịt mờ. | Dễ — trace log chỉ rõ Supervisor quyết định sai hay Worker thực thi sai. |
| Thêm capability mới | Phải nhồi nhét thêm logic vào Agent duy nhất, dễ gây hallucination. | Chỉ cần đăng ký thêm 1 Worker hoặc 1 MCP Tool mới. |
| Routing visibility | Không có — Agent tự gọi tool ngầm. | Minh bạch — lý do routing được lưu lại (`route_reason`). |
| RAG Quality | Bị giới hạn bởi ngữ cảnh (context) bị loãng. | Tối ưu nhờ mỗi Agent chỉ xử lý một tập ngữ cảnh nhỏ, chuyên sâu. |

**Nhóm điền thêm quan sát từ thực tế lab:**
Hệ thống Multi-Agent giúp giảm thiểu tình trạng LLM "quên" quy định khi xử lý các yêu cầu phức tạp (như hoàn tiền Flash Sale), do Policy Worker được ép buộc phải kiểm tra qua code/SOP trước khi tổng hợp.

---

## 6. Giới hạn và điểm cần cải tiến

1. **Hiệu năng**: Quá trình đi qua nhiều node (Supervisor -> HITL -> Worker -> Synthesis) làm tăng latency so với Single Agent.
2. **Chi phí**: Tốn nhiều token hơn do phải thực hiện nhiều lời gọi LLM cho các bước điều phối trung gian.
3. **Cơ chế HITL**: Hiện tại đang tự động duyệt (auto-approve) trong môi trường lab, cần giao diện UI để người dùng thực duyệt trong thực tế.
