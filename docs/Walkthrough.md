# 60–90 second walkthrough

1. Introduce the problem: a supplier price is not enough to make a sourcing decision; unit size, shipping, duty and evidence matter.
2. Open the dashboard and explicitly call it the fictional offline demonstration. Click Explore fictional demo.
3. Show the candidate and the 48% margin versus the 60% target. Explain that Python strips the scenario VAT from gross retail and includes shipping and duty.
4. Expand the second trace step: shipping is missing, so the calculation is INCOMPLETE. The next scripted research call resolves the fictional gap. In live mode Gemini chooses those tool calls.
5. Show field-specific sources and the human-review warning. Explain that citations still need checking; no purchase is approved.
6. Download the inquiry draft or full evidence/trace. Close with what is verified: the local workflow, calculations and mocked live adapter; real-key supplier research is the next validation step.

Do not describe this recording as a live AI investigation unless you actually run live mode and verify the sources.

## Inventory extension (separate 60-second clip)

1. Open `/inventory` and identify the fixed synthetic snapshot, 20 products and 7 replenishment candidates. State that this screen runs Python rules, not multiple live AI agents.
2. Filter to incoming-covered stock: packing tape needs no duplicate order because 200 confirmed units arrive before the projected gap.
3. Select parcel mailers. Show that the €2 wholesale offer lands at €7 after shipping, while the €3 offer lands at €4; the lower total-cost option is proposed for human review. These are fictional quotations.
4. Select cleaning wipes: shipping is unknown, so the offer remains ineligible. Show the inquiry draft and purchasing brief. Nothing has been sent.
5. Explain the next integration: n8n and model-based agents will use these tested rules and handoffs once credentials and an authenticated adapter are configured. Do not claim those connections are active.
