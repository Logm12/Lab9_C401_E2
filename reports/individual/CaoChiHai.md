# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Cao Chí Hải
**Vai trò trong nhóm:** Worker Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ


## 1. Tôi phụ trách phần nào? (100–150 từ)

Tôi phụ trách việc implement các worker trong hệ thống Supervisor-Worker, cụ thể là ba file chính: `workers/retrieval.py`, `workers/policy_tool.py`, và `workers/synthesis.py`. Đây là Sprint 2 của lab, nơi chúng tôi refactor RAG pipeline thành hệ thống multi-agent với vai trò rõ ràng.

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py`
- Functions tôi implement: `retrieve_dense()` trong retrieval.py, `analyze_policy()` và `_call_mcp_tool()` trong policy_tool.py, `synthesize()` trong synthesis.py

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Công việc của tôi cung cấp các worker cho supervisor (được implement bởi thành viên khác trong graph.py). Retrieval worker cung cấp evidence, policy_tool worker kiểm tra policy và gọi MCP tools, synthesis worker tổng hợp answer cuối cùng. Điều này tạo thành pipeline hoàn chỉnh từ input task đến final answer.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
Các file worker có docstring mô tả rõ ràng input/output theo contract trong `contracts/worker_contracts.yaml`. Ví dụ, trong `workers/retrieval.py` line 15-20, có ghi "Input (từ AgentState): - task: câu hỏi cần retrieve", chứng minh tuân theo contract.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

Tôi quyết định sử dụng rule-based policy analysis kết hợp với LLM evaluation trong policy_tool worker, thay vì chỉ dùng LLM cho tất cả policy checks.

**Quyết định:** Chọn rule-based first pass cho policy analysis, sau đó dùng LLM để đánh giá MCP results và detect conflicts.

**Lý do:**
Rule-based nhanh hơn (~50ms vs ~800ms cho LLM call), chính xác cho các exception rõ ràng như Flash Sale, digital products. LLM chỉ dùng khi cần đánh giá conflicts giữa MCP data và internal docs, giảm cost và latency. Nếu confidence <0.5 hoặc detect "mâu thuẫn", trigger HITL.

**Trade-off đã chấp nhận:**
Rule-based có thể miss edge cases không được hardcode, nhưng coverage cao cho 80% cases phổ biến. LLM thêm layer validation nhưng tăng cost.

**Bằng chứng từ trace/code:**
Trong `workers/policy_tool.py` line 151-200, function `analyze_policy()` implement rule-based detection cho exceptions như flash_sale, digital_product. Line 280-320, LLM evaluation với `_llm_policy_analysis()` chỉ gọi khi needs_tool=True. Trace từ `artifacts/traces/` cho thấy latency giảm từ 800ms xuống 45ms cho policy checks đơn giản.

```
# Ví dụ code trong policy_tool.py:
if any(kw in task_lower for kw in ["flash sale", "flashsale"]):
    exceptions_found.append({
        "type": "flash_sale_exception",
        "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
    })
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

Tôi sửa lỗi trong retrieval worker khi ChromaDB collection chưa được tạo, dẫn đến crash khi query.

**Lỗi:** Retrieval worker crash với "ValueError: Collection 'day09_docs' does not exist" khi chạy lần đầu.

**Symptom (pipeline làm gì sai?):**
Khi gọi `run({"task": "SLA P1"})`, worker_io_logs ghi error "RETRIEVAL_FAILED", retrieved_chunks=[], pipeline dừng không có evidence.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**
Trong `_get_collection()`, code chỉ gọi `client.get_collection("day09_docs")` mà không handle case collection chưa tồn tại. ChromaDB throw exception thay vì auto-create.

**Cách sửa:**
Thêm try-except, nếu collection không tồn tại, auto-create với metadata cosine. Thêm print warning để user biết cần index data.

**Bằng chứng trước/sau:**
Trước sửa: Trace `run_20260414_142701.json` show error "Collection does not exist". Sau sửa: Trace `run_20260414_162603.json` show "retrieved 3 chunks from ['sla_p1_2026.txt']", latency=45ms.

Code sửa trong `workers/retrieval.py` line 60-70:
```
try:
    collection = client.get_collection("day09_docs")
except Exception:
    collection = client.get_or_create_collection(
        "day09_docs",
        metadata={"hnsw:space": "cosine"}
    )
    print(f"⚠️  Collection 'day09_docs' chưa có data. Chạy index script trong README trước.")
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

Tôi làm tốt nhất ở việc implement workers theo contract chặt chẽ, đảm bảo stateless và testable độc lập. Mỗi worker có test section chạy được ngay, chứng minh functionality.

Tôi cần cải thiện ở documentation — docstrings có nhưng có thể thêm examples cụ thể hơn. Cũng nên thêm type hints cho Python functions.

Đóng góp chính là tạo foundation cho multi-agent system, với clear separation of concerns. Workers có thể reuse trong future projects, và trace logs giúp debug dễ dàng.

Tôi học được tầm quan trọng của contracts trong multi-agent systems — nó prevent tight coupling và enable parallel development. Rule-based + LLM hybrid approach balance speed và accuracy tốt.

Tổng thể, tôi hài lòng với implementation, nhưng sẽ focus hơn vào error handling và user feedback trong future.