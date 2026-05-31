"""Postgres engine/session helpers for the integration harness.

DATABASE_URL is exported by the harness as a driver-agnostic ``postgresql://``
URI (the contract downstream sessions read). SQLAlchemy needs an explicit
driver, so we rewrite it onto psycopg v3 here.
"""

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker


def to_psycopg_url(database_url: str) -> URL:
    """Return ``database_url`` as a SQLAlchemy URL on the psycopg-v3 driver.

    IMPORTANT: returns the URL *object*. Do NOT round-trip through ``str()`` /
    ``render_as_string()`` — in SQLAlchemy 2.0 those default to
    ``hide_password=True`` and render the password as the literal ``***``,
    which silently produces ``password authentication failed``.
    """
    return make_url(database_url).set(drivername="postgresql+psycopg")


def make_engine(database_url: str):
    """Build a SQLAlchemy Engine pointed at the Postgres fixture."""
    return create_engine(
        to_psycopg_url(database_url),
        future=True,
        pool_pre_ping=True,
    )


def make_session_factory(bind):
    """Build a sessionmaker bound to an existing connection/engine."""
    return sessionmaker(bind=bind, future=True, expire_on_commit=False)
