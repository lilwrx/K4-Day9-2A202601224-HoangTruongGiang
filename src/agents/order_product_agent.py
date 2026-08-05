from src.data_loader import DataLoader

class OrderProductAgent:
    def investigate(self, order_id: str) -> dict:
        dl = DataLoader()
        items = dl.get_order_items(order_id)
        
        item_ids = []
        seller_ids = []
        product_ids = []
        category_names = []
        
        for it in items:
            # item_ids
            iid = f"{order_id}:{it['order_item_id']}"
            if iid not in item_ids and len(item_ids) < 5:
                item_ids.append(iid)
                
            # seller_ids
            sid = it.get('seller_id')
            if sid and sid not in seller_ids and len(seller_ids) < 3:
                seller_ids.append(sid)
                
            # product_ids
            pid = it.get('product_id')
            if pid and pid not in product_ids and len(product_ids) < 5:
                product_ids.append(pid)
                
            # category_names
            if pid:
                prod_details = dl.get_product(pid)
                if prod_details:
                    cat = prod_details.get('product_category_name')
                    # Keep original Portuguese name as instructed
                    if cat and cat not in category_names and len(category_names) < 5:
                        category_names.append(cat)
                        
        return {
            'order_ids': [order_id] if order_id else [],
            'item_ids': item_ids,
            'seller_ids': seller_ids,
            'product_ids': product_ids,
            'category_names': category_names
        }
