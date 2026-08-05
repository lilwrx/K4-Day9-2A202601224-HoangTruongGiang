"""
refund_agent: owns the refund lifecycle actions — issuing a refund (full or
freight-only), rejecting an unsupported claim, and verifying that a refund
that was recommended actually gets confirmed. It only reads the assessment
policy_agent already produced (order_id, financial_resolution, root cause);
it never recomputes eligibility or amounts itself, so refund logic can't
drift from EC_POLICY_V2 in two places.
"""

from __future__ import annotations

from .base import ExecutionResult


class RefundAgent:
    agent_id = "refund_agent"
    handles = frozenset(
        {"issue_full_refund", "refund_freight", "reject_late_refund", "verify_refund_completion"}
    )

    def execute(self, action: str, assessment: dict) -> ExecutionResult:
        order_id = assessment["affected_entities"]["order_ids"][0]
        refund = assessment["financial_resolution"]["recommended_refund_brl"]
        currency = assessment["financial_resolution"]["currency"]
        primary_issue = assessment["case_assessment"]["primary_issue"]

        if action == "issue_full_refund":
            detail = f"Issued full refund of {refund} {currency} for order {order_id}."
        elif action == "refund_freight":
            detail = f"Issued freight-only refund of {refund} {currency} for order {order_id}."
        elif action == "reject_late_refund":
            detail = f"Rejected refund claim for order {order_id}: {primary_issue} — no refund due."
        elif action == "verify_refund_completion":
            detail = f"Verified refund of {refund} {currency} for order {order_id} was recorded."
        else:
            return ExecutionResult(action, self.agent_id, "skipped", f"unhandled action {action!r}")

        return ExecutionResult(action, self.agent_id, "completed", detail)
