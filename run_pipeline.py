import os
import sys
import glob
import json
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Ensure src directory is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.dispute_system import CoordinatorAgent

def main():
    input_dir = 'input'
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)

    coordinator = CoordinatorAgent(data_dir='data')

    input_files = sorted(glob.glob(os.path.join(input_dir, 'EC_*.json')))
    print(f"Found {len(input_files)} input cases in {input_dir}/.")

    all_traces = []
    start_time = time.time()

    for idx, input_path in enumerate(input_files, 1):
        case_id = os.path.basename(input_path).replace('.json', '')
        output_path = os.path.join(output_dir, f"{case_id}.json")

        final_output, trace_events = coordinator.process_case(input_path)
        
        # Save output JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)
        
        for event in trace_events:
            event['timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            all_traces.append(event)

        print(f"[{idx}/{len(input_files)}] Processed {case_id} -> Primary: {final_output['case_assessment']['primary_issue']}, Status: {final_output['case_assessment']['case_status']}")

    elapsed = time.time() - start_time
    print(f"Completed processing {len(input_files)} cases in {elapsed:.2f} seconds.")

    # Write trace.jsonl
    trace_file = 'trace.jsonl'
    with open(trace_file, 'w', encoding='utf-8') as f:
        for trace in all_traces:
            f.write(json.dumps(trace, ensure_ascii=False) + '\n')
    print(f"Saved trace log to {trace_file}.")

    # Write metadata.json
    llm_client = coordinator.policy_agent.llm_client
    is_llm_active = llm_client.is_available()
    active_model = llm_client.model if is_llm_active else "Qwen2.5-7B-Instruct"
    active_provider = llm_client.provider if is_llm_active else "Local Rule Engine (Fallback)"

    metadata = {
        "model_name": active_model,
        "parameter_size": "8B" if "8b" in active_model.lower() else "7B",
        "framework": "Custom Multi-Agent A2A Framework / Python 3.11",
        "active_provider": active_provider,
        "llm_api_available": is_llm_active,
        "supported_apis": {
            "groq": "llama-3.1-8b-instant (via GROQ_API_KEY)",
            "openrouter": "qwen/qwen-2.5-7b-instruct / qwen3-8b (via OPENROUTER_API_KEY)",
            "huggingface": "Qwen/Qwen2.5-7B-Instruct (via HF_TOKEN / HUGGINGFACE_API_KEY)"
        },
        "runtime": f"Python Multi-Agent Handoff [{active_provider}]",
        "total_cases_processed": len(input_files),
        "execution_time_seconds": round(elapsed, 2)
    }
    with open('metadata.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print("Saved metadata.json.")

if __name__ == '__main__':
    main()
