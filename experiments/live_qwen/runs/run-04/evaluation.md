# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 23 | 23 | 9 | 4 |
| case_pdf | 7 | 7 | 0 | 0 |
| synthetic | 16 | 16 | 9 | 4 |

## Что показывает этот запуск

Проверка формата и цитат отделена от сравнения смысла. Метки составлены ИИ и требуют независимой проверки людьми; это не оценка точности на рабочих данных.

| Проверка | Результат |
|---|---:|
| Обращений; формат и ссылки на цитаты приняты | 23; 9 |
| Обращений в очереди ручного разбора | 17 |
| Карточек передано в локальную очередь | 1 |
| Из них согласуются с предварительными метками | 0 |
| Из них противоречат предварительным меткам | 0 |
| Из них пока нельзя оценить | 1 |
| Ожидалось повторяющихся тем; пропущены или не подтверждены | 0; 0 |

Отсутствие отправленных карточек не считается успехом: агент может пропустить все настоящие пожелания. Совпадение цитаты и класса также не проверяет точность пересказа модели.

Подробные метки намерений доступны для 0 из 23 обращений. Совпали по цитате и классу 0 из 0 размеченных намерений. Не имеющие такой разметки примеры не включаются в этот показатель.

[Все обращения и ответы](report.html) · [Полный машинный отчёт](evaluation.json) · [Исходные ответы модели](calls.jsonl) · [Очередь разбора](review-queue.json)

- Карточка `topic_741ed1fb0c5157c7a6db155e`: not_scored_missing_intent_or_theme_labels; доставлена: True; тема по меткам: `None`.
- Карточка `topic_3839e39bd1e51bcb8ba0cd03`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.
- Карточка `topic_159b92babf5e23e2f3c0b36e`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.
- Карточка `topic_5d935de50fb483b68ef937bd`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.

Model statuses and classes:

- all: statuses `{"ok": 16, "unparseable_or_missing": 7}`; class presence `{"feature_request": 5, "incident": 6, "service_request": 6, "usability": 6}`.
- case_pdf: statuses `{"ok": 6, "unparseable_or_missing": 1}`; class presence `{"feature_request": 1, "incident": 4, "service_request": 3, "usability": 1}`.
- synthetic: statuses `{"ok": 10, "unparseable_or_missing": 6}`; class presence `{"feature_request": 4, "incident": 2, "service_request": 3, "usability": 5}`.

Model verification (separate from extraction expectations):

A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.

- Calls: 9; valid contracts: 9; verdicts: `{"supported": 7, "unsupported": 2, "unclear": 0, "invalid": 0}`.
- Blocking violations: 0.
- `syn-01` / `intent_712c370de7f3a89c6bd939c0`: supported; blocking respected: True.
- `syn-05` / `intent_22a435b21e63945ebaa68ae4`: unsupported; blocking respected: True.
- `syn-08` / `intent_9ecdfeeb69fe93ce65758a66`: supported; blocking respected: True.
- `syn-10` / `intent_32100d2d0a747e6eedb27750`: supported; blocking respected: True.
- `syn-10` / `intent_4669c47d2b37306ef6a9fe83`: supported; blocking respected: True.
- `syn-11` / `intent_b2c4a5beba1d529b1dd6caa8`: unsupported; blocking respected: True.
- `syn-12` / `intent_65ef071d8626eee14ad97bf0`: supported; blocking respected: True.
- `syn-15` / `intent_f227ac9a60aedba10cc67134`: supported; blocking respected: True.
- `syn-15` / `intent_1f50e428589bca89fd3743db`: supported; blocking respected: True.

Focused checks:

- `syn07_two_separate_intents`: **not met**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **not met**. {"topic_ids_by_source": {"syn-01": ["topic_741ed1fb0c5157c7a6db155e"], "syn-02": [], "syn-03": [], "syn-04": []}, "snapshot": null}
- `syn10_invoices_separate_from_orders`: **not met**. {"orders_topic": null, "invoice_topics": ["topic_159b92babf5e23e2f3c0b36e", "topic_3839e39bd1e51bcb8ba0cd03"]}
- `trusted_authorship_respected_by_raw_model`: **not met**. {"violating_sources": ["case-01", "case-02", "case-03", "case-04", "case-05", "case-06", "case-07", "syn-09"], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `case-01` (case_pdf): status `ok`, classes `incident, usability`; invalid extraction contract; kinds outside accepted set or no intents.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required; intents[1].origin: unverified user authorship; needs_review required
- `case-02` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required
- `case-03` (case_pdf): status `ok`, classes `incident, service_request`; invalid extraction contract; kinds outside accepted set or no intents.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required; intents[1].origin: unverified user authorship; needs_review required
- `case-04` (case_pdf): status `ok`, classes `feature_request, service_request`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required; intents[1].origin: unverified user authorship; needs_review required
- `case-05` (case_pdf): status `ok`, classes `incident`; invalid extraction contract.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required
- `case-06` (case_pdf): status `ok`, classes `service_request`; invalid extraction contract.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required
- `case-07` (case_pdf): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 204 (char 203))
- `syn-02` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `syn-03` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 214 (char 213))
- `syn-04` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 211 (char 210))
- `syn-05` (synthetic): status `ok`, classes `incident, usability`; kinds outside accepted set or no intents.
- `syn-06` (synthetic): status `ok`, classes `incident, service_request`; kinds outside accepted set or no intents.
- `syn-07` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 366 (char 365))
- `syn-09` (synthetic): status `ok`, classes `feature_request`; invalid extraction contract; explicit feature flag differs; status differs.
  Contract: status: unknown author requires needs_review; intents[0].origin: unverified user authorship; needs_review required
- `syn-10` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `syn-12` (synthetic): status `ok`, classes `usability`; status differs.
- `syn-13` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 373 (char 372))
- `syn-14` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 385 (char 384))
- `syn-16` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 231 (char 230))

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
