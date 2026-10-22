#!/usr/bin/env python3
"""Rebuild fictional operational inputs. Expected decisions are independent test fixtures."""
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "demo"
AS_OF = date(2026, 10, 1)
SEED = 221026


def write(name, value, folder=DEST):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def generate(destination=DEST, expected_folder=ROOT/"tests"/"fixtures"):
    rng = random.Random(SEED)
    names = [
        ("Industrial nitrile gloves", "box of 200", 10, 50, 10, 14, 7),
        ("Packing tape", "roll", 5, 20, 0, 10, 5),
        ("Microfibre cloths", "pack of 10", 3, 12, 0, 14, 7),
        ("Archive labels", "sheet of 100", 0, 500, 0, 14, 7),
        ("Safety glasses", "pair", 2, 10, 0, 10, 5),
        ("Disposable aprons", "pack of 100", 4, 20, 0, 14, 7),
        ("Cleaning wipes", "tub of 100", 4, 24, 0, 10, 5),
        ("Parcel mailers", "pack of 50", 6, 90, 0, 20, 7),
        ("Work gloves", "pair", 4, 20, 0, 10, 5),
        ("Shipping labels", "roll of 500", 2, 200, 0, 7, 5),
        ("Stretch film", "roll", 3, 180, 0, 10, 5),
        ("Paper towels", "pack of 6", 4, 240, 0, 14, 7),
        ("Floor cleaner", "5 litre bottle", 2, 140, 0, 14, 7),
        ("Bin liners", "roll of 20", 5, 300, 0, 10, 5),
        ("Dust masks", "box of 20", 2, 150, 0, 14, 7),
        ("Hand soap", "1 litre bottle", 3, 180, 0, 10, 5),
        ("Cable ties", "pack of 100", 1, 80, 0, 10, 5),
        ("Bubble wrap", "10 metre roll", 2, 150, 0, 10, 5),
        ("Marker pens", "pack of 4", 1, 100, 0, 10, 5),
        ("Packing paper", "5 kg bundle", 2, 150, 0, 10, 5),
    ]
    products, inventory, sales = [], [], []
    start = date(2026, 4, 1)
    for index, (name, unit, daily, stock, reserved, lead, safety) in enumerate(names, 1):
        sku = f"SKU-{index:03d}"
        products.append(dict(sku=sku, name=name, sellable_unit=unit, currency="EUR", retail_price_gross="24.00",
                             vat_rate="0.20", target_margin="0.40", lead_days=lead, safety_days=safety,
                             review_days=14, order_multiple=10, purchase_budget="1000.00" if index == 5 else "10000.00"))
        inventory.append(dict(sku=sku, on_hand=stock, reserved=reserved, snapshot_date=AS_OF.isoformat()))
        for day in range((AS_OF-start).days):
            when = start + timedelta(days=day)
            # The final 30 calendar days are controlled for hand-checkable outcomes.
            units = daily if when >= AS_OF-timedelta(days=30) else max(0, (daily or 1)+rng.choice([-1, 0, 0, 1]))
            sales.append(dict(record_id=f"S-{index:03d}-{day:03d}", sku=sku, date=when.isoformat(), kind="SALE", quantity=units))
        # A historical customer return must not be treated as negative future demand.
        if index == 1:
            sales.append(dict(record_id="R-001", sku=sku, date="2026-09-28", kind="RETURN", quantity=2))
    incoming = [
        dict(po_id="PO-001", sku="SKU-002", ordered=200, received=0, due_date="2026-10-03", status="CONFIRMED"),
        dict(po_id="PO-002", sku="SKU-003", ordered=100, received=40, due_date="2026-09-25", status="CONFIRMED"),
        dict(po_id="PO-003", sku="SKU-011", ordered=100, received=100, due_date="2026-09-29", status="CLOSED"),
        dict(po_id="PO-004", sku="SKU-009", ordered=500, received=0, due_date="2026-10-02", status="CANCELLED"),
        dict(po_id="PO-005", sku="SKU-015", ordered=80, received=0, due_date="2026-11-20", status="CONFIRMED"),
    ]
    quotations = []
    def quote(identifier, index, supplier, price, shipping, lead, moq=10, unit=None, currency="EUR", valid="2026-10-15"):
        product = products[index-1]
        quotations.append(dict(quote_id=identifier, sku=product["sku"], supplier=supplier,
            supplier_email=supplier.lower().replace(" ", "-")+"@example.invalid", currency=currency,
            sellable_unit=unit or product["sellable_unit"], wholesale_price=price, shipping_per_unit=shipping,
            duty_per_unit="0.00", moq=moq, order_multiple=10, lead_days=lead, valid_until=valid,
            evidence="Fictional supplier quotation " + identifier + "; no external supplier contacted."))
    quote("Q-001-A",1,"Fictional Pine Supply","5.26","1.20",3,100)
    quote("Q-001-B",1,"Fictional Lake Supply","4.90","2.10",2,100)
    quote("Q-003-A",3,"Fictional Birch Supply","3.00","0.50",2)
    quote("Q-005-A",5,"Fictional Bulk Supply","5.00","0.20",2,500)
    quote("Q-006-A",6,"Fictional Pack Supply","3.00","0.50",2,unit="pack of 200")
    quote("Q-007-A",7,"Fictional Coast Supply","4.00",None,2)
    quote("Q-008-A",8,"Fictional Budget Supply","2.00","5.00",3)
    quote("Q-008-B",8,"Fictional Clear Supply","3.00","1.00",3)
    quote("Q-009-A",9,"Fictional Slow Supply","2.00","0.50",14)
    quote("Q-009-B",9,"Fictional Quick Supply","3.00","0.70",2)
    quote("Q-001-C",1,"Fictional Foreign Supply","2.00","0.50",2,currency="USD")
    quote("Q-001-D",1,"Fictional Old Supply","1.00","0.10",1,valid="2026-09-30")
    metadata = dict(dataset_id="marketscout-distributor-v1", synthetic=True, seed=SEED, as_of=AS_OF.isoformat(),
        history_start=start.isoformat(), history_end="2026-09-30", demand_window_days=30,
        description="Invented operational snapshot and independent history; not a ledger-reconciled stock movement simulation.",
        units="All stock, sales and order quantities use each product's exact sellable unit.",
        limitations=["Constant last-30-day sales baseline; not a trained or validated demand forecast.",
                      "Confirmed receipts assumed available at start of due date; overdue or cancelled quantities are not available stock.",
                      "Received purchase-order quantities are already included in the inventory snapshot.",
                      "Reservations are deducted once. Historical returns are reported separately, not netted from forward demand.",
                      "No supplier verification, emails, tax determination or real business outcomes."])
    for name, rows in [("metadata.json",metadata),("products.json",products),("inventory.json",inventory),
                       ("sales.json",sales),("incoming_orders.json",incoming),("quotations.json",quotations)]:
        write(name, rows, destination)
    # Hand-specified expectations, never imported by application code or returned by the API.
    write("inventory_expected.json",{
        "SKU-001":{"status":"REORDER", "suggested_quantity":310, "daily_sales":10, "selected_quote_id":"Q-001-A"},
        "SKU-002":{"status":"INCOMING_COVERED", "suggested_quantity":0, "daily_sales":5, "selected_quote_id":None},
        "SKU-003":{"status":"REORDER", "suggested_quantity":100, "overdue_quantity":60, "selected_quote_id":"Q-003-A"},
        "SKU-004":{"status":"NO_RECENT_SALES", "suggested_quantity":0, "selected_quote_id":None},
        "SKU-005":{"status":"REORDER", "suggested_quantity":50, "selected_quote_id":None},
        "SKU-006":{"status":"REORDER", "selected_quote_id":None},
        "SKU-007":{"status":"REORDER", "selected_quote_id":None},
        "SKU-008":{"status":"REORDER", "selected_quote_id":"Q-008-B"},
        "SKU-009":{"status":"REORDER", "selected_quote_id":"Q-009-B"}
    }, expected_folder)
    print(f"Created {len(products)} products, {len(sales)} sales/return rows, {len(incoming)} incoming orders and {len(quotations)} fictional quotations.")


if __name__ == "__main__":
    generate()
