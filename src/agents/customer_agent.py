from src.agents.base_agent import BaseAgent

class CustomerAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-2-9b-it"):
        super().__init__("CustomerAgent", model_name)

    def process(self, order_context: dict, logger=None, case_id: str = "") -> dict:
        customer = order_context["customer"]
        related_orders = order_context["related_order_ids"]
        
        result = {
            "customer_unique_id": customer.get("customer_unique_id") or "",
            "related_order_ids": related_orders[:5],
            "repeat_customer": len(related_orders) >= 1
        }
        
        if logger:
            logger.log_event(case_id, self.name, "customer_analysis_completed", result)
            
        return result
