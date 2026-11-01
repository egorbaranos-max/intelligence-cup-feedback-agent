#!/usr/bin/env python3
"""Check source-text size and required artifacts; no document parsers or network."""
import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solution", default="docs/solution.md")
    parser.add_argument("--max-chars", type=int, default=15000)
    parser.add_argument("--allow-missing-solution", action="store_true",
                        help="Temporary preparation mode; never use for final submission CI")
    parser.add_argument("--require-file", action="append", default=[])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    solution = root / args.solution
    if not solution.is_file():
        if args.allow_missing_solution:
            print("Preparation: solution not present yet; final size gate not exercised.")
        else:
            print(f"ERROR: missing solution: {args.solution}", file=sys.stderr)
            return 1
    else:
        text = solution.read_text(encoding="utf-8")
        count = len(text)
        print(f"{args.solution}: {count} Unicode characters including spaces, newlines and Markdown")
        if not text.strip() or count > args.max_chars:
            print(f"ERROR: source must be nonempty and <= {args.max_chars} characters", file=sys.stderr)
            return 1
    missing = [name for name in args.require_file
               if not (root / name).is_file() or (root / name).stat().st_size == 0]
    if missing:
        print("ERROR: required artifacts absent or empty: " + ", ".join(missing), file=sys.stderr)
        return 1
    if args.require_file:
        print(f"Required artifacts present and nonempty: {len(args.require_file)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
