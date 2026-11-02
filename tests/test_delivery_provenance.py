"""Audit identity must bind real bytes and not a ZIP's enclosing Git checkout."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.verify_delivery import git_evidence, run_check, source_inventory


class DeliveryProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, name, content='fixture'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_inventory_has_relative_paths_and_excludes_reports_model_runs_and_secrets(self):
        included = ['agent/core.py', 'tests/test_core.py', 'scripts/audit.py', 'requirements-live.txt',
                    '.github/workflows/check.yml', '.gitattributes', 'Проверить.command', 'submission/manifest.json',
                    'docs/solution.md']
        for name in included:
            self.put(name)
        for name in ['artifacts/report.json', 'experiments/example/runs/run-01/calls.jsonl',
                     '.env', '.local-models/model.safetensors', 'private.txt']:
            self.put(name, 'not part of audit inventory')
        inventory = source_inventory(self.root)
        self.assertEqual(set(inventory), set(included))
        self.assertTrue(all(value == hashlib.sha256(b'fixture').hexdigest() for value in inventory.values()))
        self.assertTrue(all(not Path(name).is_absolute() for name in inventory))

    def test_changed_bytes_are_detectable_without_git(self):
        path = self.put('agent/core.py', 'before')
        before = source_inventory(self.root)
        path.write_text('after')
        after = source_inventory(self.root)
        self.assertNotEqual(before['agent/core.py'], after['agent/core.py'])
        with patch('scripts.verify_delivery.shutil.which', return_value=None):
            self.assertEqual(git_evidence(self.root), {'git': None, 'reason': 'git_unavailable'})

    def test_child_checks_use_utf8_even_when_parent_environment_disables_it(self):
        (self.root / 'text.txt').write_text('Ия — проверка', encoding='utf-8')
        with patch.dict(os.environ, {'PYTHONUTF8': '0'}):
            result = run_check(['-c', 'from pathlib import Path; import sys; '
                                'print(sys.flags.utf8_mode); print(Path("text.txt").read_text())'], self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['1', 'Ия — проверка'])

    @unittest.skipUnless(shutil.which('git'), 'Git required to test a ZIP nested in another checkout')
    def test_zip_inside_another_git_checkout_does_not_borrow_parent_revision(self):
        subprocess.run(['git', '-C', str(self.root), 'init', '--quiet'], check=True, capture_output=True)
        unpacked = self.root / 'downloaded-zip'
        unpacked.mkdir()
        (unpacked / 'README.md').write_text('standalone ZIP contents')
        evidence = git_evidence(unpacked)
        self.assertIsNone(evidence['git'])
        self.assertEqual(evidence['reason'], 'no_repository_here')


if __name__ == '__main__':
    unittest.main()
