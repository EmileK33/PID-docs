"""GDPR erasure worker package (S2-L, US-005).

Re-exports the load-bearing surface consumed by S2-F (enqueue site) and S4-A
(E2E): the ``erase_user_pii`` / ``scan_and_dispatch_erasure_jobs`` Celery tasks,
the ``compute_anonymous_id`` / ``purge_user_pii`` primitives, and the
``GDPRErasureJobPayload`` message contract.
"""
from __future__ import annotations

from app.workers.gdpr.anonymizer import (
    compute_anonymous_id,
    ensure_anonymous_id,
    erased_email,
    purge_user_pii,
)
from app.workers.gdpr.tasks import (
    GDPRErasureJobPayload,
    erase_user_pii,
    scan_and_dispatch_erasure_jobs,
)

__all__ = [
    "compute_anonymous_id",
    "ensure_anonymous_id",
    "erased_email",
    "purge_user_pii",
    "erase_user_pii",
    "scan_and_dispatch_erasure_jobs",
    "GDPRErasureJobPayload",
]
