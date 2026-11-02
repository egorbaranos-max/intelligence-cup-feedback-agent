# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 23 | 23 | 23 | 17 |
| case_pdf | 7 | 7 | 7 | 5 |
| synthetic | 16 | 16 | 16 | 12 |

## Первая попытка и повтор после ошибки контракта

Модель получает одну повторную попытку только после ошибки программной проверки. Семантически неверный ответ с правильным форматом автоматически не переписывается. Обе версии ответа сохранены.

- Формат с первой попытки: 20; после повторов: 23.
- Повторных запросов: 3; из них дали допустимый формат: 3.
- Совпадений с предварительными ожиданиями по классу и статусу: сначала 15, в конце 17.

Улучшение формата не равно улучшению понимания. При повторе модель может изменить и смысл; исходный ответ остаётся доступным для сравнения.

## Что показывает этот запуск

Проверка формата и цитат отделена от сравнения смысла. Метки составлены ИИ и требуют независимой проверки людьми; это не оценка точности на рабочих данных.

| Проверка | Результат |
|---|---:|
| Обращений; формат и ссылки на цитаты приняты | 23; 23 |
| Обращений в очереди ручного разбора | 14 |
| Карточек передано в локальную очередь | 1 |
| Из них согласуются с предварительными метками | 0 |
| Из них противоречат предварительным меткам | 0 |
| Из них пока нельзя оценить | 1 |
| Ожидалось повторяющихся тем; пропущены или не подтверждены | 0; 0 |

Отсутствие отправленных карточек не считается успехом: агент может пропустить все настоящие пожелания. Совпадение цитаты и класса также не проверяет точность пересказа модели.

Подробные метки намерений доступны для 0 из 23 обращений. Совпали по цитате и классу 0 из 0 размеченных намерений. Не имеющие такой разметки примеры не включаются в этот показатель.

[Все обращения и ответы](report.html) · [Полный машинный отчёт](evaluation.json) · [Исходные ответы модели](calls.jsonl) · [Очередь разбора](review-queue.json)

- Карточка `topic_a50af2a83527a334900ea64a`: not_scored_missing_intent_or_theme_labels; доставлена: True; тема по меткам: `None`.
- Карточка `topic_f6cc7d4bf1e492217b240c14`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.
- Карточка `topic_e01c7f5439ff1816856ac4d5`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.

Model statuses and classes:

- all: statuses `{"needs_review": 9, "ok": 14}`; class presence `{"feature_request": 13, "incident": 8, "service_request": 5, "unknown": 1, "usability": 4}`.
- case_pdf: statuses `{"needs_review": 7}`; class presence `{"feature_request": 2, "incident": 5, "service_request": 2}`.
- synthetic: statuses `{"needs_review": 2, "ok": 14}`; class presence `{"feature_request": 11, "incident": 3, "service_request": 3, "unknown": 1, "usability": 4}`.

Model verification (separate from extraction expectations):

A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.

- Calls: 9; valid contracts: 9; verdicts: `{"supported": 8, "unsupported": 1, "unclear": 0, "invalid": 0}`.
- Blocking violations: 0.
- `syn-01` / `intent_1b77fc11d76fab3c35251e01`: supported; blocking respected: True.
- `syn-02` / `intent_8fcbb1d70e8f5ac5ec3a96c8`: supported; blocking respected: True.
- `syn-03` / `intent_e363f1ac442ae8e44175014d`: supported; blocking respected: True.
- `syn-04` / `intent_85d1b5ffe00c6364a03ec97d`: supported; blocking respected: True.
- `syn-05` / `intent_bf1fe1cbd912fd38e4b1f895`: unsupported; blocking respected: True.
- `syn-07` / `intent_f6f39bee769797eac82883f9`: supported; blocking respected: True.
- `syn-08` / `intent_9ecdfeeb69fe93ce65758a66`: supported; blocking respected: True.
- `syn-10` / `intent_ac29a0064e92df2f29d2b54d`: supported; blocking respected: True.
- `syn-16` / `intent_4c6f6710c0040620ebbebdd1`: supported; blocking respected: True.

Focused checks:

- `syn07_two_separate_intents`: **met**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **met**. {"topic_ids_by_source": {"syn-01": ["topic_a50af2a83527a334900ea64a"], "syn-02": ["topic_a50af2a83527a334900ea64a"], "syn-03": ["topic_a50af2a83527a334900ea64a"], "syn-04": ["topic_a50af2a83527a334900ea64a"]}, "snapshot": {"raw_sources": 4, "independent_episodes": 3, "known_customers": 2}}
- `syn10_invoices_separate_from_orders`: **met**. {"orders_topic": "topic_a50af2a83527a334900ea64a", "invoice_topics": ["topic_f6cc7d4bf1e492217b240c14"]}
- `trusted_authorship_respected_by_raw_model`: **met**. {"violating_sources": [], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `case-01` (case_pdf): status `needs_review`, classes `feature_request, incident`; kinds outside accepted set or no intents.
- `case-04` (case_pdf): status `needs_review`, classes `feature_request, service_request`; kinds outside accepted set or no intents.
- `syn-01` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `syn-05` (synthetic): status `ok`, classes `feature_request, incident, service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `syn-10` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `syn-14` (synthetic): status `ok`, classes `service_request`; status differs.

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
