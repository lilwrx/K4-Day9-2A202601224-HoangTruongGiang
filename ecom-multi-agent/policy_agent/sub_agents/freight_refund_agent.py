"""
FreightRefundPolicyAgent: Specialized policy agent for freight refund evaluations under EC_POLICY_V2.
Evaluates late delivery policies (late_delivery_seller, late_delivery_logistics).
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

SYSTEM_PROMPT = """You are the FreightRefundPolicyAgent in an e-commerce dispute resolution pipeline.
Your job is to assess if an order qualifies for a FREIGHT REFUND under EC_POLICY_V2 due to delivery delays.

Rules:
1. `late_delivery_seller`: Order delivered after estimated date AND at least one seller handed off after shipping limit date.
   - Primary issue: late_delivery_seller
   - Responsible party: seller(s) with late handoff
   - Action: refund_freight, review_seller_handoff
   - Refund: total freight BRL
   - Root cause: SELLER_HANDOFF_AFTER_LIMIT

2. `late_delivery_logistics`: Order delivered after estimated date AND NO seller was late in handoff.
   - Primary issue: late_delivery_logistics
   - Responsible party: logistics_provider (id: LOGISTICS_PROVIDER)
   - Action: refund_freight, review_carrier_delay
   - Refund: total freight BRL
   - Root cause: CARRIER_DELIVERED_AFTER_ESTIMATE

Analyze delivery variance hours and seller handoff variance hours to return the assessment.
"""


class FreightRefundPolicyAgent:
    """Specialized policy sub-agent for freight refund checks."""

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
                        "Delivery Variance Hours: {delivery_variance}\nLate Handoff Sellers: {late_sellers}\nIs applicable?",
                    ),
                ]
            )
        else:
            self.llm = None

    def evaluate(
        self,
        delivery_variance_hours: float | None,
        late_handoff_seller_ids: list[str],
        freight_total_brl: float,
    ) -> dict | None:
        """Evaluates if freight refund policy applies based on verified database delivery analysis."""
        if delivery_variance_hours is None or delivery_variance_hours <= 0:
            return None

        if len(late_handoff_seller_ids) > 0:
            primary_issue = "late_delivery_seller"
            root_cause = "SELLER_HANDOFF_AFTER_LIMIT"
            responsible = [
                {"party_type": "seller", "party_id": sid}
                for sid in late_handoff_seller_ids[:3]
            ]
            confidence = 0.90
        else:
            primary_issue = "late_delivery_logistics"
            root_cause = "CARRIER_DELIVERED_AFTER_ESTIMATE"
            responsible = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
            confidence = 0.85

        if self.llm:
            try:
                self.prompt.format(
                    delivery_variance=delivery_variance_hours,
                    late_sellers=late_handoff_seller_ids,
                )
            except Exception:
                pass

        return {
            "primary_issue": primary_issue,
            "confidence": confidence,
            "root_cause_code": root_cause,
            "responsible_parties": responsible,
            "recommended_refund_brl": freight_total_brl,
            "primary_action": "refund_freight",
        }
