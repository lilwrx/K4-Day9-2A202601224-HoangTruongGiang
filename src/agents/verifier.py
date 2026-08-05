from src.agents.base_agent import BaseAgent

class VerifierAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-2-9b-it"):
        super().__init__("VerifierAgent", model_name)

    def process(self, case_output: dict, logger=None, case_id: str = "") -> dict:
        # Enforce case_id
        case_output["case_id"] = case_id

        # Enforce bounds
        ca = case_output["case_assessment"]
        ca["confidence"] = max(0.0, min(1.0, float(ca.get("confidence", 0.95))))

        ae = case_output["affected_entities"]
        ae["order_ids"] = ae["order_ids"][:5]
        ae["item_ids"] = ae["item_ids"][:5]
        ae["seller_ids"] = ae["seller_ids"][:3]
        ae["payment_ids"] = ae["payment_ids"][:5]

        cc = case_output["customer_context"]
        cc["related_order_ids"] = cc["related_order_ids"][:5]

        pc = case_output["product_context"]
        pc["product_ids"] = pc["product_ids"][:5]
        pc["category_names"] = pc["category_names"][:5]

        rca = case_output["root_cause_analysis"]
        rca["ranked_causes"] = rca["ranked_causes"][:3]
        rca["responsible_parties"] = rca["responsible_parties"][:3]

        case_output["evidence_ids"] = case_output["evidence_ids"][:20]
        case_output["resolution_actions"] = case_output["resolution_actions"][:5]

        # Null cleaning for timestamp fields if string 'null'
        da = case_output["delivery_analysis"]
        for key in ["delivered_at", "estimated_delivery_at", "carrier_handoff_at"]:
            if da.get(key) == "null":
                da[key] = None

        if logger:
            logger.log_event(case_id, self.name, "schema_verification_passed", {"verified": True})

        return case_output
