"""S2-I — Scan Worker (ClamAV) acceptance tests (US-008 Scanning leg).

Run with:  pytest tests/integration/test_scan_worker.py -v

These tests prove the malware-scan Celery worker in isolation — no sibling
session (S2-H ingest, S2-J ML) needs to be merged: the ``scan_drawing`` task is
invoked directly and ``celery_app.send_task`` is mocked. They are also
self-contained at the *infrastructure* level so they pass in the no-Docker
``session-tests`` gate as well as the live ``integration`` workflow:

* **DB** — the ``Drawing`` / ``StoredFile`` ORM models (S1-A) are materialised in
  an in-memory SQLite database. The worker's ``_session_factory`` seam is patched
  to that database, so ``app.db.session`` (which eagerly resolves the psycopg2
  dialect at import) is never touched — that import would otherwise fail under
  bare ``pytest`` where only psycopg v3 is installed.
* **ClamAV** — ``ClamAVClient`` is fully mocked; no clamd daemon is required.
* **S3** — ``get_s3_client().get_object(...)['Body']`` returns an in-memory
  ``BytesIO``; no MinIO/AWS call is made.
* **Redis** — ``publish_drawing_status`` (async) is replaced with an
  ``AsyncMock`` and its call args are asserted directly.

App modules are imported lazily *inside* fixtures/tests (never at module top):
S0-B's smoke suite asserts no ``app.*`` module leaks into ``sys.modules`` during
collection, so a top-level ``import app...`` would break that sibling test when
the whole ``tests/integration`` dir is collected.
"""
from __future__ import annotations

import io
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# --- make `app` (backend/app) importable ------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "backend"
for _p in (str(_BACKEND), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- §1.12 env contract: the shared conftest seeds most "Refuse to start"
# vars, but importing app.config validates the FULL required set. ML_MODEL_S3_KEY
# / ODA_CONVERTER_PATH are not seeded by conftest, so add test-safe values here
# (setdefault → real env / conftest still win) before any app import. ------------
for _k, _v in {
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
    "ENVIRONMENT": "development",
}.items():
    os.environ.setdefault(_k, _v)


# ---------------------------------------------------------------------------
# Lazy module accessors
# ---------------------------------------------------------------------------
@pytest.fixture()
def tasks_mod():
    import app.workers.scan.tasks as t

    return t


@pytest.fixture()
def clamav_mod():
    import app.workers.scan.clamav_client as c

    return c


# ---------------------------------------------------------------------------
# In-memory SQLite database with the S1-A schema (drawing + stored_file)
# ---------------------------------------------------------------------------
@pytest.fixture()
def db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db.models.drawing import Drawing  # noqa: F401
    from app.db.models.stored_file import StoredFile  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    # Create only the two tables this worker touches. The server_default
    # gen_random_uuid()/now() never fire because rows are inserted with explicit
    # ids + uploaded_at below.
    StoredFile.__table__.create(engine)
    Drawing.__table__.create(engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    try:
        yield SimpleNamespace(engine=engine, Session=Session)
    finally:
        engine.dispose()


def _state_of(db, drawing_id: str) -> str:
    """Read processing_state back from the DB in a fresh session."""
    from app.db.models.drawing import Drawing

    session = db.Session()
    try:
        drawing = session.get(Drawing, uuid.UUID(drawing_id))
        return None if drawing is None else drawing.processing_state
    finally:
        session.close()


def _seed_drawing(db, *, state: str = "Scanning") -> SimpleNamespace:
    from app.db.models.drawing import Drawing
    from app.db.models.stored_file import StoredFile

    session = db.Session()
    try:
        stored_file = StoredFile(
            id=uuid.uuid4(),
            bucket="test-bucket",
            object_key="uploads/test/drawing.pdf",
            sha256_hash="a" * 64,
            file_type="pdf",
            size_bytes=1234,
        )
        session.add(stored_file)
        session.commit()
        drawing = Drawing(
            id=uuid.uuid4(),
            owner_user_id=uuid.uuid4(),
            filename="drawing.pdf",
            processing_state=state,
            stored_file_id=stored_file.id,
            uploaded_at=datetime.now(timezone.utc),
        )
        session.add(drawing)
        session.commit()
        return SimpleNamespace(
            drawing_id=str(drawing.id),
            owner_user_id=str(drawing.owner_user_id),
            object_key=stored_file.object_key,
        )
    finally:
        session.close()


@pytest.fixture()
def scanning_drawing(db):
    """A Drawing row in ``Scanning`` state with a backing StoredFile."""
    return _seed_drawing(db, state="Scanning")


# ---------------------------------------------------------------------------
# ClamAVClient doubles (US-008 mocking contract)
# ---------------------------------------------------------------------------
@pytest.fixture()
def _scan_result(clamav_mod):
    return clamav_mod.ScanResult


@pytest.fixture()
def mock_clamav_clean(_scan_result):
    client = MagicMock(name="ClamAVClient(clean)")
    client.scan_stream.return_value = _scan_result(clean=True, infection=None)
    return client


@pytest.fixture()
def mock_clamav_infected(_scan_result):
    client = MagicMock(name="ClamAVClient(infected)")
    client.scan_stream.return_value = _scan_result(
        clean=False, infection="Eicar-Test-Signature"
    )
    return client


@pytest.fixture()
def mock_clamav_error(clamav_mod):
    client = MagicMock(name="ClamAVClient(error)")
    client.scan_stream.side_effect = clamav_mod.ClamAVConnectionError("clamd down")
    return client


# ---------------------------------------------------------------------------
# Worker wiring — patch every external seam of the tasks module.
# ---------------------------------------------------------------------------
@pytest.fixture()
def wire(tasks_mod, db, monkeypatch):
    """Return a factory that wires the tasks module to a given ClamAV double."""

    def _wire(clamav_client):
        monkeypatch.setattr(tasks_mod, "_session_factory", lambda: db.Session())

        s3 = MagicMock(name="s3_client")
        s3.get_object.return_value = {"Body": io.BytesIO(b"%PDF-1.4 fake bytes")}
        monkeypatch.setattr(tasks_mod, "get_s3_client", lambda: s3)

        publish = AsyncMock(name="publish_drawing_status")
        monkeypatch.setattr(tasks_mod, "publish_drawing_status", publish)

        monkeypatch.setattr(tasks_mod, "_clamav_client", lambda: clamav_client)

        send_task = MagicMock(name="celery_app.send_task")
        monkeypatch.setattr(tasks_mod.celery_app, "send_task", send_task)

        return SimpleNamespace(s3=s3, publish=publish, send_task=send_task)

    return _wire


def _payload(scanning_drawing, *, user_id: str | None = None) -> dict:
    return {
        "drawing_id": scanning_drawing.drawing_id,
        "storage_reference": scanning_drawing.object_key,
        "user_id": user_id or str(uuid.uuid4()),
    }


def _published_events(publish_mock) -> list:
    """Extract the DrawingStatusSSEEvent objects passed to publish_drawing_status."""
    events = []
    for call in publish_mock.await_args_list or publish_mock.call_args_list:
        args, kwargs = call
        # publish_drawing_status(drawing_id, event)
        events.append(args[1] if len(args) > 1 else kwargs["event"])
    return events


# ===========================================================================
# US-008 AC-1 — clean → Processing committed in DB
# ===========================================================================
def test_transitions_to_processing_when_file_is_clean(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_clean
):
    wire(mock_clamav_clean)
    tasks_mod.scan_drawing.run(_payload(scanning_drawing))
    assert _state_of(db, scanning_drawing.drawing_id) == "Processing"


# US-008 AC-2 — SSE Processing event published after the commit
def test_publishes_sse_processing_on_clean_scan(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_clean
):
    wired = wire(mock_clamav_clean)
    tasks_mod.scan_drawing.run(_payload(scanning_drawing))

    events = _published_events(wired.publish)
    assert len(events) == 1
    event = events[0]
    assert event.drawing_id == scanning_drawing.drawing_id
    assert event.state == "Processing"


# US-008 AC-3 — ML inference job enqueued to ml_inference queue on clean scan
def test_enqueues_ml_inference_job_on_clean_scan(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_clean
):
    wired = wire(mock_clamav_clean)
    user_id = str(uuid.uuid4())
    tasks_mod.scan_drawing.run(_payload(scanning_drawing, user_id=user_id))

    wired.send_task.assert_called_once()
    args, kwargs = wired.send_task.call_args
    assert args[0] == "backend.app.workers.ml.tasks.run_ml_inference"
    assert kwargs["queue"] == tasks_mod.QUEUE_ML == "ml_inference"
    ml_payload = kwargs["args"][0]
    assert ml_payload["drawing_id"] == scanning_drawing.drawing_id
    assert ml_payload["storage_reference"] == scanning_drawing.object_key
    assert ml_payload["user_id"] == user_id
    assert ml_payload["page_range"] is None


# ===========================================================================
# US-008 AC-4 — infected → Scan_Failed committed in DB
# ===========================================================================
def test_transitions_to_scan_failed_when_infected(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_infected
):
    wire(mock_clamav_infected)
    tasks_mod.scan_drawing.run(_payload(scanning_drawing))
    assert _state_of(db, scanning_drawing.drawing_id) == "Scan_Failed"


# US-008 AC-5 — SSE Scan_Failed event published when infected
def test_publishes_sse_scan_failed_when_infected(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_infected
):
    wired = wire(mock_clamav_infected)
    tasks_mod.scan_drawing.run(_payload(scanning_drawing))

    events = _published_events(wired.publish)
    assert len(events) == 1
    assert events[0].state == "Scan_Failed"
    assert events[0].drawing_id == scanning_drawing.drawing_id


# US-008 AC-6 — no ML job enqueued for an infected file
def test_no_ml_job_enqueued_when_infected(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_infected
):
    wired = wire(mock_clamav_infected)
    tasks_mod.scan_drawing.run(_payload(scanning_drawing))
    wired.send_task.assert_not_called()


# US-008 AC-7 — Scan_Failed is terminal: no self.retry() on malware detection
def test_scan_failed_is_terminal_no_celery_retry(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_infected, monkeypatch
):
    wired = wire(mock_clamav_infected)
    retry = MagicMock(name="self.retry")
    monkeypatch.setattr(tasks_mod.scan_drawing, "retry", retry)

    tasks_mod.scan_drawing.run(_payload(scanning_drawing))

    retry.assert_not_called()
    assert _state_of(db, scanning_drawing.drawing_id) == "Scan_Failed"
    wired.send_task.assert_not_called()


# ===========================================================================
# US-008 AC-8 — ClamAV connection error retries; drawing stays Scanning
# ===========================================================================
def test_retries_on_clamav_connection_error(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_error, monkeypatch
):
    from celery.exceptions import Retry

    wired = wire(mock_clamav_error)
    retry = MagicMock(name="self.retry", side_effect=Retry())
    monkeypatch.setattr(tasks_mod.scan_drawing, "retry", retry)

    with pytest.raises(Retry):
        tasks_mod.scan_drawing.run(_payload(scanning_drawing))

    retry.assert_called_once()
    _, kwargs = retry.call_args
    assert isinstance(kwargs["exc"], tasks_mod.ClamAVConnectionError)
    assert kwargs["max_retries"] == 3
    # Drawing remains Scanning during retries; nothing else fired.
    assert _state_of(db, scanning_drawing.drawing_id) == "Scanning"
    wired.send_task.assert_not_called()
    wired.publish.assert_not_called()


# US-008 AC-9 — retries exhausted → Failed committed in DB
def test_transitions_to_failed_after_max_retries_exhausted(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_error, monkeypatch
):
    from celery.exceptions import MaxRetriesExceededError

    wire(mock_clamav_error)
    monkeypatch.setattr(
        tasks_mod.scan_drawing,
        "retry",
        MagicMock(side_effect=MaxRetriesExceededError()),
    )

    tasks_mod.scan_drawing.run(_payload(scanning_drawing))
    assert _state_of(db, scanning_drawing.drawing_id) == "Failed"


# US-008 AC-10 — SSE Failed event published after retries exhausted
def test_publishes_sse_failed_after_max_retries_exhausted(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_error, monkeypatch
):
    from celery.exceptions import MaxRetriesExceededError

    wired = wire(mock_clamav_error)
    monkeypatch.setattr(
        tasks_mod.scan_drawing,
        "retry",
        MagicMock(side_effect=MaxRetriesExceededError()),
    )

    tasks_mod.scan_drawing.run(_payload(scanning_drawing))

    events = _published_events(wired.publish)
    assert len(events) == 1
    assert events[0].state == "Failed"
    assert events[0].drawing_id == scanning_drawing.drawing_id
    # No ML job on the failure path.
    wired.send_task.assert_not_called()


# ===========================================================================
# US-008 AC-11 — user_id flows from payload, never from the DB
# ===========================================================================
def test_user_id_taken_from_task_payload_not_db(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_clean
):
    wired = wire(mock_clamav_clean)
    payload_user_id = str(uuid.uuid4())
    # Deliberately different from the drawing's owner_user_id.
    assert payload_user_id != scanning_drawing.owner_user_id

    tasks_mod.scan_drawing.run(_payload(scanning_drawing, user_id=payload_user_id))

    _, kwargs = wired.send_task.call_args
    assert kwargs["args"][0]["user_id"] == payload_user_id
    assert kwargs["args"][0]["user_id"] != scanning_drawing.owner_user_id


# ===========================================================================
# US-008 AC-12 — every SSE event has exactly drawing_id/state/timestamp (UTC)
# ===========================================================================
def test_sse_event_payload_shape_is_correct(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_clean
):
    wired = wire(mock_clamav_clean)
    tasks_mod.scan_drawing.run(_payload(scanning_drawing))

    event = _published_events(wired.publish)[0]
    dumped = event.model_dump()
    assert set(dumped.keys()) == {"drawing_id", "state", "timestamp"}
    # timestamp must be a parseable ISO 8601 UTC instant (offset == 0).
    parsed = datetime.fromisoformat(dumped["timestamp"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(None)


# ===========================================================================
# US-008 AC-13/14/15 — ClamAVClient behaviour (real client, pyclamd patched)
# ===========================================================================
def test_clamav_client_ping_returns_true_when_reachable(clamav_mod, monkeypatch):
    socket = MagicMock()
    socket.ping.return_value = True
    monkeypatch.setattr(
        clamav_mod.pyclamd, "ClamdNetworkSocket", MagicMock(return_value=socket)
    )
    assert clamav_mod.ClamAVClient(host="clamav", port=3310).ping() is True


def test_clamav_client_ping_raises_on_connection_failure(clamav_mod, monkeypatch):
    socket = MagicMock()
    socket.ping.side_effect = clamav_mod.pyclamd.ConnectionError("refused")
    monkeypatch.setattr(
        clamav_mod.pyclamd, "ClamdNetworkSocket", MagicMock(return_value=socket)
    )
    with pytest.raises(clamav_mod.ClamAVConnectionError):
        clamav_mod.ClamAVClient(host="clamav", port=3310).ping()


def test_clamav_client_scan_stream_returns_clean_result(clamav_mod, monkeypatch):
    socket = MagicMock()
    socket.scan_stream.return_value = None  # pyclamd: None == no infection
    monkeypatch.setattr(
        clamav_mod.pyclamd, "ClamdNetworkSocket", MagicMock(return_value=socket)
    )
    result = clamav_mod.ClamAVClient().scan_stream(io.BytesIO(b"clean"))
    assert result.clean is True
    assert result.infection is None


def test_clamav_client_scan_stream_returns_infected_result(clamav_mod, monkeypatch):
    socket = MagicMock()
    # pyclamd infected shape: {filename: ('FOUND', virusname)}
    socket.scan_stream.return_value = {"stream": ("FOUND", "Eicar-Test-Signature")}
    monkeypatch.setattr(
        clamav_mod.pyclamd, "ClamdNetworkSocket", MagicMock(return_value=socket)
    )
    result = clamav_mod.ClamAVClient().scan_stream(io.BytesIO(b"x5O!P%@AP"))
    assert result.clean is False
    assert result.infection == "Eicar-Test-Signature"


# ===========================================================================
# US-008 AC-16 — no-op when the drawing is not in Scanning state
# ===========================================================================
def test_noop_when_drawing_not_in_scanning_state(tasks_mod, db, wire, mock_clamav_clean):
    queued = _seed_drawing(db, state="Queued")
    wired = wire(mock_clamav_clean)

    tasks_mod.scan_drawing.run(_payload(queued))

    # No state mutation, no scan, no SSE publish, no ML enqueue.
    assert _state_of(db, queued.drawing_id) == "Queued"
    mock_clamav_clean.scan_stream.assert_not_called()
    wired.publish.assert_not_called()
    wired.send_task.assert_not_called()


# ===========================================================================
# US-008 AC-17 — scan_drawing bound to `scan` queue; ML → `ml_inference` queue
# ===========================================================================
def test_task_registered_on_scan_queue_and_ml_dispatched_to_ml_inference_queue(
    tasks_mod, db, scanning_drawing, wire, mock_clamav_clean
):
    # Registered name is the cross-session contract S2-H send_task()s against.
    assert tasks_mod.scan_drawing.name == "backend.app.workers.scan.tasks.scan_drawing"
    # Task is bound to the `scan` queue (matches the S1-D Queues constant).
    assert tasks_mod.scan_drawing.queue == tasks_mod.QUEUE_SCAN == "scan"
    # And it is registered on the shared Celery app under that name.
    assert tasks_mod.scan_drawing.name in tasks_mod.celery_app.tasks

    # ML dispatch targets the ml_inference queue via string send_task.
    wired = wire(mock_clamav_clean)
    tasks_mod.scan_drawing.run(_payload(scanning_drawing))
    _, kwargs = wired.send_task.call_args
    assert kwargs["queue"] == tasks_mod.QUEUE_ML == "ml_inference"
