"""Celery queue routing (§1.11 Celery Job Queue Names).

[LOAD-BEARING] Declares the canonical six queues and the task-name-prefix →
queue routing table, then applies the table to the scaffolded ``celery_app``
(``app.workers.celery_app``) as a side effect of import. Phase 2 worker sessions
(S2-H/I/J/K/L/M) name their tasks with the matching prefix (e.g.
``ingest.convert_dwg``) so no per-task ``queue=`` argument is needed; if these
prefixes drift, those tasks land on the default queue and never execute.

The queue names and prefixes are exact contracts — do not rename.
"""
from __future__ import annotations

from app.workers.celery_app import celery_app

# §1.11 queue names. Constant identifiers match the session contract
# (QUEUE_ML, QUEUE_GDPR) and the string values match §1.11 exactly.
QUEUE_INGEST = "ingest"
QUEUE_SCAN = "scan"
QUEUE_ML = "ml_inference"
QUEUE_EXPORT = "export"
QUEUE_GDPR = "gdpr_erasure"
QUEUE_NOTIFICATION = "notification"

QUEUE_NAMES = (
    QUEUE_INGEST,
    QUEUE_SCAN,
    QUEUE_ML,
    QUEUE_EXPORT,
    QUEUE_GDPR,
    QUEUE_NOTIFICATION,
)

# Map each task-name prefix to its queue. ``ingest.*`` → ``ingest`` etc.
TASK_ROUTES: dict = {
    "ingest.*": {"queue": QUEUE_INGEST},
    "scan.*": {"queue": QUEUE_SCAN},
    "ml_inference.*": {"queue": QUEUE_ML},
    "export.*": {"queue": QUEUE_EXPORT},
    "gdpr_erasure.*": {"queue": QUEUE_GDPR},
    "notification.*": {"queue": QUEUE_NOTIFICATION},
}

# Apply routing to the scaffolded app (idempotent; this is the authoritative
# routing table). celery_app itself is defined in celery_app.py and not
# redefined here.
celery_app.conf.task_routes = TASK_ROUTES


__all__ = [
    "QUEUE_INGEST",
    "QUEUE_SCAN",
    "QUEUE_ML",
    "QUEUE_EXPORT",
    "QUEUE_GDPR",
    "QUEUE_NOTIFICATION",
    "QUEUE_NAMES",
    "TASK_ROUTES",
]
