"""Coordinator Agent: nhan case, giao viec cho cac agent chuyen mon,
tong hop handoff va ghi output sau khi Verifier thong qua.

Luong handoff:
    case input
      -> customer_agent      --\
      -> order_product_agent  --+--> CaseFacts --> policy_agent (LLM <=10B)
      -> payment_agent       --/                        |
      -> delivery_agent      --/                        v
                                              assembly -> verifier_agent -> output
"""

import json

from .agents import (
    customer_agent,
    delivery_agent,
    order_product_agent,
    payment_agent,
    policy_agent,
    verifier_agent,
)
from .config import LIMITS
from .trace import Timer


def _truncate(obj, limit=600):
    """Rut gon payload truoc khi ghi trace de file khong phinh to."""
    text = json.dumps(obj, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def gather_facts(store, case: dict, tracer=None) -> dict:
    """Chay 4 agent phan tich song song ve mat logic, moi agent mot domain."""
    case_id = case["case_id"]
    order_id = case["customer_request"]["claimed_order_id"]

    facts = {"case_id": case_id, "order_id": order_id}

    for agent_module, key in (
        (customer_agent, "customer_context"),
        (order_product_agent, "order_context"),
        (payment_agent, "payment_reconciliation"),
        (delivery_agent, "delivery_analysis"),
    ):
        with Timer() as timer:
            result = agent_module.analyze(store, order_id)
        facts[key] = result
        if tracer:
            tracer.emit(
                case_id,
                agent_module.AGENT_NAME,
                "handoff",
                {
                    "input": {"order_id": order_id},
                    "output": result,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
    return facts


def build_evidence_ids(store, facts: dict, root_cause: str, parties: list) -> list[str]:
    """Chi dung evidence tu du lieu that, theo thu tu: order, item, payment,
    seller chiu trach nhiem, policy.

    Cac array item/payment/seller dung dung gioi han nhu affected_entities,
    nen tong evidence luon <= 1 + 5 + 5 + 3 + 1 = 15 < 20.
    """
    order_id = facts["order_id"]
    evidence = [f"order:{order_id}"]
    evidence += [f"item:{iid}" for iid in facts["order_context"]["item_ids"]]
    evidence += [f"payment:{pid}" for pid in facts["payment_reconciliation"]["payment_ids"]]

    for party in parties:
        if party["party_type"] == "seller" and store.has_seller(party["party_id"]):
            evidence.append(f"seller:{party['party_id']}")

    evidence.append(f"policy:{root_cause}")
    return evidence[: LIMITS["evidence_ids"]]


def assemble_output(store, facts: dict, assessment: dict) -> dict:
    """Dung payload dung output schema tu su kien + ket luan policy."""
    order_id = facts["order_id"]
    order_ctx = facts["order_context"]
    payment_ctx = facts["payment_reconciliation"]
    delivery_ctx = facts["delivery_analysis"]
    customer_ctx = facts["customer_context"]

    parties = assessment["responsible_parties"][: LIMITS["responsible_parties"]]
    evidence = build_evidence_ids(store, facts, assessment["root_cause_code"], parties)

    return {
        "case_id": facts["case_id"],
        "case_assessment": {
            "primary_issue": assessment["primary_issue"],
            "secondary_issues": assessment["secondary_issues"],
            "case_status": assessment["case_status"],
            "confidence": assessment["confidence"],
        },
        "affected_entities": {
            # Order lich su KHONG duoc vao day, chi vao customer_context.
            "order_ids": [order_id],
            "item_ids": order_ctx["item_ids"],
            "seller_ids": order_ctx["seller_ids"],
            "payment_ids": payment_ctx["payment_ids"],
        },
        "customer_context": {
            "customer_unique_id": customer_ctx["customer_unique_id"],
            "related_order_ids": customer_ctx["related_order_ids"],
        },
        "product_context": {
            "product_ids": order_ctx["product_ids"],
            "category_names": order_ctx["category_names"],
        },
        "delivery_analysis": {
            "delivered_at": delivery_ctx["delivered_at"],
            "estimated_delivery_at": delivery_ctx["estimated_delivery_at"],
            "carrier_handoff_at": delivery_ctx["carrier_handoff_at"],
            "delivery_variance_hours": delivery_ctx["delivery_variance_hours"],
            "seller_handoff_analysis": delivery_ctx["seller_handoff_analysis"],
            "late_handoff_seller_ids": delivery_ctx["late_handoff_seller_ids"],
        },
        "payment_reconciliation": {
            "currency": payment_ctx["currency"],
            "item_total_brl": payment_ctx["item_total_brl"],
            "freight_total_brl": payment_ctx["freight_total_brl"],
            "expected_total_brl": payment_ctx["expected_total_brl"],
            "payment_total_brl": payment_ctx["payment_total_brl"],
            "difference_brl": payment_ctx["difference_brl"],
            "reconciled": payment_ctx["reconciled"],
            "payment_types": payment_ctx["payment_types"],
        },
        "root_cause_analysis": {
            "ranked_causes": [
                {"cause_code": assessment["root_cause_code"], "rank": 1}
            ],
            "responsible_parties": parties,
        },
        "evidence_ids": evidence,
        "financial_resolution": {
            "currency": payment_ctx["currency"],
            "recommended_refund_brl": assessment["recommended_refund_brl"],
        },
        "resolution_actions": assessment["resolution_actions"],
    }


def process_case(store, case: dict, tracer=None, use_llm: bool = True) -> tuple[dict, list[str]]:
    """Xu ly tron mot case. Tra (output payload, danh sach van de tu Verifier)."""
    case_id = case["case_id"]
    order_id = case["customer_request"]["claimed_order_id"]

    if tracer:
        tracer.emit(
            case_id,
            "coordinator",
            "dispatch",
            {"order_id": order_id, "policy_version": case.get("policy_version")},
        )

    facts = gather_facts(store, case, tracer)

    with Timer() as timer:
        assessment, policy_meta = policy_agent.analyze(facts, use_llm=use_llm)
    if tracer:
        tracer.emit(
            case_id,
            policy_agent.AGENT_NAME,
            "handoff",
            {
                "input": {"facts_keys": sorted(facts.keys())},
                "output": assessment,
                "meta": policy_meta,
                "elapsed_ms": timer.elapsed_ms,
            },
        )

    payload = assemble_output(store, facts, assessment)

    with Timer() as timer:
        issues = verifier_agent.verify(payload, store, order_id)
    if tracer:
        tracer.emit(
            case_id,
            verifier_agent.AGENT_NAME,
            "verdict",
            {
                "passed": not issues,
                "issues": issues,
                "evidence_count": len(payload["evidence_ids"]),
                "elapsed_ms": timer.elapsed_ms,
            },
        )

    return payload, issues
