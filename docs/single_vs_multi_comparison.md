# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** C401-E2

**Ngày:** 14/04/2026

---

## 1. Metrics Comparison

Dưới đây là bảng so sánh thực tế giữa phiên bản RAG đơn lẻ (Day 08) và Hệ thống Multi-Agent (Day 09) sau khi đã index Knowledge Base hoàn chỉnh.

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg accuracy | ~6.5 / 10 | **8.8 / 10** | +2.3 | Multi-agent có grounding cực tốt. |
| Avg latency (ms) | ~5,200 ms | **~8,500 ms** | +3.3s | Thêm bước supervisor và HITL. |
| Abstain rate (%) | ~5% | **~10%** | +5% | Thận trọng hơn khi không thấy docs. |
| Multi-hop accuracy | 40% | **90%** | +50% | Xử lý tốt các câu hỏi P1 + Access. |
| Routing visibility | ✗ Không có | **✓ Có route_reason** | N/A | Minh bạch hóa quá trình suy nghĩ. |
| Debug time (est) | ~20 phút | **~5 phút** | -15 phút | Khoanh vùng lỗi nhanh nhờ trace log. |

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | 90% | 100% |
| Latency | Rất nhanh (~4s) | Khá nhanh (~6-7s) |
| Observation | Hay bị dư thừa thông tin. | Trả lời súc tích, trích dẫn đúng file. |

**Kết luận:** Multi-agent đạt độ chính xác tuyệt đối nhưng tốn thêm một chút thời gian cho bước Supervisor điều phối.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | 40% | 90% |
| Routing visible? | ✗ | ✓ |
| Observation | Chỉ trả lời được một vế của câu hỏi. | Kết hợp nhuần nhuyễn thông tin từ nhiều file Docs. |

**Kết luận:** Kiến trúc Multi-Agent là bắt buộc cho các yêu cầu phức tạp cần tổng hợp dữ liệu từ nhiều nguồn khác nhau.

### 2.3 Câu hỏi cần abstain (Không có trong tài liệu)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | Thấp (Hay cố bịa - Hallucinate) | Cao (Thành thật từ chối) |
| Hallucination cases | 20% | 0% |
| Observation | Tự tạo ra quy trình IT không có thật. | Trả lời đúng form: "Không đủ thông tin". |

**Kết luận:** Khả năng kiểm soát Hallucination của Multi-Agent vượt xa Single Agent nhờ prompt chuyên biệt cho Synthesis Worker.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
Khi có câu trả lời sai, chúng ta phải đoán xem lỗi nằm ở bước Retrieval hay do Prompt Engineering. Việc sửa đổi một prompt "khổng lồ" thường dẫn tới lỗi ở các kịch bản khác.

### Day 09 — Debug workflow
Đọc file `artifacts/grading_run.jsonl` hoặc các trace cá nhân. Chúng ta biết chính xác Supervisor đã route đi đâu. 
Ví dụ: Nếu `gq07` (Mức phạt tài chính) bị điểm 0, chúng ta kiểm tra ngay `retrieval_worker` và thấy rằng tài liệu gốc thực sự không chứa thông tin mức phạt -> **Lỗi do dữ liệu đầu vào**, không phải lỗi logic.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa lại toàn bộ prompt gốc. | Thêm 1 tool vào MCP Server. |
| Thêm 1 worker mới | Khó thực hiện (monolith). | Đăng ký thêm 1 node vào StateGraph. |
| Thay đổi Model | Thay cho toàn bộ hệ thống. | Có thể dùng GPT-4 cho Supervisor và GPT-3.5 cho Retrieval. |

---

## 5. Cost & Latency Trade-off

Hệ thống Day 09 tiêu tốn trung bình **1.5x - 2x token** so với Day 08 do mỗi yêu cầu phải đi qua ít nhất 2 lời gọi LLM (Supervisor + Synthesis). Tuy nhiên, chi phí này hoàn toàn xứng đáng đổi lấy độ chính xác cao hơn và khả năng kiểm soát rủi ro thông qua HITL.

---

## 6. Kết luận

1. **Multi-Agent** là lựa chọn tối ưu cho các hệ thống Enterprise đòi hỏi tính minh bạch, độ chính xác cao và khả năng mở rộng tốt.
2. **Single Agent** phù hợp cho các bản prototype nhanh hoặc các tác vụ tra cứu đơn giản trên tập data nhỏ.
3. **Bài học lớn nhất**: Việc phân tách vai trò (Separation of Concerns) giúp AI hoạt động ổn định và dễ kiểm soát hơn rất nhiều so với việc cố gắng làm tất cả trong một lời gọi duy nhất.
