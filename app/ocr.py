"""Tesseract OCR and PDF text-layer helpers."""

import csv
import gc
import io
import os
import subprocess
import tempfile
import threading

from app.config import MEMORY_TRIM, RENDER_SCALE, TESSERACT_CMD, TESSERACT_LANG, TESSERACT_PSM
from app.memory import release_page_memory

ocr_lock = threading.Lock()
TEXT_LAYER_MIN_CHARS = 20


def _parse_tsv(tsv):
    lines = {}
    confidences = {}
    reader = csv.DictReader(io.StringIO(tsv), delimiter="\t")
    for row in reader:
        if row.get("level") != "5":
            continue
        text = row.get("text", "").strip()
        if not text:
            continue
        key = tuple(row[name] for name in ("page_num", "block_num", "par_num", "line_num"))
        lines.setdefault(key, []).append(text)
        try:
            score = float(row["conf"])
        except (KeyError, ValueError):
            continue
        if score >= 0:
            confidences.setdefault(key, []).append(score / 100)

    texts = [" ".join(words) for words in lines.values()]
    scores = [
        sum(confidences[key]) / len(confidences[key]) if confidences.get(key) else 0.0
        for key in lines
    ]
    return texts, scores


def _run_tesseract(image_path):
    try:
        result = subprocess.run(
            [
                TESSERACT_CMD,
                image_path,
                "-",
                "-l",
                TESSERACT_LANG,
                "--psm",
                str(TESSERACT_PSM),
                "tsv",
            ],
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or "no diagnostic output"
        raise RuntimeError(f"Tesseract exited {exc.returncode}: {detail}") from exc
    return _parse_tsv(result.stdout)


def ocr_page(image):
    """OCR an image/PIL page and return recognized lines plus normalized confidences."""
    if isinstance(image, (str, os.PathLike)):
        return _run_tesseract(os.fspath(image))

    with tempfile.TemporaryDirectory() as tmpdir:
        image_path = os.path.join(tmpdir, "page.png")
        image.save(image_path, format="PNG")
        return _run_tesseract(image_path)


def page_text_layer(page):
    """Return embedded PDF text when it contains enough non-whitespace characters."""
    textpage = page.get_textpage()
    try:
        text = textpage.get_text_bounded()
    finally:
        textpage.close()
    return text if len(text.strip()) >= TEXT_LAYER_MIN_CHARS else None


def ocr_file(path, suffix):
    """OCR a PDF or image, preferring existing PDF text."""
    if suffix.lower() == ".pdf":
        import pypdfium2 as pdfium

        texts = []
        doc = pdfium.PdfDocument(path)
        try:
            with ocr_lock:
                for page in doc:
                    layer_text = page_text_layer(page)
                    if layer_text is not None:
                        texts.append(layer_text)
                        continue
                    image = page.render(scale=RENDER_SCALE).to_pil()
                    try:
                        page_texts, _ = ocr_page(image)
                        texts.extend(page_texts)
                    finally:
                        image.close()
                    del page, image
                    if MEMORY_TRIM:
                        release_page_memory()
                    elif len(texts) % 100 == 0:
                        gc.collect()
        finally:
            doc.close()
        return texts

    with ocr_lock:
        texts, _ = ocr_page(path)
    return texts