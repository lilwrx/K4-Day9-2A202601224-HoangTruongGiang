"""
ExecutionRouter: the thing the orchestrator/routing agent hands a case
assessment to. It never decides *what* to do — policy_agent already fixed
resolution_actions — it only decides *who* does each action, dispatching by
a static action -> agent table built from each agent's own `handles` set.

Kept separate from orchestrator/ so the execution layer can be tested and
reasoned about on its own: given an assessment, what actions ran, on which
agent, with what result.
"""

from __future__ import annotations

from .base import ExecutionResult
from .logistics_agent import LogisticsAgent
from .payment_agent import PaymentAgent
from .refund_agent import RefundAgent


class ExecutionRouter:
    def __init__(self):
        self._agents = [RefundAgent(), PaymentAgent(), LogisticsAgent()]
        self._action_to_agent = {}
        for agent in self._agents:
            for action in agent.handles:
                if action in self._action_to_agent:
                    raise ValueError(
                        f"action {action!r} claimed by both "
                        f"{self._action_to_agent[action].agent_id} and {agent.agent_id}"
                    )
                self._action_to_agent[action] = agent

    def route(self, action: str):
        """Which agent instance owns this action, or None if unregistered."""
        return self._action_to_agent.get(action)

    def execute(self, assessment: dict) -> list[ExecutionResult]:
        """Run every resolution_actions entry from a policy_agent assessment,
        in order, and return one ExecutionResult per action."""
        results = []
        for action in assessment["resolution_actions"]:
            agent = self.route(action)
            if agent is None:
                results.append(
                    ExecutionResult(action, "execution_router", "skipped", f"no agent registered for {action!r}")
                )
                continue
            results.append(agent.execute(action, assessment))
        return results
