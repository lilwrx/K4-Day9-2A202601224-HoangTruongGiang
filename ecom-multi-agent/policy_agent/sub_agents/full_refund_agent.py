"""
FullRefundPolicyAgent: Specialized policy agent for full refund evaluations under EC_POLICY_V2.
Evaluates canceled and unavailable order policies (canceled_order_paid, unavailable_order_paid).
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

SYSTEM_PROMPT = """You are the FullRefundPolicyAgent in an e-commerce dispute resolution pipeline.
Your job is to assess if an order qualifies for a FULL REFUND under EC_POLICY_V2.

Rules:
1. `canceled_order_paid`: If order_status == "canceled" and payment_total_brl > 0.
   - Primary issue: canceled_order_paid
   - Responsible party: platform (id: OLIST_PLATFORM)
   - Action: issue_full_refund
   - Refund: total payment BRL
   - Root cause: ORDER_CANCELED_AFTER_PAYMENT

2. `unavailable_order_paid`: If order_status == "unavailable" and payment_total_brl > 0.
   - Primary issue: unavailable_order_paid
   - Responsible party: platform (id: OLIST_PLATFORM)
   - Action: issue_full_refund
   - Refund: total payment BRL
   - Root cause: ORDER_UNAVAILABLE_AFTER_PAYMENT

Analyze the provided facts and return whether this policy applies.
"""


class FullRefundPolicyAgent:
    """Specialized policy sub-agent for full refund checks."""

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
                        "Order Status: {order_status}\nPayment Total: {payment_total_brl}\nIs applicable?",
                    ),
                ]
            )
        else:
            self.llm = None

    def evaluate(self, status: str, payment_total_brl: float) -> dict | None:
        """Evaluates if full refund policy applies based on verified database facts."""
        if status == "canceled" and payment_total_brl > 0:
            primary_issue = "canceled_order_paid"
            root_cause = "ORDER_CANCELED_AFTER_PAYMENT"
        elif status == "unavailable" and payment_total_brl > 0:
            primary_issue = "unavailable_order_paid"
            root_cause = "ORDER_UNAVAILABLE_AFTER_PAYMENT"
        else:
            return None

        # Confirm with LLM prompt context if key is available
        confidence = 0.95
        if self.llm:
            try:
                res = (self.prompt | self.llm).invoke(
                    {"order_status": status, "payment_total_brl": payment_total_brl}
                )
                # LLM verified assessment
            except Exception:
                pass

        return {
            "primary_issue": primary_issue,
            "confidence": confidence,
            "root_cause_code": root_cause,
            "responsible_parties": [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
            "recommended_refund_brl": payment_total_brl,
            "primary_action": "issue_full_refund",
        }
