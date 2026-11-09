"""Тесты сборочного скрипта. Не трогают замороженную папку tests/."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_submission", ROOT / "scripts/build_submission.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)

SAMPLE = """# Заголовок

Абзац с **жирным**, `кодом` и [ссылкой](https://example.org).

## Таблица

| Колонка | Число |
|---|---:|
| Строка | 1 |
| Ещё | 22 |

- пункт один
- пункт два

1. шаг
2. шаг

```
код
```
"""


class CharCountTest(unittest.TestCase):
    def test_matches_check_submission_definition(self):
        text = (ROOT / "docs/solution.md").read_text(encoding="utf-8")
        self.assertEqual(build.count_chars(ROOT / "docs/solution.md"), len(text))

    def test_solution_within_hard_limit(self):
        self.assertLessEqual(build.count_chars(ROOT / "docs/solution.md"), build.LIMIT_HARD)


class MarkdownToDocxTest(unittest.TestCase):
    def test_renders_headings_tables_lists(self):
        try:
            from docx import Document
        except ImportError:
            self.skipTest("python-docx не установлен")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.md"
            src.write_text(SAMPLE, encoding="utf-8")
            out = Path(tmp) / "sample.docx"
            build.markdown_to_docx(src, out, Path(tmp))
            document = Document(str(out))
            texts = [p.text for p in document.paragraphs]
            self.assertIn("Заголовок", texts)
            self.assertIn("Таблица", texts)
            self.assertTrue(any("ссылкой (https://example.org)" in t for t in texts))
            self.assertEqual(len(document.tables), 1)
            self.assertEqual(document.tables[0].cell(0, 0).text, "Колонка")
            self.assertEqual(document.tables[0].cell(2, 1).text, "22")
            styles = {p.style.name for p in document.paragraphs}
            self.assertIn("List Bullet", styles)
            self.assertIn("List Number", styles)
            self.assertIn("CodeBlock", styles)


class ManifestTest(unittest.TestCase):
    def test_manifest_schema_fields(self):
        manifest = build.build_manifest(123, 6, 10, None)
        for key in ("schema", "revision", "verified_on", "source_characters",
                    "solution_pdf_pages", "presentation_slides", "sha256", "verification_scope"):
            self.assertIn(key, manifest)
        self.assertEqual(manifest["source_characters"], 123)
        self.assertEqual(manifest["schema"], "case-artifacts-v1")


if __name__ == "__main__":
    unittest.main()
