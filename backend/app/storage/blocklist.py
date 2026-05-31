"""File-hash blocklist lookup (§1.4 rule 1).

The upload flow's first gate: before any Drawing record is created or any
pre-signed URL is issued, the client-supplied SHA-256 is checked against
``file_hash_blocklist``. A present hash means the file is blocked (FR-17 AC-2 —
no blocked byte ever reaches S3).

Implementation notes:

* This is a **hot path** — an indexed primary-key probe, returning only a
  boolean. We never select the row payload; callers only need allow/deny.
* Hashes are stored lowercase; incoming values are normalized to lowercase
  before the lookup so an uppercase client hash still matches.
* This session deliberately uses raw SQL via ``sqlalchemy.text()`` against the
  bare table name rather than importing an ORM model from
  ``app/db/models/`` — those belong to S1-A and may not exist at this session's
  prerequisite tier (intra-wave decoupling).

LOAD-BEARING export: ``is_hash_blocked`` (S2-B hash-check endpoint, S2-H ingest
re-check).
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

# Indexed PK probe. ``LIMIT 1`` is redundant on a PK match but makes intent
# explicit and keeps the plan trivial on engines without PK short-circuiting.
_BLOCKLIST_PROBE = text(
    "SELECT 1 FROM file_hash_blocklist WHERE sha256_hash = :sha256_hash LIMIT 1"
)


def _normalize(sha256_hash: str) -> str:
    return sha256_hash.strip().lower()


def _probe(db: Any, normalized_hash: str) -> bool:
    return db.execute(_BLOCKLIST_PROBE, {"sha256_hash": normalized_hash}).first() is not None


def is_hash_blocked(sha256_hash: str, db: Optional[Any] = None) -> bool:
    """Return ``True`` when ``sha256_hash`` is present in ``file_hash_blocklist``.

    ``db`` is an optional SQLAlchemy ``Session``. API/worker callers should pass
    their request/task-scoped session; when omitted a short-lived session is
    opened from the app session factory. The hash is normalized to lowercase
    before the query.
    """
    normalized = _normalize(sha256_hash)

    if db is not None:
        return _probe(db, normalized)

    # Lazy import: app.db.session builds the engine at import time, so importing
    # it eagerly would couple this module's import to a reachable DB driver.
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        return _probe(session, normalized)
    finally:
        session.close()
