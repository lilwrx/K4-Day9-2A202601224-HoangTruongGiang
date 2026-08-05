"""Policy Agent: ap dung EC_POLICY_V2 bang LLM <= 10B.

Thiet ke co chu dich: LLM PHAN LOAI, khong LAM TOAN.
Cac agent phan tich da tinh san so gio va so tien; LLM chi nhan cac su kien
da tinh va chon primary issue / secondary issues / root cause / responsible
party. Moi con so tien trong output deu do rule engine tinh, vi model 8B
tinh chenh lech timestamp va cong tien khong dang tin.

Ket qua cua LLM luon duoc doi chieu voi src/policy_rules.py. Neu LLM tra ve
gia tri ngoai taxonomy hoac mau thuan voi du lieu, Policy Agent ha xuong
ket luan deterministic va ghi ro trong trace.
"""

from .. import llm
from ..policy_rules import (
    MAIN_ACTION_BY_ISSUE,
    PRIMARY_ISSUES,
    ROOT_CAUSE_BY_ISSUE,
    SECONDARY_ORDER,
    decide,
    recommended_refund,
    resolution_actions,
    responsible_parties,
)

AGENT_NAME = "policy_agent"

SYSTEM_PROMPT = """Ban la Policy Agent cua he thong xu ly khieu nai thuong mai dien tu Olist.
Ban ap dung dung chinh sach EC_POLICY_V2 tren cac su kien da duoc cac agent khac tinh san.
Ban KHONG duoc tu tinh toan lai so gio hay so tien, va KHONG duoc bia ra su kien khong co trong du lieu.

Chon primary_issue theo dung THU TU UU TIEN, dung lai o quy tac dau tien thoa man:
1. canceled_order_paid       : order_status = canceled VA payment_total_brl > 0
2. unavailable_order_paid    : order_status = unavailable VA payment_total_brl > 0
3. late_delivery_seller      : is_late_delivery = true VA late_handoff_seller_ids khong rong
4. late_delivery_logistics   : is_late_delivery = true VA late_handoff_seller_ids rong
5. valid_split_payment       : payment_count >= 2 VA reconciled = true
6. unsupported_late_claim    : cac truong hop con lai (khong giao tre, khong co can cu hoan tien)

secondary_issues chi duoc lay tu danh sach sau, giu dung thu tu nay:
- multi_item_order      : item_count >= 2
- multi_seller_order    : seller_count >= 2
- split_payment         : payment_count >= 2
- repeat_customer       : is_repeat_customer = true
- multiple_categories   : category_count >= 2

root_cause_code tuong ung 1-1 voi primary_issue:
canceled_order_paid -> ORDER_CANCELED_AFTER_PAYMENT
unavailable_order_paid -> ORDER_UNAVAILABLE_AFTER_PAYMENT
late_delivery_seller -> SELLER_HANDOFF_AFTER_LIMIT
late_delivery_logistics -> CARRIER_DELIVERED_AFTER_ESTIMATE
valid_split_payment -> MULTIPLE_PAYMENTS_RECONCILED
unsupported_late_claim -> DELIVERY_WITHIN_ESTIMATE

Chi tra ve JSON dung dinh dang:
{"primary_issue": "...", "secondary_issues": ["..."], "root_cause_code": "...",
 "confidence": 0.0, "reasoning": "mot cau ngan"}"""


def _facts_for_llm(facts: dict) -> dict:
    """Rut gon su kien xuong dung nhung gi can de phan loai.

    Khong day nguyen bang CSV vao prompt: context cang gon, model 8B cang it
    co hoi bia them chi tiet.
    """
    order = facts["order_context"]
    payment = facts["payment_reconciliation"]
    delivery = facts["delivery_analysis"]
    customer = facts["customer_context"]

    return {
        "order_status": order.get("order_status"),
        "item_count": order.get("item_count"),
        "seller_count": order.get("seller_count"),
        "category_count": order.get("category_count"),
        "payment_count": payment.get("payment_count"),
        "payment_total_brl": payment.get("payment_total_brl"),
        "expected_total_brl": payment.get("expected_total_brl"),
        "difference_brl": payment.get("difference_brl"),
        "reconciled": payment.get("reconciled"),
        "freight_total_brl": payment.get("freight_total_brl"),
        "delivery_variance_hours": delivery.get("delivery_variance_hours"),
        "is_late_delivery": delivery.get("is_late_delivery"),
        "late_handoff_seller_ids": delivery.get("late_handoff_seller_ids"),
        "is_repeat_customer": customer.get("is_repeat_customer"),
    }


def _validate_llm_output(raw: dict, facts: dict) -> tuple[dict | None, list[str]]:
    """Kiem tra ket qua LLM. Tra (assessment hop le hoac None, danh sach loi)."""
    problems = []

    primary = raw.get("primary_issue")
    if primary not in PRIMARY_ISSUES:
        problems.append(f"primary_issue ngoai taxonomy: {primary!r}")
        return None, problems

    secondary_raw = raw.get("secondary_issues") or []
    if not isinstance(secondary_raw, list):
        problems.append("secondary_issues khong phai array")
        secondary_raw = []

    unknown = [s for s in secondary_raw if s not in SECONDARY_ORDER]
    if unknown:
        problems.append(f"secondary_issues khong hop le bi loai: {unknown}")
    # Ep ve dung thu tu nghiep vu du LLM tra ve thu tu nao.
    secondary = [s for s in SECONDARY_ORDER if s in secondary_raw]

    root_cause = raw.get("root_cause_code")
    if root_cause != ROOT_CAUSE_BY_ISSUE[primary]:
        problems.append(
            f"root_cause_code {root_cause!r} khong khop primary_issue, da sua"
        )
        root_cause = ROOT_CAUSE_BY_ISSUE[primary]

    try:
        conf = float(raw.get("confidence"))
    except (TypeError, ValueError):
        conf = 0.8
        problems.append("confidence khong doc duoc, dat mac dinh 0.8")
    conf = round(max(0.0, min(1.0, conf)), 2)

    # Tien, responsible party va action luon do rule engine sinh tu su kien,
    # khong lay tu LLM.
    refund = recommended_refund(primary, facts)
    return (
        {
            "primary_issue": primary,
            "secondary_issues": secondary,
            "root_cause_code": root_cause,
            "responsible_parties": responsible_parties(primary, facts),
            "recommended_refund_brl": refund,
            "resolution_actions": resolution_actions(primary, facts),
            "case_status": "action_required" if refund > 0 else "no_action",
            "confidence": conf,
        },
        problems,
    )


def analyze(facts: dict, use_llm: bool = True) -> tuple[dict, dict]:
    """Tra ve (assessment, meta). meta ghi lai che do va moi sai lech cua LLM."""
    deterministic = decide(facts)

    if not use_llm or not llm.is_available():
        return deterministic, {
            "mode": "rule_engine",
            "reason": "LLM khong kha dung" if use_llm else "tat boi tham so",
            "problems": [],
        }

    user_prompt = (
        "Su kien da duoc cac agent phan tich xac minh tu du lieu Olist:\n"
        + _dump(_facts_for_llm(facts))
        + "\n\nAp dung EC_POLICY_V2 va tra ve JSON."
    )

    try:
        raw, call_meta = llm.complete_json(SYSTEM_PROMPT, user_prompt)
    except llm.LLMError as exc:
        return deterministic, {
            "mode": "rule_engine_fallback",
            "reason": f"loi goi LLM: {exc}",
            "problems": [],
        }

    assessment, problems = _validate_llm_output(raw, facts)
    if assessment is None:
        return deterministic, {
            "mode": "rule_engine_fallback",
            "reason": "ket qua LLM khong hop le",
            "problems": problems,
            "llm_raw": raw,
            "llm_call": call_meta,
        }

    agreed = assessment["primary_issue"] == deterministic["primary_issue"]
    return assessment, {
        "mode": "llm",
        "agrees_with_rule_engine": agreed,
        "rule_engine_primary": deterministic["primary_issue"],
        "problems": problems,
        "llm_reasoning": raw.get("reasoning"),
        "llm_call": call_meta,
    }


def _dump(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2)
