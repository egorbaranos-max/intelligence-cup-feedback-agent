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
AUDIT_PATH="artifacts/audit-$(date -u +%Y%m%dT%H%M%SZ).json"
"$AUDIT_PYTHON" scripts/verify_delivery.py --output "$AUDIT_PATH"
print "Результат проверки: $REPO_DIR/$AUDIT_PATH"
print "Эта проверка не вызывает модель. Для нового запуска Qwen откройте Запустить_проверку.command."
