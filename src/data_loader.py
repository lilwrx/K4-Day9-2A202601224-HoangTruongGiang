import os
import pandas as pd
import numpy as np

class DataLoader:
    _instance = None
    _loaded = False

    def __new__(cls, data_dir='data/'):
        if cls._instance is None:
            cls._instance = super(DataLoader, cls).__new__(cls)
        return cls._instance

    def __init__(self, data_dir='data/'):
        if not self._loaded:
            self.data_dir = data_dir
            self._load_data()
            self._loaded = True

    def _load_data(self):
        self.orders = pd.read_csv(os.path.join(self.data_dir, 'olist_orders_dataset.csv'))
        self.order_items = pd.read_csv(os.path.join(self.data_dir, 'olist_order_items_dataset.csv'))
        self.order_payments = pd.read_csv(os.path.join(self.data_dir, 'olist_order_payments_dataset.csv'))
        self.customers = pd.read_csv(os.path.join(self.data_dir, 'olist_customers_dataset.csv'))
        self.products = pd.read_csv(os.path.join(self.data_dir, 'olist_products_dataset.csv'))
        self.sellers = pd.read_csv(os.path.join(self.data_dir, 'olist_sellers_dataset.csv'))
        self.category_translations = pd.read_csv(os.path.join(self.data_dir, 'product_category_name_translation.csv'))

    def _clean_dict(self, d):
        if d is None:
            return None
        return {k: (None if pd.isna(v) else v) for k, v in d.items()}

    def get_order(self, order_id):
        res = self.orders[self.orders['order_id'] == order_id]
        if res.empty:
            return None
        return self._clean_dict(res.iloc[0].to_dict())

    def get_order_items(self, order_id):
        res = self.order_items[self.order_items['order_id'] == order_id]
        return [self._clean_dict(row.to_dict()) for _, row in res.iterrows()]

    def get_order_payments(self, order_id):
        res = self.order_payments[self.order_payments['order_id'] == order_id]
        return [self._clean_dict(row.to_dict()) for _, row in res.iterrows()]

    def get_customer(self, customer_id):
        res = self.customers[self.customers['customer_id'] == customer_id]
        if res.empty:
            return None
        return self._clean_dict(res.iloc[0].to_dict())

    def get_customer_orders(self, customer_unique_id):
        res_customers = self.customers[self.customers['customer_unique_id'] == customer_unique_id]
        customer_ids = res_customers['customer_id'].tolist()
        res_orders = self.orders[self.orders['customer_id'].isin(customer_ids)]
        return res_orders['order_id'].tolist()
        
    def get_product(self, product_id):
        res = self.products[self.products['product_id'] == product_id]
        if res.empty:
            return None
        return self._clean_dict(res.iloc[0].to_dict())

    def get_seller(self, seller_id):
        res = self.sellers[self.sellers['seller_id'] == seller_id]
        if res.empty:
            return None
        return self._clean_dict(res.iloc[0].to_dict())

    def get_category_translation(self, category_name):
        res = self.category_translations[self.category_translations['product_category_name'] == category_name]
        if res.empty:
            return category_name
        return res.iloc[0]['product_category_name_english']
