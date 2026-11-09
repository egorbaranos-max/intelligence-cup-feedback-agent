---
description: Пересобрать сабмишн, обновить manifest и прогнать все офлайн-проверки
---
Пересобери комплект для сдачи и проверь его.

1. Если `scripts/build_submission.py` отсутствует — остановись и сообщи: сначала нужно создать скрипт по ТЗ из `team/sprint-plan.md`, раздел 8.1.
2. Запусти `python3 scripts/build_submission.py`. Дождись завершения, покажи его итоговую таблицу «файл — символов — страниц — хеш — статус лимита».
3. Запусти проверки по порядку и собери результаты:
   - `python3 scripts/check_submission.py --require-file docs/solution.md --require-file docs/metrics.md --require-file submission/solution.docx --require-file submission/solution.pdf --require-file submission/presentation.pptx --require-file submission/metrics.md`
   - `python3 -m unittest discover -s tests -p 'test_*.py'`
   - `python3 scripts/verify_delivery.py --output artifacts/build-audit.json`
4. Проверь, что `submission/manifest.json` содержит актуальные SHA-256 для всех файлов из `submission/` и `docs/solution.md`, `docs/metrics.md`, `docs/ai-footnotes.md`.
5. Проверь, что в `submission/` нет файлов, которых нет в manifest, и наоборот.
6. Выведи сводку: статус каждой проверки, число символов основного документа, число страниц pdf, число слайдов pptx, дата сборки.

Если любая проверка упала — не коммить. Покажи ошибку и предложи исправление. Если всё зелёное — предложи текст коммита вида «Пересобрать сабмишн: <что изменилось в источниках>» и жди подтверждения перед `git commit`.
