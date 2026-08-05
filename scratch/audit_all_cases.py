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

def parse_dt(s):
    if pd.isna(s) or not s:
        return None
    return datetime.strptime(str(s), '%Y-%m-%d %H:%M:%S')

# Audit each case
audit_results = []
for i in range(1, 51):
    case_file = f"EC_{i:03d}.json"
    with open(os.path.join(input_dir, case_file), 'r', encoding='utf-8') as f:
        inc = json.load(f)
    with open(os.path.join(output_dir, case_file), 'r') as f:
        outc = json.load(f)
        
    oid = inc['customer_request']['claimed_order_id']
    o_row = orders[orders['order_id'] == oid].iloc[0]
    items = order_items[order_items['order_id'] == oid]
    pmts = order_payments[order_payments['order_id'] == oid]
    cust = customers[customers['customer_id'] == o_row['customer_id']].iloc[0]
    
    # Calculate delivery variance
    dt_del = parse_dt(o_row['order_delivered_customer_date'])
    dt_est = parse_dt(o_row['order_estimated_delivery_date'])
    dt_car = parse_dt(o_row['order_delivered_carrier_date'])
    
    del_var = round((dt_del - dt_est).total_seconds() / 3600, 2) if dt_del and dt_est else None
    
    # Check seller handoffs
    late_sellers = []
    seller_details = []
    for sid in items['seller_id'].unique():
        s_items = items[items['seller_id'] == sid]
        earliest_limit = min([parse_dt(x) for x in s_items['shipping_limit_date']])
        limit_str = s_items.sort_values('shipping_limit_date').iloc[0]['shipping_limit_date']
        
        h_var = round((dt_car - earliest_limit).total_seconds() / 3600, 2) if dt_car and earliest_limit else None
        is_late = h_var > 0 if h_var is not None else False
        if is_late:
            late_sellers.append(sid)
        seller_details.append((sid, limit_str, h_var, is_late))
        
    # Totals
    if len(items) > 0:
        item_tot = round(items['price'].sum(), 2)
        freight_tot = round(items['freight_value'].sum(), 2)
        exp_tot = round(item_tot + freight_tot, 2)
    else:
        item_tot, freight_tot, exp_tot = None, None, None
        
    pmt_tot = round(pmts['payment_value'].sum(), 2) if len(pmts) > 0 else 0.0
    diff = round(pmt_tot - exp_tot, 2) if exp_tot is not None else None
    reconciled = abs(diff) <= 0.10 if diff is not None else None
    
    # Related orders
    rel_orders = orders[orders['customer_id'].isin(customers[customers['customer_unique_id'] == cust['customer_unique_id']]['customer_id'])]
    rel_oids = [x for x in rel_orders['order_id'].tolist() if x != oid]
    
    audit_results.append({
        'case_id': case_file,
        'order_status': o_row['order_status'],
        'del_var': del_var,
        'late_sellers': late_sellers,
        'num_pmts': len(pmts),
        'reconciled': reconciled,
        'num_items': len(items),
        'num_sellers': len(items['seller_id'].unique()),
        'num_rel_orders': len(rel_oids),
        'actual_primary': outc['case_assessment']['primary_issue'],
        'actual_actions': outc['resolution_actions']
    })

print("Audit completed for 50 cases.")
df_audit = pd.DataFrame(audit_results)
print(df_audit.head(10).to_string())
