"""Run each OCR document in a disposable child process."""

import logging
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

logger = logging.getLogger("ocr")
_ctx = multiprocessing.get_context("spawn")


def _ocr_file_child(path, suffix):
    from app.ocr import ocr_file

    return ocr_file(path, suffix)


def _ocr_job_child(job_id, tmp_path, filename, size):
    from app.jobs import run_ocr_job

    run_ocr_job(job_id, tmp_path, filename, size)


def _run(fn, *args):
    with ProcessPoolExecutor(max_workers=1, mp_context=_ctx) as pool:
        return pool.submit(fn, *args).result()


def ocr_file_isolated(path, suffix):
    return _run(_ocr_file_child, path, suffix)


def run_job_isolated(job_id, tmp_path, filename, size):
    """BackgroundTask: mark the job failed if its OCR worker dies."""
    try:
        _run(_ocr_job_child, job_id, tmp_path, filename, size)
    except Exception as exc:
        logger.exception("Job %s: OCR worker terminated unexpectedly", job_id)
        from app.storage import get_pb

        try:
            get_pb().collection("jobs").update(
                job_id,
                {
                    "status": "error",
                    "errors": {"message": f"OCR worker failed: {exc!r}"},
                    "end_date": datetime.now(timezone.utc).isoformat(),
                },
            )
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
