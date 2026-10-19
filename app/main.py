import hashlib
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db import Job, SessionLocal, init_db
from app.errors import ApiError, api_error_handler, validation_error_handler
from app.logging_setup import correlation_id_var, setup_logging
from app.tasks import run_job


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    yield


app = FastAPI(title="IncuBrix B-roll Engine", version="0.1.0", lifespan=lifespan)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

log = logging.getLogger("api")
queue = Queue(connection=Redis.from_url(settings.redis_url))


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    cid = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    correlation_id_var.set(cid)
    log.info("%s %s", request.method, request.url.path)
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = cid
    return response


class Captions(BaseModel):
    burn_in: bool = True
    srt: bool = True


class JobRequest(BaseModel):
    audio_url: str | None = None
    script: str | None = None
    scenes: list[dict] | None = None
    voice: str = "en-IN-female"
    aspect_ratios: list[Literal["16:9", "9:16", "1:1"]] = ["16:9"]
    style: str = ""
    avoid: list[str] = []
    captions: Captions = Captions()
    callback_url: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    return {"status": "ready", "footage_provider": settings.footage_provider}


@app.post("/api/v1/broll/jobs", status_code=202)
def create_job(req: JobRequest, idempotency_key: str | None = Header(default=None)):
    if not (req.audio_url or (req.script and req.script.strip()) or req.scenes):
        raise ApiError("EMPTY_INPUT", "Provide audio_url, a non-empty script, or scenes.", 400)

    payload = req.model_dump()
    request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    with SessionLocal() as db:
        if idempotency_key:
            existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
            if existing:
                if existing.request_hash != request_hash:
                    raise ApiError("IDEMPOTENCY_KEY_REUSED",
                                   "This Idempotency-Key was used with a different request.", 409)
                return {"job_id": existing.id, "status": existing.status}

        job = Job(input=payload, idempotency_key=idempotency_key,
                  request_hash=request_hash, callback_url=req.callback_url,correlation_id=correlation_id_var.get())
        db.add(job)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
            return {"job_id": existing.id, "status": existing.status}

        queue.enqueue(run_job, job.id)
        return {"job_id": job.id, "status": job.status}


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            raise ApiError("JOB_NOT_FOUND", f"No job with id {job_id}", 404)
        return {"job_id": job.id, "status": job.status, "progress": job.progress,
                "result": job.result, "error": job.error}