"""ML inference worker package (S2-J).

Celery worker that downloads processed drawings from S3, runs symbol detection,
atomically persists results, drives the ``Processing -> Complete | Failed`` leg of
the drawing state machine, publishes SSE events via Redis, and emits the
``processing_complete`` / ``processing_failed`` analytics events.

Submodules:

* :mod:`app.workers.ml.model_loader` — per-worker-process cached model load.
* :mod:`app.workers.ml.inference` — model execution → :class:`MLInferenceResult`.
* :mod:`app.workers.ml.result_persistence` — atomic symbol/drawing persistence.
* :mod:`app.workers.ml.tasks` — the ``run_ml_inference`` Celery task.

Nothing is imported eagerly here: importing ``tasks`` pulls in ``celery_app`` and
the SQLAlchemy session factory, so consumers import the specific submodule they
need. This also keeps ``app.*`` out of ``sys.modules`` during test collection
(the S0-B smoke guard).
"""
