from src.agents.base_agent import BaseAgent

class CustomerAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-2-9b-it"):
        super().__init__("CustomerAgent", model_name)

    def process(self, order_context: dict, logger=None, case_id: str = "") -> dict:
        customer = order_context["customer"]
        related_orders = order_context["related_order_ids"]
        res = {
            "customer_unique_id": customer.get("customer_unique_id") or "",
            "related_order_ids": related_orders[:5]
        }
        if logger:
            logger.log_event(case_id, self.name, "customer_context_extracted", res)
        return res

class OrderProductAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-2-9b-it"):
        super().__init__("OrderProductAgent", model_name)

    def process(self, order_context: dict, logger=None, case_id: str = "") -> dict:
        items = order_context["items"]
        product_ids = []
        category_names = []
        for it in items:
            p_id = it.get("product_id")
            if p_id and p_id not in product_ids:
                product_ids.append(p_id)
            cat = it.get("product_category_name")
            if cat and cat != "null" and cat not in category_names:
                category_names.append(cat)

        res = {
            "product_ids": product_ids[:5],
            "category_names": category_names[:5]
        }
        if logger:
            logger.log_event(case_id, self.name, "product_context_extracted", res)
        return res

class PaymentAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-2-9b-it"):
        super().__init__("PaymentAgent", model_name)

    def process(self, order_context: dict, logger=None, case_id: str = "") -> dict:
        payments = order_context["payments"]
        order_id = order_context["order"]["order_id"]
        payment_ids = [f"{order_id}:{p['payment_sequential']}" for p in payments]
        res = {
            "payment_ids": payment_ids[:5],
            "count": len(payments)
        }
        if logger:
            logger.log_event(case_id, self.name, "payment_analysis_completed", res)
        return res

class DeliveryAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-2-9b-it"):
        super().__init__("DeliveryAgent", model_name)

    def process(self, order_context: dict, logger=None, case_id: str = "") -> dict:
        order = order_context["order"]
        res = {
            "delivered_at": order.get("order_delivered_customer_date"),
            "estimated_delivery_at": order.get("order_estimated_delivery_date"),
            "carrier_handoff_at": order.get("order_delivered_carrier_date")
        }
        if logger:
            logger.log_event(case_id, self.name, "delivery_analysis_completed", res)
        return res
