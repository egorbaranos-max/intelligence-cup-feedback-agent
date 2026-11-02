# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 48 | 48 | 48 | 27 |
| case_pdf | 0 | 0 | 0 | 0 |
| synthetic | 48 | 48 | 48 | 27 |

## Первая попытка и повтор после ошибки контракта

Модель получает одну повторную попытку только после ошибки программной проверки. Семантически неверный ответ с правильным форматом автоматически не переписывается. Обе версии ответа сохранены.

- Формат с первой попытки: 46; после повторов: 48.
- Повторных запросов: 2; из них дали допустимый формат: 2.
- Совпадений с предварительными ожиданиями по классу и статусу: сначала 27, в конце 27.

Улучшение формата не равно улучшению понимания. При повторе модель может изменить и смысл; исходный ответ остаётся доступным для сравнения.

## Полнота сравнения с существующими темами

Для каждого продукта проверяются все темы в пределах бюджета 25, группами не более 5. Частичный просмотр не позволяет создать новую тему.
- Вызовов сопоставления: 61; сравнений с реестром больше пяти тем: 17.
- Решений вне автоматического бюджета: 0; они требуют разбора.

Полнота просмотра и повторение программного решения не доказывают, что модель правильно понимает сходство тем.

Явные инструкции обработчику или признаки запроса выдумать доказательства: 1 обращений направлено на разбор и исключено из автоматического учёта.
Это ограниченный набор текстовых правил, а не полная защита от инструкций внутри данных. Возможны пропуски и ложные срабатывания, например при цитировании нормального текста.

## Что показывает этот запуск

Проверка формата и цитат отделена от сравнения смысла. Метки составлены ИИ и требуют независимой проверки людьми; это не оценка точности на рабочих данных.

| Проверка | Результат |
|---|---:|
| Обращений; формат и ссылки на цитаты приняты | 48; 48 |
| Обращений в очереди ручного разбора | 15 |
| Карточек передано в локальную очередь | 3 |
| Из них согласуются с предварительными метками | 1 |
| Из них противоречат предварительным меткам | 2 |
| Из них пока нельзя оценить | 0 |
| Ожидалось повторяющихся тем; пропущены или не подтверждены | 4; 3 |

Отсутствие отправленных карточек не считается успехом: агент может пропустить все настоящие пожелания. Совпадение цитаты и класса также не проверяет точность пересказа модели.

Подробные метки намерений доступны для 48 из 48 обращений. Совпали по цитате и классу 41 из 54 размеченных намерений. Не имеющие такой разметки примеры не включаются в этот показатель.

[Все обращения и ответы](report.html) · [Полный машинный отчёт](evaluation.json) · [Исходные ответы модели](calls.jsonl) · [Очередь разбора](review-queue.json)

- Карточка `topic_2daa69320cc14cc989812850`: provisionally_unsupported_or_mixed; доставлена: True; тема по меткам: `scheduled_email_report`.
- Карточка `topic_783df10f264d9eb478101124`: provisionally_unsupported_or_mixed; доставлена: True; тема по меткам: `None`.
- Карточка `topic_44d9675798f590f72fb4f3f3`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `role_change_audit`.
- Карточка `topic_239aab5e2bb78ccca93c5a79`: provisionally_supported_evidence_and_class; доставлена: True; тема по меткам: `sla_waiting_customer_pause`.
- Карточка `topic_8ae10b268768313cd8ce58fd`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `dark_interface`.
- Карточка `topic_cfe26f16dc5894ea2988be03`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `separate_notification_volume`.
- Карточка `topic_3b1b413fa3800146cbfe96fc`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `scheduled_customer_reply`.
- Карточка `topic_dc1e6d69174843e366778086`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `scheduled_sftp_report`.
- Карточка `topic_d5ae6604daee890ca4fc233a`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `employee_login_audit`.
- Карточка `topic_ceb02cfd00d74fbb14524724`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `sla_weekend_calendar`.
- Карточка `topic_abfae825ff00b19059d3802a`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `restore_deleted_queue`.
- Карточка `topic_73e0d42b4862ba48a1a1a89e`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `customer_xlsx_import`.
- Карточка `topic_8006c7b7d4dcc0faebcb080a`: unscored_ambiguous_evidence_alignment; доставлена: False; тема по меткам: `None`.
- Карточка `topic_d306f45fa7ddc2b06a13da20`: provisionally_unsupported_or_mixed; доставлена: False; тема по меткам: `None`.
- Карточка `topic_989000e28800a996e4030014`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `saml_sso`.
- Карточка `topic_c222e5935bf7f97562515318`: provisionally_unsupported_or_mixed; доставлена: False; тема по меткам: `ticket_queue_change_webhook`.
- Пропущена или не подтверждена повторяющаяся тема `scheduled_email_report`: 3 эпизодов, 2 клиентов.
- Пропущена или не подтверждена повторяющаяся тема `ticket_attachments_zip`: 3 эпизодов, 2 клиентов.
- Пропущена или не подтверждена повторяющаяся тема `role_change_audit`: 3 эпизодов, 3 клиентов.

Model statuses and classes:

- all: statuses `{"needs_review": 4, "ok": 44}`; class presence `{"feature_request": 41, "incident": 3, "service_request": 14, "unknown": 2, "usability": 9}`.
- case_pdf: statuses `{}`; class presence `{}`.
- synthetic: statuses `{"needs_review": 4, "ok": 44}`; class presence `{"feature_request": 41, "incident": 3, "service_request": 14, "unknown": 2, "usability": 9}`.

Model verification (separate from extraction expectations):

A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.

- Calls: 38; valid contracts: 38; verdicts: `{"supported": 37, "unsupported": 1, "unclear": 0, "invalid": 0}`.
- Blocking violations: 0.
- `hv2_001` / `intent_94f5855aa5a81291bdb5c037`: supported; blocking respected: True.
- `hv2_002` / `intent_69d873e496f9a4a8d6e660d8`: supported; blocking respected: True.
- `hv2_003` / `intent_08db88fbed07822a057bc267`: supported; blocking respected: True.
- `hv2_004` / `intent_6a322d3be13d96d79e628988`: supported; blocking respected: True.
- `hv2_005` / `intent_9febc49fa7c06d72ef1d4d37`: supported; blocking respected: True.
- `hv2_006` / `intent_42629dfc1cfd3d82f4780d8a`: supported; blocking respected: True.
- `hv2_007` / `intent_04e2b030f56b00f4e7f5726c`: supported; blocking respected: True.
- `hv2_008` / `intent_b0eeb85c03616ab70aea6992`: supported; blocking respected: True.
- `hv2_009` / `intent_62c152372b26f276a7a9f35b`: supported; blocking respected: True.
- `hv2_010` / `intent_0c868b34095ea23161910640`: supported; blocking respected: True.
- `hv2_012` / `intent_a71ab978ffc94da05474a159`: supported; blocking respected: True.
- `hv2_013` / `intent_01c0db94fb70731f9ab3e0b9`: supported; blocking respected: True.
- `hv2_013` / `intent_17ddfc409f465cc5738ef8ef`: supported; blocking respected: True.
- `hv2_014` / `intent_d493c99acfcd2eaf1b9dacc3`: supported; blocking respected: True.
- `hv2_015` / `intent_f90911750b4382a7b1f7d50a`: supported; blocking respected: True.
- `hv2_016` / `intent_8c67d5bcfe4c44974062fb9f`: supported; blocking respected: True.
- `hv2_017` / `intent_73f86984c1e6f27f4c81ebc5`: supported; blocking respected: True.
- `hv2_018` / `intent_28064ba037ca99841339e77b`: supported; blocking respected: True.
- `hv2_019` / `intent_ea4c2e0a17d6ec1f18f2acc3`: supported; blocking respected: True.
- `hv2_020` / `intent_1358c19550e8fc85cd5f3bc8`: supported; blocking respected: True.
- `hv2_021` / `intent_4d88b9443a0505d9841c4b23`: supported; blocking respected: True.
- `hv2_022` / `intent_240f18215f0bccb5e524008a`: supported; blocking respected: True.
- `hv2_023` / `intent_8155975cd324dd407048057f`: supported; blocking respected: True.
- `hv2_024` / `intent_b0eebdabb2e566807d023631`: supported; blocking respected: True.
- `hv2_025` / `intent_263a25f15ea2a9e4c7718195`: supported; blocking respected: True.
- `hv2_026` / `intent_95965a56374703b7d9302c71`: supported; blocking respected: True.
- `hv2_027` / `intent_53bd842ded041ee0f2c33051`: supported; blocking respected: True.
- `hv2_028` / `intent_eeec32bd15b2f38ce6ad595c`: supported; blocking respected: True.
- `hv2_029` / `intent_f38060c4ab3881fb3e0b1339`: supported; blocking respected: True.
- `hv2_034` / `intent_f2f950a22c0da3af08e2d616`: unsupported; blocking respected: True.
- `hv2_039` / `intent_0b3a9bdb262465a140a4bcd5`: supported; blocking respected: True.
- `hv2_040` / `intent_881cc0f618b5c74d1b818d77`: supported; blocking respected: True.
- `hv2_041` / `intent_31e99561be8d6651cdea25c1`: supported; blocking respected: True.
- `hv2_041` / `intent_749b6ff6de9947489c7b023c`: supported; blocking respected: True.
- `hv2_042` / `intent_39910547ab7bcbe23594c70a`: supported; blocking respected: True.
- `hv2_043` / `intent_3ed80d8c03fe0125fef1406b`: supported; blocking respected: True.
- `hv2_044` / `intent_f4ddff144e47e36e2101fd73`: supported; blocking respected: True.
- `hv2_044` / `intent_0f0addbf9b7ac056fc05da85`: supported; blocking respected: True.

Focused checks:

- `syn07_two_separate_intents`: **not applicable**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **not applicable**. {"topic_ids_by_source": {"syn-01": [], "syn-02": [], "syn-03": [], "syn-04": []}, "snapshot": null}
- `syn10_invoices_separate_from_orders`: **not applicable**. {"orders_topic": null, "invoice_topics": []}
- `trusted_authorship_respected_by_raw_model`: **met**. {"violating_sources": [], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `hv2_009` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_011` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_017` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents.
- `hv2_019` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_022` (synthetic): status `ok`, classes `feature_request, incident`; kinds outside accepted set or no intents.
- `hv2_026` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents.
- `hv2_027` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_028` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_029` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_030` (synthetic): status `ok`, classes `incident, service_request`; kinds outside accepted set or no intents.
- `hv2_032` (synthetic): status `ok`, classes `service_request, usability`; kinds outside accepted set or no intents.
- `hv2_033` (synthetic): status `ok`, classes `feature_request`; explicit feature flag differs.
- `hv2_034` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_035` (synthetic): status `ok`, classes `service_request, usability`; kinds outside accepted set or no intents.
- `hv2_037` (synthetic): status `needs_review`, classes `feature_request, unknown`; kinds outside accepted set or no intents.
- `hv2_038` (synthetic): status `needs_review`, classes `service_request, unknown`; kinds outside accepted set or no intents; status differs.
- `hv2_039` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents.
- `hv2_042` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_045` (synthetic): status `ok`, classes `feature_request, service_request, usability`; kinds outside accepted set or no intents.
- `hv2_047` (synthetic): status `ok`, classes `service_request, usability`; kinds outside accepted set or no intents.
- `hv2_048` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents.

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
