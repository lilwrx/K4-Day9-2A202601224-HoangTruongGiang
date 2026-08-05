import csv
import sqlite3
import os
import time

class OlistDB:
    def __init__(self, data_dir: str = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\data"):
        self.data_dir = data_dir
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._load_csvs()
        self._create_indexes()

    def _load_csvs(self):
        files = [
            "olist_customers_dataset.csv",
            "olist_geolocation_dataset.csv",
            "olist_order_items_dataset.csv",
            "olist_order_payments_dataset.csv",
            "olist_order_reviews_dataset.csv",
            "olist_orders_dataset.csv",
            "olist_products_dataset.csv",
            "olist_sellers_dataset.csv",
            "product_category_name_translation.csv"
        ]

        for f in files:
            table_name = f.replace(".csv", "").replace("olist_", "").replace("_dataset", "")
            file_path = os.path.join(self.data_dir, f)
            if not os.path.exists(file_path):
                continue
            with open(file_path, "r", encoding="utf-8-sig") as file:
                dr = csv.DictReader(file)
                headers = dr.fieldnames
                self.cursor.execute(f"CREATE TABLE `{table_name}` ({', '.join([f'`{h}` TEXT' for h in headers])});")
                to_db = [[row[h] for h in headers] for row in dr]
                self.cursor.executemany(f"INSERT INTO `{table_name}` VALUES ({', '.join(['?']*len(headers))});", to_db)

        self.conn.commit()

    def _create_indexes(self):
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_customer_id ON customers(customer_id);")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_unique_id ON customers(customer_unique_id);")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_order_id ON order_items(order_id);")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_order_id ON order_payments(order_id);")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_product_id ON products(product_id);")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_sellers_seller_id ON sellers(seller_id);")
        self.conn.commit()

    def get_order_context(self, order_id: str) -> dict:
        # Order info
        self.cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order_row = self.cursor.fetchone()
        if not order_row:
            return None
        
        order_dict = dict(order_row)
        customer_id = order_dict.get("customer_id")

        # Customer info & related orders
        customer_dict = {}
        related_order_ids = []
        if customer_id:
            self.cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
            c_row = self.cursor.fetchone()
            if c_row:
                customer_dict = dict(c_row)
                c_unique_id = customer_dict.get("customer_unique_id")
                if c_unique_id:
                    self.cursor.execute("""
                        SELECT o.order_id 
                        FROM orders o 
                        JOIN customers c ON o.customer_id = c.customer_id 
                        WHERE c.customer_unique_id = ? AND o.order_id != ?
                        ORDER BY o.order_purchase_timestamp ASC
                    """, (c_unique_id, order_id))
                    related_order_ids = [r["order_id"] for r in self.cursor.fetchall()]

        # Items & Products
        self.cursor.execute("""
            SELECT i.*, p.product_category_name, t.product_category_name_english
            FROM order_items i
            LEFT JOIN products p ON i.product_id = p.product_id
            LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
            WHERE i.order_id = ?
            ORDER BY CAST(i.order_item_id AS INTEGER) ASC
        """, (order_id,))
        items = [dict(r) for r in self.cursor.fetchall()]

        # Payments
        self.cursor.execute("""
            SELECT * FROM order_payments 
            WHERE order_id = ? 
            ORDER BY CAST(payment_sequential AS INTEGER) ASC
        """, (order_id,))
        payments = [dict(r) for r in self.cursor.fetchall()]

        return {
            "order": order_dict,
            "customer": customer_dict,
            "related_order_ids": related_order_ids,
            "items": items,
            "payments": payments
        }
