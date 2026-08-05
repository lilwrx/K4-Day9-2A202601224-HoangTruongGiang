# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung             |
| --------------- | -------------------- |
| Họ và tên       | HoangTruongGiang       |
| MSSV            | 2A202601224          |
| Khóa/Lớp        | K4                   |
| Vai trò chính   | Agent Architecture & Lead Developer |
| Ngày hoàn thành | 2026-08-05           |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| **Multi-Agent Dispute Engine** | `src/dispute_system.py` | `input/EC_xxx.json`, 9 CSV datasets | Struct kết quả điều tra theo schema | Hoàn thành |
| **Execution & Pipeline Orchestration** | `run_pipeline.py` | 50 test cases | 50 JSON outputs, `trace.jsonl`, `metadata.json` | Hoàn thành |
| **Output Validator Guardrail** | `verify_outputs.py` | `output/*.json` | Báo cáo kiểm tra tính hợp lệ dữ liệu | Hoàn thành |
| **Tài liệu Kiến trúc System** | `architecture.md` | Sơ đồ hệ thống | Sơ đồ Mermaid & mô tả luồng handoff | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm thử tập trung & Debugging | Toàn nhóm | Phát hiện và khắc phục lỗi `NameError: null` trong Python khi tính toán refund |
| Đóng gói submission | Toàn nhóm | Đóng gói thư mục `output/` đạt chuẩn 50 file JSON hợp lệ |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Phát triển Multi-Agent Engine | `src/dispute_system.py` | Các agent `Coordinator`, `Customer`, `OrderProduct`, `Payment`, `Delivery`, `Policy`, `Verifier` | `python run_pipeline.py` |
| Đảm bảo tính nhất quán dữ liệu & Schema | `verify_outputs.py` | Pass 100% 50 file JSON output đạt chuẩn `EC_POLICY_V2` | `python verify_outputs.py` |
| Tạo nhật ký chạy thật (Trace Log) | `trace.jsonl` | Nhật ký ghi nhận toàn bộ bước xử lý của agent | Kiểm tra `trace.jsonl` |
| Khai báo Metadata mô hình | `metadata.json` | Khai báo chi tiết runtime & model size 7B | Kiểm tra `metadata.json` |

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Bài toán yêu cầu điều tra 50 khiếu nại của khách hàng từ dữ liệu Olist. Mỗi trường hợp yêu cầu kết hợp nhiều nguồn dữ liệu (khách hàng, sản phẩm, thanh toán, vận chuyển) để đưa ra quyết định chính xác về bên chịu trách nhiệm, khoản hoàn tiền và hành động xử lý theo quy tắc `EC_POLICY_V2`.

### Cách triển khai
- Hệ thống được thiết kế theo kiến trúc **Multi-Agent A2A**:
  - `CoordinatorAgent`: Điều phối luồng dữ liệu, ghi vết trace log.
  - `CustomerAgent`: Tra cứu `customer_unique_id` và các đơn hàng lịch sử.
  - `OrderProductAgent`: Phân tích items, sellers, products và category.
  - `PaymentAgent`: Tính toán tổng tiền hàng, freight, tổng thanh toán và đối soát (`reconciled` khi chênh lệch $\le 0.10$ BRL).
  - `DeliveryAgent`: Tính toán `delivery_variance_hours` và `handoff_variance_hours` của từng seller.
  - `PolicyAgent`: Đánh giá quy tắc ưu tiên nguyên nhân chính/phụ, tính toán khoản hoàn tiền và giải pháp bằng cách hỗ trợ gọi API trực tiếp tới Groq API (`llama-3.1-8b-instant`), OpenRouter / HuggingFace Inference API (`Qwen/Qwen2.5-7B-Instruct` / `qwen3-8b`) kèm cơ chế deterministic rule fallback.
  - `VerifierAgent`: Đảm bảo schema, xử lý giá trị `null` cho đơn không có item và giới hạn độ dài mảng.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Case JSON (`case_id`, `customer_request.claimed_order_id`) và 9 file CSV Olist |
| Output | Case investigation JSON chuẩn hóa trong thư mục `output/` |
| Module phụ thuộc | `pandas`, `json`, `datetime` |
| Module sử dụng output | Hệ thống chấm điểm tự động Competition |
| Điều kiện lỗi cần xử lý | Đơn hàng không có item, đơn hàng giao muộn nhưng seller không muộn, sai lệch thanh toán trong/ngoài hạn mức 0.10 BRL |

### Cách xác minh

```bash
python run_pipeline.py
python verify_outputs.py
```

- **Kết quả mong đợi:** 50/50 file JSON được tạo ra thành công trong thư mục `output/` và vượt qua tất cả bài test quy tắc.
- **Kết quả thực tế:** Hệ thống xử lý 50 case trong 2.77 giây, vượt qua 100% các tiêu chí kiểm tra.
- **Artifact/log:** `trace.jsonl`, `metadata.json`, `output/*.json`

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần xử lý trường hợp đơn hàng không có item row (item count = 0).
- **Các phương án đã cân nhắc:**
  1. Gán giá trị bằng `0.0` cho `expected_total_brl` và `false` cho `reconciled`.
  2. Gán giá trị `null` (`None` trong Python) cho `expected_total_brl`, `difference_brl` và `reconciled` theo đúng đặc tả `EC_POLICY_V2`.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Đảm bảo tính chính xác nghiệp vụ. Một đơn hàng không có mặt hàng thì không thể tính tổng giá trị dự kiến hay đối soát thanh toán. Việc sử dụng `null` giúp hệ thống tránh suy diễn sai sự kiện không tồn tại.
- **Bằng chứng quyết định phù hợp:** `verify_outputs.py` xác minh chính xác các đơn không có item được gán giá trị `null` đúng chuẩn.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `NameError: name 'null' is not defined` tại `src/dispute_system.py`.
- **Lệnh hoặc bước tái hiện:** `python run_pipeline.py`
- **Nguyên nhân gốc:** Đã ghi nhầm từ khóa `null` của JavaScript thay vì `None` trong mã nguồn Python khi tính toán `recommended_refund_brl`.
- **Cách xử lý:** Thay thế toàn bộ cú pháp `is not null` thành `is not None` trong class `PolicyAgent`.
- **Cách xác minh sau khi sửa:** Chạy lại `python run_pipeline.py` và tất cả 50 case đã được xử lý hoàn toàn mượt mà.
- **Điều học được:** Luôn chú ý sự khác biệt giữa cú pháp JSON/JS (`null`) và Python (`None`) khi viết mã nguồn xử lý logic.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Dữ liệu thô từ nguồn (như API hoặc tập dữ liệu CSV) được trích xuất, làm sạch, phân tách thành các đoạn văn bản (chunks), tạo embedding vector và lưu trữ vào cơ sở dữ liệu vector (Vector Index) để phục vụ cho truy xuất ngữ cảnh.
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Evaluation set chứa danh sách các truy vấn mẫu kèm danh sách tài liệu chuẩn (ground-truth IDs). Retrieval quality được đo bằng các chỉ số như Precision@K, Recall@K, MRR, trong khi Answer Quality đánh giá độ chính xác và trung thực của câu trả lời do LLM sinh ra so với ground truth.
3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   Quality checks tập trung vào tính đúng đắn, tính toàn vẹn và độ chính xác của dữ liệu/output (schema validation, null check, array limit). Trong khi Freshness monitoring kiểm tra độ mới của dữ liệu, tần suất cập nhật và đảm bảo thông tin không bị lỗi thời.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Đảm bảo tính công bằng và khả năng so sánh nhất quán của thử nghiệm. Việc giữ cố định test set giúp đo lường chính xác tác động của nhiễu (corrupted) và hiệu quả phục hồi của thuật toán (repaired).
5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Repair thành công khi các chỉ số đánh giá (như Accuracy, F1-Score, Retrieval Precision) trên tập dữ liệu được phục hồi tiệm cận hoặc bằng mức baseline, đồng thời artifact kết quả pass toàn bộ các bước kiểm tra tính hợp lệ (validation rules).

---

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Lưu Quang Linh  
**Ngày xác nhận:** 2026-08-05  
