from src.agents.base_agent import BaseAgent

class OrderProductAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-2-9b-it"):
        super().__init__("OrderProductAgent", model_name)

    def process(self, order_context: dict, logger=None, case_id: str = "") -> dict:
        items = order_context["items"]
        order_id = order_context["order"]["order_id"]
        
        item_ids = []
        seller_ids = []
        product_ids = []
        category_names = []
        item_total = 0.0
        freight_total = 0.0
        seller_shipping_limits = {}

        for it in items:
            item_seq = it["order_item_id"]
            item_ids.append(f"{order_id}:{item_seq}")
            
            p_id = it.get("product_id")
            if p_id and p_id not in product_ids:
                product_ids.append(p_id)
                
            cat = it.get("product_category_name")
            if cat and cat != "null" and cat not in category_names:
                category_names.append(cat)

            s_id = it.get("seller_id")
            if s_id and s_id not in seller_ids:
                seller_ids.append(s_id)

            price = float(it.get("price") or 0.0)
            freight = float(it.get("freight_value") or 0.0)
            item_total += price
            freight_total += freight

            # shipping limit
            s_limit_str = it.get("shipping_limit_date")
            if s_id and s_limit_str and s_limit_str != "null":
                if s_id not in seller_shipping_limits or s_limit_str < seller_shipping_limits[s_id]:
                    seller_shipping_limits[s_id] = s_limit_str

        result = {
            "item_ids": item_ids[:5],
            "seller_ids": seller_ids[:3],
            "product_ids": product_ids[:5],
            "category_names": category_names[:5],
            "item_total_brl": round(item_total, 2),
            "freight_total_brl": round(freight_total, 2),
            "seller_shipping_limits": seller_shipping_limits,
            "has_items": len(items) > 0,
            "multi_item_order": len(items) >= 2,
            "multi_seller_order": len(seller_ids) >= 2,
            "multiple_categories": len(category_names) >= 2
        }

        if logger:
            logger.log_event(case_id, self.name, "order_product_analysis_completed", result)

        return result
