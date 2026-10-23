# n8n review workflow

This adds a manual n8n orchestration workflow around MarketScout's Python tools. It is **not three autonomous AI agents**: inventory and decision checks remain deterministic; live supplier investigation can use the existing bounded Gemini agent. The default is an offline demo with no AI calls.

**Verified:** the exported workflow was imported and executed successfully in n8n 2.44.6 against the containerized adapter. All four nodes completed in offline mode; see [the recorded validation summary](../docs/n8n-validation.json). A real-key live research run is still pending.

## Start locally with Docker

1. Copy `.env.example` to `.env` in this folder. Set `MARKETSCOUT_AUTOMATION_TOKEN` to a new random token of at least 32 characters. For example, generate one with `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`. Keep it private.
2. Run `docker compose up -d --build` from this folder.
3. Open http://localhost:5678 and finish n8n's local account setup.
4. Import `marketscout-review.json` using **Import from File**.
5. Create an n8n **Header Auth** credential: name `Authorization`, value `Bearer YOUR_TOKEN`. Select that credential in both HTTP Request nodes. The token must match the adapter's environment.
6. Click **Execute workflow**. Inspect the output of **Investigate and prepare review brief**.

The workflow reads inventory, stops if no replenishment is needed, otherwise investigates the first priority SKU and produces a human-review brief. One SKU per run deliberately bounds cost and keeps review manageable. It does not process the entire catalog or automatically select a different SKU on the next execution. To investigate another SKU, edit the POST node's SKU expression.

The adapter service has no published host port. n8n's editor is bound to localhost only. Docker Compose supplies a dedicated network; do not publish either service on the internet. The original dashboard stays separate and unchanged.

## What to inspect

- `purchasing_brief`: synthetic inventory need, quantity, budget and required date.
- `existing_quotation_review`: deterministic ranking of the existing synthetic quotes.
- `supplier_research`: executed tool trace, candidate economics and evidence.
- `review_checks`: items a person must verify before adding a new quotation.
- `inquiry_draft`: unsent text; no recipient lookup or email connection.

An offline research offer is a generic fictional example. It is not evidence for the selected SKU. Live research is also **not inserted into the existing quotation comparison**: its pack size, lead time, validity and commercial terms must first be established. Historical synthetic inventory dates cannot support a current buying decision.

## Optional live research

Only after reviewing the offline output, set `MARKETSCOUT_ALLOW_LIVE=1` and `GEMINI_API_KEY` in the adapter environment and recreate the adapter. Change the POST node's `mode` from `demo` to `live`. This sends the product query and assumptions to Google's API and may incur costs. No real-key run has been verified for this project. No email sending or purchasing is enabled in either mode.

## Failure handling

HTTP failures stop n8n. Automatic retries are disabled. A request ID derived from the n8n execution ID prevents duplicate processing during the adapter's lifetime; repeated IDs with changed inputs are rejected. Failures are cached too, so a retry does not silently repeat paid research. The adapter accepts one investigation at a time and at most 50 distinct requests before a deliberate restart.

This cache is **not durable**: a restart clears it. Starting a new n8n execution creates a new request ID and may make new paid calls. n8n execution history can retain supplier and commercial data; review its retention/access settings before using non-demo information. The API does not claim a production audit ledger or durable job queue.

The existing dashboard is not an n8n execution monitor. Review workflow execution status in n8n. Next extensions are persisted run history, validated quotation intake and an explicit email approval workflow.

## References

- [Official workflow import/export documentation](https://docs.n8n.io/workflows/export-import/)
- [Official Docker installation documentation](https://docs.n8n.io/hosting/installation/docker/)
