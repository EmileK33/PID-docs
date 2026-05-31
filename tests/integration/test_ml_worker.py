"""Integration tests for the S2-J ML inference worker.

Run: ``pytest tests/integration/test_ml_worker.py -v``

Design (isolation rule from the brief): the Celery task is invoked **directly**
via ``run_ml_inference.apply(...)`` under ``task_always_eager`` — no live broker,
no S2-H/S2-I siblings. Two tiers of test:

* **Fake-session tier** (runs everywhere, incl. the no-Docker ``session-tests``
  gate): patches the S3 / inference / Redis / analytics seams in the task module
  and drives a hand-rolled ``FakeSession`` + ``FakeDrawing``. The *real*
  ``persist_inference_results`` runs against the fake session, so symbol-field
  mapping, page-range filtering, ``estimated_symbol_count``, the single-commit
  ordering and the US-021 table P1-STUB are all exercised without a database.
* **Real-Postgres tier** (skipped unless a Postgres is reachable, i.e. only the
  ``integration`` workflow): proves real atomic persistence + the ``Complete`` /
  ``Failed`` DB transitions and JSONB ``bbox`` round-trip.

App modules are imported **lazily inside fixtures/tests**, never at module top, so
test collection does not leak ``app.*`` into ``sys.modules`` (the S0-B smoke guard).
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path

import pytest

# --- Make the backend `app` package importable -----------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "backend"
for _p in (str(_BACKEND), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- §1.12 "Refuse to start" env contract ----------------------------------
# The shared conftest seeds most vars but not the ML/ODA pair; set them (and the
# rest, setdefault so CI/dev wins) before any lazy import of app.config.
for _k, _v in {
    "DATABASE_URL": "postgresql://u:p@localhost:5432/pid",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_BUCKET_NAME": "pid-test-bucket",
    "S3_REGION": "eu-central-1",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
    "JWT_RS256_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\nMIIB\n-----END PUBLIC KEY-----",
    "STRIPE_SECRET_KEY": "sk_test_dummy",
    "STRIPE_WEBHOOK_SECRET": "whsec_dummy",
    "SENDGRID_API_KEY": "SG.dummy",
    "HMAC_SERVER_SECRET": "high-entropy-secret",
    "ML_MODEL_S3_KEY": "models/pid/v1.onnx",
    "ODA_CONVERTER_PATH": "/opt/oda/ODAFileConverter",
}.items():
    os.environ.setdefault(_k, _v)


# ---------------------------------------------------------------------------
# Postgres availability probe (third-party imports only — no app.*).
# ---------------------------------------------------------------------------
def _postgres_available() -> bool:
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import make_url

        url = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql+psycopg")
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


_PG = _postgres_available()
requires_pg = pytest.mark.skipif(
    not _PG, reason="Postgres not reachable (runs in the integration workflow only)"
)


# ---------------------------------------------------------------------------
# In-memory test doubles for the DB session / drawing.
# ---------------------------------------------------------------------------
class FakeDrawing:
    """Minimal stand-in for the Drawing ORM row (plain attributes)."""

    def __init__(self, drawing_id: str, state: str = "Processing"):
        self.id = uuid.UUID(drawing_id)
        self.processing_state = state
        self.processed_at = None
        self.estimated_symbol_count = None
        self.page_count = None


class FakeSession:
    """Records adds/commits/rollbacks and snapshots state at each commit.

    ``get`` returns the configured drawing regardless of key (the worker and the
    persistence layer both look up the same single drawing).
    """

    def __init__(self, drawing):
        self._drawing = drawing
        self.added: list = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0
        self.commit_error: Exception | None = None
        self.commit_snapshots: list[dict] = []

    def get(self, _model, _pk):
        return self._drawing

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    def commit(self):
        # Snapshot BEFORE (maybe) raising so atomicity ordering is observable.
        self.commit_snapshots.append(
            {
                "n_added": len(self.added),
                "state": getattr(self._drawing, "processing_state", None),
                "estimated": getattr(self._drawing, "estimated_symbol_count", None),
            }
        )
        if self.commit_error is not None:
            raise self.commit_error
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1


def _mock_result(contracts, drawing_id: str, *, symbols=None, tables=None):
    c = contracts
    if symbols is None:
        symbols = [
            c.DetectedSymbolResult(
                entity_class_id="valve_gate",
                subtype="manual",
                tag_label="V-101",
                confidence=0.92,
                bbox=c.BoundingBox(x=100, y=200, w=50, h=50),
                page_number=1,
            ),
            c.DetectedSymbolResult(
                entity_class_id="pipe",
                subtype="",
                tag_label=None,
                confidence=0.87,
                bbox=c.BoundingBox(x=300, y=400, w=200, h=10),
                page_number=1,
            ),
        ]
    return c.MLInferenceResult(drawing_id=drawing_id, symbols=symbols, tables=tables or [])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def eager_celery():
    """Execute tasks synchronously, returning a result (not raising) on failure."""
    from app.workers.celery_app import celery_app

    prev_eager = celery_app.conf.task_always_eager
    prev_prop = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    try:
        yield
    finally:
        celery_app.conf.task_always_eager = prev_eager
        celery_app.conf.task_eager_propagates = prev_prop


class _Harness:
    """Wires the task module's seams to in-memory doubles and runs the task."""

    def __init__(self, monkeypatch):
        from app.schemas import contracts as c
        from app.workers.ml import model_loader as ml
        from app.workers.ml import tasks as t

        self.t = t
        self.c = c
        self.ml = ml
        self.mp = monkeypatch

        self.drawing_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        self.drawing = FakeDrawing(self.drawing_id, state="Processing")
        self.session = FakeSession(self.drawing)

        # Recorders.
        self.pub_calls: list = []
        self.complete_calls: list = []
        self.failed_calls: list = []
        self.inf_calls: list = []
        self.result = _mock_result(c, self.drawing_id)

        # Model loader: real load_model (caches), but its S3 download is faked +
        # counted so the "loaded once across tasks" AC is observable.
        ml.reset_model_cache()
        self.model_download_calls = {"n": 0}

        def _fake_model_download(bucket, key, *, client=None):
            self.model_download_calls["n"] += 1
            return b"fake-model-bytes"

        monkeypatch.setattr(ml, "download_s3_bytes", _fake_model_download)
        monkeypatch.setattr(t, "load_model", ml.load_model)

        # DB session factory → the fake.
        monkeypatch.setattr(t, "SessionLocal", lambda: self.session)

        # Drawing-file download.
        monkeypatch.setattr(t, "download_s3_bytes", lambda bucket, key: b"%PDF-1.4 minimal")

        # Inference (default: succeeds, returns the mock result).
        def _infer(model, file_bytes, did, page_range=None):
            self.inf_calls.append((did, page_range))
            return self.result

        monkeypatch.setattr(t, "run_inference", _infer)

        # Redis pub/sub (async) — record, then no-op close.
        async def _publish(did, event):
            self.pub_calls.append((did, event))

        async def _close():
            return None

        monkeypatch.setattr(t, "publish_drawing_status", _publish)
        monkeypatch.setattr(t, "close_redis", _close)

        # Analytics emitters (called with keyword args by the worker).
        monkeypatch.setattr(
            t,
            "emit_processing_complete",
            lambda user_id, drawing_id: self.complete_calls.append((user_id, drawing_id)),
        )
        monkeypatch.setattr(
            t,
            "emit_processing_failed",
            lambda user_id, drawing_id: self.failed_calls.append((user_id, drawing_id)),
        )

    # -- inference behaviour mutators --
    def inference_raises_once(self, exc=None):
        exc = exc or RuntimeError("transient inference failure")
        state = {"n": 0}

        def _infer(model, file_bytes, did, page_range=None):
            self.inf_calls.append((did, page_range))
            state["n"] += 1
            if state["n"] == 1:
                raise exc
            return self.result

        self.mp.setattr(self.t, "run_inference", _infer)

    def inference_always_raises(self, exc=None):
        exc = exc or RuntimeError("permanent inference failure")

        def _infer(model, file_bytes, did, page_range=None):
            self.inf_calls.append((did, page_range))
            raise exc

        self.mp.setattr(self.t, "run_inference", _infer)

    def complete_emit_raises(self):
        def _emit(user_id, drawing_id):
            self.complete_calls.append((user_id, drawing_id))
            raise RuntimeError("posthog down")

        self.mp.setattr(self.t, "emit_processing_complete", _emit)

    def failed_emit_raises(self):
        def _emit(user_id, drawing_id):
            self.failed_calls.append((user_id, drawing_id))
            raise RuntimeError("posthog down")

        self.mp.setattr(self.t, "emit_processing_failed", _emit)

    # -- run --
    def payload(self, *, page_range=None, omit_user=False):
        p = {
            "storage_reference": "drawings/test-drawing-id/test.pdf",
            "drawing_id": self.drawing_id,
            "user_id": self.user_id,
        }
        if page_range is not None:
            p["page_range"] = page_range
        if omit_user:
            p.pop("user_id")
        return p

    def run(self, **kwargs):
        return self.t.run_ml_inference.apply(args=[self.payload(**kwargs)])


@pytest.fixture
def harness(monkeypatch):
    h = _Harness(monkeypatch)
    try:
        yield h
    finally:
        h.ml.reset_model_cache()


@pytest.fixture
def persist():
    """The real persistence function + a fake-session factory."""
    from app.schemas import contracts as c
    from app.workers.ml.result_persistence import persist_inference_results

    def _make(state="Processing"):
        drawing_id = str(uuid.uuid4())
        drawing = FakeDrawing(drawing_id, state=state)
        return FakeSession(drawing), drawing, drawing_id

    return persist_inference_results, _make, c


# ===========================================================================
# Fake-session tier — runs everywhere.
# ===========================================================================
def test_successful_inference_transitions_drawing_to_complete(harness):
    """US-011 AC-1 / US-008 AC-1."""
    result = harness.run()
    assert result.state == "SUCCESS"
    assert harness.drawing.processing_state == "Complete"
    assert harness.drawing.processed_at is not None
    assert harness.session.commits == 1


def test_detected_symbols_written_with_correct_fields(persist):
    """US-011 AC-3 — field mapping + source/rejected defaults."""
    persist_fn, make, c = persist
    session, drawing, drawing_id = make()
    count = persist_fn(session, drawing_id, _mock_result(c, drawing_id))

    assert count == 2
    assert len(session.added) == 2
    by_class = {s.entity_class_id: s for s in session.added}

    gate = by_class["valve_gate"]
    assert gate.subtype == "manual"
    assert gate.tag_label == "V-101"
    assert gate.confidence == 0.92
    assert gate.bbox == {"x": 100, "y": 200, "w": 50, "h": 50}
    assert gate.page_number == 1
    assert gate.source == "ml"
    assert gate.rejected is False
    assert gate.drawing_id == drawing.id

    pipe = by_class["pipe"]
    assert pipe.tag_label is None
    assert pipe.confidence == 0.87
    assert pipe.source == "ml"
    assert pipe.rejected is False


def test_result_persistence_is_atomic(persist):
    """US-011 AC-4 / AC-6 — symbols + drawing update in a single commit."""
    persist_fn, make, c = persist
    session, drawing, drawing_id = make()
    persist_fn(session, drawing_id, _mock_result(c, drawing_id))

    # Exactly one commit, and at that commit both symbols were staged AND the
    # drawing was already marked Complete (never a state update before inserts).
    assert session.commits == 1
    assert len(session.commit_snapshots) == 1
    snap = session.commit_snapshots[0]
    assert snap["n_added"] == 2
    assert snap["state"] == "Complete"
    assert snap["estimated"] == 2


def test_result_persistence_raises_and_does_not_swallow_commit_failure(persist):
    """US-011 AC-6 — a commit failure propagates (caller rolls back / retries)."""
    persist_fn, make, c = persist
    session, drawing, drawing_id = make()
    session.commit_error = RuntimeError("db down")
    with pytest.raises(RuntimeError, match="db down"):
        persist_fn(session, drawing_id, _mock_result(c, drawing_id))
    # The single commit was attempted with everything staged together.
    assert session.commits == 0
    assert session.commit_snapshots[0]["n_added"] == 2


def test_estimated_symbol_count_set_on_drawing(persist):
    """US-011 AC-7."""
    persist_fn, make, c = persist
    session, drawing, drawing_id = make()
    count = persist_fn(session, drawing_id, _mock_result(c, drawing_id))
    assert count == 2
    assert drawing.estimated_symbol_count == 2


def test_sse_event_published_on_complete(harness):
    """US-008 AC-2."""
    from datetime import datetime

    harness.run()
    assert len(harness.pub_calls) == 1
    did, event = harness.pub_calls[0]
    assert did == harness.drawing_id
    assert event.state == "Complete"
    assert event.drawing_id == harness.drawing_id
    # ISO 8601 UTC timestamp.
    parsed = datetime.fromisoformat(event.timestamp)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_processing_complete_analytics_emitted_on_success(harness):
    """US-010 AC-1."""
    harness.run()
    assert harness.complete_calls == [(harness.user_id, harness.drawing_id)]
    assert harness.failed_calls == []


def test_analytics_user_id_from_payload_not_db(harness):
    """US-010 AC-1 — user_id is exactly the payload value, never resolved from DB."""
    harness.user_id = "user-uuid-from-payload-12345"
    harness.run()
    assert harness.complete_calls[0][0] == "user-uuid-from-payload-12345"


def test_task_retries_once_on_first_inference_failure(harness):
    """US-008 AC-3 — first attempt fails, retry succeeds → 2 attempts, Complete."""
    harness.inference_raises_once()
    result = harness.run()
    assert result.state == "SUCCESS"
    assert len(harness.inf_calls) == 2  # exactly one retry
    assert harness.drawing.processing_state == "Complete"
    assert harness.complete_calls == [(harness.user_id, harness.drawing_id)]
    assert harness.failed_calls == []


def test_drawing_transitions_to_failed_after_retry_exhausted(harness):
    """US-008 AC-4 / AC-6 — both attempts fail → Failed."""
    harness.inference_always_raises()
    result = harness.run()
    assert result.state == "FAILURE"
    assert len(harness.inf_calls) == 2
    assert harness.drawing.processing_state == "Failed"


def test_sse_event_published_on_failed(harness):
    """US-008 AC-4."""
    harness.inference_always_raises()
    harness.run()
    assert len(harness.pub_calls) == 1
    did, event = harness.pub_calls[0]
    assert did == harness.drawing_id
    assert event.state == "Failed"


def test_processing_failed_analytics_emitted_after_retries_exhausted(harness):
    """US-010 AC-2 — failed event fires once, with payload user_id; complete never."""
    harness.inference_always_raises()
    harness.run()
    assert harness.failed_calls == [(harness.user_id, harness.drawing_id)]
    assert harness.complete_calls == []


def test_complete_and_failed_not_both_emitted(harness):
    """US-010 AC-3 — success path emits complete only, never failed."""
    harness.run()
    assert len(harness.complete_calls) == 1
    assert len(harness.failed_calls) == 0


def test_analytics_exception_does_not_propagate_on_success(harness):
    """US-010 AC-4 — a raising complete-emitter does not fail the task or revert state."""
    harness.complete_emit_raises()
    result = harness.run()
    assert result.state == "SUCCESS"
    assert harness.drawing.processing_state == "Complete"
    assert len(harness.complete_calls) == 1  # attempted once, exception swallowed


def test_analytics_exception_does_not_propagate_on_failure(harness):
    """US-010 AC-4 — a raising failed-emitter does not crash on_failure or revert state."""
    harness.inference_always_raises()
    harness.failed_emit_raises()
    result = harness.run()
    assert result.state == "FAILURE"
    assert harness.drawing.processing_state == "Failed"
    assert len(harness.failed_calls) == 1


def test_page_range_filters_symbols(persist):
    """US-011 AC-5 — only symbols inside the inclusive range are persisted."""
    persist_fn, make, c = persist
    session, drawing, drawing_id = make()
    symbols = [
        c.DetectedSymbolResult(
            entity_class_id="pipe", subtype="", tag_label=None, confidence=0.5,
            bbox=c.BoundingBox(x=0, y=0, w=1, h=1), page_number=p,
        )
        for p in (1, 2, 3)
    ]
    result = _mock_result(c, drawing_id, symbols=symbols)
    count = persist_fn(session, drawing_id, result, page_range=(2, 2))
    assert count == 1
    assert len(session.added) == 1
    assert session.added[0].page_number == 2
    assert drawing.estimated_symbol_count == 1
    # page_range present → page_count is left to ingest, not overwritten.
    assert drawing.page_count is None


def test_page_count_derived_when_no_page_range(persist):
    """§ critical note — full-doc run derives page_count from max symbol page."""
    persist_fn, make, c = persist
    session, drawing, drawing_id = make()
    symbols = [
        c.DetectedSymbolResult(
            entity_class_id="pipe", subtype="", tag_label=None, confidence=0.5,
            bbox=c.BoundingBox(x=0, y=0, w=1, h=1), page_number=p,
        )
        for p in (1, 2, 5)
    ]
    persist_fn(session, drawing_id, _mock_result(c, drawing_id, symbols=symbols))
    assert drawing.page_count == 5


def test_task_noop_when_drawing_not_in_processing_state(harness):
    """US-008 AC-7 — wrong state → no inference, no persistence, no events."""
    harness.drawing.processing_state = "Failed"
    result = harness.run()
    assert result.state == "SUCCESS"  # no-op, not an error
    assert harness.inf_calls == []
    assert harness.session.added == []
    assert harness.session.commits == 0
    assert harness.complete_calls == []
    assert harness.failed_calls == []
    assert harness.pub_calls == []


def test_task_noop_when_drawing_scan_failed(harness):
    """US-008 AC-7 [MANUAL] — terminal Scan_Failed is never processed."""
    harness.drawing.processing_state = "Scan_Failed"
    result = harness.run()
    assert result.state == "SUCCESS"
    assert harness.inf_calls == []
    assert harness.drawing.processing_state == "Scan_Failed"  # untouched
    assert harness.complete_calls == []
    assert harness.failed_calls == []


def test_task_raises_when_drawing_not_found(harness):
    """US-008 AC-7 — missing drawing raises, emits no analytics, corrupts nothing."""
    harness.session._drawing = None
    result = harness.run()
    assert result.state == "FAILURE"
    assert isinstance(result.result, harness.t.DrawingNotFoundError)
    assert harness.inf_calls == []
    assert harness.complete_calls == []
    assert harness.failed_calls == []  # on_failure re-checks, finds no row → no emit


def test_table_results_not_persisted_in_p0(persist, caplog):
    """US-021 AC-1 P1-STUB — tables accepted but never written; debug logged."""
    persist_fn, make, c = persist
    session, drawing, drawing_id = make()
    tables = [
        c.TableRegionResult(
            bbox=c.BoundingBox(x=0, y=0, w=10, h=10),
            page_number=1,
            cells=[
                c.TableCellResult(
                    row_label="r1", column_label="c1",
                    bbox=c.BoundingBox(x=1, y=1, w=2, h=2), extracted_value="42",
                )
            ],
        )
    ]
    result = _mock_result(c, drawing_id, tables=tables)
    with caplog.at_level(logging.DEBUG, logger="pid.workers.ml.result_persistence"):
        persist_fn(session, drawing_id, result)

    # Only detected symbols were staged — nothing table-shaped.
    assert all(type(o).__name__ == "DetectedSymbol" for o in session.added)
    assert any("P1-STUB" in r.getMessage() for r in caplog.records)


def test_model_loader_called_once_across_multiple_tasks(harness):
    """US-011 AC-2 — the model artifact is downloaded once, then reused."""
    r1 = harness.run()
    # Reset only the per-drawing state so a second task reuses the cached model.
    harness.drawing.processing_state = "Processing"
    harness.session.commits = 0
    r2 = harness.run()
    assert r1.state == "SUCCESS"
    assert r2.state == "SUCCESS"
    assert harness.model_download_calls["n"] == 1  # loaded once, cached thereafter


def test_missing_user_id_still_processes_drawing_but_skips_analytics(harness, caplog):
    """§ critical note — defensive: no user_id => process anyway, skip analytics."""
    with caplog.at_level(logging.ERROR, logger="pid.workers.ml.tasks"):
        result = harness.run(omit_user=True)
    assert result.state == "SUCCESS"
    assert harness.drawing.processing_state == "Complete"
    assert harness.complete_calls == []  # analytics skipped
    assert any("user_id" in r.getMessage() for r in caplog.records)


# ===========================================================================
# Task configuration ([MANUAL] ACs — static / config assertions).
# ===========================================================================
def test_task_name_and_queue_contract():
    """[LOAD-BEARING] task name (S2-B hardcodes it) + durable ml_inference queue."""
    from app.workers.ml.tasks import ML_INFERENCE_QUEUE, run_ml_inference

    assert run_ml_inference.name == "app.workers.ml.tasks.run_ml_inference"
    assert run_ml_inference.queue == "ml_inference"
    assert ML_INFERENCE_QUEUE == "ml_inference"


def test_task_retry_and_timeout_config():
    """US-008 AC-5 [MANUAL] — 1 retry, 20-min soft limit, +60s hard limit."""
    from app.config import settings
    from app.workers.ml.tasks import run_ml_inference

    assert run_ml_inference.max_retries == 1
    assert run_ml_inference.retry_kwargs == {"max_retries": 1}
    assert run_ml_inference.soft_time_limit == settings.ML_JOB_TIMEOUT_SECONDS
    assert run_ml_inference.time_limit == settings.ML_JOB_TIMEOUT_SECONDS + 60
    assert run_ml_inference.soft_time_limit == 1200  # default 20 min


def test_no_user_id_db_lookup_in_worker_sources():
    """US-010 AC-1/AC-2 [MANUAL] — no User-model DB lookup anywhere in the worker."""
    import app.workers.ml.inference as inf
    import app.workers.ml.result_persistence as rp
    import app.workers.ml.tasks as tk

    for module in (tk, rp, inf):
        src = Path(module.__file__).read_text(encoding="utf-8")
        assert "models.user" not in src, f"{module.__name__} imports the User model"
        # No ORM query/get against a User table to resolve user_id.
        assert "User" not in src.replace("user_id", "").replace("user ", ""), (
            f"{module.__name__} references the User model"
        )


def test_worker_refuses_to_start_without_required_env(monkeypatch):
    """ENV-STARTUP [MANUAL] — Settings refuses to construct without the required vars."""
    from pydantic import ValidationError

    from app.config import Settings

    for var in ("ML_MODEL_S3_KEY", "DATABASE_URL", "REDIS_URL", "S3_BUCKET_NAME", "S3_REGION"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


# ===========================================================================
# Real-Postgres tier — skipped unless a database is reachable.
# ===========================================================================
def _seed_and_make_drawing(Session, state="Processing"):
    """Create a user + Processing drawing (ensuring entity_class seed). Returns ids."""
    from app.db.models.drawing import Drawing
    from app.db.models.entity_class import EntityClass
    from app.db.models.user import User
    from app.db.seed_entity_classes import ENTITY_CLASS_SEED_DATA

    s = Session()
    try:
        for row in ENTITY_CLASS_SEED_DATA:
            if s.get(EntityClass, row["id"]) is None:
                s.add(EntityClass(**row))
        s.flush()
        user = User(
            email=f"mltest-{uuid.uuid4()}@example.com",
            display_name="ML Worker Test",
            role="user",
        )
        s.add(user)
        s.flush()
        drawing = Drawing(owner_user_id=user.id, filename="test.pdf", processing_state=state)
        s.add(drawing)
        s.commit()
        return str(user.id), str(drawing.id)
    finally:
        s.close()


def _cleanup(Session, user_id, drawing_id):
    from app.db.models.detected_symbol import DetectedSymbol
    from app.db.models.drawing import Drawing
    from app.db.models.user import User

    s = Session()
    try:
        s.query(DetectedSymbol).filter_by(drawing_id=uuid.UUID(drawing_id)).delete()
        d = s.get(Drawing, uuid.UUID(drawing_id))
        if d is not None:
            s.delete(d)
        u = s.get(User, uuid.UUID(user_id))
        if u is not None:
            s.delete(u)
        s.commit()
    finally:
        s.close()


def _patch_worker_seams(monkeypatch, t, c, Session, drawing_id, *, result=None):
    monkeypatch.setattr(t, "SessionLocal", Session)
    monkeypatch.setattr(t, "load_model", lambda: object())
    monkeypatch.setattr(t, "download_s3_bytes", lambda bucket, key: b"%PDF-1.4 minimal")
    monkeypatch.setattr(
        t, "run_inference",
        lambda model, fb, did, page_range=None: result or _mock_result(c, drawing_id),
    )

    async def _publish(did, event):
        return None

    async def _close():
        return None

    monkeypatch.setattr(t, "publish_drawing_status", _publish)
    monkeypatch.setattr(t, "close_redis", _close)
    monkeypatch.setattr(t, "emit_processing_complete", lambda user_id, drawing_id: None)
    monkeypatch.setattr(t, "emit_processing_failed", lambda user_id, drawing_id: None)


@requires_pg
def test_real_postgres_successful_inference_persists_and_completes(db_engine, monkeypatch):
    """US-011 AC-1/AC-3/AC-4 in a real database (the checkpoint claim)."""
    from sqlalchemy.orm import sessionmaker

    from app.db.models.detected_symbol import DetectedSymbol
    from app.db.models.drawing import Drawing
    from app.schemas import contracts as c
    from app.workers.ml import tasks as t

    Session = sessionmaker(bind=db_engine, future=True, expire_on_commit=False)
    user_id, drawing_id = _seed_and_make_drawing(Session)
    try:
        _patch_worker_seams(monkeypatch, t, c, Session, drawing_id)
        result = t.run_ml_inference.apply(
            args=[{"storage_reference": "drawings/x/test.pdf", "drawing_id": drawing_id, "user_id": user_id}]
        )
        assert result.state == "SUCCESS"

        verify = Session()
        try:
            d = verify.get(Drawing, uuid.UUID(drawing_id))
            assert d.processing_state == "Complete"
            assert d.processed_at is not None
            assert d.estimated_symbol_count == 2
            rows = verify.query(DetectedSymbol).filter_by(drawing_id=uuid.UUID(drawing_id)).all()
            assert len(rows) == 2
            assert {r.source for r in rows} == {"ml"}
            assert all(r.rejected is False for r in rows)
            gate = next(r for r in rows if r.entity_class_id == "valve_gate")
            assert gate.bbox == {"x": 100, "y": 200, "w": 50, "h": 50}  # JSONB round-trip
        finally:
            verify.close()
    finally:
        _cleanup(Session, user_id, drawing_id)


@requires_pg
def test_real_postgres_persistence_is_atomic_on_failure(db_engine, monkeypatch):
    """US-011 AC-6 in a real database — a bad row writes NO symbols and ends Failed."""
    from sqlalchemy.orm import sessionmaker

    from app.db.models.detected_symbol import DetectedSymbol
    from app.db.models.drawing import Drawing
    from app.schemas import contracts as c
    from app.workers.ml import tasks as t

    Session = sessionmaker(bind=db_engine, future=True, expire_on_commit=False)
    user_id, drawing_id = _seed_and_make_drawing(Session)
    try:
        # One valid symbol + one with an FK-violating entity_class_id → commit fails
        # atomically, so neither is written.
        symbols = [
            c.DetectedSymbolResult(
                entity_class_id="valve_gate", subtype="", tag_label=None, confidence=0.9,
                bbox=c.BoundingBox(x=1, y=1, w=1, h=1), page_number=1,
            ),
            c.DetectedSymbolResult(
                entity_class_id="not_a_real_class", subtype="", tag_label=None, confidence=0.9,
                bbox=c.BoundingBox(x=2, y=2, w=1, h=1), page_number=1,
            ),
        ]
        bad = _mock_result(c, drawing_id, symbols=symbols)
        _patch_worker_seams(monkeypatch, t, c, Session, drawing_id, result=bad)

        result = t.run_ml_inference.apply(
            args=[{"storage_reference": "drawings/x/test.pdf", "drawing_id": drawing_id, "user_id": user_id}]
        )
        assert result.state == "FAILURE"

        verify = Session()
        try:
            count = verify.query(DetectedSymbol).filter_by(drawing_id=uuid.UUID(drawing_id)).count()
            assert count == 0  # atomic: no partial rows
            d = verify.get(Drawing, uuid.UUID(drawing_id))
            assert d.processing_state == "Failed"
        finally:
            verify.close()
    finally:
        _cleanup(Session, user_id, drawing_id)
