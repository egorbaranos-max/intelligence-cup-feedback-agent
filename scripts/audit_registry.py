"""Replay complete-registry matching from saved evidence, without model calls.

Each model judgment is checked against its exact input intent and candidate
batch. Reproducing a judgment is not proof that its semantic relation is right.
"""
from dataclasses import asdict
import json
from pathlib import Path

from agent.pipeline import matching_messages, validate_matching
from agent.registry import candidate_plan, resolve_registry_topic


def audit_registry(calls, results, sources, validated, manifest, run_path):
    from agent.source_risks import detect_source_risks
    if manifest.get("registry_candidate_limit") != 25 or manifest.get("registry_batch_size") != 5:
        raise ValueError("Chunked registry contract requires limits of 25 total and 5 per batch")
    run_path = Path(run_path)
    source_audit = {row["source_id"]: row for row in json.loads((run_path / "source-audit.json").read_text())}
    review_queue = {row["source_id"]: row for row in json.loads((run_path / "review-queue.json").read_text())}
    topics, details, seen_calls, risk_details = [], [], set(), []
    for source_id, source in sources.items():
        result = results.get(source_id)
        if result is None:
            continue
        risks = detect_source_risks(source["text"])
        if result.get("source_risks") != risks or source_audit.get(source_id, {}).get("source_risks") != risks:
            raise ValueError("Saved source risks differ from deterministic source check")
        if source_id in review_queue and review_queue[source_id].get("source_risks") != risks:
            raise ValueError("Review queue source risks differ")
        if risks:
            if (not result.get("review_required") or source_id not in review_queue
                    or "source_risk_guard" not in result.get("review_reasons", [])
                    or result.get("counting") != "held for review: explicit processor-control or fabricated-evidence risk"):
                raise ValueError("Flagged source is not explicitly held for human review")
            if any(call.get("source_id") == source_id and call.get("stage") in {"verification", "matching"} for call in calls.values()):
                raise ValueError("Flagged source must not invoke verification or matching")
        risk_details.append({"source_id": source_id, "flagged": bool(risks), "risks": risks})
        extraction = validated[source_id]
        assignments = result.get("assignments", [])
        if not extraction.ok:
            if assignments:
                raise ValueError("Invalid extraction cannot contain registry assignments")
            continue
        intents = extraction.value["intents"]
        if len(assignments) != len(intents):
            raise ValueError("Every validated intent needs exactly one registry disposition")
        for intent, assignment in zip(intents, assignments):
            if assignment.get("intent_id") != intent["intent_id"]:
                raise ValueError("Registry disposition order or intent binding differs")
            if assignment.get("matching_call") is not None or assignment.get("matching") is not None:
                raise ValueError("Chunked matching must use explicit batch records")
            plan = candidate_plan(intent, source, topics)
            required = {"candidate_ids": plan["candidate_ids"], "candidate_pool_size": plan["candidate_pool_size"],
                        "registry_complete": plan["complete"], "registry_error": plan["error"]}
            if any(assignment.get(k) != v for k, v in required.items()):
                raise ValueError("Saved candidate plan differs from replayed complete registry")
            batches, matching_calls = assignment.get("matching_batches"), assignment.get("matching_calls")
            if not isinstance(batches, list) or not isinstance(matching_calls, list):
                raise ValueError("Explicit matching batch and call lists required")
            if matching_calls != [batch.get("call_id") for batch in batches] or len(set(matching_calls)) != len(matching_calls):
                raise ValueError("Matching call list differs from unique batch calls")
            eligible = (not intent["review_required"] and intent["origin"] == "user_explicit"
                        and intent["kind"] == "feature_request")
            verification = assignment.get("verification") or {}
            gate_open = (not risks and eligible and verification.get("ok") is True
                         and (verification.get("value") or {}).get("verdict") == "supported")
            should_compare = gate_open and plan["complete"]
            expected_batches = plan["batches"] if should_compare else []
            if len(batches) != len(expected_batches):
                raise ValueError("Matching does not cover every planned batch, or ran behind a closed gate")
            checked = []
            for saved, candidates in zip(batches, expected_batches):
                call_id = saved.get("call_id")
                if type(call_id) is not int or call_id in seen_calls:
                    raise ValueError("Invalid or reused registry matching call")
                seen_calls.add(call_id)
                call = calls.get(call_id)
                if not call or call.get("stage") != "matching" or call.get("source_id") != source_id or call.get("intent_id") != intent["intent_id"]:
                    raise ValueError("Matching call source or intent binding differs")
                if saved.get("candidate_ids") != [candidate["id"] for candidate in candidates]:
                    raise ValueError("Matching batch has missing, duplicate or substituted candidates")
                try:
                    actual_payload = json.loads(call["messages"][-1]["content"])
                    expected_payload = json.loads(matching_messages(intent, candidates)[-1]["content"])
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    raise ValueError("Malformed saved registry matching prompt") from exc
                if actual_payload != expected_payload:
                    raise ValueError("Matching prompt differs from bound intent and complete candidate batch")
                validation = validate_matching(call.get("raw_response"), candidates)
                if asdict(validation) != saved.get("matching"):
                    raise ValueError("Saved batch validation differs from raw response")
                checked.append(validation)
            if assignment.get("registry_compared") != (should_compare and len(checked) == len(plan["batches"])):
                raise ValueError("Saved registry coverage flag differs")
            if risks:
                expected_decision = {"status": "needs_review", "topic_id": None}
                if assignment.get("verification_call") is not None or assignment.get("verification") is not None:
                    raise ValueError("Flagged source cannot have model verification attached")
            elif intent["kind"] == "usability":
                expected_decision = {"status": "needs_review", "topic_id": None}
            elif eligible and not gate_open:
                expected_decision = {"status": "needs_review", "topic_id": None}
            else:
                expected_decision = resolve_registry_topic(intent, source, plan, checked)
            if any(assignment.get(k) != expected_decision[k] for k in ("status", "topic_id")):
                raise ValueError("Registry assignment differs from complete-batch decision replay")
            if assignment["status"] == "new":
                topic = {"id": assignment["topic_id"], "product_id": source["product_id"], "statement": intent["statement"]}
                if any(old["id"] == topic["id"] for old in topics):
                    raise ValueError("New topic duplicates existing registry ID")
                topics.append(topic)
            details.append({"source_id": source_id, "intent_id": intent["intent_id"],
                "candidate_pool_size": plan["candidate_pool_size"], "candidate_ids": plan["candidate_ids"],
                "within_budget": plan["complete"], "registry_compared": assignment["registry_compared"],
                "matching_call_ids": matching_calls, "valid_batch_contracts": sum(item.ok for item in checked),
                "status": assignment["status"], "topic_id": assignment["topic_id"]})
    all_matching = {identifier for identifier, call in calls.items() if call.get("stage") == "matching"}
    if manifest["status"] == "complete" and seen_calls != all_matching:
        raise ValueError("Registry matching calls are not all linked exactly once")
    if manifest["status"] == "complete" and manifest.get("source_risk_flagged_sources") != sum(r["flagged"] for r in risk_details):
        raise ValueError("Manifest flagged-source count differs")
    return {"disclaimer": "Complete bounded candidate coverage and decision replay only. Model relation judgments can still be semantically wrong; exceeding 25 candidates routes to review.",
        "candidate_limit": 25, "batch_size": 5, "matching_calls": len(seen_calls),
        "registry_topics": len(topics),
        "dispositions_over_budget": sum(not d["within_budget"] for d in details),
        "comparisons_beyond_first_five": sum(d["registry_compared"] and d["candidate_pool_size"] > 5 for d in details),
        "source_risk_guard": {"disclaimer": "Conservative explicit-pattern routing only, not complete prompt-injection protection. Legitimate quoted text may cause false positives; human review is required.",
            "flagged_sources": sum(r["flagged"] for r in risk_details), "details": risk_details},
        "details": details}
