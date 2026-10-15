from fastapi import FastAPI

from app.config import settings

app = FastAPI(title="IncuBrix B-roll Engine", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    return {"status": "ready", "footage_provider": settings.footage_provider}