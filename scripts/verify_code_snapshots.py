"""Verify archived runtime source bytes for every registered model experiment.

Hashes establish consistency with recorded manifests, not independent proof of
who executed a model or that the model understood the source correctly.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_version(manifest):
    # The first two historical runs predate pipeline_version. Do not rewrite
    # their manifests; derive a distinct archive label from their recorded code.
    return manifest.get("pipeline_version") or "legacy-code-" + digest(
        json.dumps(manifest["code_sha256"], sort_keys=True, separators=(",", ":")).encode()
    )[:24]


def verify(root):
    root = Path(root)
    folder = root / "experiments/code-snapshots"
    index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
    if index.get("schema_version") != 1 or not isinstance(index.get("snapshots"), list):
        raise ValueError("Unsupported source snapshot index")
    registered = json.loads((root / "experiments/recorded-runs.json").read_text(encoding="utf-8"))["runs"]
    seen_runs, seen_versions, seen_archives = set(), set(), set()
    for entry in index["snapshots"]:
        version, archive, files, runs = (entry[k] for k in ("pipeline_version", "archive", "files", "runs"))
        if (not isinstance(archive, str) or Path(archive).name != archive
                or not archive.endswith(".zip") or archive in seen_archives):
            raise ValueError("Invalid or duplicate source archive name")
        if not isinstance(version, str) or version in seen_versions:
            raise ValueError("Duplicate source version")
        if not isinstance(files, dict) or not files or not isinstance(runs, list) or not runs:
            raise ValueError("Source snapshot requires files and recorded runs")
        for name in files:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or str(p) != name or not name.endswith(".py"):
                raise ValueError("Unsafe source filename")
        archive_path = folder / archive
        if digest(archive_path.read_bytes()) != entry["sha256"]:
            raise ValueError("Source archive hash mismatch")
        with zipfile.ZipFile(archive_path) as zf:
            infos = zf.infolist()
            if len(infos) != len(files) or {i.filename for i in infos} != set(files):
                raise ValueError("Source archive inventory mismatch")
            for item in infos:
                if item.file_size > 2_000_000 or item.is_dir():
                    raise ValueError("Unexpected source member size/type")
                if digest(zf.read(item)) != files[item.filename]:
                    raise ValueError("Archived source file hash mismatch")
        for run in runs:
            if run not in registered or run in seen_runs:
                raise ValueError("Unknown or duplicate source snapshot run")
            manifest = json.loads((root / "experiments" / run / "manifest.json").read_text(encoding="utf-8"))
            if source_version(manifest) != version or manifest["code_sha256"] != files:
                raise ValueError(f"Source snapshot does not match run manifest: {run}")
            seen_runs.add(run)
        seen_versions.add(version)
        seen_archives.add(archive)
    if seen_runs != set(registered) or len(registered) != len(set(registered)):
        raise ValueError("Not every registered run has exactly one source snapshot")
    actual_archives = {p.name for p in folder.glob("*.zip")}
    if actual_archives != seen_archives:
        raise ValueError("Unindexed or missing source archive")
    return len(seen_versions)


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        count = verify(root)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        raise SystemExit(f"Source snapshot verification failed: {exc}") from exc
    print(f"Verified {count} exact runtime source snapshots for all registered runs.")


if __name__ == "__main__":
    main()
