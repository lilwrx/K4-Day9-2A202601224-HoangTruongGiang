"""
policy_agent: applies EC_POLICY_V2 (see EC_POLICY_V2.md) to one case and
hands the assessment back to the orchestrator/routing agent.

policy_agent never reads data/ itself — it only calls DataAgent.investigate()
for the case's claimed_order_id and reasons over whatever comes back. That
keeps a single source of truth for what "the data says": if data_agent's
join logic changes, policy_agent doesn't need to.

It also never performs the resolution_actions it recommends (no refund
issuance, no writing to output/). It returns a decision; a downstream
execution agent (routed to by the orchestrator) is the one that acts on it.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ecom-multi-agent/ is the shared import root: every agent package
# (data_agent, policy_agent, orchestrator, ...) lives directly under it and
# imports its siblings as top-level packages, e.g. `from data_agent.agent
# import DataAgent`. Since "ecom-multi-agent" itself has a hyphen, it can't
# be a dotted Python package name, so this sys.path entry is how sibling
# agents find each other rather than relative imports.
_ECOM_MULTI_AGENT_ROOT = str(Path(__file__).resolve().parents[1])
if _ECOM_MULTI_AGENT_ROOT not in sys.path:
    sys.path.insert(0, _ECOM_MULTI_AGENT_ROOT)

from data_agent.agent import DataAgent  # noqa: E402

if __package__ in (None, ""):
    # Allows `python agent.py` to work directly, not just `python -m policy_agent.agent`.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from rules import apply_policy  # noqa: E402
else:
    from .rules import apply_policy


class PolicyAgent:
    """Turns one case input into a case assessment, using data_agent for
    every fact and EC_POLICY_V2 for every decision. Read-only: makes no
    changes to order/payment/refund state."""

    def __init__(self, data_agent: DataAgent | None = None):
        # Accepts an existing DataAgent so the orchestrator can share one
        # warm DataStore across every agent in a run instead of each agent
        # re-loading the CSVs.
        self.data_agent = data_agent or DataAgent()

    def assess(self, case: dict) -> dict:
        """case is one parsed input/EC_*.json document. Returns a dict with
        case_id plus every field from README section 6 except the parts an
        execution agent would produce (nothing here is written or acted on)."""
        case_id = case["case_id"]
        order_id = case["customer_request"]["claimed_order_id"]
        bundle = self.data_agent.investigate(order_id)
        return self.assess_from_bundle(case_id, bundle)

    def assess_from_bundle(self, case_id: str, bundle: dict) -> dict:
        """Same as assess(), but for callers (e.g. the orchestrator) that
        already fetched the bundle themselves and want to log that as its
        own data_agent step instead of a hidden call inside assess()."""
        order_id = bundle["order_id"]
        if not bundle.get("found"):
            return {
                "case_id": case_id,
                "error": f"claimed_order_id {order_id!r} not found in orders data",
            }
        assessment = apply_policy(bundle)
        return {"case_id": case_id, **assessment}


if __name__ == "__main__":
    import json

    if len(sys.argv) < 2:
        print("Usage: python agent.py <path/to/input/EC_XXX.json>")
        raise SystemExit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        case_input = json.load(f)

    agent = PolicyAgent()
    result = agent.assess(case_input)
    print(json.dumps(result, indent=2, ensure_ascii=False))
