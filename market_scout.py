#!/usr/bin/env python3
"""Supplier research and deterministic, scenario-based unit economics."""
import argparse
import csv
import json
import os
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit


@dataclass
class SourcingRecord:
    product_keyword: str
    product_title: str
    supplier_name: str
    supplier_url: str
    wholesale_price: float | None
    currency: str
    moq: int | None
    retail_benchmark: float | None
    shipping_per_unit: float | None
    duty_per_unit: float | None
    source_urls: list[str]
    notes: str = ""
    category: str = "Unclassified"


def number(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{name} must be a number")
    value = Decimal(str(value))
    if not value.is_finite() or value < minimum or value > Decimal("1000000000000"):
        raise ValueError(f"{name} must be finite and between {minimum} and 1000000000000")
    return value


def safe_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        parts = urlsplit(value)
        return parts.scheme in ("http", "https") and bool(parts.hostname) and not parts.username and not parts.password
    except ValueError:
        return False


def validate_record(record):
    for field in ("product_keyword", "product_title", "supplier_name", "notes", "category"):
        value = getattr(record, field)
        if not isinstance(value, str) or len(value) > 6000:
            raise ValueError(f"Invalid {field}")
    if not re.fullmatch(r"[A-Z]{3}", record.currency):
        raise ValueError("Currency must be a three-letter uppercase code")
    if record.supplier_url and not safe_url(record.supplier_url):
        raise ValueError("Invalid supplier URL")
    if not isinstance(record.source_urls, list) or len(record.source_urls) > 30 or any(not safe_url(url) for url in record.source_urls):
        raise ValueError("Invalid source URLs")
    for field in ("wholesale_price", "retail_benchmark", "shipping_per_unit", "duty_per_unit"):
        if getattr(record, field) is not None:
            number(getattr(record, field), field)
    if record.retail_benchmark is not None and record.retail_benchmark <= 0:
        raise ValueError("Retail benchmark must be positive")
    if record.moq is not None and (type(record.moq) is not int or not 1 <= record.moq <= 1000000000):
        raise ValueError("MOQ must be a positive integer")
    return record


def calculate_margin(sourcing, vat_rate=0.20, target_margin=0.60, fixed_costs=0.0, freight_rate=0.0):
    """Gross retail includes scenario VAT; costs exclude recoverable VAT. No FX conversion."""
    validate_record(sourcing)
    vat = number(vat_rate, "VAT rate")
    target = number(target_margin, "Target margin")
    fixed = number(fixed_costs, "Fixed costs")
    freight = number(freight_rate, "Supplemental freight rate")
    if vat > 1 or target > 1 or freight > 1:
        raise ValueError("Rates must be between 0 and 1")
    missing = [name for name in ("wholesale_price", "retail_benchmark", "shipping_per_unit", "duty_per_unit", "moq") if getattr(sourcing, name) is None]
    result = {**asdict(sourcing), "vat_rate": float(vat), "target_margin": float(target), "fixed_costs": float(fixed),
              "freight_rate": float(freight), "missing_fields": missing, "decision": "INCOMPLETE",
              **dict.fromkeys(("vat_amount", "net_retail_price", "landed_cost", "gross_profit", "gross_margin", "gross_margin_percent", "breakeven_units", "moq_cost"))}
    if missing:
        return result
    wholesale = number(sourcing.wholesale_price, "Wholesale price")
    gross = number(sourcing.retail_benchmark, "Retail price")
    net = gross / (1 + vat)
    landed = wholesale + number(sourcing.shipping_per_unit, "Shipping") + number(sourcing.duty_per_unit, "Duty") + wholesale * freight
    profit = net - landed
    margin = profit / net
    money = lambda value: float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    result.update(vat_amount=money(gross-net), net_retail_price=money(net), landed_cost=money(landed), gross_profit=money(profit),
                  gross_margin=float(margin), gross_margin_percent=float(margin*100),
                  breakeven_units=int((fixed/profit).to_integral_value(rounding=ROUND_CEILING)) if profit > 0 else None,
                  moq_cost=money(landed*sourcing.moq), decision="GO" if margin >= target else "NO-GO")
    return result


def csv_safe(value):
    text = str(value) if value is not None else ""
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def artifacts(result):
    import io
    output = io.StringIO(newline="")
    fields = ["sku_name", "category", "currency", "est_wholesale", "target_retail", "moq", "margin_pct", "status"]
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(fields)
    writer.writerow([csv_safe(result[key]) for key in ("product_title", "category", "currency", "wholesale_price", "retail_benchmark", "moq", "gross_margin_percent", "decision")])
    rfq = f"""DRAFT ONLY — review before sending. Nothing has been sent.
Subject: RFQ - {result['product_title']}

Hello {result['supplier_name']},

Please confirm the specification, sellable unit / pack size and current price for {result['product_title']}.
Please provide MOQ, sample availability, tier pricing, delivery terms, destination-specific shipping,
duties, lead time, certifications, payment terms and quotation validity.
Please identify whether quoted prices include tax, and the currency ({result['currency']}).

Unresolved input fields: {', '.join(result['missing_fields']) or 'None; source evidence still requires human verification'}.
Research references (not verified quotations):
""" + "\n".join(result["source_urls"])
    return {"catalog_entry.csv": output.getvalue(), "supplier_rfq.txt": rfq,
            "research.json": json.dumps(result, indent=2, allow_nan=False)}


def export_artifacts(result, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in artifacts(result).items():
        (output_dir / name).write_text(content, encoding="utf-8")


def sample_record(keyword, region="EU"):
    return SourcingRecord(keyword, "Fictional industrial gloves — box of 200", "Fictional supplier", "https://example.com/supplier",
                          5.26, "EUR" if region.upper() == "EU" else "USD", 100, 14.90, 1.20, 0.0,
                          ["https://example.com/fictional-offer"], "Invented demonstration values. Not a supplier quote.")


def extract_sourcing_data(product_keyword, api_key, model="gemini-3.6-flash", region="EU"):
    from scout_agent import GroundedResearch
    return GroundedResearch(api_key, model).research(product_keyword, region, "Find one offer; record unknown values as null.")[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product_keyword")
    parser.add_argument("--region", default="EU")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--vat-rate", type=float, default=.20)
    parser.add_argument("--target-margin", type=float, default=.60)
    parser.add_argument("--fixed-costs", type=float, default=0)
    parser.add_argument("--api-key")
    parser.add_argument("--model", default="gemini-3.6-flash")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    key = args.api_key or os.getenv("GEMINI_API_KEY")
    if not args.dry_run and not key:
        parser.error("Set GEMINI_API_KEY or use --dry-run")
    record = sample_record(args.product_keyword, args.region) if args.dry_run else extract_sourcing_data(args.product_keyword, key, args.model, args.region)
    result = calculate_margin(record, args.vat_rate, args.target_margin, args.fixed_costs)
    export_artifacts(result, args.output_dir)
    print(json.dumps(result, indent=2, allow_nan=False))
    print(f"Draft artifacts written to {args.output_dir}")


if __name__ == "__main__":
    main()
