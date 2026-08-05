import json
import os
import re
import sys
from collections import Counter

REQUIRED_TOP_LEVEL = [
    "case_id", "case_assessment", "affected_entities", "customer_context",
    "product_context", "delivery_analysis", "payment_reconciliation",
    "root_cause_analysis", "evidence_ids", "financial_resolution",
    "resolution_actions"
]

PRIMARY_ISSUES = {
    "canceled_order_paid", "unavailable_order_paid", "late_delivery_seller",
    "late_delivery_logistics", "valid_split_payment", "unsupported_late_claim"
}

EVIDENCE_REGEX = re.compile(
    r"^(order:[a-f0-9]+|item:[a-f0-9]+:\d+|payment:[a-f0-9]+:\d+|seller:[a-f0-9]+|policy:[A-Z_]+)$"
)

TIMESTAMP_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

def validate_timestamp(ts, path, errors):
    if ts is not None and not TIMESTAMP_REGEX.match(str(ts)):
        errors.append(f"{path}: invalid timestamp format '{ts}'")

def validate_file(file_path):
    errors = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return [f"File read/parse error: {e}"], None
        
    for field in REQUIRED_TOP_LEVEL:
        if field not in data:
            errors.append(f"Missing top-level field: {field}")
            
    if not errors:
        # Array limits
        entities = data.get("affected_entities", {})
        if len(entities.get("order_ids", [])) > 5: errors.append("order_ids > 5")
        if len(entities.get("item_ids", [])) > 5: errors.append("item_ids > 5")
        if len(entities.get("seller_ids", [])) > 3: errors.append("seller_ids > 3")
        if len(entities.get("payment_ids", [])) > 5: errors.append("payment_ids > 5")
        
        ctx = data.get("customer_context", {})
        if len(ctx.get("related_order_ids", [])) > 5: errors.append("related_order_ids > 5")
        
        pctx = data.get("product_context", {})
        if len(pctx.get("product_ids", [])) > 5: errors.append("product_ids > 5")
        if len(pctx.get("category_names", [])) > 5: errors.append("category_names > 5")
        
        rca = data.get("root_cause_analysis", {})
        if len(rca.get("ranked_causes", [])) > 3: errors.append("ranked_causes > 3")
        if len(rca.get("responsible_parties", [])) > 3: errors.append("responsible_parties > 3")
        
        evid = data.get("evidence_ids", [])
        if len(evid) > 20: errors.append("evidence_ids > 20")
        for e in evid:
            if not EVIDENCE_REGEX.match(str(e)):
                errors.append(f"Invalid evidence_id format: {e}")
                
        actions = data.get("resolution_actions", [])
        if len(actions) > 5: errors.append("resolution_actions > 5")
        
        # Validate case_status and refund
        assess = data.get("case_assessment", {})
        fin = data.get("financial_resolution", {})
        refund = fin.get("recommended_refund_brl", 0.0)
        refund = refund if refund is not None else 0.0
        status = assess.get("case_status")
        if float(refund) > 0 and status != "action_required":
            errors.append(f"Refund is {refund} but status is {status}")
        elif float(refund) == 0 and status != "no_action":
            errors.append(f"Refund is {refund} but status is {status}")
            
        conf = assess.get("confidence", -1)
        if conf is None or conf < 0 or conf > 1:
            errors.append(f"Confidence out of bounds: {conf}")
            
        issue = assess.get("primary_issue")
        if issue not in PRIMARY_ISSUES:
            errors.append(f"Invalid primary_issue: {issue}")
            
        # Timestamps
        deliv = data.get("delivery_analysis", {})
        validate_timestamp(deliv.get("estimated_delivery_at"), "estimated_delivery_at", errors)
        validate_timestamp(deliv.get("delivered_at"), "delivered_at", errors)
        validate_timestamp(deliv.get("carrier_handoff_at"), "carrier_handoff_at", errors)

    return errors, data.get("case_assessment", {}).get("primary_issue")

def main():
    output_dir = r"d:\VinAI\K4-Day9-2A202601224-HoangTruongGiang\output"
    if not os.path.isdir(output_dir):
        print(f"Error: Directory {output_dir} not found.")
        return
        
    issue_counts = Counter()
    total_files = 0
    failed_files = 0
    all_errors = {}
    
    for filename in sorted(os.listdir(output_dir)):
        if filename.endswith(".json"):
            file_path = os.path.join(output_dir, filename)
            total_files += 1
            errors, issue = validate_file(file_path)
            
            if issue:
                issue_counts[issue] += 1
                
            if errors:
                failed_files += 1
                all_errors[filename] = errors
                
    print(f"--- Validation Summary ---")
    print(f"Total files checked: {total_files}")
    print(f"Passed: {total_files - failed_files}")
    print(f"Failed: {failed_files}")
    print("\n--- Primary Issue Distribution ---")
    for issue, count in issue_counts.items():
        print(f"  {issue}: {count}")
        
    if all_errors:
        print("\n--- Errors by File ---")
        for f, errs in all_errors.items():
            print(f"{f}:")
            for e in errs:
                print(f"  - {e}")
                
    if failed_files > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
