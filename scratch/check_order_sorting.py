import json
import os
import pandas as pd

project_dir = r"d:\VinAI\K4-Day9-2A202601224-HoangTruongGiang"
data_dir = os.path.join(project_dir, 'data')

orders = pd.read_csv(os.path.join(data_dir, 'olist_orders_dataset.csv'))
customers = pd.read_csv(os.path.join(data_dir, 'olist_customers_dataset.csv'))

# Check for customers with multiple orders, check order of appearance vs timestamp order
diff_count = 0
for uid in customers['customer_unique_id'].unique():
    c_ids = customers[customers['customer_unique_id'] == uid]['customer_id'].tolist()
    cust_orders = orders[orders['customer_id'].isin(c_ids)]
    if len(cust_orders) > 1:
        raw_order = cust_orders['order_id'].tolist()
        sorted_order = cust_orders.sort_values('order_purchase_timestamp')['order_id'].tolist()
        if raw_order != sorted_order:
            diff_count += 1
            print(f"UID {uid}: raw={raw_order} vs sorted={sorted_order}")

print(f"Total customers with different raw vs sorted order order: {diff_count}")
