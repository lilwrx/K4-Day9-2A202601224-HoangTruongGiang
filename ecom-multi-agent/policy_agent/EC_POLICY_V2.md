
## Quy tắc nghiệp vụ

Áp dụng `EC_POLICY_V2` theo thứ tự ưu tiên dưới đây. Mọi phép tính tiền và số giờ được làm tròn 2 chữ số thập phân.

| Primary issue               | Điều kiện                                                                              | Responsible party                               |        Refund | Action                          |
| --------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------- | ------------: | ------------------------------- |
| `canceled_order_paid`     | `order_status = canceled` và tổng payment > 0                                         | `platform` / `OLIST_PLATFORM`               | Tổng payment | `issue_full_refund`           |
| `unavailable_order_paid`  | `order_status = unavailable` và tổng payment > 0                                      | `platform` / `OLIST_PLATFORM`               | Tổng payment | `issue_full_refund`           |
| `late_delivery_seller`    | Giao sau estimated date và carrier nhận hàng sau ít nhất một`shipping_limit_date` | `seller` / các seller vi phạm               | Tổng freight | `refund_freight`              |
| `late_delivery_logistics` | Giao sau estimated date và không seller nào bàn giao muộn                            | `logistics_provider` / `LOGISTICS_PROVIDER` | Tổng freight | `refund_freight`              |
| `valid_split_payment`     | Có từ 2 payment row; tổng payment khớp tổng item + freight trong sai số 0.10 BRL    | Không có                                      |             0 | `explain_valid_split_payment` |
| `unsupported_late_claim`  | Đơn giao không muộn hơn estimated date và payment khớp                             | Không có                                      |             0 | `reject_late_refund`          |

Secondary issues được thêm theo đúng thứ tự sau khi thỏa điều kiện:

1. `multi_item_order`: có từ 2 item row.
2. `multi_seller_order`: có từ 2 seller khác nhau.
3. `split_payment`: có từ 2 payment row.
4. `repeat_customer`: cùng `customer_unique_id` có order khác.
5. `multiple_categories`: có từ 2 category khác nhau.

Root-cause code tương ứng:

- `SELLER_HANDOFF_AFTER_LIMIT`
- `CARRIER_DELIVERED_AFTER_ESTIMATE`
- `ORDER_CANCELED_AFTER_PAYMENT`
- `ORDER_UNAVAILABLE_AFTER_PAYMENT`
- `MULTIPLE_PAYMENTS_RECONCILED`
- `DELIVERY_WITHIN_ESTIMATE`

Công thức phân tích:

```text
delivery_variance_hours
  = order_delivered_customer_date - order_estimated_delivery_date

handoff_variance_hours
  = order_delivered_carrier_date - shipping_limit_date sớm nhất của seller

expected_total_brl
  = sum(order_items.price) + sum(order_items.freight_value)

difference_brl
  = sum(order_payments.payment_value) - expected_total_brl

reconciled
  = abs(difference_brl) <= 0.10 BRL
```

Với order không có item row, `expected_total_brl`, `difference_brl` và `reconciled` phải là `null`; item, seller, product, category và seller handoff để mảng rỗng.

Các action bổ sung được đặt sau action chính theo thứ tự: `review_seller_handoff` hoặc `review_carrier_delay`, `verify_refund_completion`, `coordinate_multi_seller_case`, `verify_payment_allocation`. Không thêm `verify_payment_allocation` khi primary issue là `valid_split_payment` vì action chính đã giải thích split payment.
