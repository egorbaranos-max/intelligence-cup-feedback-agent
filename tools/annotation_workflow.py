"""Prepare independent human reviews and export agreed extraction training data.

No model runs, network calls, inferred labels, or automatic human certification.
Reviewer identity is a declared name, not an authenticated corporate identity.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.pipeline import extraction_messages, validate_extraction
from agent.spans import source_spans

SCHEMA = "feedback-human-review-v1"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def load_sources(paths):
    sources = []
    for path in paths:
        sources.extend(json.loads(line) for line in Path(path).read_text().splitlines() if line.strip())
    if not sources or len({s["id"] for s in sources}) != len(sources):
        raise ValueError("Sources must be nonempty and IDs unique")
    for source in sources:
        extraction_messages(source)
    return sources


def review_template(sources):
    return {
        "schema_version": SCHEMA, "dataset_sha256": digest(sources),
        "reviewer_id": "", "label_author": "", "attested_independent": False,
        "items": [{"source_id": s["id"], "source_sha256": digest(s), "reviewed": False,
                   "family_id": "", "split": "unassigned", "note": "",
                   "annotation": {"status": "needs_review" if s["speaker"] != "user" else "ok",
                                  "intents": []}} for s in sources],
    }


def prepare(sources, output):
    payload = {"mode": "independent", "sources": sources,
               "spans": {s["id"]: source_spans(s["text"]) for s in sources},
               "review": review_template(sources)}
    return write_pack(payload, output)


def write_pack(payload, output):
    output = Path(output)
    if output.exists():
        raise ValueError("Use a new output directory; review material is not overwritten")
    template = (ROOT / "tools/annotation_template.html").read_text()
    # Safe inside an application/json script, even for hostile literal </script> text.
    html = template.replace("__ANNOTATION_PAYLOAD__", canonical(payload).replace("<", "\\u003c"))
    output.mkdir(parents=True)
    (output / "index.html").write_text(html)
    (output / "blank-review.json").write_text(json.dumps(payload["review"], ensure_ascii=False, indent=2) + "\n")
    (output / "inputs.jsonl").write_text("".join(canonical(s) + "\n" for s in payload["sources"]))
    return {"source_count": len(payload["sources"]),
            "dataset_sha256": payload["review"]["dataset_sha256"],
            "mode": payload["mode"],
            "html": str((output / "index.html").resolve()), "status": "unlabelled; human action required"}


def checked_review(review, sources, *, independent=True, allow_subset=False):
    if review.get("schema_version") != SCHEMA or review.get("dataset_sha256") != digest(sources):
        raise ValueError("Review schema or dataset hash mismatch")
    if review.get("label_author") != "human":
        raise ValueError("Training requires declared human labels, not AI-generated expectations")
    reviewer = review.get("reviewer_id")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Human reviewer_id is required")
    if independent and review.get("attested_independent") is not True:
        raise ValueError("Reviewer must explicitly attest independent first-pass review")
    raw_items = review.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("Review items must be an array")
    index = {i.get("source_id"): i for i in raw_items if isinstance(i, dict)}
    known = {s["id"] for s in sources}
    if len(index) != len(raw_items) or not set(index) <= known:
        raise ValueError("Review contains malformed, duplicate or unknown source IDs")
    if not allow_subset and set(index) != known:
        raise ValueError("Review must include every source; do not silently drop hard cases")
    by_id = {s["id"]: s for s in sources}
    for source_id, item in index.items():
        source = by_id[source_id]
        if item.get("source_sha256") != digest(source) or item.get("reviewed") is not True:
            raise ValueError(f"{source_id}: changed source or unreviewed record")
        if not isinstance(item.get("family_id"), str) or not item["family_id"].strip():
            raise ValueError(f"{source_id}: human-assigned semantic family_id required")
        if item.get("split") not in {"train", "valid", "test"}:
            raise ValueError(f"{source_id}: explicit train/valid/test split required")
        result = validate_extraction(canonical(item.get("annotation")), source)
        if not result.ok:
            raise ValueError(f"{source_id}: invalid annotation: {'; '.join(result.errors)}")
    return index


def comparable(item):
    return {k: item[k] for k in ("family_id", "split", "annotation")}


def prepare_adjudication(sources, reviews, output):
    """Expose only disagreements after two complete independent first passes."""
    if len(reviews) != 2:
        raise ValueError("Exactly two independent first-pass reviews are required")
    checked = [checked_review(r, sources) for r in reviews]
    if len({r["reviewer_id"].strip().casefold() for r in reviews}) != 2:
        raise ValueError("The two reviewers must declare different identities")
    conflicts = [s["id"] for s in sources
                 if comparable(checked[0][s["id"]]) != comparable(checked[1][s["id"]])]
    if not conflicts:
        return {"status": "no_disagreements", "source_ids": [],
                "dataset_sha256": digest(sources), "message": "No adjudication package needed"}
    visible = [s for s in sources if s["id"] in conflicts]
    blank = review_template(sources)  # Retain the hash of the entire original set.
    blank["items"] = [item for item in blank["items"] if item["source_id"] in conflicts]
    payload = {"mode": "adjudication", "sources": visible,
               "spans": {s["id"]: source_spans(s["text"]) for s in visible},
               "review": blank, "first_pass_review_sha256": [digest(r) for r in reviews],
               "first_pass_answers": {
                   sid: [{"reviewer_id": r["reviewer_id"], "item": c[sid]}
                         for r, c in zip(reviews, checked)] for sid in conflicts}}
    result = write_pack(payload, output)
    result["source_ids"] = conflicts
    return result


def export_training(sources, reviews, output, adjudication=None):
    if len(reviews) != 2:
        raise ValueError("Exactly two independent first-pass reviews are required")
    checked = [checked_review(r, sources) for r in reviews]
    identities = [r["reviewer_id"].strip().casefold() for r in reviews]
    if len(set(identities)) != 2:
        raise ValueError("The two reviewers must declare different identities")
    conflicts = [s["id"] for s in sources if comparable(checked[0][s["id"]]) != comparable(checked[1][s["id"]])]
    resolved = checked[0].copy()
    if conflicts and adjudication is None:
        return {"status": "blocked_disagreement", "source_ids": conflicts,
                "message": "A third human must reconcile these records; no training files written"}
    if adjudication is not None:
        third = checked_review(adjudication, sources, independent=False, allow_subset=True)
        if adjudication["reviewer_id"].strip().casefold() in identities:
            raise ValueError("Adjudication requires a third declared human reviewer")
        if set(third) != set(conflicts):
            raise ValueError("Adjudication must cover exactly all disagreement records")
        resolved.update(third)
    # Semantic families are assigned by people. Also catch objective leakage even
    # when someone accidentally gives the same episode or exact text two names.
    assigned = {}
    for source in sources:
        item = resolved[source["id"]]
        keys = [("family", item["family_id"]), ("text", source["product_id"], source["text"])]
        if source.get("episode_id"):
            keys.append(("episode", source["product_id"], source["episode_id"]))
        for key in keys:
            if key in assigned and assigned[key] != item["split"]:
                raise ValueError(f"Data leakage across splits for {key[0]}")
            assigned[key] = item["split"]
    counts = Counter(i["split"] for i in resolved.values())
    if any(counts[name] == 0 for name in ("train", "valid", "test")):
        raise ValueError("All three splits must be nonempty; this is not a quality sample-size criterion")
    output = Path(output)
    if output.exists():
        raise ValueError("Use a new training export directory")
    datasets = {name: [] for name in ("train", "valid", "test")}
    heldout_sources, heldout_labels = [], []
    for source in sources:
        item = resolved[source["id"]]
        example = {"messages": extraction_messages(source) +
                   [{"role": "assistant", "content": canonical(item["annotation"])}]}
        datasets[item["split"]].append(example)
        if item["split"] == "test":
            heldout_sources.append(source)
            heldout_labels.append({"source_id": source["id"], "family_id": item["family_id"],
                                   "annotation": item["annotation"]})
    (output / "training").mkdir(parents=True)
    (output / "heldout").mkdir()
    for name in ("train", "valid"):
        (output / "training" / f"{name}.jsonl").write_text("".join(canonical(x) + "\n" for x in datasets[name]))
    for name, records in (("inputs", heldout_sources), ("labels", heldout_labels)):
        (output / "heldout" / f"{name}.jsonl").write_text("".join(canonical(x) + "\n" for x in records))
    manifest = {"status": "exported; training not run", "schema_version": SCHEMA,
                "created_at": datetime.now(timezone.utc).isoformat(), "dataset_sha256": digest(sources),
                "reviewers": [r["reviewer_id"] for r in reviews],
                "review_sha256": [digest(r) for r in reviews],
                "adjudication_sha256": digest(adjudication) if adjudication else None,
                "counts": dict(counts), "source_ids": {k: [s["id"] for s in sources if resolved[s["id"]]["split"] == k] for k in datasets},
                "code_sha256": {"agent/" + p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted((ROOT / "agent").glob("*.py"))},
                "limits": ["human identity and independence are self-attested, not authenticated",
                           "schema agreement does not establish semantic truth",
                           "nonempty splits do not establish statistical adequacy",
                           "this export trains extraction only, not matching or verification"]}
    manifest["files_sha256"] = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(output.glob("*/*.jsonl"))}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "prepare-adjudication", "export"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--inputs", nargs="+", type=Path, required=True)
        cmd.add_argument("--output", type=Path, required=True)
        if name in {"prepare-adjudication", "export"}:
            cmd.add_argument("--reviews", nargs=2, type=Path, required=True)
        if name == "export":
            cmd.add_argument("--adjudication", type=Path)
    args = parser.parse_args()
    sources = load_sources(args.inputs)
    if args.command == "prepare":
        result = prepare(sources, args.output)
    else:
        reviews = [json.loads(p.read_text()) for p in args.reviews]
        if args.command == "prepare-adjudication":
            result = prepare_adjudication(sources, reviews, args.output)
        else:
            third = json.loads(args.adjudication.read_text()) if args.adjudication else None
            result = export_training(sources, reviews, args.output, third)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") == "blocked_disagreement":
        sys.exit(2)


if __name__ == "__main__":
    main()
