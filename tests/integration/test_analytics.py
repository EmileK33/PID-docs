"""Integration tests for the S1-E analytics emitter (§1.10).

Run: ``pytest tests/integration/test_analytics.py -v``

These exercise the typed emitters, the non-blocking guarantee, the disabled-mode
no-op, the Redis dead-letter queue (push + 10k cap + retry/requeue) and
server-side timestamp generation. PostHog's network call is never made: the
module-level ``posthog.capture`` is monkeypatched and a fakeredis instance backs
the dead-letter list, so the suite passes with only S0-A + S0-B + S1-E merged
(no sibling Phase 1 session and no live Redis required).

NOTE: application code (``app.analytics``) is imported LAZILY, inside fixtures,
never at module import. The shared S0-B smoke suite asserts that no ``app.*``
module leaks into ``sys.modules`` during its run; pytest collects ``smoke/``
before this file and runs its tests first, so deferring the import keeps that
guard green when the whole ``tests/integration`` tree runs together.
"""
from __future__ import annotations

import inspect
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# --- Make the `app` package (rooted at backend/) importable -----------------
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(BACKEND), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- §1.12 "Refuse to start" env contract -----------------------------------
# The shared conftest seeds most of these, but not the ML/ODA pair nor PostHog;
# set every REQUIRED var (setdefault, so CI/dev overrides win) before the lazy
# import of app.config so it does not sys.exit(1). Most tests run *enabled*.
_REQUIRED_ENV = {
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
    # Analytics enabled for the majority of tests.
    "POSTHOG_API_KEY": "test-key",
    "POSTHOG_HOST": "https://test.posthog.example",
}
for _k, _v in _REQUIRED_ENV.items():
    os.environ.setdefault(_k, _v)

# Third-party imports are safe at module level (the smoke guard only flags
# app.* / frontend / marketing modules).
import fakeredis  # noqa: E402
import posthog  # noqa: E402

DEAD_LETTER_KEY = "analytics:dead_letter"

# Populated lazily by the autouse fixture so `app.*` stays out of sys.modules
# until the first analytics test runs.
events = None
posthog_client = None
dead_letter = None


def _all_emitters():
    return (
        events.emit_drawing_uploaded,
        events.emit_processing_complete,
        events.emit_processing_failed,
        events.emit_correction_action,
        events.emit_export_initiated,
        events.emit_export_downloaded,
        events.emit_free_limit_reached,
        events.emit_subscription_upgraded,
        events.emit_subscription_downgraded,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_analytics_state():
    """Lazily import app.analytics, then bracket each test with analytics enabled."""
    global events, posthog_client, dead_letter
    from app.analytics import dead_letter as _dl
    from app.analytics import events as _ev
    from app.analytics import posthog_client as _pc

    events, posthog_client, dead_letter = _ev, _pc, _dl
    posthog_client.configure(api_key="test-key", host="https://test.posthog.example")
    yield
    posthog_client.configure(api_key="test-key", host="https://test.posthog.example")


@pytest.fixture
def fake_redis(monkeypatch):
    """Back the dead-letter queue with an in-process fakeredis (decode_responses)."""
    from app.analytics import dead_letter as _dl

    client = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(_dl, "_redis_client", client, raising=False)
    return client


@pytest.fixture
def captured(monkeypatch):
    """Record every ``posthog.capture`` call (kwargs) without hitting the network."""
    from app.analytics import posthog_client as _pc

    calls: list[dict] = []

    def _fake_capture(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return "msg-id"

    monkeypatch.setattr(posthog, "capture", _fake_capture)
    _pc.configure(api_key="test-key", host="https://test.posthog.example")
    return calls


def _props(calls: list[dict], index: int = 0) -> dict:
    return calls[index]["kwargs"]["properties"]


# ---------------------------------------------------------------------------
# Per-event payload shape  (AC: US-010)
# ---------------------------------------------------------------------------
def test_emit_drawing_uploaded_captures_correct_event_and_properties(captured):
    result = events.emit_drawing_uploaded("user-1", "drawing-1")
    assert result is None
    assert len(captured) == 1
    kw = captured[0]["kwargs"]
    assert kw["event"] == "drawing_uploaded"
    assert kw["distinct_id"] == "user-1"
    props = kw["properties"]
    assert props["user_id"] == "user-1"
    assert props["drawing_id"] == "drawing-1"
    assert "timestamp" in props


def test_emit_processing_complete_captures_correct_event_and_properties(captured):
    events.emit_processing_complete("user-2", "drawing-2")
    kw = captured[0]["kwargs"]
    assert kw["event"] == "processing_complete"
    assert kw["distinct_id"] == "user-2"
    assert _props(captured)["user_id"] == "user-2"
    assert _props(captured)["drawing_id"] == "drawing-2"


def test_emit_processing_failed_captures_correct_event_and_properties(captured):
    events.emit_processing_failed("user-3", "drawing-3")
    kw = captured[0]["kwargs"]
    assert kw["event"] == "processing_failed"
    assert _props(captured)["drawing_id"] == "drawing-3"
    assert _props(captured)["user_id"] == "user-3"


def test_emit_correction_action_includes_symbol_id(captured):
    events.emit_correction_action("user-4", "drawing-4", "symbol-4")
    assert captured[0]["kwargs"]["event"] == "correction_action"
    props = _props(captured)
    assert props["symbol_id"] == "symbol-4"
    assert props["drawing_id"] == "drawing-4"
    assert props["user_id"] == "user-4"


def test_emit_export_initiated_includes_format_field(captured):
    events.emit_export_initiated("user-5", "drawing-5", "export-5", "csv")
    assert captured[0]["kwargs"]["event"] == "export_initiated"
    props = _props(captured)
    assert props["format"] == "csv"
    assert props["export_id"] == "export-5"
    assert props["drawing_id"] == "drawing-5"


def test_emit_export_initiated_rejects_invalid_format(captured):
    with pytest.raises(ValueError):
        events.emit_export_initiated("user-5", "drawing-5", "export-5", "pdf")
    assert captured == []  # rejected before any capture


def test_emit_export_downloaded_captures_correct_event(captured):
    events.emit_export_downloaded("user-6", "drawing-6", "export-6")
    assert captured[0]["kwargs"]["event"] == "export_downloaded"
    props = _props(captured)
    assert props["export_id"] == "export-6"
    assert props["drawing_id"] == "drawing-6"
    assert props["user_id"] == "user-6"


def test_emit_free_limit_reached_includes_subscription_id(captured):
    events.emit_free_limit_reached("user-7", "drawing-7", "sub-7")
    assert captured[0]["kwargs"]["event"] == "free_limit_reached"
    props = _props(captured)
    assert props["subscription_id"] == "sub-7"
    assert props["drawing_id"] == "drawing-7"


def test_emit_subscription_upgraded_includes_both_tier_fields(captured):
    events.emit_subscription_upgraded("user-8", "sub-8", "free", "pro")
    assert captured[0]["kwargs"]["event"] == "subscription_upgraded"
    props = _props(captured)
    assert props["previous_tier"] == "free"
    assert props["new_tier"] == "pro"
    assert props["subscription_id"] == "sub-8"
    assert "drawing_id" not in props  # §1.10: subscription events carry no drawing_id


def test_emit_subscription_downgraded_includes_both_tier_fields(captured):
    events.emit_subscription_downgraded("user-9", "sub-9", "pro", "free")
    assert captured[0]["kwargs"]["event"] == "subscription_downgraded"
    props = _props(captured)
    assert props["previous_tier"] == "pro"
    assert props["new_tier"] == "free"
    assert props["subscription_id"] == "sub-9"


# ---------------------------------------------------------------------------
# Non-blocking guarantee  (AC: tech)
# ---------------------------------------------------------------------------
def test_emitter_returns_within_5ms(captured):
    events.emit_drawing_uploaded("u", "d")  # warm up import/branch paths
    best = min(
        _time_one(lambda: events.emit_drawing_uploaded("u", "d")) for _ in range(5)
    )
    assert best < 0.005, f"emitter took {best * 1000:.3f}ms (must be <5ms, non-blocking)"


def _time_one(fn) -> float:
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    assert result is None
    return elapsed


# ---------------------------------------------------------------------------
# Failure → dead-letter  (AC: tech)
# ---------------------------------------------------------------------------
def test_posthog_exception_pushes_event_to_redis_dead_letter_list(monkeypatch, fake_redis):
    def _boom(*args, **kwargs):
        raise RuntimeError("posthog network down")

    monkeypatch.setattr(posthog, "capture", _boom)
    posthog_client.configure(api_key="test-key")

    # Must NOT raise into the caller.
    assert events.emit_drawing_uploaded("user-x", "drawing-x") is None

    items = fake_redis.lrange(DEAD_LETTER_KEY, 0, -1)
    assert len(items) == 1
    envelope = json.loads(items[0])
    assert envelope["event"] == "drawing_uploaded"
    assert envelope["distinct_id"] == "user-x"
    assert envelope["properties"]["drawing_id"] == "drawing-x"
    assert envelope["properties"]["user_id"] == "user-x"
    assert "timestamp" in envelope["properties"]


# ---------------------------------------------------------------------------
# Disabled mode  (AC: tech)
# ---------------------------------------------------------------------------
def test_missing_posthog_api_key_makes_emitters_no_op_and_logs_warning(
    monkeypatch, fake_redis, caplog
):
    recorder: list = []
    monkeypatch.setattr(posthog, "capture", lambda *a, **k: recorder.append((a, k)))

    with caplog.at_level(logging.WARNING, logger="pid.analytics"):
        posthog_client.configure(api_key="")

    assert posthog_client.is_enabled() is False
    assert any(
        "POSTHOG_API_KEY" in r.getMessage() and "disabled" in r.getMessage().lower()
        for r in caplog.records
    )

    # Every emitter is a silent no-op: no capture, no dead-letter write.
    events.emit_drawing_uploaded("u", "d")
    events.emit_processing_complete("u", "d")
    assert recorder == []
    assert fake_redis.llen(DEAD_LETTER_KEY) == 0


# ---------------------------------------------------------------------------
# Dead-letter cap  (AC: tech)
# ---------------------------------------------------------------------------
def test_dead_letter_list_is_capped_at_10000_via_ltrim(monkeypatch, fake_redis):
    # Seed exactly the cap with placeholder envelopes (fast, via pipeline).
    pipe = fake_redis.pipeline()
    for i in range(10_000):
        pipe.rpush(
            DEAD_LETTER_KEY,
            json.dumps({"event": "seed", "distinct_id": "u", "properties": {"n": i}}),
        )
    pipe.execute()
    assert fake_redis.llen(DEAD_LETTER_KEY) == 10_000

    # One more failed emission must trim the oldest, not grow past 10k.
    monkeypatch.setattr(
        posthog, "capture", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    posthog_client.configure(api_key="test-key")
    events.emit_drawing_uploaded("user-cap", "drawing-cap")

    assert fake_redis.llen(DEAD_LETTER_KEY) == 10_000
    tail = json.loads(fake_redis.lindex(DEAD_LETTER_KEY, -1))
    assert tail["properties"]["drawing_id"] == "drawing-cap"  # newest retained


# ---------------------------------------------------------------------------
# Retry / requeue  (AC: tech)
# ---------------------------------------------------------------------------
def test_retry_dead_letter_drains_queue_and_re_emits(monkeypatch, fake_redis):
    for i in range(3):
        fake_redis.rpush(
            DEAD_LETTER_KEY,
            json.dumps(
                {
                    "event": "drawing_uploaded",
                    "distinct_id": f"u{i}",
                    "properties": {"timestamp": "t", "user_id": f"u{i}", "drawing_id": f"d{i}"},
                }
            ),
        )

    calls: list[dict] = []
    monkeypatch.setattr(posthog, "capture", lambda **k: calls.append(k))
    posthog_client.configure(api_key="test-key")

    resent = dead_letter.retry_dead_letter()

    assert resent == 3
    assert fake_redis.llen(DEAD_LETTER_KEY) == 0
    assert len(calls) == 3
    assert {c["distinct_id"] for c in calls} == {"u0", "u1", "u2"}


def test_retry_dead_letter_requeues_failed_resends(monkeypatch, fake_redis):
    fake_redis.rpush(
        DEAD_LETTER_KEY,
        json.dumps({"event": "drawing_uploaded", "distinct_id": "u", "properties": {}}),
    )
    monkeypatch.setattr(
        posthog, "capture", lambda **k: (_ for _ in ()).throw(RuntimeError("still down"))
    )
    posthog_client.configure(api_key="test-key")

    resent = dead_letter.retry_dead_letter()

    assert resent == 0
    assert fake_redis.llen(DEAD_LETTER_KEY) == 1  # pushed back, processed once


# ---------------------------------------------------------------------------
# Server-side timestamp + no caller timestamp / no DB lookup  (AC: tech / §1.4)
# ---------------------------------------------------------------------------
def test_timestamp_is_iso8601_utc_and_not_caller_supplied(captured):
    events.emit_drawing_uploaded("u", "d")
    ts = _props(captured)["timestamp"]
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)  # UTC

    # No emitter accepts a caller-supplied timestamp.
    for fn in _all_emitters():
        assert "timestamp" not in inspect.signature(fn).parameters


def test_every_emitter_requires_caller_supplied_user_id(captured):
    # §1.4 rule 5: user_id is always the first parameter; never resolved via DB.
    for fn in _all_emitters():
        params = list(inspect.signature(fn).parameters)
        assert params and params[0] == "user_id", f"{fn.__name__} must take user_id first"
