import json
import os
import pandas as pd

project_dir = r"d:\VinAI\K4-Day9-2A202601224-HoangTruongGiang"
data_dir = os.path.join(project_dir, 'data')
input_dir = os.path.join(project_dir, 'input')

orders = pd.read_csv(os.path.join(data_dir, 'olist_orders_dataset.csv'))
customers = pd.read_csv(os.path.join(data_dir, 'olist_customers_dataset.csv'))

for i in range(1, 51):
    case_file = f"EC_{i:03d}.json"
    with open(os.path.join(input_dir, case_file), 'r', encoding='utf-8') as f:
        inc = json.load(f)
    oid = inc['customer_request']['claimed_order_id']
    o = orders[orders['order_id'] == oid].iloc[0]
    cid = o['customer_id']
    c = customers[customers['customer_id'] == cid].iloc[0]
    uid = c['customer_unique_id']
    
    all_cids = customers[customers['customer_unique_id'] == uid]['customer_id'].tolist()
    rel_orders = orders[orders['customer_id'].isin(all_cids)]
    
    raw_list = [x for x in rel_orders['order_id'].tolist() if x != oid]
    sorted_list = [x for x in rel_orders.sort_values('order_purchase_timestamp')['order_id'].tolist() if x != oid]
    
    if raw_list != sorted_list:
        print(f"{case_file}: raw={raw_list} vs sorted={sorted_list}")
