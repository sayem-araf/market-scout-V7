# Synthetic distributor dataset

**Every product, supplier, price, stock position, sale and quotation is invented.** No supplier was contacted. Supplier email addresses use the reserved `example.invalid` domain and must never be sent to an email connector.

The fixed snapshot is **1 October 2026**, with history from **1 April through 30 September 2026**. Dates intentionally stay fixed when the demo is opened later. All quantities refer to the exact `sellable_unit` in the product catalog.

| Input | Grain / key | Purpose |
| --- | --- | --- |
| `metadata.json` | One dataset | Snapshot, history range, seed and limitations |
| `products.json` | One row per `sku` | Unit, currency, planning rules, scenario prices and per-product budget |
| `inventory.json` | One row per `sku` and snapshot | On-hand stock and separately committed reservations |
| `sales.json` | Daily `SALE` aggregate per SKU, plus a separate `RETURN` record | 3,660 explicit daily aggregates (including zero-sales days) and one return; unique `record_id` |
| `incoming_orders.json` | One order line per `po_id` + `sku` | Ordered versus received quantities, expected date and status |
| `quotations.json` | One row per `quote_id` | Manually structured fictional quotations; not AI-extracted email replies |

These are operational inputs, not a fully reconciled warehouse ledger. Historical receipts and opening balances are not provided, so the current snapshot cannot be reconstructed from sales history. The last 30 days are controlled to make expected outcomes hand-checkable; older activity varies using a fixed random seed. This is not a realistic seasonal demand model or measured forecast.

## Rules

- Available = on hand − reserved. The forecast represents additional demand, separate from the already reserved stock.
- Daily baseline = total positive sales in the last 30 calendar days / 30. Returns are reported separately. Missing daily coverage fails validation rather than becoming zero demand.
- Confirmed incoming includes only outstanding units, due on or after the snapshot and within the product’s lead-time horizon. Already received units are included in on-hand stock and are not counted again. Cancelled, closed and overdue orders are excluded.
- Reorder point = baseline × (lead days + safety days).
- Stock position = available + eligible incoming. At or below the reorder point, order toward baseline × (lead + safety + review days), rounding up to the product’s order multiple.
- Projected receipts arrive before that day’s sales. A negative projected balance marks a potential cumulative shortage/backlog, not an observed stockout. If a counted incoming delivery arrives after an early shortage, flag expedition rather than propose a duplicate full order.
- Quote quantity must satisfy both the product and supplier multiples, supplier MOQ and the proposed requirement. Compare totals only for the same currency and sellable unit. Require complete costs, valid quotations, arrival no later than the first projected shortage, an acceptable margin and the per-product budget.
- Ranking selects the lowest total cost among eligible quotations. Supplier quality, capacity and compliance are not scored or verified. Output always requires human review.

Rebuild with `python3 scripts/generate_demo.py`. It uses no network or credentials. An independent, hand-specified answer key lives under `tests/fixtures/`; application code reads only the six whitelisted input files above. The key is not served to the browser or passed to an agent.

To substitute real inputs later, preserve keys, units, date coverage and field meanings, add a reviewed importer, and replace the demo-only validation boundary. Do not simply relabel synthetic values as real stock.
