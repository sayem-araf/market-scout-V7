#!/usr/bin/env python3
"""MarketScout: source a product, calculate its margin, and export sales files."""

import argparse
import csv
import json
import os
from dataclasses import asdict, dataclass
from math import floor
from pathlib import Path
from typing import Any, Dict, List

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


@dataclass
class SourcingRecord:
    product_keyword: str
    product_title: str
    supplier_name: str
    supplier_url: str
    wholesale_price: float
    currency: str
    moq: int
    retail_benchmark: float
    shipping_per_unit: float
    duty_per_unit: float
    source_urls: List[str]
    notes: str = ""
    category: str = "Safety & PPE / Disposable Gloves"


def extract_sourcing_data(product_keyword: str, api_key: str, model: str = "gemini-3.6-flash",
                          region: str = "EU") -> SourcingRecord:
    """Use Gemini search grounding to return one normalized supplier offer."""
    if genai is None or types is None:
        raise RuntimeError("google-genai is required for live sourcing")

    client = genai.Client(api_key=api_key)
    schema = {
        "type": "OBJECT",
        "properties": {
            "product_title": {"type": "STRING"},
            "supplier_name": {"type": "STRING"},
            "supplier_url": {"type": "STRING"},
            "wholesale_price": {"type": "NUMBER"},
            "currency": {"type": "STRING"},
            "moq": {"type": "INTEGER"},
            "retail_benchmark": {"type": "NUMBER"},
            "shipping_per_unit": {"type": "NUMBER"},
            "duty_per_unit": {"type": "NUMBER"},
            "source_urls": {"type": "ARRAY", "items": {"type": "STRING"}},
            "notes": {"type": "STRING"},
        },
        "required": [
            "product_title", "supplier_name", "supplier_url", "wholesale_price",
            "currency", "moq", "retail_benchmark", "shipping_per_unit",
            "duty_per_unit", "source_urls", "notes",
        ],
    }
    prompt = f"""Find a viable wholesale supplier for: {product_keyword}

Return exactly one offer in the requested JSON schema. Use search grounding.
Prices must be per sellable unit in one currency. For the {region} region, use EUR.
retail_benchmark is the current
consumer selling price for a comparable unit, shipping_per_unit and duty_per_unit
must be numeric estimates in the same currency. Use 0 only when the cost is truly
not applicable, and explain uncertainty in notes. Include URLs used as evidence."""
    chat = client.chats.create(
        model=model,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    response = chat.send_message(prompt)
    data = json.loads(response.text)
    data["product_keyword"] = product_keyword
    return SourcingRecord(**data)


def calculate_margin(sourcing: SourcingRecord, vat_rate: float = 0.20,
                     target_margin: float = 0.60, fixed_costs: float = 0.0,
                     freight_rate: float = 0.15) -> Dict[str, Any]:
    """Calculate unit economics without asking an LLM to make arithmetic decisions."""
    if sourcing.retail_benchmark <= 0:
        raise ValueError("retail_benchmark must be greater than zero")
    if any(value < 0 for value in (sourcing.wholesale_price, sourcing.shipping_per_unit, sourcing.duty_per_unit)):
        raise ValueError("sourcing costs cannot be negative")

    retail_price = float(sourcing.retail_benchmark)
    vat_amount = retail_price * vat_rate
    net_retail_price = retail_price - vat_amount
    landed_cost = sourcing.wholesale_price * (1 + freight_rate)
    gross_profit = retail_price - landed_cost
    gross_margin = gross_profit / retail_price
    breakeven_units = (fixed_costs / gross_profit) if gross_profit > 0 else None

    return {
        **asdict(sourcing),
        "vat_rate": vat_rate,
        "vat_amount": round(vat_amount, 2),
        "net_retail_price": round(net_retail_price, 2),
        "freight_rate": freight_rate,
        "landed_cost": round(landed_cost, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin": round(gross_margin, 4),
        "gross_margin_percent": floor(gross_margin * 1000) / 10,
        "fixed_costs": fixed_costs,
        "breakeven_units": round(breakeven_units, 2) if breakeven_units is not None else None,
        "target_margin": target_margin,
        "decision": "GO" if gross_margin >= target_margin else "NO-GO",
    }


def export_artifacts(result: Dict[str, Any], output_dir: Path) -> None:
    """Write the clean inventory row and a ready-to-send supplier RFQ."""
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_row = {
        "sku_name": result["product_title"],
        "category": result["category"],
        "est_wholesale_eur": f"{result['wholesale_price']:.2f}",
        "target_retail_eur": f"{result['retail_benchmark']:.2f}",
        "moq": result["moq"],
        "margin_pct": result["gross_margin_percent"],
        "status": f"[{result['decision']}]",
    }
    with (output_dir / "catalog_entry.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=catalog_row.keys())
        writer.writeheader()
        writer.writerow(catalog_row)

    sources = "\n".join(f"- {url}" for url in result["source_urls"])
    rfq = f"""Subject: RFQ - {result['product_title']}

Hello {result['supplier_name']},

Please provide your best quotation for {result['product_title']} for delivery to the Nordics.

Requested details:
- Product specification and available variants
- Sample units for evaluation before the first commercial order
- Tiered unit pricing for 500, 2,000, and 10,000 units
- Minimum order quantity and production lead time
- Delivery lead times and shipping cost to the Nordics
- Packaging, certifications, samples, and payment terms

Our initial market benchmark is {result['retail_benchmark']:.2f} {result['currency']} per unit.
Please confirm that the quotation is current and include the quote validity period.

Regards,
MarketScout Procurement

Research references:
{sources}
"""
    (output_dir / "supplier_rfq.txt").write_text(rfq, encoding="utf-8")


def sample_record(keyword: str, region: str) -> SourcingRecord:
    """Provide deterministic input for local pipeline checks and demos."""
    if region.upper() == "EU":
        return SourcingRecord(keyword, "Nitras Medical BIG BLUE WAVE Nitrile Disposable Gloves (200 pcs)",
                              "Demo EU PPE Supplier", "https://example.com/supplier",
                              5.26, "EUR", 100, 14.90, 0.0, 0.0,
                              ["https://example.com/source"], "Demo data; replace with a live grounded result.")
    return SourcingRecord(keyword, keyword.title(), "Demo Supplier", "https://example.com/supplier",
                          2.00, "USD", 100, 10.00, 0.0, 0.0,
                          ["https://example.com/source"], "Demo data; replace with a live grounded result.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Source a product and export margin-ready commerce artifacts.")
    parser.add_argument("product_keyword", help="Product to source, such as 'heavy-duty nitrile gloves'")
    parser.add_argument("--region", default="EU", help="Sourcing and delivery region (default: EU)")
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="Directory for the two output files")
    parser.add_argument("--vat-rate", type=float, default=0.20, help="VAT rate as a decimal (default: 0.20)")
    parser.add_argument("--target-margin", type=float, default=0.60, help="Required gross margin as a decimal")
    parser.add_argument("--fixed-costs", type=float, default=0.0, help="Fixed costs used for breakeven units")
    parser.add_argument("--api-key", help="Gemini API key; otherwise use GEMINI_API_KEY")
    parser.add_argument("--model", default="gemini-3.6-flash", help="Gemini model")
    parser.add_argument("--dry-run", action="store_true", help="Use deterministic sample sourcing data")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    print("[Stage 1] Extracting supplier data with Gemini search grounding..." if not args.dry_run
          else "[Stage 1] Loading deterministic demo sourcing data...")
    if args.dry_run:
        sourcing = sample_record(args.product_keyword, args.region)
    elif not api_key:
        parser.error("a Gemini API key is required unless --dry-run is used")
    else:
        sourcing = extract_sourcing_data(args.product_keyword, api_key, args.model, args.region)

    print("[Stage 2] Calculating deterministic margin...")
    freight_rate = 0.15 if args.region.upper() == "EU" else 0.0
    result = calculate_margin(sourcing, args.vat_rate, args.target_margin, args.fixed_costs, freight_rate)
    print("[Stage 3] Exporting catalog entry and supplier RFQ...")
    export_artifacts(result, args.output_dir)
    currency = "€" if args.region.upper() == "EU" else result["currency"]
    verdict = f"[{result['decision']}]"
    reason = "Exceeds" if result["decision"] == "GO" else "Falls below"
    print(f"Product: {result['product_title']} ({args.region.upper()})")
    print(f"Benchmark Retail Price: {currency}{result['retail_benchmark']:.2f} / box")
    print(f"Estimated Wholesale Cost: {currency}{result['wholesale_price']:.2f} / box")
    print(f"Estimated Landed Cost (+{result['freight_rate']:.0%} freight/handling): {currency}{result['landed_cost']:.2f} / box")
    print(f"Net Margin: {currency}{result['gross_profit']:.2f} ({result['gross_margin_percent']:.1f}%)")
    print(f"Verdict: {verdict} - {reason} {args.target_margin:.0%} target margin.")
    print(f"Wrote {args.output_dir / 'catalog_entry.csv'}")
    print(f"Wrote {args.output_dir / 'supplier_rfq.txt'}")


if __name__ == "__main__":
    main()
