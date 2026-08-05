"""
Orchestrator: the routing agent. For each input/EC_*.json case it drives
the full handoff chain —

    data_agent -> policy_agent -> execution_agent (refund/payment/logistics)
    -> verifier -> output/EC_*.json

— and records every step to logging/trace.jsonl. It contains no business
logic of its own: data_agent owns "what happened", policy_agent owns "what
that means under EC_POLICY_V2", execution_agent owns "who acts on it", and
verifier owns "is this safe to write". The orchestrator only sequences
those calls and decides routing (which execution agent handles which
action — delegated to ExecutionRouter — and what to do when verification
fails).
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

_ECOM_MULTI_AGENT_ROOT = str(Path(__file__).resolve().parents[1])
if _ECOM_MULTI_AGENT_ROOT not in sys.path:
    sys.path.insert(0, _ECOM_MULTI_AGENT_ROOT)

from data_agent.agent import DataAgent  # noqa: E402
from execution_agent import ExecutionRouter  # noqa: E402
from policy_agent.agent import PolicyAgent  # noqa: E402

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from verifier import validate  # noqa: E402
else:
    from .verifier import validate

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "input"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output"
DEFAULT_TRACE_PATH = REPO_ROOT / "logging" / "trace.jsonl"


def _truncate(text: str, limit: int = 160) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 3] + "..."


class TraceLogger:
    """Collects trace events in memory and writes them as JSONL, one object
    per line, matching the {timestamp, agent_id, action, input_summary,
    output_summary, status, latency_ms} shape used elsewhere in this repo."""

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

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for event in self._events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")


class Orchestrator:
    def __init__(self):
        # One DataStore/DataAgent shared across every case and every
        # downstream agent, so the CSVs are only loaded once per run.
        self.data_agent = DataAgent()
        self.policy_agent = PolicyAgent(data_agent=self.data_agent)
        self.execution_router = ExecutionRouter()
        self.trace = TraceLogger()

    def run_case(self, case: dict) -> dict:
        case_id = case["case_id"]
        order_id = case["customer_request"]["claimed_order_id"]

        t0 = time.perf_counter()
        bundle = self.data_agent.investigate(order_id)
        self.trace.log(
            case_id,
            "data_agent",
            "fetch_order_bundle",
            f"order_id={order_id}",
            f"found={bundle.get('found')}",
            "ok" if bundle.get("found") else "error",
            (time.perf_counter() - t0) * 1000,
        )

        if not bundle.get("found"):
            result = {"case_id": case_id, "error": f"claimed_order_id {order_id!r} not found"}
            return result

        t0 = time.perf_counter()
        assessment = self.policy_agent.assess_from_bundle(case_id, bundle)
        ca = assessment["case_assessment"]
        self.trace.log(
            case_id,
            "policy_agent",
            "assess",
            f"order_id={order_id}",
            f"primary_issue={ca['primary_issue']} case_status={ca['case_status']}",
            "ok",
            (time.perf_counter() - t0) * 1000,
        )

        t0 = time.perf_counter()
        execution_results = self.execution_router.execute(assessment)
        self.trace.log(
            case_id,
            "execution_router",
            "route_actions",
            f"resolution_actions={assessment['resolution_actions']}",
            f"{len(execution_results)} action(s) dispatched",
            "ok",
            (time.perf_counter() - t0) * 1000,
        )
        for result in execution_results:
            self.trace.log(
                case_id, result.agent_id, result.action, order_id, result.detail, result.status, 0.0
            )

        t0 = time.perf_counter()
        ok, problems = validate(assessment)
        self.trace.log(
            case_id,
            "verifier",
            "validate",
            f"primary_issue={ca['primary_issue']}",
            "ok" if ok else f"{len(problems)} problem(s): {problems}",
            "ok" if ok else "error",
            (time.perf_counter() - t0) * 1000,
        )
        if not ok:
            assessment["_verifier_problems"] = problems

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
