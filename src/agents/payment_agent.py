"""Payment Agent: tong hop payment row va doi soat voi item + freight.

Quyen truy cap: olist_order_items_dataset, olist_order_payments_dataset.
"""

from ..config import CURRENCY, LIMITS, RECONCILE_TOLERANCE_BRL

AGENT_NAME = "payment_agent"


def analyze(store, order_id: str) -> dict:
    items = store.get_items(order_id)
    payments = store.get_payments(order_id)

    # Cong het roi moi lam tron. Lam tron tung dong roi cong se tich luy
    # sai so va co the lat co reconciled quanh nguong 0.10 BRL.
    item_total = round(sum(float(it["price"]) for it in items), 2)
    freight_total = round(sum(float(it["freight_value"]) for it in items), 2)
    payment_total = round(sum(float(p["payment_value"]) for p in payments), 2)

    if items:
        expected_total = round(
            sum(float(it["price"]) + float(it["freight_value"]) for it in items), 2
        )
        difference = round(payment_total - expected_total, 2)
        reconciled = abs(difference) <= RECONCILE_TOLERANCE_BRL
    else:
        # De bai neu dich danh DUNG BA truong nay la null khi khong co item row.
        # item_total/freight_total van la 0.0, khong tu suy dien them.
        expected_total = None
        difference = None
        reconciled = None

    payment_types = []
    for p in payments:
        if p["payment_type"] not in payment_types:
            payment_types.append(p["payment_type"])

    return {
        "currency": CURRENCY,
        "item_total_brl": item_total,
        "freight_total_brl": freight_total,
        "expected_total_brl": expected_total,
        "payment_total_brl": payment_total,
        "difference_brl": difference,
        "reconciled": reconciled,
        "payment_types": payment_types,
        "payment_ids": [
            f"{order_id}:{p['payment_sequential']}" for p in payments
        ][: LIMITS["payment_ids"]],
        "payment_count": len(payments),
        "all_payment_sequentials": [p["payment_sequential"] for p in payments],
    }
