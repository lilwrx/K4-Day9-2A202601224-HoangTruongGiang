"""
LangChain @tool wrappers around DataStore. These are the functions the
data_agent LLM (and, via handoff, other agents in the multi-agent system)
call to read data/ — the model itself never sees raw CSVs, only these
JSON-serializable results, so it can't fabricate rows that aren't there.
"""

from __future__ import annotations

from langchain_core.tools import tool

from .data_store import get_data_store
from .schema import get_schema_overview


@tool
def get_schema() -> str:
    """Return the data schema: every table's columns, types, and how the
    tables join (order_id, customer_id, product_id, seller_id, etc). Call
    this first when unsure which table or column holds a piece of data."""
    return get_schema_overview()


@tool
def fetch_order_bundle(order_id: str) -> dict:
    """Fetch everything known about one order in a single call: the order
    row, its customer, all order_items, all payments, all reviews, the
    referenced products and sellers, product category English translations,
    and the customer's other order_ids. Returns {"found": false} if the
    order_id does not exist in orders.csv. This is the primary tool for
    investigating a case's claimed_order_id."""
    return get_data_store().fetch_order_bundle(order_id)


@tool
def get_order(order_id: str) -> dict | None:
    """Fetch a single row from olist_orders_dataset.csv by order_id, or
    None if it does not exist."""
    return get_data_store().get_order(order_id)


@tool
def get_customer(customer_id: str) -> dict | None:
    """Fetch a single row from olist_customers_dataset.csv by customer_id
    (the per-order customer key, not customer_unique_id), or None if it
    does not exist."""
    return get_data_store().get_customer(customer_id)


@tool
def get_order_items(order_id: str) -> list[dict]:
    """Fetch all olist_order_items_dataset.csv rows for one order_id.
    Empty list if the order has no items."""
    return get_data_store().get_order_items(order_id)


@tool
def get_order_payments(order_id: str) -> list[dict]:
    """Fetch all olist_order_payments_dataset.csv rows for one order_id.
    Each row is one payment_sequential entry; sum payment_value across rows
    for the order total. Empty list if the order has no payments."""
    return get_data_store().get_order_payments(order_id)


@tool
def get_order_reviews(order_id: str) -> list[dict]:
    """Fetch all olist_order_reviews_dataset.csv rows for one order_id.
    Empty list if the order has no reviews."""
    return get_data_store().get_order_reviews(order_id)


@tool
def get_products(product_ids: list[str]) -> list[dict]:
    """Fetch olist_products_dataset.csv rows for the given product_ids.
    Unknown IDs are silently skipped; result may be shorter than input."""
    return get_data_store().get_products(product_ids)


@tool
def get_sellers(seller_ids: list[str]) -> list[dict]:
    """Fetch olist_sellers_dataset.csv rows for the given seller_ids.
    Unknown IDs are silently skipped; result may be shorter than input."""
    return get_data_store().get_sellers(seller_ids)


@tool
def get_category_translation(category_names: list[str]) -> dict:
    """Translate Portuguese product_category_name values to English using
    product_category_name_translation.csv. Returns {name: english_name},
    with english_name = None for names not found in the translation table."""
    return get_data_store().get_category_translation(category_names)


@tool
def get_geolocation(zip_code_prefix: str) -> dict | None:
    """Fetch one representative lat/lng/city/state row from
    olist_geolocation_dataset.csv for a zip_code_prefix. The prefix maps to
    many rows in the source data; this returns the first one, so treat it
    as approximate, not a unique key. None if the prefix is not found."""
    return get_data_store().get_geolocation(zip_code_prefix)


@tool
def get_related_order_ids(customer_unique_id: str, exclude_order_id: str = "") -> list[str]:
    """Fetch other order_ids placed by the same customer_unique_id (i.e.
    the same real customer across multiple customer_id rows), excluding
    exclude_order_id if given. Capped at 5 results."""
    return get_data_store().get_related_order_ids(
        customer_unique_id, exclude_order_id=exclude_order_id or None
    )


ALL_TOOLS = [
    get_schema,
    fetch_order_bundle,
    get_order,
    get_customer,
    get_order_items,
    get_order_payments,
    get_order_reviews,
    get_products,
    get_sellers,
    get_category_translation,
    get_geolocation,
    get_related_order_ids,
]
