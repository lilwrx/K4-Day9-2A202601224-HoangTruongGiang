from src.agents.base_agent import BaseAgent

class PolicyAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-2-9b-it"):
        super().__init__("PolicyAgent", model_name)

    def process(self, order_context: dict, cust_handoff: dict, order_prod_handoff: dict, pay_handoff: dict, del_handoff: dict, logger=None, case_id: str = "") -> dict:
        order = order_context["order"]
        order_id = order["order_id"]
        order_status = order.get("order_status")

        payment_total_brl = pay_handoff["payment_total_brl"]
        freight_total_brl = pay_handoff["freight_total_brl"]
        reconciled = pay_handoff["reconciled"]
        payment_ids = pay_handoff["payment_ids"]

        is_late_delivery = del_handoff["is_late_delivery"]
        late_handoff_seller_ids = del_handoff["late_handoff_seller_ids"]

        # Evaluate Primary Issue
        primary_issue = None
        responsible_parties = []
        recommended_refund_brl = 0.0
        primary_action = None
        root_cause_code = None
        case_status = "no_action"

        if order_status == "canceled" and payment_total_brl > 0:
            primary_issue = "canceled_order_paid"
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            recommended_refund_brl = payment_total_brl
            primary_action = "issue_full_refund"
            root_cause_code = "ORDER_CANCELED_AFTER_PAYMENT"
            case_status = "action_required"
        elif order_status == "unavailable" and payment_total_brl > 0:
            primary_issue = "unavailable_order_paid"
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            recommended_refund_brl = payment_total_brl
            primary_action = "issue_full_refund"
            root_cause_code = "ORDER_UNAVAILABLE_AFTER_PAYMENT"
            case_status = "action_required"
        elif is_late_delivery and len(late_handoff_seller_ids) > 0:
            primary_issue = "late_delivery_seller"
            for s_id in late_handoff_seller_ids[:3]:
                responsible_parties.append({"party_type": "seller", "party_id": s_id})
            recommended_refund_brl = freight_total_brl
            primary_action = "refund_freight"
            root_cause_code = "SELLER_HANDOFF_AFTER_LIMIT"
            case_status = "action_required"
        elif is_late_delivery and len(late_handoff_seller_ids) == 0:
            primary_issue = "late_delivery_logistics"
            responsible_parties = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
            recommended_refund_brl = freight_total_brl
            primary_action = "refund_freight"
            root_cause_code = "CARRIER_DELIVERED_AFTER_ESTIMATE"
            case_status = "action_required"
        elif pay_handoff["split_payment"] and reconciled:
            primary_issue = "valid_split_payment"
            responsible_parties = []
            recommended_refund_brl = 0.0
            primary_action = "explain_valid_split_payment"
            root_cause_code = "MULTIPLE_PAYMENTS_RECONCILED"
            case_status = "no_action"
        else:
            primary_issue = "unsupported_late_claim"
            responsible_parties = []
            recommended_refund_brl = 0.0
            primary_action = "reject_late_refund"
            root_cause_code = "DELIVERY_WITHIN_ESTIMATE"
            case_status = "no_action"

        # Evaluate Secondary Issues (strict order)
        secondary_issues = []
        if order_prod_handoff["multi_item_order"]:
            secondary_issues.append("multi_item_order")
        if order_prod_handoff["multi_seller_order"]:
            secondary_issues.append("multi_seller_order")
        if pay_handoff["split_payment"]:
            secondary_issues.append("split_payment")
        if cust_handoff["repeat_customer"]:
            secondary_issues.append("repeat_customer")
        if order_prod_handoff["multiple_categories"]:
            secondary_issues.append("multiple_categories")

        # Resolution Actions (strict order)
        resolution_actions = [primary_action]
        if primary_issue == "late_delivery_seller":
            resolution_actions.append("review_seller_handoff")
        elif primary_issue == "late_delivery_logistics":
            resolution_actions.append("review_carrier_delay")

        if case_status == "action_required" or recommended_refund_brl > 0:
            resolution_actions.append("verify_refund_completion")

        if "multi_seller_order" in secondary_issues:
            resolution_actions.append("coordinate_multi_seller_case")

        if "split_payment" in secondary_issues and primary_issue != "valid_split_payment":
            resolution_actions.append("verify_payment_allocation")

        resolution_actions = resolution_actions[:5]

        # Evidence IDs
        evidence_ids = [f"order:{order_id}"]
        for i_id in order_prod_handoff["item_ids"][:5]:
            evidence_ids.append(f"item:{i_id}")
        for p_id in payment_ids[:5]:
            evidence_ids.append(f"payment:{p_id}")
        for party in responsible_parties:
            if party["party_type"] == "seller":
                evidence_ids.append(f"seller:{party['party_id']}")
        evidence_ids.append(f"policy:{root_cause_code}")
        evidence_ids = evidence_ids[:20]

        result = {
            "case_assessment": {
                "primary_issue": primary_issue,
                "secondary_issues": secondary_issues,
                "case_status": case_status,
                "confidence": 0.95
            },
            "root_cause_analysis": {
                "ranked_causes": [
                    {"cause_code": root_cause_code, "rank": 1}
                ],
                "responsible_parties": responsible_parties
            },
            "evidence_ids": evidence_ids,
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": recommended_refund_brl
            },
            "resolution_actions": resolution_actions
        }

        if logger:
            logger.log_event(case_id, self.name, "policy_evaluation_completed", result)

        return result
