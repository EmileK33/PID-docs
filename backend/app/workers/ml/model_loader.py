"""Per-worker-process ML model loader (US-011 AC-2).

The detection model is a large GPU-resident artifact. On the G4dn deployment it
MUST be loaded **once per worker process** and reused for every task — loading it
per task would thrash GPU memory and blow the 20-minute SLA. So this module keeps
a module-level singleton: the first task that needs the model triggers the S3
download + initialisation, and every subsequent task reuses the cached object.

The model bytes are pulled from ``S3_BUCKET_NAME`` / ``ML_MODEL_S3_KEY`` (§1.12).
``ML_MODEL_VERSION`` is advisory — when unset, config logs a warning and the
latest object under the key is used (the key itself is the version pointer here).

Download primitive
------------------
S1-C's ``s3_client`` exposes ``get_s3_client`` / ``put_object`` / ``delete_object``
but **no** byte-download helper (the contract's ``download_file_bytes`` was never
implemented). Rather than reach into a function that does not exist, this module
builds the download on the real client factory and re-exports it as
``download_s3_bytes`` so both the model load *and* the per-task drawing download
share one S3 read path (and one patch seam in tests).
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from app.config import settings
from app.storage.s3_client import get_s3_client

logger = logging.getLogger("pid.workers.ml.model_loader")

# Module-level singleton + a lock so two tasks racing the first load on a
# prefork worker don't both download the artifact.
_model: Any = None
_model_lock = threading.Lock()


def download_s3_bytes(bucket: str, key: str, *, client: Optional[Any] = None) -> bytes:
    """Download an entire S3 object into memory as ``bytes``.

    Built on S1-C's ``get_s3_client`` (the contract's ``download_file_bytes`` is
    absent from ``s3_client``). Used for both the model artifact and the per-task
    drawing file so there is a single S3-read seam.
    """
    s3 = client if client is not None else get_s3_client()
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


class LoadedModel:
    """Thin holder around the downloaded detection-model artifact.

    The concrete inference engine (ONNX/torch runtime, pre/post-processing) is an
    external artifact wired in at deploy time; this scaffold carries the raw bytes
    and the resolved version so :mod:`app.workers.ml.inference` can run it. It is
    intentionally minimal — the orchestration (download-once, cache, atomic
    persist, state machine) is what S2-J owns.
    """

    def __init__(self, model_bytes: bytes, *, version: Optional[str], s3_key: str):
        self.model_bytes = model_bytes
        self.version = version
        self.s3_key = s3_key

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"LoadedModel(version={self.version!r}, s3_key={self.s3_key!r}, "
            f"bytes={len(self.model_bytes)})"
        )


def _build_model() -> LoadedModel:
    """Download + initialise the model artifact from S3 (called at most once)."""
    bucket = settings.S3_BUCKET_NAME
    key = settings.ML_MODEL_S3_KEY
    logger.info("Loading ML model from s3://%s/%s", bucket, key)
    model_bytes = download_s3_bytes(bucket, key)
    if not settings.ML_MODEL_VERSION:
        logger.warning(
            "ML_MODEL_VERSION unset; using model at ML_MODEL_S3_KEY=%s as latest", key
        )
    logger.info("ML model loaded (%d bytes, version=%s)", len(model_bytes), settings.ML_MODEL_VERSION)
    return LoadedModel(model_bytes, version=settings.ML_MODEL_VERSION, s3_key=key)


def load_model() -> Any:
    """Return the process-wide cached model, loading it on first use.

    Thread-safe double-checked locking so concurrent tasks on a prefork worker
    download the artifact exactly once (US-011 AC-2).
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = _build_model()
    return _model


def reset_model_cache() -> None:
    """Drop the cached model. Test-only hook; never called in production."""
    global _model
    with _model_lock:
        _model = None


def warm_model_cache(**_kwargs: Any) -> None:
    """Eagerly load the model at worker-process start (best effort).

    Connected to Celery's ``worker_process_init`` signal in :mod:`app.workers.ml.tasks`
    so the artifact is resident before the first task runs. Failures are logged,
    not raised — a transient S3 hiccup at boot must not crash the worker; the
    first task will retry the load via :func:`load_model`.
    """
    try:
        load_model()
    except Exception:  # noqa: BLE001 - boot warm-up must never crash the worker
        logger.exception("Eager ML model warm-up failed; will retry on first task")


__all__ = [
    "load_model",
    "reset_model_cache",
    "warm_model_cache",
    "download_s3_bytes",
    "LoadedModel",
]
