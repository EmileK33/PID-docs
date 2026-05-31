"""S2-B — Drawings API acceptance tests (US-003, US-006..US-010, US-018).

Run:  pytest tests/integration/test_drawings_api.py -v --tb=short

These tests are **self-contained at the infrastructure level** so they pass in
the no-Docker ``session-tests`` gate (which runs this file with bare pytest and
no Postgres/Redis/MinIO listening):

* **DB** — an in-memory SQLite engine. The ORM models use ``postgresql.UUID`` /
  ``JSONB``; compiler shims (registered once below) render those as portable
  SQLite types so ``create_all`` + the ORM round-trips work. Postgres-only DDL
  (the ``idx_drawing_fts`` GIN index) is created only in the migration, never by
  ``create_all``, and ``drawing_service`` falls back to ``ILIKE`` off-Postgres.
* **Redis** — an in-process ``fakeredis`` async client backed by one shared
  ``FakeServer`` (patched over ``app.redis.client.get_redis``).
* **S3** — pre-signed URLs are signed entirely offline by botocore.
* **Celery / analytics** — ``celery_app.send_task`` and the emitters are patched
  to record calls without dispatching.

``app.*`` is imported lazily (inside fixtures), never at module top level, so the
shared S0-B smoke suite's "no app import during collection" guard stays green
when the whole ``tests/integration`` tree runs together.
"""
from __future__ import annotations

import asyncio
import datetime
import os
import sys
import uuid
from pathlib import Path

import pytest

# --- make `app` (backend/app) importable + repo root on path ----------------
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(BACKEND), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- §1.12 "Refuse to start" env contract: set BEFORE importing app ----------
_REQUIRED_ENV = {
    "DATABASE_URL": "postgresql://u:p@localhost:5432/pid",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_BUCKET_NAME": "pidtest-bucket",
    "S3_REGION": "us-east-1",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
    "JWT_RS256_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\nMIIB\n-----END PUBLIC KEY-----",
    "STRIPE_SECRET_KEY": "sk_test_dummy",
    "STRIPE_WEBHOOK_SECRET": "whsec_dummy",
    "SENDGRID_API_KEY": "SG.dummy",
    "HMAC_SERVER_SECRET": "high-entropy-secret",
    "ML_MODEL_S3_KEY": "models/pid/v1.onnx",
    "ODA_CONVERTER_PATH": "/opt/oda/ODAFileConverter",
    "PRESIGNED_URL_EXPIRY_SECONDS": "900",
}
for _k, _v in _REQUIRED_ENV.items():
    os.environ.setdefault(_k, _v)

# Third-party imports are safe at module level (smoke guard only flags app.*).
# fastapi names MUST be module-level: ``from __future__ import annotations`` makes
# the override's ``request: Request`` annotation a string that FastAPI resolves
# against module globals — a local import would leave it unresolved (→ FastAPI
# would treat ``request`` as a query param and 422 every call).
import fakeredis.aioredis  # noqa: E402
from fastapi import HTTPException, Request, status  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB, UUID  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# Render Postgres-only column types as portable SQLite types (DDL only). Guarded
# so a re-import during a combined run does not double-register.
if not globals().get("_PG_TYPE_SHIMS_REGISTERED"):

    @compiles(JSONB, "sqlite")
    def _compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001
        return "JSON"

    @compiles(UUID, "sqlite")
    def _compile_uuid_sqlite(type_, compiler, **kw):  # noqa: ANN001
        return "CHAR(36)"

    _PG_TYPE_SHIMS_REGISTERED = True

_ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


# ===========================================================================
# Harness
# ===========================================================================
class Harness:
    """Per-test app + DB + fakeredis bundle with insert helpers."""

    def __init__(self, monkeypatch):
        # Lazy app imports (kept out of sys.modules during collection).
        from app.auth.dependencies import CurrentUser, get_current_user
        from app.db.models import (
            Base,
            Drawing,
            StoredFile,
            Subscription,
            Team,
            Tier,
            User,
        )
        from app.db.seed_tiers import TIER_SEED_DATA
        from app.db.session import get_db
        from app.main import app
        from app.redis import client as redis_client
        from starlette.testclient import TestClient

        self._models = dict(
            Drawing=Drawing,
            StoredFile=StoredFile,
            Subscription=Subscription,
            Team=Team,
            Tier=Tier,
            User=User,
        )

        # --- DB: fresh in-memory SQLite per test ---
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine, future=True)()

        # Seed the tier rows (free=3, pro/team=unlimited).
        for row in TIER_SEED_DATA:
            self.session.add(Tier(**row))
        self.session.commit()

        # --- Redis: shared fakeredis server ---
        self._fake_server = fakeredis.aioredis.FakeServer()
        monkeypatch.setattr(
            redis_client,
            "get_redis",
            lambda: fakeredis.aioredis.FakeRedis(
                server=self._fake_server, decode_responses=True
            ),
        )

        # --- Auth + DB dependency overrides ---
        def _override_get_db():
            yield self.session  # do not close; harness teardown owns the session

        def _override_current_user(
            request: Request, db=None
        ) -> "CurrentUser":  # noqa: F821
            uid = request.headers.get("x-test-user")
            if not uid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            row = self.session.get(User, uuid.UUID(uid))
            if row is None or row.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
                )
            return CurrentUser(
                id=row.id, email=row.email, role=row.role, team_id=row.team_id
            )

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = _override_current_user
        self._app = app
        self._get_db = get_db
        self._get_current_user = get_current_user
        self.client = TestClient(app)

    # --- teardown ---
    def close(self):
        self.client.close()
        self._app.dependency_overrides.pop(self._get_db, None)
        self._app.dependency_overrides.pop(self._get_current_user, None)
        self.session.close()
        self.engine.dispose()

    # --- auth helper ---
    @staticmethod
    def auth(user) -> dict:
        return {"x-test-user": str(user.id)}

    # --- redis helper ---
    def redis(self):
        return fakeredis.aioredis.FakeRedis(
            server=self._fake_server, decode_responses=True
        )

    # --- insert helpers ---
    def add_user(self, role="user", team_id=None, email=None):
        User = self._models["User"]
        u = User(
            id=uuid.uuid4(),
            email=email or f"{uuid.uuid4().hex}@example.com",
            display_name="Test User",
            role=role,
            team_id=team_id,
            email_verified=True,
        )
        self.session.add(u)
        self.session.commit()
        return u

    def add_team(self, seats=5):
        Team = self._models["Team"]
        t = Team(id=uuid.uuid4(), name="Acme", licensed_seats=seats)
        self.session.add(t)
        self.session.commit()
        return t

    def add_subscription(self, *, user_id=None, team_id=None, tier_id="free"):
        Subscription = self._models["Subscription"]
        s = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            team_id=team_id,
            tier_id=tier_id,
            billing_state="Active",
        )
        self.session.add(s)
        self.session.commit()
        return s

    def add_stored_file(self, *, sha256=_ABC_SHA256):
        StoredFile = self._models["StoredFile"]
        sf = StoredFile(
            id=uuid.uuid4(),
            bucket="pidtest-bucket",
            object_key=f"drawings/{uuid.uuid4()}/original.pdf",
            sha256_hash=sha256,
            file_type="pdf",
            size_bytes=2048,
        )
        self.session.add(sf)
        self.session.commit()
        return sf

    def add_drawing(
        self,
        *,
        owner_user_id=None,
        owner_team_id=None,
        state="Pending",
        filename="drawing.pdf",
        revision_label=None,
        uploaded_at=None,
        with_stored_file=True,
    ):
        Drawing = self._models["Drawing"]
        sf_id = None
        if with_stored_file:
            sf_id = self.add_stored_file().id
        d = Drawing(
            id=uuid.uuid4(),
            owner_user_id=owner_user_id,
            owner_team_id=owner_team_id,
            filename=filename,
            revision_label=revision_label,
            processing_state=state,
            uploaded_at=uploaded_at
            or datetime.datetime.now(datetime.timezone.utc),
            stored_file_id=sf_id,
        )
        self.session.add(d)
        self.session.commit()
        return d


@pytest.fixture
def h(monkeypatch):
    harness = Harness(monkeypatch)
    try:
        yield harness
    finally:
        harness.close()


@pytest.fixture
def auth_user(h):
    """role=user with a free-tier subscription."""
    user = h.add_user(role="user")
    h.add_subscription(user_id=user.id, tier_id="free")
    return user


@pytest.fixture
def pro_user(h):
    user = h.add_user(role="user")
    h.add_subscription(user_id=user.id, tier_id="pro")
    return user


@pytest.fixture
def team_member_user(h):
    team = h.add_team()
    user = h.add_user(role="team_member", team_id=team.id)
    h.add_subscription(team_id=team.id, tier_id="team")
    user._team = team  # type: ignore[attr-defined]
    return user


@pytest.fixture
def team_admin_user(h):
    team = h.add_team()
    user = h.add_user(role="team_admin", team_id=team.id)
    h.add_subscription(team_id=team.id, tier_id="team")
    user._team = team  # type: ignore[attr-defined]
    return user


@pytest.fixture
def mock_celery(monkeypatch):
    from app.workers.celery_app import celery_app

    calls: list[dict] = []

    def _fake_send_task(name, kwargs=None, queue=None, **extra):
        calls.append({"name": name, "kwargs": kwargs, "queue": queue})

        class _Result:
            id = "mock-task-id"

        return _Result()

    monkeypatch.setattr(celery_app, "send_task", _fake_send_task)
    return calls


@pytest.fixture
def mock_analytics(monkeypatch):
    import app.services.upload_complete_service as ucs

    calls = {"drawing_uploaded": [], "free_limit_reached": []}
    monkeypatch.setattr(
        ucs, "emit_drawing_uploaded", lambda *a: calls["drawing_uploaded"].append(a)
    )
    monkeypatch.setattr(
        ucs,
        "emit_free_limit_reached",
        lambda *a: calls["free_limit_reached"].append(a),
    )
    return calls


def _pass_hash_check(h, user, sha256=_ABC_SHA256):
    """Drive a successful hash-check so POST /drawings is permitted."""
    resp = h.client.post(
        "/drawings/hash-check",
        json={"sha256_hash": sha256, "filename": "f.pdf", "size_bytes": 2048},
        headers=h.auth(user),
    )
    assert resp.status_code == 200, resp.text
    return resp


# ===========================================================================
# US-003 — hash-check
# ===========================================================================
def test_hash_check_blocked_returns_409(h, auth_user):
    # Seed the blocklist row directly in the test DB.
    from sqlalchemy import text

    h.session.execute(
        text("INSERT INTO file_hash_blocklist (sha256_hash, blocked_at, reason) "
             "VALUES (:h, :t, :r)"),
        {"h": _ABC_SHA256, "t": datetime.datetime.now(datetime.timezone.utc), "r": "malware"},
    )
    h.session.commit()

    resp = h.client.post(
        "/drawings/hash-check",
        json={"sha256_hash": _ABC_SHA256, "filename": "evil.pdf", "size_bytes": 10},
        headers=h.auth(auth_user),
    )
    assert resp.status_code == 409
    # No Drawing created.
    from app.db.models import Drawing

    assert h.session.query(Drawing).count() == 0


def test_hash_check_allowed_returns_200_and_sets_redis_flag(h, auth_user):
    resp = h.client.post(
        "/drawings/hash-check",
        json={"sha256_hash": _ABC_SHA256, "filename": "ok.pdf", "size_bytes": 10},
        headers=h.auth(auth_user),
    )
    assert resp.status_code == 200
    assert resp.json() == {"allowed": True, "drawing_id": None}

    from app.services.hash_check_service import pass_key

    async def _check():
        r = h.redis()
        try:
            return await r.get(pass_key(str(auth_user.id), _ABC_SHA256))
        finally:
            await r.aclose()

    assert asyncio.run(_check()) == "1"


def test_post_drawings_without_hash_check_returns_400(h, auth_user):
    resp = h.client.post(
        "/drawings",
        json={
            "filename": "x.pdf",
            "sha256_hash": _ABC_SHA256,
            "size_bytes": 10,
            "file_type": "pdf",
        },
        headers=h.auth(auth_user),
    )
    assert resp.status_code == 400


def test_post_drawings_after_hash_check_creates_drawing_and_presigned_url(h, auth_user):
    _pass_hash_check(h, auth_user)
    resp = h.client.post(
        "/drawings",
        json={
            "filename": "pump.pdf",
            "sha256_hash": _ABC_SHA256,
            "size_bytes": 2048,
            "file_type": "pdf",
        },
        headers=h.auth(auth_user),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "drawing_id" in body and "presigned_url" in body
    assert body["presigned_url"].startswith("http")

    from app.db.models import Drawing, StoredFile

    drawing = h.session.get(Drawing, uuid.UUID(body["drawing_id"]))
    assert drawing is not None
    assert drawing.processing_state == "Pending"
    assert drawing.owner_user_id == auth_user.id
    assert drawing.stored_file_id is not None
    assert h.session.get(StoredFile, drawing.stored_file_id) is not None


def test_presigned_url_expiry_matches_config(h, auth_user):
    from urllib.parse import parse_qs, urlparse

    from app.config import settings

    _pass_hash_check(h, auth_user)
    resp = h.client.post(
        "/drawings",
        json={
            "filename": "p.pdf",
            "sha256_hash": _ABC_SHA256,
            "size_bytes": 2048,
            "file_type": "pdf",
        },
        headers=h.auth(auth_user),
    )
    qs = parse_qs(urlparse(resp.json()["presigned_url"]).query)
    assert qs["X-Amz-Expires"] == [str(settings.PRESIGNED_URL_EXPIRY_SECONDS)]
    assert qs["X-Amz-Expires"] == ["900"]


def test_hash_check_unauthenticated_returns_401(h):
    resp = h.client.post(
        "/drawings/hash-check",
        json={"sha256_hash": _ABC_SHA256, "filename": "f.pdf", "size_bytes": 10},
    )
    assert resp.status_code == 401


def test_post_drawings_unauthenticated_returns_401(h):
    resp = h.client.post(
        "/drawings",
        json={
            "filename": "x.pdf",
            "sha256_hash": _ABC_SHA256,
            "size_bytes": 10,
            "file_type": "pdf",
        },
    )
    assert resp.status_code == 401


# ===========================================================================
# US-006 — list
# ===========================================================================
def test_get_drawings_paginated_default_25_desc(h, auth_user):
    base = datetime.datetime(2024, 1, 1, 0, 0, 0)
    for i in range(30):
        h.add_drawing(
            owner_user_id=auth_user.id,
            filename=f"d{i:02d}.pdf",
            uploaded_at=base + datetime.timedelta(days=i),
        )
    resp = h.client.get("/drawings", headers=h.auth(auth_user))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["drawings"]) == 25
    assert body["total"] == 30
    assert body["limit"] == 25
    # Newest first.
    times = [d["uploaded_at"] for d in body["drawings"]]
    assert times == sorted(times, reverse=True)


def test_get_drawings_user_role_sees_own_only(h, auth_user):
    other = h.add_user(role="user")
    h.add_drawing(owner_user_id=auth_user.id, filename="mine.pdf")
    h.add_drawing(owner_user_id=other.id, filename="theirs.pdf")
    resp = h.client.get("/drawings", headers=h.auth(auth_user))
    names = [d["filename"] for d in resp.json()["drawings"]]
    assert names == ["mine.pdf"]


def test_get_drawings_team_member_sees_team_drawings(h, team_member_user):
    team_id = team_member_user.team_id
    h.add_drawing(owner_team_id=team_id, filename="team1.pdf")
    h.add_drawing(owner_team_id=team_id, filename="team2.pdf")
    # A drawing owned by a different individual user is not visible.
    other = h.add_user(role="user")
    h.add_drawing(owner_user_id=other.id, filename="solo.pdf")
    resp = h.client.get("/drawings", headers=h.auth(team_member_user))
    names = {d["filename"] for d in resp.json()["drawings"]}
    assert names == {"team1.pdf", "team2.pdf"}


def test_get_drawings_team_admin_sees_team_drawings(h, team_admin_user):
    team_id = team_admin_user.team_id
    h.add_drawing(owner_team_id=team_id, filename="t1.pdf")
    resp = h.client.get("/drawings", headers=h.auth(team_admin_user))
    names = {d["filename"] for d in resp.json()["drawings"]}
    assert names == {"t1.pdf"}


def test_get_drawings_response_fields_present(h, auth_user):
    h.add_drawing(owner_user_id=auth_user.id, revision_label="Rev A")
    resp = h.client.get("/drawings", headers=h.auth(auth_user))
    record = resp.json()["drawings"][0]
    for field in (
        "id",
        "filename",
        "revision_label",
        "processing_state",
        "page_count",
        "estimated_symbol_count",
        "uploaded_at",
        "processed_at",
    ):
        assert field in record


def test_get_drawings_unauthenticated_returns_401(h):
    assert h.client.get("/drawings").status_code == 401


# ===========================================================================
# US-007 — search & filter
# ===========================================================================
def test_get_drawings_fts_search(h, auth_user):
    h.add_drawing(owner_user_id=auth_user.id, filename="pump station.pdf")
    h.add_drawing(owner_user_id=auth_user.id, filename="storage tank.pdf")
    resp = h.client.get("/drawings", params={"q": "pump"}, headers=h.auth(auth_user))
    names = [d["filename"] for d in resp.json()["drawings"]]
    assert names == ["pump station.pdf"]


def test_get_drawings_filter_by_state(h, auth_user):
    h.add_drawing(owner_user_id=auth_user.id, state="Failed", filename="f.pdf")
    h.add_drawing(owner_user_id=auth_user.id, state="Complete", filename="c.pdf")
    resp = h.client.get(
        "/drawings", params={"state": "Failed"}, headers=h.auth(auth_user)
    )
    names = [d["filename"] for d in resp.json()["drawings"]]
    assert names == ["f.pdf"]


def test_get_drawings_filter_by_date_range(h, auth_user):
    h.add_drawing(
        owner_user_id=auth_user.id,
        filename="old.pdf",
        uploaded_at=datetime.datetime(2023, 6, 1),
    )
    h.add_drawing(
        owner_user_id=auth_user.id,
        filename="in.pdf",
        uploaded_at=datetime.datetime(2024, 6, 1),
    )
    h.add_drawing(
        owner_user_id=auth_user.id,
        filename="future.pdf",
        uploaded_at=datetime.datetime(2025, 6, 1),
    )
    resp = h.client.get(
        "/drawings",
        params={"uploaded_after": "2024-01-01", "uploaded_before": "2024-12-31"},
        headers=h.auth(auth_user),
    )
    names = [d["filename"] for d in resp.json()["drawings"]]
    assert names == ["in.pdf"]


def test_get_drawings_combined_filters(h, auth_user):
    h.add_drawing(
        owner_user_id=auth_user.id, filename="rev2 pump.pdf", state="Complete"
    )
    h.add_drawing(owner_user_id=auth_user.id, filename="rev2 pump.pdf", state="Failed")
    h.add_drawing(owner_user_id=auth_user.id, filename="other.pdf", state="Complete")
    resp = h.client.get(
        "/drawings",
        params={"q": "rev2", "state": "Complete"},
        headers=h.auth(auth_user),
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["drawings"][0]["filename"] == "rev2 pump.pdf"
    assert body["drawings"][0]["processing_state"] == "Complete"


def test_get_drawings_pagination_params(h, auth_user):
    base = datetime.datetime(2024, 1, 1)
    for i in range(10):
        h.add_drawing(
            owner_user_id=auth_user.id,
            filename=f"d{i:02d}.pdf",
            uploaded_at=base + datetime.timedelta(days=i),
        )
    resp = h.client.get(
        "/drawings", params={"limit": 3, "offset": 2}, headers=h.auth(auth_user)
    )
    body = resp.json()
    assert body["limit"] == 3
    assert body["offset"] == 2
    assert len(body["drawings"]) == 3

    # limit is capped at 100.
    resp2 = h.client.get(
        "/drawings", params={"limit": 999}, headers=h.auth(auth_user)
    )
    assert resp2.json()["limit"] == 100


# ===========================================================================
# US-008 — state machine (pure-function ACs; SSE in test_drawings_sse.py)
# ===========================================================================
def test_state_machine_rejects_invalid_transition():
    from app.services.drawing_state_machine import (
        InvalidStateTransitionError,
        is_valid_transition,
    )

    assert is_valid_transition("Pending", "Queued") is True
    assert is_valid_transition("Pending", "Complete") is False
    assert issubclass(InvalidStateTransitionError, ValueError)


def test_state_machine_scan_failed_terminal(h, auth_user):
    from app.services.drawing_state_machine import (
        InvalidStateTransitionError,
        transition_drawing,
    )

    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Scan_Failed")
    for target in ("Queued", "Processing", "Complete", "Failed"):
        with pytest.raises(InvalidStateTransitionError):
            transition_drawing(drawing, target, h.session)


# ===========================================================================
# US-009 — retry & delete
# ===========================================================================
def test_retry_failed_drawing_transitions_to_queued_and_enqueues(
    h, auth_user, mock_celery
):
    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Failed")
    resp = h.client.post(
        f"/drawings/{drawing.id}/retry", headers=h.auth(auth_user)
    )
    assert resp.status_code == 202
    h.session.refresh(drawing)
    assert drawing.processing_state == "Queued"
    assert len(mock_celery) == 1
    assert mock_celery[0]["name"] == "ingest.process_drawing"
    assert mock_celery[0]["queue"] == "ingest"


def test_retry_scan_failed_returns_422(h, auth_user, mock_celery):
    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Scan_Failed")
    resp = h.client.post(f"/drawings/{drawing.id}/retry", headers=h.auth(auth_user))
    assert resp.status_code == 422
    assert mock_celery == []


def test_retry_reuses_stored_file(h, auth_user, mock_celery):
    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Failed")
    original_sf_id = drawing.stored_file_id
    from app.db.models import StoredFile

    before = h.session.query(StoredFile).count()
    resp = h.client.post(f"/drawings/{drawing.id}/retry", headers=h.auth(auth_user))
    assert resp.status_code == 202
    after = h.session.query(StoredFile).count()
    assert after == before  # no new StoredFile
    assert mock_celery[0]["kwargs"]["stored_file_id"] == str(original_sf_id)
    # storage_reference matches the original object key.
    sf = h.session.get(StoredFile, original_sf_id)
    assert mock_celery[0]["kwargs"]["storage_reference"] == sf.object_key


def test_retry_complete_drawing_returns_422(h, auth_user, mock_celery):
    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Complete")
    resp = h.client.post(f"/drawings/{drawing.id}/retry", headers=h.auth(auth_user))
    assert resp.status_code == 422
    assert mock_celery == []


def test_retry_wrong_owner_returns_403(h, auth_user):
    other = h.add_user(role="user")
    drawing = h.add_drawing(owner_user_id=other.id, state="Failed")
    resp = h.client.post(f"/drawings/{drawing.id}/retry", headers=h.auth(auth_user))
    assert resp.status_code == 403


def test_delete_by_team_member_returns_403(h, team_member_user):
    drawing = h.add_drawing(owner_team_id=team_member_user.team_id)
    resp = h.client.delete(f"/drawings/{drawing.id}", headers=h.auth(team_member_user))
    assert resp.status_code == 403


def test_delete_own_drawing_returns_204(h, auth_user):
    drawing = h.add_drawing(owner_user_id=auth_user.id)
    resp = h.client.delete(f"/drawings/{drawing.id}", headers=h.auth(auth_user))
    assert resp.status_code == 204
    from app.db.models import Drawing

    assert h.session.get(Drawing, drawing.id) is None


def test_delete_mid_processing_drawing_returns_204(h, auth_user):
    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Processing")
    resp = h.client.delete(f"/drawings/{drawing.id}", headers=h.auth(auth_user))
    assert resp.status_code == 204


def test_delete_by_team_admin_returns_204(h, team_admin_user):
    drawing = h.add_drawing(owner_team_id=team_admin_user.team_id)
    resp = h.client.delete(f"/drawings/{drawing.id}", headers=h.auth(team_admin_user))
    assert resp.status_code == 204


def test_delete_nonexistent_drawing_returns_404(h, auth_user):
    resp = h.client.delete(f"/drawings/{uuid.uuid4()}", headers=h.auth(auth_user))
    assert resp.status_code == 404


# ===========================================================================
# US-003 extended — upload-complete idempotency & state
# ===========================================================================
def test_upload_complete_initial_returns_202(h, auth_user, mock_celery, mock_analytics):
    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Pending")
    resp = h.client.post(
        f"/drawings/{drawing.id}/upload-complete", headers=h.auth(auth_user)
    )
    assert resp.status_code == 202
    h.session.refresh(drawing)
    assert drawing.processing_state == "Queued"
    assert len(mock_celery) == 1


def test_upload_complete_idempotent_on_queued_returns_200(
    h, auth_user, mock_celery, mock_analytics
):
    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Queued")
    resp = h.client.post(
        f"/drawings/{drawing.id}/upload-complete", headers=h.auth(auth_user)
    )
    assert resp.status_code == 200
    assert mock_celery == []  # no re-enqueue


def test_upload_complete_idempotent_on_complete_failed_returns_200(
    h, auth_user, mock_celery, mock_analytics
):
    for state in ("Complete", "Failed"):
        drawing = h.add_drawing(owner_user_id=auth_user.id, state=state)
        resp = h.client.post(
            f"/drawings/{drawing.id}/upload-complete", headers=h.auth(auth_user)
        )
        assert resp.status_code == 200
    assert mock_celery == []


def test_ingest_job_payload_contains_user_id(
    h, auth_user, mock_celery, mock_analytics
):
    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Pending")
    h.client.post(
        f"/drawings/{drawing.id}/upload-complete", headers=h.auth(auth_user)
    )
    payload = mock_celery[0]["kwargs"]
    assert payload["user_id"] == str(auth_user.id)
    assert payload["drawing_id"] == str(drawing.id)
    assert payload["stored_file_id"] == str(drawing.stored_file_id)
    assert set(payload.keys()) == {
        "drawing_id",
        "user_id",
        "stored_file_id",
        "storage_reference",
    }


# ===========================================================================
# US-010 — analytics events
# ===========================================================================
def test_drawing_uploaded_event_emitted_on_upload_complete(
    h, auth_user, mock_celery, mock_analytics
):
    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Pending")
    h.client.post(
        f"/drawings/{drawing.id}/upload-complete", headers=h.auth(auth_user)
    )
    assert len(mock_analytics["drawing_uploaded"]) == 1
    args = mock_analytics["drawing_uploaded"][0]
    assert args[0] == str(auth_user.id)
    assert args[1] == str(drawing.id)


def test_drawing_uploaded_not_emitted_on_idempotent_upload_complete(
    h, auth_user, mock_celery, mock_analytics
):
    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Queued")
    h.client.post(
        f"/drawings/{drawing.id}/upload-complete", headers=h.auth(auth_user)
    )
    assert mock_analytics["drawing_uploaded"] == []


def test_analytics_failure_does_not_surface_to_user(h, auth_user, mock_celery, monkeypatch):
    import app.services.upload_complete_service as ucs

    def _boom(*args):
        raise RuntimeError("posthog down")

    monkeypatch.setattr(ucs, "emit_drawing_uploaded", _boom)
    drawing = h.add_drawing(owner_user_id=auth_user.id, state="Pending")
    resp = h.client.post(
        f"/drawings/{drawing.id}/upload-complete", headers=h.auth(auth_user)
    )
    # Analytics blew up but the request still succeeds and the job enqueued.
    assert resp.status_code == 202
    assert len(mock_celery) == 1


def test_free_limit_reached_event_fired_before_job_enqueue(
    h, auth_user, mock_celery, mock_analytics
):
    # Three already enqueued this month → 4th is over the limit.
    drawings = [
        h.add_drawing(owner_user_id=auth_user.id, state="Pending") for _ in range(4)
    ]
    for d in drawings[:3]:
        r = h.client.post(
            f"/drawings/{d.id}/upload-complete", headers=h.auth(auth_user)
        )
        assert r.status_code == 202
    resp = h.client.post(
        f"/drawings/{drawings[3].id}/upload-complete", headers=h.auth(auth_user)
    )
    assert resp.status_code == 402
    assert len(mock_analytics["free_limit_reached"]) == 1
    # Only the first three enqueued; the 4th did not.
    assert len(mock_celery) == 3
    h.session.refresh(drawings[3])
    assert drawings[3].processing_state == "Pending"


def test_free_limit_reached_payload_includes_subscription_id(
    h, auth_user, mock_celery, mock_analytics
):
    from app.db.models import Subscription

    sub = h.session.query(Subscription).filter_by(user_id=auth_user.id).one()
    drawings = [
        h.add_drawing(owner_user_id=auth_user.id, state="Pending") for _ in range(4)
    ]
    for d in drawings:
        h.client.post(f"/drawings/{d.id}/upload-complete", headers=h.auth(auth_user))
    args = mock_analytics["free_limit_reached"][0]
    assert args[0] == str(auth_user.id)
    assert args[2] == str(sub.id)  # subscription_id resolved server-side


# ===========================================================================
# US-018 — free-tier monthly limit
# ===========================================================================
def test_free_tier_limit_blocks_4th_drawing_upload_complete(
    h, auth_user, mock_celery, mock_analytics
):
    drawings = [
        h.add_drawing(owner_user_id=auth_user.id, state="Pending") for _ in range(4)
    ]
    statuses = [
        h.client.post(
            f"/drawings/{d.id}/upload-complete", headers=h.auth(auth_user)
        ).status_code
        for d in drawings
    ]
    assert statuses == [202, 202, 202, 402]


def test_free_tier_counter_is_atomic_concurrent():
    from app.services.free_tier_counter import check_and_increment

    server = fakeredis.aioredis.FakeServer()

    async def _run():
        user_id = "concurrent-user"

        async def _one():
            r = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
            try:
                res = await check_and_increment(user_id, None, r, limit=3)
                return res.allowed
            finally:
                await r.aclose()

        results = await asyncio.gather(*[_one() for _ in range(10)])
        return results

    results = asyncio.run(_run())
    assert sum(1 for ok in results if ok) == 3  # exactly the limit succeed


def test_pro_tier_bypasses_monthly_limit(h, pro_user, mock_celery, mock_analytics):
    drawings = [
        h.add_drawing(owner_user_id=pro_user.id, state="Pending") for _ in range(5)
    ]
    statuses = [
        h.client.post(
            f"/drawings/{d.id}/upload-complete", headers=h.auth(pro_user)
        ).status_code
        for d in drawings
    ]
    assert statuses == [202, 202, 202, 202, 202]
    assert mock_analytics["free_limit_reached"] == []


def test_free_tier_counter_scoped_to_calendar_month():
    from app.services.free_tier_counter import check_and_increment

    server = fakeredis.aioredis.FakeServer()

    async def _run():
        r = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
        try:
            jan = datetime.datetime(2024, 1, 15, tzinfo=datetime.timezone.utc)
            feb = datetime.datetime(2024, 2, 15, tzinfo=datetime.timezone.utc)
            # Fill January to the limit.
            for _ in range(3):
                assert (
                    await check_and_increment("u", None, r, limit=3, now=jan)
                ).allowed
            assert not (
                await check_and_increment("u", None, r, limit=3, now=jan)
            ).allowed
            # February starts fresh.
            assert (
                await check_and_increment("u", None, r, limit=3, now=feb)
            ).allowed
        finally:
            await r.aclose()

    asyncio.run(_run())


def test_free_tier_counter_counts_enqueued_not_completed(
    h, auth_user, mock_celery, mock_analytics
):
    # Enqueue 3 (they stay Queued, never "complete"); the 4th is still blocked,
    # proving the counter tracks enqueued drawings, not completed ones.
    drawings = [
        h.add_drawing(owner_user_id=auth_user.id, state="Pending") for _ in range(4)
    ]
    for d in drawings[:3]:
        h.client.post(f"/drawings/{d.id}/upload-complete", headers=h.auth(auth_user))
    # None have transitioned past Queued.
    for d in drawings[:3]:
        h.session.refresh(d)
        assert d.processing_state == "Queued"
    resp = h.client.post(
        f"/drawings/{drawings[3].id}/upload-complete", headers=h.auth(auth_user)
    )
    assert resp.status_code == 402
