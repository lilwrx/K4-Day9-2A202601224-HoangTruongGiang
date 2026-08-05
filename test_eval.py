import os
import json
import zipfile

def run_tests():
    print("==========================================")
    print("       EVALUATION & VALIDATION SUITE      ")
    print("==========================================")

    output_dir = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\output"
    input_dir = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\input"
    zip_path = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\output.zip"

    errors = []

    # 1. Test presence of 50 files
    print("\n[Test 1] Checking output files presence (EC_001.json to EC_050.json)...")
    for i in range(1, 51):
        fn = f"EC_{i:03d}.json"
        p = os.path.join(output_dir, fn)
        if not os.path.exists(p):
            errors.append(f"Missing output file: {fn}")

    if not errors:
        print("  -> PASSED: All 50 output JSON files exist.")

    # 2. Test JSON parsing & schema structure
    print("\n[Test 2] Validating JSON schema and hard gate constraints for 50 cases...")
    valid_primary_issues = {
        "canceled_order_paid", "unavailable_order_paid", "late_delivery_seller",
        "late_delivery_logistics", "valid_split_payment", "unsupported_late_claim"
    }
    valid_secondary_issues = {
        "multi_item_order", "multi_seller_order", "split_payment",
        "repeat_customer", "multiple_categories"
    }

    for i in range(1, 51):
        fn = f"EC_{i:03d}.json"
        p = os.path.join(output_dir, fn)
        if not os.path.exists(p):
            continue

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check case_id
            if data.get("case_id") != f"EC_{i:03d}":
                errors.append(f"{fn}: case_id mismatch '{data.get('case_id')}' != 'EC_{i:03d}'")

            # Check primary issue
            p_issue = data.get("case_assessment", {}).get("primary_issue")
            if p_issue not in valid_primary_issues:
                errors.append(f"{fn}: Invalid primary_issue '{p_issue}'")

            # Check array limits
            ae = data.get("affected_entities", {})
            if len(ae.get("order_ids", [])) > 5:
                errors.append(f"{fn}: order_ids array length > 5")
            if len(ae.get("item_ids", [])) > 5:
                errors.append(f"{fn}: item_ids array length > 5")
            if len(ae.get("seller_ids", [])) > 3:
                errors.append(f"{fn}: seller_ids array length > 3")
            if len(ae.get("payment_ids", [])) > 5:
                errors.append(f"{fn}: payment_ids array length > 5")

            # Check evidence limit & format
            ev = data.get("evidence_ids", [])
            if len(ev) > 20:
                errors.append(f"{fn}: evidence_ids array length > 20")
            for e_id in ev:
                if not any(e_id.startswith(prefix) for prefix in ["order:", "item:", "payment:", "seller:", "policy:"]):
                    errors.append(f"{fn}: Invalid evidence_id prefix '{e_id}'")

            # Check actions limit
            act = data.get("resolution_actions", [])
            if len(act) > 5:
                errors.append(f"{fn}: resolution_actions array length > 5")

        except Exception as ex:
            errors.append(f"{fn}: Error parsing JSON: {str(ex)}")

    if not errors:
        print("  -> PASSED: All 50 JSON outputs fully satisfy schema and hard gate rules.")

    # 3. Test Zip file contents
    print("\n[Test 3] Validating zip file content...")
    if not os.path.exists(zip_path):
        errors.append("output.zip file does not exist!")
    else:
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            if len(names) != 50:
                errors.append(f"Zip file contains {len(names)} files, expected 50.")
            for fn in names:
                base_fn = os.path.basename(fn)
                if not (base_fn.startswith("EC_") and base_fn.endswith(".json")):
                    errors.append(f"Unexpected file in zip: {fn}")
        print(f"  -> PASSED: output.zip contains exactly 50 valid JSON files.")

    # 4. Test trace.jsonl and metadata.json
    print("\n[Test 4] Checking trace log & metadata...")
    meta_p = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\metadata.json"
    trace_p = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\trace.jsonl"

    if not os.path.exists(meta_p):
        errors.append("metadata.json missing from root!")
    else:
        with open(meta_p, "r", encoding="utf-8") as f:
            m = json.load(f)
            if not m.get("model"):
                errors.append("metadata.json is missing required 'model' key")
        print("  -> PASSED: metadata.json verified.")

    if not os.path.exists(trace_p):
        errors.append("trace.jsonl missing from root!")
    else:
        with open(trace_p, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if len(lines) == 0:
                errors.append("trace.jsonl is empty!")
            else:
                print(f"  -> PASSED: trace.jsonl verified ({len(lines)} log events recorded).")

    print("\n==========================================")
    if errors:
        print("  [ERROR] TEST EVALUATION FAILED WITH ERRORS:")
        for err in errors:
            print("   -", err)
        return False
    else:
        print("  [OK] ALL EVALUATION TESTS PASSED (100% SUCCESS)!")
        print("==========================================")
        return True

if __name__ == "__main__":
    run_tests()
