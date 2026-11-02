# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 48 | 48 | 46 | 28 |
| case_pdf | 0 | 0 | 0 | 0 |
| synthetic | 48 | 48 | 46 | 28 |

Model statuses and classes:

- all: statuses `{"needs_review": 4, "ok": 43, "unparseable_or_missing": 1}`; class presence `{"feature_request": 30, "hypothesis": 1, "incident": 6, "service_request": 7, "unknown": 1, "usability": 11}`.
- case_pdf: statuses `{}`; class presence `{}`.
- synthetic: statuses `{"needs_review": 4, "ok": 43, "unparseable_or_missing": 1}`; class presence `{"feature_request": 30, "hypothesis": 1, "incident": 6, "service_request": 7, "unknown": 1, "usability": 11}`.

Model verification (separate from extraction expectations):

A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.

- Calls: 37; valid contracts: 36; verdicts: `{"supported": 35, "unsupported": 1, "unclear": 0, "invalid": 1}`.
- Blocking violations: 0.
- `hv2_001` / `intent_f15e4e7f4c249b3cd9ce53a7`: supported; blocking respected: True.
- `hv2_002` / `intent_c00afdc6008cdab3c7a22cf0`: supported; blocking respected: True.
- `hv2_002` / `intent_f63fd2c9fffbbc502971540e`: supported; blocking respected: True.
- `hv2_003` / `intent_4119e5e24c41f5b483c9527f`: supported; blocking respected: True.
- `hv2_004` / `intent_3d583cacbd3bbbfd8057a388`: supported; blocking respected: True.
- `hv2_005` / `intent_202a699c5ff925b09c931581`: supported; blocking respected: True.
- `hv2_007` / `intent_70b261bf1298336a8397f40a`: supported; blocking respected: True.
- `hv2_009` / `intent_845bd63568ecfeef9c3c703e`: supported; blocking respected: True.
- `hv2_011` / `intent_fd57e8f9208faeb7a5a1281f`: supported; blocking respected: True.
- `hv2_013` / `intent_0df78a6460c97c3804c2b182`: supported; blocking respected: True.
- `hv2_014` / `intent_1470cc429d60236613941af8`: supported; blocking respected: True.
- `hv2_015` / `intent_155da12d49999791fa235ae1`: supported; blocking respected: True.
- `hv2_016` / `intent_f5a16fe6c6a522eda063ae72`: supported; blocking respected: True.
- `hv2_017` / `intent_30fe35c77db9ae4385aef155`: supported; blocking respected: True.
- `hv2_018` / `intent_14cb102c1f85d81a9a62deee`: invalid; blocking respected: True.
- `hv2_019` / `intent_e6296f47a2e48a7774995f11`: supported; blocking respected: True.
- `hv2_020` / `intent_9e320b197302db4ba15c3b6e`: supported; blocking respected: True.
- `hv2_021` / `intent_d7c779aa3f2814424fd62cbf`: supported; blocking respected: True.
- `hv2_022` / `intent_6ec303e89f0e56056fac78bf`: supported; blocking respected: True.
- `hv2_023` / `intent_c4b73e2bfd038da5cffa946a`: supported; blocking respected: True.
- `hv2_024` / `intent_c59e15a2edcb0d4620258522`: supported; blocking respected: True.
- `hv2_025` / `intent_d2de1140715a3888c805855e`: supported; blocking respected: True.
- `hv2_026` / `intent_f398da5e6268d89985fbdce0`: unsupported; blocking respected: True.
- `hv2_027` / `intent_3ced9335793e436700c519ad`: supported; blocking respected: True.
- `hv2_027` / `intent_2ea42aece303ba33e8ffbcfa`: supported; blocking respected: True.
- `hv2_028` / `intent_5db0a6def3f61472d5a7557e`: supported; blocking respected: True.
- `hv2_032` / `intent_ec6f30f88bbc5d24b4ccb10f`: supported; blocking respected: True.
- `hv2_033` / `intent_fece113fbef94a357933ce65`: supported; blocking respected: True.
- `hv2_034` / `intent_843bd6f50dff21de2d9e6071`: supported; blocking respected: True.
- `hv2_039` / `intent_1ee17bc728e8ccc70755d0df`: supported; blocking respected: True.
- `hv2_040` / `intent_4ee683ddc6aeac28b0498149`: supported; blocking respected: True.
- `hv2_041` / `intent_adbc18983aeef006d97a4511`: supported; blocking respected: True.
- `hv2_042` / `intent_68db17906102e38939a7356f`: supported; blocking respected: True.
- `hv2_043` / `intent_a71edd7a47f25b85e0d8160e`: supported; blocking respected: True.
- `hv2_044` / `intent_9459da412286685097fdb114`: supported; blocking respected: True.
- `hv2_045` / `intent_a8eac0b6847e21e7a880e3df`: supported; blocking respected: True.
- `hv2_048` / `intent_fbe7999c115370488c439168`: supported; blocking respected: True.

Focused checks:

- `syn07_two_separate_intents`: **not applicable**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **not applicable**. {"topic_ids_by_source": {"syn-01": [], "syn-02": [], "syn-03": [], "syn-04": []}, "snapshot": null}
- `syn10_invoices_separate_from_orders`: **not applicable**. {"orders_topic": null, "invoice_topics": []}
- `trusted_authorship_respected_by_raw_model`: **met**. {"violating_sources": [], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `hv2_002` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_006` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_008` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_010` (synthetic): status `ok`, classes `incident`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_012` (synthetic): status `ok`, classes `incident`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_015` (synthetic): status `ok`, classes `incident, usability`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_022` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_026` (synthetic): status `ok`, classes `service_request, usability`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_027` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_028` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_029` (synthetic): status `ok`, classes `incident`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_034` (synthetic): status `ok`, classes `service_request, usability`; kinds outside accepted set or no intents.
- `hv2_035` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 353 (char 352))
- `hv2_036` (synthetic): status `needs_review`, classes `hypothesis`; invalid extraction contract; kinds outside accepted set or no intents.
  Contract: intents[0].kind: invalid kind
- `hv2_038` (synthetic): status `needs_review`, classes `(none)`; kinds outside accepted set or no intents; status differs.
- `hv2_042` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_044` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_045` (synthetic): status `ok`, classes `usability`; kinds outside accepted set or no intents.
- `hv2_046` (synthetic): status `needs_review`, classes `unknown`; kinds outside accepted set or no intents.
- `hv2_048` (synthetic): status `ok`, classes `usability`; kinds outside accepted set or no intents.

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
