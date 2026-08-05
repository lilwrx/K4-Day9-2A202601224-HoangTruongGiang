"""
payment_agent: owns payment-reconciliation communication actions — explaining
a valid split payment back to the customer, and verifying that a multi-row
payment allocation sums correctly. Reads payment_reconciliation from the
assessment rather than re-summing order_payments itself.
"""

from __future__ import annotations

from .base import ExecutionResult


class PaymentAgent:
    agent_id = "payment_agent"
    handles = frozenset({"explain_valid_split_payment", "verify_payment_allocation"})

    def execute(self, action: str, assessment: dict) -> ExecutionResult:
        order_id = assessment["affected_entities"]["order_ids"][0]
        recon = assessment["payment_reconciliation"]
        n_payments = len(assessment["affected_entities"]["payment_ids"])

        if action == "explain_valid_split_payment":
            detail = (
                f"Explained split payment for order {order_id}: {n_payments} payment rows "
                f"totaling {recon['payment_total_brl']} {recon['currency']} against expected "
                f"{recon['expected_total_brl']} {recon['currency']} (diff {recon['difference_brl']})."
            )
        elif action == "verify_payment_allocation":
            detail = (
                f"Verified payment allocation for order {order_id}: {n_payments} payment rows, "
                f"reconciled={recon['reconciled']}."
            )
        else:
            return ExecutionResult(action, self.agent_id, "skipped", f"unhandled action {action!r}")

        return ExecutionResult(action, self.agent_id, "completed", detail)
