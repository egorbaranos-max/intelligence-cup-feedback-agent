"""Evidence-aligned comparisons against provisional labels, never human accuracy.

This module reads labels only after inference. It cannot establish that a model's
paraphrase is faithful: matching exact evidence and a coarse class is necessary,
not sufficient. Ambiguous citation alignment is shown explicitly, never guessed.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path


NOTICE = ("Preliminary AI-authored labels, not human gold. Evidence/class alignment "
          "does not prove a faithful paraphrase. This small constructed sample "
          "cannot establish production precision, recall, safety or financial effect.")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _overlap(actual_quotes, expected_quotes):
    # A sentence selected by the model may contain the shorter labeled quote.
    # Arbitrary token similarity is deliberately not used to invent an alignment.
    return any(a.strip() and b.strip() and (a in b or b in a)
               for a in actual_quotes for b in expected_quotes)


def _new_demand(intent):
    return intent.get("kind") in {"feature_request", "usability"} and intent.get("origin") == "user_explicit"


def _pairs(edges):
    """Maximum one-to-one matching: one actual intent cannot cover two labels."""
    matched = {}
    def augment(expected, visited):
        for actual in edges[expected]:
            if actual in visited:
                continue
            visited.add(actual)
            if actual not in matched or augment(matched[actual], visited):
                matched[actual] = expected
                return True
        return False
    for expected in range(len(edges)):
        augment(expected, set())
    return {expected: actual for actual, expected in matched.items()}


def _labels_for_source(source, expected):
    labels = expected.get("intents")
    if labels is None:
        return None
    if not isinstance(labels, list):
        raise ValueError("Provisional intent labels must be an array")
    ids = set()
    for label in labels:
        identifier = label.get("intent_id")
        quotes = label.get("evidence_quotes")
        if not identifier or identifier in ids:
            raise ValueError("Missing or duplicate provisional intent ID")
        ids.add(identifier)
        if not isinstance(quotes, list) or not quotes or any(
                not isinstance(q, str) or not q.strip() or q not in source["text"] for q in quotes):
            raise ValueError("Provisional intent quote must be exact and nonempty")
        if not isinstance(label.get("new_demand"), bool):
            raise ValueError("Provisional new_demand must be boolean")
    return labels


def evaluate_semantics(run_path, sources, expected, themes, results, validated, manifest, *, legacy_review=False):
    run_path = Path(run_path)
    names = ("cards.json", "local-receiver.json") if legacy_review else (
        "cards.json", "local-receiver.json", "review-queue.json", "source-audit.json")
    for name in names:
        if name not in manifest.get("output_sha256", {}):
            raise ValueError(f"Missing hash-bound v2 artifact: {name}")
        if hashlib.sha256((run_path / name).read_bytes()).hexdigest() != manifest["output_sha256"][name]:
            raise ValueError(f"Saved artifact SHA-256 differs: {name}")
    cards, receiver = [_load(run_path / n) for n in ("cards.json", "local-receiver.json")]
    if legacy_review:
        # This is a post-hoc workload proxy, not a claim v1 saved a review queue.
        # Use the same routing conditions as v2, independent of all gold labels.
        review, audit = [], []
        results = {key: dict(value) for key, value in results.items()}
        for source_id, result in results.items():
            extraction, source = validated[source_id], sources[source_id]
            needs_review = (not extraction.ok or extraction.value["status"] == "needs_review"
                or any(a["status"] == "needs_review" for a in result.get("assignments", []))
                or (any(a.get("topic_id") for a in result.get("assignments", []))
                    and any(source.get(key) is None for key in ("episode_at", "episode_id", "customer_id"))))
            result["review_required"] = bool(needs_review)
            row = {"source_id": source_id, "review_required": bool(needs_review)}
            audit.append(row)
            if needs_review:
                review.append({**row, "source_text": source["text"]})
        manifest = {**manifest, "review_required_sources": len(review), "audited_sources": len(audit)}
    else:
        review = _load(run_path / "review-queue.json")
        audit = _load(run_path / "source-audit.json")
    if not all(isinstance(items, list) for items in (cards, receiver, review)):
        raise ValueError("Cards, receiver and review queue must be arrays")
    review_sources = {item.get("source_id") for item in review}
    if None in review_sources or review_sources - set(sources) or len(review_sources) != len(review):
        raise ValueError("Review queue contains unknown source")
    if not isinstance(audit, list):
        raise ValueError("Source audit must be an array")
    audit_map = {item.get("source_id"): item for item in audit}
    if len(audit_map) != len(audit) or set(audit_map) != set(results):
        raise ValueError("Source audit does not cover each processed result once")
    expected_review = {source_id for source_id, result in results.items() if result.get("review_required")}
    if expected_review != review_sources or expected_review != {
            source_id for source_id, row in audit_map.items() if row.get("review_required")}:
        raise ValueError("Manual review queue differs from source dispositions")
    for item in review:
        if item.get("source_text") != sources[item["source_id"]]["text"]:
            raise ValueError("Review queue source text differs")
    if manifest.get("review_required_sources") != len(review) or manifest.get("audited_sources") != len(audit):
        raise ValueError("Manifest review or audit count differs")
    card_map = {card["topic_id"]: card for card in cards}
    if len(card_map) != len(cards):
        raise ValueError("Duplicate final card topic")
    delivered_ids = [card["topic_id"] for card in receiver]
    if len(delivered_ids) != len(set(delivered_ids)):
        raise ValueError("Duplicate local delivery")
    for delivered in receiver:
        if delivered != card_map.get(delivered["topic_id"]) or not delivered.get("recurring"):
            raise ValueError("Local receiver differs from final recurring card")
    if manifest.get("delivered_local_cards") != len(receiver):
        raise ValueError("Manifest local delivery count differs")

    per_source, label_map = [], {}
    for source_id, source in sources.items():
        labels = _labels_for_source(source, expected[source_id])
        label_map[source_id] = labels
        extraction = validated.get(source_id)
        actual = extraction.value["intents"] if extraction and extraction.ok else []
        result = results.get(source_id, {})
        row = {"source_id": source_id, "processed": source_id in results,
               "valid_contract": bool(extraction and extraction.ok),
               "in_review_queue": source_id in review_sources,
               "expected_delivery": expected[source_id].get("expected_delivery"),
               "assignments": [{k: a.get(k) for k in
                   ("intent_id", "status", "topic_id", "reason")} for a in result.get("assignments", [])],
               "intent_labels_available": labels is not None}
        if labels is not None:
            edges, alignments = [], []
            for label in labels:
                aligned = [i for i, intent in enumerate(actual) if _overlap(
                    [ref["quote"] for ref in intent["evidence_refs"]], label["evidence_quotes"])]
                accepted = label.get("allowed_kinds", [label.get("kind")])
                compatible = [i for i in aligned if actual[i]["kind"] in accepted
                    and _new_demand(actual[i]) == label["new_demand"]
                    and (label.get("origin") is None or actual[i]["origin"] == label["origin"])]
                edges.append(compatible)
                alignments.append(aligned)
            paired = _pairs(edges)
            row["expected_intents"] = [{"intent_id": label["intent_id"],
                "kind": label.get("kind"), "new_demand": label["new_demand"],
                "evidence_aligned_actual_ids": [actual[i]["intent_id"] for i in alignments[n]],
                "evidence_and_class_match": n in paired,
                "matched_actual_id": actual[paired[n]]["intent_id"] if n in paired else None}
                for n, label in enumerate(labels)]
            row["all_expected_intents_matched"] = len(paired) == len(labels)
            row["unmatched_actual_intents"] = len(actual) - len(paired)
            row["actual_intents"] = len(actual)
        per_source.append(row)

    labels_available = all(v is not None for v in label_map.values())
    theme_rows, card_rows = [], []
    theme_map = {t["topic_id"]: t for t in themes or []}
    if len(theme_map) != len(themes or []):
        raise ValueError("Duplicate provisional theme ID")
    for card in cards:
        associations, unsupported, ambiguous = [], [], []
        for evidence in card.get("evidence", []):
            source_id, quote = evidence["source_id"], evidence["quote"]
            if source_id not in sources or quote not in sources[source_id]["text"]:
                raise ValueError("Card evidence is not an exact known source quote")
            if label_map[source_id] is None:
                ambiguous.append(source_id)
                continue
            topics = {label["topic_id"] for label in label_map[source_id]
                if label.get("new_demand") and label.get("topic_id") and not label.get("review_required")
                and _overlap([quote], label["evidence_quotes"])}
            if not topics:
                unsupported.append(source_id)
            elif len(topics) != 1:
                ambiguous.append(source_id)
            else:
                associations.append(next(iter(topics)))
        distinct = set(associations)
        theme_id = next(iter(distinct)) if len(distinct) == 1 else None
        theme = theme_map.get(theme_id)
        if not labels_available or themes is None:
            assessment = "not_scored_missing_intent_or_theme_labels"
        elif unsupported or len(distinct) > 1:
            assessment = "provisionally_unsupported_or_mixed"
        elif ambiguous or not associations or theme is None:
            assessment = "unscored_ambiguous_evidence_alignment"
        elif not {e["source_id"] for e in card.get("evidence", [])}.issubset(set(theme["eligible_source_ids"])):
            assessment = "provisionally_ineligible_evidence"
        elif card["topic_id"] in delivered_ids and not theme["expected_recurring"]:
            assessment = "provisionally_false_recurrence"
        else:
            assessment = "provisionally_supported_evidence_and_class"
        card_rows.append({"actual_topic_id": card["topic_id"], "title": card["title"],
            "delivered": card["topic_id"] in delivered_ids, "assessment": assessment,
            "provisional_theme_id": theme_id, "unsupported_source_ids": sorted(set(unsupported)),
            "ambiguous_source_ids": sorted(set(ambiguous)),
            "source_ids": sorted({e["source_id"] for e in card.get("evidence", [])})})
    for theme in themes or []:
        eligible = theme["eligible_source_ids"]
        if set(eligible) - set(sources):
            raise ValueError("Provisional theme contains unknown source")
        as_of = datetime.fromisoformat(manifest["as_of"].replace("Z", "+00:00"))
        members = [sources[i] for i in eligible]
        for source in members:
            at = source.get("episode_at")
            if source.get("speaker") != "user" or not at or not (
                    as_of - timedelta(days=30) < datetime.fromisoformat(at.replace("Z", "+00:00")) <= as_of):
                raise ValueError("Provisional eligible theme source violates author/time policy")
        episodes = {(s["product_id"], s["episode_id"]) for s in members if s.get("episode_id")}
        customers = {s["customer_id"] for s in members if s.get("episode_id") and s.get("customer_id")}
        recurring = len(episodes) >= 3 and len(customers) >= 2
        if recurring != theme["expected_recurring"]:
            raise ValueError("Provisional recurring label differs from trusted eligible identities")
        supported = [c["actual_topic_id"] for c in card_rows if c["delivered"]
            and c["provisional_theme_id"] == theme["topic_id"]
            and c["assessment"] == "provisionally_supported_evidence_and_class"]
        theme_rows.append({"topic_id": theme["topic_id"], "expected_recurring": recurring,
            "eligible_sources": len(eligible), "independent_episodes": len(episodes),
            "known_customers": len(customers), "supported_delivery_topic_ids": supported,
            "missed_or_unconfirmed": recurring and not supported})
    scored_rows = [r for r in per_source if r["intent_labels_available"]]
    expected_intents = [i for r in scored_rows for i in r["expected_intents"]]
    delivered_rows = [c for c in card_rows if c["delivered"]]
    return {"disclaimer": NOTICE, "alignment_method": "Exact quote containment plus allowed class/origin/new-demand flag; maximum one-to-one matching. Paraphrase fidelity requires human review.",
        "intent_labels_available_for_all_sources": labels_available,
        "theme_labels_available": themes is not None,
        "summary": {"sources": len(sources), "sources_with_intent_labels": len(scored_rows),
            "valid_extraction_contracts": sum(r["valid_contract"] for r in per_source),
            "sources_all_expected_intents_matched": sum(r["all_expected_intents_matched"] for r in scored_rows),
            "expected_intents": len(expected_intents),
            "expected_intents_evidence_and_class_matched": sum(i["evidence_and_class_match"] for i in expected_intents),
            "unmatched_actual_intents": sum(r["unmatched_actual_intents"] for r in scored_rows),
            "review_queue_sources": len(review_sources), "review_queue_items": len(review),
            "delivered_local_cards": len(receiver),
            "delivered_cards_supported_by_provisional_labels": sum(c["assessment"] == "provisionally_supported_evidence_and_class" for c in delivered_rows),
            "delivered_cards_contradicting_provisional_labels": sum(c["assessment"].startswith("provisionally_") and c["assessment"] != "provisionally_supported_evidence_and_class" for c in delivered_rows),
            "delivered_cards_unscored": sum(not c["assessment"].startswith("provisionally_") for c in delivered_rows),
            "expected_recurring_themes": sum(t["expected_recurring"] for t in theme_rows),
            "recurring_themes_missed_or_unconfirmed": sum(t["missed_or_unconfirmed"] for t in theme_rows)},
        "sources": per_source, "cards": card_rows, "themes": theme_rows}
