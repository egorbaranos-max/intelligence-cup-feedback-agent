"""Static live response shapes; identity and semantic checks stay in validators.

These schemas encode the existing v2 contracts, not expected evaluation labels.
Historical quote-based responses remain readable by the unchanged validators.
"""


def _object(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def _text():
    return {"type": "string", "minLength": 1}


EXTRACTION_SCHEMA = _object({
    "status": {"type": "string", "enum": ["ok", "needs_review"]},
    "intents": {"type": "array", "maxItems": 30, "items": _object({
        "kind": {"type": "string", "enum": ["incident", "service_request", "feature_request", "usability", "unknown"]},
        "origin": {"type": "string", "enum": ["user_explicit", "observed_pain", "hypothesis"]},
        "statement": _text(),
        "evidence_refs": {"type": "array", "minItems": 1,
                          "items": _object({"span_id": _text()})},
        "uncertainties": {"type": "array", "items": _text()},
    })},
})

VERIFICATION_SCHEMA = _object({
    "verdict": {"type": "string", "enum": ["supported", "unsupported", "unclear"]},
    "reason": _text(),
    "evidence_span_ids": {"type": "array", "items": _text()},
})

MATCHING_SCHEMA = _object({
    "matches": {"type": "array", "maxItems": 5, "items": _object({
        "candidate_id": _text(),
        "relation": {"type": "string", "enum": ["same", "related", "different", "unclear"]},
        "basis": _text(),
    })},
})

# Limits mirror pipeline.validate_extraction and the five-candidate batch
# contract. No evidence-ID prefix, source-specific ID enum, or semantic decision
# is imposed here. Validators still check membership, uniqueness and coverage.
RESPONSE_SCHEMAS = {"extraction": EXTRACTION_SCHEMA,
                    "verification": VERIFICATION_SCHEMA,
                    "matching": MATCHING_SCHEMA}

STAGE_SCHEMAS = {"extraction": "extraction", "extraction_repair": "extraction",
                 "verification": "verification", "matching": "matching"}
