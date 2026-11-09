#!/usr/bin/env python3
"""Сборка комплекта для сдачи из исходных markdown-файлов.

Шаги по порядку:
  1. Рендер схем docs/diagrams/*.mmd → *.png только с флагом --render-diagrams
     (нужен mmdc); по умолчанию используются уже лежащие PNG.
  2. docs/solution.md → submission/solution.docx (шрифт 12 пт, таблицы 10,5 пт,
     схемы вставлены по ширине страницы).
  3. submission/solution.docx → submission/solution.pdf через soffice --headless.
  4. docs/metrics.md → submission/metrics.md (побайтовая копия).
  5. docs/ai-footnotes.md → submission/ai-footnotes.docx.
  6. presentation/build_deck.py, если существует, пересобирает
     submission/presentation.pptx; число слайдов считается всегда.
  7. submission/manifest.json: число символов, страницы, слайды, SHA-256.

Флаг --check ничего не пишет: сверяет manifest с текущими файлами и падает при
расхождении. Этим пользуется CI и команда /build.

Запуск из корня репозитория: python3 scripts/build_submission.py [--check] [--render-diagrams]
Зависимости: python-docx (pip install python-docx), soffice для PDF, pdfinfo
для числа страниц, python-pptx для числа слайдов, mmdc для схем. Любая из
последних четырёх может отсутствовать — шаг пропускается с предупреждением.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOLUTION_MD = ROOT / "docs/solution.md"
METRICS_MD = ROOT / "docs/metrics.md"
FOOTNOTES_MD = ROOT / "docs/ai-footnotes.md"
DIAGRAMS_DIR = ROOT / "docs/diagrams"
SUBMISSION_DIR = ROOT / "submission"
MANIFEST = SUBMISSION_DIR / "manifest.json"
DECK_BUILDER = ROOT / "presentation/build_deck.py"
LIMIT_HARD = 15000
LIMIT_TARGET = 14700
MANIFEST_FILES = [
    "docs/solution.md",
    "docs/metrics.md",
    "docs/ai-footnotes.md",
    "submission/solution.docx",
    "submission/solution.pdf",
    "submission/metrics.md",
    "submission/presentation.pptx",
    "submission/ai-footnotes.docx",
]

WARNINGS: list[str] = []


def warn(message: str) -> None:
    WARNINGS.append(message)
    print("ПРЕДУПРЕЖДЕНИЕ: " + message, file=sys.stderr)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_chars(path: Path) -> int:
    """Та же метрика, что в scripts/check_submission.py: len() всего файла."""
    return len(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Шаг 1. Схемы
# ---------------------------------------------------------------------------

def render_diagrams() -> list[Path]:
    if not DIAGRAMS_DIR.is_dir():
        return []
    sources = sorted(DIAGRAMS_DIR.glob("*.mmd"))
    if not sources:
        return []
    mmdc = shutil.which("mmdc")
    rendered: list[Path] = []
    for src in sources:
        png = src.with_suffix(".png")
        if mmdc is None:
            if png.exists():
                rendered.append(png)
            else:
                warn(f"mmdc не найден, PNG для {src.name} отсутствует")
            continue
        cmd = [mmdc, "-i", str(src), "-o", str(png), "-b", "white", "-s", "2"]
        config = DIAGRAMS_DIR / "mermaid.config.json"
        if config.exists():
            cmd += ["-c", str(config)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=180)
            rendered.append(png)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            detail = getattr(error, "stderr", b"") or b""
            warn(f"рендер {src.name} не удался: {detail[-200:].decode('utf-8', 'ignore').strip()}")
            if png.exists():
                rendered.append(png)
    return rendered


# ---------------------------------------------------------------------------
# Шаг 2 и 5. Markdown → DOCX
# ---------------------------------------------------------------------------

INLINE_PATTERN = re.compile(
    r"(`[^`]+`)"                      # код
    r"|(\*\*[^*]+\*\*)"               # жирный
    r"|(\[[^\]]+\]\([^)]+\))"         # ссылка
    r"|(?<![\w*])(\*[^*\s][^*]*\*)(?![\w*])"  # курсив
)


def _add_inline(paragraph, text: str, size_pt: float | None = None) -> None:
    """Разбирает **жирный**, *курсив*, `код`, [текст](url) внутри абзаца."""
    from docx.shared import Pt

    position = 0
    for match in INLINE_PATTERN.finditer(text):
        if match.start() > position:
            run = paragraph.add_run(text[position:match.start()])
            if size_pt:
                run.font.size = Pt(size_pt)
        token = match.group(0)
        if token.startswith("`"):
            run = paragraph.add_run(token.strip("`"))
            run.font.name = "Courier New"
            run.font.size = Pt((size_pt or 12) - 1.5)
        elif token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            run.bold = True
            if size_pt:
                run.font.size = Pt(size_pt)
        elif token.startswith("["):
            label, url = re.match(r"\[([^\]]+)\]\(([^)]+)\)", token).groups()
            run = paragraph.add_run(f"{label} ({url})" if url not in label else label)
            if size_pt:
                run.font.size = Pt(size_pt)
        else:
            run = paragraph.add_run(token[1:-1])
            run.italic = True
            if size_pt:
                run.font.size = Pt(size_pt)
        position = match.end()
    if position < len(text):
        run = paragraph.add_run(text[position:])
        if size_pt:
            run.font.size = Pt(size_pt)


def _split_row(line: str) -> list[str]:
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def _is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*", line))


def _alignments(line: str):
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    result = []
    for cell in _split_row(line):
        if cell.endswith(":") and cell.startswith(":"):
            result.append(WD_ALIGN_PARAGRAPH.CENTER)
        elif cell.endswith(":"):
            result.append(WD_ALIGN_PARAGRAPH.RIGHT)
        else:
            result.append(WD_ALIGN_PARAGRAPH.LEFT)
    return result


TABLE_WIDTH_CM = 17.0


def _column_widths(columns: int):
    """Первая колонка уже (термин), остальные делят остаток поровну."""
    from docx.shared import Cm

    if columns <= 1:
        return [Cm(TABLE_WIDTH_CM)]
    first = 0.30 if columns == 2 else 0.24
    rest = (1 - first) / (columns - 1)
    return [Cm(TABLE_WIDTH_CM * first)] + [Cm(TABLE_WIDTH_CM * rest)] * (columns - 1)


def _ensure_styles(document) -> None:
    from docx.enum.style import WD_STYLE_TYPE
    from docx.shared import Pt, Cm

    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(12)
    normal.paragraph_format.space_after = Pt(6)
    if "CodeBlock" not in [s.name for s in document.styles]:
        code = document.styles.add_style("CodeBlock", WD_STYLE_TYPE.PARAGRAPH)
        code.base_style = normal
        code.font.name = "Courier New"
        code.font.size = Pt(9.5)
        code.paragraph_format.space_after = Pt(0)
        code.paragraph_format.left_indent = Cm(0.5)
    for section in document.sections:
        section.top_margin = section.bottom_margin = Cm(2)
        section.left_margin = section.right_margin = Cm(2)


MAX_IMAGE_WIDTH_CM = 16.0
MAX_IMAGE_HEIGHT_CM = 8.0


def _fit_width(image_path: Path):
    """Ширина картинки в docx: не шире 16 см и не выше 8 см, пропорции сохраняются."""
    from docx.shared import Cm
    from docx.image.image import Image as DocxImage

    try:
        image = DocxImage.from_file(str(image_path))
        ratio = image.px_width / image.px_height
    except Exception:
        return Cm(MAX_IMAGE_WIDTH_CM)
    return Cm(min(MAX_IMAGE_WIDTH_CM, MAX_IMAGE_HEIGHT_CM * ratio))


def markdown_to_docx(markdown_path: Path, docx_path: Path, image_root: Path) -> None:
    try:
        from docx import Document
        from docx.shared import Pt, Cm
    except ImportError:
        print("ОШИБКА: нужен python-docx: pip install python-docx", file=sys.stderr)
        sys.exit(2)

    document = Document()
    _ensure_styles(document)
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    index = 0
    paragraph_buffer: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_buffer:
            paragraph = document.add_paragraph()
            _add_inline(paragraph, " ".join(s.strip() for s in paragraph_buffer))
            paragraph_buffer.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                document.add_paragraph(lines[index].rstrip(), style="CodeBlock")
                index += 1
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        if stripped.startswith("<") and stripped.endswith(">"):
            flush_paragraph()
            index += 1
            continue

        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            flush_paragraph()
            index += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            text = re.sub(r"[*`]", "", heading.group(2)).strip()
            document.add_heading(text, level=min(level, 3))
            index += 1
            continue

        image = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image:
            flush_paragraph()
            alt, rel_path = image.groups()
            candidate = (markdown_path.parent / rel_path).resolve()
            if not candidate.exists():
                candidate = (image_root / rel_path).resolve()
            if candidate.exists():
                document.add_picture(str(candidate), width=_fit_width(candidate))
                if alt:
                    caption = document.add_paragraph()
                    run = caption.add_run(alt)
                    run.italic = True
                    run.font.size = Pt(10)
            else:
                warn(f"схема не найдена: {rel_path}")
                document.add_paragraph(f"[схема: {alt or rel_path}]")
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and _is_separator(lines[index + 1]):
            flush_paragraph()
            header = _split_row(stripped)
            aligns = _alignments(lines[index + 1])
            rows: list[list[str]] = []
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(_split_row(lines[index]))
                index += 1
            table = document.add_table(rows=1 + len(rows), cols=len(header))
            table.style = "Table Grid"
            table.autofit = False
            widths = _column_widths(len(header))
            for row_cells in table.rows:
                for col, cell in enumerate(row_cells.cells):
                    if col < len(widths):
                        cell.width = widths[col]
            for col, cell_text in enumerate(header):
                cell = table.rows[0].cells[col]
                cell.text = ""
                paragraph = cell.paragraphs[0]
                run = paragraph.add_run(re.sub(r"\*\*", "", cell_text))
                run.bold = True
                run.font.size = Pt(10.5)
            for row_index, row in enumerate(rows, start=1):
                for col in range(len(header)):
                    cell = table.rows[row_index].cells[col]
                    cell.text = ""
                    paragraph = cell.paragraphs[0]
                    if col < len(aligns):
                        paragraph.alignment = aligns[col]
                    _add_inline(paragraph, row[col] if col < len(row) else "", size_pt=10.5)
            document.add_paragraph()
            continue

        bullet = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if bullet:
            flush_paragraph()
            indent = len(bullet.group(1).replace("\t", "  "))
            style = "List Bullet 2" if indent >= 2 else "List Bullet"
            paragraph = document.add_paragraph(style=style)
            _add_inline(paragraph, bullet.group(2))
            index += 1
            continue

        numbered = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if numbered:
            flush_paragraph()
            paragraph = document.add_paragraph(style="List Number")
            _add_inline(paragraph, numbered.group(1))
            index += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            paragraph = document.add_paragraph(style="Quote")
            _add_inline(paragraph, stripped.lstrip("> ").strip())
            index += 1
            continue

        paragraph_buffer.append(line)
        index += 1

    flush_paragraph()
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(docx_path))


# ---------------------------------------------------------------------------
# Шаг 3. DOCX → PDF
# ---------------------------------------------------------------------------

def docx_to_pdf(docx_path: Path, out_dir: Path) -> Path | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        warn("soffice не найден, PDF не пересобран")
        return None
    cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=240)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        warn(f"конвертация в PDF не удалась: {error}")
        return None
    pdf = out_dir / (docx_path.stem + ".pdf")
    return pdf if pdf.exists() else None


def pdf_pages(pdf_path: Path | None) -> int | None:
    if pdf_path is None or not pdf_path.exists():
        return None
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo is None:
        warn("pdfinfo не найден, число страниц не определено")
        return None
    output = subprocess.run([pdfinfo, str(pdf_path)], capture_output=True, text=True).stdout
    match = re.search(r"Pages:\s+(\d+)", output)
    return int(match.group(1)) if match else None


def pptx_slides(pptx_path: Path) -> int | None:
    if not pptx_path.exists():
        return None
    try:
        from pptx import Presentation
    except ImportError:
        warn("python-pptx не найден, число слайдов не определено")
        return None
    return len(Presentation(str(pptx_path)).slides)


# ---------------------------------------------------------------------------
# Манифест и отчёт
# ---------------------------------------------------------------------------

def build_manifest(source_chars: int, pages: int | None, slides: int | None, previous: dict | None) -> dict:
    hashes = {}
    for rel in MANIFEST_FILES:
        path = ROOT / rel
        if path.exists():
            hashes[rel] = sha256(path)
        else:
            warn(f"файла нет, в манифест не включён: {rel}")
    return {
        "schema": "case-artifacts-v1",
        "revision": f"build-{date.today().isoformat()}",
        "verified_on": date.today().isoformat(),
        "source_characters": source_chars,
        "solution_pdf_pages": pages if pages is not None else (previous or {}).get("solution_pdf_pages"),
        "presentation_slides": slides if slides is not None else (previous or {}).get("presentation_slides"),
        "sha256": hashes,
        "verification_scope": (
            "Собрано scripts/build_submission.py из docs/*.md. Проверены длина "
            "исходника, совпадение копий метрик и SHA-256 всех файлов комплекта. "
            "Качество моделей и бизнес-эффект этим не подтверждаются."
        ),
    }


def print_report(manifest: dict) -> None:
    chars = manifest["source_characters"]
    status = "OK" if chars <= LIMIT_TARGET else ("ВНИМАНИЕ: выше цели 14 700" if chars <= LIMIT_HARD else "ОШИБКА: выше лимита 15 000")
    print()
    print(f"{'Файл':<34} {'Байт':>9}  {'SHA-256':<14} Примечание")
    for rel, digest in manifest["sha256"].items():
        path = ROOT / rel
        note = ""
        if rel == "docs/solution.md":
            note = f"{chars} символов — {status}"
        elif rel == "submission/solution.pdf":
            note = f"страниц: {manifest.get('solution_pdf_pages')}"
        elif rel == "submission/presentation.pptx":
            note = f"слайдов: {manifest.get('presentation_slides')}"
        elif rel == "docs/metrics.md":
            note = f"{count_chars(path)} символов"
        print(f"{rel:<34} {path.stat().st_size:>9}  {digest[:12]}…  {note}")
    print()
    if WARNINGS:
        print(f"Предупреждений: {len(WARNINGS)} (см. выше)")
    print(f"Итог: {status}")


def check_only() -> int:
    if not MANIFEST.exists():
        print("ОШИБКА: submission/manifest.json отсутствует, запусти сборку", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems: list[str] = []
    chars = count_chars(SOLUTION_MD)
    if manifest.get("source_characters") != chars:
        problems.append(f"source_characters {manifest.get('source_characters')} ≠ {chars}")
    if chars > LIMIT_HARD:
        problems.append(f"docs/solution.md превышает лимит: {chars} > {LIMIT_HARD}")
    for rel, expected in manifest.get("sha256", {}).items():
        path = ROOT / rel
        if not path.exists():
            problems.append(f"{rel}: файл отсутствует")
        elif sha256(path) != expected:
            problems.append(f"{rel}: изменён после сборки")
    if METRICS_MD.read_bytes() != (SUBMISSION_DIR / "metrics.md").read_bytes():
        problems.append("docs/metrics.md и submission/metrics.md различаются")
    for extra in sorted(p.name for p in SUBMISSION_DIR.iterdir() if p.is_file() and p.name != "manifest.json"):
        if f"submission/{extra}" not in manifest.get("sha256", {}):
            problems.append(f"submission/{extra}: есть в папке, нет в манифесте")
    if problems:
        print("ПРОВЕРКА НЕ ПРОЙДЕНА:")
        for problem in problems:
            print("  - " + problem)
        return 1
    print(f"Манифест актуален: {len(manifest['sha256'])} файлов, {chars} символов в docs/solution.md")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Сборка комплекта для сдачи")
    parser.add_argument("--check", action="store_true", help="только сверить manifest с файлами")
    parser.add_argument("--no-pdf", action="store_true", help="не конвертировать в PDF")
    parser.add_argument("--render-diagrams", action="store_true", help="перерисовать PNG схем через mmdc (по умолчанию берутся лежащие PNG)")
    parser.add_argument("--no-deck", action="store_true", help="не запускать presentation/build_deck.py")
    args = parser.parse_args()

    if args.check:
        return check_only()

    for required in (SOLUTION_MD, METRICS_MD):
        if not required.exists():
            print(f"ОШИБКА: нет файла {required.relative_to(ROOT)}", file=sys.stderr)
            return 1
    SUBMISSION_DIR.mkdir(exist_ok=True)
    previous = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else None

    chars = count_chars(SOLUTION_MD)
    if chars > LIMIT_HARD:
        print(f"ОШИБКА: docs/solution.md содержит {chars} символов, лимит {LIMIT_HARD}. Сборка остановлена.", file=sys.stderr)
        return 1

    if args.render_diagrams:
        rendered = render_diagrams()
        if rendered:
            print(f"Схемы: {len(rendered)} PNG")

    markdown_to_docx(SOLUTION_MD, SUBMISSION_DIR / "solution.docx", ROOT)
    print("solution.docx собран")
    pdf = None if args.no_pdf else docx_to_pdf(SUBMISSION_DIR / "solution.docx", SUBMISSION_DIR)
    if pdf:
        print("solution.pdf собран")

    shutil.copyfile(METRICS_MD, SUBMISSION_DIR / "metrics.md")
    print("metrics.md скопирован")

    if FOOTNOTES_MD.exists():
        markdown_to_docx(FOOTNOTES_MD, SUBMISSION_DIR / "ai-footnotes.docx", ROOT)
        print("ai-footnotes.docx собран")

    if DECK_BUILDER.exists() and not args.no_deck:
        try:
            subprocess.run([sys.executable, str(DECK_BUILDER)], check=True, timeout=600)
            print("presentation.pptx пересобран")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            warn(f"сборка презентации не удалась: {error}")

    manifest = build_manifest(chars, pdf_pages(pdf), pptx_slides(SUBMISSION_DIR / "presentation.pptx"), previous)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print_report(manifest)
    return 0 if chars <= LIMIT_HARD else 1


if __name__ == "__main__":
    sys.exit(main())
