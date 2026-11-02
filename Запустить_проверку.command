#!/bin/zsh
set -eu

REPO_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$REPO_DIR"
if [[ -x "$REPO_DIR/.venv/bin/python" && -f "$REPO_DIR/.local-models/model.json" ]]; then
  MODEL_PYTHON="$REPO_DIR/.venv/bin/python"
  MODEL_MANIFEST="$REPO_DIR/.local-models/model.json"
elif [[ -x "$REPO_DIR/../../work/live-qwen-venv/bin/python" && -f "$REPO_DIR/../../work/live-qwen-model.json" ]]; then
  MODEL_PYTHON="$REPO_DIR/../../work/live-qwen-venv/bin/python"
  MODEL_MANIFEST="$REPO_DIR/../../work/live-qwen-model.json"
else
  print "Сначала установите локальную модель по инструкции docs/live-experiment.md."
  exit 1
fi

RUN_DIR="artifacts/replay-$(date -u +%Y%m%dT%H%M%SZ)"
print "Проверяем 7 текстов из кейса и 16 вымышленных примеров."
print "Дата окна учета: 2 ноября 2026 года. Ответы модели сохраняются без исправлений."
"$MODEL_PYTHON" -m agent --inputs experiments/live_qwen/inputs.jsonl \
  --model-manifest "$MODEL_MANIFEST" --output "$RUN_DIR" --as-of 2026-11-02T12:00:00Z
"$MODEL_PYTHON" scripts/evaluate_live_run.py --run "$RUN_DIR" \
  --inputs experiments/live_qwen/inputs.jsonl --expectations experiments/live_qwen/expectations.json
"$MODEL_PYTHON" scripts/render_live_report.py --run "$RUN_DIR" --inputs experiments/live_qwen/inputs.jsonl
print "Отчет готов: $REPO_DIR/$RUN_DIR/report.html"
open "$REPO_DIR/$RUN_DIR/report.html"
