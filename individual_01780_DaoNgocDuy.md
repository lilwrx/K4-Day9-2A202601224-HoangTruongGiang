# Member Role Report — Day 9: Multi Agent A2A

## 1. Thong tin ca nhan

| Thong tin       | Noi dung                    |
| --------------- | --------------------------- |
| Ho va ten       | Dao Ngoc Duy                |
| MSSV            | 2A202601780                 |
| Khoa/Lop        | K4                          |
| Vai tro chinh   | Full-stack Developer & System Architect |
| Ngay hoan thanh | 2026-08-05                  |

## 2. Vai tro va pham vi cong viec

### Phan viec so huu

| Module/deliverable | File/ham phu trach | Input nhan vao | Output ban giao | Trang thai |
| ------------------ | ------------------ | -------------- | --------------- | ---------- |
| Data Layer | `src/data_loader.py` | 9 CSV files | DataLoader singleton | Hoan thanh |
| Customer Agent | `src/agents/customer_agent.py` | order_id | customer_context | Hoan thanh |
| Order & Product Agent | `src/agents/order_product_agent.py` | order_id | affected_entities, product_context | Hoan thanh |
| Payment Agent | `src/agents/payment_agent.py` | order_id | payment_reconciliation | Hoan thanh |
| Delivery Agent | `src/agents/delivery_agent.py` | order_id | delivery_analysis | Hoan thanh |
| Policy Agent | `src/agents/policy_agent.py` | All agent outputs | case_assessment, root_cause, refund, actions | Hoan thanh |
| Verifier Agent | `src/agents/verifier_agent.py` | Final output dict | Validated output | Hoan thanh |
| Coordinator Agent | `src/agents/coordinator_agent.py` | Case JSON | Final output + trace | Hoan thanh |
| Main Entry Point | `src/main.py` | 50 input files | 50 output JSONs + trace + metadata | Hoan thanh |
| LLM Client | `src/llm_client.py` | Agent summaries | Trace reasoning text | Hoan thanh |
| Architecture Doc | `architecture.md` | N/A | Architecture documentation | Hoan thanh |

### Viec ho tro ngoai pham vi chinh

| Hoat dong | Thanh vien/module duoc ho tro | Ket qua |
| --------- | ----------------------------- | ------- |
| Thiet ke kien truc tong the | Nhom | So do agent, data flow, handoff protocol |
| Review va fix data contract | Nhom | Dam bao tat ca agents giao tiep dung format |

## 3. Ket qua theo vai tro

| Nhiem vu da thuc hien | File/ham/artifact lien quan | Ket qua ban giao | Cach xac minh |
| --------------------- | --------------------------- | ----------------- | ------------- |
| Xay dung 7-agent pipeline | `src/agents/*.py` | 7 agent classes hoat dong | `python src/main.py` |
| Xu ly 50 cases | `output/EC_001-050.json` | 50 output JSON files | So sanh EC_002 voi README example |
| Payment reconciliation | `src/agents/payment_agent.py` | Tat ca payments doi soat chinh xac | Kiem tra difference_brl va reconciled |
| Delivery analysis | `src/agents/delivery_agent.py` | Variance hours tinh dung | So sanh EC_002: 87.39h, 1.04h |
| Policy evaluation | `src/agents/policy_agent.py` | 6 loai primary issue phan loai dung | Thong ke phan bo cases |
| Schema validation | `src/agents/verifier_agent.py` | Evidence IDs, array limits hop le | Script validate_outputs.py |

Mot output cu the: EC_002.json khop chinh xac voi example output trong README:
- delivery_variance_hours = 87.39
- handoff_variance_hours = 1.04
- recommended_refund_brl = 18.27
- primary_issue = late_delivery_seller

## 4. Giai thich phan ky thuat da thuc hien

### Van de can giai quyet

Xay dung he thong multi-agent xu ly 50 khieu nai thuong mai dien tu tren du lieu Olist. Moi case can: join du lieu tu 9 CSV, phan tich delivery/payment/customer/product, ap dung policy EC_POLICY_V2, sinh output JSON chuan.

### Cach trien khai

1. **Data Layer (Singleton Pattern):** Load 9 CSV files mot lan duy nhat vao pandas DataFrames, cung cap query functions cho tung agent. Xu ly NaN values bang cach convert sang None.

2. **Agent Architecture:** 7 agent rieng biet, moi agent la 1 Python class voi method `investigate()` hoac `evaluate()`. Coordinator Agent dieu phoi toan bo flow:
   - Customer Agent: Join orders→customers, tim customer_unique_id va related orders
   - Order & Product Agent: Iterate order_items, extract unique sellers/products/categories
   - Payment Agent: Sum prices + freight vs sum payments, kiem tra sai so ≤ 0.10 BRL
   - Delivery Agent: Tinh (delivered - estimated) hours, (carrier - shipping_limit) hours
   - Policy Agent: Ap dung 6 rules theo thu tu uu tien
   - Verifier Agent: Truncate arrays, validate evidence format, verify consistency

3. **Deterministic Logic:** Toan bo tinh toan bang Python thuan. LLM (llama-3.1-8b-instant, 8B params) chi dung de sinh reasoning summary cho trace — khong tham gia quyet dinh logic nao.

4. **Evidence Building:** Coordinator tu dong build evidence_ids tu output cua cac agent: order, items, payments, responsible sellers, policy code.

### Input, output va contract

| Thanh phan | Mo ta |
| ---------- | ----- |
| Input | 50 JSON files (EC_001-050.json) voi claimed_order_id |
| Output | 50 JSON files theo output schema + trace.jsonl + metadata.json |
| Module phu thuoc | pandas, groq SDK, python-dotenv |
| Module su dung output | Coordinator agent tong hop tat ca |
| Dieu kien loi can xu ly | Order khong co items (null handling), missing timestamps, Unicode encoding tren Windows |

### Cach xac minh

```bash
python src/main.py
python src/validate_outputs.py
```

- **Ket qua mong doi:** 50/50 cases xu ly thanh cong, tat ca output hop le
- **Ket qua thuc te:** 50/50 cases thanh cong, EC_002 khop chinh xac voi README example
- **Artifact/log:** `output/`, `logging/trace.jsonl`, `logging/metadata.json`

## 5. Mot quyet dinh ky thuat quan trong

- **Boi canh:** Chon giua viec de LLM xu ly logic (flexible nhung khong chinh xac) hay dung 100% deterministic Python.
- **Cac phuong an da can nhac:**
  1. LLM-driven: Gui du lieu CSV cho LLM, de LLM phan tich va tra JSON — don gian nhung sai so cao
  2. Deterministic Python + LLM trace: Logic tinh toan bang Python, LLM chi lam trace summary
- **Phuong an da chon:** Deterministic Python + LLM trace
- **Ly do:** Bai lab yeu cau chinh xac tung con so (delivery_variance_hours, refund, difference_brl). LLM 8B khong du kha nang tinh toan chinh xac voi so lieu day du. Python cho ket qua 100% chinh xac va tai tao duoc.
- **Bang chung quyet dinh phu hop:** EC_002 output khop chinh xac toi tung so le voi README example (87.39h, 1.04h, 18.27 BRL).

## 6. Mot loi hoac blocker da xu ly

- **Trieu chung/loi nguyen van:** `UnicodeEncodeError: 'charmap' codec can't encode character '\u2713' in position 2`
- **Lenh hoac buoc tai hien:** `python src/main.py` tren Windows console (cp1252 encoding)
- **Nguyen nhan goc:** Windows PowerShell su dung cp1252 encoding, khong ho tro Unicode checkmarks (✓, ✗, ⚠)
- **Cach xu ly:** Thay the Unicode symbols bang ASCII equivalents: `[OK]`, `[ERR]`, `[SKIP]`
- **Cach xac minh sau khi sua:** Chay lai `python src/main.py` — 50/50 cases thanh cong
- **Dieu hoc duoc:** Luon dung ASCII characters cho console output tren Windows de tranh encoding issues

## 7. Hieu biet ve luong end-to-end

1. **Du lieu di tu input den output nhu the nao?**
   Input JSON chua claimed_order_id → Coordinator dispatch toi 6 agent → Moi agent query CSV qua DataLoader → Ket qua gom lai → Policy Agent ap EC_POLICY_V2 → Verifier validate → Output JSON.

2. **EC_POLICY_V2 duoc ap dung ra sao?**
   6 rules theo thu tu uu tien: canceled_order_paid > unavailable_order_paid > late_delivery_seller > late_delivery_logistics > valid_split_payment > unsupported_late_claim. Dieu kien kiem tra: order_status, payment_total, delivery_variance, seller handoff, payment rows, reconciliation.

3. **Multi-agent khac single-prompt o diem nao?**
   Moi agent chi truy cap data domain cua minh, xu ly doc lap, va handoff ket qua cho Coordinator. Trace ghi lai tung buoc agent xu ly. Verifier kiem tra lai ket qua cuoi cung — separation of concerns thuc su.

4. **Vi sao phai dung deterministic thay vi LLM?**
   Chinh xac tuyet doi cho so hoc (rounding 2 decimal, variance hours, refund). LLM 8B khong du kha nang tinh toan chinh xac voi nhieu con so. Deterministic Python dam bao reproducibility 100%.

5. **Kiem chung thanh cong dua tren gi?**
   EC_002 output khop chinh xac voi example trong README. Validate script kiem tra schema, evidence format, array limits, case_status consistency cho tat ca 50 cases.

## 8. Cam ket cua thanh vien

- [x] Noi dung bao cao phan anh dung phan viec va muc hieu cua toi.
- [x] Toi co the giai thich luong end-to-end, khong chi module minh phu trach.
- [x] Toi khong ghi "da chay thanh cong" cho phan chua duoc kiem chung.
- [x] Bao cao khong chua `.env`, API key, token hoac secret.
- [x] Bao cao nay khong phai ban sao nguyen van cua bao cao nhom hoac bao cao thanh vien khac.

**Ho va ten:** Dao Ngoc Duy
**Ngay xac nhan:** 2026-08-05