"""Customer Agent: xac dinh danh tinh khach hang va lich su order.

Quyen truy cap: olist_customers_dataset, olist_orders_dataset.
Chi san xuat su kien, khong ket luan policy.
"""

from ..config import LIMITS

AGENT_NAME = "customer_agent"


def analyze(store, order_id: str) -> dict:
    order = store.get_order(order_id)
    if order is None:
        return {
            "customer_unique_id": None,
            "related_order_ids": [],
            "related_order_count": 0,
            "is_repeat_customer": False,
        }

    customer = store.get_customer(order["customer_id"])
    unique_id = customer["customer_unique_id"] if customer else None

    # customer_id la 1-1 voi order, phai qua customer_unique_id moi ra lich su.
    all_orders = store.get_orders_of_unique_customer(unique_id) if unique_id else []
    related = [oid for oid in all_orders if oid != order_id]

    return {
        "customer_unique_id": unique_id,
        # Cat 5 cho output, nhung dem tren tap day du de xet repeat_customer.
        "related_order_ids": related[: LIMITS["related_order_ids"]],
        "related_order_count": len(related),
        "is_repeat_customer": len(related) > 0,
    }
