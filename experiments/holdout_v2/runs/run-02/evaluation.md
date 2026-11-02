# Saved-run comparison

Frozen preliminary AI expectations only; not human gold, not a corporate accuracy estimate, not an acceptance gate. Text only; no financial effect, ASR/VL or corporate integration is tested.

Run status: `complete`.

| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |
|---|---:|---:|---:|---:|
| all | 48 | 48 | 47 | 26 |
| case_pdf | 0 | 0 | 0 | 0 |
| synthetic | 48 | 48 | 47 | 26 |

## Первая попытка и повтор после ошибки контракта

Модель получает одну повторную попытку только после ошибки программной проверки. Семантически неверный ответ с правильным форматом автоматически не переписывается. Обе версии ответа сохранены.

- Формат с первой попытки: 47; после повторов: 47.
- Повторных запросов: 1; из них дали допустимый формат: 0.
- Совпадений с предварительными ожиданиями по классу и статусу: сначала 26, в конце 26.

Улучшение формата не равно улучшению понимания. При повторе модель может изменить и смысл; исходный ответ остаётся доступным для сравнения.

## Полнота сравнения с существующими темами

Для каждого продукта проверяются все темы в пределах бюджета 25, группами не более 5. Частичный просмотр не позволяет создать новую тему.
- Вызовов сопоставления: 59; сравнений с реестром больше пяти тем: 19.
- Решений вне автоматического бюджета: 0; они требуют разбора.

Полнота просмотра и повторение программного решения не доказывают, что модель правильно понимает сходство тем.

Явные инструкции обработчику или признаки запроса выдумать доказательства: 1 обращений направлено на разбор и исключено из автоматического учёта.
Это ограниченный набор текстовых правил, а не полная защита от инструкций внутри данных. Возможны пропуски и ложные срабатывания, например при цитировании нормального текста.

## Что показывает этот запуск

Проверка формата и цитат отделена от сравнения смысла. Метки составлены ИИ и требуют независимой проверки людьми; это не оценка точности на рабочих данных.

| Проверка | Результат |
|---|---:|
| Обращений; формат и ссылки на цитаты приняты | 48; 47 |
| Обращений в очереди ручного разбора | 22 |
| Карточек передано в локальную очередь | 4 |
| Из них согласуются с предварительными метками | 1 |
| Из них противоречат предварительным меткам | 3 |
| Из них пока нельзя оценить | 0 |
| Ожидалось повторяющихся тем; пропущены или не подтверждены | 4; 3 |

Отсутствие отправленных карточек не считается успехом: агент может пропустить все настоящие пожелания. Совпадение цитаты и класса также не проверяет точность пересказа модели.

Подробные метки намерений доступны для 48 из 48 обращений. Совпали по цитате и классу 35 из 54 размеченных намерений. Не имеющие такой разметки примеры не включаются в этот показатель.

[Все обращения и ответы](report.html) · [Полный машинный отчёт](evaluation.json) · [Исходные ответы модели](calls.jsonl) · [Очередь разбора](review-queue.json)

- Карточка `topic_efa2b536d910aafd05834492`: provisionally_unsupported_or_mixed; доставлена: True; тема по меткам: `None`.
- Карточка `topic_66e7c17d6192b71d3d1614c4`: provisionally_unsupported_or_mixed; доставлена: True; тема по меткам: `None`.
- Карточка `topic_bd54d5ba4140c665fb74dd0d`: provisionally_unsupported_or_mixed; доставлена: True; тема по меткам: `role_change_audit`.
- Карточка `topic_2daacf240cf5f7f2ab74e431`: provisionally_supported_evidence_and_class; доставлена: True; тема по меткам: `sla_waiting_customer_pause`.
- Карточка `topic_8ae10b268768313cd8ce58fd`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `dark_interface`.
- Карточка `topic_6e6b42b1bba65f0cb8cbe884`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `separate_notification_volume`.
- Карточка `topic_fe6e482a2cf50c169defe433`: provisionally_unsupported_or_mixed; доставлена: False; тема по меткам: `scheduled_customer_reply`.
- Карточка `topic_dab24139410d0fb000c4df65`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `sla_weekend_calendar`.
- Карточка `topic_f3ee4a95a3b7d79de97c7bb9`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `pin_attachment_download_button`.
- Карточка `topic_55eb769c556838b3b85760c2`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `restore_deleted_queue`.
- Карточка `topic_f8a687298dc51e1030ce10b0`: unscored_ambiguous_evidence_alignment; доставлена: False; тема по меткам: `None`.
- Карточка `topic_ecf92d64cdd58b1e7ba34f8c`: provisionally_unsupported_or_mixed; доставлена: False; тема по меткам: `None`.
- Карточка `topic_989000e28800a996e4030014`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `saml_sso`.
- Карточка `topic_4a10a526e0e6b8b76c17bb40`: provisionally_supported_evidence_and_class; доставлена: False; тема по меткам: `ticket_queue_change_webhook`.
- Пропущена или не подтверждена повторяющаяся тема `scheduled_email_report`: 3 эпизодов, 2 клиентов.
- Пропущена или не подтверждена повторяющаяся тема `ticket_attachments_zip`: 3 эпизодов, 2 клиентов.
- Пропущена или не подтверждена повторяющаяся тема `role_change_audit`: 3 эпизодов, 3 клиентов.

Model statuses and classes:

- all: statuses `{"needs_review": 4, "ok": 44}`; class presence `{"feature_request": 40, "incident": 3, "service_request": 9, "unknown": 1, "usability": 13}`.
- case_pdf: statuses `{}`; class presence `{}`.
- synthetic: statuses `{"needs_review": 4, "ok": 44}`; class presence `{"feature_request": 40, "incident": 3, "service_request": 9, "unknown": 1, "usability": 13}`.

Model verification (separate from extraction expectations):

A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.

- Calls: 40; valid contracts: 40; verdicts: `{"supported": 36, "unsupported": 4, "unclear": 0, "invalid": 0}`.
- Blocking violations: 0.
- `hv2_001` / `intent_5e9ee3480106f25aa7db8cd8`: supported; blocking respected: True.
- `hv2_002` / `intent_0ddb3a4376604051fc96e2b0`: supported; blocking respected: True.
- `hv2_003` / `intent_188b052de3648457a2f142da`: supported; blocking respected: True.
- `hv2_004` / `intent_be0e85d073e4686a0cdccd85`: supported; blocking respected: True.
- `hv2_005` / `intent_202a699c5ff925b09c931581`: supported; blocking respected: True.
- `hv2_007` / `intent_15d1346c33afa31af2965e60`: supported; blocking respected: True.
- `hv2_009` / `intent_a5236933990a9802434b88dc`: supported; blocking respected: True.
- `hv2_009` / `intent_e96a938c13f5df7aad05c84e`: supported; blocking respected: True.
- `hv2_011` / `intent_fd57e8f9208faeb7a5a1281f`: supported; blocking respected: True.
- `hv2_011` / `intent_aa22365e4c5c1f4e0d5df7af`: unsupported; blocking respected: True.
- `hv2_013` / `intent_0df78a6460c97c3804c2b182`: supported; blocking respected: True.
- `hv2_014` / `intent_8cb9d2d3f45431d5c6d4f6c7`: supported; blocking respected: True.
- `hv2_015` / `intent_f90911750b4382a7b1f7d50a`: supported; blocking respected: True.
- `hv2_016` / `intent_f7e318ae4f514b3e97cd65a3`: supported; blocking respected: True.
- `hv2_017` / `intent_73f86984c1e6f27f4c81ebc5`: supported; blocking respected: True.
- `hv2_018` / `intent_116bdceda1872cf9a2c43d27`: supported; blocking respected: True.
- `hv2_019` / `intent_fef1cf1cecd808ea4b57c8b5`: supported; blocking respected: True.
- `hv2_019` / `intent_cad9b570dffbec02bebce576`: unsupported; blocking respected: True.
- `hv2_020` / `intent_9e320b197302db4ba15c3b6e`: supported; blocking respected: True.
- `hv2_021` / `intent_01136c34cb6151fce2ace012`: supported; blocking respected: True.
- `hv2_022` / `intent_240f18215f0bccb5e524008a`: supported; blocking respected: True.
- `hv2_023` / `intent_c4b73e2bfd038da5cffa946a`: supported; blocking respected: True.
- `hv2_024` / `intent_51fa8ca28922cd396a7bf424`: supported; blocking respected: True.
- `hv2_025` / `intent_c5b4997a687a6f7f3681fd87`: supported; blocking respected: True.
- `hv2_026` / `intent_c96631e7adfc0bf28c7a2d8a`: supported; blocking respected: True.
- `hv2_026` / `intent_468e33f7f621969865eb153b`: unsupported; blocking respected: True.
- `hv2_027` / `intent_53587fa07daee1a8042437f4`: supported; blocking respected: True.
- `hv2_028` / `intent_605abb8fe82a31e8d69cb490`: supported; blocking respected: True.
- `hv2_029` / `intent_ca4a1fd766a30c8e741d4684`: supported; blocking respected: True.
- `hv2_033` / `intent_fece113fbef94a357933ce65`: supported; blocking respected: True.
- `hv2_033` / `intent_147531df4239c41eda23218b`: supported; blocking respected: True.
- `hv2_034` / `intent_d0e22248739fea5c4854ff9b`: unsupported; blocking respected: True.
- `hv2_039` / `intent_659957f10cd13dd55765b08f`: supported; blocking respected: True.
- `hv2_040` / `intent_881cc0f618b5c74d1b818d77`: supported; blocking respected: True.
- `hv2_041` / `intent_32351a011d0e58e335375eaf`: supported; blocking respected: True.
- `hv2_041` / `intent_f6c45d0d044bc14b043e0a0c`: supported; blocking respected: True.
- `hv2_042` / `intent_b2096218ff8cce74eca8af65`: supported; blocking respected: True.
- `hv2_043` / `intent_3ed80d8c03fe0125fef1406b`: supported; blocking respected: True.
- `hv2_044` / `intent_9ba5c86ff536baff98971d9c`: supported; blocking respected: True.
- `hv2_044` / `intent_a4084beee1f6cbb0ae03e06d`: supported; blocking respected: True.

Focused checks:

- `syn07_two_separate_intents`: **not applicable**. "Separate incident and feature_request intents must both survive the contract."
- `syn01_04_one_topic_and_deduplicated_snapshot`: **not applicable**. {"topic_ids_by_source": {"syn-01": [], "syn-02": [], "syn-03": [], "syn-04": []}, "snapshot": null}
- `syn10_invoices_separate_from_orders`: **not applicable**. {"orders_topic": null, "invoice_topics": []}
- `trusted_authorship_respected_by_raw_model`: **not met**. {"violating_sources": ["hv2_037"], "unprocessed_sources": []}
- `no_invented_source_or_identity_fields_in_raw_extraction`: **met**. {"violating_sources": [], "unprocessed_sources": [], "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}
- `snapshot_counts_use_only_trusted_known_identities`: **met**. {"count_mismatches": [], "unprocessed_sources": []}

Disagreements with preliminary expectations:

- `hv2_006` (synthetic): status `ok`, classes `feature_request`; explicit feature flag differs.
- `hv2_007` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_008` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_010` (synthetic): status `ok`, classes `service_request, usability`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_012` (synthetic): status `ok`, classes `feature_request`; explicit feature flag differs.
- `hv2_022` (synthetic): status `ok`, classes `feature_request, incident`; kinds outside accepted set or no intents.
- `hv2_027` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_028` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_029` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents.
- `hv2_030` (synthetic): status `ok`, classes `incident, service_request`; kinds outside accepted set or no intents.
- `hv2_032` (synthetic): status `ok`, classes `service_request, usability`; kinds outside accepted set or no intents.
- `hv2_034` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_035` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_036` (synthetic): status `needs_review`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_037` (synthetic): status `needs_review`, classes `feature_request, usability`; invalid extraction contract; kinds outside accepted set or no intents; explicit feature flag differs.
  Contract: intents[0].origin: unverified user authorship; needs_review required
- `hv2_038` (synthetic): status `needs_review`, classes `unknown`; status differs.
- `hv2_039` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_042` (synthetic): status `ok`, classes `feature_request, service_request`; kinds outside accepted set or no intents; explicit feature flag differs.
- `hv2_045` (synthetic): status `ok`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_046` (synthetic): status `needs_review`, classes `feature_request, usability`; kinds outside accepted set or no intents.
- `hv2_047` (synthetic): status `ok`, classes `service_request, usability`; kinds outside accepted set or no intents.
- `hv2_048` (synthetic): status `ok`, classes `service_request`; kinds outside accepted set or no intents.

Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.
