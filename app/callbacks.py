import hashlib
import hmac
import json
import logging

import httpx

from app.config import settings

log = logging.getLogger("callbacks")


def sign(body: bytes) -> str:
    return hmac.new(settings.callback_secret.encode(), body, hashlib.sha256).hexdigest()


def send_callback(url: str, payload: dict) -> None:
    body = json.dumps(payload).encode()
    try:
        httpx.post(url, content=body, timeout=10, headers={
            "Content-Type": "application/json",
            "X-IncuBrix-Signature": sign(body),
        })
    except Exception as e:
        log.warning("callback failed: %s", e)
        