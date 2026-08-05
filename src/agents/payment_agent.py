from src.data_loader import DataLoader

class PaymentAgent:
    def investigate(self, order_id: str, order_items: list = None) -> dict:
        dl = DataLoader()
        
        if order_items is None:
            items = dl.get_order_items(order_id)
        else:
            items = order_items
            
        payments = dl.get_order_payments(order_id)
        
        has_items = len(items) > 0
        has_payments = len(payments) > 0
        
        payment_total_brl = 0.0
        payment_types_seen = set()
        payment_types = []
        payment_ids = []
        
        for p in payments:
            val = p.get('payment_value')
            if val is not None:
                payment_total_brl += float(val)
                
            pt = p.get('payment_type')
            if pt and pt not in payment_types_seen:
                payment_types_seen.add(pt)
                payment_types.append(pt)
                
            seq = p.get('payment_sequential')
            if seq:
                pid = f"{order_id}:{seq}"
                if pid not in payment_ids and len(payment_ids) < 5:
                    payment_ids.append(pid)
                    
        payment_total_brl = round(payment_total_brl, 2)
        
        if has_items:
            item_total_brl = sum(float(it.get('price', 0)) for it in items)
            freight_total_brl = sum(float(it.get('freight_value', 0)) for it in items)
            expected_total_brl = item_total_brl + freight_total_brl
            
            item_total_brl = round(item_total_brl, 2)
            freight_total_brl = round(freight_total_brl, 2)
            expected_total_brl = round(expected_total_brl, 2)
            
            difference_brl = round(payment_total_brl - expected_total_brl, 2)
            reconciled = abs(difference_brl) <= 0.10
        else:
            item_total_brl = None
            freight_total_brl = None
            expected_total_brl = None
            difference_brl = None
            reconciled = None
            
        return {
            'payment_reconciliation': {
                'currency': 'BRL',
                'item_total_brl': item_total_brl,
                'freight_total_brl': freight_total_brl,
                'expected_total_brl': expected_total_brl,
                'payment_total_brl': payment_total_brl,
                'difference_brl': difference_brl,
                'reconciled': reconciled,
                'payment_types': payment_types
            },
            'payment_ids': payment_ids
        }
