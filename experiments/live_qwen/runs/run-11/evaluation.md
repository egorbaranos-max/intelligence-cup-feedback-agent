# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 23 | 23 | 23 | 13 |
| case_pdf | 7 | 7 | 7 | 5 |
| synthetic | 16 | 16 | 16 | 8 |

## Первая попытка и повтор после ошибки контракта

Модель получает одну повторную попытку только после ошибки программной проверки. Семантически неверный ответ с правильным форматом автоматически не переписывается. Обе версии ответа сохранены.

- Формат с первой попытки: 23; после повторов: 23.
- Повторных запросов: 0; из них дали допустимый формат: 0.
- Совпадений с предварительными ожиданиями по классу и статусу: сначала 13, в конце 13.

Улучшение формата не равно улучшению понимания. При повторе модель может изменить и смысл; исходный ответ остаётся доступным для сравнения.

## Полнота сравнения с существующими темами

Для каждого продукта проверяются все темы в пределах бюджета 25, группами не более 5. Частичный просмотр не позволяет создать новую тему.
- Вызовов сопоставления: 5; сравнений с реестром больше пяти тем: 0.
- Решений вне автоматического бюджета: 0; они требуют разбора.

Полнота просмотра и повторение программного решения не доказывают, что модель правильно понимает сходство тем.

Явные инструкции обработчику или признаки запроса выдумать доказательства: 2 обращений направлено на разбор и исключено из автоматического учёта.
Это ограниченный набор текстовых правил, а не полная защита от инструкций внутри данных. Возможны пропуски и ложные срабатывания, например при цитировании нормального текста.

## Что показывает этот запуск

Проверка формата и цитат отделена от сравнения смысла. Метки составлены ИИ и требуют независимой проверки людьми; это не оценка точности на рабочих данных.

| Проверка | Результат |
|---|---:|
| Обращений; формат и ссылки на цитаты приняты | 23; 23 |
| Обращений в очереди ручного разбора | 17 |
| Карточек передано в локальную очередь | 1 |
| Из них согласуются с предварительными метками | 0 |
| Из них противоречат предварительным меткам | 0 |
| Из них пока нельзя оценить | 1 |
| Ожидалось повторяющихся тем; пропущены или не подтверждены | 0; 0 |

Отсутствие отправленных карточек не считается успехом: агент может пропустить все настоящие пожелания. Совпадение цитаты и класса также не проверяет точность пересказа модели.

Подробные метки намерений доступны для 0 из 23 обращений. Совпали по цитате и классу 0 из 0 размеченных намерений. Не имеющие такой разметки примеры не включаются в этот показатель.

[Все обращения и ответы](report.html) · [Полный машинный отчёт](evaluation.json) · [Исходные ответы модели](calls.jsonl) · [Очередь разбора](review-queue.json)

- Карточка `topic_e9387111ebc4013c412878e1`: not_scored_missing_intent_or_theme_labels; доставлена: True; тема по меткам: `None`.
- Карточка `topic_d6c10aa42c34012fb5cec106`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.
- Карточка `topic_b9ce742c5644e98e07072014`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.

Model statuses and classes:

- all: statuses `{"needs_review": 9, "ok": 14}`; class presence `{"feature_request": 11, "incident": 8, "service_request": 6, "usability": 6}`.
- case_pdf: statuses `{"needs_review": 7}`; class presence `{"feature_request": 1, "incident": 6, "service_request": 2}`.
- synthetic: statuses `{"needs_review": 2, "ok": 14}`; class presence `{"feature_request": 10, "incident": 2, "service_request": 4, "usability": 6}`.

Model verification (separate from extraction expectations):

A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.

- Calls: 7; valid contracts: 7; verdicts: `{"supported": 6, "unsupported": 1, "unclear": 0, "invalid": 0}`.
- Blocking violations: 0.
- `syn-01` / `intent_87f9e3348bb977c5c4e1c14a`: supported; blocking respected: True.
- `syn-03` / `intent_eca0a755204b3692ece862fc`: supported; blocking respected: True.
- `syn-04` / `intent_790469f830ecd72357abd097`: supported; blocking respected: True.
- `syn-07` / `intent_f6f39bee769797eac82883f9`: supported; blocking respected: True.
- `syn-10` / `intent_49e9c997ac4abfc500274edd`: supported; blocking respected: True.
- `syn-12` / `intent_25591ae82ccbc724e0c215e7`: unsupported; blocking respected: True.
- `syn-16` / `intent_9496b776ed357f6783e7a297`: supported; blocking respected: True.

Focused checks:

- `syn07_two_separate_intents`: **met**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **not met**. {"topic_ids_by_source": {"syn-01": ["topic_e9387111ebc4013c412878e1"], "syn-02": [], "syn-03": ["topic_e9387111ebc4013c412878e1"], "syn-04": ["topic_e9387111ebc4013c412878e1"]}, "snapshot": null}
- `syn10_invoices_separate_from_orders`: **not met**. {"orders_topic": null, "invoice_topics": ["topic_d6c10aa42c34012fb5cec106"]}
- `trusted_authorship_respected_by_raw_model`: **met**. {"violating_sources": [], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `case-04` (case_pdf): status `needs_review`, classes `feature_request, service_request`; kinds outside accepted set or no intents.
- `case-06` (case_pdf): status `needs_review`, classes `incident, service_request`; kinds outside accepted set or no intents.
- `syn-01` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `syn-02` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `syn-03` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents.
- `syn-05` (synthetic): status `ok`, classes `usability`; kinds outside accepted set or no intents.
- `syn-10` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `syn-12` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents; status differs.
- `syn-13` (synthetic): status `needs_review`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `syn-14` (synthetic): status `ok`, classes `service_request`; status differs.

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
