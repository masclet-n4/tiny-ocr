"""Almacenamiento de resultados OCR en RustFS/S3."""

import boto3

from app.config import (
    RUSTFS_ACCESS_KEY,
    RUSTFS_BUCKET,
    RUSTFS_ENDPOINT,
    RUSTFS_REGION,
    RUSTFS_SECRET_KEY,
)


def save_text(job_id: str, text: str) -> str:
    key = f"{job_id}.txt"

    client = boto3.client(
        "s3",
        endpoint_url=RUSTFS_ENDPOINT,
        aws_access_key_id=RUSTFS_ACCESS_KEY,
        aws_secret_access_key=RUSTFS_SECRET_KEY,
        region_name=RUSTFS_REGION,
    )

    client.put_object(
        Bucket=RUSTFS_BUCKET,
        Key=key,
        Body=text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )

    return key
