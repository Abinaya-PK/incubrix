import logging
import time

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

log = logging.getLogger("storage")
_bucket_ready = False


def _client(endpoint: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def ensure_bucket(retries: int = 15, delay: float = 2.0) -> None:
    global _bucket_ready
    if _bucket_ready:
        return
    s3 = _client(settings.s3_endpoint)
    for attempt in range(1, retries + 1):
        try:
            try:
                s3.head_bucket(Bucket=settings.s3_bucket)
            except ClientError:
                s3.create_bucket(Bucket=settings.s3_bucket)
            _bucket_ready = True
            return
        except (BotoCoreError, ClientError) as e:
            if attempt == retries:
                raise
            log.warning("storage not ready (%s), retrying", e)
            time.sleep(delay)


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    ensure_bucket()
    _client(settings.s3_endpoint).put_object(
        Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type
    )


def download_url(key: str, expires: int = 3600) -> str:
    return _client(settings.s3_public_endpoint).generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires,
    )