"""
LLMOrchestrator: The LLM-routed coordinator agent for ecom-multi-agent.
For each case, it dynamically routes calls between data_agent, policy_agent,
and execution_router using tool calling with state encapsulation.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI

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

load_dotenv()


class _CaseState:
    """Isolated per-case state container so tools read/write it directly
    and the LLM only sees lightweight summaries."""

    def __init__(self, case_id: str, claimed_order_id: str):
        self.case_id = case_id
        self.claimed_order_id = claimed_order_id
        self.bundle: dict | None = None
        self.assessment: dict | None = None
        self.execution_results: list = []
        self.found: bool = False
        self.trace_logs: list[dict] = []


class LLMOrchestrator:
    """LLM-routed Orchestrator Coordinator that sequences data retrieval, policy
    assessment, and resolution dispatch via tool calling."""

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.0):
        self.model_name = model_name
        self.data_agent = DataAgent()
        self.policy_agent = PolicyAgent(data_agent=self.data_agent)
        self.execution_router = ExecutionRouter()

        prompt_path = Path(__file__).parent / "system_prompt.md"
        with open(prompt_path, encoding="utf-8") as f:
            self.system_prompt = f.read()

        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    def run_case(self, case: dict) -> tuple[dict, list[dict]]:
        """Run one case through LLM routing and return (assessment_result, trace_events)."""
        case_id = case["case_id"]
        order_id = case["customer_request"]["claimed_order_id"]
        state = _CaseState(case_id, order_id)

        # Build tools bound to this case's state closure
        def fetch_order_data(claimed_order_id: str) -> dict:
            """Fetch order, items, payments, customer, products from database."""
            t0 = time.perf_counter()
            bundle = self.data_agent.investigate(claimed_order_id)
            state.bundle = bundle
            state.found = bool(bundle.get("found"))
            latency_ms = (time.perf_counter() - t0) * 1000

            state.trace_logs.append(
                {
                    "case_id": case_id,
                    "agent_id": "data_agent",
                    "action": "fetch_order_data",
                    "input_summary": f"order_id={claimed_order_id}",
                    "output_summary": f"found={state.found}",
                    "status": "ok" if state.found else "error",
                    "latency_ms": round(latency_ms, 2),
                }
            )

            if not state.found:
                return {"status": "not_found", "found": False, "order_id": claimed_order_id}
            return {
                "status": "ok",
                "found": True,
                "order_id": claimed_order_id,
                "order_status": bundle.get("order", {}).get("order_status"),
            }

        def run_policy_assessment() -> dict:
            """Assess EC_POLICY_V2 policy rules using modular policy sub-agents."""
            if not state.bundle or not state.found:
                return {"status": "error", "message": "No valid order bundle fetched yet"}

            t0 = time.perf_counter()
            assessment = self.policy_agent.assess_from_bundle(case_id, state.bundle)
            state.assessment = assessment
            latency_ms = (time.perf_counter() - t0) * 1000

            ca = assessment.get("case_assessment", {})
            state.trace_logs.append(
                {
                    "case_id": case_id,
                    "agent_id": "policy_agent",
                    "action": "run_policy_assessment",
                    "input_summary": f"order_id={order_id}",
                    "output_summary": f"primary_issue={ca.get('primary_issue')} case_status={ca.get('case_status')}",
                    "status": "ok",
                    "latency_ms": round(latency_ms, 2),
                }
            )

            return {
                "status": "ok",
                "primary_issue": ca.get("primary_issue"),
                "case_status": ca.get("case_status"),
                "resolution_actions": assessment.get("resolution_actions", []),
            }

        def dispatch_resolution_actions() -> dict:
            """Dispatch resolution actions to execution agents."""
            if not state.assessment:
                return {"status": "error", "message": "No policy assessment available"}

            t0 = time.perf_counter()
            results = self.execution_router.execute(state.assessment)
            state.execution_results = results
            latency_ms = (time.perf_counter() - t0) * 1000

            actions = state.assessment.get("resolution_actions", [])
            state.trace_logs.append(
                {
                    "case_id": case_id,
                    "agent_id": "execution_router",
                    "action": "dispatch_resolution_actions",
                    "input_summary": f"resolution_actions={actions}",
                    "output_summary": f"{len(results)} action(s) dispatched",
                    "status": "ok",
                    "latency_ms": round(latency_ms, 2),
                }
            )
            for res in results:
                state.trace_logs.append(
                    {
                        "case_id": case_id,
                        "agent_id": res.agent_id,
                        "action": res.action,
                        "input_summary": order_id,
                        "output_summary": res.detail,
                        "status": res.status,
                        "latency_ms": 0.0,
                    }
                )

            return {
                "status": "ok",
                "dispatched_count": len(results),
                "actions": actions,
            }

        tools = [
            StructuredTool.from_function(
                func=fetch_order_data,
                name="fetch_order_data",
                description="Fetch verified order data bundle from database for claimed_order_id.",
            ),
            StructuredTool.from_function(
                func=run_policy_assessment,
                name="run_policy_assessment",
                description="Run policy assessment over fetched data bundle using EC_POLICY_V2 policy sub-agents.",
            ),
            StructuredTool.from_function(
                func=dispatch_resolution_actions,
                name="dispatch_resolution_actions",
                description="Dispatch recommended resolution actions from policy assessment to execution agents.",
            ),
        ]

        # Invoke LLM Routing
        use_llm = bool(self.api_key)
        if use_llm:
            try:
                llm = ChatOpenAI(model=self.model_name, temperature=0.0)
                prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", self.system_prompt),
                        (
                            "human",
                            "Investigate case {case_id} for claimed order {order_id}.",
                        ),
                        MessagesPlaceholder(variable_name="agent_scratchpad"),
                    ]
                )
                agent = create_tool_calling_agent(llm, tools, prompt)
                executor = AgentExecutor(
                    agent=agent, tools=tools, verbose=False, max_iterations=5
                )
                executor.invoke({"case_id": case_id, "order_id": order_id})
            except Exception:
                use_llm = False

        # Fallback / Guarantee tool execution sequence if LLM skipped any tool
        if not state.bundle:
            fetch_order_data(order_id)

        if not state.found:
            return {
                "case_id": case_id,
                "error": f"claimed_order_id {order_id!r} not found",
            }, state.trace_logs

        if not state.assessment:
            run_policy_assessment()

        if not state.execution_results:
            dispatch_resolution_actions()

        assessment = state.assessment or {}

        # Verifier Hard Gate
        t0 = time.perf_counter()
        ok, problems = validate(assessment)
        latency_ms = (time.perf_counter() - t0) * 1000

        ca = assessment.get("case_assessment", {})
        state.trace_logs.append(
            {
                "case_id": case_id,
                "agent_id": "verifier",
                "action": "validate",
                "input_summary": f"primary_issue={ca.get('primary_issue')}",
                "output_summary": "ok" if ok else f"{len(problems)} problem(s): {problems}",
                "status": "ok" if ok else "error",
                "latency_ms": round(latency_ms, 2),
            }
        )

        if not ok:
            assessment["_verifier_problems"] = problems

        return assessment, state.trace_logs
