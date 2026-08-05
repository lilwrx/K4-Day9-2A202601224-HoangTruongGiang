import json
import os
import math
from datetime import datetime
import pandas as pd

class CustomerAgent:
    """Agent responsible for customer identity and order history analysis."""
    def __init__(self, df_customers, df_orders):
        self.df_customers = df_customers
        self.df_orders = df_orders

    def run(self, customer_id, claimed_order_id):
        cust_row = self.df_customers[self.df_customers['customer_id'] == customer_id]
        if cust_row.empty:
            return {"customer_unique_id": None, "related_order_ids": []}
        
        customer_unique_id = cust_row.iloc[0]['customer_unique_id']
        all_cust_ids = self.df_customers[self.df_customers['customer_unique_id'] == customer_unique_id]['customer_id'].tolist()
        
        related_orders = self.df_orders[
            (self.df_orders['customer_id'].isin(all_cust_ids)) & 
            (self.df_orders['order_id'] != claimed_order_id)
        ]
        
        # Sort related orders by purchase timestamp for stability
        related_orders_sorted = related_orders.sort_values(by='order_purchase_timestamp')
        related_order_ids = related_orders_sorted['order_id'].tolist()[:5]
        
        return {
            "customer_unique_id": customer_unique_id,
            "related_order_ids": related_order_ids
        }


class OrderProductAgent:
    """Agent responsible for order items, products, sellers, and category names."""
    def __init__(self, df_items, df_products, df_translation):
        self.df_items = df_items
        self.df_products = df_products
        # Build category translation dictionary if needed
        self.translation_map = dict(zip(
            df_translation['product_category_name'],
            df_translation['product_category_name_english']
        ))

    def run(self, order_id):
        order_items_df = self.df_items[self.df_items['order_id'] == order_id].sort_values(by='order_item_id')
        
        if order_items_df.empty:
            return {
                "item_ids": [],
                "seller_ids": [],
                "product_ids": [],
                "category_names": [],
                "items_detail": []
            }

        item_ids = []
        items_detail = []
        seller_ids_set = []
        product_ids_set = []
        category_names_set = []

        for _, row in order_items_df.iterrows():
            item_seq = int(row['order_item_id'])
            item_id_str = f"{order_id}:{item_seq}"
            if len(item_ids) < 5:
                item_ids.append(item_id_str)
            
            seller_id = row['seller_id']
            if seller_id not in seller_ids_set and len(seller_ids_set) < 3:
                seller_ids_set.append(seller_id)

            product_id = row['product_id']
            if product_id not in product_ids_set and len(product_ids_set) < 5:
                product_ids_set.append(product_id)

            # Get product category
            prod_row = self.df_products[self.df_products['product_id'] == product_id]
            if not prod_row.empty:
                cat_name = prod_row.iloc[0]['product_category_name']
                if pd.notna(cat_name) and cat_name:
                    # Keep original category name as per dataset
                    if cat_name not in category_names_set and len(category_names_set) < 5:
                        category_names_set.append(str(cat_name))

            items_detail.append({
                "order_item_id": item_seq,
                "product_id": product_id,
                "seller_id": seller_id,
                "shipping_limit_date": str(row['shipping_limit_date']) if pd.notna(row['shipping_limit_date']) else None,
                "price": float(row['price']),
                "freight_value": float(row['freight_value'])
            })

        return {
            "item_ids": item_ids,
            "seller_ids": seller_ids_set,
            "product_ids": product_ids_set,
            "category_names": category_names_set,
            "items_detail": items_detail
        }


class PaymentAgent:
    """Agent responsible for payment reconciliation."""
    def __init__(self, df_payments):
        self.df_payments = df_payments

    def run(self, order_id, items_detail):
        payment_rows = self.df_payments[self.df_payments['order_id'] == order_id].sort_values(by='payment_sequential')
        
        payment_ids = []
        payment_types = []
        payment_total_brl = 0.0

        for _, row in payment_rows.iterrows():
            p_seq = int(row['payment_sequential'])
            if len(payment_ids) < 5:
                payment_ids.append(f"{order_id}:{p_seq}")
            
            p_type = str(row['payment_type'])
            if p_type not in payment_types:
                payment_types.append(p_type)

            payment_total_brl += float(row['payment_value'])

        payment_total_brl = round(payment_total_brl, 2)

        if not items_detail:
            # Order with no items
            return {
                "payment_ids": payment_ids,
                "reconciliation": {
                    "currency": "BRL",
                    "item_total_brl": None,
                    "freight_total_brl": None,
                    "expected_total_brl": None,
                    "payment_total_brl": payment_total_brl,
                    "difference_brl": None,
                    "reconciled": None,
                    "payment_types": payment_types
                }
            }

        item_total = round(sum(item['price'] for item in items_detail), 2)
        freight_total = round(sum(item['freight_value'] for item in items_detail), 2)
        expected_total = round(item_total + freight_total, 2)
        difference = round(payment_total_brl - expected_total, 2)
        reconciled = abs(difference) <= 0.10

        return {
            "payment_ids": payment_ids,
            "reconciliation": {
                "currency": "BRL",
                "item_total_brl": item_total,
                "freight_total_brl": freight_total,
                "expected_total_brl": expected_total,
                "payment_total_brl": payment_total_brl,
                "difference_brl": difference,
                "reconciled": reconciled,
                "payment_types": payment_types
            }
        }


class DeliveryAgent:
    """Agent responsible for delivery dates and seller handoff analysis."""
    def run(self, order_row, items_detail):
        delivered_at = str(order_row['order_delivered_customer_date']) if pd.notna(order_row['order_delivered_customer_date']) else None
        estimated_delivery_at = str(order_row['order_estimated_delivery_date']) if pd.notna(order_row['order_estimated_delivery_date']) else None
        carrier_handoff_at = str(order_row['order_delivered_carrier_date']) if pd.notna(order_row['order_delivered_carrier_date']) else None

        delivery_variance_hours = None
        if delivered_at and estimated_delivery_at:
            dt_del = datetime.strptime(delivered_at, "%Y-%m-%d %H:%M:%S")
            dt_est = datetime.strptime(estimated_delivery_at, "%Y-%m-%d %H:%M:%S")
            delivery_variance_hours = round((dt_del - dt_est).total_seconds() / 3600.0, 2)

        seller_handoff_analysis = []
        late_handoff_seller_ids = []

        if items_detail and carrier_handoff_at:
            dt_carrier = datetime.strptime(carrier_handoff_at, "%Y-%m-%d %H:%M:%S")
            # Group items by seller_id to find earliest shipping limit date
            seller_limits = {}
            for item in items_detail:
                s_id = item['seller_id']
                s_limit = item['shipping_limit_date']
                if s_limit:
                    if s_id not in seller_limits or s_limit < seller_limits[s_id]:
                        seller_limits[s_id] = s_limit

            for s_id, s_limit in seller_limits.items():
                dt_limit = datetime.strptime(s_limit, "%Y-%m-%d %H:%M:%S")
                h_var = round((dt_carrier - dt_limit).total_seconds() / 3600.0, 2)
                is_late = dt_carrier > dt_limit
                if is_late:
                    late_handoff_seller_ids.append(s_id)
                
                seller_handoff_analysis.append({
                    "seller_id": s_id,
                    "shipping_limit_at": s_limit,
                    "handoff_variance_hours": h_var,
                    "late_handoff": is_late
                })

        return {
            "delivered_at": delivered_at,
            "estimated_delivery_at": estimated_delivery_at,
            "carrier_handoff_at": carrier_handoff_at,
            "delivery_variance_hours": delivery_variance_hours,
            "seller_handoff_analysis": seller_handoff_analysis,
            "late_handoff_seller_ids": late_handoff_seller_ids
        }


class PolicyAgent:
    """Agent implementing EC_POLICY_V2 business rules."""
    def run(self, order_status, delivery_info, payment_info, order_product_info, customer_info):
        reconciled = payment_info['reconciliation']['reconciled']
        payment_total = payment_info['reconciliation']['payment_total_brl']
        freight_total = payment_info['reconciliation']['freight_total_brl']
        
        delivered_at = delivery_info['delivered_at']
        estimated_delivery_at = delivery_info['estimated_delivery_at']
        late_sellers = delivery_info['late_handoff_seller_ids']

        is_delivered_late = False
        if delivered_at and estimated_delivery_at:
            is_delivered_late = delivered_at > estimated_delivery_at

        # Determine Primary Issue
        primary_issue = None
        cause_code = None
        responsible_parties = []
        recommended_refund_brl = 0.0
        primary_action = None

        if order_status == 'canceled' and payment_total > 0:
            primary_issue = 'canceled_order_paid'
            cause_code = 'ORDER_CANCELED_AFTER_PAYMENT'
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            recommended_refund_brl = payment_total
            primary_action = 'issue_full_refund'
        elif order_status == 'unavailable' and payment_total > 0:
            primary_issue = 'unavailable_order_paid'
            cause_code = 'ORDER_UNAVAILABLE_AFTER_PAYMENT'
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            recommended_refund_brl = payment_total
            primary_action = 'issue_full_refund'
        elif is_delivered_late and len(late_sellers) > 0:
            primary_issue = 'late_delivery_seller'
            cause_code = 'SELLER_HANDOFF_AFTER_LIMIT'
            responsible_parties = [{"party_type": "seller", "party_id": s_id} for s_id in late_sellers]
            recommended_refund_brl = freight_total if freight_total is not None and freight_total > 0 else 0.0
            primary_action = 'refund_freight'
        elif is_delivered_late and len(late_sellers) == 0:
            primary_issue = 'late_delivery_logistics'
            cause_code = 'CARRIER_DELIVERED_AFTER_ESTIMATE'
            responsible_parties = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
            recommended_refund_brl = freight_total if freight_total is not None and freight_total > 0 else 0.0
            primary_action = 'refund_freight'
        elif len(payment_info['payment_ids']) >= 2 and reconciled is True:
            primary_issue = 'valid_split_payment'
            cause_code = 'MULTIPLE_PAYMENTS_RECONCILED'
            responsible_parties = []
            recommended_refund_brl = 0.0
            primary_action = 'explain_valid_split_payment'
        else:
            primary_issue = 'unsupported_late_claim'
            cause_code = 'DELIVERY_WITHIN_ESTIMATE'
            responsible_parties = []
            recommended_refund_brl = 0.0
            primary_action = 'reject_late_refund'

        # Determine Secondary Issues (strict order)
        secondary_issues = []
        if len(order_product_info['item_ids']) >= 2:
            secondary_issues.append('multi_item_order')
        if len(order_product_info['seller_ids']) >= 2:
            secondary_issues.append('multi_seller_order')
        if len(payment_info['payment_ids']) >= 2:
            secondary_issues.append('split_payment')
        if len(customer_info['related_order_ids']) >= 1:
            secondary_issues.append('repeat_customer')
        if len(order_product_info['category_names']) >= 2:
            secondary_issues.append('multiple_categories')

        # Determine Resolution Actions (strict order)
        resolution_actions = [primary_action]
        
        if len(late_sellers) > 0:
            resolution_actions.append('review_seller_handoff')
        elif is_delivered_late:
            resolution_actions.append('review_carrier_delay')

        if primary_issue in ['canceled_order_paid', 'unavailable_order_paid', 'late_delivery_seller', 'late_delivery_logistics'] or recommended_refund_brl > 0:
            resolution_actions.append('verify_refund_completion')

        if 'multi_seller_order' in secondary_issues:
            resolution_actions.append('coordinate_multi_seller_case')

        if 'split_payment' in secondary_issues and primary_issue != 'valid_split_payment':
            resolution_actions.append('verify_payment_allocation')

        return {
            "primary_issue": primary_issue,
            "secondary_issues": secondary_issues,
            "cause_code": cause_code,
            "responsible_parties": responsible_parties,
            "recommended_refund_brl": round(recommended_refund_brl, 2),
            "resolution_actions": resolution_actions
        }


class VerifierAgent:
    """Agent responsible for final validation of schema, array limits, evidence IDs, and formats."""
    def run(self, order_id, policy_res, affected_entities, customer_context, product_context, delivery_analysis, payment_recon):
        # Build evidence_ids
        evidence_ids = []
        evidence_ids.append(f"order:{order_id}")
        
        for item_id in affected_entities['item_ids']:
            evidence_ids.append(f"item:{item_id}")
            
        for payment_id in affected_entities['payment_ids']:
            evidence_ids.append(f"payment:{payment_id}")

        for party in policy_res['responsible_parties']:
            if party['party_type'] == 'seller':
                evidence_ids.append(f"seller:{party['party_id']}")

        evidence_ids.append(f"policy:{policy_res['cause_code']}")
        evidence_ids = evidence_ids[:20]

        # Enforce case_status
        refund_val = policy_res['recommended_refund_brl']
        case_status = "action_required" if refund_val > 0 else "no_action"

        # Final assembled output schema
        output = {
            "case_id": "", # filled by coordinator
            "case_assessment": {
                "primary_issue": policy_res['primary_issue'],
                "secondary_issues": policy_res['secondary_issues'],
                "case_status": case_status,
                "confidence": 1.0
            },
            "affected_entities": {
                "order_ids": affected_entities['order_ids'][:5],
                "item_ids": affected_entities['item_ids'][:5],
                "seller_ids": affected_entities['seller_ids'][:3],
                "payment_ids": affected_entities['payment_ids'][:5]
            },
            "customer_context": {
                "customer_unique_id": customer_context['customer_unique_id'],
                "related_order_ids": customer_context['related_order_ids'][:5]
            },
            "product_context": {
                "product_ids": product_context['product_ids'][:5],
                "category_names": product_context['category_names'][:5]
            },
            "delivery_analysis": {
                "delivered_at": delivery_analysis['delivered_at'],
                "estimated_delivery_at": delivery_analysis['estimated_delivery_at'],
                "carrier_handoff_at": delivery_analysis['carrier_handoff_at'],
                "delivery_variance_hours": delivery_analysis['delivery_variance_hours'],
                "seller_handoff_analysis": delivery_analysis['seller_handoff_analysis'],
                "late_handoff_seller_ids": delivery_analysis['late_handoff_seller_ids']
            },
            "payment_reconciliation": payment_recon,
            "root_cause_analysis": {
                "ranked_causes": [
                    {
                        "cause_code": policy_res['cause_code'],
                        "rank": 1
                    }
                ],
                "responsible_parties": policy_res['responsible_parties'][:3]
            },
            "evidence_ids": evidence_ids,
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": refund_val
            },
            "resolution_actions": policy_res['resolution_actions'][:5]
        }
        return output


class CoordinatorAgent:
    """Coordinator Agent orchestrating multi-agent dispute investigation workflow."""
    def __init__(self, data_dir='data'):
        # Load datasets
        self.df_orders = pd.read_csv(os.path.join(data_dir, 'olist_orders_dataset.csv'))
        self.df_customers = pd.read_csv(os.path.join(data_dir, 'olist_customers_dataset.csv'))
        self.df_items = pd.read_csv(os.path.join(data_dir, 'olist_order_items_dataset.csv'))
        self.df_payments = pd.read_csv(os.path.join(data_dir, 'olist_order_payments_dataset.csv'))
        self.df_products = pd.read_csv(os.path.join(data_dir, 'olist_products_dataset.csv'))
        self.df_translation = pd.read_csv(os.path.join(data_dir, 'product_category_name_translation.csv'))

        # Instantiate sub-agents
        self.customer_agent = CustomerAgent(self.df_customers, self.df_orders)
        self.order_product_agent = OrderProductAgent(self.df_items, self.df_products, self.df_translation)
        self.payment_agent = PaymentAgent(self.df_payments)
        self.delivery_agent = DeliveryAgent()
        self.policy_agent = PolicyAgent()
        self.verifier_agent = VerifierAgent()

    def process_case(self, input_case_path):
        with open(input_case_path, 'r', encoding='utf-8') as f:
            case_data = json.load(f)
        
        case_id = case_data['case_id']
        claimed_order_id = case_data['customer_request']['claimed_order_id']
        
        trace_events = []
        trace_events.append({"agent": "CoordinatorAgent", "action": "start_case", "case_id": case_id, "claimed_order_id": claimed_order_id})

        # Fetch Order Row
        order_row = self.df_orders[self.df_orders['order_id'] == claimed_order_id]
        if order_row.empty:
            raise ValueError(f"Order ID {claimed_order_id} not found in orders dataset.")
        order_row = order_row.iloc[0]
        customer_id = order_row['customer_id']
        order_status = str(order_row['order_status'])

        # 1. Customer Agent Handoff
        customer_context = self.customer_agent.run(customer_id, claimed_order_id)
        trace_events.append({"agent": "CustomerAgent", "action": "resolved_customer", "customer_unique_id": customer_context['customer_unique_id']})

        # 2. Order & Product Agent Handoff
        order_product_info = self.order_product_agent.run(claimed_order_id)
        trace_events.append({"agent": "OrderProductAgent", "action": "extracted_order_details", "items_count": len(order_product_info['items_detail'])})

        # 3. Payment Agent Handoff
        payment_info = self.payment_agent.run(claimed_order_id, order_product_info['items_detail'])
        trace_events.append({"agent": "PaymentAgent", "action": "reconciled_payments", "reconciled": payment_info['reconciliation']['reconciled']})

        # 4. Delivery Agent Handoff
        delivery_analysis = self.delivery_agent.run(order_row, order_product_info['items_detail'])
        trace_events.append({"agent": "DeliveryAgent", "action": "computed_delivery_variances", "late_sellers": delivery_analysis['late_handoff_seller_ids']})

        # 5. Policy Agent Handoff
        policy_res = self.policy_agent.run(
            order_status=order_status,
            delivery_info=delivery_analysis,
            payment_info=payment_info,
            order_product_info=order_product_info,
            customer_info=customer_context
        )
        trace_events.append({"agent": "PolicyAgent", "action": "evaluated_policy", "primary_issue": policy_res['primary_issue']})

        # 6. Verifier Agent Handoff
        affected_entities = {
            "order_ids": [claimed_order_id],
            "item_ids": order_product_info['item_ids'],
            "seller_ids": order_product_info['seller_ids'],
            "payment_ids": payment_info['payment_ids']
        }
        product_context = {
            "product_ids": order_product_info['product_ids'],
            "category_names": order_product_info['category_names']
        }

        final_output = self.verifier_agent.run(
            order_id=claimed_order_id,
            policy_res=policy_res,
            affected_entities=affected_entities,
            customer_context=customer_context,
            product_context=product_context,
            delivery_analysis=delivery_analysis,
            payment_recon=payment_info['reconciliation']
        )
        final_output['case_id'] = case_id
        trace_events.append({"agent": "VerifierAgent", "action": "validated_schema_and_limits", "case_id": case_id})

        return final_output, trace_events
