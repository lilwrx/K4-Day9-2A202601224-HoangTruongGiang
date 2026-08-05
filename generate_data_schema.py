"""
Fetch information about all CSV files in the data/ folder and generate a
schema documentation file (data_schema.md) that describes each dataset's
columns, dtypes, null counts, sample values, and an entity-relationship
diagram (Mermaid ERD) showing how the tables relate to each other.

Usage:
    python generate_data_schema.py
"""

import os
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = Path(__file__).parent / "data_schema.md"

# Human-readable descriptions for each table (Olist Brazilian e-commerce dataset)
TABLE_DESCRIPTIONS = {
    "olist_customers_dataset.csv": "Customer identifiers and location (city/state/zip) for each order.",
    "olist_geolocation_dataset.csv": "Brazilian zip code prefixes mapped to lat/lng coordinates, city, and state.",
    "olist_orders_dataset.csv": "Core order records with status and purchase/delivery timestamps.",
    "olist_order_items_dataset.csv": "Line items within each order: product, seller, price, and freight value.",
    "olist_order_payments_dataset.csv": "Payment details for each order, including payment type and installments.",
    "olist_order_reviews_dataset.csv": "Customer review scores and comments left for orders.",
    "olist_products_dataset.csv": "Product catalog with category, dimensions, and weight.",
    "olist_sellers_dataset.csv": "Seller identifiers and location (city/state/zip).",
    "product_category_name_translation.csv": "Maps Portuguese product category names to English.",
}

# Column-level descriptions, keyed by table filename -> column name
COLUMN_DESCRIPTIONS = {
    "olist_customers_dataset.csv": {
        "customer_id": "Order-specific customer key (join key for orders table).",
        "customer_unique_id": "Stable identifier for a customer across multiple orders.",
        "customer_zip_code_prefix": "First digits of the customer's zip code.",
        "customer_city": "Customer's city.",
        "customer_state": "Customer's state (2-letter code).",
    },
    "olist_geolocation_dataset.csv": {
        "geolocation_zip_code_prefix": "First digits of a Brazilian zip code.",
        "geolocation_lat": "Latitude.",
        "geolocation_lng": "Longitude.",
        "geolocation_city": "City name.",
        "geolocation_state": "State (2-letter code).",
    },
    "olist_orders_dataset.csv": {
        "order_id": "Unique order identifier (primary key).",
        "customer_id": "Foreign key to olist_customers_dataset.customer_id.",
        "order_status": "Order status (e.g. delivered, shipped, canceled).",
        "order_purchase_timestamp": "Timestamp the order was placed.",
        "order_approved_at": "Timestamp payment was approved.",
        "order_delivered_carrier_date": "Timestamp order was handed to the logistics carrier.",
        "order_delivered_customer_date": "Timestamp order was delivered to the customer.",
        "order_estimated_delivery_date": "Estimated delivery date shown to the customer at purchase.",
    },
    "olist_order_items_dataset.csv": {
        "order_id": "Foreign key to olist_orders_dataset.order_id.",
        "order_item_id": "Sequential item number within the order.",
        "product_id": "Foreign key to olist_products_dataset.product_id.",
        "seller_id": "Foreign key to olist_sellers_dataset.seller_id.",
        "shipping_limit_date": "Seller's deadline to hand the item to the carrier.",
        "price": "Item price.",
        "freight_value": "Freight/shipping cost for the item.",
    },
    "olist_order_payments_dataset.csv": {
        "order_id": "Foreign key to olist_orders_dataset.order_id.",
        "payment_sequential": "Sequence number for orders paid with multiple payment methods.",
        "payment_type": "Payment method (e.g. credit_card, boleto, voucher).",
        "payment_installments": "Number of installments chosen.",
        "payment_value": "Amount paid via this payment record.",
    },
    "olist_order_reviews_dataset.csv": {
        "review_id": "Unique review identifier.",
        "order_id": "Foreign key to olist_orders_dataset.order_id.",
        "review_score": "Rating from 1 to 5.",
        "review_comment_title": "Optional review title.",
        "review_comment_message": "Optional review text.",
        "review_creation_date": "Timestamp the review was created.",
        "review_answer_timestamp": "Timestamp the seller/platform responded.",
    },
    "olist_products_dataset.csv": {
        "product_id": "Unique product identifier (primary key).",
        "product_category_name": "Category name in Portuguese (join key to translation table).",
        "product_name_lenght": "Character length of the product name.",
        "product_description_lenght": "Character length of the product description.",
        "product_photos_qty": "Number of photos listed for the product.",
        "product_weight_g": "Product weight in grams.",
        "product_length_cm": "Product length in cm.",
        "product_height_cm": "Product height in cm.",
        "product_width_cm": "Product width in cm.",
    },
    "olist_sellers_dataset.csv": {
        "seller_id": "Unique seller identifier (primary key).",
        "seller_zip_code_prefix": "First digits of the seller's zip code.",
        "seller_city": "Seller's city.",
        "seller_state": "Seller's state (2-letter code).",
    },
    "product_category_name_translation.csv": {
        "product_category_name": "Category name in Portuguese (primary key, joins to products table).",
        "product_category_name_english": "Category name translated to English.",
    },
}

# Relationships used to draw the Mermaid ERD: (child_table, fk_column, parent_table, pk_column)
RELATIONSHIPS = [
    ("olist_orders_dataset.csv", "customer_id", "olist_customers_dataset.csv", "customer_id"),
    ("olist_order_items_dataset.csv", "order_id", "olist_orders_dataset.csv", "order_id"),
    ("olist_order_items_dataset.csv", "product_id", "olist_products_dataset.csv", "product_id"),
    ("olist_order_items_dataset.csv", "seller_id", "olist_sellers_dataset.csv", "seller_id"),
    ("olist_order_payments_dataset.csv", "order_id", "olist_orders_dataset.csv", "order_id"),
    ("olist_order_reviews_dataset.csv", "order_id", "olist_orders_dataset.csv", "order_id"),
    ("olist_products_dataset.csv", "product_category_name", "product_category_name_translation.csv", "product_category_name"),
    ("olist_geolocation_dataset.csv", "geolocation_zip_code_prefix", "olist_customers_dataset.csv", "customer_zip_code_prefix"),
]

ENTITY_NAME = {
    "olist_customers_dataset.csv": "customers",
    "olist_geolocation_dataset.csv": "geolocation",
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "category_translation",
}


def profile_csv(path: Path) -> dict:
    df = pd.read_csv(path, encoding="utf-8-sig")
    size_mb = path.stat().st_size / (1024 * 1024)
    columns = []
    for col in df.columns:
        series = df[col]
        columns.append(
            {
                "name": col,
                "dtype": str(series.dtype),
                "nulls": int(series.isna().sum()),
                "null_pct": round(series.isna().mean() * 100, 2),
                "unique": int(series.nunique(dropna=True)),
                "sample": series.dropna().iloc[0] if series.notna().any() else "",
            }
        )
    return {
        "file": path.name,
        "rows": len(df),
        "cols": len(df.columns),
        "size_mb": round(size_mb, 2),
        "columns": columns,
    }


def render_columns_table(profile: dict) -> str:
    fname = profile["file"]
    col_desc = COLUMN_DESCRIPTIONS.get(fname, {})
    lines = [
        "| Column | Type | Nulls (%) | Unique | Description | Sample |",
        "|---|---|---|---|---|---|",
    ]
    for col in profile["columns"]:
        desc = col_desc.get(col["name"], "")
        sample = str(col["sample"]).replace("|", "\\|")
        if len(sample) > 40:
            sample = sample[:37] + "..."
        lines.append(
            f"| `{col['name']}` | {col['dtype']} | {col['nulls']} ({col['null_pct']}%) | "
            f"{col['unique']} | {desc} | `{sample}` |"
        )
    return "\n".join(lines)


def render_mermaid_erd() -> str:
    lines = ["```mermaid", "erDiagram"]
    for child, fk, parent, pk in RELATIONSHIPS:
        child_e = ENTITY_NAME[child]
        parent_e = ENTITY_NAME[parent]
        lines.append(f'    {parent_e} ||--o{{ {child_e} : "{pk} -> {fk}"')
    lines.append("```")
    return "\n".join(lines)


def main():
    csv_files = sorted(DATA_DIR.glob("*.csv"))
    profiles = [profile_csv(f) for f in csv_files]

    out = []
    out.append("# Data Schema")
    out.append("")
    out.append(
        f"Auto-generated documentation for the {len(profiles)} CSV files in "
        f"[`data/`](data/) — the Olist Brazilian e-commerce public dataset."
    )
    out.append("")
    out.append("## Overview")
    out.append("")
    out.append("| Table | Rows | Columns | Size (MB) | Description |")
    out.append("|---|---|---|---|---|")
    for p in profiles:
        desc = TABLE_DESCRIPTIONS.get(p["file"], "")
        out.append(f"| `{p['file']}` | {p['rows']} | {p['cols']} | {p['size_mb']} | {desc} |")
    out.append("")

    out.append("## Entity-Relationship Diagram")
    out.append("")
    out.append(render_mermaid_erd())
    out.append("")

    out.append("## Table Details")
    for p in profiles:
        out.append("")
        out.append(f"### `{p['file']}`")
        out.append("")
        out.append(TABLE_DESCRIPTIONS.get(p["file"], ""))
        out.append("")
        out.append(f"- Rows: {p['rows']}")
        out.append(f"- Columns: {p['cols']}")
        out.append(f"- File size: {p['size_mb']} MB")
        out.append("")
        out.append(render_columns_table(p))

    OUTPUT_FILE.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE} ({len(profiles)} tables profiled)")


if __name__ == "__main__":
    main()
