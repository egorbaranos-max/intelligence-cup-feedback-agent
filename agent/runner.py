"""Run text extraction, model matching and the local card receiver; save raw evidence.

No evaluation labels are read here. This batch tool is not a corporate connector,
ASR/VL service, persistent database or production authorization boundary.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

from demo.case_contract_demo import ContractDemo, Fragment, Source
from .pipeline import (extraction_messages, validate_extraction, matching_messages,
                       validate_matching, resolve_topic, prepared_contract_payload)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("UTC timestamp required")
    return int(parsed.timestamp())


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def shortlist(intent, source, topics):
    """Small-batch lexical shortlist, not production search or an embedding model."""
    words = set(re.findall(r"\w+", intent["statement"].lower()))
    scope = [t for t in topics if t["product_id"] == source["product_id"]]
    ranked = sorted(scope, key=lambda t: (-len(words & set(re.findall(r"\w+", t["statement"].lower()))), t["id"]))
    return ranked[:5], len(scope)


def run(inputs_path, output_path, backend, as_of, before_run_hashes=None):
    inputs_path, output_path = Path(inputs_path), Path(output_path)
    # Existing evidence is immutable through this entry point; use a new run folder.
    output_path.mkdir(parents=True, exist_ok=False)
    sources = [json.loads(line) for line in inputs_path.read_text().splitlines() if line.strip()]
    if len({s["id"] for s in sources}) != len(sources):
        raise ValueError("Duplicate source IDs")
    # Validate every source before the first model call.
    for source in sources:
        extraction_messages(source)
        if source.get("episode_at") and stamp(source["episode_at"]) > stamp(as_of):
            raise ValueError("Source episode is later than replay clock")
    now, begin = stamp(as_of), time.perf_counter()
    manifest = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of, "inputs_sha256": sha(inputs_path), "source_count": len(sources),
        "model": backend.provenance, "pre_run_artifact_sha256": before_run_hashes or {},
        "code_sha256": {"agent/" + p.name: sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "limits": ["text only", "no corporate API", "mock local receiver", "no financial validation",
                   "no human gold", "single ordered batch; matching can depend on input order"]}
    contract_code = Path(__file__).resolve().parents[1] / "demo" / "case_contract_demo.py"
    manifest["code_sha256"]["demo/case_contract_demo.py"] = sha(contract_code)
    dump(output_path / "manifest.json", manifest)
    demo = ContractDemo(now=now)
    demo.grant("local-reviewer", {s["product_id"] for s in sources})
    topics, results, call_count = [], [], 0

    def invoke(stage, source_id, messages, limit):
        nonlocal call_count
        call_count += 1
        call = {"call_id": call_count, "stage": stage, "source_id": source_id,
                "messages": messages, "raw_response": None, "stats": None}
        try:
            raw, stats = backend.generate(messages, max_tokens=limit)
            call.update(status="complete", raw_response=raw, stats=stats)
        except Exception as exc:
            call.update(status="failed", error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            # Retain attempted prompts and failure type/message even when the
            # local model fails before returning a response. This is a local
            # evidence log; review/redact diagnostics before sharing externally.
            with (output_path / "calls.jsonl").open("a") as f:
                f.write(json.dumps(call, ensure_ascii=False) + "\n")
                f.flush()
        return raw, call_count

    try:
        for index, source in enumerate(sources, 1):
            raw, call_id = invoke("extraction", source["id"], extraction_messages(source), 1200)
            extracted = validate_extraction(raw, source)
            result = {"source_id": source["id"], "origin": source.get("origin", "unspecified"),
                      "extraction_call": call_id, "extraction": asdict(extracted), "assignments": []}
            assignments = {}
            if extracted.ok:
                for intent in extracted.value["intents"]:
                    candidates, pool_size = shortlist(intent, source, topics)
                    eligible = (not intent["review_required"] and intent["origin"] == "user_explicit"
                                and intent["kind"] in {"feature_request", "usability"})
                    match, match_call = None, None
                    if eligible and candidates:
                        raw_match, match_call = invoke("matching", source["id"], matching_messages(intent, candidates), 900)
                        match = validate_matching(raw_match, candidates)
                    decision = resolve_topic(intent, source, candidates, match)
                    # A truncated shortlist cannot prove absence from a larger registry.
                    if decision["status"] == "new" and pool_size > len(candidates):
                        decision = {"status": "needs_review", "topic_id": None,
                                    "reason": "Candidate search truncated; cannot establish novelty"}
                    if decision["status"] == "new":
                        topic = {"id": decision["topic_id"], "product_id": source["product_id"],
                                 "statement": intent["statement"]}
                        topics.append(topic)
                        demo.add_topic(topic["id"], topic["product_id"], topic["statement"])
                    assignments[intent["intent_id"]] = decision["topic_id"]
                    result["assignments"].append({"intent_id": intent["intent_id"],
                        "matching_call": match_call, "matching": asdict(match) if match else None,
                        "candidate_pool_size": pool_size, "candidate_ids": [c["id"] for c in candidates],
                        **decision})
                if extracted.value["status"] == "ok" and extracted.value["intents"]:
                    if source.get("episode_at") is None:
                        result["counting"] = "excluded: missing trusted episode time"
                    else:
                        demo.register_source(Source(source["id"], 1, source["product_id"],
                            source.get("customer_id"), source.get("episode_id"), now + 365 * 86400,
                            (Fragment("body", source["text"], speaker=source["speaker"]),),
                            episode_at=stamp(source["episode_at"])))
                        demo.analyze("local-reviewer", prepared_contract_payload(source, extracted, assignments))
                        result["counting"] = "local contract accepted; unknown identities do not add episodes/customers"
                else:
                    result["counting"] = "held for review or no intents"
            else:
                result["counting"] = "blocked: invalid model response"
            result["cards_after_source"] = [demo.card("local-reviewer", t["id"]) for t in topics]
            results.append(result)
            with (output_path / "results.jsonl").open("a") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
            print(f"[{index}/{len(sources)}] {source['id']}: " +
                  (extracted.value["status"] if extracted.ok else "INVALID — " + "; ".join(extracted.errors)), flush=True)
        cards = [demo.card("local-reviewer", t["id"]) for t in topics]
        for card in cards:
            if card["recurring"]:
                demo.deliver_once("local-reviewer", demo.queue_card("local-reviewer", card["topic_id"]))
        dump(output_path / "topics.json", topics)
        dump(output_path / "cards.json", cards)
        dump(output_path / "local-receiver.json", list(demo.receiver.values()))
        manifest.update(status="complete", call_count=call_count,
            valid_extractions=sum(r["extraction"]["ok"] for r in results),
            delivered_local_cards=len(demo.receiver))
    except Exception as exc:
        manifest.update(status="failed", error_type=type(exc).__name__, error=str(exc), call_count=call_count)
        raise
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        manifest["elapsed_seconds"] = round(time.perf_counter() - begin, 3)
        manifest["output_sha256"] = {p.name: sha(p) for p in sorted(output_path.glob("*.json*")) if p.name != "manifest.json"}
        dump(output_path / "manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model-manifest", required=True, type=Path)
    parser.add_argument("--as-of", required=True, help="UTC replay clock; separate from real run time")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    from .backend import LocalMLX
    # Freeze filenames/hashes only. Expectation contents never enter inference.
    hashes = {p.name: sha(p) for p in args.inputs.parent.glob("expectations.json")}
    backend = LocalMLX(args.model_manifest, args.seed)
    print(json.dumps(run(args.inputs, args.output, backend, args.as_of, hashes), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
