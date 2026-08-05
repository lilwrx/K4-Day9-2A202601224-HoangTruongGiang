"""Order & Product Agent: kiem tra order, item, seller, product va category.

Quyen truy cap: olist_orders_dataset, olist_order_items_dataset,
olist_products_dataset, olist_sellers_dataset.
"""

from ..config import LIMITS
from ..data_store import clean

AGENT_NAME = "order_product_agent"


def _dedupe(values: list) -> list:
    """Loai trung nhung giu thu tu xuat hien lan dau (array phai on dinh)."""
    seen = set()
    out = []
    for v in values:
        if v is not None and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def analyze(store, order_id: str) -> dict:
    order = store.get_order(order_id)
    items = store.get_items(order_id)

    item_ids = [f"{order_id}:{it['order_item_id']}" for it in items]
    seller_ids = _dedupe([it["seller_id"] for it in items])
    product_ids = _dedupe([it["product_id"] for it in items])

    categories = []
    for pid in product_ids:
        product = store.get_product(pid)
        if product:
            # Giu ten goc tieng Bo dao Nha: day la gia tri truc tiep cua cot
            # sau khi join. File translation chi la phu luc cua dataset goc.
            category = clean(product.get("product_category_name"))
            if category:
                categories.append(category)
    categories = _dedupe(categories)

    return {
        "order_status": order["order_status"] if order else None,
        "order_exists": order is not None,
        "purchase_at": clean(order["order_purchase_timestamp"]) if order else None,
        "item_ids": item_ids[: LIMITS["item_ids"]],
        "seller_ids": seller_ids[: LIMITS["seller_ids"]],
        "product_ids": product_ids[: LIMITS["product_ids"]],
        "category_names": categories[: LIMITS["category_names"]],
        # Cac count tinh tren tap DAY DU truoc khi cat, de Policy Agent
        # xet secondary issue khong bi lech boi gioi han array.
        "item_count": len(items),
        "seller_count": len(seller_ids),
        "product_count": len(product_ids),
        "category_count": len(categories),
        "all_seller_ids": seller_ids,
    }
