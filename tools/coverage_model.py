"""Coverage7 from an independent, adjudicated gold cohort, never detector output.

JSON input: scope_id, cohort_start, cohort_end, as_of, gold. Each gold record has
topic_id, scope_id, eligible_at, delivered_at (timestamp or null), history_status
(known or fallback). Timestamps must include a timezone and are normalized to UTC.
The cohort is [start, end); maturity is seven full UTC days after eligibility.
delivered_at means a verified qualifying card/update, at or after eligibility.
This calculator cannot establish a correct denominator, recurrence or causality.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys


_DOCUMENT_FIELDS = {"scope_id", "cohort_start", "cohort_end", "as_of", "gold"}
_GOLD_FIELDS = {"topic_id", "scope_id", "eligible_at", "delivered_at", "history_status"}


def _identifier(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string identifier")
    if value != value.strip():
        raise ValueError(f"{field} must not have surrounding whitespace")
    return value


def _timestamp(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO timestamp with a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timezone missing")
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise ValueError(f"{field} must be a valid timezone-aware ISO timestamp") from error


def _iso(value):
    return value.isoformat().replace("+00:00", "Z")


def _exact_fields(value, expected, field):
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    missing, unknown = expected - value.keys(), value.keys() - expected
    if missing or unknown:
        raise ValueError(f"{field}: missing fields {sorted(missing)}, unknown fields {sorted(unknown)}")


def coverage7(document):
    """Return a conditional score; missing and fallback gold stay in the denominator.

    All records must belong to the explicit scope. Duplicate gold is invalid even
    outside the selected window. Delivery events after as_of are censored rather
    than used as observed events. No confidence interval assumes independent needs.
    """
    _exact_fields(document, _DOCUMENT_FIELDS, "input")
    scope = _identifier(document["scope_id"], "scope_id")
    start = _timestamp(document["cohort_start"], "cohort_start")
    end = _timestamp(document["cohort_end"], "cohort_end")
    as_of = _timestamp(document["as_of"], "as_of")
    if end <= start:
        raise ValueError("cohort_end must be after cohort_start (a half-open window)")
    if not isinstance(document["gold"], list):
        raise ValueError("gold must be a list of independently adjudicated records")

    counts = Counter()
    selected_history, mature_history, timely_history = Counter(), Counter(), Counter()
    seen = set()
    for i, record in enumerate(document["gold"]):
        label = f"gold[{i}]"
        _exact_fields(record, _GOLD_FIELDS, label)
        topic = _identifier(record["topic_id"], f"{label}.topic_id")
        record_scope = _identifier(record["scope_id"], f"{label}.scope_id")
        if record_scope != scope:
            raise ValueError(f"{label}.scope_id does not match requested scope {scope!r}")
        key = (record_scope, topic)
        if key in seen:
            raise ValueError(f"Duplicate gold topic/scope {key!r}")
        seen.add(key)
        history = record["history_status"]
        if history not in ("known", "fallback"):
            raise ValueError(f"{label}.history_status must explicitly be known or fallback")
        eligible = _timestamp(record["eligible_at"], f"{label}.eligible_at")
        delivered = (None if record["delivered_at"] is None else
                     _timestamp(record["delivered_at"], f"{label}.delivered_at"))
        if delivered is not None and delivered < eligible:
            raise ValueError(f"{label}.delivered_at must describe a qualifying card/update at or after eligible_at")
        try:
            deadline = eligible + timedelta(days=7)
        except OverflowError as error:
            raise ValueError(f"{label}.eligible_at cannot form a seven-day deadline") from error
        counts["input_gold"] += 1
        if not start <= eligible < end:
            counts["outside_cohort_excluded"] += 1
            continue
        counts["selected_cohort_gold"] += 1
        selected_history[history] += 1
        if delivered is not None and delivered > as_of:
            counts["selected_future_delivery_events_censored"] += 1
        if deadline > as_of:
            counts["immature_gold_excluded"] += 1
            continue
        counts["mature_gold_denominator"] += 1
        mature_history[history] += 1
        if delivered is None or delivered > as_of:
            counts["missing_as_of"] += 1
        elif delivered <= deadline:
            counts["timely"] += 1
            timely_history[history] += 1
        else:
            counts["late_delivered"] += 1

    denominator = counts["mature_gold_denominator"]
    quality = ("fallback_present" if mature_history["fallback"] else
               "known_history_only" if denominator else "N/A_no_mature_gold")
    count_fields = ("input_gold", "selected_cohort_gold", "mature_gold_denominator",
                    "immature_gold_excluded", "outside_cohort_excluded", "timely",
                    "late_delivered", "missing_as_of", "selected_future_delivery_events_censored")
    return {
        "status": "Conditional calculation from supplied independent adjudicated gold",
        "scope_id": scope,
        "cohort_start_inclusive_utc": _iso(start),
        "cohort_end_exclusive_utc": _iso(end),
        "as_of_utc": _iso(as_of),
        "maturity": "eligible_at + 7 full UTC days <= as_of; deadline is inclusive",
        "coverage7": counts["timely"] / denominator if denominator else None,
        "coverage7_population": "combined_observed_cohorts",
        "coverage7_status": "available" if denominator else "N/A_no_mature_gold",
        "counts": {field: counts[field] for field in count_fields},
        "cohort_quality": {
            "mature_history_status": quality,
            "selected_history_counts": {key: selected_history[key] for key in ("known", "fallback")},
            "mature_history_counts": {key: mature_history[key] for key in ("known", "fallback")},
            "fallback_included_in_denominator": True,
        },
        "cohort_scores": {
            history: {
                "definition": ("known_history_cohort" if history == "known" else
                               "first_observed_threshold_cohort; not a claim of newly arising needs"),
                "timely_numerator": timely_history[history],
                "mature_gold_denominator": mature_history[history],
                "coverage7": (timely_history[history] / mature_history[history]
                              if mature_history[history] else None),
                "coverage7_status": ("available" if mature_history[history] else
                                     "N/A_no_mature_gold"),
            }
            for history in ("known", "fallback")
        },
        "limitations": [
            "Independent gold, complete flow, eligible_at, recurrence and correct scope must be adjudicated upstream; this calculator cannot verify them.",
            "Fallback history is reported and included, never silently dropped; its reliability cannot be reconstructed here.",
            "No confidence interval, causal effect, PM review or cash benefit is inferred.",
        ],
    }


def example_input():
    """Hand-authored illustration only: one timely, one late, one missing, one immature."""
    return {
        "scope_id": "synthetic-product",
        "cohort_start": "2026-11-01T00:00:00Z",
        "cohort_end": "2026-11-08T00:00:00Z",
        "as_of": "2026-11-09T00:00:00Z",
        "gold": [
            {"topic_id": "timely", "scope_id": "synthetic-product", "eligible_at": "2026-11-01T00:00:00Z", "delivered_at": "2026-11-08T00:00:00Z", "history_status": "known"},
            {"topic_id": "late", "scope_id": "synthetic-product", "eligible_at": "2026-11-01T00:00:00Z", "delivered_at": "2026-11-08T12:00:00Z", "history_status": "known"},
            {"topic_id": "missing", "scope_id": "synthetic-product", "eligible_at": "2026-11-01T00:00:00Z", "delivered_at": None, "history_status": "fallback"},
            {"topic_id": "immature", "scope_id": "synthetic-product", "eligible_at": "2026-11-07T00:00:00Z", "delivered_at": None, "history_status": "known"},
        ],
    }


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object field {key!r}")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="JSON input file, or - to read stdin")
    parser.add_argument("--example", action="store_true", help="Print synthetic example input, not company data")
    args = parser.parse_args(argv)
    if args.example:
        if args.path is not None:
            parser.error("Use --example without an input path")
        result = example_input()
    else:
        if args.path is None:
            parser.error("Provide a JSON path/- or request --example")
        try:
            raw = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
            document = json.loads(raw, object_pairs_hook=_unique_json_object)
            result = coverage7(document)
        except (OSError, UnicodeError, ValueError) as error:
            parser.error(str(error))
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
