# Routing Decisions Log — Lab Day 09

**Nhóm:** C401-E2
**Ngày:** 14/04/2026

---

## Routing Decision #1 (Retrieval Case)

**Task đầu vào:**
> Ticket P1 được tạo lúc 22:47. Đúng theo SLA, ai nhận thông báo đầu tiên và qua kênh nào? Deadline escalation là mấy giờ?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `Default routing to retrieval_worker`  
**MCP tools được gọi:** `search_kb` (qua retrieval_worker logic)  
**Workers called sequence:** `human_review` -> `retrieval_worker` -> `synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Thông báo được gửi đến On-call Engineer qua Slack [#incident-p1], Email và PagerDuty. Deadline escalation là 2:57 (10 phút sau khi tạo).
- confidence: 0.95
- Correct routing? Yes

**Nhận xét:**
Hệ thống nhận diện đúng đây là câu tra cứu thông tin vận hành. Mặc dù có trigger HITL do liên quan đến "Ticket P1", nhưng sau khi được duyệt, Retrieval Worker đã tìm đúng đoạn văn bản trong `sla_p1_2026.txt`.

---

## Routing Decision #2 (Policy & Tool Case)

**Task đầu vào:**
> Khách hàng đặt đơn ngày 31/01/2026 và gửi yêu cầu hoàn tiền ngày 07/02/2026 vì lỗi nhà sản xuất. Sản phẩm chưa kích hoạt, không phải Flash Sale, không phải kỹ thuật số. Chính sách nào áp dụng và có được hoàn tiền không?

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `Phát hiện intent thực hiện hành động (gửi) -> Cần HITL phê duyệt`  
**MCP tools được gọi:** `search_kb`  
**Workers called sequence:** `human_review` -> `policy_tool_worker` -> `synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Khách hàng được hoàn tiền vì sản phẩm chưa kích hoạt và không vi phạm các ngoại lệ. Đơn hàng thuộc phạm vi chính sách hoàn tiền hiện hành.
- confidence: 0.85
- Correct routing? Yes

**Nhận xét:**
Supervisor đã gán nhãn `policy_tool_worker` chính xác nhờ phát hiện các từ khóa "hoàn tiền" và "chính sách". Việc sử dụng Policy Worker giúp kiểm tra các điều kiện loại trừ một cách có hệ thống trước khi trả lời.

---

## Routing Decision #3 (HITL & Emergency Case)

**Task đầu vào:**
> Sự cố P1 xảy ra lúc 2am. Đồng thời cần cấp Level 2 access tạm thời cho contractor để thực hiện emergency fix. Hãy nêu đầy đủ: (1) các bước SLA P1 notification phải làm ngay, và (2) điều kiện để cấp Level 2 emergency access.

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `Default routing to retrieval_worker | Cảnh báo: Task có độ rủi ro cao/khẩn cấp | human approved`  
**MCP tools được gọi:** `check_access_permission`  
**Workers called sequence:** `human_review` -> `retrieval_worker` -> `synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): (1) Notify qua Slack/Email/PagerDuty ngay lập tức. (2) Cấp Level 2 cần Manager phê duyệt trực tiếp, contractor phải có MFA và session bị giới hạn 4 giờ.
- confidence: 0.88
- Correct routing? Yes

**Nhận xét:**
Đây là câu hỏi phức tạp (multi-hop) đòi hỏi thông tin từ cả `sla_p1_2026.txt` và `access_control_sop.txt`. Supervisor đã kích hoạt HITL vì tính chất nhạy cảm của việc cấp quyền (Level 2) và tình trạng khẩn cấp.

---

## Tổng kết

### Routing Distribution (Dựa trên grading run)

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 6 | 60% |
| policy_tool_worker | 4 | 40% |
| human_review (HITL triggered) | 10 | 100% |

### Routing Accuracy

- Câu route đúng: 10 / 10
- Câu route sai: 0
- Câu trigger HITL: 10 (Sát sao theo chính sách an toàn của lab)

### Lesson Learned về Routing

1. **Safety First**: Việc cấu hình Supervisor luôn trigger HITL khi phát hiện intent "tạo/xóa" hoặc "quyền hạn" giúp hệ thống an toàn tuyệt đối trước các hành động nhạy cảm.
2. **Keyword Hinting**: Kết hợp gợi ý từ các từ khóa trong câu hỏi giúp Supervisor phân loại chính xác giữa các Worker chuyên biệt.
