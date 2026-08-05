class PolicyAgent:
    """Applies EC_POLICY_V2 business rules deterministically."""

    def evaluate(self, order_status, order_product_data, payment_data, delivery_data, customer_data) -> dict:
        # Extract data from agent outputs
        payment_recon = payment_data.get('payment_reconciliation', {})
        payment_total = payment_recon.get('payment_total_brl', 0.0)
        freight_total = payment_recon.get('freight_total_brl')
        reconciled = payment_recon.get('reconciled')
        
        num_payment_rows = len(payment_data.get('payment_ids', []))
        num_item_rows = len(order_product_data.get('item_ids', []))
        num_sellers = len(order_product_data.get('seller_ids', []))
        num_categories = len(order_product_data.get('category_names', []))
        
        delivery_variance = delivery_data.get('delivery_variance_hours')
        late_handoff_sellers = delivery_data.get('late_handoff_seller_ids', [])
        related_orders = customer_data.get('related_order_ids', [])
        
        # --- Primary issue (priority order) ---
        primary_issue = None
        
        # 1. canceled_order_paid
        if order_status == 'canceled' and payment_total > 0:
            primary_issue = 'canceled_order_paid'
        # 2. unavailable_order_paid
        elif order_status == 'unavailable' and payment_total > 0:
            primary_issue = 'unavailable_order_paid'
        # 3. late_delivery_seller
        elif delivery_variance is not None and delivery_variance > 0 and len(late_handoff_sellers) > 0:
            primary_issue = 'late_delivery_seller'
        # 4. late_delivery_logistics
        elif delivery_variance is not None and delivery_variance > 0 and len(late_handoff_sellers) == 0:
            primary_issue = 'late_delivery_logistics'
        # 5. valid_split_payment
        elif num_payment_rows >= 2 and reconciled is True:
            primary_issue = 'valid_split_payment'
        # 6. unsupported_late_claim (fallback)
        else:
            primary_issue = 'unsupported_late_claim'

        # --- Secondary issues (in order) ---
        secondary_issues = []
        if num_item_rows >= 2:
            secondary_issues.append('multi_item_order')
        if num_sellers >= 2:
            secondary_issues.append('multi_seller_order')
        if num_payment_rows >= 2:
            secondary_issues.append('split_payment')
        if len(related_orders) > 0:
            secondary_issues.append('repeat_customer')
        if num_categories >= 2:
            secondary_issues.append('multiple_categories')

        # --- Root cause mapping ---
        root_cause_map = {
            'canceled_order_paid': 'ORDER_CANCELED_AFTER_PAYMENT',
            'unavailable_order_paid': 'ORDER_UNAVAILABLE_AFTER_PAYMENT',
            'late_delivery_seller': 'SELLER_HANDOFF_AFTER_LIMIT',
            'late_delivery_logistics': 'CARRIER_DELIVERED_AFTER_ESTIMATE',
            'valid_split_payment': 'MULTIPLE_PAYMENTS_RECONCILED',
            'unsupported_late_claim': 'DELIVERY_WITHIN_ESTIMATE'
        }
        root_cause_code = root_cause_map[primary_issue]

        # --- Responsible parties ---
        responsible_parties = []
        if primary_issue in ('canceled_order_paid', 'unavailable_order_paid'):
            responsible_parties.append({'party_type': 'platform', 'party_id': 'OLIST_PLATFORM'})
        elif primary_issue == 'late_delivery_seller':
            for sid in late_handoff_sellers[:3]:
                responsible_parties.append({'party_type': 'seller', 'party_id': sid})
        elif primary_issue == 'late_delivery_logistics':
            responsible_parties.append({'party_type': 'logistics_provider', 'party_id': 'LOGISTICS_PROVIDER'})

        # --- Refund ---
        if primary_issue in ('canceled_order_paid', 'unavailable_order_paid'):
            refund_brl = round(payment_total, 2)
        elif primary_issue in ('late_delivery_seller', 'late_delivery_logistics'):
            refund_brl = round(freight_total, 2) if freight_total is not None else 0.0
        else:
            refund_brl = 0.0

        # --- Case status ---
        case_status = 'action_required' if refund_brl > 0 else 'no_action'

        # --- Resolution actions ---
        action_map = {
            'canceled_order_paid': 'issue_full_refund',
            'unavailable_order_paid': 'issue_full_refund',
            'late_delivery_seller': 'refund_freight',
            'late_delivery_logistics': 'refund_freight',
            'valid_split_payment': 'explain_valid_split_payment',
            'unsupported_late_claim': 'reject_late_refund'
        }
        actions = [action_map[primary_issue]]

        # Additional actions in order
        if len(late_handoff_sellers) > 0:
            actions.append('review_seller_handoff')
        if primary_issue == 'late_delivery_logistics':
            actions.append('review_carrier_delay')
        if refund_brl > 0:
            actions.append('verify_refund_completion')
        if 'multi_seller_order' in secondary_issues:
            actions.append('coordinate_multi_seller_case')
        if 'split_payment' in secondary_issues and primary_issue != 'valid_split_payment':
            actions.append('verify_payment_allocation')

        actions = actions[:5]

        return {
            'case_assessment': {
                'primary_issue': primary_issue,
                'secondary_issues': secondary_issues,
                'case_status': case_status,
                'confidence': 0.95
            },
            'root_cause_analysis': {
                'ranked_causes': [{'cause_code': root_cause_code, 'rank': 1}],
                'responsible_parties': responsible_parties[:3]
            },
            'financial_resolution': {
                'currency': 'BRL',
                'recommended_refund_brl': refund_brl
            },
            'resolution_actions': actions
        }
