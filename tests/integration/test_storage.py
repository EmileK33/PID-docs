"""S1-C — Storage & Hash Utilities acceptance tests.

Run with:  cd backend && poetry run pytest ../tests/integration/test_storage.py -v

These tests prove the storage helpers in isolation — no sibling session (S1-A
models, S2-* APIs) needs to be merged. They are also self-contained at the
*infrastructure* level so they pass whether or not the Docker fixture stack is
up:

* **S3** — pre-signed URLs are signed entirely offline by botocore; the direct
  ``put_object`` / ``delete_object`` / ``get_object`` paths are exercised
  against an injected client double. No MinIO/AWS network call is made.
* **Blocklist** — the raw-SQL lookup runs against an in-memory SQLite database
  with the same ``file_hash_blocklist`` schema S1-A's migration 0001 creates
  (``CREATE TABLE IF NOT EXISTS`` — compatible columns + PK), so the test owns
  no dependency on a live Postgres or on S1-A being merged.

The module self-configures ``sys.path`` so ``app`` (rooted at ``backend/``) is
importable, and sets every §1.12 "Refuse to start" env var *before* importing
``app`` so ``app.config`` does not ``sys.exit(1)`` at import time.
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# --- make `app` (backend/app) importable -----------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(BACKEND), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- §1.12 env contract: set BEFORE importing app code ----------------------
# conftest.py provides most of these; ML_MODEL_S3_KEY / ODA_CONVERTER_PATH are
# REQUIRED by app.config but not seeded there, and we pin the presigned expiry
# to the documented 900 s default so the hard-constraint assertions are stable.
_REQUIRED_ENV = {
    "DATABASE_URL": "postgresql://u:p@localhost:5432/pid",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_BUCKET_NAME": "test-bucket",
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

# NOTE: do not mutate S3_ENDPOINT_URL here — the shared conftest s3_client
# fixture (used by the smoke suite in the full integration run) reads it. The
# pre-signed URL tests build their own endpoint-free boto3 client instead.

# Deferred app imports: a module-level `import app...` would pull app.* into
# sys.modules during *collection*, breaking the harness smoke suite's
# `test_smoke_does_not_import_app` (which runs earlier in the same session).
# The autouse `_deferred_app_import` fixture binds these names at test-run time.
settings = None  # type: ignore[assignment]
s3_client_mod = None  # type: ignore[assignment]
SSE_ALGORITHM = None  # type: ignore[assignment]
compute_sha256_stream = None  # type: ignore[assignment]
delete_object = None  # type: ignore[assignment]
drawing_object_key = None  # type: ignore[assignment]
export_object_key = None  # type: ignore[assignment]
generate_presigned_get_url = None  # type: ignore[assignment]
generate_presigned_put_url = None  # type: ignore[assignment]
get_s3_client = None  # type: ignore[assignment]
is_hash_blocked = None  # type: ignore[assignment]
put_object = None  # type: ignore[assignment]
verify_object_sha256 = None  # type: ignore[assignment]

_DEFERRED_NAMES = (
    "SSE_ALGORITHM",
    "compute_sha256_stream",
    "delete_object",
    "drawing_object_key",
    "export_object_key",
    "generate_presigned_get_url",
    "generate_presigned_put_url",
    "get_s3_client",
    "is_hash_blocked",
    "put_object",
    "verify_object_sha256",
)

# Known SHA-256 test vector: hash of b"abc".
_ABC = b"abc"
_ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

BUCKET = "test-bucket"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _deferred_app_import():
    """Bind the app.storage exports onto module globals at test-run time.

    Keeps app.* out of sys.modules during collection so the smoke suite stays
    green in the combined integration session (see the note above).
    """
    import app.storage as _storage
    from app.config import settings as _settings
    from app.storage import s3_client as _s3_client_mod

    g = globals()
    g["settings"] = _settings
    g["s3_client_mod"] = _s3_client_mod
    for _name in _DEFERRED_NAMES:
        g[_name] = getattr(_storage, _name)
    yield
@pytest.fixture()
def signing_client():
    """A real, offline boto3 S3 client (SigV4) for pre-signed URL assertions."""
    import boto3
    from botocore.client import Config

    return boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="secretkey",
        config=Config(signature_version="s3v4"),
    )


@pytest.fixture()
def fake_client():
    """An injectable S3 client double for the direct operation paths."""
    return MagicMock(name="s3_client")


@pytest.fixture()
def blocklist_session():
    """In-memory SQLite session with the canonical file_hash_blocklist table.

    StaticPool keeps the one in-memory connection alive so the DDL and the
    session share a database. The DDL mirrors S1-A migration 0001's columns +
    PK and is valid on both SQLite and Postgres (CURRENT_TIMESTAMP, not NOW()).
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS file_hash_blocklist ("
                "  sha256_hash VARCHAR PRIMARY KEY,"
                "  blocked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                "  reason VARCHAR NOT NULL"
                ")"
            )
        )
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _insert_blocked(session, sha256_hash: str, reason: str = "malware") -> None:
    session.execute(
        text("INSERT INTO file_hash_blocklist (sha256_hash, reason) VALUES (:h, :r)"),
        {"h": sha256_hash, "r": reason},
    )
    session.commit()


# ---------------------------------------------------------------------------
# Blocklist (§1.4 rule 1)
# ---------------------------------------------------------------------------
def test_is_hash_blocked_returns_true_when_present(blocklist_session):
    _insert_blocked(blocklist_session, _ABC_SHA256)
    assert is_hash_blocked(_ABC_SHA256, db=blocklist_session) is True


def test_is_hash_blocked_returns_false_when_absent(blocklist_session):
    assert is_hash_blocked("0" * 64, db=blocklist_session) is False


def test_is_hash_blocked_normalizes_uppercase_input(blocklist_session):
    # Stored lowercase (as hexdigest() produces); client sends uppercase.
    _insert_blocked(blocklist_session, _ABC_SHA256)
    assert is_hash_blocked(_ABC_SHA256.upper(), db=blocklist_session) is True


# ---------------------------------------------------------------------------
# Pre-signed PUT URL (§1.9 expiry, §1.7 SSE)
# ---------------------------------------------------------------------------
def test_presigned_put_url_uses_configured_expiry(signing_client):
    assert settings.PRESIGNED_URL_EXPIRY_SECONDS == 900
    url = generate_presigned_put_url(
        BUCKET, "drawings/d1/original.pdf", 1234, "application/pdf",
        client=signing_client,
    )
    qs = parse_qs(urlparse(url).query)
    assert qs["X-Amz-Expires"] == [str(settings.PRESIGNED_URL_EXPIRY_SECONDS)]
    assert qs["X-Amz-Expires"] == ["900"]


def test_presigned_put_url_signs_sse_aes256(signing_client):
    url = generate_presigned_put_url(
        BUCKET, "drawings/d1/original.pdf", 1234, "application/pdf",
        client=signing_client,
    )
    qs = parse_qs(urlparse(url).query)
    # The SSE header is committed to the signature via SignedHeaders: the URL
    # is only valid if the client sends `x-amz-server-side-encryption: AES256`,
    # so an unencrypted PUT with this URL fails the signature check.
    signed_headers = qs["X-Amz-SignedHeaders"][0].lower()
    assert "x-amz-server-side-encryption" in signed_headers


def test_presigned_put_expiry_param_propagated_to_boto3(fake_client):
    fake_client.generate_presigned_url.return_value = "https://example/url"
    generate_presigned_put_url(
        BUCKET, "k", 10, "application/pdf", client=fake_client
    )
    _, kwargs = fake_client.generate_presigned_url.call_args
    assert kwargs["ExpiresIn"] == settings.PRESIGNED_URL_EXPIRY_SECONDS
    assert kwargs["ExpiresIn"] == 900
    # And the signed params commit to SSE.
    assert kwargs["Params"]["ServerSideEncryption"] == "AES256"


# ---------------------------------------------------------------------------
# Pre-signed GET URL (§1.9 expiry)
# ---------------------------------------------------------------------------
def test_presigned_get_url_uses_configured_expiry(signing_client):
    url = generate_presigned_get_url(
        BUCKET, "exports/e1.csv", client=signing_client
    )
    qs = parse_qs(urlparse(url).query)
    assert qs["X-Amz-Expires"] == [str(settings.PRESIGNED_URL_EXPIRY_SECONDS)]
    assert qs["X-Amz-Expires"] == ["900"]


# ---------------------------------------------------------------------------
# Streaming SHA-256
# ---------------------------------------------------------------------------
def test_compute_sha256_stream_known_value():
    assert compute_sha256_stream(io.BytesIO(_ABC)) == _ABC_SHA256


def test_compute_sha256_stream_chunked_no_full_load():
    """Hash is computed via repeated bounded reads, never one full read."""

    class _TrackingReader:
        def __init__(self, data: bytes):
            self._buf = io.BytesIO(data)
            self.read_sizes: list[int] = []
            self.largest_chunk = 0

        def read(self, n: int = -1) -> bytes:
            self.read_sizes.append(n)
            chunk = self._buf.read(n)
            self.largest_chunk = max(self.largest_chunk, len(chunk))
            return chunk

    data = b"x" * 10
    reader = _TrackingReader(data)
    chunk = 4

    digest = compute_sha256_stream(reader, chunk_size=chunk)

    assert digest == hashlib.sha256(data).hexdigest()
    # Every read request is bounded by chunk_size...
    assert reader.read_sizes and all(n == chunk for n in reader.read_sizes)
    # ...and no single read pulled more than a chunk into memory.
    assert reader.largest_chunk <= chunk
    # 10 bytes / 4 => at least 3 data reads + 1 terminating empty read.
    assert len(reader.read_sizes) >= 4


# ---------------------------------------------------------------------------
# verify_object_sha256 (§1.4 rule 3)
# ---------------------------------------------------------------------------
def test_verify_object_sha256_match(fake_client):
    fake_client.get_object.return_value = {"Body": io.BytesIO(_ABC)}
    assert verify_object_sha256(BUCKET, "k", _ABC_SHA256, client=fake_client) is True


def test_verify_object_sha256_mismatch_returns_false(fake_client):
    fake_client.get_object.return_value = {"Body": io.BytesIO(b"different")}
    assert verify_object_sha256(BUCKET, "k", _ABC_SHA256, client=fake_client) is False


def test_verify_object_sha256_lowercase_normalization(fake_client):
    fake_client.get_object.return_value = {"Body": io.BytesIO(_ABC)}
    # Client supplies the expected hash uppercased; must still match.
    assert (
        verify_object_sha256(BUCKET, "k", _ABC_SHA256.upper(), client=fake_client)
        is True
    )


def test_verify_object_sha256_missing_object_returns_false(fake_client):
    fake_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "missing"}}, "GetObject"
    )
    assert verify_object_sha256(BUCKET, "k", _ABC_SHA256, client=fake_client) is False


# ---------------------------------------------------------------------------
# Object-key conventions
# ---------------------------------------------------------------------------
def test_drawing_object_key_format():
    assert drawing_object_key("abc-123", "pdf") == "drawings/abc-123/original.pdf"


def test_export_object_key_format():
    assert export_object_key("exp-9", "xlsx") == "exports/exp-9.xlsx"


# ---------------------------------------------------------------------------
# Direct object operations (§1.7 SSE, GDPR delete, no public ACL)
# ---------------------------------------------------------------------------
def test_put_object_sets_sse_aes256(fake_client):
    put_object(BUCKET, "k", b"data", "application/pdf", client=fake_client)
    _, kwargs = fake_client.put_object.call_args
    assert kwargs["ServerSideEncryption"] == "AES256"
    assert kwargs["Bucket"] == BUCKET and kwargs["Key"] == "k"


def test_delete_object_removes_object(fake_client):
    delete_object(BUCKET, "k", client=fake_client)
    fake_client.delete_object.assert_called_once_with(Bucket=BUCKET, Key="k")


def test_no_method_sets_public_acl():
    """No storage source ever sets ACL=public-read or any public ACL (§1.7)."""
    from app.storage import presigned as presigned_mod

    for mod in (s3_client_mod, presigned_mod):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "public-read" not in src.lower()
        # boto3 sets an ACL via an `ACL=` parameter; assert none is used.
        assert "ACL=" not in src


# ---------------------------------------------------------------------------
# Credential resolution (§1.12)
# ---------------------------------------------------------------------------
def test_s3_client_iam_role_fallback():
    """No explicit creds -> empty kwargs -> boto3 default chain (IAM role)."""
    no_creds = SimpleNamespace(AWS_ACCESS_KEY_ID=None, AWS_SECRET_ACCESS_KEY=None)
    assert s3_client_mod._credentials_kwargs(no_creds) == {}


def test_s3_client_uses_explicit_credentials():
    both = SimpleNamespace(AWS_ACCESS_KEY_ID="AKID", AWS_SECRET_ACCESS_KEY="SECRET")
    kwargs = s3_client_mod._credentials_kwargs(both)
    assert kwargs == {
        "aws_access_key_id": "AKID",
        "aws_secret_access_key": "SECRET",
    }


def test_get_s3_client_constructs_client():
    """Smoke: the factory returns a usable S3 client bound to the region."""
    client = get_s3_client()
    assert client.meta.service_model.service_name == "s3"
    assert client.meta.region_name == settings.S3_REGION


def test_sse_algorithm_is_aes256():
    assert SSE_ALGORITHM == "AES256"
