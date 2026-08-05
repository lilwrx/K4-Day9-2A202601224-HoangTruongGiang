"""Entry point: chay pipeline multi-agent tren toan bo 50 case.

    python run.py                # dung LLM neu co GROQ_API_KEY, khong thi rule engine
    python run.py --no-llm       # ep chay deterministic
    python run.py --case EC_001  # chay mot case de debug
"""

import argparse
import json
import platform
import sys
import time
from collections import Counter

from src import config, llm
from src.coordinator import process_case
from src.data_store import DataStore
from src.trace import TraceWriter


def load_cases(case_filter=None) -> list[dict]:
    cases = []
    for path in sorted(config.INPUT_DIR.glob("EC_*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        if case_filter and case["case_id"] != case_filter:
            continue
        cases.append(case)
    return cases


def write_metadata(runtime_s: float, mode: str, case_count: int) -> None:
    metadata = {
        "model": config.LLM_MODEL,
        "provider": config.LLM_PROVIDER,
        "parameter_size": f"{config.LLM_PARAM_SIZE_B}B",
        "parameter_size_constraint": "<=10B",
        "framework": "custom multi-agent orchestration (Python stdlib, no external deps)",
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "total_seconds": round(runtime_s, 2),
            "cases": case_count,
        },
        "policy_version": config.POLICY_VERSION,
        "execution_mode": mode,
        "agents": [
            "coordinator",
            "customer_agent",
            "order_product_agent",
            "payment_agent",
            "delivery_agent",
            "policy_agent",
            "verifier_agent",
        ],
        "llm_settings": {
            "temperature": config.LLM_TEMPERATURE,
            "max_tokens": config.LLM_MAX_TOKENS,
            "response_format": "json_object",
        },
    }
    config.METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="ep chay rule engine")
    parser.add_argument("--case", help="chi chay mot case_id")
    args = parser.parse_args()

    use_llm = not args.no_llm
    if use_llm and not llm.is_available():
        print("[!] Khong tim thay GROQ_API_KEY -> chay bang rule engine deterministic.")
        use_llm = False

    started = time.perf_counter()
    print("Dang load du lieu Olist...")
    store = DataStore()
    print(f"    {store.stats()}")

    cases = load_cases(args.case)
    if not cases:
        print("Khong tim thay case nao trong input/", file=sys.stderr)
        return 1

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    primary_counter = Counter()
    mode_counter = Counter()
    failed = []

    with TraceWriter() as tracer:
        tracer.emit(
            "-",
            "coordinator",
            "run_start",
            {
                "cases": len(cases),
                "use_llm": use_llm,
                "model": config.LLM_MODEL if use_llm else None,
                "policy_version": config.POLICY_VERSION,
            },
        )

        for case in cases:
            payload, issues = process_case(store, case, tracer, use_llm=use_llm)
            primary_counter[payload["case_assessment"]["primary_issue"]] += 1
            if issues:
                failed.append((case["case_id"], issues))

            out_path = config.OUTPUT_DIR / f"{case['case_id']}.json"
            out_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        runtime = time.perf_counter() - started
        tracer.emit(
            "-",
            "coordinator",
            "run_end",
            {
                "cases": len(cases),
                "verifier_failures": len(failed),
                "primary_issue_distribution": dict(primary_counter),
                "total_seconds": round(runtime, 2),
            },
        )

    mode = "llm" if use_llm else "rule_engine"
    write_metadata(runtime, mode, len(cases))

    print(f"\nDa ghi {len(cases)} file vao {config.OUTPUT_DIR}")
    print(f"Phan bo primary issue: {dict(primary_counter)}")
    if failed:
        print(f"\n[!] Verifier bao loi o {len(failed)} case:")
        for case_id, issues in failed:
            print(f"  {case_id}: {issues}")
        return 2
    print("Verifier: tat ca case dat chuan schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
