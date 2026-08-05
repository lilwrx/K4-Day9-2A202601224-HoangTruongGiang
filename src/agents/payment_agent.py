from src.agents.base_agent import BaseAgent

class PaymentAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-2-9b-it"):
        super().__init__("PaymentAgent", model_name)

    def process(self, order_context: dict, order_prod_handoff: dict, logger=None, case_id: str = "") -> dict:
        payments = order_context["payments"]
        order_id = order_context["order"]["order_id"]
        
        payment_types = []
        payment_total = 0.0
        payment_ids = []
        for p in payments:
            p_seq = p["payment_sequential"]
            payment_ids.append(f"{order_id}:{p_seq}")
            p_val = float(p.get("payment_value") or 0.0)
            payment_total += p_val
            p_type = p.get("payment_type")
            if p_type and p_type not in payment_types:
                payment_types.append(p_type)

        payment_total_brl = round(payment_total, 2)
        has_items = order_prod_handoff.get("has_items", True)

        if has_items:
            item_total = order_prod_handoff["item_total_brl"]
            freight_total = order_prod_handoff["freight_total_brl"]
            expected_total_brl = round(item_total + freight_total, 2)
            difference_brl = round(payment_total_brl - expected_total_brl, 2)
            reconciled = abs(difference_brl) <= 0.10
        else:
            item_total = 0.0
            freight_total = 0.0
            expected_total_brl = None
            difference_brl = None
            reconciled = None

        result = {
            "payment_ids": payment_ids[:5],
            "payment_types": payment_types,
            "payment_total_brl": payment_total_brl,
            "item_total_brl": item_total,
            "freight_total_brl": freight_total,
            "expected_total_brl": expected_total_brl,
            "difference_brl": difference_brl,
            "reconciled": reconciled,
            "split_payment": len(payments) >= 2
        }

        if logger:
            logger.log_event(case_id, self.name, "payment_reconciliation_completed", result)

        return result
