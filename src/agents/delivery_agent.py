"""Delivery Agent: tinh delivery variance va seller handoff variance.

Quyen truy cap: olist_orders_dataset, olist_order_items_dataset.
Agent nay chi bao cao SO GIO lech, khong ket luan ben nao chiu trach nhiem.
"""

from ..data_store import clean, parse_ts

AGENT_NAME = "delivery_agent"


def _variance_hours(later, earlier):
    """So gio chenh lech, lam tron 2 chu so. Thieu du lieu -> None."""
    if later is None or earlier is None:
        return None
    return round((later - earlier).total_seconds() / 3600.0, 2)


def analyze(store, order_id: str) -> dict:
    order = store.get_order(order_id)
    items = store.get_items(order_id)

    if order is None:
        return {
            "delivered_at": None,
            "estimated_delivery_at": None,
            "carrier_handoff_at": None,
            "delivery_variance_hours": None,
            "seller_handoff_analysis": [],
            "late_handoff_seller_ids": [],
            "is_late_delivery": False,
        }

    # Xuat ra chuoi GOC tu CSV, khong phai str(datetime).
    delivered_raw = clean(order["order_delivered_customer_date"])
    estimated_raw = clean(order["order_estimated_delivery_date"])
    carrier_raw = clean(order["order_delivered_carrier_date"])

    delivered = parse_ts(delivered_raw)
    estimated = parse_ts(estimated_raw)
    carrier = parse_ts(carrier_raw)

    delivery_variance = _variance_hours(delivered, estimated)

    # Gom item theo seller, lay shipping_limit_date SOM NHAT cua tung seller.
    limits_by_seller: dict[str, object] = {}
    raw_by_seller: dict[str, str] = {}
    for item in items:
        seller_id = item["seller_id"]
        raw = clean(item["shipping_limit_date"])
        ts = parse_ts(raw)
        if ts is None:
            continue
        if seller_id not in limits_by_seller or ts < limits_by_seller[seller_id]:
            limits_by_seller[seller_id] = ts
            raw_by_seller[seller_id] = raw

    handoff_analysis = []
    late_sellers = []
    seen = set()
    for item in items:  # duyet theo thu tu order_item_id -> thu tu on dinh
        seller_id = item["seller_id"]
        if seller_id in seen:
            continue
        seen.add(seller_id)

        limit_ts = limits_by_seller.get(seller_id)
        variance = _variance_hours(carrier, limit_ts)
        late = variance is not None and variance > 0

        handoff_analysis.append(
            {
                "seller_id": seller_id,
                "shipping_limit_at": raw_by_seller.get(seller_id),
                "handoff_variance_hours": variance,
                "late_handoff": late,
            }
        )
        if late:
            late_sellers.append(seller_id)

    return {
        "delivered_at": delivered_raw,
        "estimated_delivery_at": estimated_raw,
        "carrier_handoff_at": carrier_raw,
        "delivery_variance_hours": delivery_variance,
        "seller_handoff_analysis": handoff_analysis,
        "late_handoff_seller_ids": late_sellers,
        "is_late_delivery": delivery_variance is not None and delivery_variance > 0,
    }
