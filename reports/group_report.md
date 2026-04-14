# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Helpdesk Orchestrator Team  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Nguyễn Văn A | Supervisor Owner | a@example.com |
| Cao Chí Hải | Worker Owner | caochihai1710@gmail.com |
| Lê Văn C | MCP Owner | c@example.com |
| Phạm Thị D | Trace & Docs Owner | d@example.com |

**Ngày nộp:** 2026-04-14  
**Repo:** https://github.com/example/lab9  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Hướng dẫn nộp group report:**
> 
> - File này nộp tại: `reports/group_report.md`
> - Deadline: Được phép commit **sau 18:00** (xem SCORING.md)
> - Tập trung vào **quyết định kỹ thuật cấp nhóm** — không trùng lặp với individual reports
> - Phải có **bằng chứng từ code/trace** — không mô tả chung chung
> - Mỗi mục phải có ít nhất 1 ví dụ cụ thể từ code hoặc trace thực tế của nhóm

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

> Mô tả ngắn gọn hệ thống nhóm: bao nhiêu workers, routing logic hoạt động thế nào,
> MCP tools nào được tích hợp. Dùng kết quả từ `docs/system_architecture.md`.

**Hệ thống tổng quan:**
Nhóm đã xây dựng hệ thống Multi-Agent Orchestration sử dụng LangGraph với 4 nodes chính: Supervisor, Human Review (HITL), Retrieval Worker, Policy Tool Worker, và Synthesis Worker. Supervisor phân tích task và route dựa trên keywords, trigger HITL cho các actions rủi ro cao. Retrieval Worker tìm evidence từ ChromaDB, Policy Tool Worker kiểm tra policy và gọi MCP tools, Synthesis Worker tổng hợp answer grounded.

**Routing logic cốt lõi:**
Supervisor sử dụng keyword-based routing: tasks chứa "hoàn tiền", "refund" → policy_tool_worker; mặc định → retrieval_worker. HITL trigger khi detect irreversible intents ("tạo", "xóa"), error codes ("ERR-"), hoặc risk keywords ("khẩn cấp"). Logic này đảm bảo safety và accuracy, với route_reason ghi rõ lý do.

**MCP tools đã tích hợp:**
- `search_kb`: Tìm kiếm knowledge base, gọi từ retrieval_worker khi không có chunks.
- `get_ticket_info`: Lấy chi tiết ticket, gọi từ policy_tool_worker cho tasks liên quan P1/SLA.
- `check_access_permission`: Kiểm tra quyền truy cập, gọi cho tasks cấp quyền Level 3.

Ví dụ trace `run_20260414_162603.json`: Task "Cần cấp quyền Level 3 khẩn cấp" → route policy_tool_worker → gọi MCP check_access_permission → HITL triggered.

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

> Chọn **1 quyết định thiết kế** mà nhóm thảo luận và đánh đổi nhiều nhất.
> Phải có: (a) vấn đề gặp phải, (b) các phương án cân nhắc, (c) lý do chọn phương án đã chọn.

**Quyết định:** Chọn Supervisor-Worker pattern thay vì Single Agent, với keyword-based routing và HITL.

**Bối cảnh vấn đề:**
Trong Day 08, Single Agent gặp khó khăn với multi-hop questions (chỉ trả lời 40% chính xác), hallucination cao (20%), và debug khó khi sai. Nhóm cần refactor để xử lý tốt hơn các tasks phức tạp như P1 + Access, và đảm bảo safety cho actions nhạy cảm.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Giữ Single Agent, tối ưu prompt | Nhanh deploy, ít code | Khó mở rộng, hallucination cao |
| LLM Classifier routing | Chính xác hơn keyword | Chậm hơn (~800ms vs 5ms), tốn token |
| Rule-based routing + HITL | An toàn, debug dễ | Latency cao hơn |

**Phương án đã chọn và lý do:**
Chọn Supervisor-Worker với keyword routing + HITL vì balance giữa speed, safety, và extensibility. Keyword routing đủ chính xác cho 5 categories, HITL đảm bảo human oversight cho risk tasks. Trade-off: latency tăng 3s nhưng accuracy +2.3 điểm, debug time giảm từ 20p xuống 5p.

**Bằng chứng từ trace/code:**
Trong `graph.py` line 101-130, keyword routing logic: if "hoàn tiền" in task → policy_tool_worker. Trace `run_20260414_162603.json` show route_reason='Phát hiện từ khóa policy/refund', latency=8500ms nhưng confidence=0.88, HITL triggered=True.

```
# Routing code snippet:
if any(kw in task for kw in policy_keywords):
    route = "policy_tool_worker"
    route_reason = "Phát hiện từ khóa policy/refund -> Chuyển sang policy_tool_worker"
```

---

## 3. Kết quả grading questions (150–200 từ)

> Sau khi chạy pipeline với grading_questions.json (public lúc 17:00):
> - Nhóm đạt bao nhiêu điểm raw?
> - Câu nào pipeline xử lý tốt nhất?
> - Câu nào pipeline fail hoặc gặp khó khăn?

**Tổng điểm raw ước tính:** 85 / 96 (88.5%)

**Câu pipeline xử lý tốt nhất:**
- ID: gq01 — Lý do tốt: Task "SLA ticket P1 là bao lâu?" → route retrieval_worker → retrieved chunks từ sla_p1_2026.txt → synthesis answer chính xác, confidence=0.95, latency=6500ms.

**Câu pipeline fail hoặc partial:**
- ID: gq07 — Fail ở đâu: Abstain không đúng, trả lời hallucination về "mức phạt tài chính". Root cause: Retrieval không tìm được chunks liên quan, policy_result trống → synthesis bịa đặt.

**Câu gq07 (abstain):** Nhóm xử lý bằng cách thêm logic abstain trong synthesis_worker nếu confidence <0.7 hoặc "Không đủ thông tin" trong answer.

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers: retrieval_worker (chunks từ sla_p1_2026.txt) + policy_tool_worker (MCP get_ticket_info) → synthesis kết hợp thành answer đầy đủ, multi_hop_success=True.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

> Dựa vào `docs/single_vs_multi_comparison.md` — trích kết quả thực tế.

**Metric thay đổi rõ nhất (có số liệu):**
Accuracy tăng từ 6.5/10 lên 8.8/10 (+2.3), latency tăng từ 5200ms lên 8500ms (+3300ms), abstain rate tăng từ 5% lên 10% (+5%), multi-hop accuracy từ 40% lên 90% (+50%).

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**
HITL trigger rate 100% cho safety, nhưng auto-approve trong lab làm latency tăng không cần thiết. Multi-agent debug dễ hơn nhờ trace logs rõ ràng worker nào sai.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**
Tasks đơn giản như "SLA P1 là bao lâu?" — single agent nhanh hơn 3s, multi-agent thêm bước supervisor không cần thiết.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

> Đánh giá trung thực về quá trình làm việc nhóm.

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Nguyễn Văn A | Implement supervisor & graph.py, routing logic | Sprint 1 |
| Trần Thị B | Implement workers (retrieval, policy_tool, synthesis) | Sprint 2 |
| Lê Văn C | MCP server & tools integration | Sprint 3 |
| Phạm Thị D | Eval, traces, docs & reports | Sprint 4 |

**Điều nhóm làm tốt:**
Phân công rõ ràng theo sprint, phối hợp tốt qua Git commits. Code reviews kịp thời, trace logs đầy đủ giúp debug nhanh.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**
Đôi lúc overlap khi implement contracts — worker owner quên update status trong contracts.yaml. Communication qua Slack chậm khi gặp blocker MCP.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**
Setup daily standup 15p để sync progress, và dùng GitHub Issues cho task tracking thay vì chỉ chat.

**Ngày nộp:** ___________  
**Repo:** ___________  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Hướng dẫn nộp group report:**
> 
> - File này nộp tại: `reports/group_report.md`
> - Deadline: Được phép commit **sau 18:00** (xem SCORING.md)
> - Tập trung vào **quyết định kỹ thuật cấp nhóm** — không trùng lặp với individual reports
> - Phải có **bằng chứng từ code/trace** — không mô tả chung chung
> - Mỗi mục phải có ít nhất 1 ví dụ cụ thể từ code hoặc trace thực tế của nhóm

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

> Mô tả ngắn gọn hệ thống nhóm: bao nhiêu workers, routing logic hoạt động thế nào,
> MCP tools nào được tích hợp. Dùng kết quả từ `docs/system_architecture.md`.

**Hệ thống tổng quan:**

_________________

**Routing logic cốt lõi:**
> Mô tả logic supervisor dùng để quyết định route (keyword matching, LLM classifier, rule-based, v.v.)

_________________

**MCP tools đã tích hợp:**
> Liệt kê tools đã implement và 1 ví dụ trace có gọi MCP tool.

- `search_kb`: ___________________
- `get_ticket_info`: ___________________
- ___________________: ___________________

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

> Chọn **1 quyết định thiết kế** mà nhóm thảo luận và đánh đổi nhiều nhất.
> Phải có: (a) vấn đề gặp phải, (b) các phương án cân nhắc, (c) lý do chọn phương án đã chọn.

**Quyết định:** ___________________

**Bối cảnh vấn đề:**

_________________

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| ___ | ___ | ___ |
| ___ | ___ | ___ |

**Phương án đã chọn và lý do:**

_________________

**Bằng chứng từ trace/code:**
> Dẫn chứng cụ thể (VD: route_reason trong trace, đoạn code, v.v.)

```
[NHÓM ĐIỀN VÀO ĐÂY — ví dụ trace hoặc code snippet]
```

---

## 3. Kết quả grading questions (150–200 từ)

> Sau khi chạy pipeline với grading_questions.json (public lúc 17:00):
> - Nhóm đạt bao nhiêu điểm raw?
> - Câu nào pipeline xử lý tốt nhất?
> - Câu nào pipeline fail hoặc gặp khó khăn?

**Tổng điểm raw ước tính:** ___ / 96

**Câu pipeline xử lý tốt nhất:**
- ID: ___ — Lý do tốt: ___________________

**Câu pipeline fail hoặc partial:**
- ID: ___ — Fail ở đâu: ___________________  
  Root cause: ___________________

**Câu gq07 (abstain):** Nhóm xử lý thế nào?

_________________

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers không? Kết quả thế nào?

_________________

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

> Dựa vào `docs/single_vs_multi_comparison.md` — trích kết quả thực tế.

**Metric thay đổi rõ nhất (có số liệu):**

_________________

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

_________________

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

_________________

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

> Đánh giá trung thực về quá trình làm việc nhóm.

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| ___ | ___________________ | ___ |
| ___ | ___________________ | ___ |
| ___ | ___________________ | ___ |
| ___ | ___________________ | ___ |

**Điều nhóm làm tốt:**

_________________

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**

_________________

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**

_________________

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

> 1–2 cải tiến cụ thể với lý do có bằng chứng từ trace/scorecard.

_________________

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
