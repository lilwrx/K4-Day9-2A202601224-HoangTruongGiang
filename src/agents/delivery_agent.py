from datetime import datetime
from src.agents.base_agent import BaseAgent

def parse_dt(dt_str):
    if not dt_str or dt_str.lower() == 'null':
        return None
    try:
        return datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(dt_str.strip(), "%Y-%m-%d")
        except ValueError:
            return None

def hours_diff(dt1, dt2):
    if not dt1 or not dt2:
        return None
    seconds = (dt1 - dt2).total_seconds()
    return round(seconds / 3600.0, 2)

class DeliveryAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-2-9b-it"):
        super().__init__("DeliveryAgent", model_name)

    def process(self, order_context: dict, order_prod_handoff: dict, logger=None, case_id: str = "") -> dict:
        order = order_context["order"]
        delivered_customer_dt = parse_dt(order.get("order_delivered_customer_date"))
        estimated_delivery_dt = parse_dt(order.get("order_estimated_delivery_date"))
        carrier_handoff_dt = parse_dt(order.get("order_delivered_carrier_date"))

        delivery_variance_hours = hours_diff(delivered_customer_dt, estimated_delivery_dt)
        is_late_delivery = bool(delivered_customer_dt and estimated_delivery_dt and delivered_customer_dt > estimated_delivery_dt)

        seller_shipping_limits = order_prod_handoff.get("seller_shipping_limits", {})
        has_items = order_prod_handoff.get("has_items", True)

        seller_handoff_analysis = []
        late_handoff_seller_ids = []

        if has_items:
            for s_id, s_limit_str in seller_shipping_limits.items():
                s_limit_dt = parse_dt(s_limit_str)
                h_variance = hours_diff(carrier_handoff_dt, s_limit_dt) if carrier_handoff_dt and s_limit_dt else None
                is_late = bool(carrier_handoff_dt > s_limit_dt) if (carrier_handoff_dt and s_limit_dt) else False
                if is_late:
                    late_handoff_seller_ids.append(s_id)
                seller_handoff_analysis.append({
                    "seller_id": s_id,
                    "shipping_limit_at": s_limit_dt.strftime("%Y-%m-%d %H:%M:%S") if s_limit_dt else None,
                    "handoff_variance_hours": h_variance,
                    "late_handoff": is_late
                })

        result = {
            "delivered_at": order.get("order_delivered_customer_date") if order.get("order_delivered_customer_date") != "null" else None,
            "estimated_delivery_at": order.get("order_estimated_delivery_date") if order.get("order_estimated_delivery_date") != "null" else None,
            "carrier_handoff_at": order.get("order_delivered_carrier_date") if order.get("order_delivered_carrier_date") != "null" else None,
            "delivery_variance_hours": delivery_variance_hours,
            "is_late_delivery": is_late_delivery,
            "seller_handoff_analysis": seller_handoff_analysis,
            "late_handoff_seller_ids": late_handoff_seller_ids
        }

        if logger:
            logger.log_event(case_id, self.name, "delivery_analysis_completed", result)

        return result
