# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 23 | 23 | 20 | 14 |
| case_pdf | 7 | 7 | 7 | 5 |
| synthetic | 16 | 16 | 13 | 9 |

Model statuses and classes:

- all: statuses `{"needs_review": 9, "ok": 14}`; class presence `{"feature_request": 10, "incident": 9, "service_request": 5, "usability": 4}`.
- case_pdf: statuses `{"needs_review": 7}`; class presence `{"incident": 6, "service_request": 2}`.
- synthetic: statuses `{"needs_review": 2, "ok": 14}`; class presence `{"feature_request": 10, "incident": 3, "service_request": 3, "usability": 4}`.

Model verification (separate from extraction expectations):

A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.

- Calls: 10; valid contracts: 9; verdicts: `{"supported": 7, "unsupported": 2, "unclear": 0, "invalid": 1}`.
- Blocking violations: 0.
- `syn-01` / `intent_d840cffde647c7f88c90dbb9`: supported; blocking respected: True.
- `syn-03` / `intent_813150caefa13ef17825be59`: supported; blocking respected: True.
- `syn-04` / `intent_ef954dfb32e99b91059c0625`: supported; blocking respected: True.
- `syn-08` / `intent_1d6a86939d1eb376aa48a147`: supported; blocking respected: True.
- `syn-10` / `intent_6a337d7071c86eb5533339bf`: supported; blocking respected: True.
- `syn-10` / `intent_5e4e232dcf8be028375315a9`: unsupported; blocking respected: True.
- `syn-11` / `intent_d9a87bb748876d860d18bd1f`: unsupported; blocking respected: True.
- `syn-12` / `intent_8a086c118233ff3ad38a8aed`: supported; blocking respected: True.
- `syn-14` / `intent_595449ffc3d7197ef143d59f`: invalid; blocking respected: True.
- `syn-16` / `intent_693648af50848196b2c52e57`: supported; blocking respected: True.

Focused checks:

- `syn07_two_separate_intents`: **not met**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **not met**. {"topic_ids_by_source": {"syn-01": ["topic_f0a91bb5e864043b9f240557"], "syn-02": [], "syn-03": ["topic_f0a91bb5e864043b9f240557"], "syn-04": ["topic_f0a91bb5e864043b9f240557"]}, "snapshot": null}
- `syn10_invoices_separate_from_orders`: **not met**. {"orders_topic": null, "invoice_topics": ["topic_59df5a8ce4e56f32e3faf884"]}
- `trusted_authorship_respected_by_raw_model`: **not met**. {"violating_sources": ["syn-09"], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `case-03` (case_pdf): status `needs_review`, classes `incident, service_request`; kinds outside accepted set or no intents.
- `case-06` (case_pdf): status `needs_review`, classes `incident`; kinds outside accepted set or no intents.
- `syn-02` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `syn-07` (synthetic): status `ok`, classes `feature_request, incident`; invalid extraction contract.
  Contract: intents[1].evidence_refs[0].quote: no exact source match
- `syn-09` (synthetic): status `needs_review`, classes `feature_request`; invalid extraction contract; explicit feature flag differs.
  Contract: intents[0].origin: unverified user authorship; needs_review required
- `syn-10` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `syn-12` (synthetic): status `ok`, classes `usability`; status differs.
- `syn-13` (synthetic): status `needs_review`, classes `feature_request`; invalid extraction contract.
  Contract: intents[0].origin: invalid origin
- `syn-14` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents; explicit feature flag differs; status differs.

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
