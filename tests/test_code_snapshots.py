import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.verify_code_snapshots import digest, verify


class CodeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "experiments/code-snapshots"
        self.folder.mkdir(parents=True)
        self.run = self.root / "experiments/synthetic/runs/run-01"
        self.run.mkdir(parents=True)
        self.source = b'print("sample")\n'
        self.files = {"agent/example.py": digest(self.source)}
        (self.root / "experiments/recorded-runs.json").write_text(json.dumps({"runs": ["synthetic/runs/run-01"]}))
        (self.run / "manifest.json").write_text(json.dumps({"pipeline_version": "text-example", "code_sha256": self.files}))
        self.write_archive()

    def write_archive(self, source=None, extra=False):
        path = self.folder / "text-example.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("agent/example.py", self.source if source is None else source)
            if extra:
                zf.writestr("unexpected.py", b"pass\n")
        self.index = {"schema_version": 1, "snapshots": [{"pipeline_version": "text-example",
            "archive": path.name, "sha256": digest(path.read_bytes()), "files": self.files,
            "runs": ["synthetic/runs/run-01"]}]}
        self.save_index()

    def save_index(self):
        (self.folder / "index.json").write_text(json.dumps(self.index))

    def test_exact_archive_matches_recorded_code(self):
        self.assertEqual(verify(self.root), 1)

    def test_altered_source_rejected_even_if_archive_hash_updated(self):
        self.write_archive(source=b'print("altered")\n')
        with self.assertRaisesRegex(ValueError, "source file hash"):
            verify(self.root)

    def test_missing_run_mapping_rejected(self):
        self.index["snapshots"] = []
        self.save_index()
        with self.assertRaisesRegex(ValueError, "every registered run"):
            verify(self.root)

    def test_extra_archive_member_rejected(self):
        self.write_archive(extra=True)
        with self.assertRaisesRegex(ValueError, "inventory"):
            verify(self.root)

    def test_run_source_manifest_change_rejected(self):
        (self.run / "manifest.json").write_text(json.dumps({"pipeline_version": "text-example", "code_sha256": {"agent/example.py": "0" * 64}}))
        with self.assertRaisesRegex(ValueError, "run manifest"):
            verify(self.root)

    def test_duplicate_mapping_rejected(self):
        self.index["snapshots"][0]["runs"] *= 2
        self.save_index()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            verify(self.root)

    def test_archive_path_escape_rejected(self):
        self.index["snapshots"][0]["archive"] = "../outside.zip"
        self.save_index()
        with self.assertRaisesRegex(ValueError, "archive name"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
