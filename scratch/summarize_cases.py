import json
import os
import pandas as pd
from datetime import datetime

project_dir = r"d:\VinAI\K4-Day9-2A202601224-HoangTruongGiang"
data_dir = os.path.join(project_dir, 'data')
input_dir = os.path.join(project_dir, 'input')
output_dir = os.path.join(project_dir, 'output')

orders = pd.read_csv(os.path.join(data_dir, 'olist_orders_dataset.csv'))
order_items = pd.read_csv(os.path.join(data_dir, 'olist_order_items_dataset.csv'))
order_payments = pd.read_csv(os.path.join(data_dir, 'olist_order_payments_dataset.csv'))
customers = pd.read_csv(os.path.join(data_dir, 'olist_customers_dataset.csv'))
products = pd.read_csv(os.path.join(data_dir, 'olist_products_dataset.csv'))
sellers = pd.read_csv(os.path.join(data_dir, 'olist_sellers_dataset.csv'))
trans = pd.read_csv(os.path.join(data_dir, 'product_category_name_translation.csv'))

# Create translation map
cat_map = dict(zip(trans['product_category_name'], trans['product_category_name_english']))

print(f"Total input files: {len(os.listdir(input_dir))}")

# Inspect each of the 50 cases in detail
cases_summary = []
for i in range(1, 51):
    case_file = f"EC_{i:03d}.json"
    with open(os.path.join(input_dir, case_file), 'r', encoding='utf-8') as f:
        inc = json.load(f)
    with open(os.path.join(output_dir, case_file), 'r', encoding='utf-8') as f:
        outc = json.load(f)
        
    oid = inc['customer_request']['claimed_order_id']
    o_row = orders[orders['order_id'] == oid]
    o_status = o_row.iloc[0]['order_status'] if not o_row.empty else 'MISSING'
    
    items = order_items[order_items['order_id'] == oid]
    payments = order_payments[order_payments['order_id'] == oid]
    
    cases_summary.append({
        'case_id': case_file,
        'order_id': oid,
        'order_status': o_status,
        'num_items': len(items),
        'num_payments': len(payments),
        'primary_issue': outc['case_assessment']['primary_issue'],
        'secondary_issues': outc['case_assessment']['secondary_issues'],
        'refund': outc['financial_resolution']['recommended_refund_brl'],
        'actions': outc['resolution_actions']
    })

df_sum = pd.DataFrame(cases_summary)
print(df_sum.to_string())
