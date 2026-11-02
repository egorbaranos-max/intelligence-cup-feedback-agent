# Local JSON grammar integration evidence

The MLX backend uses `llguidance==1.9.1` to mask invalid tokens before sampling. The grammar requires one JSON object, permits recursive nesting and Unicode escapes, and leaves the existing field and meaning validators in place. It uses the already loaded local tokenizer and the official MLX mask adapter. The chat template and generated text are preserved.

The published ARM64 ABI3 wheel is 3,141,060 bytes, SHA-256 `a942487cd6221b793df3a11450881a6c9d25a45460a900c56d99b682633c45fe`, with no mandatory transitive dependencies. The implementation was checked against the installed release, its [PyPI package](https://pypi.org/project/llguidance/1.9.1/), [versioned MLX adapter](https://github.com/guidance-ai/llguidance/blob/v1.9.1/python/llguidance/mlx.py), and [versioned JSON grammar documentation](https://github.com/guidance-ai/llguidance/blob/v1.9.1/docs/json_schema.md).

| Check | Recorded result |
| --- | --- |
| Stdlib test runtime | 17 passed; 5 optional native/tokenizer checks skipped |
| Actual cached Qwen3-4B tokenizer, CPU | 22 passed; no skipped checks |
| Actual cached Qwen3-8B tokenizer, CPU | 22 passed; no skipped checks |
| Qwen3-4B, actual Apple GPU | Metal mask check, 3 JSON calls, forced truncation rejection passed |
| Qwen3-8B, actual Apple GPU | Metal mask check, 3 JSON calls, forced truncation rejection passed |

The logs and JSON reports retain commands, versions, code hashes, unchanged raw GPU responses, and failure details. `recorded-smoke-harness.py` preserves the initial 4B harness; the 8B report records the hash of `scripts/smoke_structured_decoding.py`, the maintained entry point with output overwrite protection. Both use the same probes and assertions. The two model reports reference the same backend and grammar source hashes. These synthetic syntax probes do not measure extraction or grouping quality and do not use holdout cases or human labels.

To reproduce, start at the repository root. Set the environment variables to an existing live Python environment and already downloaded model manifests. Installation needs network access; tokenizer tests and inference use local files.

```sh
export LIVE_PYTHON="/absolute/path/to/live-venv/bin/python"
export MODEL_4B_MANIFEST="/absolute/path/to/4b-model-manifest.json"
export MODEL_8B_MANIFEST="/absolute/path/to/8b-model-manifest.json"
uv pip install --python "$LIVE_PYTHON" -r requirements-live.txt

python3 -m unittest discover -s tests -p test_structured_decoding.py -v
STRUCTURED_TOKENIZER_MANIFEST="$MODEL_4B_MANIFEST" "$LIVE_PYTHON" -m unittest discover -s tests -p test_structured_decoding.py -v
STRUCTURED_TOKENIZER_MANIFEST="$MODEL_8B_MANIFEST" "$LIVE_PYTHON" -m unittest discover -s tests -p test_structured_decoding.py -v

"$LIVE_PYTHON" scripts/smoke_structured_decoding.py --model-manifest "$MODEL_4B_MANIFEST" --output /absolute/path/to/new-4b-smoke.json
"$LIVE_PYTHON" scripts/smoke_structured_decoding.py --model-manifest "$MODEL_8B_MANIFEST" --output /absolute/path/to/new-8b-smoke.json
```

The GPU commands require Apple Silicon/Metal and must run sequentially. Recorded integration used MLX-LM 0.32.2, MLX 0.32.4 and Python 3.11.5. The callback supports one sequence and the installed MLX token-history lifecycle; speculative or rewritten histories are rejected. Native parser limits, missing dependencies, invalid grammar states and token-budget truncation fail explicitly. Strict completion checks also reject duplicate keys. There is no unconstrained fallback or JSON patching; failure logs retain emitted raw text. `LocalMLX(..., structured_json=False)` is an explicit baseline option and is recorded in provenance. Grammar constraints do not establish factual correctness, correct evidence spans, equivalent topics, or recurrence.
