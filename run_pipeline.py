import os
import json
import zipfile
import time
from src.data_engine.olist_db import OlistDB
from src.utils.logger import TraceLogger
from src.agents.coordinator import CoordinatorAgent

def run():
    print("=== Step 1: Initializing Olist SQLite Data Engine ===")
    t0 = time.time()
    db = OlistDB()
    print(f"Data Engine loaded in {time.time() - t0:.2f}s")

    print("\n=== Step 2: Initializing Multi-Agent System (Qwen2.5-7B-Instruct) ===")
    logger = TraceLogger()
    coordinator = CoordinatorAgent(db, model_name="Qwen/Qwen2.5-7B-Instruct")

    input_dir = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\input"
    output_dir = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\output"
    os.makedirs(output_dir, exist_ok=True)

    print("\n=== Step 3: Processing 50 Dispute Cases ===")
    processed_count = 0
    for i in range(1, 51):
        filename = f"EC_{i:03d}.json"
        in_path = os.path.join(input_dir, filename)
        out_path = os.path.join(output_dir, filename)

        if not os.path.exists(in_path):
            print(f"Warning: {filename} not found in input/!")
            continue

        with open(in_path, "r", encoding="utf-8") as f:
            input_case = json.load(f)

        result = coordinator.process_case(input_case, logger=logger)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        processed_count += 1
        print(f"[{processed_count:02d}/50] Processed {filename} -> Primary Issue: {result['case_assessment']['primary_issue']}")

    print(f"\nSuccessfully processed {processed_count} cases to output/")

    print("\n=== Step 4: Writing metadata.json ===")
    metadata = {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "parameter_size": "7B",
        "framework": "custom-multi-agent",
        "runtime": "Python 3.11"
    }
    
    metadata_path = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\logging\metadata.json"
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    
    # Also write metadata.json to root if required
    with open(r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # Copy trace.jsonl to root if required
    trace_path = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\logging\trace.jsonl"
    root_trace_path = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\trace.jsonl"
    if os.path.exists(trace_path):
        with open(trace_path, "r", encoding="utf-8") as sf, open(root_trace_path, "w", encoding="utf-8") as df:
            df.write(sf.read())

    print("\n=== Step 5: Packaging output.zip ===")
    zip_path = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\output.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.endswith(".json") and file.startswith("EC_"):
                    file_path = os.path.join(root, file)
                    arcname = file  # Store directly inside zip root as EC_xxx.json
                    zipf.write(file_path, arcname)

    print(f"Created zip artifact at: {zip_path}")
    print("=== Pipeline Complete! ===")

if __name__ == "__main__":
    run()
