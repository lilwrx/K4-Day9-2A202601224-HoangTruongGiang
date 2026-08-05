"""
Pure, deterministic implementation of EC_POLICY_V2 (see EC_POLICY_V2.md).

Takes the data bundle data_agent.DataAgent.investigate() returns and turns
it into the case assessment shape the orchestrator writes to output/. No
LLM involved: refund amounts, hour variances, and rule matches all have to
be exactly reproducible, which is not something worth risking on a model.

This module only *decides* what should happen (primary/secondary issue,
responsible party, recommended refund, suggested actions). It never writes
files or calls anything that mutates state — that is the execution agent's
job once the orchestrator routes the decision to it.
"""

from __future__ import annotations

from datetime import datetime

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
RECONCILIATION_TOLERANCE_BRL = 0.10

# --- limits from README section 6 -----------------------------------------

MAX_ORDER_IDS = 5
MAX_ITEM_IDS = 5
MAX_SELLER_IDS = 3
MAX_PAYMENT_IDS = 5
MAX_RELATED_ORDER_IDS = 5
MAX_PRODUCT_IDS = 5
MAX_CATEGORY_NAMES = 5
MAX_ROOT_CAUSES = 3
MAX_RESPONSIBLE_PARTIES = 3
MAX_EVIDENCE_IDS = 20
MAX_ACTIONS = 5

ROOT_CAUSE_BY_ISSUE = {
    "canceled_order_paid": "ORDER_CANCELED_AFTER_PAYMENT",
    "unavailable_order_paid": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
    "late_delivery_seller": "SELLER_HANDOFF_AFTER_LIMIT",
    "late_delivery_logistics": "CARRIER_DELIVERED_AFTER_ESTIMATE",
    "valid_split_payment": "MULTIPLE_PAYMENTS_RECONCILED",
    "unsupported_late_claim": "DELIVERY_WITHIN_ESTIMATE",
}

PRIMARY_ACTION_BY_ISSUE = {
    "canceled_order_paid": "issue_full_refund",
    "unavailable_order_paid": "issue_full_refund",
    "late_delivery_seller": "refund_freight",
    "late_delivery_logistics": "refund_freight",
    "valid_split_payment": "explain_valid_split_payment",
    "unsupported_late_claim": "reject_late_refund",
}

REFUND_ISSUING_ISSUES = {
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
}


def _parse_dt(value) -> datetime | None:
    if not value or (isinstance(value, float) and value != value):  # NaN
        return None
    try:
        return datetime.strptime(str(value), TIMESTAMP_FORMAT)
    except ValueError:
        return None


def _round2(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _hours_between(later, earlier) -> float | None:
    a, b = _parse_dt(later), _parse_dt(earlier)
    if a is None or b is None:
        return None
    return _round2((a - b).total_seconds() / 3600)


def _dedupe(seq) -> list:
    return list(dict.fromkeys(x for x in seq if x is not None))


# --- payment reconciliation --------------------------------------------------


def compute_payment_reconciliation(bundle: dict) -> dict:
    items = bundle["items"]
    payments = bundle["payments"]

    item_total = round(sum(float(it["price"]) for it in items), 2)
    freight_total = round(sum(float(it["freight_value"]) for it in items), 2)
    payment_total = round(sum(float(p["payment_value"]) for p in payments), 2)

    if items:
        expected_total = round(item_total + freight_total, 2)
        difference = round(payment_total - expected_total, 2)
        reconciled = abs(difference) <= RECONCILIATION_TOLERANCE_BRL
    else:
        expected_total = None
        difference = None
        reconciled = None

    return {
        "currency": "BRL",
        "item_total_brl": item_total,
        "freight_total_brl": freight_total,
        "expected_total_brl": expected_total,
        "payment_total_brl": payment_total,
        "difference_brl": difference,
        "reconciled": reconciled,
        "payment_types": _dedupe(p["payment_type"] for p in payments),
    }


# --- delivery analysis --------------------------------------------------------


def compute_delivery_analysis(bundle: dict) -> dict:
    order = bundle["order"]
    items = bundle["items"]

    delivered_at = order.get("order_delivered_customer_date")
    estimated_at = order.get("order_estimated_delivery_date")
    carrier_handoff_at = order.get("order_delivered_carrier_date")

    delivery_variance_hours = _hours_between(delivered_at, estimated_at)

    seller_shipping_limit: dict[str, str] = {}
    for it in items:
        seller_id = it["seller_id"]
        limit = it["shipping_limit_date"]
        current = seller_shipping_limit.get(seller_id)
        if current is None or (_parse_dt(limit) or datetime.max) < (_parse_dt(current) or datetime.max):
            seller_shipping_limit[seller_id] = limit

    seller_handoff_analysis = []
    late_handoff_seller_ids = []
    for seller_id, shipping_limit_at in seller_shipping_limit.items():
        variance = _hours_between(carrier_handoff_at, shipping_limit_at)
        late = bool(variance is not None and variance > 0)
        seller_handoff_analysis.append(
            {
                "seller_id": seller_id,
                "shipping_limit_at": shipping_limit_at,
                "handoff_variance_hours": variance,
                "late_handoff": late,
            }
        )
        if late:
            late_handoff_seller_ids.append(seller_id)

    return {
        "delivered_at": delivered_at,
        "estimated_delivery_at": estimated_at,
        "carrier_handoff_at": carrier_handoff_at,
        "delivery_variance_hours": delivery_variance_hours,
        "seller_handoff_analysis": seller_handoff_analysis,
        "late_handoff_seller_ids": late_handoff_seller_ids,
    }


# --- primary issue classification --------------------------------------------


def classify_primary_issue(bundle: dict, delivery: dict, payment: dict) -> tuple[str, float]:
    """Returns (primary_issue, confidence). Rules are tried in the exact
    priority order from EC_POLICY_V2.md; the first match wins."""
    order = bundle["order"]
    status = order.get("order_status")
    payment_total = payment["payment_total_brl"]

    delivered_late = bool(
        delivery["delivery_variance_hours"] is not None and delivery["delivery_variance_hours"] > 0
    )
    any_seller_late = len(delivery["late_handoff_seller_ids"]) > 0

    if status == "canceled" and payment_total > 0:
        return "canceled_order_paid", 0.95
    if status == "unavailable" and payment_total > 0:
        return "unavailable_order_paid", 0.95
    if delivered_late and any_seller_late:
        return "late_delivery_seller", 0.9
    if delivered_late and not any_seller_late:
        return "late_delivery_logistics", 0.85
    if len(bundle["payments"]) >= 2 and payment["reconciled"]:
        return "valid_split_payment", 0.9
    if not delivered_late and payment["reconciled"]:
        return "unsupported_late_claim", 0.9

    # Data doesn't cleanly satisfy any rule (e.g. no item rows and the
    # order isn't canceled/unavailable/late) — default to the "no
    # actionable claim" bucket rather than fabricate a refund, but flag it
    # with reduced confidence since no rule condition was actually met.
    return "unsupported_late_claim", 0.4


# --- secondary issues ----------------------------------------------------------


def classify_secondary_issues(bundle: dict) -> list[str]:
    items = bundle["items"]
    payments = bundle["payments"]
    products = bundle["products"]

    secondary = []
    if len(items) >= 2:
        secondary.append("multi_item_order")
    if len({it["seller_id"] for it in items}) >= 2:
        secondary.append("multi_seller_order")
    if len(payments) >= 2:
        secondary.append("split_payment")
    if bundle["related_order_ids"]:
        secondary.append("repeat_customer")
    if len({p["product_category_name"] for p in products if p.get("product_category_name")}) >= 2:
        secondary.append("multiple_categories")
    return secondary


# --- root cause + responsibility -----------------------------------------------


def compute_root_cause_analysis(primary_issue: str, delivery: dict) -> dict:
    root_cause_code = ROOT_CAUSE_BY_ISSUE[primary_issue]
    ranked_causes = [{"cause_code": root_cause_code, "rank": 1}][:MAX_ROOT_CAUSES]

    if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
        responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
    elif primary_issue == "late_delivery_seller":
        responsible_parties = [
            {"party_type": "seller", "party_id": sid}
            for sid in delivery["late_handoff_seller_ids"][:MAX_RESPONSIBLE_PARTIES]
        ]
    elif primary_issue == "late_delivery_logistics":
        responsible_parties = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
    else:
        responsible_parties = []

    return {
        "ranked_causes": ranked_causes,
        "responsible_parties": responsible_parties[:MAX_RESPONSIBLE_PARTIES],
    }


# --- financial resolution + actions --------------------------------------------


def compute_financial_resolution(primary_issue: str, payment: dict) -> dict:
    if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
        refund = payment["payment_total_brl"]
    elif primary_issue in ("late_delivery_seller", "late_delivery_logistics"):
        refund = payment["freight_total_brl"]
    else:
        refund = 0.0
    return {"currency": "BRL", "recommended_refund_brl": _round2(refund)}


def compute_resolution_actions(primary_issue: str, secondary_issues: list[str]) -> list[str]:
    actions = [PRIMARY_ACTION_BY_ISSUE[primary_issue]]

    if primary_issue == "late_delivery_seller":
        actions.append("review_seller_handoff")
    elif primary_issue == "late_delivery_logistics":
        actions.append("review_carrier_delay")

    if primary_issue in REFUND_ISSUING_ISSUES:
        actions.append("verify_refund_completion")

    if "multi_seller_order" in secondary_issues:
        actions.append("coordinate_multi_seller_case")

    if "split_payment" in secondary_issues and primary_issue != "valid_split_payment":
        actions.append("verify_payment_allocation")

    return actions[:MAX_ACTIONS]


# --- evidence ids ---------------------------------------------------------------


def compute_evidence_ids(
    bundle: dict,
    item_ids: list[str],
    payment_ids: list[str],
    responsible_parties: list[dict],
    root_causes: list[dict],
) -> list[str]:
    order_id = bundle["order_id"]
    evidence = [f"order:{order_id}"]
    evidence += [f"item:{eid}" for eid in item_ids]
    evidence += [f"payment:{eid}" for eid in payment_ids]
    evidence += [
        f"seller:{p['party_id']}" for p in responsible_parties if p["party_type"] == "seller"
    ]
    evidence += [f"policy:{c['cause_code']}" for c in root_causes]
    return _dedupe(evidence)[:MAX_EVIDENCE_IDS]


# --- top-level entry point ------------------------------------------------------


def apply_policy(bundle: dict) -> dict:
    """bundle is DataAgent.investigate(order_id)'s return value. Returns the
    full case assessment (everything in README section 6 except case_id,
    which the orchestrator already has from the input file)."""
    order_id = bundle["order_id"]

    if not bundle["found"]:
        raise ValueError(f"order_id {order_id!r} not found in data/ — cannot apply policy")

    items = bundle["items"]
    payments = bundle["payments"]
    products = bundle["products"]

    delivery = compute_delivery_analysis(bundle)
    payment = compute_payment_reconciliation(bundle)
    primary_issue, confidence = classify_primary_issue(bundle, delivery, payment)
    secondary_issues = classify_secondary_issues(bundle)
    root_cause = compute_root_cause_analysis(primary_issue, delivery)
    financial = compute_financial_resolution(primary_issue, payment)
    actions = compute_resolution_actions(primary_issue, secondary_issues)
    case_status = "action_required" if financial["recommended_refund_brl"] > 0 else "no_action"

    item_ids = [f"{order_id}:{it['order_item_id']}" for it in items][:MAX_ITEM_IDS]
    payment_ids = [f"{order_id}:{p['payment_sequential']}" for p in payments][:MAX_PAYMENT_IDS]
    seller_ids = _dedupe(it["seller_id"] for it in items)[:MAX_SELLER_IDS]
    product_ids = _dedupe(p["product_id"] for p in products)[:MAX_PRODUCT_IDS]
    category_names = _dedupe(p["product_category_name"] for p in products)[:MAX_CATEGORY_NAMES]

    evidence_ids = compute_evidence_ids(
        bundle, item_ids, payment_ids, root_cause["responsible_parties"], root_cause["ranked_causes"]
    )

    return {
        "case_assessment": {
            "primary_issue": primary_issue,
            "secondary_issues": secondary_issues,
            "case_status": case_status,
            "confidence": confidence,
        },
        "affected_entities": {
            "order_ids": [order_id][:MAX_ORDER_IDS],
            "item_ids": item_ids,
            "seller_ids": seller_ids,
            "payment_ids": payment_ids,
        },
        "customer_context": {
            "customer_unique_id": (bundle["customer"] or {}).get("customer_unique_id"),
            "related_order_ids": bundle["related_order_ids"][:MAX_RELATED_ORDER_IDS],
        },
        "product_context": {
            "product_ids": product_ids,
            "category_names": category_names,
        },
        "delivery_analysis": delivery,
        "payment_reconciliation": payment,
        "root_cause_analysis": root_cause,
        "evidence_ids": evidence_ids,
        "financial_resolution": financial,
        "resolution_actions": actions,
    }
