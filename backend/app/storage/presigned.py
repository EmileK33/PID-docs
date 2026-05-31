"""Pre-signed URL generation and object-key conventions (§1.8 / §1.9).

Pre-signed URLs are the *only* upload/download path for clients — the API never
proxies bytes (§1.8 client-direct pattern). Two hard rules from §1.9 / §1.7:

* **Expiry is exactly ``PRESIGNED_URL_EXPIRY_SECONDS`` (default 900 = 15 min).**
  The generators take no caller-supplied expiry override, so a caller can never
  mint a longer-lived URL than the security constraint allows.
* **Every signed PUT commits to ``ServerSideEncryption=AES256``.** The header is
  baked into the signature via ``Params`` so the client cannot upload an
  unencrypted object with the URL.

LOAD-BEARING exports: ``generate_presigned_put_url`` (S2-B),
``generate_presigned_get_url`` (S2-D / S2-K), ``drawing_object_key`` (S2-B /
S2-H), ``export_object_key`` (S2-D / S2-K).
"""
from __future__ import annotations

from typing import Any, Optional

from app.config import settings
from app.storage.s3_client import SSE_ALGORITHM, get_s3_client


def _expiry_seconds() -> int:
    """The single source of truth for pre-signed URL TTL (§1.9 hard constraint)."""
    return settings.PRESIGNED_URL_EXPIRY_SECONDS


def generate_presigned_put_url(
    bucket: str,
    key: str,
    content_length: int,
    content_type: str,
    *,
    client: Optional[Any] = None,
) -> str:
    """Return a 15-minute pre-signed PUT URL that commits to SSE-S3.

    ``ServerSideEncryption`` is included in the signed ``Params`` so the upload
    is rejected unless the client sends the matching header — there is no path
    to store an unencrypted object via this URL.
    """
    s3 = client if client is not None else get_s3_client()
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": bucket,
            "Key": key,
            "ContentType": content_type,
            "ContentLength": content_length,
            "ServerSideEncryption": SSE_ALGORITHM,
        },
        ExpiresIn=_expiry_seconds(),
    )


def generate_presigned_get_url(
    bucket: str,
    key: str,
    *,
    client: Optional[Any] = None,
) -> str:
    """Return a 15-minute pre-signed GET URL (the only download path, §1.7)."""
    s3 = client if client is not None else get_s3_client()
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=_expiry_seconds(),
    )


def drawing_object_key(drawing_id: str, ext: str) -> str:
    """Canonical S3 key for an uploaded drawing's original file.

    Convention (load-bearing for S2-B / S2-H): ``drawings/{id}/original.{ext}``.
    """
    return f"drawings/{drawing_id}/original.{ext.lstrip('.')}"


def export_object_key(export_id: str, ext: str) -> str:
    """Canonical S3 key for a generated export file.

    Convention (load-bearing for S2-D / S2-K): ``exports/{id}.{ext}``.
    """
    return f"exports/{export_id}.{ext.lstrip('.')}"
