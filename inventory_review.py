"""Deterministic inventory and quotation review. No LLM, outbound calls or answer-key access."""
import csv
import io
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from market_scout import SourcingRecord, calculate_margin, csv_safe

DATA_DIR = Path(__file__).resolve().parent / "data" / "demo"
INPUT_FILES = ("metadata", "products", "inventory", "sales", "incoming_orders", "quotations")


def whole(value, field, minimum=0):
    if type(value) is not int or not minimum <= value <= 1_000_000_000:
        raise ValueError(f"{field} must be an integer between {minimum} and 1000000000")
    return value


def decimal(value, field):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{field} must be numeric")
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"Invalid {field}") from exc
    if not result.is_finite() or not 0 <= result <= Decimal("1000000000000"):
        raise ValueError(f"Invalid {field}")
    return result


def money(value):
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def rounded_order(quantity, multiple):
    return int((max(Decimal(0), quantity)/multiple).to_integral_value(rounding=ROUND_CEILING))*multiple


def unique(rows, fields, label):
    values = [tuple(row[field] for field in fields) for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {label}")


def load_inputs(folder=DATA_DIR):
    # Exact whitelist: test fixtures / expected answers never enter this application path.
    inputs = {name: json.loads((folder / f"{name}.json").read_text(encoding="utf-8")) for name in INPUT_FILES}
    validate_inputs(inputs)
    return inputs


def validate_inputs(data):
    metadata = data["metadata"]
    if metadata.get("synthetic") is not True:
        raise ValueError("This demo endpoint accepts only its labelled synthetic dataset")
    as_of = date.fromisoformat(metadata["as_of"])
    start = date.fromisoformat(metadata["history_start"])
    end = date.fromisoformat(metadata["history_end"])
    if not start <= end < as_of or end != as_of-timedelta(days=1):
        raise ValueError("History must end immediately before the inventory snapshot")
    window = whole(metadata["demand_window_days"], "Demand window", 1)
    if window > 366 or (as_of-start).days < window:
        raise ValueError("Insufficient history for the demand window")
    for name, fields in (("products", ("sku",)), ("inventory", ("sku",)), ("sales", ("record_id",)),
                        ("incoming_orders", ("po_id", "sku")), ("quotations", ("quote_id",))):
        unique(data[name], fields, name)
    products = {row["sku"]: row for row in data["products"]}
    if set(products) != {row["sku"] for row in data["inventory"]}:
        raise ValueError("Every product must have exactly one stock snapshot")
    for rows in (data["inventory"], data["sales"], data["incoming_orders"], data["quotations"]):
        if any(row["sku"] not in products for row in rows):
            raise ValueError("Unknown product reference")
    for product in products.values():
        for field in ("lead_days", "safety_days", "review_days"):
            if whole(product[field], field) > 365:
                raise ValueError("Planning periods must be at most 365 calendar days")
        whole(product["order_multiple"], "Order multiple", 1)
        if not product["name"] or not product["sellable_unit"] or len(product["currency"]) != 3:
            raise ValueError("Product name, unit and currency required")
        for field in ("retail_price_gross", "purchase_budget", "vat_rate", "target_margin"):
            decimal(product[field], field)
        if decimal(product["retail_price_gross"], "Retail") == 0 or any(decimal(product[field], field)>1 for field in ("vat_rate", "target_margin")):
            raise ValueError("Invalid product retail or rate")
    for row in data["inventory"]:
        if row["snapshot_date"] != metadata["as_of"]:
            raise ValueError("Stock snapshots must match the analysis date")
        whole(row["on_hand"], "On hand")
        whole(row["reserved"], "Reserved")
        if row["reserved"] > row["on_hand"]:
            raise ValueError("Reservations exceed stock; reconcile inventory before analysis")
    for row in data["sales"]:
        if row["kind"] not in ("SALE", "RETURN") or not start <= date.fromisoformat(row["date"]) <= end:
            raise ValueError("Invalid sales history row")
        whole(row["quantity"], "Sales/return quantity")
    expected_days = {(as_of-timedelta(days=offset)).isoformat() for offset in range(1, window+1)}
    for sku in products:
        observed = {row["date"] for row in data["sales"] if row["sku"] == sku and row["kind"] == "SALE"}
        if not expected_days <= observed:
            raise ValueError("Missing daily sales coverage; do not treat absent records as zero demand")
    for row in data["incoming_orders"]:
        whole(row["ordered"], "Ordered")
        whole(row["received"], "Received")
        date.fromisoformat(row["due_date"])
        if row["received"] > row["ordered"] or row["status"] not in ("CONFIRMED", "CANCELLED", "CLOSED"):
            raise ValueError("Invalid incoming order")
    for row in data["quotations"]:
        for field in ("moq", "order_multiple"):
            whole(row[field], field, 1)
        whole(row["lead_days"], "Quote lead time")
        date.fromisoformat(row["valid_until"])
        for field in ("wholesale_price", "shipping_per_unit", "duty_per_unit"):
            if row[field] is not None:
                decimal(row[field], field)


def review_product(product, stock, sales, orders, metadata):
    as_of = date.fromisoformat(metadata["as_of"])
    window = metadata["demand_window_days"]
    cutoff = as_of-timedelta(days=window)
    sold = sum(row["quantity"] for row in sales if row["kind"] == "SALE" and cutoff <= date.fromisoformat(row["date"]) < as_of)
    returned = sum(row["quantity"] for row in sales if row["kind"] == "RETURN" and cutoff <= date.fromisoformat(row["date"]) < as_of)
    daily = Decimal(sold)/window
    available = stock["on_hand"]-stock["reserved"]
    lead = product["lead_days"]
    horizon = max(1, lead+product["safety_days"]+product["review_days"])
    eligible = [row for row in orders if row["status"] == "CONFIRMED" and row["ordered"] > row["received"] and date.fromisoformat(row["due_date"]) >= as_of]
    overdue = sum(row["ordered"]-row["received"] for row in orders if row["status"] == "CONFIRMED" and date.fromisoformat(row["due_date"]) < as_of)
    incoming = sum(row["ordered"]-row["received"] for row in eligible if date.fromisoformat(row["due_date"]) <= as_of+timedelta(days=lead))
    position = available+incoming
    reorder_point = daily*(lead+product["safety_days"])
    target = daily*horizon
    projected, first_shortage = Decimal(available), None
    daily_projection = []
    for offset in range(horizon):
        when = as_of+timedelta(days=offset)
        receipt = sum(row["ordered"]-row["received"] for row in eligible if row["due_date"] == when.isoformat())
        projected += receipt-daily
        if projected < 0 and first_shortage is None:
            first_shortage = when.isoformat()
        daily_projection.append(dict(date=when.isoformat(), incoming=receipt, projected_units=float(projected)))
    quantity = rounded_order(target-position, product["order_multiple"]) if daily > 0 and position <= reorder_point else 0
    if daily == 0:
        status = "NO_RECENT_SALES"
        reason = "No sales in the baseline window. Review excess stock; do not infer future demand is permanently zero."
    elif quantity > 0:
        status = "REORDER"
        reason = "Stock position is at or below the reorder point. Review a replenishment proposal."
    elif first_shortage and any(first_shortage < row["due_date"] <= (as_of+timedelta(days=lead)).isoformat() for row in eligible):
        status = "EXPEDITE_EXISTING"
        reason = "Incoming stock supports the position but arrives after a projected gap. Expedite or source a bridge quantity; avoid a duplicate full order."
    elif incoming and available <= reorder_point:
        status = "INCOMING_COVERED"
        reason = "Confirmed incoming stock covers the reorder threshold; no duplicate order proposed. Reassess at the next review cycle."
    else:
        status = "SUFFICIENT"
        reason = "Stock position exceeds the reorder point under the baseline assumptions."
    if overdue:
        reason += f" {overdue} overdue units are excluded pending a reconfirmed delivery date."
    return {**product, **stock, "daily_sales": float(daily), "window_sales": sold, "window_returns": returned,
            "available": available, "confirmed_incoming": incoming, "overdue_quantity": overdue,
            "stock_position": position, "reorder_point": float(reorder_point), "target_stock": float(target),
            "days_cover": round(available/float(daily), 1) if daily else None, "first_shortage_date": first_shortage,
            "suggested_quantity": quantity, "status": status, "reason": reason,
            "projection": daily_projection, "incoming_orders": orders, "human_review_required": True}


def compare_quotes(item, quotations, as_of):
    rows = []
    required = item["suggested_quantity"]
    for quote in quotations:
        issues = []
        if quote["currency"] != item["currency"]:
            issues.append("Currency differs; no automatic FX conversion")
        if quote["sellable_unit"] != item["sellable_unit"]:
            issues.append("Pack / sellable unit differs; confirm comparability")
        if date.fromisoformat(quote["valid_until"]) < as_of:
            issues.append("Quotation expired")
        missing = [field for field in ("wholesale_price", "shipping_per_unit", "duty_per_unit") if quote[field] is None]
        if missing:
            issues.append("Missing " + ", ".join(missing))
        arrival = as_of+timedelta(days=quote["lead_days"])
        if item["first_shortage_date"] and arrival > date.fromisoformat(item["first_shortage_date"]):
            issues.append("Delivery later than the first projected shortage")
        # Quantities must satisfy both the product and supplier order multiples.
        from math import lcm
        quantity = rounded_order(Decimal(max(required, quote["moq"])), lcm(item["order_multiple"],quote["order_multiple"])) if required else 0
        economics = None
        total = None
        # Never compute a comparable margin for a mismatched currency or unit.
        comparable = quote["currency"] == item["currency"] and quote["sellable_unit"] == item["sellable_unit"]
        if not missing and comparable:
            record = SourcingRecord(item["name"], item["name"], quote["supplier"], "", float(decimal(quote["wholesale_price"],"Wholesale")),
                item["currency"], quote["moq"], float(decimal(item["retail_price_gross"],"Retail")),
                float(decimal(quote["shipping_per_unit"],"Shipping")), float(decimal(quote["duty_per_unit"],"Duty")), [], quote["evidence"])
            economics = calculate_margin(record,float(item["vat_rate"]),float(item["target_margin"]))
            landed = sum(decimal(quote[field],field) for field in ("wholesale_price","shipping_per_unit","duty_per_unit"))
            total = money(landed*quantity)
            if landed*quantity > decimal(item["purchase_budget"],"Budget"):
                issues.append("Minimum compliant order exceeds the per-product budget")
            if economics["decision"] != "GO":
                issues.append("Gross margin below the product target")
        rows.append({**quote,"order_quantity":quantity,"arrival_date":arrival.isoformat(),"order_cost":total,
                     "economics":economics,"issues":issues,"eligible":required>0 and not issues})
    eligible = [row for row in rows if row["eligible"]]
    # Cost only: supplier quality, certifications and capacity have not been established.
    best = min(eligible, key=lambda row:(row["order_cost"],row["arrival_date"],row["quote_id"])) if eligible else None
    action = "REVIEW_PROPOSAL" if best else ("CLARIFY_OR_FIND_SUPPLIERS" if required else "NO_NEW_ORDER")
    return dict(quotations=rows,selected_quote_id=best["quote_id"] if best else None,action=action,
                recommendation=(f"Review {best['supplier']}: lowest total cost among complete, comparable quotations meeting budget, timing and margin rules. Supplier qualification remains unverified." if best else
                                "No eligible quotation. Resolve the flagged constraints before a purchasing decision." if required else
                                "No new order proposed. Review the inventory reason and any overdue deliveries."))


def build_review(inputs=None):
    data = load_inputs() if inputs is None else inputs
    validate_inputs(data)
    metadata = data["metadata"]
    items = []
    for product in data["products"]:
        sku = product["sku"]
        stock = next(row for row in data["inventory"] if row["sku"] == sku)
        item = review_product(product,stock,[row for row in data["sales"] if row["sku"]==sku],
                              [row for row in data["incoming_orders"] if row["sku"]==sku],metadata)
        item.update(compare_quotes(item,[row for row in data["quotations"] if row["sku"]==sku],date.fromisoformat(metadata["as_of"])))
        # These are data handoffs, not fabricated AI-agent executions.
        item["handoff"] = {"sku":sku,"product":item["name"],"sellable_unit":item["sellable_unit"],"currency":item["currency"],
            "quantity":item["suggested_quantity"],"required_by":item["first_shortage_date"],"budget":item["purchase_budget"],
            "constraints":["Same sellable unit and currency", "Confirm delivery and quote validity", "Human approval required"],
            "mode":"synthetic-rules-only","email_sending_enabled":False}
        items.append(item)
    rank = {"REORDER":0,"EXPEDITE_EXISTING":1,"INCOMING_COVERED":2,"NO_RECENT_SALES":3,"SUFFICIENT":4}
    items.sort(key=lambda row:(rank[row["status"]],row["first_shortage_date"] or "9999",row["sku"]))
    return {"mode":"synthetic-rules-only","metadata":metadata,"items":items,
            "summary":{"products":len(items),"reorder":sum(row["status"]=="REORDER" for row in items),
                       "incoming_covered":sum(row["status"]=="INCOMING_COVERED" for row in items),
                       "quote_gaps":sum(row["suggested_quantity"]>0 and not row["selected_quote_id"] for row in items)},
            "connections":{"inventory":"Bundled synthetic snapshot","email":"Not connected","n8n":"Not connected","ai":"No AI calls in this review"}}


def draft_inquiry(item):
    brief = item["handoff"]
    return f"""DRAFT ONLY — synthetic scenario. No message has been sent.
Subject: Quotation request — {item['name']}

Please quote {brief['quantity']} of the following sellable unit: {brief['sellable_unit']}.
Currency: {brief['currency']}. Required arrival: {brief['required_by'] or 'to be agreed'}.
Please confirm the specification, pack size, MOQ, order multiple, VAT-exclusive unit price,
shipping and duty per sellable unit, delivery date, quote validity and payment terms.
Please state any certifications and whether you can supply the requested quantity.

This is a fictional demonstration, not a purchase commitment.
"""


def review_csv(report):
    output=io.StringIO(newline="")
    fields=("sku","name","sellable_unit","available","daily_sales","confirmed_incoming","overdue_quantity",
            "suggested_quantity","first_shortage_date","status","selected_quote_id","action")
    writer=csv.writer(output,lineterminator="\n")
    writer.writerow(fields)
    for item in report["items"]:
        writer.writerow(csv_safe(item.get(field)) for field in fields)
    return output.getvalue()
