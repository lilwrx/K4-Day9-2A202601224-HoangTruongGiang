# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                            |
| --------------- | --------------------------------------------------- |
| Họ và tên       | Hoàng Trường Giang                                  |
| MSSV            | 2A202601224                                         |
| Khóa/Lớp        | K4                                                  |
| Vai trò chính   | Agent System Architect & Multi-Agent Orchestrator   |
| Ngày hoàn thành | 2026-08-05                                          |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | ----------------- | ------------------------------------- |
| Agent System Architecture & Orchestration | `src/agents/coordinator.py`, `src/agents/verifier.py` | `input/EC_xxx.json` | 50 JSON outputs trong `output/` | Hoàn thành |
| Data Engine & Policy Metrics | `src/data_engine/olist_db.py`, `src/data_engine/metrics.py` | 9 file CSV Olist trong `data/` | Reconciled metrics & Policy decisions | Hoàn thành |
| Trace Logging & Output Packaging | `src/utils/logger.py`, `run_pipeline.py` | Log events từ các Agents | `trace.jsonl`, `metadata.json`, `output.zip` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Tích hợp Gemma-9B & Prompting | Domain Agents | Các prompt chuyên biệt hóa cho Gemma-9B trích xuất context chuẩn xác |
| Test suite & Evaluation | Quality Assurance & Compliance | File `test_eval.py` vượt qua 100% các tiêu chí kiểm thử schema |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | --------------------------- | ------------------------- | --------------- |
| Xây dựng SQLite Data Engine cho Olist | `src/data_engine/olist_db.py` | Indexing & load 9 CSV trong ~10 giây | Test query SQLite thành công |
| Đơn giản hóa & chuẩn hóa EC_POLICY_V2 | `src/data_engine/metrics.py` | Phân loại chính xác 50/50 case dispute | Run pipeline & eval schema |
| Thiết kế kiến trúc Multi-Agent Handoff | `architecture.md` | Sơ đồ luồng handoff & quyền hạn các agent | Đạt chuẩn thiết kế hệ thống |
| Tạo gói sản phẩm chấm điểm | `output.zip`, `metadata.json`, `trace.jsonl` | File nộp bài hoàn chỉnh theo quy định | `python test_eval.py` |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Bài toán yêu cầu điều tra 50 khiếu nại của khách hàng thương mại điện tử Olist với các dữ liệu đối soát phức tạp về đơn hàng, thời gian bàn giao của seller, thời gian giao hàng thực tế của đơn vị vận chuyển, thanh toán nhiều dòng (split payment), và thông tin sản phẩm/khách hàng.

### Cách triển khai
- **Architecture:** Sử dụng kiến trúc Multi-Agent với Coordinator Agent đóng vai trò trung tâm điều phối 4 Domain Agents (`CustomerAgent`, `OrderProductAgent`, `PaymentAgent`, `DeliveryAgent`).
- **Data Layer:** Sử dụng SQLite in-memory database để load toàn bộ 9 file CSV Olist và tạo các chỉ mục (`INDEX`) trên các khóa join chính, cho phép truy vấn dữ liệu theo thời gian thực ($<0.01$ giây per order).
- **Rule Engine:** Cấu hình chuẩn xác thứ tự ưu tiên của `EC_POLICY_V2` đối với Primary Issue, Secondary Issues, các công thức tính `delivery_variance_hours`, `handoff_variance_hours`, `expected_total_brl`, `difference_brl` và `reconciled`.
- **Verifier:** Thêm Verifier Agent để ép kiểu, kiểm tra mảng tối đa ($\le 5$ items/orders/payments/products/categories/actions, $\le 3$ sellers/causes/parties, $\le 20$ evidence), đảm bảo không vi phạm Hard Gate.

### Input, output và contract

| Thành phần | Mô tả |
| ----------- | -------------------------------------- |
| Input | File JSON `EC_xxx.json` chứa `case_id`, `claimed_order_id`, `customer_request`, `investigation_scope`, `policy_version`. |
| Output | File JSON `output/EC_xxx.json` theo đúng schema quy định tại Mục 6 của `README.md`. |
| Module phụ thuộc | Python standard libraries (`sqlite3`, `json`, `csv`, `zipfile`, `datetime`). |
| Module sử dụng output | Hệ thống chấm điểm tự động (Auto-evaluator). |
| Điều kiện lỗi cần xử lý | Xử lý file CSV có UTF-8 BOM (`utf-8-sig`), order không có item row (`expected_total_brl = null`), timestamp rỗng/null. |

### Cách xác minh

```bash
python run_pipeline.py
python test_eval.py
```

- **Kết quả mong đợi:** Cả 50 case xử lý thành công, không gặp lỗi schema hay hard gate, file `output.zip` chứa đúng 50 file JSON.
- **Kết quả thực tế:** Tất cả 50 case đã được sinh ra chính xác, vượt qua 100% bài kiểm tra `test_eval.py`.
- **Artifact/log:** `logging/trace.jsonl`, `logging/metadata.json`, `output.zip`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần xử lý và join 9 file CSV dung lượng lớn của Olist để lấy ngữ cảnh đầy đủ cho 50 case trong thời gian ngắn nhất.
- **Các phương án đã cân nhắc:**
  1. Dùng `pandas` để load CSV và thực hiện DataFrame merges.
  2. Sử dụng SQLite in-memory database (`sqlite3.connect(":memory:")`) với các bảng và `INDEX` trên các khóa join chính.
- **Phương án đã chọn:** Phương án 2 (SQLite in-memory).
- **Lý do:** SQLite là thư viện có sẵn trong Python (zero external dependencies), cho phép load dữ liệu nhanh ($\sim 10$ giây), thực hiện SQL joins phức tạp và lập chỉ mục tối ưu tốc độ truy vấn gấp nhiều lần so với pandas.
- **Bằng chứng quyết định phù hợp:** Thời gian load toàn bộ 9 CSV và tạo 8 indexes chỉ mất 10.12s; thời gian xử lý mỗi case dispute chỉ mất vài milliseconds.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `sqlite3.OperationalError: no such column: t.product_category_name` khi truy vấn bảng `product_category_name_translation`.
- **Lệnh hoặc bước tái hiện:** Trực tiếp chạy `python run_pipeline.py`.
- **Nguyên nhân gốc:** File `product_category_name_translation.csv` chứa ký tự UTF-8 BOM (`\ufeff`) ở đầu header, làm cho tên cột đầu tiên bị biến thành `\ufeffproduct_category_name` khi dùng `encoding="utf-8"`.
- **Cách xử lý:** Thay đổi encoding từ `"utf-8"` sang `"utf-8-sig"` trong hàm `_load_csvs()` của `OlistDB`.
- **Cách xác minh sau khi sửa:** Lệnh `python run_pipeline.py` hoàn thành trôi chảy 50/50 case không còn lỗi.
- **Điều học được:** Luôn sử dụng `utf-8-sig` khi đọc các file CSV từ bên ngoài để tự động loại bỏ UTF-8 BOM byte order marks.

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu đi từ các file CSV Olist $\rightarrow$ nạp vào SQLite in-memory DB $\rightarrow$ Coordinator Agent nhận case $\rightarrow$ các Domain Agents trích xuất ngữ cảnh $\rightarrow$ Policy Agent áp dụng `EC_POLICY_V2` $\rightarrow$ Verifier Agent kiểm duyệt schema $\rightarrow$ xuất file `output/EC_xxx.json`.
2. Evaluation set gồm 50 case khiếu nại thực tế đo đạc 7 thành phần trọng số (Primary/Secondary issues, Affected entities, Customer/Product context, Delivery analysis, Payment reconciliation, Root cause & Evidence, Financial resolution & Actions).
3. Hard gate checks đảm bảo tính chính xác tuyệt đối của evidence IDs và không vi phạm bất kỳ giới hạn mảng hay định dạng nào.
4. Model được cấu hình là `gemma-2-9b-it` ($\le 10B$ parameters) đúng theo quy chế cuộc thi.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Hoàng Trường Giang  
**Ngày xác nhận:** 2026-08-05
