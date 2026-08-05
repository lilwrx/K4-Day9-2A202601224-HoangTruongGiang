import pandas as pd, glob, json

orders = pd.read_csv('data/olist_orders_dataset.csv')
items = pd.read_csv('data/olist_order_items_dataset.csv')
payments = pd.read_csv('data/olist_order_payments_dataset.csv')

for fpath in sorted(glob.glob('input/EC_*.json')):
    with open(fpath, encoding='utf-8') as f:
        data = json.load(f)
    cid = data['case_id']
    oid = data['customer_request']['claimed_order_id']
    o_row = orders[orders['order_id'] == oid].iloc[0]
    st = o_row['order_status']
    
    if st in ['canceled', 'unavailable']:
        o_items = items[items['order_id'] == oid]
        o_pay = payments[payments['order_id'] == oid]
        pay_tot = o_pay['payment_value'].sum() if not o_pay.empty else 0
        print(f"{cid} ({st}): items_cnt={len(o_items)}, pay_cnt={len(o_pay)}, pay_tot={pay_tot}")
