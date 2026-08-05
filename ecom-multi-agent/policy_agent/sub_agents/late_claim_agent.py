"""
LateClaimPolicyAgent: Specialized policy agent for unsupported late claim evaluations under EC_POLICY_V2.
Evaluates unsupported_late_claim policy.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

SYSTEM_PROMPT = """You are the LateClaimPolicyAgent in an e-commerce dispute resolution pipeline.
Your job is to assess if an order claim is UNSUPPORTED because delivery was within estimate under EC_POLICY_V2.

Rules:
`unsupported_late_claim`: Order delivered within estimated date (not late) and payment reconciled.
- Primary issue: unsupported_late_claim
- Responsible party: None
- Action: reject_late_refund
- Refund: 0.0
- Root cause: DELIVERY_WITHIN_ESTIMATE
"""


class LateClaimPolicyAgent:
    """Specialized policy sub-agent for unsupported late claim checks."""

    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.model_name = model_name
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = ChatOpenAI(model=model_name, temperature=0.0)
            self.prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", SYSTEM_PROMPT),
                    (
                        "human",
                        "Delivery Variance Hours: {delivery_variance}\nReconciled: {reconciled}\nIs applicable?",
                    ),
                ]
            )
        else:
            self.llm = None

    def evaluate(self, delivery_variance_hours: float | None, reconciled: bool | None) -> dict | None:
        """Evaluates if unsupported_late_claim policy applies based on verified delivery dates."""
        delivered_late = bool(
            delivery_variance_hours is not None and delivery_variance_hours > 0
        )
        if not delivered_late and (reconciled or reconciled is None):
            return {
                "primary_issue": "unsupported_late_claim",
                "confidence": 0.90,
                "root_cause_code": "DELIVERY_WITHIN_ESTIMATE",
                "responsible_parties": [],
                "recommended_refund_brl": 0.0,
                "primary_action": "reject_late_refund",
            }
        return None
