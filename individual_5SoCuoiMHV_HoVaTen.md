# Member Role Report — Day 9: Multi Agent A2A

> ⚠️ Cần điền trước khi nộp: các ô `[ ]` ở mục 1, mục 2 (phần hỗ trợ), và tự tick
> checklist mục 8. Đổi tên file thành `individual_<5 số cuối MSSV>_<HọVàTên>.md`.

## 1. Thông tin cá nhân

| Thông tin       | Nội dung     |
| --------------- | ------------ |
| Họ và tên       | [Họ và tên]  |
| MSSV            | [MSSV]       |
| Khóa/Lớp        | K4           |
| Vai trò chính   | Pipeline & Policy — thiết kế contract giữa agent, rule engine EC_POLICY_V2, Verifier |
| Ngày hoàn thành | 2026-08-05   |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data layer | `src/data_store.py` — `DataStore._load`, `parse_ts`, `clean` | 7 file CSV Olist | 6 index trong RAM + API tra cứu O(1) | Hoàn thành |
| 4 agent phân tích | `src/agents/{customer,order_product,payment,delivery}_agent.py` — `analyze()` | `(store, order_id)` | 4 contract sự kiện tạo thành `CaseFacts` | Hoàn thành |
| Rule engine policy | `src/policy_rules.py` — `classify_primary`, `resolution_actions` | `CaseFacts` | phân loại + refund + action deterministic | Hoàn thành |
| Policy Agent (LLM) | `src/agents/policy_agent.py` — `analyze`, `_validate_llm_output` | `CaseFacts` rút gọn | assessment đã kiểm chứng chéo | Hoàn thành (chạy được ở chế độ rule engine khi thiếu API key) |
| Verifier | `src/agents/verifier_agent.py` — `verify` | output payload | danh sách vi phạm; rỗng = đạt | Hoàn thành |
| Orchestration & trace | `src/coordinator.py`, `src/trace.py`, `run.py` | 50 case JSON | 50 output + `trace.jsonl` + `metadata.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| [Debug/tích hợp/tài liệu] | [Tên hoặc module] | [Kết quả và bằng chứng] |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Nạp và index 7 CSV Olist | `src/data_store.py` | 99.441 order, 112.650 item row, 103.886 payment row | `DataStore().stats()` đối chiếu `wc -l` từng file trừ header |
| Sinh 50 output đúng schema | `output/EC_001.json`…`EC_050.json` | 50 file JSON | `python run.py` → "Verifier: tất cả case đạt chuẩn schema" |
| Kiểm chứng độc lập | `src/agents/verifier_agent.py` | 12 nhóm kiểm tra, 0 vi phạm trên 50 case | exit code 0 của `run.py` |
| Trace chạy thật | `logging/trace.jsonl` | 352 bản ghi, 7 agent, 50 case | `wc -l logging/trace.jsonl` |

Một output cụ thể mà phần việc của tôi tạo ra:

`logging/trace.jsonl` ghi lại từng lượt handoff kèm thời gian thực thi. Đây là bằng
chứng rằng hệ thống thực sự có phân công giữa các agent chứ không phải một prompt
duy nhất: mỗi case sinh 7 bản ghi — 1 `dispatch` của Coordinator, 5 `handoff` của
các agent chuyên môn, 1 `verdict` của Verifier.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cùng một khiếu nại "giao hàng trễ" có thể quy trách nhiệm cho seller, cho đơn vị vận
chuyển, hoặc không cho ai — tùy vào dữ liệu chứ không tùy vào lời khách kể. Phần của
tôi phải biến dữ liệu thô của 9 file CSV thành kết luận có thể kiểm chứng, và phải
ngăn hệ thống bịa ra sự kiện không tồn tại trong dữ liệu.

### Cách triển khai

Ranh giới thiết kế trung tâm: **agent phân tích chỉ sản xuất sự kiện, chỉ Policy
Agent được kết luận.** Delivery Agent báo cáo "giao trễ 87.39 giờ, seller X bàn giao
muộn 1.04 giờ" nhưng không được nói "đây là `late_delivery_seller`". Nhờ vậy quy tắc
nghiệp vụ chỉ nằm ở một nơi duy nhất, và Policy Agent (LLM 8B) thực sự có việc để
quyết định thay vì chỉ đóng dấu lên kết luận đã có sẵn.

Bên trong Policy Agent, tôi chia việc tiếp: **LLM phân loại, code làm toán.** Model
8B nhận các sự kiện đã tính sẵn (số giờ lệch, tổng tiền, cờ `reconciled`) và chọn
`primary_issue` theo 6 quy tắc ưu tiên. Mọi phép trừ timestamp và cộng tiền do code
thực hiện, vì sai một xu ở ngưỡng 0.10 BRL là lật `reconciled` và mất 15% điểm case.

Ba chi tiết kỹ thuật quyết định độ chính xác:

1. **Cộng trước, làm tròn sau.** `round(Σ price + Σ freight, 2)` chứ không cộng các
   giá trị đã làm tròn — với đơn nhiều item, sai số tích lũy có thể vượt ngưỡng đối
   soát.
2. **Tách `count` khỏi array bị cắt.** `seller_count` đếm trên tập đầy đủ, còn
   `seller_ids` mới bị cắt còn 3. Nếu xét `multi_seller_order` trên array đã cắt thì
   giới hạn schema sẽ làm sai kết luận nghiệp vụ.
3. **Timestamp xuất ra là chuỗi gốc từ CSV.** Parse sang `datetime` chỉ để trừ; khi
   ghi output thì lấy lại chuỗi ban đầu, không dùng `str(datetime)`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `input/EC_XXX.json` (`case_id`, `claimed_order_id`, `policy_version`) + 7 CSV Olist |
| Output | `output/EC_XXX.json` đúng output schema; `logging/trace.jsonl`; `logging/metadata.json` |
| Module phụ thuộc | `src/data_store.py` (mọi agent), `src/llm.py` (Policy Agent) |
| Module sử dụng output | `src/coordinator.py` gom `CaseFacts`; `src/agents/verifier_agent.py` kiểm payload cuối |
| Điều kiện lỗi cần xử lý | đơn không có item row (6/50 case); thiếu `order_delivered_customer_date` (14/50); thiếu `carrier_handoff_at`; product không có category; LLM trả JSON sai taxonomy hoặc gọi API thất bại |

### Cách xác minh

```bash
python run.py
python -c "import json,glob; [json.load(open(f,encoding='utf-8')) for f in glob.glob('output/EC_*.json')]"
wc -l logging/trace.jsonl
```

- **Kết quả mong đợi:** 50 file JSON hợp lệ, Verifier không báo vi phạm nào, trace
  ghi đủ 7 agent cho mỗi case.
- **Kết quả thực tế:** `Đã ghi 50 file`, `Verifier: tất cả case đạt chuẩn schema`,
  exit code 0; `trace.jsonl` có 352 bản ghi; phân bố `primary_issue` phủ cả 6 nhánh
  policy (10 `late_delivery_seller`, 10 `late_delivery_logistics`, 8
  `canceled_order_paid`, 8 `valid_split_payment`, 8 `unsupported_late_claim`,
  6 `unavailable_order_paid`).
- **Artifact/log:** `output/`, `logging/trace.jsonl`, `logging/metadata.json`.
  Không chứa secret — API key nằm trong `.env` đã bị `.gitignore` loại trừ.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** đề bài bắt buộc mỗi agent dùng model ≤ 10B, nhưng thang điểm lại
  chấm hoàn toàn trên độ chính xác của JSON. Model 8B tính chênh lệch timestamp và
  cộng tiền không đáng tin, trong khi sai một xu ở ngưỡng 0.10 BRL là mất 15% điểm
  của case.
- **Các phương án đã cân nhắc:**
  1. Để LLM tự đọc dữ liệu thô và tự tính toàn bộ — đúng tinh thần "agent" nhất
     nhưng rủi ro sai số học và bịa evidence ID rất cao.
  2. Làm deterministic hoàn toàn, không dùng LLM — chính xác và tái lập tuyệt đối
     nhưng không còn là hệ multi-agent dùng model.
  3. Chia đôi: code tính số, LLM phân loại chính sách.
- **Phương án đã chọn:** phương án 3, kèm một rule engine deterministic đóng vai trò
  chốt chặn — kết quả LLM luôn được đối chiếu, sai taxonomy thì hạ xuống kết luận
  của engine và ghi rõ trong trace.
- **Lý do:** giữ được vai trò quyết định thật sự cho model (chọn `primary_issue`
  theo 6 quy tắc ưu tiên là phần suy luận chính sách, không phải phần số học) mà
  không đánh đổi độ chính xác của những trường được chấm điểm. Hệ thống cũng chạy
  được khi mất mạng hoặc hết quota — điều đáng giá trong một cuộc thi 4 tiếng.
- **Bằng chứng quyết định phù hợp:** 50/50 case qua Verifier không vi phạm; mọi
  evidence ID đều được tra ngược lại `DataStore` và không có ID nào không tồn tại.

Một quyết định nhỏ hơn nhưng cũng phải chọn: `category_names` dùng tên tiếng Bồ Đào
Nha (`beleza_saude`) thay vì bản dịch tiếng Anh (`health_beauty`), vì đó là giá trị
trực tiếp của cột `products.product_category_name` sau khi join. File translation có
mặt trong `data/` chỉ vì nó thuộc bộ dataset gốc, còn tên trường trong output schema
là `category_names` chứ không phải `category_names_english`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** trong lượt khảo sát dữ liệu, tra
  `category_en['beleza_saude']` trả về `KeyError`, dù dòng đó rõ ràng có trong
  `product_category_name_translation.csv`.
- **Lệnh hoặc bước tái hiện:** đọc file bằng `csv.DictReader` với
  `encoding="utf-8"` rồi in `list(rows[0].keys())`.
- **Nguyên nhân gốc:** file có BOM ở đầu, nên key đầu tiên thực chất là
  `'﻿product_category_name'` chứ không phải `'product_category_name'`. Đây là
  loại lỗi *trượt im lặng*: chương trình không nổ exception ở chỗ đọc file mà chỉ
  cho ra map rỗng, và hậu quả chỉ lộ ra ở tận trường `category_names` của output.
- **Cách xử lý:** đọc file đó bằng `encoding="utf-8-sig"` để Python tự loại BOM.
- **Cách xác minh sau khi sửa:** `list(store.category_en.items())[:2]` trả về
  `[('beleza_saude', 'health_beauty'), ('informatica_acessorios', 'computers_accessories')]`.
- **Điều học được:** với dữ liệu ngoài, phải kiểm tra *key thực tế* mà parser đọc
  được chứ không tin vào những gì nhìn thấy trong editor. Cùng nhóm với bài học này
  là việc `sort` theo `order_item_id` phải ép `int` — sắp xếp theo chuỗi sẽ cho
  `"10"` đứng trước `"2"` và làm lệch thứ tự array trong output.

## 7. Hiểu biết về luồng end-to-end

> Ghi chú: 5 câu hỏi trong mẫu báo cáo nhắc tới Crossref, vector index và freshness
> monitoring — đó là artifact của lab RAG, không có trong lab Day 9. Tôi trả lời
> theo các thành phần tương ứng của pipeline thực tế đã xây.

**Câu trả lời:**

1. **Dữ liệu đi từ nguồn tới nơi ra quyết định như thế nào?** `claimed_order_id`
   trong file input là điểm vào duy nhất. Từ đó `DataStore` join ngược ra 6 nhánh:
   `orders → customers → customer_unique_id → lịch sử order`;
   `orders → order_items → sellers, products → categories`;
   `orders → order_payments`. Bốn agent phân tích mỗi agent lấy một nhánh, biến
   thành sự kiện đã tính (số giờ lệch, tổng tiền, các cờ đếm), rồi Coordinator gom
   thành `CaseFacts` — đó là toàn bộ những gì Policy Agent được nhìn thấy. Model
   không bao giờ chạm vào CSV thô.

2. **Đo chất lượng kết luận bằng gì khi không có ground truth?** Không có nhãn
   đúng để so, nên tôi dùng hai nguồn đối chiếu thay thế: (a) rule engine
   deterministic áp cùng bộ quy tắc lên cùng bộ sự kiện, cờ
   `agrees_with_rule_engine` trong trace cho biết LLM có lệch không; (b) Verifier
   kiểm tính nhất quán nội tại — `case_status` phải khớp dấu của refund,
   `difference_brl` phải bằng `payment_total − expected_total`, mọi evidence ID
   phải dựng lại được từ dữ liệu. Sai lệch nội tại là dấu hiệu sai sớm nhất mà ta
   phát hiện được mà không cần đáp án.

3. **Kiểm tra chất lượng khác giám sát vận hành ở chỗ nào?** Verifier chạy trên
   *từng payload* và có quyền chặn không cho ghi file — nó là cổng chất lượng.
   `trace.jsonl` thì không chặn gì cả, nó ghi lại quá trình để truy vết sau khi
   chạy: agent nào mất bao lâu, LLM có bị fallback không, có bao nhiêu case lệch
   giữa hai cách quyết định. Một cái quyết định "có được ra hay không", cái kia trả
   lời "chuyện gì đã xảy ra".

4. **Vì sao phải chạy cùng một bộ input cho mọi chế độ?** Vì `--no-llm` và chế độ
   LLM chỉ khác nhau ở đúng một mắt xích (ai chọn `primary_issue`). Giữ nguyên 50
   case, nguyên `DataStore`, nguyên `CaseFacts` thì mọi khác biệt trong output đều
   quy được về mắt xích đó. Đổi input cùng lúc với đổi chế độ thì không còn kết
   luận được gì.

5. **Dựa vào artifact nào để nói pipeline chạy thành công?** Ba thứ, theo thứ tự
   ràng buộc giảm dần: `run.py` thoát với exit code 0 (Verifier không tìm thấy vi
   phạm nào trên cả 50 case); `output/` có đúng 50 file JSON parse được và đúng
   schema; `logging/trace.jsonl` có đủ 352 bản ghi phủ 7 agent × 50 case, chứng
   minh mọi agent đều thực sự được gọi.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** [Họ và tên]
**Ngày xác nhận:** [YYYY-MM-DD]
