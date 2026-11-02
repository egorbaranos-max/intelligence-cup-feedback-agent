"""Evaluate saved text-experiment evidence without making any model calls.

These comparisons use frozen preliminary AI labels, not human gold. They are
neither corporate accuracy estimates nor acceptance gates. Existing reports
are never overwritten; preserve the run and use a separate copy for a rerun.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sys

# Direct execution from scripts/ must resolve the local, deterministic validators.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agent.pipeline import validate_extraction, validate_matching

DISCLAIMER = ("Frozen preliminary AI expectations only; not human gold, not a "
              "corporate accuracy estimate, not an acceptance gate. Text only; "
              "no financial effect, ASR/VL or corporate integration is tested.")
CHUNKED_CONTRACT = "text-spans-v3-chunked-repair-v1"
REPAIR_CONTRACTS = {"text-spans-v2-repair-v1", CHUNKED_CONTRACT}
V2_CONTRACTS = {"text-spans-v2", *REPAIR_CONTRACTS}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def indexed(rows, key, label):
    found = {}
    for row in rows:
        identifier = row.get(key)
        if identifier is None or identifier in found:
            raise ValueError(f"{label}: missing or duplicate {key}")
        found[identifier] = row
    return found


def parsed_model(raw):
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def model_intents(value):
    intents = value.get("intents", [])
    return [item for item in intents if isinstance(item, dict)] if isinstance(intents, list) else []


def kinds(value):
    return sorted({i["kind"] for i in model_intents(value) if isinstance(i.get("kind"), str)})


def explicit_feature(value):
    return any(i.get("kind") == "feature_request" and i.get("origin") == "user_explicit"
               for i in model_intents(value))


def topic_ids(result):
    return {a["topic_id"] for a in result.get("assignments", [])
            if a.get("topic_id") and a.get("status") in {"new", "matched"}}


def check(name, passed, details, applicable=True):
    return {"name": name, "applicable": applicable,
            "passed": bool(passed) if applicable else None, "details": details}


def audit_structured_completion(manifest, calls):
    """Reject contradictory grammar logs without changing saved report objects.

    This checks recorded lifecycle evidence, not that a model's meaning is right.
    Failed calls may retain an accepting prefix or a length stop; only completed
    calls must satisfy the backend's successful-completion policy.
    """
    grammar = manifest.get("model", {}).get("decoding", {}).get("structured_json", {})
    enabled = isinstance(grammar, dict) and grammar.get("enabled") is True
    if isinstance(grammar, dict) and grammar.get("mode") == "named_json_schemas" and not enabled:
        raise ValueError("Named-schema provenance must enable structured generation")
    for call in calls.values():
        stats = call.get("stats")
        structured = stats.get("structured_json") if isinstance(stats, dict) else None
        if not enabled:
            if structured is not None:
                raise ValueError("Structured call statistics lack enabled grammar provenance")
            continue
        if call.get("status") != "complete":
            continue
        if (not isinstance(stats, dict) or stats.get("finish_reason") != "stop"
                or not isinstance(structured, dict) or structured.get("accepting") is not True):
            raise ValueError("Completed structured call lacks normal stop and accepting grammar state")
    if enabled and (grammar.get("mode") == "named_json_schemas"
                    or any("response_schema" in call for call in calls.values())):
        audit_named_schemas(manifest, calls, grammar)


def audit_named_schemas(manifest, calls, grammar):
    """Bind each recorded stage to its frozen static schema and matcher log.

    Grammar fingerprints are checked for shape; recompiling a native grammar is
    deliberately not part of this stdlib audit. Exact runtime source archives
    and integration smoke evidence are verified separately.
    """
    from agent.response_schemas import RESPONSE_SCHEMAS, STAGE_SCHEMAS
    if grammar.get("mode") != "named_json_schemas":
        raise ValueError("Stage-specific call lacks named-schema provenance")
    recorded_code = manifest.get("code_sha256", {}).get("agent/response_schemas.py")
    if recorded_code != sha(ROOT / "agent" / "response_schemas.py"):
        raise ValueError("Missing or changed response-schema source after run")
    expected = {"generic": {"type": "object"}, **RESPONSE_SCHEMAS}
    records = grammar.get("schemas")
    if not isinstance(records, dict) or set(records) != set(expected):
        raise ValueError("Named-schema provenance inventory differs")
    schema_hashes = {}
    for name, schema in expected.items():
        record = records[name]
        digest = hashlib.sha256(json.dumps(schema, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        recorded_schema_hash = hashlib.sha256(json.dumps(record.get("schema"), sort_keys=True,
            separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest() if isinstance(record, dict) else None
        if not isinstance(record, dict) or recorded_schema_hash != digest or record.get("schema_sha256") != digest:
            raise ValueError("Recorded schema differs from frozen response schema")
        grammar_hash = record.get("grammar_sha256")
        if (not isinstance(grammar_hash, str) or len(grammar_hash) != 64
                or any(c not in "0123456789abcdef" for c in grammar_hash)):
            raise ValueError("Missing or malformed compiled-grammar fingerprint")
        schema_hashes[name] = digest
    for call in calls.values():
        name = STAGE_SCHEMAS.get(call.get("stage"))
        if name is None or call.get("response_schema") != name:
            raise ValueError("Call stage and requested response schema differ")
        if call.get("status") != "complete":
            # Construction failures can occur before processor statistics exist.
            continue
        stats = call.get("stats", {})
        matched = stats.get("structured_json", {})
        if (stats.get("response_schema") != name or matched.get("schema_name") != name
                or matched.get("schema_sha256") != schema_hashes[name]):
            raise ValueError("Completed call matcher schema differs from requested stage")


def evaluate_verification(calls, results, source_map, validated, manifest):
    """Audit model-verifier evidence separately from extraction expectations."""
    verification_calls = {identifier: call for identifier, call in calls.items()
                          if call["stage"] == "verification"}
    assignments_with_verification = [
        (source_id, assignment)
        for source_id, result in results.items()
        for assignment in result.get("assignments", [])
        if assignment.get("verification_call") is not None or assignment.get("verification") is not None]
    if not verification_calls:
        if assignments_with_verification:
            raise ValueError("Saved verification has no corresponding model calls")
        return None
    # New verification runs must bind the verifier contract to recorded source.
    # Old runs without this stage keep exactly their original report structure.
    v2 = manifest.get("contract_version") in V2_CONTRACTS
    filename = "verifier_v2.py" if v2 else "verifier.py"
    recorded = manifest.get("code_sha256", {}).get("agent/" + filename,
        manifest.get("code_sha256", {}).get(filename))
    if not recorded or recorded != sha(ROOT / "agent" / filename):
        raise ValueError(f"Missing or changed verifier source after run: {filename}")
    if v2:
        from agent.verifier_v2 import verification_messages, validate_verification
    else:
        from agent.verifier import verification_messages, validate_verification

    counts = {name: 0 for name in ("supported", "unsupported", "unclear", "invalid")}
    details, seen = [], set()
    for source_id, assignment in assignments_with_verification:
        call_id = assignment.get("verification_call")
        call = verification_calls.get(call_id)
        intent_id = assignment.get("intent_id")
        if not call or call.get("source_id") != source_id or call.get("intent_id") != intent_id:
            raise ValueError(f"Verification call/source/intent mismatch: {source_id}")
        if v2 and call.get("status") != "complete":
            raise ValueError("Failed verification call cannot supply a completed judgment")
        if call_id in seen:
            raise ValueError("Verification call reused by multiple assignments")
        seen.add(call_id)
        extraction = validated.get(source_id)
        if extraction is None or not extraction.ok:
            raise ValueError("Verification cannot bind to an invalid extraction")
        intents = [i for i in extraction.value["intents"] if i.get("intent_id") == intent_id]
        if len(intents) != 1:
            raise ValueError("Verification intent absent from validated extraction")
        source, intent = source_map[source_id], intents[0]
        # Compare the data payload only; the original system prompt is retained
        # in the immutable calls file and never re-executed by this evaluator.
        try:
            actual_payload = json.loads(call["messages"][-1]["content"])
            expected_payload = json.loads(verification_messages(source, intent)[-1]["content"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError("Malformed saved verification prompt") from exc
        if actual_payload != expected_payload:
            raise ValueError(f"Verification prompt differs from bound source/intent: {source_id}")
        verified = validate_verification(call.get("raw_response"), source, intent)
        if asdict(verified) != assignment.get("verification"):
            raise ValueError(f"Saved verification differs from raw-response revalidation: {source_id}")
        verdict = verified.value["verdict"] if verified.ok else "invalid"
        counts[verdict] += 1
        blocks = verdict != "supported"
        blocking_respected = (not blocks or
            (assignment.get("topic_id") is None and assignment.get("matching_call") is None))
        if manifest.get("contract_version") == CHUNKED_CONTRACT and blocks:
            blocking_respected = blocking_respected and not assignment.get("matching_calls") and not assignment.get("matching_batches")
        details.append({"call_id": call_id, "source_id": source_id, "intent_id": intent_id,
            "valid_contract": verified.ok, "verdict": verdict, "errors": verified.errors,
            "value": verified.value, "requires_blocking": blocks,
            "blocking_respected": blocking_respected,
            "assignment_status": assignment.get("status"), "topic_id": assignment.get("topic_id"),
            "matching_call": assignment.get("matching_call")})
    if seen != set(verification_calls):
        raise ValueError("Verification calls are not linked to saved assignments")
    return {"disclaimer": "A second model judgment, not human gold or proof of semantic correctness; errors may be correlated with extraction. Extraction expectation matches are unchanged by this block.",
            "calls": len(verification_calls), "valid_contracts": sum(d["valid_contract"] for d in details),
            "verdicts": counts, "blocking_violations": sum(not d["blocking_respected"] for d in details),
            "details": details}


def evaluate_extraction_attempts(source, result, calls, validate_extraction, expectation):
    """Audit one bounded model retry after a mechanical contract failure only."""
    from agent.repair import extraction_repair_messages
    from agent.pipeline import extraction_messages
    attempts = result.get("extraction_attempts")
    if (not isinstance(attempts, list) or not 1 <= len(attempts) <= 2
            or any(type(value) is not int for value in attempts) or len(set(attempts)) != len(attempts)
            or result.get("extraction_call") != attempts[-1]):
        raise ValueError("Extraction attempts must contain one or two unique calls, with final selected")
    selected = [calls.get(identifier) for identifier in attempts]
    if any(not call or call.get("source_id") != source["id"] for call in selected):
        raise ValueError("Extraction attempt source/call mismatch")
    if any(call.get("status") != "complete" for call in selected):
        raise ValueError("Failed extraction attempt cannot supply a completed result")
    first = selected[0]
    if first.get("stage") != "extraction":
        raise ValueError("First extraction attempt must be an extraction call")
    initial = validate_extraction(first.get("raw_response"), source)
    if asdict(initial) != result.get("first_pass_extraction"):
        raise ValueError("First-pass extraction differs from raw-response revalidation")
    try:
        if json.loads(first["messages"][-1]["content"]) != json.loads(extraction_messages(source)[-1]["content"]):
            raise ValueError("First extraction prompt differs from bound source")
        if len(selected) == 2:
            second = selected[1]
            if initial.ok:
                raise ValueError("Contract-valid extraction must not receive a repair retry")
            if second.get("stage") != "extraction_repair" or second.get("repair_of") != first["call_id"]:
                raise ValueError("Repair stage or original-call binding differs")
            actual = json.loads(second["messages"][-1]["content"])
            expected = json.loads(extraction_repair_messages(source, first.get("raw_response"), initial.errors)[-1]["content"])
            if actual != expected:
                raise ValueError("Repair prompt differs from source, original raw response or validation errors")
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Malformed saved extraction/repair prompt") from exc
    raw = parsed_model(first.get("raw_response"))
    statuses = expectation["expected_status"]
    statuses = [statuses] if isinstance(statuses, str) else statuses
    expected_explicit = expectation["expected_explicit_feature"]
    match = (initial.ok and bool(kinds(raw)) and set(kinds(raw)).issubset(expectation["accepted_kinds"])
             and (expected_explicit is None or explicit_feature(raw) == expected_explicit)
             and raw.get("status") in statuses)
    return {"source_id": source["id"], "attempt_call_ids": attempts,
        "first_pass_valid_contract": initial.ok, "first_pass_contract_errors": initial.errors,
        "first_pass_parseable": bool(raw), "first_pass_model_kinds": kinds(raw),
        "first_pass_model_status": raw.get("status"),
        "first_pass_matched_preliminary_expectation": match, "repair_requested": len(selected) == 2}


def evaluate(run_path, inputs_path, expectations_path):
    """Pure post-run read and deterministic comparisons; write nothing here."""
    run_path, inputs_path, expectations_path = map(Path, (run_path, inputs_path, expectations_path))
    manifest = load(run_path / "manifest.json")
    version = manifest.get("contract_version")
    if version not in {None, *V2_CONTRACTS}:
        raise ValueError(f"Unsupported saved contract version: {version}")
    v2 = version in V2_CONTRACTS
    repair_version = version in REPAIR_CONTRACTS
    chunked_version = version == CHUNKED_CONTRACT
    if repair_version and manifest.get("extraction_repair_limit") != 1:
        raise ValueError("Repair contract requires an explicit limit of one")
    if v2:
        from agent.pipeline import validate_extraction, validate_matching
    else:
        from agent.pipeline_v1 import validate_extraction, validate_matching
    if manifest.get("status") not in {"complete", "failed"}:
        raise ValueError("Only a finished or failed saved run may be evaluated")
    if manifest.get("inputs_sha256") != sha(inputs_path):
        raise ValueError("Input SHA-256 differs from the saved run")
    frozen = manifest.get("pre_run_artifact_sha256", {}).get(expectations_path.name)
    if not frozen or frozen != sha(expectations_path):
        raise ValueError("Missing or different pre-run expectation SHA-256")
    for filename in ("calls.jsonl", "results.jsonl"):
        if manifest.get("output_sha256", {}).get(filename) != sha(run_path / filename):
            raise ValueError(f"Saved output SHA-256 differs: {filename}")
    # Prompt revisions are retained verbatim in calls.jsonl and may differ across
    # experiments. Revalidation must use the same deterministic validator code.
    name = "pipeline.py"
    recorded = manifest.get("code_sha256", {}).get("agent/" + name,
        manifest.get("code_sha256", {}).get(name))
    # Historical source is preserved byte-for-byte in pipeline_v1.py. Its
    # original manifest still names pipeline.py; never rewrite that evidence.
    local_name = name if v2 else "pipeline_v1.py"
    if recorded and recorded != sha(ROOT / "agent" / local_name):
        raise ValueError(f"Validator source changed after run: {name}")
    if v2:
        for name in ("pipeline.py", "spans.py", "verifier_v2.py"):
            if manifest.get("code_sha256", {}).get("agent/" + name) != sha(ROOT / "agent" / name):
                raise ValueError(f"Missing or changed v2 validator source after run: {name}")
        if repair_version and manifest.get("code_sha256", {}).get("agent/repair.py") != sha(ROOT / "agent" / "repair.py"):
            raise ValueError("Missing or changed repair source after run: repair.py")
        if chunked_version and manifest.get("code_sha256", {}).get("agent/registry.py") != sha(ROOT / "agent" / "registry.py"):
            raise ValueError("Missing or changed registry source after run: registry.py")
        if chunked_version and manifest.get("code_sha256", {}).get("agent/source_risks.py") != sha(ROOT / "agent" / "source_risks.py"):
            raise ValueError("Missing or changed source-risk guard after run: source_risks.py")
        for filename, digest in manifest.get("output_sha256", {}).items():
            if Path(filename).name != filename or sha(run_path / filename) != digest:
                raise ValueError(f"Saved output SHA-256 differs: {filename}")

    sources = lines(inputs_path)
    source_map = indexed(sources, "id", "inputs")
    expectations = load(expectations_path)
    if expectations.get("author") != "AI reviewer, not human gold" or expectations.get("tentative") is not True:
        raise ValueError("Expected explicitly tentative AI labels")
    expected = indexed(expectations.get("cases", []), "id", "expectations")
    if set(expected) != set(source_map):
        raise ValueError("Input and expectation ID sets differ")
    if manifest.get("source_count") != len(sources):
        raise ValueError("Manifest source count differs")
    calls = indexed(lines(run_path / "calls.jsonl"), "call_id", "calls")
    results = indexed(lines(run_path / "results.jsonl"), "source_id", "results")
    if set(results) - set(source_map):
        raise ValueError("Result contains a source absent from inputs")
    if manifest["status"] == "complete" and set(results) != set(source_map):
        raise ValueError("A complete run must contain every source result")
    if manifest.get("call_count") != len(calls):
        raise ValueError("Manifest call count differs")
    allowed_stages = {"extraction", "matching", "verification"}
    if repair_version:
        allowed_stages.add("extraction_repair")
    for call in calls.values():
        if call.get("source_id") not in source_map or call.get("stage") not in allowed_stages:
            raise ValueError("Unknown source or stage in saved call")
        if v2 and manifest["status"] == "complete" and call.get("status") != "complete":
            raise ValueError("Complete run contains a failed or non-complete model call")
    audit_structured_completion(manifest, calls)

    details, raw_by_id, validated, referenced = [], {}, {}, set()
    attempt_details, attempt_references = [], set()
    for source in sources:
        identifier, exp = source["id"], expected[source["id"]]
        result = results.get(identifier)
        if result is None:
            details.append({"id": identifier, "origin": source["origin"], "processed": False,
                "valid_contract": False, "model_status": "not_processed", "model_kinds": [],
                "matched_preliminary_expectation": False, "disagreements": ["not processed"]})
            continue
        call = calls.get(result.get("extraction_call"))
        if repair_version:
            attempt = evaluate_extraction_attempts(source, result, calls, validate_extraction, exp)
            if attempt_references.intersection(attempt["attempt_call_ids"]):
                raise ValueError("Extraction attempt reused by multiple results")
            attempt_references.update(attempt["attempt_call_ids"])
            attempt_details.append(attempt)
        valid_stages = {"extraction", "extraction_repair"} if repair_version else {"extraction"}
        if not call or call["source_id"] != identifier or call["stage"] not in valid_stages:
            raise ValueError(f"Extraction call/source mismatch: {identifier}")
        if v2 and call.get("status") != "complete":
            raise ValueError("Failed extraction call cannot supply a completed result")
        if call["call_id"] in referenced:
            raise ValueError("Extraction call reused by multiple results")
        referenced.add(call["call_id"])
        raw = parsed_model(call.get("raw_response"))
        raw_by_id[identifier] = raw
        valid = validate_extraction(call.get("raw_response"), source)
        if asdict(valid) != result.get("extraction"):
            raise ValueError(f"Saved extraction differs from raw-response revalidation: {identifier}")
        validated[identifier] = valid
        actual_kinds = kinds(raw)
        status = raw.get("status")
        status = status if isinstance(status, str) else "unparseable_or_missing"
        accepted_status = exp["expected_status"]
        accepted_status = [accepted_status] if isinstance(accepted_status, str) else accepted_status
        kind_match = bool(actual_kinds) and set(actual_kinds).issubset(set(exp["accepted_kinds"]))
        explicit = explicit_feature(raw)
        expected_explicit = exp["expected_explicit_feature"]
        explicit_match = expected_explicit is None or explicit == expected_explicit
        status_match = status in accepted_status
        disagreements = []
        if not valid.ok:
            disagreements.append("invalid extraction contract")
        if not kind_match:
            disagreements.append("kinds outside accepted set or no intents")
        if not explicit_match:
            disagreements.append("explicit feature flag differs")
        if not status_match:
            disagreements.append("status differs")
        details.append({"id": identifier, "origin": source["origin"], "processed": True,
            "valid_contract": valid.ok, "contract_errors": valid.errors,
            "model_status": status, "model_kinds": actual_kinds,
            "model_explicit_feature": explicit, "expected_explicit_feature": expected_explicit,
            "explicit_feature_comparison": "not_scored_ambiguous" if expected_explicit is None else explicit_match,
            "accepted_kinds": exp["accepted_kinds"], "accepted_status": accepted_status,
            "matched_preliminary_expectation": valid.ok and kind_match and explicit_match and status_match,
            "disagreements": disagreements})

    if repair_version:
        extraction_calls = {identifier for identifier, call in calls.items()
                            if call["stage"] in {"extraction", "extraction_repair"}}
        if manifest["status"] == "complete" and extraction_calls != attempt_references:
            raise ValueError("Extraction/repair calls are not all linked to results")
        for attempt in attempt_details:
            final = validated[attempt["source_id"]]
            attempt["final_valid_contract"] = final.ok
            attempt["final_contract_errors"] = final.errors
        attempt_counts = {
            "first_pass_valid_extractions": sum(a["first_pass_valid_contract"] for a in attempt_details),
            "extraction_repair_calls": sum(a["repair_requested"] for a in attempt_details),
            "repaired_valid_extractions": sum(a["repair_requested"] and a["final_valid_contract"] for a in attempt_details)}
        if manifest["status"] == "complete" and any(manifest.get(k) != v for k, v in attempt_counts.items()):
            raise ValueError("Manifest extraction-attempt counts differ")
        if manifest["status"] == "complete" and manifest.get("valid_extractions") != sum(
                a["final_valid_contract"] for a in attempt_details):
            raise ValueError("Manifest final extraction count differs")

    matching = []
    for call in calls.values():
        if call["stage"] != "matching":
            continue
        if v2 and call.get("status") != "complete":
            matching.append({"call_id": call["call_id"], "source_id": call["source_id"],
                "valid_contract": False, "errors": ["Failed call: partial raw response is not a completed matching judgment"]})
            continue
        try:
            payload = json.loads(call["messages"][-1]["content"])
            candidates = payload["candidates"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError("Malformed saved matching prompt") from exc
        valid = validate_matching(call.get("raw_response"), candidates)
        matching.append({"call_id": call["call_id"], "source_id": call["source_id"],
                         "valid_contract": valid.ok, "errors": valid.errors})

    verification = evaluate_verification(calls, results, source_map, validated, manifest)
    registry_audit = None
    if chunked_version:
        from scripts.audit_registry import audit_registry
        registry_audit = audit_registry(calls, results, source_map, validated, manifest, run_path)

    summary = {}
    for label, origin in (("all", None), ("case_pdf", "case_pdf"), ("synthetic", "synthetic")):
        group = [d for d in details if origin is None or d["origin"] == origin]
        summary[label] = {"sources": len(group), "processed": sum(d["processed"] for d in group),
            "valid_extraction_contracts": sum(d["valid_contract"] for d in group),
            "matched_preliminary_expectations": sum(d["matched_preliminary_expectation"] for d in group),
            "model_statuses": dict(sorted(Counter(d["model_status"] for d in group).items())),
            "model_kind_presence": dict(sorted(Counter(k for d in group for k in d["model_kinds"]).items()))}

    focused = []
    s7 = validated.get("syn-07")
    two = s7 is not None and s7.ok and {"incident", "feature_request"}.issubset(kinds(s7.value))
    focused.append(check("syn07_two_separate_intents", two,
                         "Separate incident and feature_request intents must both survive the contract.", "syn-07" in source_map))
    order_sources = ["syn-01", "syn-02", "syn-03", "syn-04"]
    order_sets = [topic_ids(results.get(i, {})) for i in order_sources]
    same = all(len(t) == 1 for t in order_sets) and len(set.union(*order_sets)) == 1
    order_topic = next(iter(order_sets[0])) if same else None
    snapshot = next((c for c in results.get("syn-04", {}).get("cards_after_source", [])
                     if c.get("topic_id") == order_topic), None)
    counts = {k: snapshot.get(k) for k in ("raw_sources", "independent_episodes", "known_customers")} if snapshot else None
    focused.append(check("syn01_04_one_topic_and_deduplicated_snapshot",
        same and counts == {"raw_sources": 4, "independent_episodes": 3, "known_customers": 2},
        {"topic_ids_by_source": dict(zip(order_sources, [sorted(s) for s in order_sets])), "snapshot": counts},
        all(i in source_map for i in order_sources)))
    invoice = topic_ids(results.get("syn-10", {}))
    focused.append(check("syn10_invoices_separate_from_orders", same and len(invoice) == 1 and order_topic not in invoice,
        {"orders_topic": order_topic, "invoice_topics": sorted(invoice)}, "syn-10" in source_map and all(i in source_map for i in order_sources)))

    authorship_violations, invention_violations, unavailable = [], [], []
    for source in sources:
        identifier = source["id"]
        raw = raw_by_id.get(identifier)
        if raw is None:
            unavailable.append(identifier)
            continue
        if source["speaker"] != "user" and any(i.get("origin") == "user_explicit" for i in model_intents(raw)):
            authorship_violations.append(identifier)
        if source["speaker"] == "unknown" and raw.get("status") != "needs_review":
            authorship_violations.append(identifier)
        for intent in model_intents(raw):
            refs = intent.get("evidence_refs", [])
            if isinstance(refs, list) and any(not isinstance(r, dict) or
                    (r.get("id") != identifier and not (v2 and set(r) == {"span_id"})) for r in refs):
                invention_violations.append(identifier)
        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {"customer_id", "episode_id", "episode_at"} and child != source.get(key):
                        invention_violations.append(identifier)
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(raw)
    focused.append(check("trusted_authorship_respected_by_raw_model", not authorship_violations and not unavailable,
        {"violating_sources": sorted(set(authorship_violations)), "unprocessed_sources": unavailable}))
    focused.append(check("no_invented_source_or_identity_fields_in_raw_extraction", not invention_violations and not unavailable,
        {"violating_sources": sorted(set(invention_violations)), "unprocessed_sources": unavailable,
         "scope": "Checks structured IDs only; statements need manual review for invented counts or facts."}))

    # Reconcile every saved snapshot against trusted source identity/time fields.
    active, count_errors = {}, []
    as_of = datetime.fromisoformat(manifest["as_of"].replace("Z", "+00:00"))
    for source in sources:
        identifier, result = source["id"], results.get(source["id"])
        if result is None:
            continue
        valid = validated[identifier]
        if valid.ok and valid.value["status"] == "ok" and source.get("episode_at"):
            at = datetime.fromisoformat(source["episode_at"].replace("Z", "+00:00"))
            if as_of - timedelta(days=30) < at <= as_of:
                for topic in topic_ids(result):
                    active.setdefault(topic, {})[identifier] = source
        for card in result.get("cards_after_source", []):
            evidence_sources = list(active.get(card["topic_id"], {}).values())
            expected_counts = {
                "raw_sources": len(evidence_sources),
                "independent_episodes": len({(s["product_id"], s["episode_id"]) for s in evidence_sources if s.get("episode_id")}),
                "known_customers": len({s["customer_id"] for s in evidence_sources if s.get("customer_id") and s.get("episode_id")})}
            actual_counts = {k: card.get(k) for k in expected_counts}
            if actual_counts != expected_counts:
                count_errors.append({"after_source": identifier, "topic_id": card["topic_id"],
                                     "expected": expected_counts, "actual": actual_counts})
    focused.append(check("snapshot_counts_use_only_trusted_known_identities", not count_errors and not unavailable,
                         {"count_mismatches": count_errors, "unprocessed_sources": unavailable}))
    report = {"evaluation_type": "post_run_preliminary_ai_comparison", "disclaimer": DISCLAIMER,
        "run_status": manifest["status"], "model": manifest.get("model"),
        "verified_sha256": {"inputs": sha(inputs_path), "expectations_pre_run": frozen,
            "manifest": sha(run_path / "manifest.json"), "calls": sha(run_path / "calls.jsonl"),
            "results": sha(run_path / "results.jsonl")},
        "summary": summary, "matching_contracts": {"calls": len(matching),
            "valid": sum(m["valid_contract"] for m in matching), "details": matching},
        "focused_checks": focused, "cases": details,
        "disagreements": [d for d in details if not d["matched_preliminary_expectation"]]}
    if verification is not None:
        report["verification_contracts"] = verification
    if registry_audit is not None:
        report["registry_comparison"] = registry_audit
    if repair_version:
        report["extraction_attempts"] = {
            "disclaimer": "At most one model retry after a mechanical validator rejection. Original raw responses are retained. Contract-valid semantic mistakes are never retried automatically; a retry may still change meaning and needs semantic review.",
            **attempt_counts,
            "first_pass_matched_preliminary_expectations": sum(a["first_pass_matched_preliminary_expectation"] for a in attempt_details),
            "final_valid_extractions": sum(a["final_valid_contract"] for a in attempt_details),
            "final_matched_preliminary_expectations": summary["all"]["matched_preliminary_expectations"],
            "details": attempt_details}
    if v2:
        from scripts.evaluate_semantics import evaluate_semantics
        report["contract_version"] = version
        report["provisional_semantics"] = evaluate_semantics(
            run_path, source_map, expected, expectations.get("themes"), results, validated, manifest)
    return report


def markdown(report):
    out = ["# Saved-run comparison", "", report["disclaimer"], "", f"Run status: `{report['run_status']}`.", "",
           "| Material | Sources | Processed | Valid extraction contracts | Matches to preliminary AI expectations |",
           "|---|---:|---:|---:|---:|"]
    for label, s in report["summary"].items():
        out.append(f"| {label} | {s['sources']} | {s['processed']} | {s['valid_extraction_contracts']} | {s['matched_preliminary_expectations']} |")
    if "extraction_attempts" in report:
        attempts = report["extraction_attempts"]
        out += ["", "## Первая попытка и повтор после ошибки контракта", "",
            "Модель получает одну повторную попытку только после ошибки программной проверки. Семантически неверный ответ с правильным форматом автоматически не переписывается. Обе версии ответа сохранены.", "",
            f"- Формат с первой попытки: {attempts['first_pass_valid_extractions']}; после повторов: {attempts['final_valid_extractions']}.",
            f"- Повторных запросов: {attempts['extraction_repair_calls']}; из них дали допустимый формат: {attempts['repaired_valid_extractions']}.",
            f"- Совпадений с предварительными ожиданиями по классу и статусу: сначала {attempts['first_pass_matched_preliminary_expectations']}, в конце {attempts['final_matched_preliminary_expectations']}.",
            "", "Улучшение формата не равно улучшению понимания. При повторе модель может изменить и смысл; исходный ответ остаётся доступным для сравнения."]
    if "registry_comparison" in report:
        registry = report["registry_comparison"]
        out += ["", "## Полнота сравнения с существующими темами", "",
            f"Для каждого продукта проверяются все темы в пределах бюджета {registry['candidate_limit']}, группами не более {registry['batch_size']}. Частичный просмотр не позволяет создать новую тему.",
            f"- Вызовов сопоставления: {registry['matching_calls']}; сравнений с реестром больше пяти тем: {registry['comparisons_beyond_first_five']}.",
            f"- Решений вне автоматического бюджета: {registry['dispositions_over_budget']}; они требуют разбора.",
            "", "Полнота просмотра и повторение программного решения не доказывают, что модель правильно понимает сходство тем."]
        guard = registry["source_risk_guard"]
        out += ["", f"Явные инструкции обработчику или признаки запроса выдумать доказательства: {guard['flagged_sources']} обращений направлено на разбор и исключено из автоматического учёта.",
            "Это ограниченный набор текстовых правил, а не полная защита от инструкций внутри данных. Возможны пропуски и ложные срабатывания, например при цитировании нормального текста."]
    if "provisional_semantics" in report:
        semantic = report["provisional_semantics"]
        s = semantic["summary"]
        out += ["", "## Что показывает этот запуск", "",
            "Проверка формата и цитат отделена от сравнения смысла. Метки составлены ИИ и требуют независимой проверки людьми; это не оценка точности на рабочих данных.", "",
            "| Проверка | Результат |", "|---|---:|",
            f"| Обращений; формат и ссылки на цитаты приняты | {s['sources']}; {s['valid_extraction_contracts']} |",
            f"| Обращений в очереди ручного разбора | {s['review_queue_sources']} |",
            f"| Карточек передано в локальную очередь | {s['delivered_local_cards']} |",
            f"| Из них согласуются с предварительными метками | {s['delivered_cards_supported_by_provisional_labels']} |",
            f"| Из них противоречат предварительным меткам | {s['delivered_cards_contradicting_provisional_labels']} |",
            f"| Из них пока нельзя оценить | {s['delivered_cards_unscored']} |",
            f"| Ожидалось повторяющихся тем; пропущены или не подтверждены | {s['expected_recurring_themes']}; {s['recurring_themes_missed_or_unconfirmed']} |", "",
            "Отсутствие отправленных карточек не считается успехом: агент может пропустить все настоящие пожелания. Совпадение цитаты и класса также не проверяет точность пересказа модели.", "",
            f"Подробные метки намерений доступны для {s['sources_with_intent_labels']} из {s['sources']} обращений. Совпали по цитате и классу {s['expected_intents_evidence_and_class_matched']} из {s['expected_intents']} размеченных намерений. Не имеющие такой разметки примеры не включаются в этот показатель.", "",
            "[Все обращения и ответы](report.html) · [Полный машинный отчёт](evaluation.json) · [Исходные ответы модели](calls.jsonl) · [Очередь разбора](review-queue.json)", ""]
        for card in semantic["cards"]:
            out.append(f"- Карточка `{card['actual_topic_id']}`: {card['assessment']}; доставлена: {card['delivered']}; тема по меткам: `{card['provisional_theme_id']}`.")
        for theme in semantic["themes"]:
            if theme["missed_or_unconfirmed"]:
                out.append(f"- Пропущена или не подтверждена повторяющаяся тема `{theme['topic_id']}`: {theme['independent_episodes']} эпизодов, {theme['known_customers']} клиентов.")
    out += ["", "Model statuses and classes:", ""]
    for label, s in report["summary"].items():
        out.append(f"- {label}: statuses `{json.dumps(s['model_statuses'], ensure_ascii=False)}`; class presence `{json.dumps(s['model_kind_presence'], ensure_ascii=False)}`.")
    if "verification_contracts" in report:
        verification = report["verification_contracts"]
        out += ["", "Model verification (separate from extraction expectations):", "",
                verification["disclaimer"], "",
                f"- Calls: {verification['calls']}; valid contracts: {verification['valid_contracts']}; verdicts: `{json.dumps(verification['verdicts'])}`.",
                f"- Blocking violations: {verification['blocking_violations']}."]
        for item in verification["details"]:
            out.append(f"- `{item['source_id']}` / `{item['intent_id']}`: {item['verdict']}; blocking respected: {item['blocking_respected']}.")
    out += ["", "Focused checks:", ""]
    for c in report["focused_checks"]:
        result = "not applicable" if not c["applicable"] else ("met" if c["passed"] else "not met")
        out.append(f"- `{c['name']}`: **{result}**. {json.dumps(c['details'], ensure_ascii=False)}")
    out += ["", "Disagreements with preliminary expectations:", ""]
    if not report["disagreements"]:
        out.append("None in this small constructed set. This does not establish real-world quality.")
    for d in report["disagreements"]:
        out.append(f"- `{d['id']}` ({d['origin']}): status `{d['model_status']}`, classes `{', '.join(d['model_kinds']) or '(none)'}`; {'; '.join(d['disagreements'])}.")
        if d.get("contract_errors"):
            out.append("  Contract: " + "; ".join(d["contract_errors"]))
    out += ["", "Review the saved raw calls and citations for semantic mistakes. Exact quote matching does not prove the interpretation.", ""]
    return "\n".join(out)


def write_evaluation(run_path, inputs_path, expectations_path):
    run_path = Path(run_path)
    targets = [run_path / "evaluation.json", run_path / "evaluation.md"]
    if any(p.exists() for p in targets):
        raise FileExistsError("Evaluation files already exist; refusing to overwrite saved evidence")
    report = evaluate(run_path, inputs_path, expectations_path)
    # Exclusive create also protects against a concurrent evaluator.
    created = []
    try:
        for path, text in zip(targets, (json.dumps(report, ensure_ascii=False, indent=2) + "\n", markdown(report))):
            with path.open("x", encoding="utf-8") as handle:
                created.append(path)
                handle.write(text)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--expectations", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = write_evaluation(args.run, args.inputs, args.expectations)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Evaluation refused: {exc}\n")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
