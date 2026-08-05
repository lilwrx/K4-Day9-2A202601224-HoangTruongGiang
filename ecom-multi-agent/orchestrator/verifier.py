"""
Deterministic pre-write gate on a policy_agent assessment: array-length
caps, evidence ID formats, confidence range, and internal consistency
(case_status matches whether a refund was recommended). Doesn't touch
data/ or re-derive the decision — it only checks the shape and internal
consistency of what policy_agent already returned.

The assignment hard-gates (0 points) any case with a broken schema or
fabricated evidence, so this runs before the orchestrator writes output/,
not after.
"""

from __future__ import annotations

import re

VALID_PRIMARY_ISSUES = {
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
}

VALID_SECONDARY_ISSUES = {
    "multi_item_order",
    "multi_seller_order",
    "split_payment",
    "repeat_customer",
    "multiple_categories",
}

EVIDENCE_PATTERNS = [
    re.compile(r"^order:[^:]+$"),
    re.compile(r"^item:[^:]+:[^:]+$"),
    re.compile(r"^payment:[^:]+:[^:]+$"),
    re.compile(r"^seller:[^:]+$"),
    re.compile(r"^policy:[A-Z_]+$"),
]

LIMITS = {
    ("affected_entities", "order_ids"): 5,
    ("affected_entities", "item_ids"): 5,
    ("affected_entities", "seller_ids"): 3,
    ("affected_entities", "payment_ids"): 5,
    ("customer_context", "related_order_ids"): 5,
    ("product_context", "product_ids"): 5,
    ("product_context", "category_names"): 5,
    ("root_cause_analysis", "ranked_causes"): 3,
    ("root_cause_analysis", "responsible_parties"): 3,
    (None, "evidence_ids"): 20,
    (None, "resolution_actions"): 5,
}

REQUIRED_TOP_LEVEL_KEYS = {
    "case_id",
    "case_assessment",
    "affected_entities",
    "customer_context",
    "product_context",
    "delivery_analysis",
    "payment_reconciliation",
    "root_cause_analysis",
    "evidence_ids",
    "financial_resolution",
    "resolution_actions",
}


def _is_valid_evidence_id(evidence_id: str) -> bool:
    return any(p.match(evidence_id) for p in EVIDENCE_PATTERNS)


def validate(assessment: dict) -> tuple[bool, list[str]]:
    """Returns (ok, problems). problems is empty iff ok is True."""
    problems: list[str] = []

    missing = REQUIRED_TOP_LEVEL_KEYS - assessment.keys()
    if missing:
        problems.append(f"missing top-level keys: {sorted(missing)}")
        return False, problems  # nothing else is safe to inspect

    ca = assessment["case_assessment"]
    if ca["primary_issue"] not in VALID_PRIMARY_ISSUES:
        problems.append(f"unknown primary_issue {ca['primary_issue']!r}")
    bad_secondary = set(ca["secondary_issues"]) - VALID_SECONDARY_ISSUES
    if bad_secondary:
        problems.append(f"unknown secondary_issues {sorted(bad_secondary)}")
    if ca["case_status"] not in ("action_required", "no_action"):
        problems.append(f"invalid case_status {ca['case_status']!r}")
    if not (0 <= ca["confidence"] <= 1):
        problems.append(f"confidence {ca['confidence']} out of [0, 1]")

    refund = assessment["financial_resolution"]["recommended_refund_brl"]
    if refund < 0:
        problems.append(f"recommended_refund_brl is negative: {refund}")
    expect_action_required = refund > 0
    is_action_required = ca["case_status"] == "action_required"
    if expect_action_required != is_action_required:
        problems.append(
            f"case_status={ca['case_status']!r} inconsistent with recommended_refund_brl={refund}"
        )

    for (section, field), limit in LIMITS.items():
        value = assessment[section][field] if section else assessment[field]
        if len(value) > limit:
            path = f"{section}.{field}" if section else field
            problems.append(f"{path} has {len(value)} entries, limit is {limit}")

    for evidence_id in assessment["evidence_ids"]:
        if not _is_valid_evidence_id(evidence_id):
            problems.append(f"malformed evidence_id {evidence_id!r}")

    if len(assessment["evidence_ids"]) != len(set(assessment["evidence_ids"])):
        problems.append("evidence_ids contains duplicates")

    return len(problems) == 0, problems
