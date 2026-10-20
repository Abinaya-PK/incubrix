import json
import logging
import time

from app.callbacks import send_callback
from app.db import Job, SessionLocal
from app.logging_setup import correlation_id_var, job_id_var, setup_logging
from app.storage import download_url, upload_bytes


def run_job(job_id: str) -> None:
    setup_logging()
    job_id_var.set(job_id)
    log = logging.getLogger("worker")

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        correlation_id_var.set(job.correlation_id)
        job.status = "running"
        job.progress = 10
        db.commit()
        log.info("job started")

        for p in (30, 60, 90):
            time.sleep(1)
            job.progress = p
            db.commit()

        manifest = {"job_id": job.id, "note": "fake manifest, real pipeline comes later"}
        key = f"jobs/{job.id}/manifest.json"
        upload_bytes(key, json.dumps(manifest).encode(), "application/json")

        job.status = "succeeded"
        job.progress = 100
        job.result = {"manifest_url": download_url(key)}
        db.commit()
        log.info("job succeeded")

        if job.callback_url:
            send_callback(
                job.callback_url,
                {"job_id": job.id, "status": job.status, "result": job.result},
            )