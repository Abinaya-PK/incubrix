import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from app.config import settings

bucket = settings.s3_bucket
key = "test/sample.wav"
config = Config(signature_version="s3v4", s3={"addressing_style": "path"})

# Upload from Windows through the published port.
local_s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:8333",
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name="us-east-1",
    config=config,
)

try:
    local_s3.head_bucket(Bucket=bucket)
except ClientError:
    local_s3.create_bucket(Bucket=bucket)

with open("sample.wav", "rb") as f:
    local_s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=f,
        ContentType="audio/wav",
    )

# Generate a URL using the hostname reachable from the worker container.
docker_s3 = boto3.client(
    "s3",
    endpoint_url="http://minio:8333",
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name="us-east-1",
    config=config,
)

print(docker_s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": bucket, "Key": key},
    ExpiresIn=3600,
))
