"""EC_POLICY_V2 duoi dang rule engine deterministic.

Vai tro kep:
1. Fallback khi Policy Agent (LLM) khong tra ve ket qua hop le.
2. Chot chan kiem chung: Verifier doi chieu ket luan cua LLM voi engine nay.

Toan bo tien va so gio da duoc cac agent phan tich tinh san; module nay
chi lam viec phan loai theo thu tu uu tien cua policy.
"""

from .config import LIMITS

# Thu tu uu tien primary issue theo bang trong de bai.
PRIMARY_ISSUES = [
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
]

ROOT_CAUSE_BY_ISSUE = {
    "canceled_order_paid": "ORDER_CANCELED_AFTER_PAYMENT",
    "unavailable_order_paid": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
    "late_delivery_seller": "SELLER_HANDOFF_AFTER_LIMIT",
    "late_delivery_logistics": "CARRIER_DELIVERED_AFTER_ESTIMATE",
    "valid_split_payment": "MULTIPLE_PAYMENTS_RECONCILED",
    "unsupported_late_claim": "DELIVERY_WITHIN_ESTIMATE",
}

MAIN_ACTION_BY_ISSUE = {
    "canceled_order_paid": "issue_full_refund",
    "unavailable_order_paid": "issue_full_refund",
    "late_delivery_seller": "refund_freight",
    "late_delivery_logistics": "refund_freight",
    "valid_split_payment": "explain_valid_split_payment",
    "unsupported_late_claim": "reject_late_refund",
}

FULL_REFUND_ISSUES = {"canceled_order_paid", "unavailable_order_paid"}

# Thu tu secondary issue la co dinh theo de bai.
SECONDARY_ORDER = [
    "multi_item_order",
    "multi_seller_order",
    "split_payment",
    "repeat_customer",
    "multiple_categories",
]


def classify_primary(facts: dict) -> str:
    """Ap dung 6 quy tac theo dung thu tu uu tien, dung o quy tac dau tien khop."""
    order = facts["order_context"]
    payment = facts["payment_reconciliation"]
    delivery = facts["delivery_analysis"]

    status = order.get("order_status")
    paid = (payment.get("payment_total_brl") or 0) > 0
    late_delivery = delivery.get("is_late_delivery", False)
    late_sellers = delivery.get("late_handoff_seller_ids") or []
    reconciled = payment.get("reconciled")
    multi_payment = payment.get("payment_count", 0) >= 2

    if status == "canceled" and paid:
        return "canceled_order_paid"
    if status == "unavailable" and paid:
        return "unavailable_order_paid"
    if late_delivery and late_sellers:
        return "late_delivery_seller"
    if late_delivery and not late_sellers:
        return "late_delivery_logistics"
    if multi_payment and reconciled is True:
        return "valid_split_payment"
    # Quy tac cuoi cung dong vai tro catch-all: don khong giao tre thi khong
    # co can cu hoan tien, du doi soat payment co lech.
    return "unsupported_late_claim"


def secondary_issues(facts: dict) -> list[str]:
    order = facts["order_context"]
    payment = facts["payment_reconciliation"]
    customer = facts["customer_context"]

    flags = {
        "multi_item_order": order.get("item_count", 0) >= 2,
        "multi_seller_order": order.get("seller_count", 0) >= 2,
        "split_payment": payment.get("payment_count", 0) >= 2,
        "repeat_customer": customer.get("is_repeat_customer", False),
        "multiple_categories": order.get("category_count", 0) >= 2,
    }
    return [name for name in SECONDARY_ORDER if flags[name]]


def responsible_parties(primary: str, facts: dict) -> list[dict]:
    if primary in FULL_REFUND_ISSUES:
        return [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
    if primary == "late_delivery_seller":
        late = facts["delivery_analysis"].get("late_handoff_seller_ids") or []
        return [
            {"party_type": "seller", "party_id": sid}
            for sid in late[: LIMITS["responsible_parties"]]
        ]
    if primary == "late_delivery_logistics":
        return [
            {"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}
        ]
    return []


def recommended_refund(primary: str, facts: dict) -> float:
    payment = facts["payment_reconciliation"]
    if primary in FULL_REFUND_ISSUES:
        return round(payment.get("payment_total_brl") or 0.0, 2)
    if primary in ("late_delivery_seller", "late_delivery_logistics"):
        return round(payment.get("freight_total_brl") or 0.0, 2)
    return 0.0


def resolution_actions(primary: str, facts: dict) -> list[str]:
    """Action chinh dung dau, cac action bo sung theo dung thu tu de bai."""
    actions = [MAIN_ACTION_BY_ISSUE[primary]]

    if primary == "late_delivery_seller":
        actions.append("review_seller_handoff")
    elif primary == "late_delivery_logistics":
        actions.append("review_carrier_delay")

    # Vi du trong de bai khong them verify_refund_completion cho refund_freight,
    # nen chi ap dung cho truong hop hoan toan bo tien.
    if primary in FULL_REFUND_ISSUES:
        actions.append("verify_refund_completion")

    if facts["order_context"].get("seller_count", 0) >= 2:
        actions.append("coordinate_multi_seller_case")

    # Khong them verify_payment_allocation khi action chinh da giai thich
    # split payment.
    if (
        facts["payment_reconciliation"].get("payment_count", 0) >= 2
        and primary != "valid_split_payment"
    ):
        actions.append("verify_payment_allocation")

    return actions[: LIMITS["resolution_actions"]]


def confidence(primary: str, facts: dict) -> float:
    """Do tin cay dua tren muc day du cua du lieu can de ket luan."""
    delivery = facts["delivery_analysis"]
    payment = facts["payment_reconciliation"]

    score = 0.95
    if primary in ("late_delivery_seller", "late_delivery_logistics"):
        if delivery.get("carrier_handoff_at") is None:
            score -= 0.10
    if payment.get("reconciled") is None:
        score -= 0.05
    elif payment.get("reconciled") is False:
        score -= 0.03
    return round(max(0.0, min(1.0, score)), 2)


def decide(facts: dict) -> dict:
    """Ket luan day du cho mot case theo EC_POLICY_V2."""
    primary = classify_primary(facts)
    refund = recommended_refund(primary, facts)
    return {
        "primary_issue": primary,
        "secondary_issues": secondary_issues(facts),
        "root_cause_code": ROOT_CAUSE_BY_ISSUE[primary],
        "responsible_parties": responsible_parties(primary, facts),
        "recommended_refund_brl": refund,
        "resolution_actions": resolution_actions(primary, facts),
        "case_status": "action_required" if refund > 0 else "no_action",
        "confidence": confidence(primary, facts),
    }
