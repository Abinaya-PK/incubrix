from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="IncuBrix B-roll Engine", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    return {"status": "ready", "footage_provider": settings.footage_provider}