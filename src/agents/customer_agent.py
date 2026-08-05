from src.data_loader import DataLoader

class CustomerAgent:
    def investigate(self, order_id: str) -> dict:
        dl = DataLoader()
        order = dl.get_order(order_id)
        if not order:
            return {'customer_unique_id': None, 'related_order_ids': []}
            
        customer_id = order.get('customer_id')
        customer = dl.get_customer(customer_id)
        if not customer:
            return {'customer_unique_id': None, 'related_order_ids': []}
            
        customer_unique_id = customer.get('customer_unique_id')
        related_order_ids = []
        if customer_unique_id:
            all_orders = dl.get_customer_orders(customer_unique_id)
            for cid in all_orders:
                if cid != order_id:
                    if cid not in related_order_ids:
                        related_order_ids.append(cid)
                    if len(related_order_ids) >= 5:
                        break
                        
        return {
            'customer_unique_id': customer_unique_id,
            'related_order_ids': related_order_ids
        }
