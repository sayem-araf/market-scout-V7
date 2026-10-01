# MarketScout

MarketScout turns a product keyword into a sourcing decision and two operational files.

## Pipeline

1. **AI sourcing extraction**: Gemini 3.6 Flash uses Google Search grounding to return one structured supplier offer with wholesale price, MOQ, retail benchmark, shipping, duty, and evidence URLs.
2. **Deterministic margin engine**: Python calculates VAT, landed cost, net retail price, gross profit, gross margin, breakeven units, and a `GO`/`NO-GO` decision against the target margin.
3. **Artifact exporter**: writes `catalog_entry.csv` and `supplier_rfq.txt`.

## Setup

Python 3.9+ is recommended. Live sourcing requires the Gemini SDK:

```bash
pip install google-genai
export GEMINI_API_KEY="your-api-key-here"
```

## Usage

Run a live, search-grounded sourcing pass:

```bash
python market_scout.py "heavy-duty nitrile gloves" \
  --region EU \
  --output-dir outputs \
  --vat-rate 0.20 \
  --target-margin 0.60 \
  --fixed-costs 500
```

The API key can also be passed with `--api-key`. Use `--model` to select a different Gemini model.

Run the local deterministic check without an API key:

```bash
python market_scout.py "Nitras Medical nitrile gloves 200 pcs" \
  --region EU \
  --target-margin 0.60 \
  --vat-rate 0.24 \
  --dry-run \
  --output-dir outputs
```

## Outputs

- `catalog_entry.csv`: one clean inventory row with columns `sku_name`, `category`, `est_wholesale_eur`, `target_retail_eur`, `moq`, `margin_pct`, and `status`.
- `supplier_rfq.txt`: ready-to-send Nordic supplier inquiry requesting samples, 500/2,000/10,000-unit pricing, and delivery lead times.

Prices must be per sellable unit and all cost fields must use the same currency. VAT and target margin are decimal rates, so `0.20` means 20%.



<img width="615" height="227" alt="01_Pipeline_Run_And_Margin_Gate" src="https://github.com/user-attachments/assets/62402e1f-ba05-479f-baab-1f73cdda8833" />



<img width="979" height="52" alt="02_Exported_Catalog_Entry" src="https://github.com/user-attachments/assets/06f13091-85d2-424b-84e2-879949f3b485" />


<img width="1013" height="403" alt="03_Generated_Supplier_RFQ" src="https://github.com/user-attachments/assets/1be0df28-5c11-47a5-b3c6-e9334e92b73e" />

