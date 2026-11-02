"""Smoke evidence must bind stored bytes, not whichever code is current."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.verify_auxiliary_evidence import safe_path, verify_bundle


class AuxiliaryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.relative = 'experiments/probe'
        self.bundle = self.root / self.relative
        self.bundle.mkdir(parents=True)
        self.report = self.bundle / 'report.json'
        self.report.write_bytes(b'{"passed":true}\n')
        self.source = self.bundle / 'source-snapshot/agent/backend.py'
        self.source.parent.mkdir(parents=True)
        # A historical source is data: executing it would fail the test.
        self.source.write_bytes(b'raise RuntimeError("must never execute")\n')
        self.manifest = {'schema_version': 1, 'kind': 'test-evidence', 'files': {
            'report.json': {'bytes': self.report.stat().st_size,
                            'sha256': hashlib.sha256(self.report.read_bytes()).hexdigest()}},
            'source_sha256': {'agent/backend.py': hashlib.sha256(self.source.read_bytes()).hexdigest()}}
        self.save()

    def save(self):
        (self.bundle / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def check(self):
        return verify_bundle(self.root, self.relative, 'test-evidence')

    def test_historical_bytes_pass_despite_different_current_source(self):
        current = self.root / 'agent/backend.py'
        current.parent.mkdir()
        current.write_text('new implementation')
        result = self.check()
        self.assertTrue(result['passed'], result['errors'])
        self.assertEqual((result['files_checked'], result['sources_checked']), (1, 1))

    def test_same_length_tamper_and_wrong_byte_count_are_rejected(self):
        original = self.report.read_bytes()
        self.report.write_bytes(original.replace(b'true', b'null'))
        self.assertFalse(self.check()['passed'])
        self.report.write_bytes(original)
        self.manifest['files']['report.json']['bytes'] += 1
        self.save()
        self.assertFalse(self.check()['passed'])

    def test_missing_report_and_missing_or_tampered_historical_source_are_rejected(self):
        original = self.report.read_bytes()
        self.report.unlink()
        self.assertFalse(self.check()['passed'])
        self.report.write_bytes(original)
        self.source.write_bytes(b'altered source')
        self.assertFalse(self.check()['passed'])
        self.source.unlink()
        self.assertFalse(self.check()['passed'])

    def test_unsafe_paths_and_external_symlink_are_rejected(self):
        for name in ('.', '../outside', '/tmp/outside', 'a/../../outside', 'a\\outside',
                     'C:/outside', 'a//b', './report.json'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_path(self.bundle, name)
        outside = self.root / 'outside'
        outside.write_text('must not read')
        try:
            (self.bundle / 'linked').symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('symlink creation unavailable on this platform')
        with self.assertRaises(ValueError):
            safe_path(self.bundle, 'linked')

    def test_traversal_declaration_and_duplicate_manifest_key_are_rejected(self):
        self.manifest['files']['../outside'] = self.manifest['files']['report.json']
        self.save()
        self.assertFalse(self.check()['passed'])
        (self.bundle / 'manifest.json').write_text('{"files":{},"files":{}}')
        self.assertFalse(self.check()['passed'])

    def test_missing_manifest_and_source_path_escape_fail_closed(self):
        (self.bundle / 'manifest.json').unlink()
        self.assertFalse(self.check()['passed'])
        self.manifest['source_sha256'] = {'../report.json': self.manifest['files']['report.json']['sha256']}
        self.save()
        self.assertFalse(self.check()['passed'])


if __name__ == '__main__':
    unittest.main()
