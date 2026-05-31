"""Celery task base class (§1.8 retry/timeout/priority; §1.4 rule 14).

[LOAD-BEARING] All Phase 2 worker tasks register via
``@celery_app.task(base=BaseTask, ...)``. ``BaseTask`` encodes the durable-queue
retry policy that NFR-7 / §1.4 rule 14 require so queued jobs survive worker
restarts and transient failures retry with backoff rather than being dropped.

Importing this module also installs ``BaseTask`` as the default task base on the
scaffolded ``celery_app`` so plain ``@celery_app.task`` decorators inherit the
policy too. The Celery app itself is not redefined here.

Per-task timeouts (e.g. ML inference ``ML_JOB_TIMEOUT_SECONDS``) are declared by
the owning task via ``time_limit`` — NOT globally — so CPU queues are not capped
by the GPU job budget.
"""
from __future__ import annotations

from celery import Task

from app.workers.celery_app import celery_app

# Default retries for transient failures (§1.8). Backoff is exponential with
# jitter, capped so a stuck dependency does not push retries arbitrarily far.
DEFAULT_MAX_RETRIES = 3
RETRY_BACKOFF_MAX_SECONDS = 600


class BaseTask(Task):
    """Shared base for every queue worker.

    * ``acks_late`` + ``reject_on_worker_lost`` — a job is acknowledged only
      after it completes, and is requeued if the worker dies mid-execution, so
      in-flight jobs survive restarts (NFR-7, §1.4 rule 14).
    * ``autoretry_for`` + ``retry_backoff`` — transient exceptions retry up to
      ``max_retries`` times with exponential backoff and jitter.
    """

    # Durability: don't ack until done; requeue on worker loss.
    acks_late = True
    reject_on_worker_lost = True

    # Retry policy: exponential backoff with jitter, bounded retries.
    autoretry_for = (Exception,)
    max_retries = DEFAULT_MAX_RETRIES
    retry_backoff = True
    retry_backoff_max = RETRY_BACKOFF_MAX_SECONDS
    retry_jitter = True
    retry_kwargs = {"max_retries": DEFAULT_MAX_RETRIES}


# Make BaseTask the default base so plain @celery_app.task tasks inherit the
# policy. Explicit base=BaseTask in worker sessions remains valid.
celery_app.Task = BaseTask


__all__ = ["BaseTask", "DEFAULT_MAX_RETRIES", "RETRY_BACKOFF_MAX_SECONDS"]
