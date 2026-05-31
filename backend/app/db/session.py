"""Database session factory and FastAPI dependency.

[LOAD-BEARING] Exports ``engine``, ``SessionLocal`` and the ``get_db()``
dependency consumed by every backend service. The engine is created lazily — it
does not open a connection at import time, so importing this module with a dummy
``DATABASE_URL`` (e.g. in unit tests) is safe.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session, closing it when the request completes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
