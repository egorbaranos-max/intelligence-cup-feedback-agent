"""Verify recorded live experiments without inference or rewriting evidence."""
import json
from pathlib import Path

from evaluate_live_run import evaluate


root = Path(__file__).resolve().parents[1]
count = 0
for dataset in ("live_qwen", "fresh_probe"):
    folder = root / "experiments" / dataset
    for run in sorted((folder / "runs").glob("run-*")):
        actual = evaluate(run, folder / "inputs.jsonl", folder / "expectations.json")
        recorded = json.loads((run / "evaluation.json").read_text())
        if actual != recorded:
            raise SystemExit(f"Saved evaluation differs: {dataset}/{run.name}")
        count += 1
if count != 4:
    raise SystemExit(f"Expected four recorded experiments, found {count}")
print("Verified four saved live runs: input/output hashes, contracts and recorded comparisons. No model inference or quality acceptance.")
