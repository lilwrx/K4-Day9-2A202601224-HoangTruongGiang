"""Verifier Agent: kiem tra ID, so tien, null handling, array limit va schema
truoc khi ghi file.

Agent nay khong tin ket qua cua bat ky agent nao khac, ke ca Policy Agent:
moi evidence ID deu duoc doi chieu nguoc lai DataStore, moi array deu duoc
kiem gioi han, moi timestamp deu duoc kiem dinh dang.
"""

import re

from ..config import LIMITS, RECONCILE_TOLERANCE_BRL
from ..policy_rules import PRIMARY_ISSUES, ROOT_CAUSE_BY_ISSUE, SECONDARY_ORDER

AGENT_NAME = "verifier_agent"

TS_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

VALID_ACTIONS = {
    "issue_full_refund",
    "refund_freight",
    "explain_valid_split_payment",
    "reject_late_refund",
    "review_seller_handoff",
    "review_carrier_delay",
    "verify_refund_completion",
    "coordinate_multi_seller_case",
    "verify_payment_allocation",
}

VALID_PARTY_TYPES = {"platform", "seller", "logistics_provider"}


def _check_timestamps(payload: dict, issues: list) -> None:
    delivery = payload["delivery_analysis"]
    for field in ("delivered_at", "estimated_delivery_at", "carrier_handoff_at"):
        value = delivery.get(field)
        if value is not None and not TS_PATTERN.match(value):
            issues.append(f"delivery_analysis.{field} sai dinh dang: {value!r}")
    for entry in delivery.get("seller_handoff_analysis", []):
        value = entry.get("shipping_limit_at")
        if value is not None and not TS_PATTERN.match(value):
            issues.append(f"shipping_limit_at sai dinh dang: {value!r}")


def _check_limits(payload: dict, issues: list) -> None:
    checks = [
        (payload["affected_entities"]["order_ids"], "order_ids"),
        (payload["affected_entities"]["item_ids"], "item_ids"),
        (payload["affected_entities"]["seller_ids"], "seller_ids"),
        (payload["affected_entities"]["payment_ids"], "payment_ids"),
        (payload["customer_context"]["related_order_ids"], "related_order_ids"),
        (payload["product_context"]["product_ids"], "product_ids"),
        (payload["product_context"]["category_names"], "category_names"),
        (payload["root_cause_analysis"]["ranked_causes"], "ranked_causes"),
        (payload["root_cause_analysis"]["responsible_parties"], "responsible_parties"),
        (payload["evidence_ids"], "evidence_ids"),
        (payload["resolution_actions"], "resolution_actions"),
    ]
    for array, name in checks:
        if len(array) > LIMITS[name]:
            issues.append(f"{name} vuot gioi han {LIMITS[name]}: {len(array)}")


def _check_evidence(payload: dict, store, order_id: str, issues: list) -> None:
    """Moi evidence ID phai dung dinh dang VA dung duoc tu du lieu that."""
    valid_item_ids = {
        f"{order_id}:{it['order_item_id']}" for it in store.get_items(order_id)
    }
    valid_payment_ids = {
        f"{order_id}:{p['payment_sequential']}" for p in store.get_payments(order_id)
    }

    for evidence in payload["evidence_ids"]:
        if evidence.startswith("order:"):
            if store.get_order(evidence[len("order:") :]) is None:
                issues.append(f"evidence order khong ton tai: {evidence}")
        elif evidence.startswith("item:"):
            if evidence[len("item:") :] not in valid_item_ids:
                issues.append(f"evidence item khong ton tai: {evidence}")
        elif evidence.startswith("payment:"):
            if evidence[len("payment:") :] not in valid_payment_ids:
                issues.append(f"evidence payment khong ton tai: {evidence}")
        elif evidence.startswith("seller:"):
            if not store.has_seller(evidence[len("seller:") :]):
                issues.append(f"evidence seller khong ton tai: {evidence}")
        elif evidence.startswith("policy:"):
            if evidence[len("policy:") :] not in ROOT_CAUSE_BY_ISSUE.values():
                issues.append(f"evidence policy khong hop le: {evidence}")
        else:
            issues.append(f"evidence sai dinh dang: {evidence}")


def _check_payment_nulls(payload: dict, issues: list) -> None:
    """Don khong co item row phai co dung 3 truong null."""
    recon = payload["payment_reconciliation"]
    has_items = bool(payload["affected_entities"]["item_ids"])
    null_fields = ("expected_total_brl", "difference_brl", "reconciled")

    if not has_items:
        for field in null_fields:
            if recon.get(field) is not None:
                issues.append(f"don khong co item nhung {field} khong null")
    else:
        for field in null_fields:
            if recon.get(field) is None:
                issues.append(f"don co item nhung {field} lai null")
        expected = recon["expected_total_brl"]
        computed = round(recon["item_total_brl"] + recon["freight_total_brl"], 2)
        if abs(expected - computed) > 0.011:
            issues.append(
                f"expected_total_brl {expected} != item+freight {computed}"
            )
        difference = round(recon["payment_total_brl"] - expected, 2)
        if abs(difference - recon["difference_brl"]) > 0.011:
            issues.append("difference_brl khong khop payment_total - expected_total")
        if recon["reconciled"] != (abs(recon["difference_brl"]) <= RECONCILE_TOLERANCE_BRL):
            issues.append("reconciled khong khop nguong 0.10 BRL")


def verify(payload: dict, store, order_id: str) -> list[str]:
    """Tra ve danh sach van de. Rong = output dat chuan."""
    issues: list[str] = []

    assessment = payload["case_assessment"]
    if assessment["primary_issue"] not in PRIMARY_ISSUES:
        issues.append(f"primary_issue khong hop le: {assessment['primary_issue']}")
    for secondary in assessment["secondary_issues"]:
        if secondary not in SECONDARY_ORDER:
            issues.append(f"secondary_issue khong hop le: {secondary}")
    expected_order = [s for s in SECONDARY_ORDER if s in assessment["secondary_issues"]]
    if assessment["secondary_issues"] != expected_order:
        issues.append("secondary_issues sai thu tu nghiep vu")
    if assessment["case_status"] not in ("action_required", "no_action"):
        issues.append(f"case_status khong hop le: {assessment['case_status']}")
    if not 0.0 <= assessment["confidence"] <= 1.0:
        issues.append(f"confidence ngoai [0,1]: {assessment['confidence']}")

    refund = payload["financial_resolution"]["recommended_refund_brl"]
    if refund < 0:
        issues.append("recommended_refund_brl am")
    expected_status = "action_required" if refund > 0 else "no_action"
    if assessment["case_status"] != expected_status:
        issues.append(
            f"case_status {assessment['case_status']} khong khop refund {refund}"
        )

    for action in payload["resolution_actions"]:
        if action not in VALID_ACTIONS:
            issues.append(f"action khong hop le: {action}")
    if (
        assessment["primary_issue"] == "valid_split_payment"
        and "verify_payment_allocation" in payload["resolution_actions"]
    ):
        issues.append("valid_split_payment khong duoc kem verify_payment_allocation")

    for party in payload["root_cause_analysis"]["responsible_parties"]:
        if party["party_type"] not in VALID_PARTY_TYPES:
            issues.append(f"party_type khong hop le: {party['party_type']}")
        if party["party_type"] == "seller" and not store.has_seller(party["party_id"]):
            issues.append(f"seller chiu trach nhiem khong ton tai: {party['party_id']}")

    ranks = [c["rank"] for c in payload["root_cause_analysis"]["ranked_causes"]]
    if ranks != list(range(1, len(ranks) + 1)):
        issues.append(f"rank cua root cause khong lien tuc tu 1: {ranks}")

    _check_timestamps(payload, issues)
    _check_limits(payload, issues)
    _check_evidence(payload, store, order_id, issues)
    _check_payment_nulls(payload, issues)

    return issues
