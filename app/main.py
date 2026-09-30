"""API FastAPI: endpoints de OCR."""

import logging
import os
import tempfile
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from app.admission import BoundedOcrAdmission
from app.config import ISOLATE_PROCESS, MAX_FILE_SIZE
from app.storage import get_pb

# Con OCR_ISOLATE_PROCESS=1 el procesamiento de cada documento vive en un hijo.
if ISOLATE_PROCESS:
    from app.isolation import ocr_file_isolated as _ocr_file
    from app.isolation import run_job_isolated as _run_job
else:
    from app.jobs import run_ocr_job as _run_job
    from app.ocr import ocr_file as _ocr_file

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("ocr")


class _HealthcheckAccessLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) > 2:
            request_path = str(args[2]).split("?", 1)[0]
            if request_path == "/alive":
                return False
        return True


logging.getLogger("uvicorn.access").addFilter(_HealthcheckAccessLogFilter())


app = FastAPI()
app.add_middleware(BoundedOcrAdmission)

_CHUNK = 1024 * 1024


async def _save_upload(file: UploadFile, suffix: str):
    """Copia el upload a un temporal por bloques, sin cargarlo entero en memoria."""
    size = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        try:
            while chunk := await file.read(_CHUNK):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large (max {MAX_FILE_SIZE // (1024 * 1024)}MB)",
                    )
                tmp.write(chunk)
        except BaseException:
            tmp.close()
            os.unlink(tmp.name)
            raise
    return tmp.name, size


@app.get("/alive")
async def root():
    return {"status": "alive"}


@app.post("/ocr", response_class=PlainTextResponse)
async def ocr_endpoint(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "image.png")[1] or ".png"
    tmp_path, _ = await _save_upload(file, suffix)
    try:
        texts = await run_in_threadpool(_ocr_file, tmp_path, suffix)
        return "\n".join(texts) if texts else ""
    finally:
        os.unlink(tmp_path)


@app.post("/ocr/async")
async def ocr_async(
    file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()
):
    suffix = os.path.splitext(file.filename or "image.png")[1] or ".png"
    tmp_path, size = await _save_upload(file, suffix)
    logger.debug("POST /ocr/async: file=%s size=%d bytes", file.filename, size)

    try:
        now = datetime.now(timezone.utc).isoformat()
        job = (
            get_pb()
            .collection("jobs")
            .create(
                {
                    "type": "ocr",
                    "status": "starting",
                    "start_date": now,
                    "details": {"filename": file.filename, "size": size},
                    "errors": {"message": None},
                }
            )
        )
    except Exception:
        os.unlink(tmp_path)
        raise
    logger.debug("POST /ocr/async: job %s created", job.id)

    background_tasks.add_task(_run_job, job.id, tmp_path, file.filename, size)
    return {"job_id": job.id}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = get_pb().collection("jobs").get_one(job_id)
    result = {"job_id": job.id, "status": job.status}
    if job.details:
        for key in (
            "filename",
            "size",
            "pages_processed",
            "total_pages",
            "pages_text_layer",
        ):
            if key in job.details:
                result[key] = job.details[key]
    if job.status == "done" and job.details:
        if "avg_score" in job.details:
            result["avg_score"] = job.details["avg_score"]
        if "result_key" in job.details:
            result["result_key"] = job.details["result_key"]

    elif job.status == "error" and job.errors:
        result["errors"] = job.errors
    return result
