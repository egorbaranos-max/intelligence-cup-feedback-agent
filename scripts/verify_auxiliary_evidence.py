#!/usr/bin/env python3
"""Check saved smoke-evidence bytes and historical sources; never execute them.

This is a consistency check, not proof that a recorded execution occurred or
that the model understood its input correctly. Current source may differ from
the exact historical source-snapshot without invalidating old evidence.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


BUNDLES = {
    "experiments/structured-decoding": "structured-decoding-integration-evidence",
    "experiments/structured-stage-schemas": "named-stage-schema-integration-evidence",
}


def safe_path(root, name):
    """Accept portable relative names and prohibit escape through symlinks."""
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("invalid relative path")
    relative = PurePosixPath(name)
    if not relative.parts or relative.is_absolute() or relative.as_posix() != name or any(
            part in (".", "..") for part in relative.parts):
        raise ValueError("unsafe relative path")
    root = Path(root).resolve()
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root):
        raise ValueError("path escapes evidence directory")
    return path


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest key")
        result[key] = value
    return result


def load_manifest(path):
    raw = path.read_bytes()
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    if not isinstance(result, dict):
        raise ValueError("manifest must be an object")
    return result, hashlib.sha256(raw).hexdigest()


def checked_hash(path, expected, byte_count=None):
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("invalid SHA-256 declaration")
    data = path.read_bytes()
    if byte_count is not None and len(data) != byte_count:
        raise ValueError("declared byte count differs")
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("declared SHA-256 differs")


def required_mapping(manifest, key):
    mapping = manifest.get(key)
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError(f"{key} must be a nonempty object")
    return mapping


def verify_bundle(root, relative, expected_kind):
    result = {"path": relative, "manifest_sha256": None, "files_checked": 0,
              "sources_checked": 0, "legacy_snapshot_files_checked": 0, "errors": []}
    errors = result["errors"]
    try:
        bundle = safe_path(root, relative)
        manifest, result["manifest_sha256"] = load_manifest(safe_path(bundle, "manifest.json"))
        if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1 or manifest.get("kind") != expected_kind:
            raise ValueError("unexpected manifest schema or kind")
        files = required_mapping(manifest, "files")
        sources = required_mapping(manifest, "source_sha256")
    except (OSError, ValueError, TypeError) as error:
        errors.append(f"manifest: {error}")
        result["passed"] = False
        return result

    for name, declaration in files.items():
        try:
            if not isinstance(declaration, dict):
                raise ValueError("file declaration must be an object")
            count = declaration.get("bytes")
            if type(count) is not int or count < 0:
                raise ValueError("invalid byte count declaration")
            checked_hash(safe_path(bundle, name), declaration.get("sha256"), count)
            result["files_checked"] += 1
        except (OSError, ValueError, TypeError) as error:
            errors.append(f"file {name!r}: {error}")

    try:
        snapshot = safe_path(bundle, "source-snapshot")
    except ValueError as error:
        errors.append(f"historical source directory: {error}")
        result["passed"] = False
        return result
    for name, expected in sources.items():
        try:
            checked_hash(safe_path(snapshot, name), expected)
            result["sources_checked"] += 1
        except (OSError, ValueError, TypeError) as error:
            errors.append(f"historical source {name!r}: {error}")

    # The first snapshot also preserved two flat-named files and its own
    # manifest. Retain and check these; the full six-file snapshot is additive.
    try:
        legacy = safe_path(snapshot, "manifest.json")
        if legacy.exists():
            legacy_manifest, result["legacy_snapshot_manifest_sha256"] = load_manifest(legacy)
            for name, expected in required_mapping(legacy_manifest, "sha256").items():
                checked_hash(safe_path(snapshot, name), expected)
                result["legacy_snapshot_files_checked"] += 1
    except (OSError, ValueError, TypeError) as error:
        errors.append(f"legacy snapshot: {error}")
    result["passed"] = not errors
    return result


def verify(root):
    bundles = [verify_bundle(root, relative, kind) for relative, kind in BUNDLES.items()]
    return {"schema": "auxiliary-evidence-audit-v1", "passed": all(item["passed"] for item in bundles),
            "scope": "manifest consistency only; no code execution, model accuracy or execution attestation",
            "bundles": bundles}


def main():
    result = verify(Path(__file__).resolve().parents[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
