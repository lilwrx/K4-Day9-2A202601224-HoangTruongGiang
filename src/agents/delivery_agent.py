from datetime import datetime
from src.data_loader import DataLoader

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None

class DeliveryAgent:
    def investigate(self, order_id: str) -> dict:
        dl = DataLoader()
        order = dl.get_order(order_id)
        if not order:
            return {
                'delivered_at': None,
                'estimated_delivery_at': None,
                'carrier_handoff_at': None,
                'delivery_variance_hours': None,
                'seller_handoff_analysis': [],
                'late_handoff_seller_ids': []
            }
            
        delivered_at = order.get('order_delivered_customer_date')
        estimated_delivery_at = order.get('order_estimated_delivery_date')
        carrier_handoff_at = order.get('order_delivered_carrier_date')
        
        dt_delivered = parse_date(delivered_at)
        dt_estimated = parse_date(estimated_delivery_at)
        dt_carrier = parse_date(carrier_handoff_at)
        
        delivery_variance_hours = None
        if dt_delivered and dt_estimated:
            diff = dt_delivered - dt_estimated
            delivery_variance_hours = round(diff.total_seconds() / 3600, 2)
            
        items = dl.get_order_items(order_id)
        seller_limits = {}
        
        for it in items:
            sid = it.get('seller_id')
            limit_str = it.get('shipping_limit_date')
            dt_limit = parse_date(limit_str)
            if sid and dt_limit:
                if sid not in seller_limits or dt_limit < seller_limits[sid]['dt']:
                    seller_limits[sid] = {'dt': dt_limit, 'str': limit_str}
                    
        seller_handoff_analysis = []
        late_handoff_seller_ids = []
        
        # We process in order of appearance of sellers in items to be deterministic
        processed_sids = set()
        
        for it in items:
            sid = it.get('seller_id')
            if sid and sid in seller_limits and sid not in processed_sids:
                processed_sids.add(sid)
                limit_info = seller_limits[sid]
                
                dt_limit = limit_info['dt']
                limit_str = limit_info['str']
                
                handoff_variance_hours = None
                late_handoff = False
                
                if dt_carrier:
                    diff = dt_carrier - dt_limit
                    handoff_variance_hours = round(diff.total_seconds() / 3600, 2)
                    late_handoff = handoff_variance_hours > 0
                    
                seller_handoff_analysis.append({
                    'seller_id': sid,
                    'shipping_limit_at': limit_str,
                    'handoff_variance_hours': handoff_variance_hours,
                    'late_handoff': late_handoff
                })
                
                if late_handoff:
                    late_handoff_seller_ids.append(sid)
                    
        return {
            'delivered_at': delivered_at,
            'estimated_delivery_at': estimated_delivery_at,
            'carrier_handoff_at': carrier_handoff_at,
            'delivery_variance_hours': delivery_variance_hours,
            'seller_handoff_analysis': seller_handoff_analysis,
            'late_handoff_seller_ids': late_handoff_seller_ids
        }
