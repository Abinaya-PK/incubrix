import json
import logging
import tempfile

from app.callbacks import send_callback
from app.db import Job, SessionLocal
from app.errors import ApiError
from app.logging_setup import correlation_id_var, job_id_var, setup_logging
from app.pipeline.run import run_pipeline
from app.storage import download_url, upload_bytes


def run_job(job_id: str) -> None:
    setup_logging()
    job_id_var.set(job_id)
    log = logging.getLogger("worker")

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        correlation_id_var.set(job.correlation_id)
        job.status, job.progress = "running", 5
        db.commit()
        log.info("job started")

        def progress(pct, msg=""):
            job.progress = pct
            db.commit()
            if msg:
                log.info(msg)

        try:
            with tempfile.TemporaryDirectory() as workdir:
                out = run_pipeline(job.input, workdir, progress, output_id=job.id)

            urls = {}
            for name in ("timeline", "manifest"):
                key = f"jobs/{job.id}/{name}.json"
                upload_bytes(key, json.dumps(out[name], indent=2).encode(), "application/json")
                urls[f"{name}_url"] = download_url(key)

            job.result = {**urls, "scenes": len(out["timeline"]["scenes"]),
                          "warnings": out["manifest"]["warnings"]}
            job.status, job.progress = "succeeded", 100
            db.commit()
            log.info("job succeeded")
        except ApiError as e:
            job.status, job.progress = "failed", job.progress
            job.error = {"code": e.code, "message": e.message,
                         "retryable": e.retryable, "details": e.details}
            db.commit()
            log.warning("job failed: %s", e.code)
        except Exception as e:
            job.status = "failed"
            job.error = {"code": "INTERNAL_ERROR", "message": str(e),
                         "retryable": True, "details": {}}
            db.commit()
            log.exception("job crashed")

        if job.callback_url:
            send_callback(job.callback_url, {"job_id": job.id, "status": job.status,
                                             "result": job.result, "error": job.error})