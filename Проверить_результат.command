#!/bin/zsh
set -eu
REPO_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$REPO_DIR"
if [[ -x "$REPO_DIR/.venv/bin/python" ]]; then
  AUDIT_PYTHON="$REPO_DIR/.venv/bin/python"
elif [[ -x "$REPO_DIR/../../work/live-qwen-venv/bin/python" ]]; then
  AUDIT_PYTHON="$REPO_DIR/../../work/live-qwen-venv/bin/python"
else
  AUDIT_PYTHON="python3"
fi
"$AUDIT_PYTHON" -c 'import sys; assert sys.version_info >= (3,10), "Нужен Python 3.10 или новее"'
AUDIT_PATH="artifacts/audit-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
AUDIT_EXIT_CODE=0
"$AUDIT_PYTHON" scripts/verify_delivery.py --output "$AUDIT_PATH" || AUDIT_EXIT_CODE=$?
if [[ -f "$AUDIT_PATH" ]]; then
  print "Результат проверки: $REPO_DIR/$AUDIT_PATH"
else
  print "JSON-отчет не создан. Смотрите причину в сообщениях выше."
fi
if (( AUDIT_EXIT_CODE != 0 )); then
  print "Проверка завершилась с ошибкой. Прочитайте сообщения выше и сохраненный JSON; успешная проверка не подтверждена."
  exit "$AUDIT_EXIT_CODE"
fi
print "Эта проверка не вызывает модель. Для нового запуска Qwen откройте Запустить_проверку.command."
