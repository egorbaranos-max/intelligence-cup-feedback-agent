"""Optional token-level JSON grammar; importing this module requires only stdlib.

Pinned LLGuidance supplies a recursive JSON grammar, not output repair. Each
MLX generation owns a fresh matcher. Only sampled completion tokens enter it;
MLX's cumulative prompt history is skipped on the first logits callback.
"""
import hashlib
import importlib.metadata
import json

ENGINE_VERSION = "1.9.1"
OBJECT_SCHEMA = {"type": "object"}
COMPILER_OPTIONS = {
    "whitespace_flexible": True,
    "json_allow_general_unicode_escapes": True,
    "lenient": False,
}


class StructuredDecodingError(RuntimeError):
    """Failure is explicit; the backend attaches unchanged partial output/stats."""


def _strict_object(text):
    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(text, parse_constant=invalid_constant, object_pairs_hook=unique_keys)
    if not isinstance(value, dict):
        raise ValueError("Completion must be a JSON object")
    return value


class JSONLogitsProcessor:
    """Single-sequence MLX-LM 0.32.2 callback, with no speculative/reset fallback.

    ``apply_mask`` receives immutable little-endian bitmask bytes. A fresh mask
    buffer per callback prevents asynchronous MLX work observing a later mask.
    The matcher permits EOS after completion, including MLX's extra look-ahead.
    """

    def __init__(self, matcher, vocab_size, apply_mask, schema_name="generic", schema_sha256=None):
        self.matcher = matcher
        self.vocab_size = vocab_size
        self.apply_mask = apply_mask
        self.history_length = None
        self.previous_last_token = None
        self.prompt_tokens = None
        self.generated_tokens_consumed = 0
        self.callback_count = 0
        self.schema_name, self.schema_sha256 = schema_name, schema_sha256
        self._check_matcher()

    def _check_matcher(self):
        if self.matcher.is_error():
            raise StructuredDecodingError(f"JSON grammar failed: {self.matcher.get_error()}")

    def __call__(self, tokens, logits):
        self._check_matcher()
        if tuple(logits.shape) != (1, self.vocab_size):
            raise StructuredDecodingError("JSON grammar supports one sequence with the exact model vocabulary")
        if len(tokens.shape) != 1 or len(tokens) < 1:
            raise StructuredDecodingError("Expected nonempty cumulative token history")
        count = len(tokens)
        if self.history_length is None:
            self.prompt_tokens = count
        else:
            if count != self.history_length + 1:
                raise StructuredDecodingError("Token history must grow by one; cached/speculative decoding is unsupported")
            if int(tokens[self.history_length - 1].item()) != self.previous_last_token:
                raise StructuredDecodingError("Token history changed; JSON matcher cannot be reset implicitly")
            token = int(tokens[-1].item())
            if not 0 <= token < self.vocab_size:
                raise StructuredDecodingError("Generated token is outside the model vocabulary")
            if not self.matcher.consume_token(token):
                self._check_matcher()
                raise StructuredDecodingError("JSON grammar rejected a generated token")
            self.generated_tokens_consumed += 1
        self.history_length = count
        self.previous_last_token = int(tokens[-1].item())
        self.callback_count += 1
        self._check_matcher()
        mask = self.matcher.compute_bitmask()
        self._check_matcher()
        expected_bytes = ((self.vocab_size + 31) // 32) * 4
        if not isinstance(mask, bytes) or len(mask) not in (expected_bytes, expected_bytes + 4):
            raise StructuredDecodingError("JSON grammar returned an invalid token mask")
        # Native 1.9.1 returns an extra alignment word when vocabulary size is
        # divisible by 32. Only IDs in the model's actual logits are meaningful.
        mask = mask[:expected_bytes]
        full_bytes, remaining_bits = divmod(self.vocab_size, 8)
        if not (any(mask[:full_bytes]) or
                (remaining_bits and mask[full_bytes] & ((1 << remaining_bits) - 1))):
            raise StructuredDecodingError("JSON grammar allows no token; refusing unconstrained fallback")
        return self.apply_mask(logits, mask)

    def finish(self, raw_text, finish_reason):
        """Validate completion without rewriting, completing, or extracting JSON."""
        self._check_matcher()
        if finish_reason != "stop":
            raise StructuredDecodingError(f"JSON generation did not finish normally: {finish_reason}")
        if not self.callback_count or not self.matcher.is_accepting():
            raise StructuredDecodingError("JSON grammar did not reach an accepting state")
        try:
            _strict_object(raw_text)
        except (ValueError, TypeError, RecursionError) as exc:
            raise StructuredDecodingError(f"Generated JSON object failed validation: {exc}") from exc

    def stats(self):
        return {"schema_name": self.schema_name, "schema_sha256": self.schema_sha256,
                "prompt_tokens_skipped": self.prompt_tokens,
                "generated_tokens_consumed": self.generated_tokens_consumed,
                "logits_callbacks": self.callback_count,
                "accepting": bool(self.matcher.is_accepting()),
                "stop_reason": self.matcher.stop_reason()}


class JSONGrammar:
    """Compile once against the already loaded local tokenizer, match per call."""

    def __init__(self, tokenizer, vocab_size, schemas=None):
        try:
            version = importlib.metadata.version("llguidance")
        except importlib.metadata.PackageNotFoundError as exc:
            raise StructuredDecodingError("Install requirements-structured.txt to enable JSON grammar") from exc
        if version != ENGINE_VERSION:
            raise StructuredDecodingError(f"Expected llguidance=={ENGINE_VERSION}, found {version}")
        # These imports are deliberately behind explicit live-backend construction.
        from llguidance import LLMatcher
        from llguidance.hf import from_tokenizer

        eos_ids = sorted(tokenizer.eos_token_ids)
        if not eos_ids or any(type(t) is not int or not 0 <= t < vocab_size for t in eos_ids):
            raise StructuredDecodingError("Tokenizer must expose valid MLX end-of-sequence token IDs")
        hf_tokenizer = getattr(tokenizer, "_tokenizer", tokenizer)
        self.tokenizer = from_tokenizer(hf_tokenizer, n_vocab=vocab_size, eos_token=eos_ids)
        self.matcher_type = LLMatcher
        self.vocab_size = vocab_size
        if schemas is not None and (not isinstance(schemas, dict) or "generic" in schemas
                or any(not isinstance(name, str) or not name or not isinstance(schema, dict)
                       for name, schema in schemas.items())):
            raise StructuredDecodingError("Named schemas must be objects and cannot replace generic")
        # Copy JSON data so outside mutation cannot alter the recorded contract.
        self.schemas = json.loads(json.dumps({"generic": OBJECT_SCHEMA, **(schemas or {})}))
        self.grammars = {name: LLMatcher.grammar_from_json_schema(schema, overrides=COMPILER_OPTIONS)
                         for name, schema in self.schemas.items()}
        self.grammar = self.grammars["generic"]
        schema_records = {}
        # LLMatcher reports grammar/resource errors in state, not necessarily by raising.
        for name, schema in self.schemas.items():
            probe = self._new_matcher(name)
            warnings = probe.get_grammar_warnings()
            if warnings:
                raise StructuredDecodingError(f"JSON grammar {name} warnings: " + "; ".join(warnings))
            schema_records[name] = {
                "schema": schema,
                "schema_sha256": hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
                "grammar_sha256": hashlib.sha256(self.grammars[name].encode()).hexdigest(),
            }
        self.provenance = {
            "enabled": True, "engine": "llguidance", "version": version,
            "mode": "named_json_schemas" if schemas else "json_object", "schema": OBJECT_SCHEMA.copy(),
            "schemas": schema_records,
            "compiler_options": COMPILER_OPTIONS.copy(),
            "grammar_sha256": hashlib.sha256(self.grammar.encode()).hexdigest(),
            "vocab_size": vocab_size, "eos_token_ids": eos_ids,
            "parser_limits": "llguidance 1.9.1 defaults; errors fail closed",
            "prompt_handling": "skip first callback history; consume one completion token per callback",
            "completion_policy": "stop, accepting grammar, strict JSON object; reject truncation/duplicate keys",
            "fallback": "none", "output_repair": False,
        }

    def _new_matcher(self, schema_name="generic"):
        if schema_name not in self.grammars:
            raise StructuredDecodingError(f"Unknown response schema: {schema_name}")
        matcher = self.matcher_type(self.tokenizer, self.grammars[schema_name], log_level=0)
        if matcher.is_error():
            raise StructuredDecodingError(f"Cannot initialize JSON grammar: {matcher.get_error()}")
        return matcher

    def new_processor(self, apply_mask=None, schema_name="generic"):
        matcher = self._new_matcher(schema_name)
        if apply_mask is None:
            import numpy as np
            from llguidance.mlx import apply_token_bitmask

            def apply_mask(logits, mask_bytes):
                # LLGuidance's public MLX adapter sets disallowed logits to -inf.
                mask = np.frombuffer(mask_bytes, dtype="<i4").reshape(1, -1)
                return apply_token_bitmask(logits, mask)

        return JSONLogitsProcessor(matcher, self.vocab_size, apply_mask, schema_name=schema_name,
            schema_sha256=self.provenance["schemas"][schema_name]["schema_sha256"])
