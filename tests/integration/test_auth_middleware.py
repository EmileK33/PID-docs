"""Integration tests for the S1-B auth layer.

Covers JWT verification, the FastAPI auth dependencies / ownership gates, the
Redis brute-force lockout, and the Supabase Admin client wrapper.

SELF-CONTAINED re backing services. The authoritative ``session-tests`` CI gate
runs this file's ``test.cmd`` WITHOUT booting the Docker fixture stack
(Postgres/Redis/MinIO) — only the separate ``integration`` workflow brings them
up. So this suite must not open a real DB/Redis connection:

* the ``token_invalidated_at`` / ``deleted_at`` user-state lookup is served by a
  tiny in-memory fake that honours the exact SQL row contract the middleware
  depends on (``get_db`` is overridden), and
* the brute-force counter runs against ``fakeredis`` (in-process) by patching
  ``brute_force._client``.

It therefore depends only on S0-A + S0-B: no S1-A models, no S1-D Redis wrapper,
no S1-E analytics, and no live services. ``app`` modules are imported *inside*
fixtures/tests (never at import time) so the sibling S0-B smoke assertion
``test_smoke_does_not_import_app`` stays green when the whole ``tests/integration``
suite runs together.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

# NOTE: the FastAPI symbols above MUST be module-level imports. The test routes
# in `app_client` use `from __future__ import annotations`, so FastAPI resolves
# their string annotations (e.g. ``request: Request``) against this module's
# globals — a fixture-local import would leave ``Request`` unresolved and FastAPI
# would treat ``request`` as a query param (HTTP 422). `app.*` imports stay lazy
# (inside fixtures) so the sibling smoke test never sees app modules imported.

# Make `backend/app` importable. tests/integration/test_auth_middleware.py
# -> parents[2] == repo root; the app package lives under repo_root/backend.
_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# S0-A's config.py marks ML_MODEL_S3_KEY / ODA_CONVERTER_PATH as REQUIRED ("refuse
# to start"), but the S0-B harness conftest only seeds the auth/storage subset.
# Seed the remainder here — at import time, before any `app.config` import — so
# the settings singleton can load under this suite. setdefault leaves any value
# the harness or CI already provided untouched.
os.environ.setdefault("ML_MODEL_S3_KEY", "models/test-model.onnx")
os.environ.setdefault("ODA_CONVERTER_PATH", "/usr/bin/ODAFileConverter")

# Must match the harness SUPABASE_URL (tests/integration/conftest.py default).
SUPABASE_URL = "https://test.supabase.co"
SERVICE_ROLE_KEY = "test-service-role-key-do-not-use"

# drawing_id -> (owner_user_id, owner_team_id); populated per-test, read by the
# resource resolver registered on the test app.
RESOURCES: dict[str, tuple[uuid.UUID | None, uuid.UUID | None]] = {}


def _run(coro):
    """Drive a coroutine to completion from a synchronous test."""
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# Key material + settings injection
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def rsa_keypair():
    """Ephemeral RS256 keypair (PEM strings) for signing/verifying test tokens."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture(scope="session", autouse=True)
def _configure_settings(rsa_keypair):
    """Inject the test public key + Supabase config into the settings singleton.

    Verification reads these at call time, so overriding the singleton is enough;
    no env reload is required.
    """
    from app.config import settings

    _, public_pem = rsa_keypair
    object.__setattr__(settings, "JWT_RS256_PUBLIC_KEY", public_pem)
    object.__setattr__(settings, "SUPABASE_URL", SUPABASE_URL)
    object.__setattr__(settings, "SUPABASE_SERVICE_ROLE_KEY", SERVICE_ROLE_KEY)
    yield


@pytest.fixture
def make_token(rsa_keypair):
    """Factory signing RS256 (or, for negative tests, other-alg) test tokens."""
    private_pem, _ = rsa_keypair

    def _make(
        user_id,
        *,
        iat: datetime | None = None,
        exp: datetime | None = None,
        iss: str = SUPABASE_URL,
        aud: str = "authenticated",
        alg: str = "RS256",
        email: str = "user@example.com",
        key: str | None = None,
    ) -> str:
        now = datetime.now(tz=timezone.utc)
        iat = iat or now
        exp = exp or (now + timedelta(hours=1))
        payload = {
            "sub": str(user_id),
            "email": email,
            "iss": iss,
            "aud": aud,
            "iat": int(iat.timestamp()),
            "exp": int(exp.timestamp()),
        }
        if alg == "none":
            return jwt.encode(payload, key=None, algorithm="none")
        if alg == "HS256":
            secret = key or ("shared-symmetric-secret-" + "x" * 32)
            return jwt.encode(payload, secret, algorithm="HS256")
        return jwt.encode(payload, key or private_pem, algorithm="RS256")

    return _make


# --------------------------------------------------------------------------- #
# In-memory DB double honouring the middleware's user-state SQL contract
# --------------------------------------------------------------------------- #
class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeDB:
    """Stands in for the SQLAlchemy ``Session``.

    The middleware issues exactly one query:
    ``SELECT token_invalidated_at, deleted_at, team_id, role FROM "user"
    WHERE id = :id``. We key user rows by UUID and return the 4-tuple in that
    column order (or ``None`` for an unknown id), using real Python
    datetime/UUID objects so the middleware's comparisons run unchanged.
    """

    def __init__(self):
        self.users: dict[uuid.UUID, tuple] = {}

    def execute(self, statement, params=None):  # noqa: ARG002 - statement ignored
        params = params or {}
        return _FakeResult(self.users.get(params.get("id")))


@pytest.fixture
def fake_db():
    return _FakeDB()


@pytest.fixture
def make_user(fake_db):
    """Insert a user row into the fake DB and return its id."""

    def _insert(
        *,
        role: str = "user",
        team_id: uuid.UUID | None = None,
        deleted_at: datetime | None = None,
        token_invalidated_at: datetime | None = None,
        user_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        uid = user_id or uuid.uuid4()
        # Column order mirrors the middleware SELECT.
        fake_db.users[uid] = (token_invalidated_at, deleted_at, team_id, role)
        return uid

    return _insert


# --------------------------------------------------------------------------- #
# FastAPI test app + client
# --------------------------------------------------------------------------- #
@pytest.fixture
def app_client(fake_db):
    """A TestClient over a minimal app exercising the auth dependencies."""
    from app.auth.dependencies import get_current_user, require_permission
    from app.db.session import get_db

    RESOURCES.clear()

    app = FastAPI()

    def drawing_resolver(request: Request):
        return RESOURCES.get(request.path_params["drawing_id"], (None, None))

    @app.get("/_test/protected")
    def protected(request: Request, user=Depends(get_current_user)):
        # Prove the dependency populated request.state.user with the identity.
        assert request.state.user is user
        su = request.state.user
        return {
            "id": str(su.id),
            "email": su.email,
            "role": su.role,
            "team_id": str(su.team_id) if su.team_id else None,
        }

    @app.get(
        "/_test/drawings/{drawing_id}",
        dependencies=[Depends(require_permission("drawing_view", drawing_resolver))],
    )
    def view_drawing(drawing_id: str):
        return {"ok": True}

    @app.delete(
        "/_test/drawings/{drawing_id}",
        dependencies=[Depends(require_permission("drawing_delete", drawing_resolver))],
    )
    def delete_drawing(drawing_id: str):
        return {"ok": True}

    @app.post(
        "/_test/team/manage",
        dependencies=[Depends(require_permission("team_manage", lambda r: (None, None)))],
    )
    def manage_team():
        return {"ok": True}

    app.dependency_overrides[get_db] = lambda: fake_db
    return TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# JWT / middleware: authentication
# --------------------------------------------------------------------------- #
def test_accepts_valid_rs256_token_and_populates_request_state(app_client, make_user, make_token):
    uid = make_user(role="user")
    token = make_token(uid, email="alice@example.com")

    resp = app_client.get("/_test/protected", headers=_auth(token))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "id": str(uid),
        "email": "alice@example.com",
        "role": "user",
        "team_id": None,
    }


def test_returns_401_when_authorization_header_missing(app_client):
    assert app_client.get("/_test/protected").status_code == 401


def test_returns_401_for_malformed_jwt(app_client):
    assert app_client.get("/_test/protected", headers=_auth("not-a-real-jwt")).status_code == 401


def test_rejects_alg_none_token(app_client, make_user, make_token):
    uid = make_user()
    token = make_token(uid, alg="none")
    assert app_client.get("/_test/protected", headers=_auth(token)).status_code == 401


def test_rejects_hs256_token(app_client, make_user, make_token):
    uid = make_user()
    token = make_token(uid, alg="HS256")
    assert app_client.get("/_test/protected", headers=_auth(token)).status_code == 401


def test_returns_401_for_expired_token(app_client, make_user, make_token):
    uid = make_user()
    past = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    token = make_token(uid, iat=past, exp=past + timedelta(minutes=1))
    assert app_client.get("/_test/protected", headers=_auth(token)).status_code == 401


def test_returns_401_for_wrong_issuer(app_client, make_user, make_token):
    uid = make_user()
    token = make_token(uid, iss="https://evil.example.com")
    assert app_client.get("/_test/protected", headers=_auth(token)).status_code == 401


def test_rejects_token_issued_before_token_invalidated_at(app_client, make_user, make_token):
    now = datetime.now(tz=timezone.utc)
    uid = make_user(token_invalidated_at=now)
    # Token was issued an hour before the invalidation timestamp → rejected.
    token = make_token(uid, iat=now - timedelta(hours=1))
    assert app_client.get("/_test/protected", headers=_auth(token)).status_code == 401


def test_rejects_soft_deleted_user(app_client, make_user, make_token):
    uid = make_user(deleted_at=datetime.now(tz=timezone.utc))
    token = make_token(uid)
    assert app_client.get("/_test/protected", headers=_auth(token)).status_code == 401


# --------------------------------------------------------------------------- #
# Authorization: ownership + role-permission matrix (§1.3, §1.5)
# --------------------------------------------------------------------------- #
def test_returns_403_on_cross_user_resource_access(app_client, make_user, make_token):
    uid = make_user(role="user")
    token = make_token(uid)
    # Drawing owned by a different user; role "user" has drawing_view='own'.
    RESOURCES["d-cross"] = (uuid.uuid4(), None)
    assert app_client.get("/_test/drawings/d-cross", headers=_auth(token)).status_code == 403


def test_denies_team_member_drawing_delete(app_client, make_user, make_token):
    team_id = uuid.uuid4()
    uid = make_user(role="team_member", team_id=team_id)
    token = make_token(uid)
    RESOURCES["d-team"] = (None, team_id)
    assert app_client.delete("/_test/drawings/d-team", headers=_auth(token)).status_code == 403


def test_allows_team_admin_drawing_delete(app_client, make_user, make_token):
    team_id = uuid.uuid4()
    uid = make_user(role="team_admin", team_id=team_id)
    token = make_token(uid)
    RESOURCES["d-team"] = (None, team_id)
    assert app_client.delete("/_test/drawings/d-team", headers=_auth(token)).status_code == 200


def test_allows_team_member_view_of_team_drawing(app_client, make_user, make_token):
    team_id = uuid.uuid4()
    uid = make_user(role="team_member", team_id=team_id)
    token = make_token(uid)
    RESOURCES["d-team"] = (None, team_id)
    assert app_client.get("/_test/drawings/d-team", headers=_auth(token)).status_code == 200


def test_denies_user_role_team_manage(app_client, make_user, make_token):
    uid = make_user(role="user")
    token = make_token(uid)
    assert app_client.post("/_test/team/manage", headers=_auth(token)).status_code == 403


# --------------------------------------------------------------------------- #
# Brute-force lockout (§1.9, §1.11, US-002) — fakeredis, no live service
# --------------------------------------------------------------------------- #
@pytest.fixture
def fake_redis(monkeypatch):
    """Patch brute_force._client to use an in-process fakeredis server.

    Returns a synchronous client bound to the same server so tests can assert
    TTLs / key existence directly.
    """
    import fakeredis
    import fakeredis.aioredis

    from app.auth import brute_force

    server = fakeredis.FakeServer()

    def _client():
        return fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)

    monkeypatch.setattr(brute_force, "_client", _client)
    return fakeredis.FakeStrictRedis(server=server, decode_responses=True)


def _bf_key(email: str) -> str:
    return f"brute_force:{email.lower()}"


def test_locks_out_after_5_failed_attempts(fake_redis):
    from app.auth.brute_force import is_locked_out, record_login_failure

    email = "lockme@example.com"
    for _ in range(4):
        _run(record_login_failure(email))
    assert _run(is_locked_out(email)) is False  # 4 failures: not yet locked

    fifth = _run(record_login_failure(email))
    assert fifth == 5
    # 5 failures reached the threshold → the 6th attempt is rejected first.
    assert _run(is_locked_out(email)) is True


def test_sets_900s_ttl_on_first_failure(fake_redis):
    from app.auth.brute_force import record_login_failure

    email = "ttl@example.com"
    count = _run(record_login_failure(email))
    assert count == 1

    ttl = fake_redis.ttl(_bf_key(email))
    assert 890 <= ttl <= 900  # set to 900 on the first failure


def test_uses_lowercased_email_in_brute_force_key(fake_redis):
    from app.auth.brute_force import record_login_failure

    mixed = "MixedCase@Example.COM"
    _run(record_login_failure(mixed))
    assert fake_redis.exists(_bf_key(mixed)) == 1
    assert fake_redis.exists(f"brute_force:{mixed}") == 0


def test_clears_brute_force_counter_on_success_below_threshold(fake_redis):
    from app.auth.brute_force import clear_failures, is_locked_out, record_login_failure

    email = "clearme@example.com"
    _run(record_login_failure(email))
    _run(record_login_failure(email))
    assert _run(is_locked_out(email)) is False

    _run(clear_failures(email))
    assert fake_redis.exists(_bf_key(email)) == 0


# --------------------------------------------------------------------------- #
# Supabase Admin client wrapper (Rule #12, §1.7) — httpx MockTransport
# --------------------------------------------------------------------------- #
def _mock_supabase(monkeypatch, handler):
    """Point supabase_client._build_client at an httpx MockTransport."""
    from app.auth import supabase_client

    def _factory():
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url=SUPABASE_URL,
            headers=supabase_client._admin_headers(),
        )

    monkeypatch.setattr(supabase_client, "_build_client", _factory)


def test_admin_sign_out_calls_supabase_logout_endpoint(monkeypatch):
    from app.auth.supabase_client import admin_sign_out

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(204)

    _mock_supabase(monkeypatch, handler)

    user_id = uuid.uuid4()
    _run(admin_sign_out(user_id))

    assert len(captured) == 1
    req = captured[0]
    assert req.method == "POST"
    assert req.url.path == f"/auth/v1/admin/users/{user_id}/logout"
    assert req.headers["authorization"] == f"Bearer {SERVICE_ROLE_KEY}"


def test_find_user_by_email_returns_user_or_none_never_merges(monkeypatch):
    from app.auth.supabase_client import find_user_by_email

    existing = {"id": str(uuid.uuid4()), "email": "exists@example.com"}

    def handler(request: httpx.Request) -> httpx.Response:
        email = request.url.params.get("email")
        if email == "exists@example.com":
            return httpx.Response(200, json={"users": [existing]})
        return httpx.Response(200, json={"users": []})

    _mock_supabase(monkeypatch, handler)

    found = _run(find_user_by_email("exists@example.com"))
    assert found == existing  # returns the record verbatim — no merge performed

    missing = _run(find_user_by_email("nobody@example.com"))
    assert missing is None


# --------------------------------------------------------------------------- #
# Role-permission matrix is a byte-for-byte mirror of §1.3
# --------------------------------------------------------------------------- #
def test_role_permissions_matrix_matches_spec():
    from app.auth.permissions import ROLE_PERMISSIONS

    expected = {
        "user": {
            "drawing_upload": True,
            "drawing_view": "own",
            "drawing_delete": "own",
            "drawing_retry": "own",
            "symbol_correct": "own",
            "export_initiate": "own",
            "team_manage": False,
            "billing_manage": True,
            "gdpr_delete_account": True,
        },
        "team_member": {
            "drawing_upload": True,
            "drawing_view": "team",
            "drawing_delete": False,
            "drawing_retry": "team",
            "symbol_correct": "team",
            "export_initiate": "team",
            "team_manage": False,
            "billing_manage": False,
            "gdpr_delete_account": True,
        },
        "team_admin": {
            "drawing_upload": True,
            "drawing_view": "team",
            "drawing_delete": "team",
            "drawing_retry": "team",
            "symbol_correct": "team",
            "export_initiate": "team",
            "team_manage": True,
            "billing_manage": True,
            "gdpr_delete_account": True,
        },
    }
    assert ROLE_PERMISSIONS == expected
