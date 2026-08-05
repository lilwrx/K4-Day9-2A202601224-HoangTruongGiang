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
sellers = pd.read_csv(os.path.join(data_dir, 'olist_sellers_dataset.csv'))
trans = pd.read_csv(os.path.join(data_dir, 'product_category_name_translation.csv'))

print("Data loaded successfully.")
