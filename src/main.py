"""
K4 Day 09 - Multi-Agent E-commerce Dispute Resolution
Main entry point: processes 50 input cases and generates output JSONs + trace + metadata.

Model: llama-3.1-8b-instant (8B parameters) via Groq API
Framework: Python + pandas + groq SDK
"""
import os
import sys
import json
import time
import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load .env
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from src.data_loader import DataLoader
from src.agents.coordinator_agent import CoordinatorAgent
from src.llm_client import get_model_name, get_model_params

# Model name declared explicitly in source code (as required by lab rules)
MODEL_NAME = "llama-3.1-8b-instant"
MODEL_PARAMS = "8B"
FRAMEWORK = "python+pandas+groq"


def main():
    print("=" * 60)
    print("K4 Day 09 - Multi-Agent E-commerce Dispute Resolution")
    print(f"Model: {MODEL_NAME} ({MODEL_PARAMS} parameters)")
    print("=" * 60)

    input_dir = os.path.join(PROJECT_ROOT, 'input')
    output_dir = os.path.join(PROJECT_ROOT, 'output')
    logging_dir = os.path.join(PROJECT_ROOT, 'logging')

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(logging_dir, exist_ok=True)

    # Pre-load data (singleton, only loads once)
    print("\n[1/4] Loading data...")
    start_load = time.time()
    dl = DataLoader(os.path.join(PROJECT_ROOT, 'data'))
    print(f"  Data loaded in {time.time() - start_load:.2f}s")

    # Initialize coordinator
    coordinator = CoordinatorAgent()

    # Process all 50 cases
    print("\n[2/4] Processing 50 cases...")
    trace_entries = []
    total_start = time.time()
    errors = []

    for i in range(1, 51):
        case_file = f"EC_{i:03d}.json"
        input_path = os.path.join(input_dir, case_file)

        if not os.path.exists(input_path):
            print(f"  [SKIP] {case_file} not found, skipping")
            errors.append(case_file)
            continue

        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                case_data = json.load(f)

            case_start = time.time()
            output, trace = coordinator.process_case(case_data)
            case_time = time.time() - case_start

            # Write output
            output_path = os.path.join(output_dir, case_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            trace_entries.append(trace)

            status = output['case_assessment']['case_status']
            issue = output['case_assessment']['primary_issue']
            refund = output['financial_resolution']['recommended_refund_brl']
            print(f"  [OK] {case_file} | {issue:30s} | {status:15s} | refund={refund:>10.2f} BRL | {case_time:.2f}s")

        except Exception as e:
            print(f"  [ERR] {case_file} ERROR: {e}")
            errors.append(case_file)
            import traceback
            traceback.print_exc()

    total_time = time.time() - total_start
    print(f"\n  Processed {50 - len(errors)}/50 cases in {total_time:.2f}s")

    # Write trace
    print("\n[3/4] Writing trace.jsonl...")
    trace_path = os.path.join(logging_dir, 'trace.jsonl')
    with open(trace_path, 'w', encoding='utf-8') as f:
        for entry in trace_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    print(f"  Written {len(trace_entries)} trace entries")

    # Write metadata
    print("\n[4/4] Writing metadata.json...")
    metadata = {
        "model": MODEL_NAME,
        "parameter_size": MODEL_PARAMS,
        "framework": FRAMEWORK,
        "runtime": {
            "python_version": sys.version,
            "total_cases": 50,
            "processed_cases": 50 - len(errors),
            "total_time_seconds": round(total_time, 2),
            "avg_time_per_case_seconds": round(total_time / max(1, 50 - len(errors)), 2)
        },
        "agents": [
            {"name": "coordinator_agent", "role": "orchestration"},
            {"name": "customer_agent", "role": "customer identity & history"},
            {"name": "order_product_agent", "role": "order, items, sellers, products"},
            {"name": "payment_agent", "role": "payment reconciliation"},
            {"name": "delivery_agent", "role": "delivery & handoff analysis"},
            {"name": "policy_agent", "role": "EC_POLICY_V2 evaluation"},
            {"name": "verifier_agent", "role": "schema & data validation"}
        ],
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    metadata_path = os.path.join(logging_dir, 'metadata.json')
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print("DONE!")
    if errors:
        print(f"  Errors: {errors}")
    print(f"  Output: {output_dir}")
    print(f"  Trace:  {trace_path}")
    print(f"  Meta:   {metadata_path}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
