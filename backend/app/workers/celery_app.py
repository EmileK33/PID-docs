"""Celery application + queue declarations (§1.11).

[LOAD-BEARING] Declares all six queues from §1.11 via ``task_routes``. Downstream
worker sessions (S1-D, S2-H..M) register tasks against these queue names;
renaming a queue post-merge breaks every worker. No tasks are registered here —
this scaffold only establishes the broker connection and routing table.
"""
from __future__ import annotations

from celery import Celery

from app.config import settings

# §1.11 Celery Job Queue Names — the canonical set. Do not rename.
QUEUE_INGEST = "ingest"
QUEUE_SCAN = "scan"
QUEUE_ML_INFERENCE = "ml_inference"
QUEUE_EXPORT = "export"
QUEUE_GDPR_ERASURE = "gdpr_erasure"
QUEUE_NOTIFICATION = "notification"

QUEUE_NAMES = (
    QUEUE_INGEST,
    QUEUE_SCAN,
    QUEUE_ML_INFERENCE,
    QUEUE_EXPORT,
    QUEUE_GDPR_ERASURE,
    QUEUE_NOTIFICATION,
)

celery_app = Celery(
    "pid",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
)

# Map task name prefixes → queues. Downstream workers name their tasks with the
# matching prefix (e.g. ``ingest.convert_dwg``) so routing requires no per-task
# config. Each value is a dict so the queue name is discoverable via
# ``celery_app.conf.task_routes[...]["queue"]``.
celery_app.conf.task_routes = {
    "ingest.*": {"queue": QUEUE_INGEST},
    "scan.*": {"queue": QUEUE_SCAN},
    "ml_inference.*": {"queue": QUEUE_ML_INFERENCE},
    "export.*": {"queue": QUEUE_EXPORT},
    "gdpr_erasure.*": {"queue": QUEUE_GDPR_ERASURE},
    "notification.*": {"queue": QUEUE_NOTIFICATION},
}

celery_app.conf.update(
    task_acks_late=True,  # NFR-7: jobs survive worker restarts
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue=QUEUE_INGEST,
    timezone="UTC",
    enable_utc=True,
)
