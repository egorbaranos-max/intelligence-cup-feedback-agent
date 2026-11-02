"""Download public weights, never send case data. Use a task-local cache."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--revision", help="Commit SHA; omit only to resolve the first experiment")
    args = parser.parse_args()
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HOME"] = str(args.cache.resolve() / "hf-home")
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    from huggingface_hub import HfApi, snapshot_download
    model_id = "Qwen/Qwen3-4B-MLX-4bit"
    info = HfApi().model_info(model_id, revision=args.revision, token=False)
    revision = info.sha
    print(json.dumps({"model_id": model_id, "revision": revision}), flush=True)
    path = Path(snapshot_download(
        repo_id=model_id, revision=revision, cache_dir=args.cache, token=False,
        allow_patterns=["*.json", "*.safetensors", "tokenizer.model", "README.md", "LICENSE*"],
    ))
    files = {}
    for item in sorted(path.iterdir()):
        if item.is_file():
            digest = hashlib.sha256()
            with item.open("rb") as f:
                for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
                    digest.update(chunk)
            files[item.name] = {"sha256": digest.hexdigest(), "bytes": item.stat().st_size}
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps({"model_id": model_id, "revision": revision,
        "local_path": str(path.resolve()), "files": files}, ensure_ascii=False, indent=2) + "\n")
    print(f"Downloaded {sum(f['bytes'] for f in files.values()) / 1e9:.3f} GB; manifest: {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
