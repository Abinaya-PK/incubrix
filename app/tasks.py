import time

from app.db import Job, SessionLocal


def run_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        job.status = "running"
        job.progress = 10
        db.commit()

        for p in (30, 60, 90):
            time.sleep(1)
            job.progress = p
            db.commit()

        job.status = "succeeded"
        job.progress = 100
        job.result = {"note": "fake result, real pipeline comes later"}
        db.commit()