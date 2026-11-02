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
from .verifier_v2 import verification_messages, validate_verification
from .repair import extraction_repair_messages
from .prompts import VERIFICATION_POLICY
from .registry import candidate_plan, resolve_registry_topic, MAX_REGISTRY_CANDIDATES, BATCH_SIZE
from .source_risks import detect_source_risks
from .response_schemas import STAGE_SCHEMAS


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
    manifest = {"status": "running", "contract_version": "text-spans-v3-chunked-repair-v1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of, "inputs_sha256": sha(inputs_path), "source_count": len(sources),
        "model": backend.provenance, "pre_run_artifact_sha256": before_run_hashes or {},
        "code_sha256": {"agent/" + p.name: sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "limits": ["text only", "no corporate API", "mock local receiver", "no financial validation",
                   "no human gold", "single ordered batch; matching can depend on input order",
                   "model verification is not human approval",
                   "at most one extraction retry after failed mechanical validation; no semantic retry",
                   "usability observations require human review and never count as automatic wishes",
                   "complete product registry comparison up to 25 candidates; overflow requires review",
                   "limited heuristic source-risk guard can miss attacks and flag legitimate prompt-editor requests",
                   "extraction needs_review or source-risk guard holds all intents in that source",
                   "a source review queue entry can coexist with acceptance of its other verified intents"]}
    manifest["extraction_repair_limit"] = 1
    manifest["registry_candidate_limit"] = MAX_REGISTRY_CANDIDATES
    manifest["registry_batch_size"] = BATCH_SIZE
    contract_code = Path(__file__).resolve().parents[1] / "demo" / "case_contract_demo.py"
    manifest["code_sha256"]["demo/case_contract_demo.py"] = sha(contract_code)
    version_seed = json.dumps({"code": manifest["code_sha256"], "model": backend.provenance}, sort_keys=True)
    manifest["pipeline_version"] = "text-" + hashlib.sha256(version_seed.encode()).hexdigest()[:24]
    dump(output_path / "manifest.json", manifest)
    demo = ContractDemo(now=now)
    demo.grant("local-reviewer", {s["product_id"] for s in sources})
    topics, results, call_count = [], [], 0
    review_queue, source_audit = [], []

    def invoke(stage, source_id, messages, limit, intent_id=None, repair_of=None):
        nonlocal call_count
        call_count += 1
        call = {"call_id": call_count, "stage": stage, "source_id": source_id,
                "messages": messages, "raw_response": None, "stats": None,
                "response_schema": STAGE_SCHEMAS[stage]}
        if intent_id is not None:
            call["intent_id"] = intent_id
        if repair_of is not None:
            call["repair_of"] = repair_of
        try:
            raw, stats = backend.generate(messages, max_tokens=limit, schema_name=STAGE_SCHEMAS[stage])
            call.update(status="complete", raw_response=raw, stats=stats)
        except Exception as exc:
            call.update(status="failed", error_type=type(exc).__name__, error=str(exc))
            if isinstance(getattr(exc, "raw_response", None), str):
                call["raw_response"] = exc.raw_response
            if isinstance(getattr(exc, "stats", None), dict):
                call["stats"] = exc.stats
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
            source_risks = detect_source_risks(source["text"])
            raw, call_id = invoke("extraction", source["id"], extraction_messages(source), 1200)
            extracted = validate_extraction(raw, source)
            first_pass = extracted
            attempts = [call_id]
            if not extracted.ok:
                raw, repaired_call = invoke("extraction_repair", source["id"],
                    extraction_repair_messages(source, raw, extracted.errors), 1200, repair_of=call_id)
                call_id = repaired_call
                attempts.append(call_id)
                extracted = validate_extraction(raw, source)
            result = {"source_id": source["id"], "origin": source.get("origin", "unspecified"),
                      "extraction_call": call_id, "extraction_attempts": attempts,
                      "first_pass_extraction": asdict(first_pass),
                      "extraction": asdict(extracted), "source_risks": source_risks, "assignments": []}
            assignments = {}
            if extracted.ok:
                for intent in extracted.value["intents"]:
                    plan = candidate_plan(intent, source, topics)
                    eligible = (not intent["review_required"] and intent["origin"] == "user_explicit"
                                and intent["kind"] == "feature_request")
                    verification, verification_call = None, None
                    gate_open = False
                    if eligible and not source_risks:
                        messages = verification_messages(source, intent)
                        messages[0]["content"] = VERIFICATION_POLICY + "\n" + messages[0]["content"]
                        raw_verification, verification_call = invoke("verification", source["id"],
                            messages, 700, intent["intent_id"])
                        verification = validate_verification(raw_verification, source, intent)
                        gate_open = verification.ok and verification.value["verdict"] == "supported"
                    batch_results, batch_records = [], []
                    if gate_open and plan["complete"]:
                        for candidates in plan["batches"]:
                            raw_match, match_call = invoke("matching", source["id"],
                                matching_messages(intent, candidates), 900, intent["intent_id"])
                            match = validate_matching(raw_match, candidates)
                            batch_results.append(match)
                            batch_records.append({"call_id": match_call,
                                "candidate_ids": [c["id"] for c in candidates], "matching": asdict(match)})
                    if source_risks:
                        decision = {"status": "needs_review", "topic_id": None,
                                    "reason": "Source-risk guard: all intents held for human review; no automatic evidence count"}
                    elif intent["kind"] == "usability":
                        decision = {"status": "needs_review", "topic_id": None,
                                    "reason": "Observed usability pain requires explicit-change review; no automatic wish count"}
                    elif eligible and not gate_open:
                        decision = {"status": "needs_review", "topic_id": None,
                                    "reason": "Wish support not confirmed by semantic verifier"}
                    else:
                        decision = resolve_registry_topic(intent, source, plan, batch_results)
                    if decision["status"] == "new":
                        topic = {"id": decision["topic_id"], "product_id": source["product_id"],
                                 "statement": intent["statement"]}
                        topics.append(topic)
                        demo.add_topic(topic["id"], topic["product_id"], topic["statement"])
                    assignments[intent["intent_id"]] = decision["topic_id"]
                    result["assignments"].append({"intent_id": intent["intent_id"],
                        "verification_call": verification_call,
                        "verification": asdict(verification) if verification else None,
                        "matching_call": None, "matching": None,
                        "matching_calls": [b["call_id"] for b in batch_records],
                        "matching_batches": batch_records,
                        "candidate_pool_size": plan["candidate_pool_size"], "candidate_ids": plan["candidate_ids"],
                        "registry_complete": plan["complete"], "registry_error": plan["error"],
                        "registry_compared": gate_open and plan["complete"] and len(batch_results) == len(plan["batches"]),
                        **decision})
                if source_risks:
                    result["counting"] = "held for review: explicit processor-control or fabricated-evidence risk"
                elif extracted.value["status"] == "ok" and extracted.value["intents"]:
                    if source.get("episode_at") is None:
                        result["counting"] = "excluded: missing trusted episode time"
                    else:
                        demo.register_source(Source(source["id"], 1, source["product_id"],
                            source.get("customer_id"), source.get("episode_id"), now + 365 * 86400,
                            (Fragment("body", source["text"], speaker=source["speaker"]),),
                            episode_at=stamp(source["episode_at"])))
                        demo.analyze("local-reviewer", prepared_contract_payload(source, extracted, assignments,
                            pipeline_version=manifest["pipeline_version"]))
                        result["counting"] = "local contract accepted; unknown identities do not add episodes/customers"
                else:
                    result["counting"] = "held for review or no intents"
            else:
                result["counting"] = "blocked: invalid model response"
            if source_risks:
                result["counting"] = "held for review: explicit processor-control or fabricated-evidence risk"
            # Keep all nonautomatic outcomes visible. The audit includes even
            # apparently ordinary incidents/operations so false negatives can
            # be sampled; the review queue is not an estimate of model quality.
            review_reasons = []
            if source_risks:
                review_reasons.append("source_risk_guard")
            if not extracted.ok:
                review_reasons.append("invalid_extraction_contract")
            elif extracted.value["status"] == "needs_review":
                review_reasons.append("source_requires_review")
            if any(a["status"] == "needs_review" for a in result["assignments"]):
                review_reasons.append("intent_requires_review")
            if any(a["topic_id"] for a in result["assignments"]):
                if source.get("episode_at") is None:
                    review_reasons.append("missing_episode_time")
                if source.get("episode_id") is None or source.get("customer_id") is None:
                    review_reasons.append("missing_recurrence_identity")
            audit = {"source_id": source["id"], "review_required": bool(review_reasons),
                     "source_risks": source_risks,
                     "review_reasons": review_reasons,
                     "extraction_status": extracted.value["status"] if extracted.ok else "invalid",
                     "intent_count": len(extracted.value["intents"]) if extracted.ok else None,
                     "assignment_statuses": [a["status"] for a in result["assignments"]],
                     "topic_ids": sorted({a["topic_id"] for a in result["assignments"] if a["topic_id"]}),
                     "counting": result["counting"],
                     "audit_note": "All categories need human sampling to discover missed wishes"}
            source_audit.append(audit)
            result["review_required"] = bool(review_reasons)
            result["review_reasons"] = review_reasons
            if review_reasons:
                review_queue.append({**audit, "source_text": source["text"],
                    "product_id": source["product_id"], "extraction_call": result["extraction_call"],
                    "errors": extracted.errors})
            # Save incrementally: a later backend failure must not erase the
            # manual-review backlog or already-completed source dispositions.
            dump(output_path / "review-queue.json", review_queue)
            dump(output_path / "source-audit.json", source_audit)
            result["cards_after_source"] = [demo.card("local-reviewer", t["id"]) for t in topics]
            results.append(result)
            with (output_path / "results.jsonl").open("a") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
            extraction_label = extracted.value["status"] if extracted.ok else "INVALID — " + "; ".join(extracted.errors)
            route_label = ("нужна проверка человеком: " + ", ".join(result["review_reasons"])
                           if result["review_required"] else "автоматический разбор завершён")
            print(f"[{index}/{len(sources)}] {source['id']}: извлечение={extraction_label}; {route_label}", flush=True)
        cards = [demo.card("local-reviewer", t["id"]) for t in topics]
        for card in cards:
            if card["recurring"]:
                demo.deliver_once("local-reviewer", demo.queue_card("local-reviewer", card["topic_id"]))
        dump(output_path / "topics.json", topics)
        dump(output_path / "cards.json", cards)
        dump(output_path / "local-receiver.json", list(demo.receiver.values()))
        manifest.update(status="complete", call_count=call_count,
            valid_extractions=sum(r["extraction"]["ok"] for r in results),
            first_pass_valid_extractions=sum(r["first_pass_extraction"]["ok"] for r in results),
            extraction_repair_calls=sum(len(r["extraction_attempts"]) - 1 for r in results),
            repaired_valid_extractions=sum(not r["first_pass_extraction"]["ok"] and r["extraction"]["ok"] for r in results),
            source_risk_flagged_sources=sum(bool(r["source_risks"]) for r in results),
            review_required_sources=len(review_queue),
            audited_sources=len(source_audit),
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
