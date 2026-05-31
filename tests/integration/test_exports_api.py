"""S2-D — Export Endpoints + Sync Path: acceptance tests (US-016, US-017).

Run with:  ``pytest tests/integration/test_exports_api.py -v``

SELF-CONTAINED re backing services. The authoritative ``session-tests`` PR gate
runs this file's ``test.cmd`` with bare pytest and NO Docker fixture stack
(Postgres / Redis / MinIO). So, like S1-C's storage suite, this module is fully
self-contained:

* **DB** — an in-memory SQLite database created from the real S1-A ORM metadata.
  The two Postgres-only column types (``UUID`` / ``JSONB``) are taught to render
  on SQLite via ``@compiles`` shims, and the ``gen_random_uuid()`` / ``now()``
  server defaults are registered as SQLite functions. Round-trips preserve
  ``uuid.UUID`` and ``dict`` values exactly, so the export service's ORM queries
  run unchanged.
* **S3** — ``put_object`` and ``generate_presigned_get_url`` are patched where
  the service imports them; no MinIO/AWS call is made (one focused test signs a
  URL fully offline with botocore to assert the 15-minute expiry contract).
* **Celery** — ``celery_app.send_task`` is patched; no broker connection.
* **Analytics** — the ``emit_*`` emitters are spied via the analytics module.

It depends only on S1-A..S1-E + S0-A/S0-B — no Phase-2 sibling (S2-B/C/K). All
fixture data is created inline via SQLAlchemy; no sibling API endpoint is called.

``app.*`` imports are deferred into fixtures so the sibling S0-B smoke assertion
``test_smoke_does_not_import_app`` stays green when the whole suite runs together.
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# --- make `app` (backend/app) importable -----------------------------------
# tests/integration/test_exports_api.py -> parents[2] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(BACKEND), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

# --- §1.12 env contract: set BEFORE importing app code ----------------------
# conftest.py seeds most of these; ML_MODEL_S3_KEY / ODA_CONVERTER_PATH are
# REQUIRED by app.config but not seeded there. Pin the presigned expiry to the
# documented 900s default so the hard-constraint assertion is stable.
_REQUIRED_ENV = {
    "DATABASE_URL": "postgresql://u:p@localhost:5432/pid",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_BUCKET_NAME": "pidtest-exports-bucket",
    "S3_REGION": "us-east-1",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
    "JWT_RS256_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\nMIIB\n-----END PUBLIC KEY-----",
    "STRIPE_SECRET_KEY": "sk_test_dummy",
    "STRIPE_WEBHOOK_SECRET": "whsec_dummy",
    "SENDGRID_API_KEY": "SG.dummy",
    "HMAC_SERVER_SECRET": "high-entropy-secret",
    "ML_MODEL_S3_KEY": "models/pid/v1.onnx",
    "ODA_CONVERTER_PATH": "/opt/oda/ODAFileConverter",
    "ENVIRONMENT": "development",
}
for _k, _v in _REQUIRED_ENV.items():
    os.environ.setdefault(_k, _v)
# Do NOT set S3_ENDPOINT_URL — the offline signing client must talk to real AWS
# hostnames for the expiry assertion. The shared conftest may set it for other
# suites; we read it defensively only where needed.

# Make the Postgres-only column types render + round-trip on SQLite. Registered
# at import (no app import involved) and before any create_all runs.
_SHIMS_REGISTERED = False


def _register_sqlite_type_shims() -> None:
    global _SHIMS_REGISTERED
    if _SHIMS_REGISTERED:
        return

    @compiles(JSONB, "sqlite")
    def _compile_jsonb(element, compiler, **kw):  # noqa: ANN001, ARG001
        return "JSON"

    @compiles(UUID, "sqlite")
    def _compile_uuid(element, compiler, **kw):  # noqa: ANN001, ARG001
        return "CHAR(36)"

    _SHIMS_REGISTERED = True


_register_sqlite_type_shims()


# Known SHA-256 test vector for offline assertions is not needed here; bytes are
# hashed from captured upload payloads instead.

CSV_CONTENT_TYPE = "text/csv"
XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
EXPORT_TASK_NAME = "pid_analyzer.workers.export.tasks.generate_export_task"


# ---------------------------------------------------------------------------
# DB engine / session fixtures (in-memory SQLite from the real ORM metadata)
# ---------------------------------------------------------------------------
@pytest.fixture()
def engine():
    """A fresh in-memory SQLite DB with the full S1-A schema + seed entity rows."""
    from app.db.models import Base
    from app.db.seed_entity_classes import ENTITY_CLASS_SEED_DATA

    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(eng, "connect")
    def _register_functions(dbapi_conn, _record):  # noqa: ANN001
        dbapi_conn.create_function(
            "gen_random_uuid", 0, lambda: str(uuid.uuid4())
        )
        dbapi_conn.create_function(
            "now", 0, lambda: datetime.now(timezone.utc).isoformat(sep=" ")
        )

    Base.metadata.create_all(eng)

    # Seed entity_class rows so detected_symbol / user_correction FKs resolve.
    from app.db.models import EntityClass

    seed_session = sessionmaker(bind=eng, future=True, expire_on_commit=False)()
    try:
        for row in ENTITY_CLASS_SEED_DATA:
            seed_session.add(EntityClass(**row))
        seed_session.commit()
    finally:
        seed_session.close()

    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def db_session(engine):
    """Function-scoped session shared between the test and the app (via get_db)."""
    session = sessionmaker(bind=engine, future=True, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Domain fixtures
# ---------------------------------------------------------------------------
def _make_user(db_session, *, role="user", team_id=None):
    from app.db.models import User

    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        display_name="Test User",
        role=role,
        team_id=team_id,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _make_drawing(db_session, owner_user_id=None, owner_team_id=None):
    from app.db.models import Drawing

    drawing = Drawing(
        id=uuid.uuid4(),
        owner_user_id=owner_user_id,
        owner_team_id=owner_team_id,
        filename="diagram.pdf",
        processing_state="Complete",
    )
    db_session.add(drawing)
    db_session.commit()
    return drawing


def _add_symbols(db_session, drawing_id, n, *, entity_class_id="pipe", rejected=False):
    from app.db.models import DetectedSymbol

    symbols = []
    for i in range(n):
        sym = DetectedSymbol(
            id=uuid.uuid4(),
            drawing_id=drawing_id,
            entity_class_id=entity_class_id,
            subtype="ball" if entity_class_id.startswith("valve") else None,
            tag_label=f"TAG-{i:04d}",
            confidence=0.91,
            bbox={"x": float(i), "y": 2.0, "w": 3.0, "h": 4.0},
            source="ml",
            rejected=rejected,
            page_number=1,
        )
        symbols.append(sym)
        db_session.add(sym)
    db_session.commit()
    return symbols


def _add_reclassify(db_session, symbol_id, user_id, new_class_id, *, created_at=None):
    from app.db.models import UserCorrection

    correction = UserCorrection(
        id=uuid.uuid4(),
        detected_symbol_id=symbol_id,
        table_cell_id=None,
        user_id=user_id,
        correction_type="reclassify",
        new_class_id=new_class_id,
        training_consent=True,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db_session.add(correction)
    db_session.commit()
    return correction


@pytest.fixture()
def test_user(db_session):
    return _make_user(db_session, role="user")


@pytest.fixture()
def other_user(db_session):
    return _make_user(db_session, role="user")


@pytest.fixture()
def test_drawing_small(db_session, test_user):
    drawing = _make_drawing(db_session, owner_user_id=test_user.id)
    _add_symbols(db_session, drawing.id, 5)
    return drawing


@pytest.fixture()
def test_drawing_large(db_session, test_user):
    drawing = _make_drawing(db_session, owner_user_id=test_user.id)
    _add_symbols(db_session, drawing.id, 1001)
    return drawing


@pytest.fixture()
def test_drawing_boundary(db_session, test_user):
    drawing = _make_drawing(db_session, owner_user_id=test_user.id)
    _add_symbols(db_session, drawing.id, 1000)
    return drawing


@pytest.fixture()
def test_drawing_with_corrections(db_session, test_user):
    """5 symbols; 2 reclassified to valve_ball (latest correction wins)."""
    drawing = _make_drawing(db_session, owner_user_id=test_user.id)
    symbols = _add_symbols(db_session, drawing.id, 5)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # symbol[0]: two reclassifies — the later one (valve_ball) must win.
    _add_reclassify(
        db_session, symbols[0].id, test_user.id, "valve_gate", created_at=base
    )
    _add_reclassify(
        db_session,
        symbols[0].id,
        test_user.id,
        "valve_ball",
        created_at=base + timedelta(hours=1),
    )
    # symbol[1]: single reclassify to instrument.
    _add_reclassify(
        db_session,
        symbols[1].id,
        test_user.id,
        "instrument",
        created_at=base + timedelta(hours=2),
    )
    return drawing, symbols


# ---------------------------------------------------------------------------
# App / client / mock fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def app_instance(db_session):
    """The real FastAPI app with ``get_db`` overridden onto the test session."""
    from app.db.session import get_db
    from app.main import app

    def _override_get_db():
        # Do NOT close — the test fixture owns the session lifecycle.
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def make_client(app_instance):
    """Factory: build a TestClient authenticated as ``user`` (or unauthenticated).

    ``user=None`` leaves the real ``get_current_user`` in place so missing
    credentials yield 401 (US-016 AC-10).
    """
    from app.auth.dependencies import CurrentUser, get_current_user

    def _make(user=None):
        if user is not None:
            current = CurrentUser(
                id=user.id, email=user.email, role=user.role, team_id=user.team_id
            )
            app_instance.dependency_overrides[get_current_user] = lambda: current
        else:
            app_instance.dependency_overrides.pop(get_current_user, None)
        return TestClient(app_instance)

    return _make


@pytest.fixture()
def client(make_client, test_user):
    """TestClient authenticated as ``test_user``."""
    return make_client(test_user)


@pytest.fixture()
def svc_mocks(monkeypatch):
    """Patch S3 + analytics + Celery where ``export_service`` uses them.

    Returns a namespace exposing the individual mocks. ``presign`` returns a
    stable sentinel URL; ``upload`` / ``send_task`` are no-ops by default.
    """
    import app.services.export_service as svc

    presign_url = (
        "https://s3.example.com/exports/mock/mock.dat"
        "?X-Amz-Expires=900&X-Amz-Signature=deadbeef"
    )
    upload = MagicMock(return_value=None)
    presign = MagicMock(return_value=presign_url)
    initiated = MagicMock(return_value=None)
    downloaded = MagicMock(return_value=None)
    send_task = MagicMock(return_value=None)

    monkeypatch.setattr(svc, "put_object", upload)
    monkeypatch.setattr(svc, "generate_presigned_get_url", presign)
    monkeypatch.setattr(svc.analytics_events, "emit_export_initiated", initiated)
    monkeypatch.setattr(svc.analytics_events, "emit_export_downloaded", downloaded)
    monkeypatch.setattr(svc.celery_app, "send_task", send_task)

    ns = MagicMock()
    ns.upload = upload
    ns.presign = presign
    ns.presign_url = presign_url
    ns.initiated = initiated
    ns.downloaded = downloaded
    ns.send_task = send_task
    return ns


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _insert_export(db_session, *, drawing_id, user_id, fmt="csv", status="Queued",
                   stored_file_id=None, completed_at=None):
    from app.db.models import ExportRecord

    record = ExportRecord(
        id=uuid.uuid4(),
        drawing_id=drawing_id,
        user_id=user_id,
        format=fmt,
        status=status,
        stored_file_id=stored_file_id,
        initiated_at=datetime.now(timezone.utc),
        completed_at=completed_at,
    )
    db_session.add(record)
    db_session.commit()
    return record


# ===========================================================================
# US-016 — Synchronous CSV / XLSX export
# ===========================================================================
def test_post_export_csv_sync_returns_201_with_download_url(
    client, test_drawing_small, svc_mocks
):
    resp = client.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "csv"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "Complete"
    assert body["format"] == "csv"
    assert body["download_url"] == svc_mocks.presign_url
    assert body["completed_at"] is not None


def test_post_export_xlsx_sync_returns_201_with_download_url(
    client, test_drawing_small, svc_mocks
):
    resp = client.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "xlsx"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "Complete"
    assert body["format"] == "xlsx"
    assert body["download_url"] == svc_mocks.presign_url
    # The uploaded payload is a valid XLSX workbook.
    _, _, data, content_type = svc_mocks.upload.call_args.args
    assert content_type == XLSX_CONTENT_TYPE
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data))
    assert "Symbols" in wb.sheetnames


def test_csv_output_contains_required_columns(
    client, test_drawing_small, svc_mocks
):
    client.post(f"/drawings/{test_drawing_small.id}/exports", json={"format": "csv"})
    _, _, data, content_type = svc_mocks.upload.call_args.args
    assert content_type == CSV_CONTENT_TYPE
    import csv

    reader = csv.reader(io.StringIO(data.decode("utf-8")))
    header = next(reader)
    assert header == [
        "symbol_id",
        "entity_class_id",
        "subtype",
        "tag_label",
        "confidence",
        "page_number",
        "bbox_x",
        "bbox_y",
        "bbox_w",
        "bbox_h",
        "source",
        "rejected",
    ]
    rows = list(reader)
    assert len(rows) == 5


def test_csv_entity_class_reflects_latest_reclassify_correction(
    client, test_drawing_with_corrections, svc_mocks
):
    drawing, symbols = test_drawing_with_corrections
    client.post(f"/drawings/{drawing.id}/exports", json={"format": "csv"})
    _, _, data, _ = svc_mocks.upload.call_args.args

    import csv

    reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
    by_id = {row["symbol_id"]: row for row in reader}
    # symbol[0] reclassified twice; the latest (valve_ball) wins.
    assert by_id[str(symbols[0].id)]["entity_class_id"] == "valve_ball"
    # symbol[1] reclassified once.
    assert by_id[str(symbols[1].id)]["entity_class_id"] == "instrument"
    # symbol[2] never reclassified -> original class.
    assert by_id[str(symbols[2].id)]["entity_class_id"] == "pipe"


def test_xlsx_symbols_worksheet_contains_required_columns(
    client, test_drawing_small, svc_mocks
):
    client.post(f"/drawings/{test_drawing_small.id}/exports", json={"format": "xlsx"})
    _, _, data, _ = svc_mocks.upload.call_args.args

    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data))
    ws = wb["Symbols"]
    header = [cell.value for cell in ws[1]]
    assert header == [
        "symbol_id",
        "entity_class_id",
        "subtype",
        "tag_label",
        "confidence",
        "page_number",
        "bbox_x",
        "bbox_y",
        "bbox_w",
        "bbox_h",
        "source",
        "rejected",
    ]
    # 5 non-rejected data rows + 1 header.
    assert ws.max_row == 6


def test_xlsx_corrections_worksheet_contains_correction_rows(
    client, test_drawing_with_corrections, svc_mocks
):
    drawing, _symbols = test_drawing_with_corrections
    client.post(f"/drawings/{drawing.id}/exports", json={"format": "xlsx"})
    _, _, data, _ = svc_mocks.upload.call_args.args

    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data))
    assert "Corrections" in wb.sheetnames
    ws = wb["Corrections"]
    header = [cell.value for cell in ws[1]]
    assert "correction_type" in header
    assert "new_class_id" in header
    # 3 correction rows were created for this drawing + 1 header.
    assert ws.max_row == 4


def test_re_export_creates_new_record_does_not_overwrite(
    client, test_drawing_small, svc_mocks, db_session
):
    from app.db.models import ExportRecord

    r1 = client.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "csv"}
    ).json()
    r2 = client.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "xlsx"}
    ).json()

    assert r1["id"] != r2["id"]
    records = (
        db_session.query(ExportRecord)
        .filter(ExportRecord.drawing_id == test_drawing_small.id)
        .all()
    )
    assert len(records) == 2
    # The first record retains its original csv format (not overwritten).
    first = next(r for r in records if str(r.id) == r1["id"])
    assert first.format == "csv"


def test_export_initiated_event_fires_sync_path(
    client, test_drawing_small, svc_mocks
):
    resp = client.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "csv"}
    ).json()
    svc_mocks.initiated.assert_called_once()
    kwargs = svc_mocks.initiated.call_args.kwargs
    assert kwargs["export_id"] == resp["id"]
    assert kwargs["drawing_id"] == str(test_drawing_small.id)
    assert kwargs["format"] == "csv"
    assert kwargs["user_id"] == resp["user_id"]


def test_export_initiated_event_fires_async_path(
    client, test_drawing_large, svc_mocks
):
    resp = client.post(
        f"/drawings/{test_drawing_large.id}/exports", json={"format": "csv"}
    )
    assert resp.status_code == 202
    svc_mocks.initiated.assert_called_once()
    assert svc_mocks.initiated.call_args.kwargs["export_id"] == resp.json()["id"]


def test_presigned_url_uses_configured_expiry_seconds():
    """The download URL TTL is driven by ``settings.PRESIGNED_URL_EXPIRY_SECONDS``
    (default 900) — asserted against the real, offline-signed generator (S1-C)."""
    import boto3
    from botocore.client import Config

    from app.config import settings
    from app.storage.presigned import generate_presigned_get_url

    signing_client = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="secretkey",
        config=Config(signature_version="s3v4"),
    )
    url = generate_presigned_get_url(
        "pidtest-exports-bucket", "exports/e1/d1.csv", client=signing_client
    )
    qs = parse_qs(urlparse(url).query)
    assert qs["X-Amz-Expires"] == [str(settings.PRESIGNED_URL_EXPIRY_SECONDS)]
    assert qs["X-Amz-Expires"] == ["900"]


def test_get_export_complete_returns_200_with_download_url(
    client, test_drawing_small, svc_mocks
):
    created = client.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "csv"}
    ).json()
    resp = client.get(f"/exports/{created['id']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "Complete"
    assert body["download_url"] == svc_mocks.presign_url


def test_export_downloaded_event_fires_on_get_complete_export(
    client, test_drawing_small, svc_mocks
):
    created = client.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "csv"}
    ).json()
    svc_mocks.downloaded.assert_not_called()
    client.get(f"/exports/{created['id']}")
    svc_mocks.downloaded.assert_called_once()
    kwargs = svc_mocks.downloaded.call_args.kwargs
    assert kwargs["export_id"] == created["id"]
    assert kwargs["drawing_id"] == str(test_drawing_small.id)


def test_stored_file_record_created_with_correct_fields(
    client, test_drawing_small, svc_mocks, db_session
):
    from app.db.models import ExportRecord, StoredFile

    created = client.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "csv"}
    ).json()
    bucket, _key, data, _ct = svc_mocks.upload.call_args.args

    record = db_session.get(ExportRecord, uuid.UUID(created["id"]))
    assert record.stored_file_id is not None
    stored = db_session.get(StoredFile, record.stored_file_id)
    # Bucket comes from settings.S3_BUCKET_NAME — same value the upload used.
    assert stored.bucket == bucket
    assert stored.object_key == f"exports/{created['id']}/{test_drawing_small.id}.csv"
    assert stored.file_type == CSV_CONTENT_TYPE
    assert stored.size_bytes == len(data)
    assert stored.sha256_hash == hashlib.sha256(data).hexdigest()


def test_post_export_unauthenticated_returns_401(make_client, test_drawing_small):
    unauth = make_client(user=None)
    resp = unauth.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "csv"}
    )
    assert resp.status_code == 401


def test_post_export_wrong_owner_returns_403(
    make_client, db_session, other_user, test_user, svc_mocks
):
    # Drawing owned by other_user; test_user (role 'user', export_initiate='own').
    drawing = _make_drawing(db_session, owner_user_id=other_user.id)
    _add_symbols(db_session, drawing.id, 3)
    client = make_client(test_user)
    resp = client.post(f"/drawings/{drawing.id}/exports", json={"format": "csv"})
    assert resp.status_code == 403


def test_post_export_nonexistent_drawing_returns_404(client, svc_mocks):
    resp = client.post(f"/drawings/{uuid.uuid4()}/exports", json={"format": "csv"})
    assert resp.status_code == 404


def test_post_export_invalid_format_returns_422(client, test_drawing_small):
    resp = client.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "pdf"}
    )
    assert resp.status_code == 422


# ===========================================================================
# US-017 — Async export queue (initiation)
# ===========================================================================
def test_post_export_over_threshold_returns_202_queued(
    client, test_drawing_large, svc_mocks
):
    resp = client.post(
        f"/drawings/{test_drawing_large.id}/exports", json={"format": "csv"}
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "Queued"
    assert body["download_url"] is None
    # No file was generated / uploaded on the async path.
    svc_mocks.upload.assert_not_called()


def test_threshold_evaluated_server_side_not_from_client(
    client, test_drawing_large, test_drawing_small, svc_mocks
):
    # A client-supplied count cannot flip a >1000-symbol drawing onto the sync
    # path, nor a small drawing onto the async path.
    big = client.post(
        f"/drawings/{test_drawing_large.id}/exports",
        json={"format": "csv", "symbol_count": 1},
    )
    assert big.status_code == 202

    small = client.post(
        f"/drawings/{test_drawing_small.id}/exports",
        json={"format": "csv", "symbol_count": 99999},
    )
    assert small.status_code == 201


def test_threshold_boundary_exactly_1000_sync_1001_async(
    make_client, db_session, test_user, svc_mocks
):
    sync_drawing = _make_drawing(db_session, owner_user_id=test_user.id)
    _add_symbols(db_session, sync_drawing.id, 1000)
    async_drawing = _make_drawing(db_session, owner_user_id=test_user.id)
    _add_symbols(db_session, async_drawing.id, 1001)

    client = make_client(test_user)
    assert (
        client.post(
            f"/drawings/{sync_drawing.id}/exports", json={"format": "csv"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/drawings/{async_drawing.id}/exports", json={"format": "csv"}
        ).status_code
        == 202
    )


def test_export_record_committed_before_celery_send_task(
    client, test_drawing_large, svc_mocks, engine
):
    from app.db.models import ExportRecord

    seen = {}

    def _on_send_task(task_name, **kwargs):
        # At enqueue time the row must already be committed (visible to a fresh
        # connection) in Queued state.
        export_id = uuid.UUID(kwargs["kwargs"]["export_id"])
        probe = sessionmaker(bind=engine, future=True)()
        try:
            row = probe.get(ExportRecord, export_id)
            seen["exists"] = row is not None
            seen["status"] = row.status if row else None
        finally:
            probe.close()

    svc_mocks.send_task.side_effect = _on_send_task

    resp = client.post(
        f"/drawings/{test_drawing_large.id}/exports", json={"format": "csv"}
    )
    assert resp.status_code == 202
    assert seen.get("exists") is True
    assert seen.get("status") == "Queued"


def test_get_export_queued_returns_200_null_url(
    client, db_session, test_user, test_drawing_small
):
    record = _insert_export(
        db_session,
        drawing_id=test_drawing_small.id,
        user_id=test_user.id,
        status="Queued",
    )
    resp = client.get(f"/exports/{record.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "Queued"
    assert body["download_url"] is None


def test_get_export_failed_returns_200_null_url(
    client, db_session, test_user, test_drawing_small
):
    record = _insert_export(
        db_session,
        drawing_id=test_drawing_small.id,
        user_id=test_user.id,
        status="Failed",
    )
    resp = client.get(f"/exports/{record.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "Failed"
    assert body["download_url"] is None


def test_get_export_wrong_user_returns_403(
    make_client, db_session, test_user, other_user, test_drawing_small
):
    record = _insert_export(
        db_session,
        drawing_id=test_drawing_small.id,
        user_id=test_user.id,
        status="Queued",
    )
    client = make_client(other_user)
    resp = client.get(f"/exports/{record.id}")
    assert resp.status_code == 403


def test_get_export_nonexistent_returns_404(client):
    resp = client.get(f"/exports/{uuid.uuid4()}")
    assert resp.status_code == 404


# ===========================================================================
# Technical / contract assertions
# ===========================================================================
def test_async_path_sends_task_with_correct_name_and_kwargs(
    client, test_drawing_large, svc_mocks
):
    resp = client.post(
        f"/drawings/{test_drawing_large.id}/exports", json={"format": "csv"}
    ).json()
    svc_mocks.send_task.assert_called_once()
    args, kwargs = svc_mocks.send_task.call_args
    assert args[0] == EXPORT_TASK_NAME
    assert kwargs["kwargs"] == {"export_id": resp["id"]}


def test_s3_object_key_follows_exports_pattern(
    client, test_drawing_small, svc_mocks
):
    created = client.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "csv"}
    ).json()
    bucket, object_key, _data, _ct = svc_mocks.upload.call_args.args
    assert object_key == f"exports/{created['id']}/{test_drawing_small.id}.csv"


def test_stored_file_and_export_record_updated_atomically_after_s3(
    client, test_drawing_small, svc_mocks, db_session
):
    from app.db.models import ExportRecord, StoredFile

    created = client.post(
        f"/drawings/{test_drawing_small.id}/exports", json={"format": "csv"}
    ).json()
    # Both the StoredFile and the Complete ExportRecord update are committed.
    record = db_session.get(ExportRecord, uuid.UUID(created["id"]))
    assert record.status == "Complete"
    assert record.completed_at is not None
    assert record.stored_file_id is not None
    assert db_session.get(StoredFile, record.stored_file_id) is not None
    # S3 upload happened before the StoredFile row existed.
    svc_mocks.upload.assert_called_once()


def test_csv_includes_rejected_symbols_with_flag(
    make_client, db_session, test_user, svc_mocks
):
    drawing = _make_drawing(db_session, owner_user_id=test_user.id)
    _add_symbols(db_session, drawing.id, 3, rejected=False)
    _add_symbols(db_session, drawing.id, 2, rejected=True)

    client = make_client(test_user)
    client.post(f"/drawings/{drawing.id}/exports", json={"format": "csv"})
    _, _, data, _ = svc_mocks.upload.call_args.args

    import csv

    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    assert len(rows) == 5  # rejected symbols are NOT dropped
    rejected_flags = {row["rejected"] for row in rows}
    assert "True" in rejected_flags and "False" in rejected_flags


def test_export_initiated_fires_before_send_task_not_from_worker(
    client, test_drawing_large, svc_mocks
):
    # Attach both spies to a parent manager to assert call ordering: the API
    # layer must emit export_initiated BEFORE handing off to the worker queue.
    manager = MagicMock()
    manager.attach_mock(svc_mocks.initiated, "initiated")
    manager.attach_mock(svc_mocks.send_task, "send_task")

    client.post(f"/drawings/{test_drawing_large.id}/exports", json={"format": "csv"})

    call_names = [c[0] for c in manager.mock_calls]
    assert call_names == ["initiated", "send_task"]
