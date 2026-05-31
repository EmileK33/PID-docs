"""Shared storage utilities: S3 client, pre-signed URLs, hashing, blocklist.

Single import surface for every upload-path session (drawings API, ingest /
export / GDPR workers). See the individual modules for the §-references behind
each constraint.
"""
from __future__ import annotations

from app.storage.blocklist import is_hash_blocked
from app.storage.hashing import (
    DEFAULT_CHUNK_SIZE,
    compute_sha256_stream,
    verify_object_sha256,
)
from app.storage.presigned import (
    drawing_object_key,
    export_object_key,
    generate_presigned_get_url,
    generate_presigned_put_url,
)
from app.storage.s3_client import (
    SSE_ALGORITHM,
    delete_object,
    get_s3_client,
    put_object,
)

__all__ = [
    # s3_client
    "get_s3_client",
    "put_object",
    "delete_object",
    "SSE_ALGORITHM",
    # presigned
    "generate_presigned_put_url",
    "generate_presigned_get_url",
    "drawing_object_key",
    "export_object_key",
    # hashing
    "compute_sha256_stream",
    "verify_object_sha256",
    "DEFAULT_CHUNK_SIZE",
    # blocklist
    "is_hash_blocked",
]
