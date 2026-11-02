# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 12 | 12 | 12 | 3 |
| case_pdf | 0 | 0 | 0 | 0 |
| synthetic | 12 | 12 | 12 | 3 |

## Первая попытка и повтор после ошибки контракта

Модель получает одну повторную попытку только после ошибки программной проверки. Семантически неверный ответ с правильным форматом автоматически не переписывается. Обе версии ответа сохранены.

- Формат с первой попытки: 11; после повторов: 12.
- Повторных запросов: 1; из них дали допустимый формат: 1.
- Совпадений с предварительными ожиданиями по классу и статусу: сначала 2, в конце 3.

Улучшение формата не равно улучшению понимания. При повторе модель может изменить и смысл; исходный ответ остаётся доступным для сравнения.

## Полнота сравнения с существующими темами

Для каждого продукта проверяются все темы в пределах бюджета 25, группами не более 5. Частичный просмотр не позволяет создать новую тему.
- Вызовов сопоставления: 4; сравнений с реестром больше пяти тем: 0.
- Решений вне автоматического бюджета: 0; они требуют разбора.

Полнота просмотра и повторение программного решения не доказывают, что модель правильно понимает сходство тем.

Явные инструкции обработчику или признаки запроса выдумать доказательства: 1 обращений направлено на разбор и исключено из автоматического учёта.
Это ограниченный набор текстовых правил, а не полная защита от инструкций внутри данных. Возможны пропуски и ложные срабатывания, например при цитировании нормального текста.

## Что показывает этот запуск

Проверка формата и цитат отделена от сравнения смысла. Метки составлены ИИ и требуют независимой проверки людьми; это не оценка точности на рабочих данных.

| Проверка | Результат |
|---|---:|
| Обращений; формат и ссылки на цитаты приняты | 12; 12 |
| Обращений в очереди ручного разбора | 7 |
| Карточек передано в локальную очередь | 1 |
| Из них согласуются с предварительными метками | 0 |
| Из них противоречат предварительным меткам | 0 |
| Из них пока нельзя оценить | 1 |
| Ожидалось повторяющихся тем; пропущены или не подтверждены | 0; 0 |

Отсутствие отправленных карточек не считается успехом: агент может пропустить все настоящие пожелания. Совпадение цитаты и класса также не проверяет точность пересказа модели.

Подробные метки намерений доступны для 0 из 12 обращений. Совпали по цитате и классу 0 из 0 размеченных намерений. Не имеющие такой разметки примеры не включаются в этот показатель.

[Все обращения и ответы](report.html) · [Полный машинный отчёт](evaluation.json) · [Исходные ответы модели](calls.jsonl) · [Очередь разбора](review-queue.json)

- Карточка `topic_9294258a8c34105ced474e0b`: not_scored_missing_intent_or_theme_labels; доставлена: True; тема по меткам: `None`.
- Карточка `topic_8156fa8d0cccb6eb42b77407`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.
- Карточка `topic_1a43f6f2a43b395a6da08cf8`: not_scored_missing_intent_or_theme_labels; доставлена: False; тема по меткам: `None`.

Model statuses and classes:

- all: statuses `{"needs_review": 1, "ok": 11}`; class presence `{"feature_request": 8, "incident": 3, "service_request": 5, "unknown": 1, "usability": 5}`.
- case_pdf: statuses `{}`; class presence `{}`.
- synthetic: statuses `{"needs_review": 1, "ok": 11}`; class presence `{"feature_request": 8, "incident": 3, "service_request": 5, "unknown": 1, "usability": 5}`.

Model verification (separate from extraction expectations):

A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.

- Calls: 5; valid contracts: 5; verdicts: `{"supported": 5, "unsupported": 0, "unclear": 0, "invalid": 0}`.
- Blocking violations: 0.
- `synthetic-fresh-01` / `intent_e7c7e572ef7b56c1fa6500f0`: supported; blocking respected: True.
- `synthetic-fresh-02` / `intent_8d08195ed0e7a5dc9f95eac9`: supported; blocking respected: True.
- `synthetic-fresh-03` / `intent_59f96668ea63b8ae92e0b324`: supported; blocking respected: True.
- `synthetic-fresh-07` / `intent_76175cb497818e13b35513e5`: supported; blocking respected: True.
- `synthetic-fresh-12` / `intent_7f282e93cb4f1a5fed526295`: supported; blocking respected: True.

Focused checks:

- `syn07_two_separate_intents`: **not applicable**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **not applicable**. {"topic_ids_by_source": {"syn-01": [], "syn-02": [], "syn-03": [], "syn-04": []}, "snapshot": null}
- `syn10_invoices_separate_from_orders`: **not applicable**. {"orders_topic": null, "invoice_topics": []}
- `trusted_authorship_respected_by_raw_model`: **met**. {"violating_sources": [], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `synthetic-fresh-01` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `synthetic-fresh-03` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents.
- `synthetic-fresh-04` (synthetic): status `ok`, classes `service_request, usability`; kinds outside accepted set or no intents; explicit feature flag differs.
- `synthetic-fresh-05` (synthetic): status `ok`, classes `incident, service_request, usability`; kinds outside accepted set or no intents.
- `synthetic-fresh-06` (synthetic): status `ok`, classes `incident, service_request`; kinds outside accepted set or no intents.
- `synthetic-fresh-07` (synthetic): status `ok`, classes `feature_request, service_request, usability`; kinds outside accepted set or no intents.
- `synthetic-fresh-08` (synthetic): status `ok`, classes `feature_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `synthetic-fresh-09` (synthetic): status `ok`, classes `usability`; status differs.
- `synthetic-fresh-10` (synthetic): status `ok`, classes `feature_request`; status differs.

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
