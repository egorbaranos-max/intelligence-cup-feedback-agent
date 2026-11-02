# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 23 | 23 | 12 | 8 |
| case_pdf | 7 | 7 | 0 | 0 |
| synthetic | 16 | 16 | 12 | 8 |

Model statuses and classes:

- all: statuses `{"ok": 23}`; class presence `{"feature_request": 9, "incident": 8, "service_request": 6, "usability": 2}`.
- case_pdf: statuses `{"ok": 7}`; class presence `{"incident": 5, "service_request": 2}`.
- synthetic: statuses `{"ok": 16}`; class presence `{"feature_request": 9, "incident": 3, "service_request": 4, "usability": 2}`.

Focused checks:

- `syn07_two_separate_intents`: **met**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **not met**. {"topic_ids_by_source": {"syn-01": ["topic_f0a91bb5e864043b9f240557"], "syn-02": [], "syn-03": ["topic_f0a91bb5e864043b9f240557"], "syn-04": ["topic_f0a91bb5e864043b9f240557"]}, "snapshot": null}
- `syn10_invoices_separate_from_orders`: **not met**. {"orders_topic": null, "invoice_topics": ["topic_59df5a8ce4e56f32e3faf884"]}
- `trusted_authorship_respected_by_raw_model`: **not met**. {"violating_sources": ["case-01", "case-02", "case-03", "case-04", "case-05", "case-06", "case-07", "syn-09", "syn-13"], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `case-01` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review
- `case-02` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review
- `case-03` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review
- `case-04` (case_pdf): status `ok`, classes `service_request`; invalid extraction contract.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required; intents[1].origin: unverified user authorship; needs_review required
- `case-05` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review
- `case-06` (case_pdf): status `ok`, classes `service_request`; invalid extraction contract.
  Contract: status: unknown author requires needs_review
- `case-07` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review
- `syn-02` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `syn-05` (synthetic): status `ok`, classes `incident`; invalid extraction contract.
  Contract: intents[0]: unexpected or missing fields
- `syn-08` (synthetic): status `ok`, classes `feature_request`; invalid extraction contract.
  Contract: intents[0]: unexpected or missing fields
- `syn-09` (synthetic): status `ok`, classes `feature_request`; invalid extraction contract; explicit feature flag differs; status differs.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required
- `syn-10` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents.
- `syn-12` (synthetic): status `ok`, classes `usability`; status differs.
- `syn-13` (synthetic): status `ok`, classes `feature_request`; invalid extraction contract; explicit feature flag differs.
  Contract: intents[0].origin: unverified user authorship; needs_review required
- `syn-14` (synthetic): status `ok`, classes `service_request`; status differs.

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
