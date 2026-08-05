import json
import os
import pandas as pd

project_dir = r"d:\VinAI\K4-Day9-2A202601224-HoangTruongGiang"
data_dir = os.path.join(project_dir, 'data')
input_dir = os.path.join(project_dir, 'input')

orders = pd.read_csv(os.path.join(data_dir, 'olist_orders_dataset.csv'))
order_items = pd.read_csv(os.path.join(data_dir, 'olist_order_items_dataset.csv'))
order_payments = pd.read_csv(os.path.join(data_dir, 'olist_order_payments_dataset.csv'))

# Check all 50 cases for missing timestamps or dates
for i in range(1, 51):
    case_file = f"EC_{i:03d}.json"
    with open(os.path.join(input_dir, case_file), 'r', encoding='utf-8') as f:
        inc = json.load(f)
    oid = inc['customer_request']['claimed_order_id']
    o = orders[orders['order_id'] == oid].iloc[0]
    
    status = o['order_status']
    deliv_cust = o['order_delivered_customer_date']
    deliv_car = o['order_delivered_carrier_date']
    est = o['order_estimated_delivery_date']
    
    items = order_items[order_items['order_id'] == oid]
    
    if pd.isna(deliv_cust) or pd.isna(deliv_car) or pd.isna(est):
        print(f"{case_file} ({oid}) status={status}: deliv_cust={deliv_cust}, deliv_car={deliv_car}, est={est}, items={len(items)}")
