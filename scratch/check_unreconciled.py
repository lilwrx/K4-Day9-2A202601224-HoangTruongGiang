import json
import os
import pandas as pd

project_dir = r"d:\VinAI\K4-Day9-2A202601224-HoangTruongGiang"
data_dir = os.path.join(project_dir, 'data')
input_dir = os.path.join(project_dir, 'input')

orders = pd.read_csv(os.path.join(data_dir, 'olist_orders_dataset.csv'))
order_items = pd.read_csv(os.path.join(data_dir, 'olist_order_items_dataset.csv'))
order_payments = pd.read_csv(os.path.join(data_dir, 'olist_order_payments_dataset.csv'))

unreconciled_cases = []
for i in range(1, 51):
    case_file = f"EC_{i:03d}.json"
    with open(os.path.join(input_dir, case_file), 'r', encoding='utf-8') as f:
        inc = json.load(f)
    oid = inc['customer_request']['claimed_order_id']
    items = order_items[order_items['order_id'] == oid]
    pmts = order_payments[order_payments['order_id'] == oid]
    
    if len(items) > 0:
        item_tot = round(items['price'].sum(), 2)
        freight_tot = round(items['freight_value'].sum(), 2)
        exp_tot = round(item_tot + freight_tot, 2)
        pmt_tot = round(pmts['payment_value'].sum(), 2)
        diff = round(pmt_tot - exp_tot, 2)
        reconciled = abs(diff) <= 0.10
        if not reconciled:
            unreconciled_cases.append((case_file, oid, exp_tot, pmt_tot, diff))

print(f"Unreconciled cases count: {len(unreconciled_cases)}")
for u in unreconciled_cases:
    print(u)
