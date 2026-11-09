#!/usr/bin/env python3
"""Хук PreToolUse для Edit / MultiEdit / Write.

Блокирует запись в замороженные папки доказательной базы и в submission/
(который собирается только скриптом). Код возврата 2 — запрет с сообщением,
0 — разрешить. Формат входного JSON сверить с документацией hooks:
ожидается объект с полем tool_input, внутри file_path.
"""
import json
import os
import sys

FROZEN_PREFIXES = (
    "agent/",
    "demo/",
    "tools/",
    "tests/",
    "experiments/",
    "submission/",
)
FROZEN_FILES = (
    "scripts/check_live_runs.py",
)
FROZEN_FILE_PREFIXES = (
    "scripts/verify_",
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # нет данных — не мешаем

    tool_input = payload.get("tool_input") or {}
    raw_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not raw_path:
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    abs_path = os.path.abspath(os.path.join(project_dir, raw_path)) if not os.path.isabs(raw_path) else raw_path
    try:
        rel = os.path.relpath(abs_path, project_dir).replace(os.sep, "/")
    except ValueError:
        rel = raw_path.replace(os.sep, "/")

    blocked = (
        rel.startswith(FROZEN_PREFIXES)
        or rel in FROZEN_FILES
        or rel.startswith(FROZEN_FILE_PREFIXES)
    )
    if blocked:
        sys.stderr.write(
            "Запрещено: файл в замороженной зоне (" + rel + "). "
            "См. CLAUDE.md, разделы 2 и 3. Для submission/ используй "
            "scripts/build_submission.py. Изменение FROZEN требует записи "
            "в team/decisions.md и подтверждения человека.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
