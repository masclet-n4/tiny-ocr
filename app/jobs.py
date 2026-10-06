"""Lógica del job de OCR en background."""

import gc
import logging
import os
import time
from datetime import datetime, timezone

import pypdfium2 as pdfium

from app.config import MEMORY_TRIM
from app.file_storage import save_text
from app.memory import release_page_memory
from app.ocr import extract_pdf_page, ocr_lock
from app.storage import get_pb

logger = logging.getLogger("ocr")


def run_ocr_job(job_id: str, tmp_path: str, filename: str, size: int):
    pb = get_pb()
    base_details = {"filename": filename, "size": size}
    doc = None
    try:
        # Comprobar magic bytes
        with open(tmp_path, "rb") as f:
            magic = f.read(5)
        if magic != b"%PDF-":
            raise ValueError(
                f"Not a PDF (magic={magic!r}, size={os.path.getsize(tmp_path)})"
            )

        # Comprobar que PDFium puede abrirlo
        doc = pdfium.PdfDocument(tmp_path)
        total_pages = len(doc)
        logger.info("Job %s: PDF válido, %d páginas", job_id, total_pages)

        pb.collection("jobs").update(
            job_id,
            {
                "status": "processing",
                "details": {
                    **base_details,
                    "total_pages": total_pages,
                    "pages_processed": 0,
                },
            },
        )
        t0 = time.monotonic()
        # Capa de texto primero; OCR solo si la página no tiene texto embebido
        texts, scores, pages_processed, pages_text_layer = [], [], 0, 0
        with ocr_lock:
            for i, page in enumerate(doc, 1):
                page_texts, page_scores, has_text_layer = extract_pdf_page(page)
                texts.extend(page_texts)
                scores.extend(page_scores)
                if has_text_layer:
                    pages_text_layer += 1
                pages_processed = i
                del page
                if MEMORY_TRIM and not has_text_layer:
                    release_page_memory()
                elif i % 10 == 0:
                    gc.collect()
                # Feedback de progreso (preservando filename/size)
                pb.collection("jobs").update(
                    job_id,
                    {
                        "details": {
                            **base_details,
                            "pages_processed": pages_processed,
                            "total_pages": total_pages,
                        },
                    },
                )
                logger.debug("Job %s: page %d processed", job_id, i)

        full_text = "\n".join(texts)
        avg_score = sum(scores) / len(scores) if scores else 0.0
        details = {
            **base_details,
            "avg_score": round(avg_score, 4),
            "pages_processed": pages_processed,
            "total_pages": total_pages,
            "pages_text_layer": pages_text_layer,
        }

        result_key = save_text(job_id, full_text)
        details["result_key"] = result_key

        now = datetime.now(timezone.utc).isoformat()
        pb.collection("jobs").update(
            job_id,
            {
                "status": "done",
                "details": details,
                "end_date": now,
            },
        )

        logger.info(
            "Job %s: done in %.1fs, %d pages (%d text layer), %d chars, avg_score=%.4f",
            job_id,
            time.monotonic() - t0,
            pages_processed,
            pages_text_layer,
            len(full_text),
            avg_score,
        )
    except Exception as exc:
        logger.exception("Job %s: OCR failed", job_id)
        now = datetime.now(timezone.utc).isoformat()
        pb.collection("jobs").update(
            job_id,
            {
                "status": "error",
                "errors": {"message": str(exc)},
                "end_date": now,
            },
        )
    finally:
        if doc is not None:
            doc.close()
        os.unlink(tmp_path)
