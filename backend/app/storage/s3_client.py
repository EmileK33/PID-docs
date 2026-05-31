"""S3 client factory and direct object operations (§1.7 / §1.8).

This module owns the single boto3 S3 client construction discipline for the
whole backend:

* **Credentials** — IAM role by default (boto3's default credential chain).
  Falls back to explicit ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` only
  when *both* are present in settings (§1.12).
* **S3-compatible endpoints** — when ``S3_ENDPOINT_URL`` is set (MinIO /
  LocalStack in dev and the integration harness), the client is pointed at it
  with path-style addressing + SigV4. In production the variable is unset and
  boto3 talks to real AWS S3.
* **Encryption** — every ``put_object`` writes with ``ServerSideEncryption``
  ``AES256`` (SSE-S3). Buckets are never made public; no method here ever sets
  an ACL.

LOAD-BEARING exports: ``get_s3_client`` (any worker needing a raw client),
``put_object`` (S2-K / S2-J), ``delete_object`` (S2-L GDPR worker).
"""
from __future__ import annotations

import os
from typing import IO, Any, Optional, Union

import boto3
from botocore.client import Config

from app.config import settings

# SSE-S3 minimum per §1.7 ("SSE-S3 or SSE-KMS encryption required"). Applied to
# every write — both direct ``put_object`` and the signed PUT URL (presigned.py).
SSE_ALGORITHM = "AES256"


def _credentials_kwargs(s: Any = None) -> dict[str, str]:
    """Return boto3 credential kwargs.

    Explicit static credentials are used only when *both* are present (§1.12);
    otherwise an empty dict is returned so boto3 resolves credentials from its
    default chain (IAM role / instance profile / env).
    """
    s = s if s is not None else settings
    if s.AWS_ACCESS_KEY_ID and s.AWS_SECRET_ACCESS_KEY:
        return {
            "aws_access_key_id": s.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": s.AWS_SECRET_ACCESS_KEY,
        }
    return {}


def get_s3_client() -> Any:
    """Build a boto3 S3 client honoring the credential + endpoint discipline.

    Consumed by every worker that needs a raw client. The client is cheap to
    construct and holds no open sockets, so callers may create one per use.
    """
    client_kwargs: dict[str, Any] = {"region_name": settings.S3_REGION}
    client_kwargs.update(_credentials_kwargs())

    endpoint_url = os.environ.get("S3_ENDPOINT_URL")
    if endpoint_url:
        # MinIO / LocalStack: no DNS-based virtual-hosted buckets, so force
        # path-style addressing and SigV4 (matches the integration harness).
        client_kwargs["endpoint_url"] = endpoint_url
        client_kwargs["config"] = Config(
            signature_version="s3v4", s3={"addressing_style": "path"}
        )

    return boto3.client("s3", **client_kwargs)


def put_object(
    bucket: str,
    key: str,
    body: Union[bytes, IO[bytes]],
    content_type: str,
    *,
    client: Optional[Any] = None,
) -> None:
    """Upload ``body`` to ``bucket/key`` with SSE-S3 encryption enforced.

    Never sets an ACL — objects inherit the bucket's (private) policy.
    """
    s3 = client if client is not None else get_s3_client()
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
        ServerSideEncryption=SSE_ALGORITHM,
    )


def delete_object(bucket: str, key: str, *, client: Optional[Any] = None) -> None:
    """Delete ``bucket/key`` (used by the GDPR erasure worker, S2-L)."""
    s3 = client if client is not None else get_s3_client()
    s3.delete_object(Bucket=bucket, Key=key)
