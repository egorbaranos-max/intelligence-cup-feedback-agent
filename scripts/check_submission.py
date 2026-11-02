#!/usr/bin/env python3
"""Check source-text size and required artifacts; no document parsers or network."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solution", default="docs/solution.md")
    parser.add_argument("--max-chars", type=int, default=15000)
    parser.add_argument("--require-file", action="append", default=[])
    parser.add_argument("--manifest", default="submission/manifest.json",
                        help="SHA-256 manifest of the visually checked exported artifacts")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    solution = root / args.solution
    if not solution.is_file():
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
    metric_source, metric_copy = root / "docs/metrics.md", root / "submission/metrics.md"
    if metric_source.read_bytes() != metric_copy.read_bytes():
        print("ERROR: source and submission metrics differ", file=sys.stderr)
        return 1
    try:
        manifest = json.loads((root / args.manifest).read_text(encoding="utf-8"))
        if manifest["source_characters"] != len(solution.read_text(encoding="utf-8")):
            raise ValueError("source character count differs from manifest")
        for name, expected in manifest["sha256"].items():
            actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"{name}: file changed after the checked export")
        if not manifest["sha256"]:
            raise ValueError("empty artifact manifest")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: artifact manifest: {error}", file=sys.stderr)
        return 1
    print(f"Metrics copies match; SHA-256 verified for {len(manifest['sha256'])} sources/artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
