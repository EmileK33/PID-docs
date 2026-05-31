"""Post-storage SHA-256 re-verification + second blocklist gate (§1.4 rule 3).

The Ingest Worker runs a *server-side* SHA-256 verification of the stored object
against the client-supplied hash, then checks the hash a second time against the
blocklist to catch entries added between the upload-time gate (step 3) and ingest
(step 7). Both checks happen here, in order:

1. **Integrity** — re-hash the downloaded bytes and compare to
   ``stored_file.sha256_hash``. A mismatch means the stored object was tampered
   with (→ ``"mismatch"``).
2. **Second blocklist gate** — re-check the (now-verified) hash against
   ``file_hash_blocklist`` via the S1-C service (→ ``"blocked"``).

Both failures are terminal and drive a ``Scanning → Scan_Failed`` transition in
the caller; only ``"ok"`` proceeds to format detection.

This module never re-implements SHA-256 inline — it delegates to
``app.storage.hashing`` (S1-C) — and never queries ``file_hash_blocklist``
directly — it uses ``app.storage.blocklist.is_hash_blocked`` (S1-C).
"""
from __future__ import annotations

import io
from typing import Any, Literal

from app.storage.blocklist import is_hash_blocked
from app.storage.hashing import compute_sha256_stream

HashVerifyResult = Literal["ok", "mismatch", "blocked"]


def reverify_hash(file_bytes: bytes, expected_sha256: str, db_session: Any) -> HashVerifyResult:
    """Re-verify integrity then run the second blocklist gate.

    * ``"mismatch"`` — re-hash of ``file_bytes`` != ``expected_sha256``.
    * ``"blocked"``  — hash matched but is now present on the blocklist.
    * ``"ok"``       — integrity verified and not blocked.

    ``expected_sha256`` is normalized to lowercase before comparison (the stored
    hash and ``hashlib.hexdigest()`` are both lowercase).
    """
    actual = compute_sha256_stream(io.BytesIO(file_bytes))
    if actual != expected_sha256.strip().lower():
        return "mismatch"
    # Second, independent gate: pass the verified hash to the S1-C service.
    if is_hash_blocked(actual, db_session):
        return "blocked"
    return "ok"


__all__ = ["reverify_hash", "HashVerifyResult"]
