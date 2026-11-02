"""Offline consistency audit of the frozen three-run protocol; no inference.

Works in an extracted ZIP without Git. A local freeze-commit blob, when present
in this repository, is an additional check, not a dependency of the audit.
"""
from datetime import datetime
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

PROTOCOL_SHA256 = "90151b4278a8bbf125897d72e58916262ec66158f0d769a7a62a599b0b8d7189"
PROTOCOL_COMMIT = "fde343c0f11445236d3c51467dba792c7a078fb1"
MODEL_KEYS = {"4B": "live-qwen-model.json", "8B": "live-qwen-8b-model.json"}
MODEL_REFERENCES = {"4B": "live_qwen/runs/run-03", "8B": "fresh_probe/runs/run-05"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def utc_stamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Audit timestamps must contain a timezone")
    return result


def git_evidence(root, protocol_path):
    """Never inspect an enclosing repository or fetch a missing commit."""
    root = Path(root).resolve()
    unavailable = {"status": "not_available", "reason": "No matching local freeze commit; ZIP audit remains supported"}
    if not (root / ".git").exists():
        return unavailable
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=10)
    try:
        top = git("rev-parse", "--show-toplevel")
        if top.returncode or Path(top.stdout.decode().strip()).resolve() != root:
            return unavailable
        if git("cat-file", "-e", PROTOCOL_COMMIT + "^{commit}").returncode:
            return unavailable
        blob = git("show", PROTOCOL_COMMIT + ":experiments/holdout_v2/protocol.json")
    except (OSError, subprocess.TimeoutExpired):
        return unavailable
    if blob.returncode or blob.stdout != protocol_path.read_bytes():
        raise ValueError("Local freeze-commit protocol blob differs")
    return {"status": "verified", "commit": PROTOCOL_COMMIT,
            "blob_sha256": hashlib.sha256(blob.stdout).hexdigest()}


def verify(root, *, expected_protocol_sha=PROTOCOL_SHA256):
    root = Path(root).resolve()
    folder = root / "experiments" / "holdout_v2"
    protocol_path = folder / "protocol.json"
    if digest(protocol_path) != expected_protocol_sha:
        raise ValueError("Protocol bytes differ from the pre-inference SHA256")
    protocol = read(protocol_path)
    frozen_at = utc_stamp(protocol["recorded_before_inference_at_utc"])
    if len(protocol["runs"]) != 3:
        raise ValueError("Protocol must contain exactly three predeclared runs")
    for name, expected in protocol["data_sha256"].items():
        if Path(name).name != name or digest(folder / name) != expected:
            raise ValueError("Frozen input or expectation hash differs")
    for name, expected in protocol["code_sha256"].items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or digest(root / path) != expected:
            raise ValueError("Frozen candidate or evaluator source differs: " + name)
    sources = [json.loads(line) for line in (folder / "inputs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(sources) != 48 or len({s["id"] for s in sources}) != 48:
        raise ValueError("The frozen comparison requires 48 unique source records")
    baseline = read(root / "experiments" / MODEL_REFERENCES["4B"] / "manifest.json")
    candidate_code = {k: v for k, v in protocol["code_sha256"].items()
                      if k.startswith("agent/") or k.startswith("demo/")}
    previous_end, rows, seen = frozen_at, [], set()
    for index, specification in enumerate(protocol["runs"]):
        relative = Path(specification["path"])
        if relative.parts != ("runs", f"run-{index + 1:02d}") or str(relative) in seen:
            raise ValueError("Unexpected or duplicate protocol run path")
        seen.add(str(relative))
        run = folder / relative
        manifest = read(run / "manifest.json")
        if manifest.get("status") != "complete" or manifest.get("source_count") != 48:
            raise ValueError("Protocol run is not complete with 48 sources: " + str(relative))
        if manifest.get("inputs_sha256") != protocol["data_sha256"]["inputs.jsonl"]:
            raise ValueError("Run input hash differs: " + str(relative))
        if manifest.get("pre_run_artifact_sha256", {}).get("expectations.json") != protocol["data_sha256"]["expectations.json"]:
            raise ValueError("Run did not retain the frozen expectation hash: " + str(relative))
        if manifest.get("as_of") != protocol["as_of"]:
            raise ValueError("Run replay clock differs: " + str(relative))
        expected_code = baseline["code_sha256"] if index == 0 else candidate_code
        if manifest.get("code_sha256") != expected_code:
            raise ValueError("Runtime source inventory or hashes differ: " + str(relative))
        model_name = specification["model"]
        pinned = protocol["models"][MODEL_KEYS[model_name]]
        model = manifest["model"]
        if any(model.get(k) != pinned[k] for k in ("model_id", "revision")):
            raise ValueError("Pinned model differs: " + str(relative))
        reference = read(root / "experiments" / MODEL_REFERENCES[model_name] / "manifest.json")
        if not model.get("files") or model["files"] != reference["model"]["files"]:
            raise ValueError("Recorded model-file inventory differs from the pre-freeze reference")
        start, end = utc_stamp(manifest["started_at"]), utc_stamp(manifest["finished_at"])
        if not frozen_at < start <= end or start < previous_end:
            raise ValueError("Run chronology contradicts the frozen sequential protocol")
        previous_end = end
        output_hashes = manifest.get("output_sha256", {})
        if not {"calls.jsonl", "results.jsonl", "cards.json", "local-receiver.json"}.issubset(output_hashes):
            raise ValueError("Missing hash-bound raw protocol artifacts")
        for name, expected in output_hashes.items():
            if Path(name).name != name or digest(run / name) != expected:
                raise ValueError("Recorded run output hash differs: " + str(relative / name))
        result_rows = [json.loads(line) for line in (run / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(result_rows) != 48 or {r["source_id"] for r in result_rows} != {s["id"] for s in sources}:
            raise ValueError("Completed run does not account for all frozen source IDs")
        rows.append({"path": str(relative), "role": specification["role"],
            "model_id": model["model_id"], "revision": model["revision"],
            "manifest_sha256": digest(run / "manifest.json"),
            "started_at": manifest["started_at"], "finished_at": manifest["finished_at"],
            "input_and_expectation_hashes_match": True, "runtime_code_inventory_matches": True,
            "recorded_model_file_inventory_matches": True, "output_hashes_match": True,
            "all_48_source_ids_present": True})
    return {"status": "verified", "kind": "offline protocol and recorded evidence consistency",
        "protocol_sha256": expected_protocol_sha, "candidate_commit": protocol["candidate_commit"],
        "baseline_commit": protocol["baseline_commit"], "protocol_recorded_at": protocol["recorded_before_inference_at_utc"],
        "frozen_source_files_verified": len(protocol["code_sha256"]), "runs": rows,
        "git_evidence": git_evidence(root, protocol_path),
        "limitations": ["Timestamps are recorded claims, not independent time attestation.",
            "Hashes establish consistency, not who operated the model or semantic correctness.",
            "Model binaries are not downloaded or rehashed here; pinned metadata and prior recorded file inventories are compared.",
            "Exact runtime source ZIPs and saved evaluation equality are audited separately by check_live_runs.py.",
            "Optional Git availability can differ between a checkout and an extracted ZIP; it does not affect offline checks."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Optional new JSON report; existing files are never overwritten")
    args = parser.parse_args()
    report = verify(args.root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps({"status": report["status"], "runs": len(report["runs"]),
                      "git_evidence": report["git_evidence"]["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
