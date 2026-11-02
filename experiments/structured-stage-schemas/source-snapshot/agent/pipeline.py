"""Strict text-pipeline contracts, separate from model inference and scoring.

This is an experimental adaptation, not the deployed multimodal case system.
Exact evidence validation proves that a quote exists, not that the model has
understood it. Negation, invented causality and semantic classification require
independent evaluation against human labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Any

from .prompts import EXTRACTION_SYSTEM, MATCHING_SYSTEM
from .spans import model_spans, source_spans

KINDS = {"incident", "service_request", "feature_request", "usability", "unknown"}
ORIGINS = {"user_explicit", "observed_pain", "hypothesis"}
RELATIONS = {"same", "related", "different", "unclear"}
MAX_RESPONSE_CHARS = 100_000


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    value: dict[str, Any] | None
    errors: list[str]


def _nonempty(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _keys(value: Any, expected: set[str], location: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{location}: expected object")
        return False
    if set(value) != expected:
        errors.append(f"{location}: unexpected or missing fields")
        return False
    return True


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"Non-JSON constant: {value}")


def _decode(raw: str) -> ValidationResult:
    if not isinstance(raw, str) or not raw.strip():
        return ValidationResult(False, None, ["response: nonempty JSON text required"])
    if len(raw) > MAX_RESPONSE_CHARS:
        return ValidationResult(False, None, ["response: size limit exceeded"])
    try:
        value = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
    except (ValueError, RecursionError) as exc:
        return ValidationResult(False, None, [f"response: invalid JSON ({exc})"])
    if not isinstance(value, dict):
        return ValidationResult(False, None, ["response: expected JSON object"])
    return ValidationResult(True, value, [])


def _source_errors(source: dict) -> list[str]:
    if not isinstance(source, dict):
        return ["source: expected object"]
    errors = []
    for name in ("id", "product_id", "text"):
        if not _nonempty(source.get(name)):
            errors.append(f"source.{name}: nonempty string required")
    if not isinstance(source.get("speaker"), str) or source["speaker"] not in {"user", "operator", "unknown"}:
        errors.append("source.speaker: trusted user/operator/unknown required")
    # Null identity/time is retained as unknown, never invented for recurrence.
    for name in ("customer_id", "episode_id"):
        if source.get(name) is not None and not _nonempty(source[name]):
            errors.append(f"source.{name}: nonempty string or null required")
    if source.get("episode_at") is not None:
        try:
            stamp = source["episode_at"]
            if not isinstance(stamp, str):
                raise ValueError("not text")
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
                raise ValueError("not UTC")
        except (ValueError, TypeError, OverflowError):
            errors.append("source.episode_at: UTC ISO timestamp or null required")
    context = source.get("product_context")
    if context is not None and not isinstance(context, str):
        errors.append("source.product_context: string or null required")
    elif context and not _nonempty(context):
        errors.append("source.product_context: valid Unicode text required")
    return errors


def extraction_messages(source: dict) -> list[dict[str, str]]:
    """Allowlist model inputs; never send gold labels or synthetic-origin flags."""
    errors = _source_errors(source)
    if errors:
        raise ValueError("; ".join(errors))
    payload = {
        "metadata": {"id": source["id"], "product_id": source["product_id"],
                     "speaker": source["speaker"]},
        "text": source["text"],
        "source_spans": model_spans(source["text"]),
    }
    if source.get("product_context"):
        payload["product_context"] = source["product_context"]
    return [{"role": "system", "content": EXTRACTION_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def validate_extraction(raw: str, source: dict) -> ValidationResult:
    """Reject invalid output atomically; never repair or relabel a model claim."""
    errors = _source_errors(source)
    if errors:
        return ValidationResult(False, None, errors)
    decoded = _decode(raw)
    if not decoded.ok:
        return decoded
    value = decoded.value
    if not _keys(value, {"status", "intents"}, "response", errors):
        return ValidationResult(False, None, errors)
    if not isinstance(value["status"], str) or value["status"] not in {"ok", "needs_review"}:
        errors.append("status: expected ok or needs_review")
    if source["speaker"] == "unknown" and value["status"] != "needs_review":
        errors.append("status: unknown author requires needs_review")
    if not isinstance(value["intents"], list):
        errors.append("intents: expected array")
        return ValidationResult(False, None, errors)
    if len(value["intents"]) > 30:
        return ValidationResult(False, None, errors + ["intents: at most 30 per source"])
    normalized, identifiers = [], set()
    spans_by_id = {span["span_id"]: span for span in source_spans(source["text"])}
    for index, intent in enumerate(value["intents"]):
        loc = f"intents[{index}]"
        if not _keys(intent, {"kind", "origin", "statement", "evidence_refs", "uncertainties"}, loc, errors):
            continue
        before = len(errors)
        if not isinstance(intent["kind"], str) or intent["kind"] not in KINDS:
            errors.append(f"{loc}.kind: invalid kind")
        if not isinstance(intent["origin"], str) or intent["origin"] not in ORIGINS:
            errors.append(f"{loc}.origin: invalid origin")
        if intent["origin"] == "user_explicit" and source["speaker"] != "user":
            errors.append(f"{loc}.origin: unverified user authorship; needs_review required")
        if not _nonempty(intent["statement"]):
            errors.append(f"{loc}.statement: nonempty text required")
        uncertainties = intent["uncertainties"]
        if not isinstance(uncertainties, list) or not all(_nonempty(u) for u in uncertainties):
            errors.append(f"{loc}.uncertainties: array of nonempty strings required")
        elif uncertainties and value["status"] != "needs_review":
            errors.append(f"{loc}.uncertainties: uncertainty requires needs_review")
        if intent["kind"] == "unknown" and value["status"] != "needs_review":
            errors.append(f"{loc}.kind: unknown requires needs_review")
        evidence = intent["evidence_refs"]
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{loc}.evidence_refs: nonempty array required")
            continue
        checked_refs = []
        selected_spans = set()
        for e_index, ref in enumerate(evidence):
            rloc = f"{loc}.evidence_refs[{e_index}]"
            # v2 delegates all quote copying to deterministic code. Preserve
            # the old strict quote schema below for immutable v1 recordings.
            if isinstance(ref, dict) and set(ref) == {"span_id"}:
                span_id = ref["span_id"]
                if not isinstance(span_id, str) or span_id not in spans_by_id:
                    errors.append(f"{rloc}.span_id: unknown source span")
                    continue
                if span_id in selected_spans:
                    errors.append(f"{rloc}.span_id: duplicate source span")
                    continue
                selected_spans.add(span_id)
                span = spans_by_id[span_id]
                checked_refs.append({"id": source["id"], "quote": span["text"],
                    "locator": {"fragment_id": "body", "start": span["start"], "end": span["end"]}})
                continue
            if not _keys(ref, {"id", "quote", "locator"}, rloc, errors):
                continue
            if ref["id"] != source["id"]:
                errors.append(f"{rloc}.id: must match trusted source ID")
            if not _keys(ref["locator"], {"fragment_id"}, rloc + ".locator", errors):
                continue
            if ref["locator"]["fragment_id"] != "body":
                errors.append(f"{rloc}.locator: unknown fragment")
            quote = ref["quote"]
            if not _nonempty(quote):
                errors.append(f"{rloc}.quote: nonempty exact quote required")
                continue
            start = source["text"].find(quote)
            if start < 0:
                errors.append(f"{rloc}.quote: no exact source match")
                continue
            if source["text"].find(quote, start + 1) != -1:
                errors.append(f"{rloc}.quote: ambiguous span; use a longer unique quote")
                continue
            checked_refs.append({"id": source["id"], "quote": quote,
                                 "locator": {"fragment_id": "body", "start": start,
                                             "end": start + len(quote)}})
        if len(errors) != before:
            continue
        stable_payload = [source["id"], source["product_id"], source["text"],
                          intent["kind"], intent["origin"], intent["statement"], checked_refs]
        identifier = "intent_" + sha256(json.dumps(stable_payload, ensure_ascii=False,
                                                   sort_keys=True).encode()).hexdigest()[:24]
        if identifier in identifiers:
            errors.append(f"{loc}: duplicate intent")
            continue
        identifiers.add(identifier)
        normalized.append({**intent, "intent_id": identifier,
                           "evidence_refs": checked_refs,
                           "review_required": value["status"] == "needs_review"})
    if errors:
        return ValidationResult(False, None, errors)
    return ValidationResult(True, {"status": value["status"], "intents": normalized}, [])


def _candidate_errors(candidates: list[dict]) -> list[str]:
    if not isinstance(candidates, list) or len(candidates) > 5:
        return ["candidates: array with at most five entries required"]
    errors, ids = [], set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            errors.append(f"candidates[{index}]: expected object")
            continue
        for field in ("id", "product_id", "statement"):
            if not _nonempty(candidate.get(field)):
                errors.append(f"candidates[{index}].{field}: nonempty string required")
        identifier = candidate.get("id")
        if isinstance(identifier, str):
            if identifier in ids:
                errors.append("candidates: duplicate ID")
            ids.add(identifier)
    return errors


def matching_messages(intent: dict, candidates: list[dict]) -> list[dict[str, str]]:
    errors = _candidate_errors(candidates)
    if errors:
        raise ValueError("; ".join(errors))
    # Intent evidence is useful context; evaluation labels and source provenance
    # such as case_pdf/synthetic are intentionally not passed to the model.
    payload = {
        "intent": {key: intent[key] for key in
                   ("kind", "origin", "statement", "evidence_refs", "uncertainties")},
        "candidates": [{key: candidate[key] for key in ("id", "product_id", "statement")}
                       for candidate in candidates],
    }
    return [{"role": "system", "content": MATCHING_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def validate_matching(raw: str, candidates: list[dict]) -> ValidationResult:
    errors = _candidate_errors(candidates)
    if errors:
        return ValidationResult(False, None, errors)
    decoded = _decode(raw)
    if not decoded.ok:
        return decoded
    value = decoded.value
    if not _keys(value, {"matches"}, "response", errors):
        return ValidationResult(False, None, errors)
    if not isinstance(value["matches"], list):
        return ValidationResult(False, None, ["matches: array required"])
    allowed = {candidate["id"] for candidate in candidates}
    seen = set()
    for index, match in enumerate(value["matches"]):
        loc = f"matches[{index}]"
        if not _keys(match, {"candidate_id", "relation", "basis"}, loc, errors):
            continue
        identifier = match["candidate_id"]
        if not isinstance(identifier, str) or identifier not in allowed:
            errors.append(f"{loc}.candidate_id: unknown ID")
        elif identifier in seen:
            errors.append(f"{loc}.candidate_id: duplicate ID")
        else:
            seen.add(identifier)
        if not isinstance(match["relation"], str) or match["relation"] not in RELATIONS:
            errors.append(f"{loc}.relation: invalid relation")
        if not _nonempty(match["basis"]):
            errors.append(f"{loc}.basis: nonempty explanation required")
    if seen != allowed:
        errors.append("matches: every candidate must be covered exactly once")
    if errors:
        return ValidationResult(False, None, errors)
    return ValidationResult(True, value, [])


def resolve_topic(intent: dict, source: dict, candidates: list[dict],
                  matching_result: ValidationResult | None) -> dict:
    """Assign only explicit, reviewed wishes; uncertainty never triggers a merge."""
    def decision(status, topic_id=None, reason=""):
        return {"status": status, "topic_id": topic_id, "reason": reason}
    if intent.get("review_required"):
        return decision("needs_review", reason="Extraction requires review")
    if intent.get("kind") not in {"feature_request", "usability"} or intent.get("origin") != "user_explicit":
        return decision("not_eligible", reason="Not an explicit wish")
    if source.get("speaker") != "user":
        return decision("needs_review", reason="Unverified user authorship")
    if _candidate_errors(candidates):
        return decision("needs_review", reason="Invalid candidate registry")
    if any(c["product_id"] != source["product_id"] for c in candidates):
        return decision("needs_review", reason="Candidate outside product scope")
    if not _nonempty(intent.get("intent_id")):
        return decision("needs_review", reason="Validated stable intent ID missing")
    if candidates:
        if matching_result is None or not matching_result.ok:
            return decision("needs_review", reason="Matching response missing or invalid")
        # Revalidate to bind the result to these exact candidate IDs.
        rechecked = validate_matching(json.dumps(matching_result.value, ensure_ascii=False), candidates)
        if not rechecked.ok:
            return decision("needs_review", reason="Matching response has another candidate scope")
        matches = rechecked.value["matches"]
        if any(m["relation"] == "unclear" for m in matches):
            return decision("needs_review", reason="Unclear relation; no automatic merge")
        same = [m["candidate_id"] for m in matches if m["relation"] == "same"]
        if len(same) > 1:
            return decision("needs_review", reason="Multiple same candidates require registry review")
        if same:
            return decision("matched", same[0], "One same relation")
    elif matching_result is not None:
        if not matching_result.ok or not validate_matching(json.dumps(matching_result.value), []).ok:
            return decision("needs_review", reason="Unexpected matching result with empty registry")
    topic_seed = json.dumps([source["product_id"], intent["intent_id"]], ensure_ascii=False)
    topic_id = "topic_" + sha256(topic_seed.encode()).hexdigest()[:24]
    return decision("new", topic_id, "No same or unclear candidate")


def prepared_contract_payload(source: dict, extraction: ValidationResult | dict,
                              topic_assignments: dict[str, str | None],
                              pipeline_version: str = "text-experiment-v1") -> dict:
    """Adapt validated evidence to ContractDemo; registration/ACL stay with caller.

An empty extraction has no payload in that demonstrator. The caller should
record it as a successful no-intent inference instead of invoking analyze().
"""
    if isinstance(extraction, ValidationResult):
        if not extraction.ok:
            raise ValueError("Cannot adapt an invalid extraction")
        extraction = extraction.value
    if extraction["status"] != "ok":
        raise ValueError("Review-required extraction cannot enter the automatic stream")
    if not extraction["intents"]:
        raise ValueError("No intents to register; retain the successful empty result")
    items = []
    for intent in extraction["intents"]:
        topic_id = topic_assignments.get(intent["intent_id"])
        if topic_id is not None and (intent["kind"] not in {"feature_request", "usability"}
                                    or intent["origin"] != "user_explicit"):
            raise ValueError("Only explicit wishes may be assigned a topic")
        for ref in intent["evidence_refs"]:
            locator = ref["locator"]
            if ref["id"] != source["id"] or source["text"][locator["start"]:locator["end"]] != ref["quote"]:
                raise ValueError("Evidence does not belong to this source")
        items.append({"label": intent["kind"], "origin": intent["origin"],
                      "need": intent["statement"], "topic_id": topic_id,
                      "evidence": [{"fragment_id": ref["locator"]["fragment_id"],
                                    "start": ref["locator"]["start"],
                                    "end": ref["locator"]["end"], "quote": ref["quote"]}
                                   for ref in intent["evidence_refs"]]})
    return {"source_id": source["id"], "source_version": 1,
            "pipeline_version": pipeline_version, "items": items}
