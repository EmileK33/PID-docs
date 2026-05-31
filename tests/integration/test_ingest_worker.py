"""S2-H — Ingest Worker acceptance tests.

Run with:  pytest tests/integration/test_ingest_worker.py -v

These tests are **fully self-contained re backing services** so they pass in the
no-Docker ``session-tests`` CI gate as well as the fixtures-live ``integration``
workflow (see the harness import-root / CI-fixture notes):

* **Database** — an in-memory SQLite database with the canonical ``drawing`` /
  ``stored_file`` / ``file_hash_blocklist`` tables. The ingest worker takes the
  session as an argument (``_run_ingest(payload, db)``), so no Postgres is
  required. The worker creates ``StoredFile`` rows with an explicit ``id`` and
  never inserts ``drawing`` rows, so the Postgres-only server defaults
  (``gen_random_uuid()`` / ``now()``) are never exercised under SQLite.
* **S3 / ODA / Redis / Celery** — every external effect is a module-level seam in
  ``app.workers.ingest.tasks`` that the tests monkeypatch: ``_download_file_bytes``
  (S3 GET), ``put_object`` (S3 PUT), ``convert_dwg_to_pdf`` (ODA sandbox),
  ``_publish_status`` (Redis pub/sub bridge) and ``celery_app.send_task`` (scan
  dispatch). No network call is made.

App modules are imported lazily inside an autouse fixture, not at import time, so
``app.*`` does not leak into ``sys.modules`` during collection (the S0-B smoke
suite asserts it does not).
"""
from __future__ import annotations

import io
import logging
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

# ── Make `app` (backend/app) importable + satisfy §1.12 before importing app ──
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "backend"
for _p in (str(_BACKEND), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The shared conftest seeds the load-bearing subset; app.config validates the
# FULL required set, so provide the remaining REQUIRED vars (setdefault → real
# env / conftest still win). This session owns neither config.py nor conftest.py.
for _key, _value in {
    "DATABASE_URL": "postgresql://u:p@localhost:5432/pid",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_BUCKET_NAME": "pidtest-bucket",
    "S3_REGION": "us-east-1",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    "JWT_RS256_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----",
    "STRIPE_SECRET_KEY": "sk_test_FAKE",
    "STRIPE_WEBHOOK_SECRET": "whsec_test_FAKE",
    "SENDGRID_API_KEY": "SG.test_FAKE",
    "HMAC_SERVER_SECRET": "test-secret",
    "ML_MODEL_S3_KEY": "test/model.onnx",
    "ODA_CONVERTER_PATH": "/opt/oda/ODAFileConverter",
}.items():
    os.environ.setdefault(_key, _value)

BUCKET = os.environ["S3_BUCKET_NAME"]

# Sample ingest job payloads. NOTE: the UUIDs deliberately contain hex *letters*.
# SQLite has dynamic numeric affinity, so an all-digit 32-char UUID hex (e.g.
# "1111...") round-trips as a float and breaks the SQLAlchemy UUID result
# processor. This is a SQLite test-DB artifact only — Postgres stores UUIDs
# natively — so we use letter-bearing UUIDs to keep the in-memory DB faithful.
DRAWING_PDF = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DRAWING_DWG = "dddddddd-dddd-dddd-dddd-dddddddddddd"
USER_ID = "babababa-baba-baba-baba-babababababa"
STORED_FILE_PDF = "cccccccc-cccc-cccc-cccc-cccccccccccc"
STORED_FILE_DWG = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
PDF_KEY = "uploads/cccccccc-cccc-cccc-cccc-cccccccccccc/drawing.pdf"
DWG_KEY = "uploads/eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee/drawing.dwg"

DWG_MAGIC_BYTES = b"AC1027" + b"\x00" * 100


# Deferred app-module handles, bound at test-run time by the autouse fixture.
tasks = None  # type: ignore[assignment]
oda_converter = None  # type: ignore[assignment]
format_detect = None  # type: ignore[assignment]
hash_reverify = None  # type: ignore[assignment]
Drawing = None  # type: ignore[assignment]
StoredFile = None  # type: ignore[assignment]
DrawingStatusSSEEvent = None  # type: ignore[assignment]
compute_sha256_stream = None  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _deferred_app_import():
    """Bind app handles onto module globals at run time (keeps collection clean)."""
    import app.workers.ingest.tasks as _tasks
    from app.db.models.drawing import Drawing as _Drawing
    from app.db.models.stored_file import StoredFile as _StoredFile
    from app.schemas.contracts import DrawingStatusSSEEvent as _Event
    from app.storage.hashing import compute_sha256_stream as _hash
    from app.workers.ingest import format_detect as _fmt
    from app.workers.ingest import hash_reverify as _hr
    from app.workers.ingest import oda_converter as _oda

    g = globals()
    g.update(
        tasks=_tasks,
        oda_converter=_oda,
        format_detect=_fmt,
        hash_reverify=_hr,
        Drawing=_Drawing,
        StoredFile=_StoredFile,
        DrawingStatusSSEEvent=_Event,
        compute_sha256_stream=_hash,
    )
    yield


# ── Test doubles / data builders ──────────────────────────────────────────────
def _make_pdf(pages: int = 1) -> bytes:
    """Build a valid PDF with a known page count (starts with the %PDF magic)."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _sha256(data: bytes) -> str:
    return compute_sha256_stream(io.BytesIO(data))


@pytest.fixture()
def db():
    """In-memory SQLite session with the canonical ingest tables."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    # Portable blocklist DDL (CURRENT_TIMESTAMP, not Postgres NOW()).
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
    # stored_file before drawing (FK target); ORM-mapped so the worker's ORM
    # reads/writes work unchanged.
    StoredFile.__table__.create(engine)
    Drawing.__table__.create(engine)

    session = sessionmaker(bind=engine, future=True, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_drawing(
    db,
    *,
    drawing_id: str,
    stored_file_id: str,
    object_key: str,
    sha256: str,
    state: str = "Queued",
    file_type: str = "pdf",
    page_count=None,
    processed_at=None,
    owner_user_id: str | None = None,
):
    sf = StoredFile(
        id=uuid.UUID(stored_file_id),
        bucket=BUCKET,
        object_key=object_key,
        sha256_hash=sha256,
        file_type=file_type,
        size_bytes=123,
    )
    db.add(sf)
    drawing = Drawing(
        id=uuid.UUID(drawing_id),
        owner_user_id=uuid.UUID(owner_user_id) if owner_user_id else uuid.uuid4(),
        filename=f"drawing.{file_type}",
        processing_state=state,
        stored_file_id=sf.id,
        uploaded_at=datetime.now(timezone.utc),
        processed_at=processed_at,
        page_count=page_count,
    )
    db.add(drawing)
    db.commit()
    return drawing, sf


def _insert_blocked(db, sha256: str) -> None:
    from sqlalchemy import text

    db.execute(
        text("INSERT INTO file_hash_blocklist (sha256_hash, reason) VALUES (:h, :r)"),
        {"h": sha256, "r": "malware"},
    )
    db.commit()


def _payload(drawing_id, stored_file_id, object_key):
    return tasks.IngestJobPayload(
        drawing_id=drawing_id,
        user_id=USER_ID,
        stored_file_id=stored_file_id,
        storage_reference=object_key,
    )


@pytest.fixture()
def publish_calls(monkeypatch):
    """Record (drawing_id, state) tuples published, bypassing real Redis."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        tasks, "_publish_status", lambda did, state: calls.append((did, state))
    )
    return calls


@pytest.fixture()
def scan_calls(monkeypatch):
    """Record celery_app.send_task calls (the scan-job dispatch)."""
    calls: list[dict] = []

    def _fake_send_task(name, kwargs=None, queue=None, **_extra):
        calls.append({"name": name, "kwargs": kwargs, "queue": queue})

    monkeypatch.setattr(tasks.celery_app, "send_task", _fake_send_task)
    return calls


@pytest.fixture()
def uploads(monkeypatch):
    """Record put_object (S3 PUT) calls, bypassing real S3."""
    calls: list[dict] = []

    def _fake_put(bucket, key, body, content_type, **_extra):
        calls.append(
            {"bucket": bucket, "key": key, "body": body, "content_type": content_type}
        )

    monkeypatch.setattr(tasks, "put_object", _fake_put)
    return calls


def _patch_download(monkeypatch, data: bytes):
    monkeypatch.setattr(tasks, "_download_file_bytes", lambda bucket, key: data)


def _state(db, drawing_id: str) -> str:
    return db.get(Drawing, uuid.UUID(drawing_id)).processing_state


# ════════════════════════════════════════════════════════════════════════════
# US-008-AC-1 — Scanning transition + SSE event BEFORE any file op
# ════════════════════════════════════════════════════════════════════════════
def test_scanning_state_set_before_s3_download(db, monkeypatch, publish_calls, scan_calls):
    pdf = _make_pdf(1)
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf),
    )

    seen: dict[str, str] = {}

    def _download_observing_state(bucket, key):
        # Capture the DB-visible state at the moment the download begins.
        seen["state_at_download"] = _state(db, DRAWING_PDF)
        return pdf

    monkeypatch.setattr(tasks, "_download_file_bytes", _download_observing_state)

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    # The DB write to Scanning happened before the download was attempted...
    assert seen["state_at_download"] == "Scanning"
    # ...and the Scanning SSE event was published.
    assert (DRAWING_PDF, "Scanning") in publish_calls
    # The Scanning publish precedes any later event.
    assert publish_calls[0] == (DRAWING_PDF, "Scanning")


# ════════════════════════════════════════════════════════════════════════════
# US-008-AC-3 / US-009-AC-2 — no-op if not Queued
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("state", ["Scanning", "Processing", "Complete", "Scan_Failed"])
def test_noop_if_drawing_already_scanning(db, monkeypatch, publish_calls, scan_calls, state):
    pdf = _make_pdf(1)
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf), state=state,
    )

    def _fail_if_called(bucket, key):
        raise AssertionError("download must not run for a non-Queued drawing")

    monkeypatch.setattr(tasks, "_download_file_bytes", _fail_if_called)

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    assert _state(db, DRAWING_PDF) == state  # unchanged
    assert publish_calls == []  # no event
    assert scan_calls == []  # no scan job


# ════════════════════════════════════════════════════════════════════════════
# US-003-AC-1 — hash mismatch → Scan_Failed (+ event, no scan job)
# ════════════════════════════════════════════════════════════════════════════
def test_hash_mismatch_transitions_to_scan_failed(db, monkeypatch, publish_calls, scan_calls):
    pdf = _make_pdf(1)
    # stored hash is for `pdf`, but S3 returns tampered bytes → mismatch.
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf),
    )
    _patch_download(monkeypatch, b"%PDF-1.4 tampered different content")

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    assert _state(db, DRAWING_PDF) == "Scan_Failed"
    assert (DRAWING_PDF, "Scan_Failed") in publish_calls
    assert scan_calls == []


# ════════════════════════════════════════════════════════════════════════════
# US-003-AC-2 — second-gate blocklist hit → Scan_Failed (+ event, no scan job)
# ════════════════════════════════════════════════════════════════════════════
def test_second_gate_blocklist_hit_transitions_to_scan_failed(
    db, monkeypatch, publish_calls, scan_calls
):
    pdf = _make_pdf(1)
    digest = _sha256(pdf)
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=digest,
    )
    _patch_download(monkeypatch, pdf)  # hash MATCHES (gate 1 passes)
    _insert_blocked(db, digest)  # ...but it's now on the blocklist (gate 2)

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    assert _state(db, DRAWING_PDF) == "Scan_Failed"
    assert (DRAWING_PDF, "Scan_Failed") in publish_calls
    assert scan_calls == []


# ════════════════════════════════════════════════════════════════════════════
# US-009-AC-2 — Scan_Failed is terminal; the ingest path does not raise/retry
# ════════════════════════════════════════════════════════════════════════════
def test_scan_failed_is_terminal_no_celery_retry(db, monkeypatch, publish_calls, scan_calls):
    pdf = _make_pdf(1)
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf),
    )
    _patch_download(monkeypatch, b"tampered")

    # Returns normally (no exception) → Celery's autoretry_for is not triggered.
    result = tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)
    assert result is None
    assert _state(db, DRAWING_PDF) == "Scan_Failed"
    assert scan_calls == []

    # Re-invocation on the now-terminal drawing is a clean no-op.
    publish_calls.clear()
    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)
    assert publish_calls == []
    assert _state(db, DRAWING_PDF) == "Scan_Failed"


# ════════════════════════════════════════════════════════════════════════════
# US-003-AC-3 — format detection from magic bytes
# ════════════════════════════════════════════════════════════════════════════
def test_format_detect_pdf_magic_bytes():
    assert format_detect.detect_format(b"%PDF-1.7\n...") == "pdf"
    # Extension lies (not used) — content wins.
    assert format_detect.detect_format(b"%PDF-1.4 anything") == "pdf"


def test_format_detect_dwg_magic_bytes():
    assert format_detect.detect_format(DWG_MAGIC_BYTES) == "dwg"
    assert format_detect.detect_format(b"AC1032" + b"\x00" * 10) == "dwg"


def test_unknown_format_transitions_to_failed(db, monkeypatch, publish_calls, scan_calls):
    junk = b"ZIPP\x00not a known format"
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(junk),
    )
    _patch_download(monkeypatch, junk)  # hash matches; format is unsupported

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    assert _state(db, DRAWING_PDF) == "Failed"
    assert (DRAWING_PDF, "Failed") in publish_calls
    assert scan_calls == []


# ════════════════════════════════════════════════════════════════════════════
# US-003-AC-4 / US-011-AC-1 — PDF page count + scan job with original key
# ════════════════════════════════════════════════════════════════════════════
def test_pdf_page_count_updated_on_success(db, monkeypatch, publish_calls, scan_calls, uploads):
    pdf = _make_pdf(3)
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf),
    )
    _patch_download(monkeypatch, pdf)

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    assert db.get(Drawing, uuid.UUID(DRAWING_PDF)).page_count == 3
    assert len(scan_calls) == 1
    assert uploads == []  # PDF needs no conversion / re-upload


def test_pdf_scan_job_enqueued_with_correct_storage_reference(
    db, monkeypatch, publish_calls, scan_calls
):
    pdf = _make_pdf(1)
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf),
    )
    _patch_download(monkeypatch, pdf)

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    assert scan_calls[0]["kwargs"]["storage_reference"] == PDF_KEY  # original key


# ════════════════════════════════════════════════════════════════════════════
# US-003-AC-5 — DWG triggers ODA; ODA failure → Failed
# ════════════════════════════════════════════════════════════════════════════
def test_dwg_triggers_oda_conversion(db, monkeypatch, publish_calls, scan_calls, uploads):
    converted = _make_pdf(2)
    _seed_drawing(
        db, drawing_id=DRAWING_DWG, stored_file_id=STORED_FILE_DWG,
        object_key=DWG_KEY, sha256=_sha256(DWG_MAGIC_BYTES), file_type="dwg",
    )
    _patch_download(monkeypatch, DWG_MAGIC_BYTES)

    convert_args: dict = {}

    def _fake_convert(dwg_bytes, drawing_id):
        convert_args["dwg_bytes"] = dwg_bytes
        convert_args["drawing_id"] = drawing_id
        return converted

    monkeypatch.setattr(tasks, "convert_dwg_to_pdf", _fake_convert)

    tasks._run_ingest(_payload(DRAWING_DWG, STORED_FILE_DWG, DWG_KEY), db)

    assert convert_args["dwg_bytes"] == DWG_MAGIC_BYTES
    assert convert_args["drawing_id"] == DRAWING_DWG


def test_oda_failure_transitions_to_failed(db, monkeypatch, publish_calls, scan_calls, uploads):
    _seed_drawing(
        db, drawing_id=DRAWING_DWG, stored_file_id=STORED_FILE_DWG,
        object_key=DWG_KEY, sha256=_sha256(DWG_MAGIC_BYTES), file_type="dwg",
    )
    _patch_download(monkeypatch, DWG_MAGIC_BYTES)

    def _boom(dwg_bytes, drawing_id):
        raise oda_converter.ODAConversionError("non-zero exit")

    monkeypatch.setattr(tasks, "convert_dwg_to_pdf", _boom)

    tasks._run_ingest(_payload(DRAWING_DWG, STORED_FILE_DWG, DWG_KEY), db)

    assert _state(db, DRAWING_DWG) == "Failed"
    assert (DRAWING_DWG, "Failed") in publish_calls
    assert scan_calls == []
    assert uploads == []  # nothing uploaded on conversion failure


# ════════════════════════════════════════════════════════════════════════════
# US-003-AC-6 — converted PDF upload, new StoredFile, repoint, atomic, page count
# ════════════════════════════════════════════════════════════════════════════
def _run_dwg_success(db, monkeypatch, converted_pdf):
    _seed_drawing(
        db, drawing_id=DRAWING_DWG, stored_file_id=STORED_FILE_DWG,
        object_key=DWG_KEY, sha256=_sha256(DWG_MAGIC_BYTES), file_type="dwg",
    )
    _patch_download(monkeypatch, DWG_MAGIC_BYTES)
    monkeypatch.setattr(tasks, "convert_dwg_to_pdf", lambda b, d: converted_pdf)
    tasks._run_ingest(_payload(DRAWING_DWG, STORED_FILE_DWG, DWG_KEY), db)


def test_dwg_converted_pdf_uploaded_to_s3(db, monkeypatch, publish_calls, scan_calls, uploads):
    _run_dwg_success(db, monkeypatch, _make_pdf(2))
    expected_key = f"converted/{DRAWING_DWG}/drawing.pdf"
    assert len(uploads) == 1
    assert uploads[0]["key"] == expected_key
    assert uploads[0]["bucket"] == BUCKET
    assert uploads[0]["content_type"] == "application/pdf"


def test_dwg_new_stored_file_record_created(db, monkeypatch, publish_calls, scan_calls, uploads):
    _run_dwg_success(db, monkeypatch, _make_pdf(2))
    expected_key = f"converted/{DRAWING_DWG}/drawing.pdf"
    rows = db.query(StoredFile).filter(StoredFile.object_key == expected_key).all()
    assert len(rows) == 1
    assert rows[0].file_type == "pdf"
    assert rows[0].id != uuid.UUID(STORED_FILE_DWG)


def test_dwg_drawing_stored_file_id_updated(db, monkeypatch, publish_calls, scan_calls, uploads):
    _run_dwg_success(db, monkeypatch, _make_pdf(2))
    expected_key = f"converted/{DRAWING_DWG}/drawing.pdf"
    new_sf = db.query(StoredFile).filter(StoredFile.object_key == expected_key).one()
    drawing = db.get(Drawing, uuid.UUID(DRAWING_DWG))
    assert drawing.stored_file_id == new_sf.id
    assert drawing.stored_file_id != uuid.UUID(STORED_FILE_DWG)


def test_dwg_stored_file_and_drawing_update_atomic(db, monkeypatch, publish_calls, scan_calls, uploads):
    """The StoredFile insert + drawing repoint + page_count share one transaction.

    Force a failure *after* the StoredFile is added/flushed and the drawing is
    repointed (during the page-count read just before commit); the whole unit
    must roll back together — no new StoredFile row, drawing still on its
    original stored_file_id.
    """
    _seed_drawing(
        db, drawing_id=DRAWING_DWG, stored_file_id=STORED_FILE_DWG,
        object_key=DWG_KEY, sha256=_sha256(DWG_MAGIC_BYTES), file_type="dwg",
    )
    _patch_download(monkeypatch, DWG_MAGIC_BYTES)
    monkeypatch.setattr(tasks, "convert_dwg_to_pdf", lambda b, d: _make_pdf(2))

    def _boom_page_count(pdf_bytes):
        raise RuntimeError("transient page-count failure")

    monkeypatch.setattr(tasks, "_read_pdf_page_count", _boom_page_count)

    with pytest.raises(RuntimeError):
        tasks._run_ingest(_payload(DRAWING_DWG, STORED_FILE_DWG, DWG_KEY), db)

    db.rollback()  # discard the failed, uncommitted unit
    expected_key = f"converted/{DRAWING_DWG}/drawing.pdf"
    assert db.query(StoredFile).filter(StoredFile.object_key == expected_key).count() == 0
    assert db.get(Drawing, uuid.UUID(DRAWING_DWG)).stored_file_id == uuid.UUID(STORED_FILE_DWG)
    assert scan_calls == []  # never reached the enqueue


def test_dwg_page_count_updated_after_conversion(db, monkeypatch, publish_calls, scan_calls, uploads):
    _run_dwg_success(db, monkeypatch, _make_pdf(5))
    assert db.get(Drawing, uuid.UUID(DRAWING_DWG)).page_count == 5


# ════════════════════════════════════════════════════════════════════════════
# US-011-AC-1 / AC-2 — scan job: converted key, user_id pass-through, queue, dispatch
# ════════════════════════════════════════════════════════════════════════════
def test_dwg_scan_job_enqueued_with_converted_storage_reference(
    db, monkeypatch, publish_calls, scan_calls, uploads
):
    _run_dwg_success(db, monkeypatch, _make_pdf(2))
    assert scan_calls[0]["kwargs"]["storage_reference"] == f"converted/{DRAWING_DWG}/drawing.pdf"


def test_user_id_passed_through_to_scan_job_no_db_lookup(
    db, monkeypatch, publish_calls, scan_calls
):
    pdf = _make_pdf(1)
    # owner_user_id deliberately differs from the payload user_id; the scan job
    # must carry the PAYLOAD user_id (proves no DB lookup, §1.4 rule 5).
    other_owner = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf), owner_user_id=other_owner,
    )
    _patch_download(monkeypatch, pdf)

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    assert scan_calls[0]["kwargs"]["user_id"] == USER_ID
    assert scan_calls[0]["kwargs"]["user_id"] != other_owner
    assert scan_calls[0]["kwargs"]["drawing_id"] == DRAWING_PDF


def test_scan_job_enqueued_on_correct_queue(db, monkeypatch, publish_calls, scan_calls):
    pdf = _make_pdf(1)
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf),
    )
    _patch_download(monkeypatch, pdf)

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    from app.workers.queues import QUEUE_SCAN

    assert scan_calls[0]["queue"] == QUEUE_SCAN == "scan"


def test_scan_job_dispatched_via_send_task_not_direct_import(
    db, monkeypatch, publish_calls, scan_calls
):
    pdf = _make_pdf(1)
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf),
    )
    _patch_download(monkeypatch, pdf)

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    # String-based dispatch with the exact cross-session task name.
    assert scan_calls[0]["name"] == "workers.scan.tasks.scan_task"
    assert scan_calls[0]["name"] == tasks.SCAN_TASK_NAME
    # And the worker never imports the S2-I scan package (string-name dispatch
    # only). The task-name string constant legitimately contains "workers.scan",
    # so check for actual import statements rather than the bare substring.
    src = Path(tasks.__file__).read_text(encoding="utf-8")
    import_lines = [
        ln for ln in src.splitlines()
        if ln.lstrip().startswith(("import ", "from "))
    ]
    assert not any("workers.scan" in ln for ln in import_lines)
    assert not any("scan.tasks" in ln for ln in import_lines)


# ════════════════════════════════════════════════════════════════════════════
# US-003-AC-7 — ODA license expiry monitoring
# ════════════════════════════════════════════════════════════════════════════
def test_oda_license_expiry_warning_within_30_days(caplog):
    near = (date.today() + timedelta(days=10)).isoformat()
    with caplog.at_level(logging.WARNING, logger="pid.workers.ingest.oda"):
        oda_converter.check_oda_license_expiry(near)
    assert any(
        "license expires" in r.getMessage().lower() for r in caplog.records
    ), "expected a WARNING about imminent license expiry"


def test_oda_license_expiry_absent_logs_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="pid.workers.ingest.oda"):
        result = oda_converter.check_oda_license_expiry(None)
    assert result is None  # absence does not block conversion
    assert any(
        "absent" in r.getMessage().lower() for r in caplog.records
    ), "expected a WARNING that the expiry date is absent"


def test_oda_license_expiry_far_future_no_warning(caplog):
    far = (date.today() + timedelta(days=400)).isoformat()
    with caplog.at_level(logging.WARNING, logger="pid.workers.ingest.oda"):
        oda_converter.check_oda_license_expiry(far)
    assert not any("expires" in r.getMessage().lower() for r in caplog.records)


# ════════════════════════════════════════════════════════════════════════════
# US-009-AC-1 — retry reuses the existing stored_file_id (no new upload)
# ════════════════════════════════════════════════════════════════════════════
def test_retry_reuses_existing_stored_file_id(db, monkeypatch, publish_calls, scan_calls, uploads):
    pdf = _make_pdf(2)
    # A previously-Failed drawing reset back to Queued by S2-B, same stored file.
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf), state="Queued",
    )
    _patch_download(monkeypatch, pdf)

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    drawing = db.get(Drawing, uuid.UUID(DRAWING_PDF))
    assert drawing.stored_file_id == uuid.UUID(STORED_FILE_PDF)  # unchanged
    assert uploads == []  # no new S3 upload
    assert scan_calls[0]["kwargs"]["storage_reference"] == PDF_KEY


# ════════════════════════════════════════════════════════════════════════════
# US-008-AC-2 — SSE event schema fields
# ════════════════════════════════════════════════════════════════════════════
def test_sse_event_schema_fields():
    event = DrawingStatusSSEEvent(
        drawing_id=DRAWING_PDF, state="Scanning", timestamp="2026-05-31T12:00:00Z"
    )
    assert set(event.model_dump().keys()) == {"drawing_id", "state", "timestamp"}


# ════════════════════════════════════════════════════════════════════════════
# technical — ingest task registered & routed to the ingest queue
# ════════════════════════════════════════════════════════════════════════════
def test_ingest_task_registered_on_ingest_queue():
    assert tasks.INGEST_TASK_NAME == "workers.ingest.tasks.ingest_task"
    assert tasks.INGEST_TASK_NAME in tasks.celery_app.tasks
    route = tasks.celery_app.amqp.router.route({}, tasks.INGEST_TASK_NAME)
    assert route["queue"].name == "ingest"


# ════════════════════════════════════════════════════════════════════════════
# technical — Redis publish failure is logged but never fails the task
# ════════════════════════════════════════════════════════════════════════════
def test_redis_publish_failure_does_not_fail_task(db, monkeypatch, scan_calls):
    pdf = _make_pdf(1)
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf),
    )
    _patch_download(monkeypatch, pdf)

    # Exercise the REAL _publish_status; make the underlying async publish raise.
    async def _boom(drawing_id, event):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(tasks, "publish_drawing_status", _boom)

    # Must not raise despite the publish failure...
    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    # ...and processing still progressed to enqueue the scan job.
    assert _state(db, DRAWING_PDF) == "Scanning"
    assert len(scan_calls) == 1


# ════════════════════════════════════════════════════════════════════════════
# technical — processed_at is NOT modified by the ingest worker (owned by S2-J)
# ════════════════════════════════════════════════════════════════════════════
def test_processed_at_not_modified_by_ingest_worker(db, monkeypatch, publish_calls, scan_calls):
    pdf = _make_pdf(1)
    _seed_drawing(
        db, drawing_id=DRAWING_PDF, stored_file_id=STORED_FILE_PDF,
        object_key=PDF_KEY, sha256=_sha256(pdf), processed_at=None,
    )
    _patch_download(monkeypatch, pdf)

    tasks._run_ingest(_payload(DRAWING_PDF, STORED_FILE_PDF, PDF_KEY), db)

    assert db.get(Drawing, uuid.UUID(DRAWING_PDF)).processed_at is None


# ════════════════════════════════════════════════════════════════════════════
# technical — free-tier counter is NOT touched by the ingest worker (§1.4 rule 8)
# ════════════════════════════════════════════════════════════════════════════
def test_free_tier_counter_not_modified():
    """The ingest worker never reads or writes the free-tier counter / subscription."""
    src = Path(tasks.__file__).read_text(encoding="utf-8").lower()
    for forbidden in ("subscription", "free_tier", "counter", "increment"):
        assert forbidden not in src, f"ingest worker must not reference {forbidden!r}"


# ════════════════════════════════════════════════════════════════════════════
# [MANUAL ACs automated] — ODA sandbox docker command security flags
# ════════════════════════════════════════════════════════════════════════════
def test_oda_docker_command_security_flags():
    cmd = oda_converter._build_oda_command("/tmp/work-123")
    joined = " ".join(cmd)
    # --network none (no egress)
    assert "--network" in cmd and cmd[cmd.index("--network") + 1] == "none"
    # non-root user
    assert "--user" in cmd and cmd[cmd.index("--user") + 1] == "1000:1000"
    # read-only host filesystem (except the work-dir mount + tmpfs)
    assert "--read-only" in cmd
    assert "--tmpfs" in cmd
    assert "/tmp/work-123:/work" in cmd
    # never privileged; never mounts the docker socket
    assert "--privileged" not in cmd
    assert "docker.sock" not in joined
