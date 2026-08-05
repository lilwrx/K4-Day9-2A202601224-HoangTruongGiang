import re
from datetime import datetime


class VerifierAgent:
    """Validates the final output JSON: checks formats, enforces array limits, ensures schema compliance."""

    ARRAY_LIMITS = {
        'affected_entities.order_ids': 5,
        'affected_entities.item_ids': 5,
        'affected_entities.seller_ids': 3,
        'affected_entities.payment_ids': 5,
        'customer_context.related_order_ids': 5,
        'product_context.product_ids': 5,
        'product_context.category_names': 5,
        'root_cause_analysis.ranked_causes': 3,
        'root_cause_analysis.responsible_parties': 3,
        'evidence_ids': 20,
        'resolution_actions': 5,
    }

    EVIDENCE_PATTERNS = [
        re.compile(r'^order:[a-f0-9]+$'),
        re.compile(r'^item:[a-f0-9]+:\d+$'),
        re.compile(r'^payment:[a-f0-9]+:\d+$'),
        re.compile(r'^seller:[a-f0-9]+$'),
        re.compile(r'^policy:[A-Z_]+$'),
    ]

    def _is_valid_evidence_id(self, eid: str) -> bool:
        return any(p.match(eid) for p in self.EVIDENCE_PATTERNS)

    def _check_timestamp(self, val):
        if val is None:
            return None
        try:
            datetime.strptime(str(val), '%Y-%m-%d %H:%M:%S')
            return str(val)
        except ValueError:
            return None

    def verify(self, output_dict: dict) -> dict:
        # --- Truncate arrays ---
        ae = output_dict.get('affected_entities', {})
        ae['order_ids'] = ae.get('order_ids', [])[:5]
        ae['item_ids'] = ae.get('item_ids', [])[:5]
        ae['seller_ids'] = ae.get('seller_ids', [])[:3]
        ae['payment_ids'] = ae.get('payment_ids', [])[:5]

        cc = output_dict.get('customer_context', {})
        cc['related_order_ids'] = cc.get('related_order_ids', [])[:5]

        pc = output_dict.get('product_context', {})
        pc['product_ids'] = pc.get('product_ids', [])[:5]
        pc['category_names'] = pc.get('category_names', [])[:5]

        rc = output_dict.get('root_cause_analysis', {})
        rc['ranked_causes'] = rc.get('ranked_causes', [])[:3]
        rc['responsible_parties'] = rc.get('responsible_parties', [])[:3]

        output_dict['evidence_ids'] = output_dict.get('evidence_ids', [])[:20]
        output_dict['resolution_actions'] = output_dict.get('resolution_actions', [])[:5]

        # --- Validate evidence IDs ---
        valid_evidence = [eid for eid in output_dict.get('evidence_ids', []) if self._is_valid_evidence_id(eid)]
        output_dict['evidence_ids'] = valid_evidence

        # --- Validate case_status matches refund ---
        refund = output_dict.get('financial_resolution', {}).get('recommended_refund_brl', 0.0)
        ca = output_dict.get('case_assessment', {})
        ca['case_status'] = 'action_required' if refund > 0 else 'no_action'

        # --- Validate confidence in [0, 1] ---
        conf = ca.get('confidence', 0.95)
        ca['confidence'] = max(0.0, min(1.0, conf))

        # --- Validate delivery timestamps ---
        da = output_dict.get('delivery_analysis', {})
        for field in ['delivered_at', 'estimated_delivery_at', 'carrier_handoff_at']:
            da[field] = self._check_timestamp(da.get(field))
        for h in da.get('seller_handoff_analysis', []):
            h['shipping_limit_at'] = self._check_timestamp(h.get('shipping_limit_at'))

        return output_dict
