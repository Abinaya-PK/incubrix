import logging
import time

from app.callbacks import send_callback
from app.db import Job, SessionLocal
from app.logging_setup import job_id_var, setup_logging


def run_job(job_id: str) -> None:
    setup_logging()
    job_id_var.set(job_id)
    log = logging.getLogger("worker")

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        job.status = "running"
        job.progress = 10
        db.commit()
        log.info("job started")

        for p in (30, 60, 90):
            time.sleep(1)
            job.progress = p
            db.commit()

        job.status = "succeeded"
        job.progress = 100
        job.result = {"note": "fake result, real pipeline comes later"}
        db.commit()
        log.info("job succeeded")

        if job.callback_url:
            send_callback(
                job.callback_url,
                {"job_id": job.id, "status": job.status, "result": job.result},
            )