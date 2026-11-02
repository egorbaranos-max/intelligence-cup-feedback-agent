# Stage JSON schema integration evidence

The local backend now constrains each application stage to its existing response contract. Extraction and extraction repair share a schema; verification and matching have their own. A generic JSON-object mode remains available for standalone syntax probes. All schemas share one cached local tokenizer and receive a fresh matcher per generation.

Extraction requires status and an intents array; each intent has exactly kind, origin, statement, evidence_refs and uncertainties. Existing category enums are enforced before sampling. Arrays preserve multiple intents and evidence references. The 30-intent and five-candidate limits mirror existing validators. Verification constrains verdict, reason and evidence_span_ids; matching constrains candidate_id, relation and basis. No new ID prefix or semantic rule is imposed. Validators still enforce identity, membership, uniqueness, complete candidate coverage, author consistency and supported evidence.

This uses the same pinned [llguidance 1.9.1 release](https://pypi.org/project/llguidance/1.9.1/), [JSON-schema implementation](https://github.com/guidance-ai/llguidance/blob/v1.9.1/docs/json_schema.md) and [MLX adapter](https://github.com/guidance-ai/llguidance/blob/v1.9.1/python/llguidance/mlx.py) as the preceding generic-grammar integration. Historical generic smoke files were preserved; exact earlier backend sources are in `../structured-decoding/source-snapshot/`.

| Check | Recorded result |
| --- | --- |
| Full stdlib suite | 261 tests: 251 passed, 10 optional checks skipped |
| Stage tests, actual 4B tokenizer on CPU | 8 passed |
| Stage tests, actual 8B tokenizer on CPU | 8 passed |
| 4B GPU with real application prompts | Extraction, verification and matching passed existing mechanical validators |
| 8B GPU with real application prompts | Extraction, verification and matching passed existing mechanical validators |

CPU token-mask tests explicitly reject both `kind="no_feature_request"` and `kind="observed_pain"`, plus invalid origins, verdicts, relations, keys and types. They accept multiple intents/references and demonstrate that unknown-author and unknown-ID failures remain the validator's responsibility. GPU reports preserve all raw responses, prompts, selected schemas and source hashes. Verification and matching use a declared synthetic fixture intent, so this is not an end-to-end accuracy evaluation. No holdout cases, human labels, semantic-quality claims, prompt changes or model training are involved.

Each call records `response_schema`; its statistics repeat that field and include `structured_json.schema_name` and `schema_sha256`. Backend provenance contains exact schemas and their schema/grammar-specification hashes. Schema SHA-256 uses UTF-8 JSON with `sort_keys=True`, `separators=(',', ':')`, `ensure_ascii=False`. `source-snapshot/` preserves the tested implementation. The local manifest hashes evidence and source files; raw model reports are unchanged.

Reproduce from the repository root, using the existing live runtime and local model manifests:

```sh
export LIVE_PYTHON="/absolute/path/to/live-venv/bin/python"
export MODEL_4B_MANIFEST="/absolute/path/to/4b-model-manifest.json"
export MODEL_8B_MANIFEST="/absolute/path/to/8b-model-manifest.json"
uv pip install --python "$LIVE_PYTHON" -r requirements-live.txt
python3 -m unittest discover -s tests -v
STRUCTURED_TOKENIZER_MANIFEST="$MODEL_4B_MANIFEST" "$LIVE_PYTHON" -m unittest discover -s tests -p test_response_schemas.py -v
STRUCTURED_TOKENIZER_MANIFEST="$MODEL_8B_MANIFEST" "$LIVE_PYTHON" -m unittest discover -s tests -p test_response_schemas.py -v
"$LIVE_PYTHON" scripts/smoke_stage_schemas.py --model-manifest "$MODEL_4B_MANIFEST" --output /absolute/path/to/new-stage-4b.json
"$LIVE_PYTHON" scripts/smoke_stage_schemas.py --model-manifest "$MODEL_8B_MANIFEST" --output /absolute/path/to/new-stage-8b.json
```

Run the GPU commands sequentially. Recorded integration used MLX-LM 0.32.2, MLX 0.32.4 and Python 3.11.5. Grammar constraints enforce output structure; they do not prove correct interpretation, relevant evidence or valid recurrence. Native resource limits and truncation still fail explicitly without JSON repair or unconstrained fallback.
