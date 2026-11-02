# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 23 | 23 | 4 | 2 |
| case_pdf | 7 | 7 | 2 | 0 |
| synthetic | 16 | 16 | 2 | 2 |

## Первая попытка и повтор после ошибки контракта

Модель получает одну повторную попытку только после ошибки программной проверки. Семантически неверный ответ с правильным форматом автоматически не переписывается. Обе версии ответа сохранены.

- Формат с первой попытки: 3; после повторов: 4.
- Повторных запросов: 20; из них дали допустимый формат: 1.
- Совпадений с предварительными ожиданиями по классу и статусу: сначала 2, в конце 2.

Улучшение формата не равно улучшению понимания. При повторе модель может изменить и смысл; исходный ответ остаётся доступным для сравнения.

## Что показывает этот запуск

Проверка формата и цитат отделена от сравнения смысла. Метки составлены ИИ и требуют независимой проверки людьми; это не оценка точности на рабочих данных.

| Проверка | Результат |
|---|---:|
| Обращений; формат и ссылки на цитаты приняты | 23; 4 |
| Обращений в очереди ручного разбора | 22 |
| Карточек передано в локальную очередь | 0 |
| Из них согласуются с предварительными метками | 0 |
| Из них противоречат предварительным меткам | 0 |
| Из них пока нельзя оценить | 0 |
| Ожидалось повторяющихся тем; пропущены или не подтверждены | 0; 0 |

Отсутствие отправленных карточек не считается успехом: агент может пропустить все настоящие пожелания. Совпадение цитаты и класса также не проверяет точность пересказа модели.

Подробные метки намерений доступны для 0 из 23 обращений. Совпали по цитате и классу 0 из 0 размеченных намерений. Не имеющие такой разметки примеры не включаются в этот показатель.

[Все обращения и ответы](report.html) · [Полный машинный отчёт](evaluation.json) · [Исходные ответы модели](calls.jsonl) · [Очередь разбора](review-queue.json)

- Карточка `topic_89d9a0cf576ebf16892d77ba`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.

Model statuses and classes:

- all: statuses `{"needs_review": 3, "ok": 2, "unparseable_or_missing": 18}`; class presence `{"feature_request": 2, "incident": 1, "service_request": 2, "unknown": 2, "usability": 1}`.
- case_pdf: statuses `{"needs_review": 2, "unparseable_or_missing": 5}`; class presence `{"feature_request": 1, "service_request": 1, "unknown": 1}`.
- synthetic: statuses `{"needs_review": 1, "ok": 2, "unparseable_or_missing": 13}`; class presence `{"feature_request": 1, "incident": 1, "service_request": 1, "unknown": 1, "usability": 1}`.

Model verification (separate from extraction expectations):

A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.

- Calls: 1; valid contracts: 1; verdicts: `{"supported": 1, "unsupported": 0, "unclear": 0, "invalid": 0}`.
- Blocking violations: 0.
- `syn-07` / `intent_f6f39bee769797eac82883f9`: supported; blocking respected: True.

Focused checks:

- `syn07_two_separate_intents`: **met**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **not met**. {"topic_ids_by_source": {"syn-01": [], "syn-02": [], "syn-03": [], "syn-04": []}, "snapshot": null}
- `syn10_invoices_separate_from_orders`: **not met**. {"orders_topic": null, "invoice_topics": []}
- `trusted_authorship_respected_by_raw_model`: **not met**. {"violating_sources": ["case-01", "case-02", "case-03", "case-06", "case-07", "syn-09"], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `case-01` (case_pdf): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 375 (char 374))
- `case-02` (case_pdf): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 323 (char 322))
- `case-03` (case_pdf): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 433 (char 432))
- `case-04` (case_pdf): status `needs_review`, classes `feature_request, service_request`; kinds outside accepted set or no intents.
- `case-05` (case_pdf): status `needs_review`, classes `unknown`; kinds outside accepted set or no intents.
- `case-06` (case_pdf): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 451 (char 450))
- `case-07` (case_pdf): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 258 (char 257))
- `syn-01` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Expecting ',' delimiter: line 1 column 208 (char 207))
- `syn-02` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Expecting ',' delimiter: line 1 column 184 (char 183))
- `syn-03` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 244 (char 243))
- `syn-04` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Expecting ',' delimiter: line 1 column 204 (char 203))
- `syn-05` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 391 (char 390))
- `syn-06` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Expecting ',' delimiter: line 1 column 189 (char 188))
- `syn-08` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Expecting ',' delimiter: line 1 column 209 (char 208))
- `syn-09` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Expecting ',' delimiter: line 1 column 251 (char 250))
- `syn-10` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 377 (char 376))
- `syn-12` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 338 (char 337))
- `syn-13` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 239 (char 238))
- `syn-14` (synthetic): status `needs_review`, classes `unknown`; invalid extraction contract.
  Contract: intents[1]: duplicate intent
- `syn-15` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 364 (char 363))
- `syn-16` (synthetic): status `unparseable_or_missing`, classes `(none)`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs; status differs.
  Contract: response: invalid JSON (Extra data: line 1 column 238 (char 237))

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
