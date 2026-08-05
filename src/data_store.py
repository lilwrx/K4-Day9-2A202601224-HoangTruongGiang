import csv
from datetime import datetime
from typing import Optional

from . import config


# ---------- helper dùng chung ----------

def parse_ts(value: Optional[str]) -> Optional[datetime]:
    """Chuỗi timestamp CSV -> datetime. Chuỗi rỗng/None -> None (bẫy #2)."""
    if value is None or not value.strip():
        return None
    return datetime.strptime(value.strip(), config.TS_FORMAT)


def clean(value: Optional[str]) -> Optional[str]:
    """Chuỗi rỗng -> None, để phân biệt 'thiếu dữ liệu' với 'chuỗi rỗng'."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def _read_csv(path, encoding="utf-8"):
    """Đọc CSV thành dict từng dòng. Generator nên không giữ cả file trong RAM."""
    with open(path, "r", encoding=encoding, newline="") as fh:
        yield from csv.DictReader(fh)


# ---------- kho dữ liệu ----------

class DataStore:
    """Kho dữ liệu chỉ-đọc, dùng chung cho mọi agent."""

    def __init__(self, data_dir=None):
        self.data_dir = data_dir or config.DATA_DIR

        self.orders: dict[str, dict] = {}                       # order_id -> row
        self.items_by_order: dict[str, list[dict]] = {}         # order_id -> [item]
        self.payments_by_order: dict[str, list[dict]] = {}      # order_id -> [payment]
        self.customers: dict[str, dict] = {}                    # customer_id -> row
        self.orders_by_unique_customer: dict[str, list[str]] = {}  # unique_id -> [order_id]
        self.products: dict[str, dict] = {}                     # product_id -> row
        self.seller_ids: set[str] = set()
        self.category_en: dict[str, str] = {}                   # pt -> en

        self._load()

    def _load(self) -> None:
        # customers phải load TRƯỚC orders, vì lúc duyệt orders ta cần
        # tra ngay customer_unique_id để dựng index lịch sử khách hàng.
        for row in _read_csv(self.data_dir / "olist_customers_dataset.csv"):
            self.customers[row["customer_id"]] = row

        for row in _read_csv(self.data_dir / "olist_orders_dataset.csv"):
            oid = row["order_id"]
            self.orders[oid] = row
            cust = self.customers.get(row["customer_id"])
            if cust:
                # append theo đúng thứ tự dòng CSV -> array output ổn định (bẫy #3)
                self.orders_by_unique_customer.setdefault(
                    cust["customer_unique_id"], []
                ).append(oid)

        for row in _read_csv(self.data_dir / "olist_order_items_dataset.csv"):
            self.items_by_order.setdefault(row["order_id"], []).append(row)

        for row in _read_csv(self.data_dir / "olist_order_payments_dataset.csv"):
            self.payments_by_order.setdefault(row["order_id"], []).append(row)

        for row in _read_csv(self.data_dir / "olist_products_dataset.csv"):
            self.products[row["product_id"]] = row

        for row in _read_csv(self.data_dir / "olist_sellers_dataset.csv"):
            self.seller_ids.add(row["seller_id"])

        # File translation có BOM -> utf-8-sig, nếu không key đầu sẽ là
        # '\ufeffproduct_category_name' và mọi tra cứu trượt im lặng (bẫy #1).
        for row in _read_csv(
            self.data_dir / "product_category_name_translation.csv",
            encoding="utf-8-sig",
        ):
            self.category_en[row["product_category_name"]] = \
                row["product_category_name_english"]

        # Sắp xếp theo khóa nghiệp vụ, ép int để "10" không đứng trước "2" (bẫy #3).
        for rows in self.items_by_order.values():
            rows.sort(key=lambda r: int(r["order_item_id"]))
        for rows in self.payments_by_order.values():
            rows.sort(key=lambda r: int(r["payment_sequential"]))

    # ---------- API tra cứu cho agent ----------

    def get_order(self, order_id: str) -> Optional[dict]:
        return self.orders.get(order_id)

    def get_items(self, order_id: str) -> list[dict]:
        return self.items_by_order.get(order_id, [])       # không có item -> []

    def get_payments(self, order_id: str) -> list[dict]:
        return self.payments_by_order.get(order_id, [])

    def get_customer(self, customer_id: str) -> Optional[dict]:
        return self.customers.get(customer_id)

    def get_orders_of_unique_customer(self, unique_id: str) -> list[str]:
        return self.orders_by_unique_customer.get(unique_id, [])

    def get_product(self, product_id: str) -> Optional[dict]:
        return self.products.get(product_id)

    def has_seller(self, seller_id: str) -> bool:
        return seller_id in self.seller_ids

    def stats(self) -> dict:
        return {
            "orders": len(self.orders),
            "customers": len(self.customers),
            "item_rows": sum(len(v) for v in self.items_by_order.values()),
            "payment_rows": sum(len(v) for v in self.payments_by_order.values()),
            "products": len(self.products),
            "sellers": len(self.seller_ids),
        } 