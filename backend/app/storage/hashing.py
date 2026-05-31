"""SHA-256 streaming hash utilities (§1.4 rule 3).

Two responsibilities:

* ``compute_sha256_stream`` — hash any file-like / stream in bounded memory by
  feeding fixed-size chunks into ``hashlib.sha256``. A 100 MB upload (the
  ``MAX_UPLOAD_SIZE_BYTES`` ceiling) is hashed without ever materializing the
  whole file in RAM.
* ``verify_object_sha256`` — the server-side re-verification the Ingest Worker
  (S2-H) runs after storage. It streams the *stored* object back through
  ``hashlib.sha256`` and compares to the client-supplied hash. It never trusts
  the S3 ETag, which is not a SHA-256 for multipart uploads.

LOAD-BEARING export: ``verify_object_sha256`` (S2-H, §1.4 rule 3).
"""
from __future__ import annotations

import hashlib
from typing import IO, Any, Optional

from botocore.exceptions import ClientError

from app.storage.s3_client import get_s3_client

# 8 MiB: large enough to amortize syscall/HTTP overhead, small enough that peak
# memory stays bounded regardless of file size.
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024


def compute_sha256_stream(
    file_like: IO[bytes], chunk_size: int = DEFAULT_CHUNK_SIZE
) -> str:
    """Return the lowercase hex SHA-256 of ``file_like``, read in chunks.

    ``file_like`` only needs a ``read(n)`` method (real files, ``BytesIO``,
    botocore ``StreamingBody`` all qualify). Memory use is proportional to
    ``chunk_size``, not file size.
    """
    digest = hashlib.sha256()
    while True:
        chunk = file_like.read(chunk_size)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def verify_object_sha256(
    bucket: str,
    key: str,
    expected_hash: str,
    *,
    client: Optional[Any] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> bool:
    """Stream ``bucket/key`` and return whether its SHA-256 matches.

    Returns ``False`` (never raises) when the object is missing or its hash
    differs. ``expected_hash`` is normalized to lowercase before comparison so
    a client-supplied uppercase hex digest still matches.
    """
    s3 = client if client is not None else get_s3_client()
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except ClientError:
        return False

    body = response["Body"]
    actual = compute_sha256_stream(body, chunk_size=chunk_size)
    return actual == expected_hash.strip().lower()
