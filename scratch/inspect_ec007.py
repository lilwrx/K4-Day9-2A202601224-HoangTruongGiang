import json
import os
import pandas as pd

project_dir = r"d:\VinAI\K4-Day9-2A202601224-HoangTruongGiang"
data_dir = os.path.join(project_dir, 'data')

orders = pd.read_csv(os.path.join(data_dir, 'olist_orders_dataset.csv'))
order_items = pd.read_csv(os.path.join(data_dir, 'olist_order_items_dataset.csv'))
order_payments = pd.read_csv(os.path.join(data_dir, 'olist_order_payments_dataset.csv'))
customers = pd.read_csv(os.path.join(data_dir, 'olist_customers_dataset.csv'))
products = pd.read_csv(os.path.join(data_dir, 'olist_products_dataset.csv'))

# Inspect EC_007 claimed order id: cf788ee4258fde5130bb5651bda63918
oid = 'cf788ee4258fde5130bb5651bda63918'
o = orders[orders['order_id'] == oid].iloc[0]
items = order_items[order_items['order_id'] == oid]
pmts = order_payments[order_payments['order_id'] == oid]
c = customers[customers['customer_id'] == o['customer_id']].iloc[0]

print("--- EC_007 Raw Data ---")
print("Order status:", o['order_status'])
print("Customer unique id:", c['customer_unique_id'])

# Check items
print("\nItems:")
for _, it in items.iterrows():
    p = products[products['product_id'] == it['product_id']].iloc[0]
    print(f"  item_id={it['order_item_id']}, seller={it['seller_id']}, prod={it['product_id']}, cat={p['product_category_name']}")

# Check payments
print("\nPayments:")
for _, pmt in pmts.iterrows():
    print(f"  seq={pmt['payment_sequential']}, type={pmt['payment_type']}, val={pmt['payment_value']}")

# Check related orders
rel_c = customers[customers['customer_unique_id'] == c['customer_unique_id']]
rel_o = orders[orders['customer_id'].isin(rel_c['customer_id'])]
print("\nRelated orders count:", len(rel_o) - 1)
