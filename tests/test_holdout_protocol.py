"""Synthetic metadata tests; no model, labels or real-run contents are modified."""
import json
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.verify_holdout_protocol import digest, main, verify, utc_stamp


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "experiments/holdout_v2"
        self.folder.mkdir(parents=True)
        self.sources = [{"id": f"fixture-{i}"} for i in range(48)]
        (self.folder / "inputs.jsonl").write_text("".join(json.dumps(s) + "\n" for s in self.sources))
        self.write(self.folder / "expectations.json", {"fixture": "no semantic labels"})
        files = ["agent/pipeline.py", "demo/case_contract_demo.py", "scripts/evaluate_live_run.py"]
        for name in files:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# synthetic protocol-test source\n")
        code = {name: digest(self.root / name) for name in files}
        self.models = {name: {"model_id": "TEST_ONLY_" + name, "revision": "a" * 40,
            "decoding": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "seed": 42,
                         "per_call_seed": "seed + zero-based call index", "enable_thinking": False},
            "files": {"fixture.json": {"sha256": "b" * 64, "bytes": 1}}} for name in ("4B", "8B")}
        self.baseline = {"agent/pipeline.py": "c" * 64, "demo/case_contract_demo.py": "d" * 64}
        self.write(self.root / "experiments/live_qwen/runs/run-03/manifest.json",
                   {"model": self.models["4B"], "code_sha256": self.baseline})
        self.write(self.root / "experiments/fresh_probe/runs/run-05/manifest.json",
                   {"model": self.models["8B"], "code_sha256": code})
        self.protocol = {"recorded_before_inference_at_utc": "2026-11-02T12:00:00Z",
            "candidate_commit": "fixture-candidate", "baseline_commit": "fixture-baseline",
            "as_of": "2026-11-02T12:00:00Z", "code_sha256": code,
            "data_sha256": {name: digest(self.folder / name) for name in ("inputs.jsonl", "expectations.json")},
            "models": {key: {k: self.models[name][k] for k in ("model_id", "revision")}
                for name, key in (("4B", "live-qwen-model.json"), ("8B", "live-qwen-8b-model.json"))},
            "runs": [{"path": f"runs/run-{n:02d}", "model": model, "role": f"fixture role {n}"}
                     for n, model in enumerate(("4B", "4B", "8B"), 1)]}
        self.manifests = []
        for n, model in enumerate(("4B", "4B", "8B"), 1):
            folder = self.folder / f"runs/run-{n:02d}"
            folder.mkdir(parents=True)
            for name in ("calls.jsonl", "cards.json", "local-receiver.json"):
                (folder / name).write_text("[]\n")
            (folder / "results.jsonl").write_text("".join(json.dumps({"source_id": s["id"]}) + "\n" for s in self.sources))
            manifest = {"status": "complete", "source_count": 48,
                "inputs_sha256": self.protocol["data_sha256"]["inputs.jsonl"],
                "pre_run_artifact_sha256": {"expectations.json": self.protocol["data_sha256"]["expectations.json"]},
                "as_of": self.protocol["as_of"], "model": self.models[model],
                "code_sha256": self.baseline if n == 1 else {k: v for k, v in code.items() if not k.startswith("scripts/")},
                "started_at": f"2026-11-02T12:0{n * 2 - 1}:00Z", "finished_at": f"2026-11-02T12:0{n * 2}:00Z",
                "output_sha256": {p.name: digest(p) for p in folder.iterdir()}}
            self.manifests.append(manifest)
            self.write(folder / "manifest.json", manifest)
        self.write(self.folder / "protocol.json", self.protocol)
        self.frozen_hash = digest(self.folder / "protocol.json")

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def audit(self):
        return verify(self.root, expected_protocol_sha=self.frozen_hash)

    def save_run(self, index):
        self.write(self.folder / f"runs/run-{index + 1:02d}/manifest.json", self.manifests[index])

    def test_offline_zip_without_git_is_supported(self):
        report = self.audit()
        self.assertEqual(report["status"], "verified")
        self.assertEqual(len(report["runs"]), 3)
        self.assertEqual(report["git_evidence"]["status"], "not_available")
        self.assertTrue(all(row["source_order_matches"] for row in report["runs"]))
        self.assertTrue(all(row["recorded_generation_matches_prior_reference"] for row in report["runs"]))

    def test_cli_creates_output_directory_and_never_overwrites_report(self):
        target = self.root / 'new-artifacts/protocol.json'
        report = self.audit()
        with patch('sys.argv', ['verify_holdout_protocol.py', '--output', str(target)]), \
                patch('scripts.verify_holdout_protocol.verify', return_value=report), \
                contextlib.redirect_stdout(io.StringIO()):
            main()
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['status'], 'verified')
            with self.assertRaises(FileExistsError):
                main()

    def test_changed_protocol_is_rejected_before_reinterpreting_it(self):
        self.protocol["as_of"] = "2026-11-01T12:00:00Z"
        self.write(self.folder / "protocol.json", self.protocol)
        with self.assertRaisesRegex(ValueError, "pre-inference"):
            self.audit()

    def test_frozen_evaluator_and_runtime_inventory_cannot_change(self):
        self.manifests[1]["code_sha256"]["agent/extra.py"] = "e" * 64
        self.save_run(1)
        with self.assertRaisesRegex(ValueError, "Runtime source inventory"):
            self.audit()
        (self.root / "scripts/evaluate_live_run.py").write_text("changed")
        with self.assertRaisesRegex(ValueError, "evaluator source"):
            self.audit()

    def test_baseline_hashes_are_compared_with_baseline_reference(self):
        self.manifests[0]["code_sha256"] = dict(self.manifests[1]["code_sha256"])
        self.save_run(0)
        with self.assertRaisesRegex(ValueError, "Runtime source inventory"):
            self.audit()

    def test_pre_freeze_or_overlapping_run_fails(self):
        for time in ("2026-11-02T11:59:00Z", "2026-11-02T12:01:59Z"):
            self.manifests[1]["started_at"] = time
            self.save_run(1)
            with self.subTest(time=time), self.assertRaisesRegex(ValueError, "chronology"):
                self.audit()

    def test_changed_model_pin_or_weight_inventory_fails(self):
        self.manifests[2]["model"] = {**self.models["8B"], "revision": "f" * 40}
        self.save_run(2)
        with self.assertRaisesRegex(ValueError, "Pinned model"):
            self.audit()
        self.manifests[2]["model"] = {**self.models["8B"], "files": {"new": {}}}
        self.save_run(2)
        with self.assertRaisesRegex(ValueError, "model-file inventory"):
            self.audit()

    def test_changed_raw_outputs_and_missing_source_are_rejected(self):
        path = self.folder / "runs/run-03/results.jsonl"
        path.write_text(path.read_text().splitlines()[0] + "\n")
        with self.assertRaisesRegex(ValueError, "output hash"):
            self.audit()
        self.manifests[2]["output_sha256"]["results.jsonl"] = digest(path)
        self.save_run(2)
        with self.assertRaisesRegex(ValueError, "all frozen source IDs"):
            self.audit()

    def test_missing_or_unfinished_run_cannot_pass(self):
        self.manifests[2]["status"] = "running"
        self.save_run(2)
        with self.assertRaisesRegex(ValueError, "not complete"):
            self.audit()
        (self.folder / "runs/run-03/manifest.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.audit()

    def test_permuted_source_order_fails_even_with_updated_output_hash(self):
        path = self.folder / "runs/run-02/results.jsonl"
        rows = path.read_text().splitlines()
        rows[0], rows[1] = rows[1], rows[0]
        path.write_text("\n".join(rows) + "\n")
        self.manifests[1]["output_sha256"]["results.jsonl"] = digest(path)
        self.save_run(1)
        with self.assertRaisesRegex(ValueError, "source order"):
            self.audit()

    def test_common_generation_is_compared_with_prior_recorded_settings(self):
        self.manifests[1]["model"] = {**self.models["4B"],
            "decoding": {**self.models["4B"]["decoding"], "seed": 99}}
        self.save_run(1)
        with self.assertRaisesRegex(ValueError, "generation settings"):
            self.audit()
        self.manifests[1]["model"]["decoding"].pop("seed")
        self.save_run(1)
        with self.assertRaisesRegex(ValueError, "generation settings"):
            self.audit()

    def test_naive_timestamp_cannot_be_assumed_utc(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            utc_stamp("2026-11-02T12:00:00")


if __name__ == "__main__":
    unittest.main()
