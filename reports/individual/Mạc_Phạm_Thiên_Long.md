# Individual report — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Mạc Phạm Thiên Long 
**Vai trò trong nhóm:** MCP Owner  
**Ngày nộp:** 14/04/2026

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Trong dự án này, em chịu trách nhiệm chính về hạ tầng cung cấp các tools cho hệ thống thông qua giao thức MCP (Model Context Protocol). Em đã thiết kế và triển khai 1 server MCP độc lập giúp các workers như `policy_tool_worker` có thể tương tác với cơ sở dữ liệu và hệ thống nghiệp vụ normalized.
**Module/file tôi chịu trách nhiệm:**
- File chính: `mcp_server.py`
- Functions em implement: `tool_search_kb`, `tool_get_ticket_info`, `tool_check_access_permission`, `dispatch_tool` và kiến trúc HTTP Server bằng FastAPI.

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Công việc của em là trục "xương sống" cho toàn bộ các tool execution. `policy_tool_worker` gọi các tool HTTP của em để kiểm tra quyền truy cập và tra cứu ticket. Kết quả từ MCP tool sau đó được truyền sang `synthesis_worker` để trả lời khách hàng.

**Bằng chứng:**
Tệp `mcp_server.py` chứa toàn bộ logic xử lý tool và transport layer qua port 8000.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Sử dụng transport layer dựa trên HTTP (FastAPI) thay vì gọi hàm trực tiếp (in-process) cho MCP tool.

**Lý do:**
Ban đầu, nhóm định dùng cách gọi hàm trực tiếp để tiết kiệm tài nguyên. Tuy nhiên, em đã đề xuất tách biệt MCP server thành một tiến trình độc lập chạy qua HTTP. Quyết định này giúp hệ thống mô phỏng đúng kiến trúc Microservices thực tế, cho phép mở rộng tool mà không cần sửa đổi logic lõi của Agent. Ngoài ra, việc dùng HTTP giúp chúng ta dễ dàng tích hợp thêm các công cụ viết bằng ngôn ngữ khác (ví dụ Node.js) trong tương lai.

**Trade-off đã chấp nhận:**
Latency tăng thêm khoảng 20-50ms cho mỗi lần gọi tool do độ trễ mạng mạng cục bộ và overhead của HTTP. Tuy nhiên, so với tổng latency của LLM (~2s-5s), con số này là không đáng kể.

**Bằng chứng từ code/trace:**
Trong `workers/policy_tool.py`, hàm `_call_mcp_tool` ưu tiên gọi qua HTTP endpoint trước khi dùng fallback:
```python
try:
    import httpx
    url = f"http://localhost:8000/tools/call/{tool_name}"
    resp = httpx.post(url, json=tool_input, timeout=5.0)
    ...
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Hệ thống trả về Accuracy = 0 trên toàn bộ tập grading questions.

**Symptom:** AI luôn trả lời "Không đủ thông tin trong tài liệu nội bộ" mặc dù các câu hỏi đều nằm trong phạm vi tài liệu.

**Root cause:** 
1. Lỗi tham số `max_tokens` không tương thích với model trong `synthesis_worker`.
2. Quan trọng nhất: Vector database (ChromaDB) trống do lỗi trong quá trình indexing ban đầu sử dụng không đúng mô hình Embedding.

**Cách sửa:**
Em đã trực tiếp viết lại script indexing và thực hiện nạp lại dữ liệu (re-indexing) sử dụng model `text-embedding-3-small` để đồng bộ hoàn toàn với logic của `retrieval_worker`. Đồng thời, tôi gỡ bỏ các tham số `max_tokens` gây lỗi API.

**Bằng chứng trước/sau:**
- **Trước**: Trace log `gq01` ghi nhận `score=0/10` và `final_answer="Không đủ thông tin"`.
- **Sau**: Chạy lại grading run, `gq01` đạt `score=10/10` với nội dung trích lục chính xác từ tệp `sla_p1_2026.txt`.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Em đã xử lý tốt phần hạ tầng, giúp hệ thống có khả năng mở rộng cao. Đặc biệt, việc em chủ động xử lý sự cố Accuracy=0 đã cải thiện kết quả cuối cùng của cả nhóm.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Em chưa tối ưu được việc gọi song song các MCP tools dẫn đến latency tổng thể vẫn còn ở mức trung bình (~8.5s).

**Nhóm phụ thuộc vào tôi ở đâu?**
Toàn bộ `policy_tool_worker` sẽ bị tê liệt nếu em không hoàn thiện MCP server hoặc nếu các công cụ `check_access` trả về kết quả sai định dạng contract.

**Phần tôi phụ thuộc vào thành viên khác:**
Em cần Nguyễn Doãn Hiếu (Supervisor) chuyển tham số input đúng định dạng JSON Schema mà em đã định nghĩa trong `TOOL_SCHEMAS`.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Em sẽ thử triển khai cơ chế **Parallel Tool Calling** vì trace của câu `gq09` cho thấy hệ thống phải đợi tuần tự từng thành phần, khiến latency lên tới gần 10 giây cho một câu hỏi phức tạp.

---

