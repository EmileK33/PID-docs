"""Export worker package (S2-K).

Imports the task module so ``celery_app`` discovers ``export.generate_export``
on worker startup (the ``include`` list in S0-A's ``celery_app.py`` also names
``backend.app.workers.export.tasks``). Re-exports ``generate_export`` for the
load-bearing import path consumed by S2-D's ``export_service.py``.
"""
from __future__ import annotations

from app.workers.export.tasks import generate_export

__all__ = ["generate_export"]
