"""Bounded complete-registry comparison using the immutable five-candidate contract.

This is deliberately a small-batch prototype. Above the explicit total budget,
no automatic match or novelty decision is made. Production search needs a
separate recall evaluation; truncating a shortlist cannot prove novelty.
"""
from __future__ import annotations

import json
import re

from .pipeline import ValidationResult, _candidate_errors, resolve_topic, validate_matching

MAX_REGISTRY_CANDIDATES = 25
BATCH_SIZE = 5


def candidate_plan(intent, source, topics, max_candidates=MAX_REGISTRY_CANDIDATES):
    """Deterministic product-scoped ordering and complete batches, or abstention."""
    if type(max_candidates) is not int or not 1 <= max_candidates <= MAX_REGISTRY_CANDIDATES:
        raise ValueError("Candidate budget must be between 1 and 25")
    if not isinstance(topics, list) or any(not isinstance(t, dict) for t in topics):
        return {"candidate_ids": [], "candidate_pool_size": 0, "complete": False,
                "error": "Invalid candidate registry", "batches": []}
    registry_ids = [t.get("id") for t in topics]
    if (any(not isinstance(identifier, str) or not identifier for identifier in registry_ids)
            or len(set(registry_ids)) != len(registry_ids)
            or any(not isinstance(t.get("product_id"), str) for t in topics)):
        return {"candidate_ids": [], "candidate_pool_size": 0, "complete": False,
                "error": "Invalid or duplicate candidate identity", "batches": []}
    scope = [t for t in topics if t["product_id"] == source["product_id"]]
    # Validate each bounded chunk before using statements in lexical ranking.
    for offset in range(0, len(scope), BATCH_SIZE):
        if _candidate_errors(scope[offset:offset + BATCH_SIZE]):
            return {"candidate_ids": [t["id"] for t in scope], "candidate_pool_size": len(scope),
                    "complete": False, "error": "Invalid candidate fields", "batches": []}
    words = set(re.findall(r"\w+", intent["statement"].lower()))
    ranked = sorted(scope, key=lambda t: (-len(words & set(re.findall(r"\w+", t["statement"].lower()))), t["id"]))
    candidates = [{k: t[k] for k in ("id", "product_id", "statement")} for t in ranked]
    complete = len(candidates) <= max_candidates
    return {"candidate_ids": [t["id"] for t in candidates], "candidate_pool_size": len(candidates),
            "complete": complete,
            "error": None if complete else f"Registry exceeds {max_candidates}-candidate automatic comparison budget",
            "batches": [candidates[i:i + BATCH_SIZE] for i in range(0, len(candidates), BATCH_SIZE)] if complete else []}


def resolve_registry_topic(intent, source, plan, matches):
    """Require complete, unique, product-bound coverage before any auto decision."""
    def review(reason):
        return {"status": "needs_review", "topic_id": None, "reason": reason}
    initial = resolve_topic(intent, source, [], None)
    if initial["status"] != "new":
        return initial
    if not isinstance(plan, dict) or plan.get("complete") is not True or plan.get("error") is not None:
        return review("Complete registry comparison unavailable; manual review required")
    ids, batches = plan.get("candidate_ids"), plan.get("batches")
    if (not isinstance(ids, list) or any(not isinstance(i, str) or not i for i in ids)
            or len(set(ids)) != len(ids) or len(ids) > MAX_REGISTRY_CANDIDATES
            or type(plan.get("candidate_pool_size")) is not int or plan["candidate_pool_size"] != len(ids)
            or not isinstance(batches, list) or not isinstance(matches, list) or len(matches) != len(batches)):
        return review("Invalid registry comparison plan or incomplete batch results")
    covered, decisions = [], []
    for batch, result in zip(batches, matches):
        if not isinstance(batch, list) or not batch or _candidate_errors(batch):
            return review("Invalid candidate batch")
        if any(c["product_id"] != source["product_id"] for c in batch):
            return review("Candidate batch outside product scope")
        covered.extend(c["id"] for c in batch)
        if not isinstance(result, ValidationResult) or not result.ok:
            return review("At least one candidate batch is invalid; no automatic assignment")
        # Bind saved results again to these exact IDs before combining decisions.
        checked = validate_matching(json.dumps(result.value, ensure_ascii=False), batch)
        decision = resolve_topic(intent, source, batch, checked)
        if decision["status"] == "needs_review":
            return review("At least one candidate batch is unclear or invalid; no automatic assignment")
        decisions.append(decision)
    if covered != ids:
        return review("Candidate batches do not cover the complete registry exactly once")
    matched = [d["topic_id"] for d in decisions if d["status"] == "matched"]
    if len(matched) > 1:
        return review("Multiple same candidates across registry batches require review")
    if matched:
        return {"status": "matched", "topic_id": matched[0],
                "reason": "One same relation after complete registry comparison"}
    return {**initial, "reason": "No same or unclear relation after complete registry comparison"}
