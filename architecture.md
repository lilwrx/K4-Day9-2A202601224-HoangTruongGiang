# Architecture — Multi-Agent E-commerce Dispute Resolution

## 1. Tổng quan hệ thống

Hệ thống sử dụng kiến trúc **multi-agent** với 7 agent chuyên biệt, mỗi agent phụ trách một domain dữ liệu riêng biệt. Coordinator Agent điều phối toàn bộ luồng xử lý, thu thập kết quả từ các agent chuyên môn, và tổng hợp thành output cuối cùng.

**Model sử dụng:** `llama-3.1-8b-instant` (8B parameters) qua Groq API  
**Framework:** Python + pandas + groq SDK  
**Chiến lược:** Logic xử lý 100% deterministic bằng Python; LLM chỉ dùng cho trace reasoning summary

## 2. Sơ đồ kiến trúc

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT (EC_XXX.json)                       │
│              claimed_order_id + policy_version               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   COORDINATOR AGENT                          │
│  - Nhận case, extract order_id                               │
│  - Dispatch tới các agent chuyên môn                         │
│  - Tổng hợp kết quả, build evidence, assemble output        │
│  - Ghi output JSON + trace entry                             │
└────┬────────┬────────┬────────┬────────┬────────┬───────────┘
     │        │        │        │        │        │
     ▼        ▼        ▼        ▼        ▼        ▼
┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
│Customer││Order & ││Payment ││Delivery││ Policy ││Verifier│
│ Agent  ││Product ││ Agent  ││ Agent  ││ Agent  ││ Agent  │
│        ││ Agent  ││        ││        ││        ││        │
└────────┘└────────┘└────────┘└────────┘└────────┘└────────┘
```

## 3. Chi tiết từng Agent

### 3.1 Coordinator Agent (`src/agents/coordinator_agent.py`)
- **Vai trò:** Điều phối toàn bộ pipeline
- **Quyền truy cập:** Tất cả CSVs (qua DataLoader), tất cả agents
- **Input:** Case JSON từ `input/`
- **Output:** Final output JSON + trace entry
- **Luồng xử lý:**
  1. Extract `claimed_order_id` từ input
  2. Dispatch song song tới Customer, Order&Product, Payment, Delivery agents
  3. Gom kết quả → gửi Policy Agent
  4. Policy Agent trả kết quả → build evidence IDs
  5. Assemble full output → gửi Verifier Agent
  6. Verifier validate → output cuối cùng

### 3.2 Customer Agent (`src/agents/customer_agent.py`)
- **Vai trò:** Xác định customer identity và lịch sử order
- **Quyền truy cập:** `orders`, `customers`
- **Input:** `order_id`
- **Output:** `customer_unique_id`, `related_order_ids`
- **Logic:** Join orders→customers bằng customer_id, tìm các order khác cùng customer_unique_id

### 3.3 Order & Product Agent (`src/agents/order_product_agent.py`)
- **Vai trò:** Kiểm tra order items, sellers, products, categories
- **Quyền truy cập:** `order_items`, `products`, `sellers`
- **Input:** `order_id`
- **Output:** `order_ids`, `item_ids`, `seller_ids`, `product_ids`, `category_names`
- **Logic:** Iterate order_items, extract unique values với array limits

### 3.4 Payment Agent (`src/agents/payment_agent.py`)
- **Vai trò:** Tổng hợp và đối soát payment
- **Quyền truy cập:** `order_payments`, `order_items`
- **Input:** `order_id`
- **Output:** `payment_reconciliation` (item/freight/expected/payment totals, difference, reconciled), `payment_ids`
- **Logic:** Tính sum prices + freight vs sum payments, kiểm tra sai số ≤ 0.10 BRL

### 3.5 Delivery Agent (`src/agents/delivery_agent.py`)
- **Vai trò:** Phân tích delivery variance và seller handoff
- **Quyền truy cập:** `orders`, `order_items`
- **Input:** `order_id`
- **Output:** `delivery_analysis` (timestamps, variance hours, seller handoff analysis)
- **Logic:** Tính (delivered - estimated) hours, (carrier_handoff - shipping_limit) hours cho mỗi seller

### 3.6 Policy Agent (`src/agents/policy_agent.py`)
- **Vai trò:** Áp dụng EC_POLICY_V2, xác định issue/cause/refund/actions
- **Quyền truy cập:** Output từ tất cả agents trên
- **Input:** order_status + data từ 4 agents
- **Output:** `case_assessment`, `root_cause_analysis`, `financial_resolution`, `resolution_actions`
- **Logic:** Áp dụng policy theo thứ tự ưu tiên (canceled > unavailable > late_seller > late_logistics > split_payment > unsupported)

### 3.7 Verifier Agent (`src/agents/verifier_agent.py`)
- **Vai trò:** Validate schema, evidence IDs, array limits
- **Quyền truy cập:** Final output dict
- **Input:** Assembled output dict
- **Output:** Validated output dict
- **Logic:** Truncate arrays, validate evidence format, verify case_status/refund consistency

## 4. Luồng Handoff

```
Input JSON
    │
    ▼
Coordinator ─────────────┐
    │                    │
    ├─→ Customer Agent   │
    │   └─→ customer_context ──────────────────┐
    │                                           │
    ├─→ Order&Product Agent                     │
    │   └─→ affected_entities, product_context ─┤
    │                                           │
    ├─→ Payment Agent                           │
    │   └─→ payment_reconciliation, payment_ids ┤
    │                                           │
    ├─→ Delivery Agent                          │
    │   └─→ delivery_analysis ─────────────────┤
    │                                           │
    │  ┌────────────────────────────────────────┘
    │  │ (All agent outputs collected)
    │  ▼
    ├─→ Policy Agent
    │   └─→ case_assessment, root_cause, refund, actions
    │
    ├─→ Build Evidence IDs
    │
    ├─→ Assemble Full Output
    │
    └─→ Verifier Agent
        └─→ Validated Output → EC_XXX.json
```

## 5. Data Layer (`src/data_loader.py`)

Singleton pattern load 9 CSV files một lần duy nhất:
- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`
- `olist_customers_dataset.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`
- `product_category_name_translation.csv`
- `olist_order_reviews_dataset.csv`
- `olist_geolocation_dataset.csv`

## 6. LLM Integration (`src/llm_client.py`)

- **Model:** `llama-3.1-8b-instant` (8B params, ≤ 10B limit)
- **Provider:** Groq API (free tier)
- **Mục đích:** Sinh reasoning summary cho trace entries
- **Không dùng cho:** Bất kỳ logic tính toán hay quyết định nào
- **Fallback:** Template deterministic nếu API fail

## 7. File Structure

```
├── data/                          # 9 CSV files
├── input/                         # 50 input cases (EC_001-EC_050.json)
├── output/                        # 50 output results (EC_001-EC_050.json)
├── logging/
│   ├── trace.jsonl                # Agent execution trace
│   └── metadata.json              # Model & runtime info
├── src/
│   ├── __init__.py
│   ├── data_loader.py             # Singleton CSV loader
│   ├── llm_client.py              # Groq API client
│   ├── main.py                    # Entry point
│   └── agents/
│       ├── __init__.py
│       ├── coordinator_agent.py
│       ├── customer_agent.py
│       ├── order_product_agent.py
│       ├── payment_agent.py
│       ├── delivery_agent.py
│       ├── policy_agent.py
│       └── verifier_agent.py
├── architecture.md                # This file
├── individual_5SoCuoiMHV_HoVaTen.md
├── .env                           # API keys (not committed)
├── .gitignore
└── README.md
```
