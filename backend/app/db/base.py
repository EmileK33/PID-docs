"""SQLAlchemy declarative base.

[LOAD-BEARING] S1-A attaches every ORM model to this ``Base`` and Alembic's
``env.py`` reads ``Base.metadata`` as ``target_metadata``. This session ships an
empty base only — no models (S1-A owns those).
"""
from __future__ import annotations

from sqlalchemy.orm import declarative_base

Base = declarative_base()
