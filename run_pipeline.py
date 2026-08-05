import os
import sys
import glob
import json
import time

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
    metadata = {
        "model_name": "Qwen2.5-7B-Instruct",
        "parameter_size": "7B",
        "framework": "Custom Multi-Agent Framework / Python 3.11",
        "runtime": "Local Python Async Execution",
        "total_cases_processed": len(input_files),
        "execution_time_seconds": round(elapsed, 2)
    }
    with open('metadata.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print("Saved metadata.json.")

if __name__ == '__main__':
    main()
