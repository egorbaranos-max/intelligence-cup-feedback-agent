# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 12 | 12 | 10 | 2 |
| case_pdf | 0 | 0 | 0 | 0 |
| synthetic | 12 | 12 | 10 | 2 |

Model statuses and classes:

- all: statuses `{"needs_review": 1, "ok": 10, "unparseable_or_missing": 1}`; class presence `{"feature_request": 5, "incident": 2, "service_request": 4, "usability": 4}`.
- case_pdf: statuses `{}`; class presence `{}`.
- synthetic: statuses `{"needs_review": 1, "ok": 10, "unparseable_or_missing": 1}`; class presence `{"feature_request": 5, "incident": 2, "service_request": 4, "usability": 4}`.

Model verification (separate from extraction expectations):

A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.

- Calls: 7; valid contracts: 7; verdicts: `{"supported": 6, "unsupported": 1, "unclear": 0, "invalid": 0}`.
- Blocking violations: 0.
- `synthetic-fresh-01` / `intent_a754b3b489f044ec0cfd3620`: supported; blocking respected: True.
- `synthetic-fresh-01` / `intent_95828e0769cbd02ef687e6ca`: supported; blocking respected: True.
- `synthetic-fresh-05` / `intent_174b66241c3e98040d0893c0`: supported; blocking respected: True.
- `synthetic-fresh-07` / `intent_f7d8f0b5187844b641769f98`: supported; blocking respected: True.
- `synthetic-fresh-07` / `intent_19b2c9712449fd562e1f38c1`: supported; blocking respected: True.
- `synthetic-fresh-07` / `intent_e768a455ba31406ad58c339e`: supported; blocking respected: True.
- `synthetic-fresh-08` / `intent_1b467517251b44f917658a4d`: unsupported; blocking respected: True.

Focused checks:

- `syn07_two_separate_intents`: **not applicable**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **not applicable**. {"topic_ids_by_source": {"syn-01": [], "syn-02": [], "syn-03": [], "syn-04": []}, "snapshot": null}
- `syn10_invoices_separate_from_orders`: **not applicable**. {"orders_topic": null, "invoice_topics": []}
- `trusted_authorship_respected_by_raw_model`: **met**. {"violating_sources": [], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `synthetic-fresh-01` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `synthetic-fresh-02` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `synthetic-fresh-03` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `synthetic-fresh-04` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `synthetic-fresh-05` (synthetic): status `ok`, classes `service_request, usability`; kinds outside accepted set or no intents.
- `synthetic-fresh-07` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `synthetic-fresh-08` (synthetic): status `ok`, classes `feature_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `synthetic-fresh-09` (synthetic): status `ok`, classes `usability`; status differs.
- `synthetic-fresh-10` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 487 (char 486))
- `synthetic-fresh-12` (synthetic): status `ok`, classes `feature_request, incident`; invalid extraction contract.
  Contract: intents[1].evidence_refs[0].quote: no exact source match

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
