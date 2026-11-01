"""Run via python -m demo from a clean repository checkout."""
import argparse
import json
from pathlib import Path
from .case_contract_demo import run_demo


def main():
    parser = argparse.ArgumentParser(
        description="Синтетический демонстратор контрактов; Qwen/ASR/VL не запускаются.")
    parser.add_argument("--output", type=Path,
                        help="Сохранить JSON в указанный файл вместо stdout")
    args = parser.parse_args()
    result = json.dumps(run_demo(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
