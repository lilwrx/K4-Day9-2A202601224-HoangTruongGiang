import json
import os
from datetime import datetime

class TraceLogger:
    def __init__(self, log_path: str = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\logging\trace.jsonl"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        # Clear existing log for new run
        with open(self.log_path, "w", encoding="utf-8") as f:
            pass

    def log_event(self, case_id: str, agent_name: str, action: str, details: dict):
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "case_id": case_id,
            "agent": agent_name,
            "action": action,
            "details": details
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
