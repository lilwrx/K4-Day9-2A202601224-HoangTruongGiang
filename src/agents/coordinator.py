from src.agents.base_agent import BaseAgent
from src.agents.customer_agent import CustomerAgent
from src.agents.order_product_agent import OrderProductAgent
from src.agents.payment_agent import PaymentAgent
from src.agents.delivery_agent import DeliveryAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.verifier import VerifierAgent

class CoordinatorAgent(BaseAgent):
    def __init__(self, db, model_name: str = "gemma-2-9b-it"):
        super().__init__("CoordinatorAgent", model_name)
        self.db = db
        # Instantiating 6 explicit sub-agents
        self.customer_agent = CustomerAgent(model_name)
        self.order_product_agent = OrderProductAgent(model_name)
        self.payment_agent = PaymentAgent(model_name)
        self.delivery_agent = DeliveryAgent(model_name)
        self.policy_agent = PolicyAgent(model_name)
        self.verifier_agent = VerifierAgent(model_name)

    def process_case(self, input_case: dict, logger=None) -> dict:
        case_id = input_case["case_id"]
        customer_req = input_case["customer_request"]
        claimed_order_id = customer_req["claimed_order_id"]

        if logger:
            logger.log_event(case_id, self.name, "coordinator_case_received", {"claimed_order_id": claimed_order_id})

        # Fetch data context from SQLite
        order_context = self.db.get_order_context(claimed_order_id)
        if not order_context:
            raise ValueError(f"Order ID {claimed_order_id} not found in database!")

        # 1. Customer Agent
        cust_handoff = self.customer_agent.process(order_context, logger, case_id)

        # 2. Order & Product Agent
        order_prod_handoff = self.order_product_agent.process(order_context, logger, case_id)

        # 3. Payment Agent
        pay_handoff = self.payment_agent.process(order_context, order_prod_handoff, logger, case_id)

        # 4. Delivery Agent
        del_handoff = self.delivery_agent.process(order_context, order_prod_handoff, logger, case_id)

        # 5. Policy Agent (EC_POLICY_V2 evaluation)
        policy_handoff = self.policy_agent.process(order_context, cust_handoff, order_prod_handoff, pay_handoff, del_handoff, logger, case_id)

        # Assemble full candidate output
        candidate_output = {
            "case_id": case_id,
            "case_assessment": policy_handoff["case_assessment"],
            "affected_entities": {
                "order_ids": [claimed_order_id],
                "item_ids": order_prod_handoff["item_ids"],
                "seller_ids": order_prod_handoff["seller_ids"],
                "payment_ids": pay_handoff["payment_ids"]
            },
            "customer_context": {
                "customer_unique_id": cust_handoff["customer_unique_id"],
                "related_order_ids": cust_handoff["related_order_ids"]
            },
            "product_context": {
                "product_ids": order_prod_handoff["product_ids"],
                "category_names": order_prod_handoff["category_names"]
            },
            "delivery_analysis": {
                "delivered_at": del_handoff["delivered_at"],
                "estimated_delivery_at": del_handoff["estimated_delivery_at"],
                "carrier_handoff_at": del_handoff["carrier_handoff_at"],
                "delivery_variance_hours": del_handoff["delivery_variance_hours"],
                "seller_handoff_analysis": del_handoff["seller_handoff_analysis"],
                "late_handoff_seller_ids": del_handoff["late_handoff_seller_ids"]
            },
            "payment_reconciliation": {
                "currency": "BRL",
                "item_total_brl": pay_handoff["item_total_brl"],
                "freight_total_brl": pay_handoff["freight_total_brl"],
                "expected_total_brl": pay_handoff["expected_total_brl"],
                "payment_total_brl": pay_handoff["payment_total_brl"],
                "difference_brl": pay_handoff["difference_brl"],
                "reconciled": pay_handoff["reconciled"],
                "payment_types": pay_handoff["payment_types"]
            },
            "root_cause_analysis": policy_handoff["root_cause_analysis"],
            "evidence_ids": policy_handoff["evidence_ids"],
            "financial_resolution": policy_handoff["financial_resolution"],
            "resolution_actions": policy_handoff["resolution_actions"]
        }

        # 6. Verifier Agent
        verified_output = self.verifier_agent.process(candidate_output, logger, case_id)

        if logger:
            logger.log_event(case_id, self.name, "coordinator_case_completed", {
                "primary_issue": verified_output["case_assessment"]["primary_issue"],
                "refund": verified_output["financial_resolution"]["recommended_refund_brl"]
            })

        return verified_output
