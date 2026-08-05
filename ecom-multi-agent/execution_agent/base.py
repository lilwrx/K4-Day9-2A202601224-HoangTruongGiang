"""
Shared contract for execution agents. Each execution agent "performs" a
subset of resolution_actions — in this dataset that means producing an
auditable confirmation record, not calling a real payment API: Olist has
no refund ledger or transaction ID to write to (README section 2), so
there is nothing to actually mutate. What matters for the assignment is
that responsibility for each action type lives in its own agent instead of
one function with a giant if/elif over every action name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExecutionResult:
    action: str
    agent_id: str
    status: str  # "completed" | "skipped"
    detail: str

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "agent_id": self.agent_id,
            "status": self.status,
            "detail": self.detail,
        }


class ExecutionAgent(Protocol):
    agent_id: str
    handles: frozenset[str]

    def execute(self, action: str, assessment: dict) -> ExecutionResult: ...
