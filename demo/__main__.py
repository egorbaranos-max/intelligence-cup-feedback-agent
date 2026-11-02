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
    parser.add_argument("--compact", action="store_true",
                        help="Краткий сценарий для устной защиты вместо полного JSON")
    args = parser.parse_args()
    data = run_demo()
    if args.compact:
        labels = {
            "three_sources_two_episodes_blocked": "До порога",
            "four_sources_three_episodes_eligible": "После третьего эпизода",
            "after_call_delete": "Удален связанный звонок",
            "after_episode_delete_below_threshold": "Удален независимый эпизод",
        }
        lines = [data["disclaimer"]]
        for key, label in labels.items():
            card = data[key]
            lines.append(f"{label}: источники={card['raw_sources']}, "
                         f"эпизоды={card['independent_episodes']}, "
                         f"клиенты={card['known_customers']}, "
                         f"порог={'пройден' if card['recurring'] else 'не пройден'}")
        lines.append(f"Карточек после потери ACK и повтора: {data['mock_destination_cards_after_retry']}")
        lines.append(f"Карточек после потери эпизода: {data['destination_cards_after_episode_delete']}")
        lines.append(data["limits"])
        result = "\n".join(lines) + "\n"
    else:
        result = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
