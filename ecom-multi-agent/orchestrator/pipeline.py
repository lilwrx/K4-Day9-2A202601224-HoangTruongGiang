"""
Orchestrator: The LLM-routed coordinator pipeline. For each input/EC_*.json case,
it drives the tool-calling handoff chain via LLM routing:

    fetch_order_data -> run_policy_assessment -> dispatch_resolution_actions
    -> verifier -> output/EC_*.json

All trace events are recorded to logging/trace.jsonl. The verifier gate and file writing
run unconditionally in Python after tool routing completes.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_ECOM_MULTI_AGENT_ROOT = str(Path(__file__).resolve().parents[1])
if _ECOM_MULTI_AGENT_ROOT not in sys.path:
    sys.path.insert(0, _ECOM_MULTI_AGENT_ROOT)

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from agent import LLMOrchestrator  # noqa: E402
else:
    from .agent import LLMOrchestrator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "input"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output"
DEFAULT_TRACE_PATH = REPO_ROOT / "logging" / "trace.jsonl"


def _truncate(text: str, limit: int = 160) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 3] + "..."


class TraceLogger:
    """Collects trace events in memory and writes them as JSONL."""

    def __init__(self):
        self._events: list[dict] = []

    def log(
        self,
        case_id: str,
        agent_id: str,
        action: str,
        input_summary: str,
        output_summary: str,
        status: str,
        latency_ms: float,
    ) -> None:
        self._events.append(
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "case_id": case_id,
                "agent_id": agent_id,
                "action": action,
                "input_summary": _truncate(input_summary),
                "output_summary": _truncate(output_summary),
                "status": status,
                "latency_ms": round(latency_ms, 2),
            }
        )

    def add_events(self, events: list[dict]) -> None:
        for event in events:
            self._events.append(
                {
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "case_id": event["case_id"],
                    "agent_id": event["agent_id"],
                    "action": event["action"],
                    "input_summary": _truncate(event["input_summary"]),
                    "output_summary": _truncate(event["output_summary"]),
                    "status": event["status"],
                    "latency_ms": round(event.get("latency_ms", 0.0), 2),
                }
            )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for event in self._events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")


class Orchestrator:
    """Wrapper around LLMOrchestrator that handles running individual cases and all cases."""

    def __init__(self):
        self.llm_orchestrator = LLMOrchestrator()
        self.trace = TraceLogger()

    def run_case(self, case: dict) -> dict:
        assessment, trace_logs = self.llm_orchestrator.run_case(case)
        self.trace.add_events(trace_logs)
        return assessment

    def run_all(
        self,
        input_dir: Path = DEFAULT_INPUT_DIR,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        trace_path: Path = DEFAULT_TRACE_PATH,
    ) -> list[dict]:
        output_dir.mkdir(parents=True, exist_ok=True)
        summaries = []

        for input_path in sorted(input_dir.glob("EC_*.json")):
            with open(input_path, encoding="utf-8") as f:
                case = json.load(f)

            result = self.run_case(case)
            problems = result.pop("_verifier_problems", None)

            output_path = output_dir / input_path.name
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            summaries.append(
                {
                    "case_id": result["case_id"],
                    "primary_issue": result.get("case_assessment", {}).get("primary_issue"),
                    "error": result.get("error"),
                    "verifier_problems": problems,
                }
            )

        self.trace.write(trace_path)
        return summaries


if __name__ == "__main__":
    orchestrator = Orchestrator()
    run_summaries = orchestrator.run_all()

    n_errors = sum(1 for s in run_summaries if s["error"])
    n_flagged = sum(1 for s in run_summaries if s["verifier_problems"])
    print(f"Processed {len(run_summaries)} cases -> output/")
    print(f"  data errors: {n_errors}")
    print(f"  verifier-flagged: {n_flagged}")
    for s in run_summaries:
        if s["error"] or s["verifier_problems"]:
            print(f"  {s['case_id']}: error={s['error']} problems={s['verifier_problems']}")
