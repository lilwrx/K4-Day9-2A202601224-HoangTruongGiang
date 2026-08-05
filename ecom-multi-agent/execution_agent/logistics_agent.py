"""
logistics_agent: owns seller/carrier coordination actions — flagging a
seller's late handoff, flagging carrier/logistics delay, and coordinating a
case that spans multiple sellers. Reads delivery_analysis and root_cause
from the assessment rather than recomputing handoff variances itself.
"""

from __future__ import annotations

from .base import ExecutionResult


class LogisticsAgent:
    agent_id = "logistics_agent"
    handles = frozenset({"review_seller_handoff", "review_carrier_delay", "coordinate_multi_seller_case"})

    def execute(self, action: str, assessment: dict) -> ExecutionResult:
        order_id = assessment["affected_entities"]["order_ids"][0]
        delivery = assessment["delivery_analysis"]

        if action == "review_seller_handoff":
            late_ids = delivery["late_handoff_seller_ids"]
            detail = (
                f"Flagged {len(late_ids)} seller(s) for late handoff on order {order_id}: "
                f"{late_ids}."
            )
        elif action == "review_carrier_delay":
            detail = (
                f"Flagged carrier/logistics provider for order {order_id}: delivered "
                f"{delivery['delivery_variance_hours']}h after estimate with no late seller handoff."
            )
        elif action == "coordinate_multi_seller_case":
            seller_ids = assessment["affected_entities"]["seller_ids"]
            detail = f"Coordinated multi-seller case for order {order_id} across sellers {seller_ids}."
        else:
            return ExecutionResult(action, self.agent_id, "skipped", f"unhandled action {action!r}")

        return ExecutionResult(action, self.agent_id, "completed", detail)
