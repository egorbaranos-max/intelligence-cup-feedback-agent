"""Stdlib lifecycle tests; optional native CFG tests run when llguidance is installed."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent.backend import LocalMLX
from agent.structured import (COMPILER_OPTIONS, ENGINE_VERSION, JSONGrammar,
                              JSONLogitsProcessor, StructuredDecodingError)


class Scalar(int):
    def item(self):
        return int(self)


class Tokens(list):
    @property
    def shape(self):
        return (len(self),)

    def __getitem__(self, key):
        return Scalar(super().__getitem__(key))


class FakeMatcher:
    """Tiny genuine state machine for {}, with EOS token 3 and no resets."""
    def __init__(self):
        self.seen = []
        self.error = ""
        self.mask_error = False
        self.override_mask = None

    def is_error(self):
        return bool(self.error)

    def get_error(self):
        return self.error

    def is_accepting(self):
        return self.seen[:2] == [1, 2]

    def stop_reason(self):
        return "NoExtension" if self.is_accepting() else "NotStopped"

    def consume_token(self, token):
        wanted = [1, 2][len(self.seen)] if len(self.seen) < 2 else 3
        if token != wanted:
            self.error = "invalid token"
            return False
        self.seen.append(token)
        return True

    def compute_bitmask(self):
        if self.mask_error:
            self.error = "resource limit"
        if self.override_mask is not None:
            return self.override_mask
        token = [1, 2][len(self.seen)] if len(self.seen) < 2 else 3
        return (1 << token).to_bytes(4, "little")


def fake_processor(matcher=None):
    return JSONLogitsProcessor(matcher or FakeMatcher(), 8, lambda logits, mask: mask)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.logits = SimpleNamespace(shape=(1, 8))

    def call(self, processor, tokens):
        return processor(Tokens(tokens), self.logits)

    def test_skip_entire_prompt_and_mlx_lookahead_including_eos(self):
        p = fake_processor()
        self.assertEqual(self.call(p, [7, 6, 5]), b'\x02\0\0\0')
        self.assertEqual(p.matcher.seen, [])
        self.call(p, [7, 6, 5, 1])
        self.call(p, [7, 6, 5, 1, 2])
        self.call(p, [7, 6, 5, 1, 2, 3])
        # MLX may compute next logits before noticing EOS in stream_generate.
        self.assertEqual(self.call(p, [7, 6, 5, 1, 2, 3, 3]), b'\x08\0\0\0')
        p.finish('{}', 'stop')
        self.assertEqual(p.stats()['prompt_tokens_skipped'], 3)
        self.assertEqual(p.matcher.seen, [1, 2, 3, 3])

    def test_prompt_is_never_validated_as_json(self):
        p = fake_processor()
        self.call(p, [1, 2, 3, 9999])
        self.assertEqual(p.matcher.seen, [])

    def test_new_processor_has_independent_state(self):
        a, b = fake_processor(), fake_processor()
        self.call(a, [7]); self.call(a, [7, 1])
        self.call(b, [7])
        self.assertEqual(b.matcher.seen, [])
        self.assertEqual(a.matcher.seen, [1])

    def test_wrong_token_fails_without_reset(self):
        p = fake_processor(); self.call(p, [7])
        with self.assertRaisesRegex(StructuredDecodingError, 'invalid token'):
            self.call(p, [7, 3])
        with self.assertRaises(StructuredDecodingError):
            self.call(p, [7, 1])
        self.assertTrue(p.matcher.is_error())

    def test_history_rewind_jump_or_replacement_fails(self):
        for history in ([7], [7, 1, 2], [6, 1]):
            with self.subTest(history=history):
                p = fake_processor(); self.call(p, [7])
                with self.assertRaises(StructuredDecodingError):
                    self.call(p, history)

    def test_invalid_dimensions_and_oov_fail(self):
        for shape in ((8,), (2, 8), (1, 9)):
            with self.assertRaises(StructuredDecodingError):
                fake_processor()(Tokens([7]), SimpleNamespace(shape=shape))
        p = fake_processor(); self.call(p, [7])
        with self.assertRaises(StructuredDecodingError):
            self.call(p, [7, 99])

    def test_constructor_and_mask_resource_errors_fail_closed(self):
        m = FakeMatcher(); m.error = 'bad grammar'
        with self.assertRaises(StructuredDecodingError):
            fake_processor(m)
        m = FakeMatcher(); m.mask_error = True
        with self.assertRaisesRegex(StructuredDecodingError, 'resource limit'):
            self.call(fake_processor(m), [7])

    def test_empty_malformed_and_padding_only_masks_fail(self):
        for mask in (b'', b'\0' * 4, b'\0\0\0\x80', bytearray(b'\2\0\0\0')):
            m = FakeMatcher(); m.override_mask = mask
            with self.subTest(mask=mask), self.assertRaises(StructuredDecodingError):
                self.call(fake_processor(m), [7])

    def completed(self):
        p = fake_processor()
        self.call(p, [7]); self.call(p, [7, 1]); self.call(p, [7, 1, 2])
        return p

    def test_finish_rejects_truncation_even_if_raw_happens_to_be_valid(self):
        for reason in ('length', None, 'error'):
            with self.assertRaises(StructuredDecodingError):
                self.completed().finish('{}', reason)

    def test_finish_rejects_incomplete_or_unstarted_matcher(self):
        p = fake_processor()
        with self.assertRaises(StructuredDecodingError): p.finish('{}', 'stop')
        self.call(p, [7])
        with self.assertRaises(StructuredDecodingError): p.finish('{}', 'stop')

    def test_final_json_validation_never_extracts_or_repairs(self):
        for raw in ('prefix {}', '```json\n{}\n```', '{} {}', '[]', '{',
                    '{"x":NaN}', '{"x":1,"x":2}'):
            with self.subTest(raw=raw), self.assertRaises(StructuredDecodingError):
                self.completed().finish(raw, 'stop')
        original = ' { "a": "\\u0410", "x": [true, null, 1.25e-3] } '
        self.completed().finish(original, 'stop')
        self.assertIn('\\u0410', original)

    def test_import_does_not_import_optional_packages(self):
        code = ('import sys; import agent.structured; import agent.backend; '
                'assert not any(p in sys.modules for p in ("mlx", "llguidance", "numpy", "torch"))')
        subprocess.run([sys.executable, '-c', code], check=True, cwd=Path(__file__).resolve().parents[1])

    def test_unpinned_engine_version_rejected_before_runtime_import(self):
        with patch('agent.structured.importlib.metadata.version', return_value='0.0.0'):
            with self.assertRaisesRegex(StructuredDecodingError, ENGINE_VERSION):
                JSONGrammar(None, 8)


class BackendRawLoggingTests(unittest.TestCase):
    def backend(self, stream, finish_failure=False):
        backend = LocalMLX.__new__(LocalMLX)
        backend.seed, backend.calls = 42, 0
        backend.mx = SimpleNamespace(random=SimpleNamespace(seed=lambda seed: None))
        backend.tokenizer = SimpleNamespace(apply_chat_template=lambda *a, **kw: 'original prompt')
        backend.model, backend.sampler = object(), object()
        backend.stream_generate = stream
        def finish(raw, reason):
            if finish_failure:
                raise StructuredDecodingError('truncated')
        processor = SimpleNamespace(finish=finish, stats=lambda: {'accepting': not finish_failure})
        backend.json_grammar = SimpleNamespace(new_processor=lambda: processor)
        return backend, processor

    def test_success_passes_processor_and_preserves_raw(self):
        seen = {}
        def stream(*args, **kwargs):
            seen.update(kwargs)
            yield SimpleNamespace(text=' {"a":', finish_reason=None)
            yield SimpleNamespace(text='1} ', finish_reason='stop')
        b, p = self.backend(stream)
        raw, stats = b.generate([], max_tokens=12)
        self.assertEqual(raw, ' {"a":1} ')
        self.assertEqual(seen['prompt'], 'original prompt')
        self.assertEqual(seen['logits_processors'], [p])
        self.assertEqual(stats['finish_reason'], 'stop')
        self.assertEqual(stats['seed'], 42)

    def test_generation_failure_attaches_exact_partial_output(self):
        def stream(*args, **kwargs):
            yield SimpleNamespace(text=' {"x":', finish_reason=None)
            raise RuntimeError('native failure')
        b, _ = self.backend(stream)
        with self.assertRaises(StructuredDecodingError) as caught:
            b.generate([])
        self.assertEqual(caught.exception.raw_response, ' {"x":')
        self.assertIn('rendered_prompt_sha256', caught.exception.stats)
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)

    def test_finish_failure_attaches_full_unmodified_text(self):
        def stream(*args, **kwargs):
            yield SimpleNamespace(text='{}', finish_reason='length')
        b, _ = self.backend(stream, finish_failure=True)
        with self.assertRaises(StructuredDecodingError) as caught:
            b.generate([])
        self.assertEqual(caught.exception.raw_response, '{}')
        self.assertEqual(caught.exception.stats['finish_reason'], 'length')

    def test_runner_retains_raw_and_stats_when_backend_raises(self):
        from agent.runner import run
        class FailingBackend:
            provenance = {'backend': 'test double; no model'}
            def generate(self, messages, max_tokens):
                exc = StructuredDecodingError('grammar resource limit')
                exc.raw_response = ' {"partial":'
                exc.stats = {'max_tokens': max_tokens, 'structured_json': {'accepting': False}}
                raise exc
        with tempfile.TemporaryDirectory() as tmp:
            inputs = Path(tmp) / 'input.jsonl'
            inputs.write_text(json.dumps({'id': 'grammar-error-test', 'product_id': 'fixture',
                                          'text': 'Тест.', 'speaker': 'user'}) + '\n')
            output = Path(tmp) / 'run'
            with self.assertRaises(StructuredDecodingError):
                run(inputs, output, FailingBackend(), '2026-11-02T12:00:00Z')
            call = json.loads((output / 'calls.jsonl').read_text())
            self.assertEqual(call['status'], 'failed')
            self.assertEqual(call['raw_response'], ' {"partial":')
            self.assertFalse(call['stats']['structured_json']['accepting'])


@unittest.skipUnless(importlib.util.find_spec('llguidance'), 'optional native grammar dependency')
class NativeGrammarTests(unittest.TestCase):
    """Use byte tokens to test split UTF-8; no model, MLX, Torch, or network."""
    @classmethod
    def setUpClass(cls):
        from llguidance import LLTokenizer, TokenizerWrapper, LLMatcher
        class ByteTokenizer:
            eos_token_id = 256
            bos_token_id = None
            tokens = [bytes([n]) for n in range(256)] + [b'<eos>']
            special_token_ids = [256]
            def __call__(self, value):
                return list(value if isinstance(value, bytes) else value.encode())
        cls.tokenizer = LLTokenizer(TokenizerWrapper(ByteTokenizer()), eos_token=256)
        cls.grammar = LLMatcher.grammar_from_json_schema({'type': 'object'}, overrides=COMPILER_OPTIONS)
        cls.matcher_type = LLMatcher

    def processor(self):
        m = self.matcher_type(self.tokenizer, self.grammar, log_level=0)
        return JSONLogitsProcessor(m, 257, lambda logits, mask: mask)

    def test_nested_objects_split_utf8_and_unicode_escapes(self):
        examples = ['{}', '{"a":"Ж😀","b":"\\u0410\\uD83D\\uDE00"}',
                    '{"a":' + '[' * 20 + '{"b":true}' + ']' * 20 + '}',
                    '{\n "a"\t:\r [null, false, -12.5e+2], "b": {}\n}']
        for raw in examples:
            with self.subTest(raw=raw):
                p = self.processor(); history = Tokens([111, 256])
                logits = SimpleNamespace(shape=(1, 257))
                mask = p(history, logits)
                for token in raw.encode():
                    self.assertTrue(mask[token // 8] & (1 << (token % 8)))
                    history.append(token); mask = p(history, logits)
                self.assertTrue(mask[32] & 1, 'EOS must be allowed after complete object')
                history.append(256); p(history, logits)
                p.finish(raw, 'stop')

    def test_invalid_json_cannot_be_selected(self):
        for raw in ('[]', '{"x":NaN}', '{"x":undefined}', '{} trailing', '{"x":"\\q"}'):
            p = self.processor(); history = Tokens([111]); logits = SimpleNamespace(shape=(1, 257))
            mask = p(history, logits); blocked = False
            for token in raw.encode():
                if not mask[token // 8] & (1 << (token % 8)):
                    blocked = True; break
                history.append(token); mask = p(history, logits)
            self.assertTrue(blocked, raw)

    def test_eos_masked_until_complete_and_invalid_grammar_detected(self):
        p = self.processor(); history = Tokens([111]); logits = SimpleNamespace(shape=(1, 257))
        for token in b'{"x":[':
            mask = p(history, logits)
            self.assertFalse(mask[32] & 1)
            history.append(token)
        mask = p(history, logits); self.assertFalse(mask[32] & 1)
        m = self.matcher_type(self.tokenizer, 'invalid grammar', log_level=0)
        with self.assertRaises(StructuredDecodingError):
            JSONLogitsProcessor(m, 257, lambda a, b: b)


@unittest.skipUnless(os.environ.get('STRUCTURED_TOKENIZER_MANIFEST'),
                     'set STRUCTURED_TOKENIZER_MANIFEST for local Qwen tokenizer tests')
class LocalQwenTokenizerTests(unittest.TestCase):
    """CPU only: actual cached Qwen BPE tokens, all configured EOS, padded vocab.

    Run from the repository with the live interpreter and an absolute local model
    manifest path in STRUCTURED_TOKENIZER_MANIFEST. No weights are loaded.
    """
    @classmethod
    def setUpClass(cls):
        from transformers import AutoTokenizer
        manifest = json.loads(Path(os.environ['STRUCTURED_TOKENIZER_MANIFEST']).read_text())
        model_path = Path(manifest['local_path'])
        config = json.loads((model_path / 'config.json').read_text())
        generation_path = model_path / 'generation_config.json'
        generation = json.loads(generation_path.read_text()) if generation_path.exists() else {}
        cls.hf = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True,
                                              trust_remote_code=False)
        eos = generation.get('eos_token_id', config.get('eos_token_id', cls.hf.eos_token_id))
        cls.eos = sorted(eos if isinstance(eos, list) else [eos])
        cls.vocab_size = config['vocab_size']
        wrapper = SimpleNamespace(_tokenizer=cls.hf, eos_token_ids=set(cls.eos))
        cls.factory = JSONGrammar(wrapper, cls.vocab_size)

    def new(self):
        p = self.factory.new_processor(apply_mask=lambda logits, mask: mask)
        prompt = self.hf.encode('User prompt is not JSON. </think>', add_special_tokens=False)
        return p, Tokens(prompt), SimpleNamespace(shape=(1, self.vocab_size))

    def test_actual_qwen_tokens_nested_unicode_and_multiple_fresh_calls(self):
        for raw in ('{}', '{"x":"\\u0410\\uD83D\\uDE00","q":"Ж 😀"}',
                    '{"x":' + '[' * 20 + '{"deep":null}' + ']' * 20 + '}',
                    json.dumps({'a': [True, False, -3.4e2], 'b': 'escaped " quote'}, indent=2)):
            with self.subTest(raw=raw):
                p, history, logits = self.new()
                mask = p(history, logits)
                for eos in self.eos:
                    self.assertFalse(mask[eos // 8] & (1 << (eos % 8)))
                for token in self.hf.encode(raw, add_special_tokens=False):
                    self.assertTrue(mask[token // 8] & (1 << (token % 8)))
                    self.assertFalse(any(mask[t // 8] & (1 << (t % 8))
                                         for t in range(len(self.hf), self.vocab_size)))
                    history.append(token); mask = p(history, logits)
                for eos in self.eos:
                    self.assertTrue(mask[eos // 8] & (1 << (eos % 8)))
                history.append(self.eos[-1]); p(history, logits)
                p.finish(raw, 'stop')

    def test_actual_qwen_rejects_invalid_root_nan_and_extra_text(self):
        for raw in ('[]', '{"x":NaN}', '{} trailing'):
            p, history, logits = self.new(); mask = p(history, logits); blocked = False
            for token in self.hf.encode(raw, add_special_tokens=False):
                if not mask[token // 8] & (1 << (token % 8)):
                    blocked = True; break
                history.append(token); mask = p(history, logits)
            self.assertTrue(blocked, raw)


if __name__ == '__main__':
    unittest.main()
