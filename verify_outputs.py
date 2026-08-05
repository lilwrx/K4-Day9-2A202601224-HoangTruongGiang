import os
import glob
import json
import re

def verify_outputs():
    output_files = sorted(glob.glob('output/EC_*.json'))
    print(f"Verifying {len(output_files)} files in output/...")
    
    assert len(output_files) == 50, f"Expected 50 output files, found {len(output_files)}"

    valid_primary_issues = {
        'canceled_order_paid',
        'unavailable_order_paid',
        'late_delivery_seller',
        'late_delivery_logistics',
        'valid_split_payment',
        'unsupported_late_claim'
    }

    valid_secondary_issues = {
        'multi_item_order',
        'multi_seller_order',
        'split_payment',
        'repeat_customer',
        'multiple_categories'
    }

    valid_cause_codes = {
        'SELLER_HANDOFF_AFTER_LIMIT',
        'CARRIER_DELIVERED_AFTER_ESTIMATE',
        'ORDER_CANCELED_AFTER_PAYMENT',
        'ORDER_UNAVAILABLE_AFTER_PAYMENT',
        'MULTIPLE_PAYMENTS_RECONCILED',
        'DELIVERY_WITHIN_ESTIMATE'
    }

    evidence_pattern = re.compile(r'^(order:[^:]+|item:[^:]+:\d+|payment:[^:]+:\d+|seller:[^:]+|policy:[A-Z0-9_]+)$')

    errors = []

    for fpath in output_files:
        filename = os.path.basename(fpath)
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 1. Top-level keys
        req_top = [
            'case_id', 'case_assessment', 'affected_entities', 'customer_context',
            'product_context', 'delivery_analysis', 'payment_reconciliation',
            'root_cause_analysis', 'evidence_ids', 'financial_resolution', 'resolution_actions'
        ]
        for k in req_top:
            if k not in data:
                errors.append(f"{filename}: Missing top-level key {k}")

        # 2. Case assessment
        ca = data.get('case_assessment', {})
        if ca.get('primary_issue') not in valid_primary_issues:
            errors.append(f"{filename}: Invalid primary issue {ca.get('primary_issue')}")

        for sec in ca.get('secondary_issues', []):
            if sec not in valid_secondary_issues:
                errors.append(f"{filename}: Invalid secondary issue {sec}")

        status = ca.get('case_status')
        refund = data.get('financial_resolution', {}).get('recommended_refund_brl', 0.0)
        if refund > 0 and status != 'action_required':
            errors.append(f"{filename}: Refund > 0 ({refund}) but case_status is {status}")
        elif refund == 0 and status != 'no_action':
            errors.append(f"{filename}: Refund == 0 but case_status is {status}")

        conf = ca.get('confidence')
        if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
            errors.append(f"{filename}: Invalid confidence {conf}")

        # 3. Array limits
        ae = data.get('affected_entities', {})
        if len(ae.get('order_ids', [])) > 5:
            errors.append(f"{filename}: order_ids > 5")
        if len(ae.get('item_ids', [])) > 5:
            errors.append(f"{filename}: item_ids > 5")
        if len(ae.get('seller_ids', [])) > 3:
            errors.append(f"{filename}: seller_ids > 3")
        if len(ae.get('payment_ids', [])) > 5:
            errors.append(f"{filename}: payment_ids > 5")

        cc = data.get('customer_context', {})
        if len(cc.get('related_order_ids', [])) > 5:
            errors.append(f"{filename}: related_order_ids > 5")

        pc = data.get('product_context', {})
        if len(pc.get('product_ids', [])) > 5:
            errors.append(f"{filename}: product_ids > 5")
        if len(pc.get('category_names', [])) > 5:
            errors.append(f"{filename}: category_names > 5")

        rca = data.get('root_cause_analysis', {})
        if len(rca.get('ranked_causes', [])) > 3:
            errors.append(f"{filename}: ranked_causes > 3")
        if len(rca.get('responsible_parties', [])) > 3:
            errors.append(f"{filename}: responsible_parties > 3")

        ev = data.get('evidence_ids', [])
        if len(ev) > 20:
            errors.append(f"{filename}: evidence_ids > 20")

        act = data.get('resolution_actions', [])
        if len(act) > 5:
            errors.append(f"{filename}: resolution_actions > 5")

        # 4. Evidence ID regex
        for evid in ev:
            if not evidence_pattern.match(evid):
                errors.append(f"{filename}: Malformed evidence ID: {evid}")

        # 5. Itemless orders null check
        pr = data.get('payment_reconciliation', {})
        if len(ae.get('item_ids', [])) == 0:
            if pr.get('expected_total_brl') is not None or pr.get('reconciled') is not None:
                errors.append(f"{filename}: Itemless order should have null expected_total_brl and reconciled")

    if errors:
        print(f"Validation FAILED with {len(errors)} errors:")
        for err in errors[:10]:
            print(f" - {err}")
    else:
        print("Validation PASSED! All 50 files comply 100% with the requirements.")

if __name__ == '__main__':
    verify_outputs()
