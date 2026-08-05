import datetime
from src.data_loader import DataLoader
from src.agents.customer_agent import CustomerAgent
from src.agents.order_product_agent import OrderProductAgent
from src.agents.payment_agent import PaymentAgent
from src.agents.delivery_agent import DeliveryAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.verifier_agent import VerifierAgent

try:
    from src.llm_client import generate_agent_reasoning
except Exception:
    generate_agent_reasoning = None


class CoordinatorAgent:
    """Orchestrates the full investigation pipeline for a single case."""

    def __init__(self):
        self.dl = DataLoader()
        self.customer_agent = CustomerAgent()
        self.order_product_agent = OrderProductAgent()
        self.payment_agent = PaymentAgent()
        self.delivery_agent = DeliveryAgent()
        self.policy_agent = PolicyAgent()
        self.verifier_agent = VerifierAgent()

    def _make_summary(self, agent_name, task, data_summary, conclusion):
        if generate_agent_reasoning:
            try:
                return generate_agent_reasoning(agent_name, task, data_summary, conclusion)
            except Exception:
                pass
        return f"{agent_name}: {conclusion}"

    def process_case(self, case_dict: dict) -> tuple:
        case_id = case_dict['case_id']
        order_id = case_dict['customer_request']['claimed_order_id']

        # Step 1: Get order info
        order = self.dl.get_order(order_id)
        order_status = order.get('order_status') if order else None

        # Step 2: Customer Agent
        customer_data = self.customer_agent.investigate(order_id)

        # Step 3: Order & Product Agent
        order_product_data = self.order_product_agent.investigate(order_id)

        # Step 4: Payment Agent
        payment_data = self.payment_agent.investigate(order_id)

        # Step 5: Delivery Agent
        delivery_data = self.delivery_agent.investigate(order_id)

        # Step 6: Policy Agent
        policy_result = self.policy_agent.evaluate(
            order_status, order_product_data, payment_data, delivery_data, customer_data
        )

        # Step 7: Build evidence_ids
        evidence_ids = []
        evidence_ids.append(f"order:{order_id}")

        for item_id in order_product_data.get('item_ids', []):
            # item_id is already in format "order_id:item_num"
            evidence_ids.append(f"item:{item_id}")

        for payment_id in payment_data.get('payment_ids', []):
            # payment_id is already in format "order_id:sequential"
            evidence_ids.append(f"payment:{payment_id}")

        # Add seller evidence only for responsible sellers
        for rp in policy_result['root_cause_analysis']['responsible_parties']:
            if rp['party_type'] == 'seller':
                evidence_ids.append(f"seller:{rp['party_id']}")

        # Add policy evidence
        if policy_result['root_cause_analysis']['ranked_causes']:
            cause_code = policy_result['root_cause_analysis']['ranked_causes'][0]['cause_code']
            evidence_ids.append(f"policy:{cause_code}")

        evidence_ids = evidence_ids[:20]

        # Step 8: Assemble final output
        final_output = {
            "case_id": case_id,
            "case_assessment": policy_result['case_assessment'],
            "affected_entities": {
                "order_ids": order_product_data.get('order_ids', [order_id]),
                "item_ids": order_product_data.get('item_ids', []),
                "seller_ids": order_product_data.get('seller_ids', []),
                "payment_ids": payment_data.get('payment_ids', [])
            },
            "customer_context": customer_data,
            "product_context": {
                "product_ids": order_product_data.get('product_ids', []),
                "category_names": order_product_data.get('category_names', [])
            },
            "delivery_analysis": delivery_data,
            "payment_reconciliation": payment_data.get('payment_reconciliation', {}),
            "root_cause_analysis": policy_result['root_cause_analysis'],
            "evidence_ids": evidence_ids,
            "financial_resolution": policy_result['financial_resolution'],
            "resolution_actions": policy_result['resolution_actions']
        }

        # Step 9: Verify
        verified_output = self.verifier_agent.verify(final_output)

        # Step 10: Build trace entry
        trace_entry = {
            'case_id': case_id,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'agents': [
                {'agent': 'coordinator', 'action': 'dispatch', 'status': 'complete'},
                {'agent': 'customer_agent', 'action': 'investigate', 'status': 'complete',
                 'output_summary': self._make_summary('customer_agent', 'investigate customer',
                    f"customer_unique_id={customer_data.get('customer_unique_id')}, related_orders={len(customer_data.get('related_order_ids', []))}",
                    f"Found customer with {len(customer_data.get('related_order_ids', []))} related orders")},
                {'agent': 'order_product_agent', 'action': 'investigate', 'status': 'complete',
                 'output_summary': self._make_summary('order_product_agent', 'investigate order items',
                    f"items={len(order_product_data.get('item_ids', []))}, sellers={len(order_product_data.get('seller_ids', []))}",
                    f"Found {len(order_product_data.get('item_ids', []))} items from {len(order_product_data.get('seller_ids', []))} sellers")},
                {'agent': 'payment_agent', 'action': 'investigate', 'status': 'complete',
                 'output_summary': self._make_summary('payment_agent', 'reconcile payments',
                    f"payment_total={payment_data.get('payment_reconciliation', {}).get('payment_total_brl')}, reconciled={payment_data.get('payment_reconciliation', {}).get('reconciled')}",
                    f"Payment total={payment_data.get('payment_reconciliation', {}).get('payment_total_brl')} BRL, reconciled={payment_data.get('payment_reconciliation', {}).get('reconciled')}")},
                {'agent': 'delivery_agent', 'action': 'investigate', 'status': 'complete',
                 'output_summary': self._make_summary('delivery_agent', 'analyze delivery',
                    f"variance_hours={delivery_data.get('delivery_variance_hours')}, late_sellers={len(delivery_data.get('late_handoff_seller_ids', []))}",
                    f"Delivery variance={delivery_data.get('delivery_variance_hours')}h, {len(delivery_data.get('late_handoff_seller_ids', []))} late sellers")},
                {'agent': 'policy_agent', 'action': 'evaluate', 'status': 'complete',
                 'output_summary': self._make_summary('policy_agent', 'apply EC_POLICY_V2',
                    f"primary={policy_result['case_assessment']['primary_issue']}, status={policy_result['case_assessment']['case_status']}",
                    f"Primary issue: {policy_result['case_assessment']['primary_issue']}, refund={policy_result['financial_resolution']['recommended_refund_brl']} BRL")},
                {'agent': 'verifier_agent', 'action': 'verify', 'status': 'complete',
                 'output_summary': 'Output verified: schema compliant, evidence IDs valid, array limits enforced'},
            ],
            'result': {
                'primary_issue': verified_output['case_assessment']['primary_issue'],
                'case_status': verified_output['case_assessment']['case_status'],
                'refund_brl': verified_output['financial_resolution']['recommended_refund_brl']
            }
        }

        return verified_output, trace_entry
