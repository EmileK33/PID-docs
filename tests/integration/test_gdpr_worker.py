"""S2-L — GDPR Erasure Worker (US-005) integration tests.

Two test groups:

* **Pure-logic tests** (HMAC derivation, determinism, queue routing, startup
  refusal) need neither Postgres nor Redis and run in every environment —
  including the no-Docker ``session-tests`` PR gate, where they provide real
  coverage.
* **DB tests** (PII purge, audit_log nulling, consent deletion, scanner window,
  retry/idempotency, crash-and-retry) require a live Postgres with the S1-A
  schema applied. They are grouped under ``TestErasureWithDatabase`` which is
  ``skipif``-gated on Postgres reachability, so the no-Docker gate skips them
  cleanly while ``integration.yml`` (fixtures live) runs them for real. See
  ``test_db_schema.py`` for the same pattern.

``app.*`` modules are imported lazily (inside the ``gdpr`` fixture and the row
factories), never at import time, so the sibling S0-B smoke assertion
``test_smoke_does_not_import_app`` stays green when the whole ``tests/integration``
suite runs together.

CI command: ``pytest tests/integration/test_gdpr_worker.py -v``
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

# --- import bootstrap (mirrors test_db_schema.py) --------------------------
# Resolve both import roots: ``app.*`` (what app/alembic import) and
# ``backend.app.*`` (the cross-session contract). parents[2] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(REPO_ROOT), str(BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# DATABASE_URL is exported as a driver-agnostic ``postgresql://`` URI; SQLAlchemy
# and Alembic need psycopg v3 named explicitly (psycopg2 is not installed).
# Rewrite BEFORE any ``app`` import constructs the ``settings`` singleton.
_db_url = os.environ.get(
    "DATABASE_URL", "postgresql://pidtest:pidtest@localhost:55432/pidtest"
)
if "+psycopg" not in _db_url and _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)
os.environ["DATABASE_URL"] = _db_url

# app.config marks ML_MODEL_S3_KEY / ODA_CONVERTER_PATH as REQUIRED, but the S0-B
# conftest only seeds the subset its smoke suite needs. Supply test-safe values
# before the ``settings`` singleton is ever built.
os.environ.setdefault("ML_MODEL_S3_KEY", "models/test-model.onnx")
os.environ.setdefault("ODA_CONVERTER_PATH", "/usr/bin/ODAFileConverter")

from sqlalchemy import event, select  # noqa: E402


# --- lazy app-symbol loader ------------------------------------------------
@pytest.fixture
def gdpr() -> SimpleNamespace:
    """Import the S2-L worker surface lazily and expose it as a namespace.

    Importing ``app.*`` here (not at module top) keeps app modules out of
    ``sys.modules`` at collection time so the S0-B no-leak smoke test stays green.
    """
    from app.config import settings
    from app.db.models import AuditLog, MLTrainingConsent, User
    from app.workers.celery_app import celery_app
    from app.workers.gdpr import anonymizer
    from app.workers.gdpr.anonymizer import (
        compute_anonymous_id,
        ensure_anonymous_id,
        erased_email,
        purge_user_pii,
    )
    from app.workers.gdpr.tasks import (
        ERASE_TASK_NAME,
        ERASURE_DELAY_DAYS,
        SCAN_TASK_NAME,
        GDPRErasureJobPayload,
        erase_user_pii,
        scan_and_dispatch_erasure_jobs,
    )
    from app.workers.queues import QUEUE_GDPR

    return SimpleNamespace(
        settings=settings,
        User=User,
        AuditLog=AuditLog,
        MLTrainingConsent=MLTrainingConsent,
        celery_app=celery_app,
        anonymizer=anonymizer,
        compute_anonymous_id=compute_anonymous_id,
        ensure_anonymous_id=ensure_anonymous_id,
        erased_email=erased_email,
        purge_user_pii=purge_user_pii,
        erase_user_pii=erase_user_pii,
        scan_and_dispatch_erasure_jobs=scan_and_dispatch_erasure_jobs,
        ERASE_TASK_NAME=ERASE_TASK_NAME,
        SCAN_TASK_NAME=SCAN_TASK_NAME,
        ERASURE_DELAY_DAYS=ERASURE_DELAY_DAYS,
        GDPRErasureJobPayload=GDPRErasureJobPayload,
        QUEUE_GDPR=QUEUE_GDPR,
    )


# --- Postgres availability gate (DB tests only) ----------------------------
def _postgres_available() -> bool:
    """True iff the Postgres fixture is reachable (3s timeout).

    The ``session-tests`` PR gate runs this file with bare pytest and no Docker;
    ``integration.yml`` / local dev bring the fixture stack up. DB-backed tests
    skip cleanly when Postgres is absent rather than erroring the gate.
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy import text as _text

        eng = create_engine(
            os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3}
        )
        try:
            with eng.connect() as conn:
                conn.execute(_text("SELECT 1"))
        finally:
            eng.dispose()
        return True
    except Exception:
        return False


requires_postgres = pytest.mark.skipif(
    not _postgres_available(),
    reason="Postgres fixture unreachable (session-tests gate runs bare pytest with "
    "no Docker); integration.yml / local runs execute these for real.",
)


# --- test constants + helpers ----------------------------------------------
THIRTY_ONE_DAYS_AGO = datetime.now(timezone.utc) - timedelta(days=31)
TWENTY_NINE_DAYS_AGO = datetime.now(timezone.utc) - timedelta(days=29)


def expected_anonymous_id(user_id: str) -> str:
    """Reference HMAC using the *actually configured* secret.

    The S0-B conftest sets ``HMAC_SERVER_SECRET`` via ``setdefault`` (default
    ``test-secret-do-not-use``), so we derive the expectation from
    ``settings.HMAC_SERVER_SECRET`` rather than hardcoding a literal.
    """
    from app.config import settings

    return hmac.new(
        settings.HMAC_SERVER_SECRET.encode(),
        str(user_id).encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


def make_user(db, *, deleted_at=None, anonymous_id=None):
    """Create a User row with controlled ``deleted_at`` / ``anonymous_id``."""
    from app.db.models import User

    user = User(
        email=f"user_{uuid4()}@example.com",
        display_name="Test User",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$abc$def",
        email_verified=True,
        role="user",
        deleted_at=deleted_at,
        anonymous_id=anonymous_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_audit_log_entry(db, user_id):
    from app.db.models import AuditLog

    entry = AuditLog(
        user_id=user_id,
        action_type="test_action",
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def make_ml_consent(db, user_id):
    from app.db.models import MLTrainingConsent

    consent = MLTrainingConsent(user_id=user_id, opted_in=True)
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


# ===========================================================================
# Pure-logic tests — no backing services required (always run, incl. PR gate)
# ===========================================================================
class TestAnonymousIdDerivation:
    def test_anonymous_id_computed_as_hmac_sha256(self, gdpr):
        """US-005 AC-1: anonymous_id == HMAC-SHA256(user_id || secret) hex digest."""
        user_id = str(uuid4())
        assert gdpr.compute_anonymous_id(user_id) == expected_anonymous_id(user_id)

    def test_compute_anonymous_id_is_deterministic(self, gdpr):
        """US-005 AC-6: identical inputs always produce the identical hex digest."""
        user_id = str(uuid4())
        first = gdpr.compute_anonymous_id(user_id)
        again = gdpr.compute_anonymous_id(user_id)
        assert first == again
        # SHA-256 hex digest: 64 lowercase hex chars.
        assert len(first) == 64
        assert all(c in "0123456789abcdef" for c in first)
        # Distinct users derive distinct ids.
        assert gdpr.compute_anonymous_id(str(uuid4())) != first


class TestQueueRegistration:
    def test_erase_task_registered_on_gdpr_erasure_queue(self, gdpr):
        """US-005 AC-7: erase_user_pii routes to the gdpr_erasure queue."""
        # Registered under the gdpr_erasure-prefixed task name.
        assert gdpr.ERASE_TASK_NAME == "gdpr_erasure.erase_user_pii"
        assert gdpr.ERASE_TASK_NAME in gdpr.celery_app.tasks
        assert gdpr.SCAN_TASK_NAME in gdpr.celery_app.tasks
        # S1-D's routing table maps the gdpr_erasure.* prefix to the queue.
        routes = gdpr.celery_app.conf.task_routes
        assert routes["gdpr_erasure.*"]["queue"] == gdpr.QUEUE_GDPR
        assert gdpr.QUEUE_GDPR == "gdpr_erasure"


class TestStartupValidation:
    def test_startup_refuses_without_hmac_server_secret(self, gdpr):
        """US-005 AC-8: absent/empty HMAC_SERVER_SECRET refuses startup."""
        with patch.object(gdpr.anonymizer.settings, "HMAC_SERVER_SECRET", ""):
            with pytest.raises(EnvironmentError):
                gdpr.anonymizer._validate_hmac_secret_configured()
        # The secret also feeds compute_anonymous_id, which refuses too.
        with patch.object(gdpr.anonymizer.settings, "HMAC_SERVER_SECRET", None):
            with pytest.raises(EnvironmentError):
                gdpr.compute_anonymous_id(str(uuid4()))


class TestJobPayloadContract:
    def test_payload_shape_is_user_id(self, gdpr):
        """Cross-session contract with S2-F: {"user_id": "<uuid>"}."""
        payload = {"user_id": str(uuid4())}
        assert set(payload.keys()) == {"user_id"}
        # The TypedDict is exported for S2-F's enqueue-site type safety.
        assert "user_id" in gdpr.GDPRErasureJobPayload.__annotations__
        assert gdpr.ERASURE_DELAY_DAYS == 30


# ===========================================================================
# DB-backed tests — require live Postgres + S1-A schema (gated)
# ===========================================================================
def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    return cfg


@requires_postgres
class TestErasureWithDatabase:
    @pytest.fixture(scope="class", autouse=True)
    def migrated_db(self, db_engine):
        """Reset the schema and apply all S1-A migrations once for the class."""
        from alembic import command
        from sqlalchemy import text

        with db_engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.commit()
        command.upgrade(_alembic_config(), "head")
        yield db_engine

    # --- AC-1: happy-path field-by-field ---------------------------------
    def test_email_replaced_with_erased_placeholder(self, gdpr, db_session):
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        gdpr.purge_user_pii(str(user.id), db_session)
        db_session.refresh(user)
        anon = user.anonymous_id
        assert user.email == f"erased_{anon[:16]}@erased.invalid"
        assert user.email.endswith("@erased.invalid")

    def test_display_name_replaced_with_deleted_user(self, gdpr, db_session):
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        gdpr.purge_user_pii(str(user.id), db_session)
        db_session.refresh(user)
        assert user.display_name == "Deleted User"

    def test_password_hash_set_to_null(self, gdpr, db_session):
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        assert user.password_hash is not None
        gdpr.purge_user_pii(str(user.id), db_session)
        db_session.refresh(user)
        assert user.password_hash is None

    def test_audit_log_user_id_set_to_null(self, gdpr, db_session):
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        entry = make_audit_log_entry(db_session, user.id)
        gdpr.purge_user_pii(str(user.id), db_session)
        # No audit_log row still references the user.
        remaining = (
            db_session.execute(
                select(gdpr.AuditLog).where(gdpr.AuditLog.user_id == user.id)
            )
            .scalars()
            .all()
        )
        assert remaining == []
        db_session.refresh(entry)
        assert entry.user_id is None

    def test_ml_training_consent_rows_deleted(self, gdpr, db_session):
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        make_ml_consent(db_session, user.id)
        gdpr.purge_user_pii(str(user.id), db_session)
        remaining = (
            db_session.execute(
                select(gdpr.MLTrainingConsent).where(
                    gdpr.MLTrainingConsent.user_id == user.id
                )
            )
            .scalars()
            .all()
        )
        assert remaining == []

    def test_user_row_retained_with_deleted_at_preserved(self, gdpr, db_session):
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        original_deleted_at = user.deleted_at
        user_id = user.id
        gdpr.purge_user_pii(str(user_id), db_session)
        db_session.expire_all()
        reloaded = db_session.get(gdpr.User, user_id)
        assert reloaded is not None  # NOT hard-deleted
        assert reloaded.deleted_at == original_deleted_at  # preserved
        assert reloaded.anonymous_id is not None  # populated

    def test_anonymous_id_matches_hmac_after_erasure(self, gdpr, db_session):
        """US-005 AC-1: persisted anonymous_id equals the HMAC of the user id."""
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        user_id = str(user.id)
        gdpr.purge_user_pii(user_id, db_session)
        db_session.refresh(user)
        assert user.anonymous_id == expected_anonymous_id(user_id)

    # --- AC-1 + AC-9: two-transaction ordering ---------------------------
    def test_anonymous_id_written_in_separate_transaction_before_pii_purge(
        self, gdpr, db_session
    ):
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        captured = []  # (anonymous_id, email) snapshot at each commit
        real_commit = db_session.commit

        def recording_commit():
            captured.append((user.anonymous_id, user.email))
            return real_commit()

        with patch.object(db_session, "commit", side_effect=recording_commit):
            gdpr.purge_user_pii(str(user.id), db_session)

        # At least two commits: (1) anonymous_id, (2) PII purge.
        assert len(captured) >= 2
        # First commit persisted anonymous_id while email was still original PII.
        assert captured[0][0] is not None
        assert not captured[0][1].startswith("erased_")
        # By the final commit the email has been replaced with the placeholder.
        assert captured[-1][1].startswith("erased_")

    def test_crash_after_anonymous_id_commit_retry_completes_correctly(
        self, gdpr, db_session
    ):
        """US-005 AC-9: anonymous_id commits, then a crash; retry finishes."""
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        user_id = str(user.id)

        # Simulate the job committing anonymous_id and crashing before the purge.
        anon = gdpr.ensure_anonymous_id(user_id, db_session)
        assert anon == expected_anonymous_id(user_id)
        db_session.refresh(user)
        assert user.anonymous_id == anon  # committed in its own transaction
        assert not user.email.startswith("erased_")  # purge had not run

        # Retry: must read the persisted anonymous_id, never recompute the HMAC.
        with patch(
            "app.workers.gdpr.anonymizer.compute_anonymous_id",
            side_effect=AssertionError("HMAC must not be recomputed on retry"),
        ) as mock_compute:
            gdpr.purge_user_pii(user_id, db_session)
        mock_compute.assert_not_called()

        db_session.refresh(user)
        assert user.anonymous_id == anon
        assert user.email == f"erased_{anon[:16]}@erased.invalid"
        assert user.display_name == "Deleted User"
        assert user.password_hash is None

    # --- AC-2: retry idempotency -----------------------------------------
    def test_retry_reads_existing_anonymous_id_not_recompute(self, gdpr, db_session):
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        # Pre-set a sentinel anonymous_id that is NOT the real HMAC value.
        sentinel = "deadbeef" * 8  # 64 hex chars
        user.anonymous_id = sentinel
        db_session.commit()

        with patch(
            "app.workers.gdpr.anonymizer.compute_anonymous_id"
        ) as mock_compute:
            gdpr.purge_user_pii(str(user.id), db_session)
        mock_compute.assert_not_called()

        db_session.refresh(user)
        # Stored value read directly — not overwritten by a fresh HMAC.
        assert user.anonymous_id == sentinel
        assert user.email == f"erased_{sentinel[:16]}@erased.invalid"

    def test_retry_produces_identical_final_state(self, gdpr, db_session):
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        user_id = str(user.id)

        gdpr.purge_user_pii(user_id, db_session)
        db_session.refresh(user)
        first = (
            user.anonymous_id,
            user.email,
            user.display_name,
            user.password_hash,
        )

        gdpr.purge_user_pii(user_id, db_session)  # retry
        db_session.refresh(user)
        second = (
            user.anonymous_id,
            user.email,
            user.display_name,
            user.password_hash,
        )
        assert first == second

    # --- AC-5: already-erased no-op --------------------------------------
    def test_already_erased_user_is_noop(self, gdpr, db_session):
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        user_id = str(user.id)
        anon = expected_anonymous_id(user_id)
        # Pre-erase the user fully.
        user.anonymous_id = anon
        user.email = gdpr.erased_email(anon)
        user.display_name = "Deleted User"
        user.password_hash = None
        db_session.commit()

        gdpr.purge_user_pii(user_id, db_session)  # must not raise

        db_session.refresh(user)
        assert user.anonymous_id == anon  # unchanged
        assert user.email == gdpr.erased_email(anon)
        assert user.display_name == "Deleted User"
        assert user.password_hash is None

    # --- AC-3 / AC-4: scanner window -------------------------------------
    def test_scanner_skips_user_deleted_less_than_30_days_ago(self, gdpr, db_session):
        recent = make_user(db_session, deleted_at=TWENTY_NINE_DAYS_AGO)
        old = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)

        with patch.object(gdpr.erase_user_pii, "apply_async") as mock_apply:
            gdpr.scan_and_dispatch_erasure_jobs(db=db_session)

        dispatched = [c.kwargs["args"][0] for c in mock_apply.call_args_list]
        assert str(old.id) in dispatched
        assert str(recent.id) not in dispatched

    def test_scanner_skips_user_without_deleted_at(self, gdpr, db_session):
        active = make_user(db_session, deleted_at=None)
        old = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)

        with patch.object(gdpr.erase_user_pii, "apply_async") as mock_apply:
            gdpr.scan_and_dispatch_erasure_jobs(db=db_session)

        dispatched = [c.kwargs["args"][0] for c in mock_apply.call_args_list]
        assert str(old.id) in dispatched
        assert str(active.id) not in dispatched

    # --- Technical ACs ----------------------------------------------------
    def test_user_correction_rows_not_modified(self, gdpr, db_session):
        """user_correction.user_id is NOT NULL — erasure must never touch it.

        Inserting a real user_correction requires a detected_symbol/table_cell FK
        chain through tables this session may not own, so we assert the stronger
        invariant at the SQL layer: the purge emits no statement against the
        user_correction table (hence no row can be modified).
        """
        user = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        statements: list[str] = []
        conn = db_session.connection()

        def _record(conn_, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(conn, "before_cursor_execute", _record)
        try:
            gdpr.purge_user_pii(str(user.id), db_session)
        finally:
            event.remove(conn, "before_cursor_execute", _record)

        assert statements, "expected the purge to emit SQL"
        assert not any("user_correction" in s.lower() for s in statements)

    def test_email_placeholder_unique_across_multiple_erased_users(
        self, gdpr, db_session
    ):
        u1 = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)
        u2 = make_user(db_session, deleted_at=THIRTY_ONE_DAYS_AGO)

        # Must not raise a UNIQUE violation on user.email.
        gdpr.purge_user_pii(str(u1.id), db_session)
        gdpr.purge_user_pii(str(u2.id), db_session)

        db_session.refresh(u1)
        db_session.refresh(u2)
        assert u1.email != u2.email
        for u in (u1, u2):
            assert u.email.startswith("erased_")
            assert u.email.endswith("@erased.invalid")
