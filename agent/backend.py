"""Optional local MLX backend. Importing the pipeline never loads these packages."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import time


def verify_model_manifest(manifest_path):
    """Verify the complete flat snapshot before importing any ML runtime.

Hugging Face snapshot files are normally symlinks into its content-addressed
cache, so file symlinks are supported. Their resolved contents are hashed.
This verifies local reproducibility, not the trustworthiness of model weights.
"""
    manifest = json.loads(Path(manifest_path).read_text())
    if not isinstance(manifest, dict):
        raise ValueError("Model manifest must be an object")
    if not isinstance(manifest.get("revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", manifest["revision"]):
        raise ValueError("Model manifest must pin a full commit SHA")
    if not isinstance(manifest.get("model_id"), str) or not manifest["model_id"].strip():
        raise ValueError("Model manifest requires model_id")
    if not isinstance(manifest.get("local_path"), str):
        raise ValueError("Model manifest requires local_path")
    model_path = Path(manifest["local_path"])
    if not model_path.is_absolute() or not model_path.is_dir():
        raise ValueError("Downloaded model directory must exist at an absolute path")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Model manifest requires a nonempty file inventory")
    for name, expected in files.items():
        if (not isinstance(name, str) or not name or name in {".", ".."}
                or "/" in name or "\\" in name or Path(name).is_absolute()):
            raise ValueError("Model manifest file names must be flat basenames")
        if (not isinstance(expected, dict) or set(expected) != {"sha256", "bytes"}
                or type(expected["bytes"]) is not int or expected["bytes"] < 0
                or not isinstance(expected["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected["sha256"])):
            raise ValueError(f"Invalid hash or size entry: {name}")
    names = set(files)
    if not {"config.json", "tokenizer_config.json"}.issubset(names):
        raise ValueError("Model configuration and tokenizer configuration are required")
    if not names.intersection({"tokenizer.json", "tokenizer.model"}):
        raise ValueError("A local tokenizer file is required")
    if not any(name.endswith(".safetensors") and files[name]["bytes"] > 0 for name in names):
        raise ValueError("Nonempty local safetensors weights are required")
    entries = list(model_path.iterdir())
    if any(not item.is_file() for item in entries) or {item.name for item in entries} != names:
        raise ValueError("Model snapshot file set does not match the manifest")
    for name, expected in files.items():
        file = model_path / name
        digest = hashlib.sha256()
        with file.open("rb") as f:
            for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        if file.stat().st_size != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
            raise ValueError(f"Downloaded file hash mismatch: {name}")
    return manifest, model_path


class LocalMLX:
    def __init__(self, manifest_path, seed=42, structured_json=True):
        # Inference must use downloaded files only; no implicit hub fallback/token.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
        manifest, model_path = verify_model_manifest(manifest_path)
        import mlx.core as mx
        from mlx_lm import load, stream_generate
        from mlx_lm.sample_utils import make_sampler
        self.mx, self.stream_generate = mx, stream_generate
        self.model, self.tokenizer = load(str(model_path), tokenizer_config={"trust_remote_code": False})
        self.seed, self.calls = seed, 0
        self.sampler = make_sampler(temp=0.7, top_p=0.8, top_k=20)
        self.json_grammar = None
        if structured_json:
            from .structured import JSONGrammar
            from .response_schemas import RESPONSE_SCHEMAS
            config = json.loads((model_path / "config.json").read_text())
            self.json_grammar = JSONGrammar(self.tokenizer, config["vocab_size"], schemas=RESPONSE_SCHEMAS)
        self.provenance = {k: v for k, v in manifest.items() if k != "local_path"}
        self.provenance.update({"backend": "mlx-lm", "python": platform.python_version(),
            "machine": platform.machine(), "macos": platform.mac_ver()[0],
            "packages": {p: importlib.metadata.version(p) for p in
                ("mlx", "mlx-lm", "transformers", "huggingface-hub", "safetensors")},
            "decoding": {"temperature": 0.7, "top_p": 0.8, "top_k": 20,
                         "seed": seed, "per_call_seed": "seed + zero-based call index",
                         "enable_thinking": False},
            "inference_network": "HF offline flags; local model directory; no network client in backend"})
        self.provenance["decoding"]["structured_json"] = (
            self.json_grammar.provenance if self.json_grammar else {"enabled": False})
        if self.json_grammar:
            self.provenance["packages"]["llguidance"] = importlib.metadata.version("llguidance")

    def generate(self, messages, max_tokens=1200, schema_name="generic"):
        self.mx.random.seed(self.seed + self.calls)
        self.calls += 1
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False,
                    add_generation_prompt=True, enable_thinking=False)
        started = datetime.now(timezone.utc).isoformat()
        begin = time.perf_counter()
        parts, last, processor = [], None, None

        def generation_stats():
            stats = {"started_at": started, "elapsed_seconds": round(time.perf_counter() - begin, 3),
                     "max_tokens": max_tokens, "seed": self.seed + self.calls - 1,
                     "response_schema": schema_name,
                     "rendered_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
            if last is not None:
                for name in ("prompt_tokens", "generation_tokens", "prompt_tps", "generation_tps",
                             "peak_memory", "finish_reason"):
                    value = getattr(last, name, None)
                    if isinstance(value, (str, int, float)) or value is None:
                        stats[name] = value
            if processor is not None:
                stats["structured_json"] = processor.stats()
            return stats

        try:
            kwargs = {}
            if self.json_grammar:
                processor = self.json_grammar.new_processor(schema_name=schema_name)
                kwargs["logits_processors"] = [processor]
            for item in self.stream_generate(self.model, self.tokenizer, prompt=prompt,
                                            max_tokens=max_tokens, sampler=self.sampler, **kwargs):
                parts.append(item.text)
                last = item
            raw = "".join(parts)
            if processor is not None:
                processor.finish(raw, getattr(last, "finish_reason", None))
            return raw, generation_stats()
        except Exception as exc:
            # Preserve the exact prefix already emitted by MLX, including on a
            # grammar/resource/truncation failure. Never return it as successful.
            from .structured import StructuredDecodingError
            error = exc if isinstance(exc, StructuredDecodingError) else StructuredDecodingError(str(exc))
            error.raw_response = "".join(parts)
            error.stats = generation_stats()
            if error is exc:
                raise
            raise error from exc
