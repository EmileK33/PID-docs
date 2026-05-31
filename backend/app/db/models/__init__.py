"""ORM model package (S1-A).

[LOAD-BEARING] Every model class and ``Base`` is re-exported here. Alembic's
``env.py`` imports this package to populate ``Base.metadata``; S1-B and every
S2-* session imports models from ``backend.app.db.models`` /
``app.db.models``.

Intra-package imports use the ``app.`` root so the model classes have a single
canonical module identity regardless of whether downstream code imports via
``app.db.models`` or ``backend.app.db.models`` (importing both must not redefine
the tables on ``Base.metadata``).
"""
from __future__ import annotations

from app.db.base import Base
from app.db.models.audit_log import AuditLog, create_audit_log_partition
from app.db.models.detected_symbol import DetectedSymbol
from app.db.models.drawing import Drawing
from app.db.models.entity_class import EntityClass
from app.db.models.export_record import ExportRecord
from app.db.models.file_hash_blocklist import FileHashBlocklist
from app.db.models.ml_training_consent import MLTrainingConsent
from app.db.models.revision_comparison import RevisionComparison
from app.db.models.stored_file import StoredFile
from app.db.models.stripe_event import StripeEvent
from app.db.models.subscription import Subscription
from app.db.models.table_cell import TableCell
from app.db.models.team import Team
from app.db.models.tier import Tier
from app.db.models.user import User
from app.db.models.user_correction import UserCorrection

__all__ = [
    "Base",
    "User",
    "Team",
    "Tier",
    "Subscription",
    "StoredFile",
    "FileHashBlocklist",
    "Drawing",
    "EntityClass",
    "DetectedSymbol",
    "TableCell",
    "UserCorrection",
    "ExportRecord",
    "MLTrainingConsent",
    "RevisionComparison",
    "AuditLog",
    "StripeEvent",
    "create_audit_log_partition",
]
