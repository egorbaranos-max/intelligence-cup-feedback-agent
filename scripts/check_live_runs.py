"""Verify every registered saved experiment, without inference or rewriting it.

The registry makes deletion of an entire recorded run fail verification. New
run folders must be registered explicitly after their evidence is complete.
"""
import json
from pathlib import Path
import zipfile

try:
    from .evaluate_live_run import evaluate
except ImportError:
    from evaluate_live_run import evaluate


HISTORICAL_RUNS = {
    "live_qwen/runs/run-01", "live_qwen/runs/run-02", "live_qwen/runs/run-03",
    "fresh_probe/runs/run-01",
}


def registered_runs(root):
    experiments = Path(root) / "experiments"
    registry = json.loads((experiments / "recorded-runs.json").read_text(encoding="utf-8"))
    entries = registry.get("runs")
    if not isinstance(entries, list) or not all(isinstance(p, str) for p in entries):
        raise ValueError("Recorded-run registry must contain a runs array")
    if len(entries) != len(set(entries)) or not HISTORICAL_RUNS.issubset(entries):
        raise ValueError("Registry duplicates or missing historical recorded experiments")
    for entry in entries:
        parts = Path(entry).parts
        if len(parts) != 3 or parts[1] != "runs" or not parts[2].startswith("run-") or ".." in parts or Path(entry).is_absolute():
            raise ValueError("Unsafe or unsupported recorded-run path")
    discovered = {str(p.relative_to(experiments)) for p in experiments.glob("*/runs/run-*") if p.is_dir()}
    if discovered != set(entries):
        raise ValueError(f"Recorded run inventory differs: missing {sorted(set(entries) - discovered)}; unregistered {sorted(discovered - set(entries))}")
    return [(experiments / entry) for entry in sorted(entries)]


def verify(root):
    runs = registered_runs(root)
    try:
        from .verify_code_snapshots import verify as verify_source_snapshots
    except ImportError:
        from verify_code_snapshots import verify as verify_source_snapshots
    verify_source_snapshots(root)
    for run in runs:
        folder = run.parent.parent
        actual = evaluate(run, folder / "inputs.jsonl", folder / "expectations.json")
        recorded = json.loads((run / "evaluation.json").read_text(encoding="utf-8"))
        if actual != recorded:
            raise ValueError(f"Saved evaluation differs: {run.relative_to(root)}")
        benchmark_path = run / "benchmark.json"
        if benchmark_path.exists():
            try:
                from .benchmark_live_run import benchmark
            except ImportError:
                from benchmark_live_run import benchmark
            actual_benchmark = benchmark(run, folder / "inputs.jsonl", folder / "expectations.json")
            if actual_benchmark != json.loads(benchmark_path.read_text(encoding="utf-8")):
                raise ValueError(f"Saved semantic benchmark differs: {run.relative_to(root)}")
    return len(runs)


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        count = verify(root)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        raise SystemExit(f"Saved-run verification failed: {exc}") from exc
    print(f"Verified {count} registered saved live runs: exact runtime source snapshots, input/output hashes, contracts and recorded comparisons. No model inference or quality acceptance.")


if __name__ == "__main__":
    main()
