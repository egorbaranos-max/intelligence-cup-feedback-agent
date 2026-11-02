# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 23 | 23 | 10 | 6 |
| case_pdf | 7 | 7 | 0 | 0 |
| synthetic | 16 | 16 | 10 | 6 |

## Что показывает этот запуск

Проверка формата и цитат отделена от сравнения смысла. Метки составлены ИИ и требуют независимой проверки людьми; это не оценка точности на рабочих данных.

| Проверка | Результат |
|---|---:|
| Обращений; формат и ссылки на цитаты приняты | 23; 10 |
| Обращений в очереди ручного разбора | 14 |
| Карточек передано в локальную очередь | 1 |
| Из них согласуются с предварительными метками | 0 |
| Из них противоречат предварительным меткам | 0 |
| Из них пока нельзя оценить | 1 |
| Ожидалось повторяющихся тем; пропущены или не подтверждены | 0; 0 |

Отсутствие отправленных карточек не считается успехом: агент может пропустить все настоящие пожелания. Совпадение цитаты и класса также не проверяет точность пересказа модели.

Подробные метки намерений доступны для 0 из 23 обращений. Совпали по цитате и классу 0 из 0 размеченных намерений. Не имеющие такой разметки примеры не включаются в этот показатель.

[Все обращения и ответы](report.html) · [Полный машинный отчёт](evaluation.json) · [Исходные ответы модели](calls.jsonl) · [Очередь разбора](review-queue.json)

- Карточка `topic_741ed1fb0c5157c7a6db155e`: not_scored_missing_intent_or_theme_labels; доставлена: True; тема по меткам: `None`.
- Карточка `topic_754a05dbc06ea9ab517423ed`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.
- Карточка `topic_e01c7f5439ff1816856ac4d5`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.

Model statuses and classes:

- all: statuses `{"ok": 17, "unparseable_or_missing": 6}`; class presence `{"feature_request": 6, "incident": 7, "service_request": 3, "usability": 3}`.
- case_pdf: statuses `{"ok": 6, "unparseable_or_missing": 1}`; class presence `{"incident": 5, "service_request": 1}`.
- synthetic: statuses `{"ok": 11, "unparseable_or_missing": 5}`; class presence `{"feature_request": 6, "incident": 2, "service_request": 2, "usability": 3}`.

Model verification (separate from extraction expectations):

A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.

- Calls: 6; valid contracts: 6; verdicts: `{"supported": 6, "unsupported": 0, "unclear": 0, "invalid": 0}`.
- Blocking violations: 0.
- `syn-01` / `intent_712c370de7f3a89c6bd939c0`: supported; blocking respected: True.
- `syn-01` / `intent_9ad9bdbdc35ff3e4d74dfaa1`: supported; blocking respected: True.
- `syn-03` / `intent_cc33f16f3f47d9fbb7331e34`: supported; blocking respected: True.
- `syn-04` / `intent_85d1b5ffe00c6364a03ec97d`: supported; blocking respected: True.
- `syn-08` / `intent_b28ab8819c3d5bcbd40da91f`: supported; blocking respected: True.
- `syn-16` / `intent_4c6f6710c0040620ebbebdd1`: supported; blocking respected: True.

Focused checks:

- `syn07_two_separate_intents`: **not met**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **not met**. {"topic_ids_by_source": {"syn-01": ["topic_741ed1fb0c5157c7a6db155e", "topic_754a05dbc06ea9ab517423ed"], "syn-02": [], "syn-03": ["topic_741ed1fb0c5157c7a6db155e"], "syn-04": ["topic_741ed1fb0c5157c7a6db155e"]}, "snapshot": null}
- `syn10_invoices_separate_from_orders`: **not met**. {"orders_topic": null, "invoice_topics": []}
- `trusted_authorship_respected_by_raw_model`: **not met**. {"violating_sources": ["case-01", "case-02", "case-03", "case-04", "case-05", "case-06", "case-07", "syn-09"], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `case-01` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review
- `case-02` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required
- `case-03` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required; intents[1].origin: unverified user authorship; needs_review required; intents[2].origin: unverified user authorship; needs_review required
- `case-04` (case_pdf): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 689 (char 688))
- `case-05` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review
- `case-06` (case_pdf): status `ok`, classes `service_request`; invalid extraction contract.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required
- `case-07` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review
- `syn-01` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `syn-02` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 213 (char 212))
- `syn-05` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 505 (char 504))
- `syn-07` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 342 (char 341))
- `syn-09` (synthetic): status `ok`, classes `feature_request`; invalid extraction contract; explicit feature flag differs; status differs.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required
- `syn-10` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 415 (char 414))
- `syn-11` (synthetic): status `ok`, classes `incident, service_request`; kinds outside accepted set or no intents.
- `syn-12` (synthetic): status `ok`, classes `usability`; status differs.
- `syn-13` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 350 (char 349))
- `syn-14` (synthetic): status `ok`, classes `service_request`; status differs.

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
