from datetime import datetime

def parse_dt(dt_str):
    if not dt_str or dt_str.lower() == 'null':
        return None
    try:
        return datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(dt_str.strip(), "%Y-%m-%d")
        except ValueError:
            return None

def hours_diff(dt1, dt2):
    if not dt1 or not dt2:
        return None
    seconds = (dt1 - dt2).total_seconds()
    return round(seconds / 3600.0, 2)

def evaluate_case(order_context: dict) -> dict:
    order = order_context["order"]
    customer = order_context["customer"]
    related_order_ids = order_context["related_order_ids"][:5]
    items = order_context["items"]
    payments = order_context["payments"]

    order_id = order["order_id"]
    order_status = order.get("order_status")
    
    # Parse timestamps
    delivered_customer_dt = parse_dt(order.get("order_delivered_customer_date"))
    estimated_delivery_dt = parse_dt(order.get("order_estimated_delivery_date"))
    carrier_handoff_dt = parse_dt(order.get("order_delivered_carrier_date"))

    # Delivery variance
    delivery_variance_hours = hours_diff(delivered_customer_dt, estimated_delivery_dt)

    # Payment calculations
    payment_types = []
    payment_total = 0.0
    payment_ids = []
    for p in payments:
        p_seq = p["payment_sequential"]
        payment_ids.append(f"{order_id}:{p_seq}")
        p_val = float(p.get("payment_value") or 0.0)
        payment_total += p_val
        p_type = p.get("payment_type")
        if p_type and p_type not in payment_types:
            payment_types.append(p_type)
    
    payment_total_brl = round(payment_total, 2)
    payment_ids = payment_ids[:5]

    # Item & Seller & Product processing
    item_ids = []
    seller_ids = []
    product_ids = []
    category_names = []
    item_total = 0.0
    freight_total = 0.0

    seller_shipping_limits = {} # seller_id -> earliest shipping_limit_date dt

    if len(items) > 0:
        for it in items:
            item_seq = it["order_item_id"]
            item_ids.append(f"{order_id}:{item_seq}")
            
            p_id = it.get("product_id")
            if p_id and p_id not in product_ids:
                product_ids.append(p_id)
            
            # category name directly from products table (Portuguese name in Olist dataset)
            cat_name = it.get("product_category_name")
            if cat_name and cat_name != "null" and cat_name not in category_names:
                category_names.append(cat_name)

            s_id = it.get("seller_id")
            if s_id and s_id not in seller_ids:
                seller_ids.append(s_id)
            
            price = float(it.get("price") or 0.0)
            freight = float(it.get("freight_value") or 0.0)
            item_total += price
            freight_total += freight

            # shipping limit
            s_limit_dt = parse_dt(it.get("shipping_limit_date"))
            if s_id and s_limit_dt:
                if s_id not in seller_shipping_limits or s_limit_dt < seller_shipping_limits[s_id]:
                    seller_shipping_limits[s_id] = s_limit_dt

        item_total_brl = round(item_total, 2)
        freight_total_brl = round(freight_total, 2)
        expected_total_brl = round(item_total_brl + freight_total_brl, 2)
        difference_brl = round(payment_total_brl - expected_total_brl, 2)
        reconciled = abs(difference_brl) <= 0.10
    else:
        item_total_brl = 0.0
        freight_total_brl = 0.0
        expected_total_brl = None
        difference_brl = None
        reconciled = None

    # Seller handoff analysis
    seller_handoff_analysis = []
    late_handoff_seller_ids = []
    for s_id, s_limit_dt in seller_shipping_limits.items():
        h_variance = hours_diff(carrier_handoff_dt, s_limit_dt) if carrier_handoff_dt and s_limit_dt else None
        is_late = (carrier_handoff_dt > s_limit_dt) if (carrier_handoff_dt and s_limit_dt) else False
        if is_late:
            late_handoff_seller_ids.append(s_id)
        seller_handoff_analysis.append({
            "seller_id": s_id,
            "shipping_limit_at": s_limit_dt.strftime("%Y-%m-%d %H:%M:%S") if s_limit_dt else None,
            "handoff_variance_hours": h_variance,
            "late_handoff": is_late
        })

    # Evaluate Primary Issue
    primary_issue = None
    responsible_parties = []
    recommended_refund_brl = 0.0
    primary_action = None
    root_cause_code = None
    case_status = "no_action"

    is_late_delivery = (delivered_customer_dt and estimated_delivery_dt and delivered_customer_dt > estimated_delivery_dt)

    if order_status == "canceled" and payment_total_brl > 0:
        primary_issue = "canceled_order_paid"
        responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
        recommended_refund_brl = payment_total_brl
        primary_action = "issue_full_refund"
        root_cause_code = "ORDER_CANCELED_AFTER_PAYMENT"
        case_status = "action_required"
    elif order_status == "unavailable" and payment_total_brl > 0:
        primary_issue = "unavailable_order_paid"
        responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
        recommended_refund_brl = payment_total_brl
        primary_action = "issue_full_refund"
        root_cause_code = "ORDER_UNAVAILABLE_AFTER_PAYMENT"
        case_status = "action_required"
    elif is_late_delivery and len(late_handoff_seller_ids) > 0:
        primary_issue = "late_delivery_seller"
        for s_id in late_handoff_seller_ids[:3]:
            responsible_parties.append({"party_type": "seller", "party_id": s_id})
        recommended_refund_brl = freight_total_brl
        primary_action = "refund_freight"
        root_cause_code = "SELLER_HANDOFF_AFTER_LIMIT"
        case_status = "action_required"
    elif is_late_delivery and len(late_handoff_seller_ids) == 0:
        primary_issue = "late_delivery_logistics"
        responsible_parties = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
        recommended_refund_brl = freight_total_brl
        primary_action = "refund_freight"
        root_cause_code = "CARRIER_DELIVERED_AFTER_ESTIMATE"
        case_status = "action_required"
    elif len(payments) >= 2 and reconciled:
        primary_issue = "valid_split_payment"
        responsible_parties = []
        recommended_refund_brl = 0.0
        primary_action = "explain_valid_split_payment"
        root_cause_code = "MULTIPLE_PAYMENTS_RECONCILED"
        case_status = "no_action"
    else:
        primary_issue = "unsupported_late_claim"
        responsible_parties = []
        recommended_refund_brl = 0.0
        primary_action = "reject_late_refund"
        root_cause_code = "DELIVERY_WITHIN_ESTIMATE"
        case_status = "no_action"

    # Evaluate Secondary Issues (in exact specified order)
    secondary_issues = []
    if len(items) >= 2:
        secondary_issues.append("multi_item_order")
    if len(seller_ids) >= 2:
        secondary_issues.append("multi_seller_order")
    if len(payments) >= 2:
        secondary_issues.append("split_payment")
    if len(related_order_ids) >= 1:
        secondary_issues.append("repeat_customer")
    if len(category_names) >= 2:
        secondary_issues.append("multiple_categories")

    # Evaluate Actions
    resolution_actions = [primary_action]
    if primary_issue == "late_delivery_seller":
        resolution_actions.append("review_seller_handoff")
    elif primary_issue == "late_delivery_logistics":
        resolution_actions.append("review_carrier_delay")

    if case_status == "action_required" or recommended_refund_brl > 0:
        resolution_actions.append("verify_refund_completion")

    if "multi_seller_order" in secondary_issues:
        resolution_actions.append("coordinate_multi_seller_case")

    if "split_payment" in secondary_issues and primary_issue != "valid_split_payment":
        resolution_actions.append("verify_payment_allocation")

    resolution_actions = resolution_actions[:5]

    # Generate Evidence IDs
    evidence_ids = [f"order:{order_id}"]
    for i_id in item_ids[:5]:
        evidence_ids.append(f"item:{i_id}")
    for p_id in payment_ids[:5]:
        evidence_ids.append(f"payment:{p_id}")
    for party in responsible_parties:
        if party["party_type"] == "seller":
            evidence_ids.append(f"seller:{party['party_id']}")
    evidence_ids.append(f"policy:{root_cause_code}")
    evidence_ids = evidence_ids[:20]

    # Caps
    item_ids = item_ids[:5]
    seller_ids = seller_ids[:3]
    payment_ids = payment_ids[:5]
    product_ids = product_ids[:5]
    category_names = category_names[:5]

    # Assemble schema
    result = {
        "case_id": "", # to be populated from input
        "case_assessment": {
            "primary_issue": primary_issue,
            "secondary_issues": secondary_issues,
            "case_status": case_status,
            "confidence": 0.95
        },
        "affected_entities": {
            "order_ids": [order_id],
            "item_ids": item_ids,
            "seller_ids": seller_ids,
            "payment_ids": payment_ids
        },
        "customer_context": {
            "customer_unique_id": customer.get("customer_unique_id") or "",
            "related_order_ids": related_order_ids
        },
        "product_context": {
            "product_ids": product_ids,
            "category_names": category_names
        },
        "delivery_analysis": {
            "delivered_at": order.get("order_delivered_customer_date") if order.get("order_delivered_customer_date") != "null" else None,
            "estimated_delivery_at": order.get("order_estimated_delivery_date") if order.get("order_estimated_delivery_date") != "null" else None,
            "carrier_handoff_at": order.get("order_delivered_carrier_date") if order.get("order_delivered_carrier_date") != "null" else None,
            "delivery_variance_hours": delivery_variance_hours,
            "seller_handoff_analysis": seller_handoff_analysis if len(items) > 0 else [],
            "late_handoff_seller_ids": late_handoff_seller_ids if len(items) > 0 else []
        },
        "payment_reconciliation": {
            "currency": "BRL",
            "item_total_brl": item_total_brl,
            "freight_total_brl": freight_total_brl,
            "expected_total_brl": expected_total_brl,
            "payment_total_brl": payment_total_brl,
            "difference_brl": difference_brl,
            "reconciled": reconciled,
            "payment_types": payment_types
        },
        "root_cause_analysis": {
            "ranked_causes": [
                {"cause_code": root_cause_code, "rank": 1}
            ],
            "responsible_parties": responsible_parties
        },
        "evidence_ids": evidence_ids,
        "financial_resolution": {
            "currency": "BRL",
            "recommended_refund_brl": recommended_refund_brl
        },
        "resolution_actions": resolution_actions
    }

    return result
