"""
Loads and indexes the Olist CSVs from data/ once per process, then serves
joined lookups keyed by order_id / customer_id / product_id / seller_id.

This is the deterministic data-access layer: it never calls an LLM and never
invents values. Anything not present in the CSVs comes back as None or an
empty list, so callers (agents, policy logic) can tell "missing" apart from
"zero".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd

# ecom-multi-agent/data_agent/tools/data_store.py -> repo_root/data
DATA_DIR = Path(__file__).resolve().parents[3] / "data"

CUSTOMERS_CSV = DATA_DIR / "olist_customers_dataset.csv"
GEOLOCATION_CSV = DATA_DIR / "olist_geolocation_dataset.csv"
ORDERS_CSV = DATA_DIR / "olist_orders_dataset.csv"
ORDER_ITEMS_CSV = DATA_DIR / "olist_order_items_dataset.csv"
ORDER_PAYMENTS_CSV = DATA_DIR / "olist_order_payments_dataset.csv"
ORDER_REVIEWS_CSV = DATA_DIR / "olist_order_reviews_dataset.csv"
PRODUCTS_CSV = DATA_DIR / "olist_products_dataset.csv"
SELLERS_CSV = DATA_DIR / "olist_sellers_dataset.csv"
CATEGORY_TRANSLATION_CSV = DATA_DIR / "product_category_name_translation.csv"


def _clean_record(record: dict) -> dict:
    """Replace pandas NaN (from empty CSV cells) with None so records stay
    valid, unambiguous JSON instead of a bare NaN token."""
    return {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in record.items()}


def _records_by_key(df: pd.DataFrame, key: str) -> dict:
    """Group a dataframe's rows (as dicts) by a non-unique key column.

    Uses one whole-frame to_dict("records") plus a plain Python grouping
    loop instead of df.groupby(...).to_dict(...) per group — pandas'
    per-group overhead makes the groupby version ~100x slower on a table
    with as many distinct keys as rows (order_items, order_payments)."""
    out: dict[str, list[dict]] = defaultdict(list)
    for record in df.to_dict("records"):
        out[record[key]].append(_clean_record(record))
    return dict(out)


@dataclass
class DataStore:
    """Lazily-loaded, cached view over the Olist CSVs in data/."""

    _customers: pd.DataFrame | None = field(default=None, repr=False)
    _orders: pd.DataFrame | None = field(default=None, repr=False)
    _order_items_by_order: dict | None = field(default=None, repr=False)
    _order_payments_by_order: dict | None = field(default=None, repr=False)
    _order_reviews_by_order: dict | None = field(default=None, repr=False)
    _products: pd.DataFrame | None = field(default=None, repr=False)
    _sellers: pd.DataFrame | None = field(default=None, repr=False)
    _category_translation: pd.DataFrame | None = field(default=None, repr=False)
    _geolocation_first_by_zip: pd.DataFrame | None = field(default=None, repr=False)
    _orders_by_customer_unique_id: dict | None = field(default=None, repr=False)

    # ---- lazy loaders -------------------------------------------------

    @property
    def customers(self) -> pd.DataFrame:
        if self._customers is None:
            self._customers = pd.read_csv(CUSTOMERS_CSV, dtype=str).set_index(
                "customer_id", drop=False
            )
        return self._customers

    @property
    def orders(self) -> pd.DataFrame:
        if self._orders is None:
            self._orders = pd.read_csv(ORDERS_CSV, dtype=str).set_index(
                "order_id", drop=False
            )
        return self._orders

    @property
    def order_items_by_order(self) -> dict:
        if self._order_items_by_order is None:
            df = pd.read_csv(ORDER_ITEMS_CSV, dtype=str)
            df["price"] = df["price"].astype(float)
            df["freight_value"] = df["freight_value"].astype(float)
            self._order_items_by_order = _records_by_key(df, "order_id")
        return self._order_items_by_order

    @property
    def order_payments_by_order(self) -> dict:
        if self._order_payments_by_order is None:
            df = pd.read_csv(ORDER_PAYMENTS_CSV, dtype=str)
            df["payment_value"] = df["payment_value"].astype(float)
            df["payment_sequential"] = df["payment_sequential"].astype(int)
            df["payment_installments"] = df["payment_installments"].astype(int)
            self._order_payments_by_order = _records_by_key(df, "order_id")
        return self._order_payments_by_order

    @property
    def order_reviews_by_order(self) -> dict:
        if self._order_reviews_by_order is None:
            df = pd.read_csv(ORDER_REVIEWS_CSV, dtype=str)
            self._order_reviews_by_order = _records_by_key(df, "order_id")
        return self._order_reviews_by_order

    @property
    def products(self) -> pd.DataFrame:
        if self._products is None:
            self._products = pd.read_csv(PRODUCTS_CSV, dtype=str).set_index(
                "product_id", drop=False
            )
        return self._products

    @property
    def sellers(self) -> pd.DataFrame:
        if self._sellers is None:
            self._sellers = pd.read_csv(SELLERS_CSV, dtype=str).set_index(
                "seller_id", drop=False
            )
        return self._sellers

    @property
    def category_translation(self) -> pd.DataFrame:
        if self._category_translation is None:
            self._category_translation = pd.read_csv(
                CATEGORY_TRANSLATION_CSV, encoding="utf-8-sig", dtype=str
            ).set_index("product_category_name", drop=False)
        return self._category_translation

    @property
    def geolocation_first_by_zip(self) -> pd.DataFrame:
        # geolocation is ~1M rows / 59MB and has many duplicate zip prefixes;
        # only load it on first actual use, and keep just one row per prefix.
        if self._geolocation_first_by_zip is None:
            df = pd.read_csv(GEOLOCATION_CSV, dtype=str)
            self._geolocation_first_by_zip = df.drop_duplicates(
                subset="geolocation_zip_code_prefix", keep="first"
            ).set_index("geolocation_zip_code_prefix", drop=False)
        return self._geolocation_first_by_zip

    @property
    def orders_by_customer_unique_id(self) -> dict:
        if self._orders_by_customer_unique_id is None:
            customer_lookup = self.customers[["customer_id", "customer_unique_id"]].reset_index(
                drop=True
            )
            merged = self.orders.reset_index(drop=True).merge(
                customer_lookup, on="customer_id", how="left"
            )
            out: dict[str, list[str]] = defaultdict(list)
            for order_id, unique_id in zip(merged["order_id"], merged["customer_unique_id"]):
                out[unique_id].append(order_id)
            self._orders_by_customer_unique_id = dict(out)
        return self._orders_by_customer_unique_id

    # ---- lookups --------------------------------------------------------

    def get_order(self, order_id: str) -> dict | None:
        if order_id not in self.orders.index:
            return None
        return _clean_record(self.orders.loc[order_id].to_dict())

    def get_customer(self, customer_id: str) -> dict | None:
        if customer_id not in self.customers.index:
            return None
        return _clean_record(self.customers.loc[customer_id].to_dict())

    def get_order_items(self, order_id: str) -> list[dict]:
        return self.order_items_by_order.get(order_id, [])

    def get_order_payments(self, order_id: str) -> list[dict]:
        return self.order_payments_by_order.get(order_id, [])

    def get_order_reviews(self, order_id: str) -> list[dict]:
        return self.order_reviews_by_order.get(order_id, [])

    def get_products(self, product_ids: list[str]) -> list[dict]:
        found = [pid for pid in dict.fromkeys(product_ids) if pid in self.products.index]
        if not found:
            return []
        rows = self.products.loc[found]
        if isinstance(rows, pd.Series):
            return [_clean_record(rows.to_dict())]
        return [_clean_record(r) for r in rows.to_dict("records")]

    def get_sellers(self, seller_ids: list[str]) -> list[dict]:
        found = [sid for sid in dict.fromkeys(seller_ids) if sid in self.sellers.index]
        if not found:
            return []
        rows = self.sellers.loc[found]
        if isinstance(rows, pd.Series):
            return [_clean_record(rows.to_dict())]
        return [_clean_record(r) for r in rows.to_dict("records")]

    def get_category_translation(self, category_names: list[str]) -> dict[str, str | None]:
        out: dict[str, str | None] = {}
        for name in dict.fromkeys(c for c in category_names if c):
            if name in self.category_translation.index:
                out[name] = self.category_translation.loc[name, "product_category_name_english"]
            else:
                out[name] = None
        return out

    def get_geolocation(self, zip_code_prefix: str) -> dict | None:
        if not zip_code_prefix:
            return None
        idx = self.geolocation_first_by_zip.index
        if zip_code_prefix not in idx:
            return None
        return _clean_record(self.geolocation_first_by_zip.loc[zip_code_prefix].to_dict())

    def get_related_order_ids(
        self, customer_unique_id: str, exclude_order_id: str | None = None, limit: int = 5
    ) -> list[str]:
        order_ids = self.orders_by_customer_unique_id.get(customer_unique_id, [])
        if exclude_order_id is not None:
            order_ids = [oid for oid in order_ids if oid != exclude_order_id]
        return order_ids[:limit]

    # ---- composite fetch --------------------------------------------------

    def fetch_order_bundle(self, order_id: str) -> dict:
        """
        Everything another agent needs about one order in a single call:
        the order row, its customer, items, payments, reviews, the products
        and sellers referenced by those items, category translations, and
        the customer's other order_ids (for repeat_customer detection).
        """
        order = self.get_order(order_id)
        if order is None:
            return {"order_id": order_id, "found": False}

        customer = self.get_customer(order["customer_id"])
        items = self.get_order_items(order_id)
        payments = self.get_order_payments(order_id)
        reviews = self.get_order_reviews(order_id)

        product_ids = [it["product_id"] for it in items]
        seller_ids = [it["seller_id"] for it in items]
        products = self.get_products(product_ids)
        sellers = self.get_sellers(seller_ids)

        category_names = [p["product_category_name"] for p in products if p.get("product_category_name")]
        category_translation = self.get_category_translation(category_names)

        related_order_ids: list[str] = []
        if customer and customer.get("customer_unique_id"):
            related_order_ids = self.get_related_order_ids(
                customer["customer_unique_id"], exclude_order_id=order_id
            )

        return {
            "order_id": order_id,
            "found": True,
            "order": order,
            "customer": customer,
            "items": items,
            "payments": payments,
            "reviews": reviews,
            "products": products,
            "sellers": sellers,
            "category_translation": category_translation,
            "related_order_ids": related_order_ids,
        }


@lru_cache(maxsize=1)
def get_data_store() -> DataStore:
    """Process-wide singleton so every agent/tool shares one warm cache."""
    return DataStore()
