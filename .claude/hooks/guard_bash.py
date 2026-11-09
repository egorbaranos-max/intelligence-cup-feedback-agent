#!/usr/bin/env python3
"""Хук PreToolUse для Bash.

Блокирует разрушительные команды, в том числе замаскированные пробелами,
кавычками или цепочками через ; && ||. Код возврата 2 — запрет, 0 — разрешить.
Формат входного JSON сверить с документацией hooks: ожидается tool_input.command.
"""
import json
import re
import sys

BLOCKED_PATTERNS = [
    (r"(^|[;&|]\s*)sudo\b", "sudo запрещён: системные изменения делает человек"),
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b", "rm -rf запрещён"),
    (r"\brm\s+-[a-zA-Z]*r\b", "рекурсивное удаление запрещено"),
    (r"\bgit\s+push\b[^;&|]*\s(--force|-f)\b", "force-push запрещён"),
    (r"\bgit\s+push\b[^;&|]*\s--force-with-lease\b", "force-push запрещён"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard запрещён"),
    (r"\bgit\s+branch\s+-D\b", "удаление веток запрещено"),
    (r"\bgit\s+clean\b", "git clean запрещён"),
    (r"\bgit\s+rebase\b", "переписывание истории запрещено"),
    (r"\bgit\s+filter-branch\b", "переписывание истории запрещено"),
    (r"\bgit\s+checkout\s+(--\s+)?(agent|demo|tools|tests|experiments)/", "откат FROZEN-файлов запрещён"),
    (r"\bgit\s+(rm|mv)\s+[^;&|]*(agent|demo|tools|tests|experiments)/", "перемещение и удаление FROZEN запрещено"),
    (r"(>|>>)\s*(agent|demo|tools|tests|experiments|submission)/", "запись в FROZEN и submission/ через перенаправление запрещена"),
    (r"\b(mkfs|dd\s+if=|chmod\s+-R\s+777|chown\s+-R)\b", "опасная системная команда"),
    (r"\bcurl\b[^;&|]*\s(-d|--data|-F|--form|-T|--upload-file)\b", "отправка данных наружу запрещена"),
    (r"\bscp\b|\brsync\b[^;&|]*@", "копирование на другие машины запрещено"),
    (r"\bgit\s+push\b[^;&|]*\s(main|master)\b", "push в main запрещён: только через PR"),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0

    normalized = re.sub(r"\s+", " ", command.strip())
    for pattern, reason in BLOCKED_PATTERNS:
        if re.search(pattern, normalized):
            sys.stderr.write(
                "Запрещено хуком guard_bash: " + reason + ". Команда: " + normalized + "\n"
                "См. CLAUDE.md, раздел 3, и EXECUTOR.md, раздел 2.3 (красная зона).\n"
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
