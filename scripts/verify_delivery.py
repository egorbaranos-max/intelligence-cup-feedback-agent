"""One-command offline audit; proves checked artifacts, not model quality."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


INVENTORY_SCOPE = ("Python sources under agent/demo/tools/scripts/tests; root requirements and .command files; "
                   "GitHub workflows; submission files; main document/metrics/AI-footnote sources. "
                   "Generated audits and experiment runs are excluded; saved-run evidence has its own verification.")


def source_inventory(root):
    """Hash the inspected delivery independently of Git or machine-specific paths."""
    root = Path(root).resolve()
    paths = set()
    for folder in ("agent", "demo", "tools", "scripts", "tests"):
        paths.update((root / folder).rglob("*.py"))
    for pattern in ("requirements*.txt", "*.command", ".github/workflows/*.yml",
                    ".github/workflows/*.yaml", "submission/*"):
        paths.update(root.glob(pattern))
    paths.update(root / "docs" / name for name in ("solution.md", "metrics.md", "ai-footnotes.md"))
    result = {}
    for path in sorted(paths):
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(root):
            raise ValueError("Delivery inventory contains a link outside the repository")
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def git_evidence(root):
    """A ZIP nested inside another checkout must not inherit its parent's HEAD."""
    root = Path(root).resolve()
    git = shutil.which("git")
    if git is None:
        return {"git": None, "reason": "git_unavailable"}
    try:
        top = subprocess.run([git, "-C", str(root), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5)
        if top.returncode or Path(top.stdout.strip()).resolve() != root:
            return {"git": None, "reason": "no_repository_here"}
        head = subprocess.run([git, "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=5)
        status = subprocess.run([git, "-C", str(root), "status", "--porcelain=v1", "--untracked-files=normal"],
                                capture_output=True, text=True, timeout=5)
        if head.returncode or status.returncode:
            return {"git": None, "reason": "git_revision_unavailable"}
        return {"git": {"head": head.stdout.strip(), "dirty": bool(status.stdout.strip()),
                        "status_porcelain": status.stdout.splitlines()}}
    except (OSError, subprocess.TimeoutExpired):
        # Git diagnostics can expose local configuration. Source hashes remain
        # sufficient for a ZIP audit; no arbitrary stderr is copied into it.
        return {"git": None, "reason": "git_read_failed"}


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
    report = {"schema": "delivery-audit-v2", "started_at": datetime.now(timezone.utc).isoformat(), "checks": [],
              "scope": "offline verification only; no model inference, corporate access or financial validation"}
    report["revision_evidence"] = {"inventory_scope": INVENTORY_SCOPE,
        "git_start": git_evidence(root), "source_sha256_start": source_inventory(root)}
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
    revision = report["revision_evidence"]
    revision["git_end"] = git_evidence(root)
    revision["source_sha256_end"] = source_inventory(root)
    before, after = revision["source_sha256_start"], revision["source_sha256_end"]
    revision["changed_source_paths"] = sorted(path for path in set(before) | set(after)
                                               if before.get(path) != after.get(path))
    revision["source_inventory_unchanged"] = not revision["changed_source_paths"]
    report["passed"] = all(c["exit_code"] == 0 for c in report["checks"]) and revision["source_inventory_unchanged"]
    if not revision["source_inventory_unchanged"]:
        print("FAIL: delivery sources changed during the audit; rerun after edits finish.", flush=True)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation preserves earlier audit evidence even on a race.
        with args.output.open("x", encoding="utf-8") as file:
            json.dump(report, file, ensure_ascii=False, indent=2)
            file.write("\n")
    print("Offline checks passed. This does not establish AI accuracy or production readiness." if report["passed"]
          else "Some checks failed. Read the diagnostics; do not treat the delivery as verified.")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
