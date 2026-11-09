#!/usr/bin/env python3
"""Обёртка: собирает презентацию (node build_deck.js) и контрольный лист.

Запуск: python3 presentation/build_deck.py
Требует node и пакет pptxgenjs (npm install pptxgenjs в корне репозитория или глобально).
Контрольный лист artifacts/deck-contact.png собирается, если есть soffice и pdftoppm.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PPTX = ROOT / "submission" / "presentation.pptx"
ART = ROOT / "artifacts"


def strip_directory_entries(pptx: Path) -> None:
    """pptxgenjs пишет в ZIP записи-папки; облачные редакторы на них спотыкаются. Переупаковываем без них."""
    import zipfile

    tmp = pptx.with_suffix(".tmp.pptx")
    with zipfile.ZipFile(pptx) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename.endswith("/"):
                continue
            dst.writestr(item, src.read(item.filename))
    tmp.replace(pptx)


def main() -> int:
    node = shutil.which("node")
    if node is None:
        print("ОШИБКА: node не найден; презентация не пересобрана", file=sys.stderr)
        return 1
    env = dict(os.environ)
    extra = [str(ROOT / "node_modules")]
    try:
        extra.append(subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
    except Exception:
        pass
    env["NODE_PATH"] = os.pathsep.join([p for p in extra if p] + [env.get("NODE_PATH", "")])
    result = subprocess.run([node, str(ROOT / "presentation" / "build_deck.js")], env=env)
    if result.returncode != 0:
        return result.returncode
    strip_directory_entries(PPTX)
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    pdftoppm = shutil.which("pdftoppm")
    if soffice and pdftoppm:
        ART.mkdir(exist_ok=True)
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(ART), str(PPTX)], capture_output=True, timeout=240)
        pdf = ART / "presentation.pdf"
        if pdf.exists():
            for old in ART.glob("deck-*.png"):
                old.unlink()
            subprocess.run([pdftoppm, "-r", "60", "-png", str(pdf), str(ART / "deck")], capture_output=True)
            try:
                from PIL import Image
                pages = sorted(ART.glob("deck-*.png"))
                if pages:
                    ims = [Image.open(p) for p in pages]
                    w, h = ims[0].size
                    cols = 5
                    rows = (len(ims) + cols - 1) // cols
                    sheet = Image.new("RGB", (w * cols, h * rows), "white")
                    for i, im in enumerate(ims):
                        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
                    sheet.save(ART / "deck-contact.png")
                    print(f"Контрольный лист: {ART / 'deck-contact.png'} ({len(ims)} слайдов)")
            except ImportError:
                print("Pillow не установлен: контрольный лист не собран, PNG слайдов в artifacts/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
