"""One-command offline audit; proves checked artifacts, not model quality."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional new JSON report; never overwrite an audit")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.output and args.output.exists():
        parser.error("Use a new output filename")
    commands = [
        ("Program contracts", ["-m", "unittest", "discover", "-s", "demo", "-p", "test_*.py"]),
        ("Pipeline, evaluation, finance, metrics and human-label safeguards", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
        ("Saved real model evidence", ["scripts/check_live_runs.py"]),
        ("Submission files and character limit", ["scripts/check_submission.py", "--require-file", "submission/solution.docx", "--require-file", "submission/solution.pdf", "--require-file", "submission/presentation.pptx", "--require-file", "submission/metrics.md"]),
    ]
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "checks": [],
              "scope": "offline verification only; no model inference, corporate access or financial validation"}
    for label, command in commands:
        begin = time.perf_counter()
        print(f"Checking: {label}", flush=True)
        try:
            result = subprocess.run([sys.executable, *command], cwd=root, capture_output=True, text=True, timeout=180)
            record = {"name": label, "command": [sys.executable, *command], "exit_code": result.returncode,
                      "elapsed_seconds": round(time.perf_counter() - begin, 3),
                      "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            record = {"name": label, "command": [sys.executable, *command], "exit_code": 124, "error": "180-second timeout"}
        report["checks"].append(record)
        print("PASS" if record["exit_code"] == 0 else "FAIL", flush=True)
        if record["exit_code"]:
            print(record.get("stdout", "") + record.get("stderr", "") + record.get("error", ""), flush=True)
    report["passed"] = all(c["exit_code"] == 0 for c in report["checks"])
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation preserves earlier audit evidence even on a race.
        with args.output.open("x") as file:
            json.dump(report, file, ensure_ascii=False, indent=2)
            file.write("\n")
    print("Offline checks passed. This does not establish AI accuracy or production readiness." if report["passed"]
          else "Some checks failed. Read the diagnostics; do not treat the delivery as verified.")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
