"""
SplitPaymentPolicyAgent: Specialized policy agent for valid split payment evaluations under EC_POLICY_V2.
Evaluates valid_split_payment policy.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

SYSTEM_PROMPT = """You are the SplitPaymentPolicyAgent in an e-commerce dispute resolution pipeline.
Your job is to assess if an order represents a VALID SPLIT PAYMENT claim under EC_POLICY_V2.

Rules:
`valid_split_payment`: Order has >= 2 payment rows AND payment total matches expected item + freight within 0.10 BRL tolerance.
- Primary issue: valid_split_payment
- Responsible party: None
- Action: explain_valid_split_payment
- Refund: 0.0
- Root cause: MULTIPLE_PAYMENTS_RECONCILED
"""


class SplitPaymentPolicyAgent:
    """Specialized policy sub-agent for valid split payment checks."""

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
                        "Payment Row Count: {payment_count}\nReconciled: {reconciled}\nIs applicable?",
                    ),
                ]
            )
        else:
            self.llm = None

    def evaluate(self, num_payments: int, reconciled: bool | None) -> dict | None:
        """Evaluates if valid_split_payment policy applies based on verified payment reconciliation."""
        if num_payments >= 2 and reconciled:
            return {
                "primary_issue": "valid_split_payment",
                "confidence": 0.90,
                "root_cause_code": "MULTIPLE_PAYMENTS_RECONCILED",
                "responsible_parties": [],
                "recommended_refund_brl": 0.0,
                "primary_action": "explain_valid_split_payment",
            }
        return None
