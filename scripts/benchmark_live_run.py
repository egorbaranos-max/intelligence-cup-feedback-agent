"""Separate post-hoc semantic benchmark for a saved v1 or v2 run.

Does not modify evaluation.json or any model evidence. V1 review workload is
inferred from saved decisions under v2 routing conditions; v1 had no saved queue.
All comparisons remain provisional AI-label comparisons, never human accuracy.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.evaluate_live_run import evaluate, load, lines, indexed, sha, V2_CONTRACTS
from scripts.evaluate_semantics import evaluate_semantics


def benchmark(run_path, inputs_path, expectations_path):
    run_path, inputs_path, expectations_path = map(Path, (run_path, inputs_path, expectations_path))
    # First run the established integrity audit and raw-response revalidation.
    evaluation = evaluate(run_path, inputs_path, expectations_path)
    manifest = load(run_path / "manifest.json")
    legacy = manifest.get("contract_version") not in V2_CONTRACTS
    if legacy:
        from agent.pipeline_v1 import validate_extraction
    else:
        from agent.pipeline import validate_extraction
    sources = indexed(lines(inputs_path), "id", "inputs")
    labels = load(expectations_path)
    expected = indexed(labels["cases"], "id", "expectations")
    calls = indexed(lines(run_path / "calls.jsonl"), "call_id", "calls")
    results = indexed(lines(run_path / "results.jsonl"), "source_id", "results")
    validated = {source_id: validate_extraction(calls[row["extraction_call"]]["raw_response"], sources[source_id])
                 for source_id, row in results.items()}
    report = evaluate_semantics(run_path, sources, expected, labels.get("themes"), results,
                                validated, manifest, legacy_review=legacy)
    return {"benchmark_version": 1, "review_measurement": (
        "Post-hoc proxy from saved v1 dispositions under v2 routing rules; no materialized v1 review queue"
        if legacy else "Materialized v2 review queue, hash-bound and reconciled to saved dispositions"),
        "contract_version": manifest.get("contract_version", "legacy-text-v1"),
        "verified_sha256": evaluation["verified_sha256"], **report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--expectations", required=True, type=Path)
    args = parser.parse_args()
    target = args.run / "benchmark.json"
    try:
        if target.exists():
            raise FileExistsError("Benchmark already exists; refusing to overwrite")
        report = benchmark(args.run, args.inputs, args.expectations)
        with target.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Benchmark refused: {exc}\n")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(report["review_measurement"])
    print(report["disclaimer"])


if __name__ == "__main__":
    main()
