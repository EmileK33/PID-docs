"""S2-E — Subscription + Stripe Webhook acceptance tests.

Run with:  pytest tests/sessions/test_s2_e.py -v

Self-contained by design (see project memory): the authoritative ``session-tests``
gate runs this with BARE pytest against ``backend/requirements.txt`` and does NOT
boot Postgres/Redis/MinIO. So this module:

* sets ``DATABASE_URL`` to an in-memory SQLite URL *before* importing ``app`` (so
  ``app.db.session`` never resolves the psycopg2 dialect / opens Postgres),
* builds an isolated SQLite engine per test, creating only the tables S2-E needs
  and seeding the ``tier`` rows (S1-A's ``seed_tiers``), with a ``JSONB → JSON``
  compile shim so the Postgres-typed ``stripe_event.payload`` column compiles,
* overrides the ``get_db`` / ``get_current_user`` FastAPI dependencies,
* mocks every external boundary: Stripe SDK, Redis cache writes, the analytics
  emitters, and the Celery dispatcher (notification tasks are owned by S2-M and
  need not exist).

Webhook payloads are signed manually with the test ``STRIPE_WEBHOOK_SECRET``
using Stripe's documented header format (``t=<ts>,v1=<hmac_sha256>``); the
``stripe.WebhookSignature.generate_header`` helper referenced by the brief does
not exist in the pinned ``stripe`` (10.x), and the manual format is what
``stripe.Webhook.construct_event`` verifies against.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: sys.path + env BEFORE importing app (config.py exits if vars miss).
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(BACKEND), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

TEST_WEBHOOK_SECRET = "whsec_test_secret"
PRO_PRICE_ID = "price_pro_test"
TEAM_PRICE_ID = "price_team_test"

_REQUIRED_ENV = {
    # SQLite (NOT postgresql://) so app.db.session builds a psycopg2-free engine.
    "DATABASE_URL": "sqlite://",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_BUCKET_NAME": "pid-test-bucket",
    "S3_REGION": "us-east-1",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
    "JWT_RS256_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\nMIIB\n-----END PUBLIC KEY-----",
    "STRIPE_SECRET_KEY": "sk_test_dummy",
    "STRIPE_WEBHOOK_SECRET": TEST_WEBHOOK_SECRET,
    "STRIPE_PRO_PRICE_ID": PRO_PRICE_ID,
    "STRIPE_TEAM_PRICE_ID": TEAM_PRICE_ID,
    "SENDGRID_API_KEY": "SG.dummy",
    "HMAC_SERVER_SECRET": "high-entropy-secret",
    "ML_MODEL_S3_KEY": "models/pid/v1.onnx",
    "ODA_CONVERTER_PATH": "/opt/oda/ODAFileConverter",
}
for _k, _v in _REQUIRED_ENV.items():
    os.environ.setdefault(_k, _v)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # noqa: ANN001
    """Render the Postgres ``JSONB`` column as SQLite ``JSON`` so create_all works."""
    return "JSON"


from app.api.routers import stripe_webhook as webhook_module  # noqa: E402
from app.auth.dependencies import CurrentUser, get_current_user  # noqa: E402
from app.db.models import StripeEvent, Subscription, Team, Tier, User  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

_TABLES = [Team.__table__, Tier.__table__, User.__table__, Subscription.__table__, StripeEvent.__table__]


# ---------------------------------------------------------------------------
# Webhook signing + canonical payloads
# ---------------------------------------------------------------------------
def _sign(event: dict) -> tuple[bytes, str]:
    payload_str = json.dumps(event)
    payload_bytes = payload_str.encode("utf-8")
    ts = int(time.time())
    signed = f"{ts}.{payload_str}".encode("utf-8")
    sig = hmac.new(TEST_WEBHOOK_SECRET.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return payload_bytes, f"t={ts},v1={sig}"


def _post_webhook(client, event: dict):
    body, header = _sign(event)
    return client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )


CUSTOMER = "cus_test_xxx"
STRIPE_SUB = "sub_test_pro_001"
PERIOD_END_EPOCH = 1767225600


def _checkout_completed(user_id: str, tier_id: str = "pro", event_id: str = "evt_checkout_completed_001") -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_abc123",
                "client_reference_id": user_id,
                "customer": CUSTOMER,
                "subscription": STRIPE_SUB,
                "payment_status": "paid",
                "metadata": {"user_id": user_id, "tier_id": tier_id},
            }
        },
    }


def _sub_updated_upgrade(event_id: str = "evt_sub_updated_upgrade_001") -> dict:
    return {
        "id": event_id,
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": STRIPE_SUB,
                "customer": CUSTOMER,
                "status": "active",
                "current_period_end": PERIOD_END_EPOCH,
                "cancel_at_period_end": False,
                "items": {"data": [{"price": {"id": PRO_PRICE_ID, "product": "prod_pro"}}]},
            },
            "previous_attributes": {
                "items": {"data": [{"price": {"id": "price_free", "product": "prod_free"}}]}
            },
        },
    }


def _sub_updated_downgrade(event_id: str = "evt_sub_updated_downgrade_001") -> dict:
    return {
        "id": event_id,
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": STRIPE_SUB,
                "customer": CUSTOMER,
                "status": "active",
                "current_period_end": PERIOD_END_EPOCH,
                "cancel_at_period_end": True,
                "items": {"data": [{"price": {"id": PRO_PRICE_ID, "product": "prod_pro"}}]},
            },
            "previous_attributes": {"cancel_at_period_end": False},
        },
    }


def _invoice_failed(event_id: str = "evt_invoice_failed_001") -> dict:
    return {
        "id": event_id,
        "type": "invoice.payment_failed",
        "data": {"object": {"id": "in_test_failed_001", "customer": CUSTOMER, "subscription": STRIPE_SUB}},
    }


def _invoice_succeeded(event_id: str = "evt_invoice_succeeded_001") -> dict:
    return {
        "id": event_id,
        "type": "invoice.payment_succeeded",
        "data": {"object": {"id": "in_test_ok_001", "customer": CUSTOMER, "subscription": STRIPE_SUB}},
    }


def _sub_deleted(event_id: str = "evt_sub_deleted_001") -> dict:
    return {
        "id": event_id,
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": STRIPE_SUB, "customer": CUSTOMER}},
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def db():
    """Fresh in-memory SQLite DB per test, with S2-E tables + seeded tiers."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Tier.metadata.create_all(engine, tables=_TABLES)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    session.add_all(
        [
            Tier(id="free", name="Free", monthly_drawing_limit=3, team_features=False, api_access=False),
            Tier(id="pro", name="Pro", monthly_drawing_limit=None, team_features=False, api_access=False),
            Tier(id="team", name="Team", monthly_drawing_limit=None, team_features=True, api_access=False),
        ]
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db):
    """TestClient with get_db wired to the test session. Auth is opt-in per test
    via :func:`authenticate_as` (left unauthenticated by default → real 401)."""
    from fastapi.testclient import TestClient

    def _override_db():
        yield db  # shared session; not closed here (the db fixture owns it)

    app.dependency_overrides[get_db] = _override_db
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def authenticate_as(user: User) -> None:
    """Make subsequent requests authenticate as ``user`` (overrides get_current_user)."""
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=user.id, email=user.email, role=user.role, team_id=user.team_id
    )


@pytest.fixture()
def webhook_mocks(monkeypatch):
    """Patch every external boundary the webhook touches and return the mocks."""
    invalidate = AsyncMock()
    set_flags = AsyncMock()
    upgraded = MagicMock()
    downgraded = MagicMock()
    celery = MagicMock()
    monkeypatch.setattr(webhook_module, "invalidate_subscription_flags", invalidate)
    monkeypatch.setattr(webhook_module, "set_subscription_flags", set_flags)
    monkeypatch.setattr(webhook_module, "emit_subscription_upgraded", upgraded)
    monkeypatch.setattr(webhook_module, "emit_subscription_downgraded", downgraded)
    monkeypatch.setattr(webhook_module, "celery_app", celery)
    return MagicMock(
        invalidate=invalidate,
        set_flags=set_flags,
        upgraded=upgraded,
        downgraded=downgraded,
        celery=celery,
    )


# --- seed helpers -----------------------------------------------------------
def _make_user(db, email="test@example.com") -> User:
    user = User(id=uuid.uuid4(), email=email, display_name="Test", role="user", email_verified=True)
    db.add(user)
    db.commit()
    return user


def _make_subscription(db, user, tier_id="free", billing_state="Active", **kw) -> Subscription:
    sub = Subscription(
        id=uuid.uuid4(), user_id=user.id, tier_id=tier_id, billing_state=billing_state, **kw
    )
    db.add(sub)
    db.commit()
    return sub


@pytest.fixture()
def free_user_with_subscription(db):
    user = _make_user(db)
    sub = _make_subscription(db, user, tier_id="free", billing_state="Active")
    return user, sub


@pytest.fixture()
def pro_user_with_stripe_subscription(db):
    user = _make_user(db, email="pro@example.com")
    sub = _make_subscription(
        db,
        user,
        tier_id="pro",
        billing_state="Active",
        stripe_customer_id=CUSTOMER,
        stripe_subscription_id=STRIPE_SUB,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    return user, sub


@pytest.fixture()
def mock_stripe_checkout(monkeypatch):
    created = MagicMock(
        return_value={
            "id": "cs_test_abc123",
            "url": "https://checkout.stripe.com/pay/cs_test_abc123",
            "client_reference_id": "x",
            "customer": CUSTOMER,
            "payment_status": "unpaid",
        }
    )
    import stripe

    monkeypatch.setattr(stripe.checkout.Session, "create", created)
    return created


# ===========================================================================
# US-019 — Stripe Checkout upgrade
# ===========================================================================
def test_checkout_creates_session_pro_tier(client, free_user_with_subscription, mock_stripe_checkout):
    user, _ = free_user_with_subscription
    authenticate_as(user)
    resp = client.post("/subscription/checkout", json={"tier_id": "pro"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkout_url"].startswith("https://checkout.stripe.com/")
    assert body["session_id"] == "cs_test_abc123"
    # Stripe was asked for the configured Pro price, tagged with the user UUID.
    kwargs = mock_stripe_checkout.call_args.kwargs
    assert kwargs["client_reference_id"] == str(user.id)
    assert kwargs["line_items"][0]["price"] == PRO_PRICE_ID


def test_checkout_creates_session_team_tier(client, free_user_with_subscription, mock_stripe_checkout):
    user, _ = free_user_with_subscription
    authenticate_as(user)
    resp = client.post("/subscription/checkout", json={"tier_id": "team"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["checkout_url"].startswith("https://checkout.stripe.com/")
    assert mock_stripe_checkout.call_args.kwargs["line_items"][0]["price"] == TEAM_PRICE_ID


def test_checkout_does_not_mutate_subscription_table(
    client, free_user_with_subscription, mock_stripe_checkout, db
):
    user, sub = free_user_with_subscription
    authenticate_as(user)
    resp = client.post("/subscription/checkout", json={"tier_id": "pro"})
    assert resp.status_code == 200
    db.expire_all()
    refreshed = db.get(Subscription, sub.id)
    assert refreshed.tier_id == "free"
    assert refreshed.billing_state == "Active"
    assert refreshed.stripe_subscription_id is None


def test_checkout_returns_401_unauthenticated(client, mock_stripe_checkout):
    # No authenticate_as() → real get_current_user runs → 401.
    resp = client.post("/subscription/checkout", json={"tier_id": "pro"})
    assert resp.status_code == 401


def test_get_subscription_returns_current_state(client, pro_user_with_stripe_subscription):
    user, sub = pro_user_with_stripe_subscription
    authenticate_as(user)
    resp = client.get("/subscription")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tier_id"] == "pro"
    assert body["billing_state"] == "Active"
    assert body["current_period_end"] is not None
    assert body["grace_period_start"] is None
    assert body["id"] == str(sub.id)


def test_get_subscription_returns_401_unauthenticated(client):
    resp = client.get("/subscription")
    assert resp.status_code == 401


def test_checkout_completed_webhook_updates_tier_and_billing_state(
    client, free_user_with_subscription, webhook_mocks, db
):
    user, sub = free_user_with_subscription
    resp = _post_webhook(client, _checkout_completed(str(user.id), tier_id="pro"))
    assert resp.status_code == 200, resp.text
    db.expire_all()
    refreshed = db.get(Subscription, sub.id)
    assert refreshed.tier_id == "pro"
    assert refreshed.billing_state == "Active"


def test_checkout_completed_webhook_stores_stripe_ids(
    client, free_user_with_subscription, webhook_mocks, db
):
    user, sub = free_user_with_subscription
    resp = _post_webhook(client, _checkout_completed(str(user.id)))
    assert resp.status_code == 200
    db.expire_all()
    refreshed = db.get(Subscription, sub.id)
    assert refreshed.stripe_customer_id == CUSTOMER
    assert refreshed.stripe_subscription_id == STRIPE_SUB


def test_checkout_completed_webhook_invalidates_redis_cache(
    client, free_user_with_subscription, webhook_mocks
):
    user, _ = free_user_with_subscription
    resp = _post_webhook(client, _checkout_completed(str(user.id)))
    assert resp.status_code == 200
    webhook_mocks.invalidate.assert_awaited_once_with(str(user.id))
    webhook_mocks.set_flags.assert_awaited_once()
    flags = webhook_mocks.set_flags.await_args.args[1]
    assert flags["tier_id"] == "pro"


def test_subscription_updated_webhook_fires_upgraded_analytics(
    client, db, webhook_mocks
):
    user = _make_user(db, email="upgrade@example.com")
    sub = _make_subscription(db, user, tier_id="free", billing_state="Active", stripe_customer_id=CUSTOMER)

    # Prove the tier change is committed BEFORE analytics fires (§1.10 / AC-10).
    observed = {}

    def _record(uid, sid, prev, new):
        with sessionmaker(bind=db.get_bind())() as fresh:
            observed["tier_at_emit"] = fresh.get(Subscription, sub.id).tier_id

    webhook_mocks.upgraded.side_effect = _record

    resp = _post_webhook(client, _sub_updated_upgrade())
    assert resp.status_code == 200, resp.text
    webhook_mocks.upgraded.assert_called_once()
    args = webhook_mocks.upgraded.call_args.args
    assert args[0] == str(user.id)
    assert args[1] == str(sub.id)
    assert args[2] == "free" and args[3] == "pro"
    assert observed["tier_at_emit"] == "pro"  # committed before emit


def test_checkout_endpoint_does_not_fire_upgraded_analytics(
    client, free_user_with_subscription, mock_stripe_checkout, monkeypatch
):
    user, _ = free_user_with_subscription
    authenticate_as(user)
    from app.api.routers import subscription as sub_module

    # subscription router must not import/fire analytics at all; assert the
    # webhook-module emitter is never invoked from the checkout path.
    fired = MagicMock()
    monkeypatch.setattr(webhook_module, "emit_subscription_upgraded", fired)
    assert not hasattr(sub_module, "emit_subscription_upgraded")
    resp = client.post("/subscription/checkout", json={"tier_id": "pro"})
    assert resp.status_code == 200
    fired.assert_not_called()


# ===========================================================================
# US-020 — Grace period, cancellation, idempotency
# ===========================================================================
def test_invoice_payment_failed_enters_grace_period(
    client, pro_user_with_stripe_subscription, webhook_mocks, db
):
    user, sub = pro_user_with_stripe_subscription
    resp = _post_webhook(client, _invoice_failed())
    assert resp.status_code == 200, resp.text
    db.expire_all()
    assert db.get(Subscription, sub.id).billing_state == "Grace"


def test_invoice_payment_failed_sets_grace_period_start(
    client, pro_user_with_stripe_subscription, webhook_mocks, db
):
    user, sub = pro_user_with_stripe_subscription
    before = datetime.now(timezone.utc)
    resp = _post_webhook(client, _invoice_failed())
    assert resp.status_code == 200
    db.expire_all()
    gps = db.get(Subscription, sub.id).grace_period_start
    assert gps is not None
    if gps.tzinfo is None:
        gps = gps.replace(tzinfo=timezone.utc)
    assert gps >= before - timedelta(seconds=5)


def test_invoice_payment_failed_does_not_reset_grace_period_start_if_already_in_grace(
    client, db, webhook_mocks
):
    user = _make_user(db, email="grace@example.com")
    original = datetime(2026, 1, 1, tzinfo=timezone.utc)
    sub = _make_subscription(
        db, user, tier_id="pro", billing_state="Grace",
        stripe_customer_id=CUSTOMER, grace_period_start=original,
    )
    resp = _post_webhook(client, _invoice_failed(event_id="evt_failed_again_001"))
    assert resp.status_code == 200
    db.expire_all()
    gps = db.get(Subscription, sub.id).grace_period_start
    if gps.tzinfo is None:
        gps = gps.replace(tzinfo=timezone.utc)
    assert gps == original
    # No new grace emails enqueued for a repeat failure.
    webhook_mocks.celery.send_task.assert_not_called()


def test_invoice_payment_failed_enqueues_day1_notification(
    client, pro_user_with_stripe_subscription, webhook_mocks
):
    user, _ = pro_user_with_stripe_subscription
    resp = _post_webhook(client, _invoice_failed())
    assert resp.status_code == 200
    names = [c.args[0] for c in webhook_mocks.celery.send_task.call_args_list]
    assert "notification.send_grace_period_started_email" in names
    day1 = next(
        c for c in webhook_mocks.celery.send_task.call_args_list
        if c.args[0] == "notification.send_grace_period_started_email"
    )
    assert day1.kwargs["args"][0] == str(user.id)
    assert "eta" not in day1.kwargs  # day-1 is immediate


def test_invoice_payment_failed_enqueues_day6_reminder_with_eta(
    client, pro_user_with_stripe_subscription, webhook_mocks, db
):
    user, sub = pro_user_with_stripe_subscription
    resp = _post_webhook(client, _invoice_failed())
    assert resp.status_code == 200
    day6 = next(
        c for c in webhook_mocks.celery.send_task.call_args_list
        if c.args[0] == "notification.send_grace_period_reminder_email"
    )
    db.expire_all()
    gps = db.get(Subscription, sub.id).grace_period_start
    if gps.tzinfo is None:
        gps = gps.replace(tzinfo=timezone.utc)
    eta = day6.kwargs["eta"]
    if eta.tzinfo is None:
        eta = eta.replace(tzinfo=timezone.utc)
    assert abs((eta - (gps + timedelta(days=6))).total_seconds()) < 1
    assert day6.kwargs["args"][0] == str(user.id)


def test_invoice_payment_succeeded_exits_grace_period(client, db, webhook_mocks):
    user = _make_user(db, email="recover@example.com")
    sub = _make_subscription(
        db, user, tier_id="pro", billing_state="Grace",
        stripe_customer_id=CUSTOMER, grace_period_start=datetime.now(timezone.utc),
    )
    resp = _post_webhook(client, _invoice_succeeded())
    assert resp.status_code == 200, resp.text
    db.expire_all()
    refreshed = db.get(Subscription, sub.id)
    assert refreshed.billing_state == "Active"
    assert refreshed.grace_period_start is None


def test_subscription_deleted_cancels_and_downgrades_to_free(
    client, pro_user_with_stripe_subscription, webhook_mocks, db
):
    user, sub = pro_user_with_stripe_subscription
    resp = _post_webhook(client, _sub_deleted())
    assert resp.status_code == 200, resp.text
    db.expire_all()
    refreshed = db.get(Subscription, sub.id)
    assert refreshed.billing_state == "Canceled"
    assert refreshed.tier_id == "free"


def test_subscription_updated_webhook_fires_downgraded_analytics_immediately(
    client, pro_user_with_stripe_subscription, webhook_mocks, db
):
    user, sub = pro_user_with_stripe_subscription
    resp = _post_webhook(client, _sub_updated_downgrade())
    assert resp.status_code == 200, resp.text
    webhook_mocks.downgraded.assert_called_once()
    args = webhook_mocks.downgraded.call_args.args
    assert args[0] == str(user.id) and args[1] == str(sub.id)
    assert args[2] == "pro" and args[3] == "free"
    # Access retained until period end — DB tier unchanged immediately.
    db.expire_all()
    assert db.get(Subscription, sub.id).tier_id == "pro"


def test_webhook_invalid_signature_returns_400(client, free_user_with_subscription):
    body = json.dumps(_checkout_completed(str(free_user_with_subscription[0].id))).encode()
    resp = client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": "t=123,v1=deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400


def test_duplicate_webhook_returns_200_without_state_mutation(
    client, pro_user_with_stripe_subscription, webhook_mocks, db
):
    user, sub = pro_user_with_stripe_subscription
    # Pre-record the event as already processed.
    db.add(
        StripeEvent(
            id="evt_invoice_failed_001",
            event_type="invoice.payment_failed",
            received_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            payload={},
        )
    )
    db.commit()
    resp = _post_webhook(client, _invoice_failed())
    assert resp.status_code == 200
    db.expire_all()
    # State untouched: still Active (no Grace transition for the duplicate).
    assert db.get(Subscription, sub.id).billing_state == "Active"
    webhook_mocks.celery.send_task.assert_not_called()


def test_webhook_returns_200_on_success(client, free_user_with_subscription, webhook_mocks):
    user, _ = free_user_with_subscription
    resp = _post_webhook(client, _checkout_completed(str(user.id)))
    assert resp.status_code == 200


def test_duplicate_webhook_returns_200_not_4xx(
    client, pro_user_with_stripe_subscription, webhook_mocks
):
    user, _ = pro_user_with_stripe_subscription
    event = _invoice_failed(event_id="evt_dup_check_001")
    first = _post_webhook(client, event)
    second = _post_webhook(client, event)
    assert first.status_code == 200
    assert second.status_code == 200


def test_stripe_event_inserted_before_subscription_mutation(
    client, free_user_with_subscription, webhook_mocks, db, monkeypatch
):
    from app.services import subscription_service

    event_id = "evt_ordering_001"
    real = subscription_service.apply_checkout_session_completed
    order = []

    def _spy(session, obj):
        # The stripe_event row must already be inserted+flushed before the
        # subscription is mutated (§1.4 Rule 10 / AC-13).
        assert session.get(StripeEvent, event_id) is not None
        order.append("mutation")
        return real(session, obj)

    monkeypatch.setattr(subscription_service, "apply_checkout_session_completed", _spy)
    user, _ = free_user_with_subscription
    resp = _post_webhook(client, _checkout_completed(str(user.id), event_id=event_id))
    assert resp.status_code == 200, resp.text
    assert order == ["mutation"]
    db.expire_all()
    assert db.get(StripeEvent, event_id) is not None


def test_webhook_invalidates_subscription_cache(
    client, pro_user_with_stripe_subscription, webhook_mocks
):
    user, _ = pro_user_with_stripe_subscription
    resp = _post_webhook(client, _invoice_failed())
    assert resp.status_code == 200
    webhook_mocks.invalidate.assert_awaited_once_with(str(user.id))
    webhook_mocks.set_flags.assert_awaited_once()


# ===========================================================================
# US-020 AC-16 — billing state machine (marked MANUAL; asserted here too)
# ===========================================================================
def test_billing_state_machine_rejects_illegal_transition():
    from app.services.billing_state_machine import BillingStateMachine, InvalidTransitionError

    sub = SimpleNamespace(billing_state="Canceled")
    with pytest.raises(InvalidTransitionError):
        BillingStateMachine.transition(sub, "Grace")  # Canceled -> Grace not allowed
    # Same-state is also not a defined transition and must raise (not silently skip).
    sub.billing_state = "Grace"
    with pytest.raises(InvalidTransitionError):
        BillingStateMachine.transition(sub, "Grace")
    assert sub.billing_state == "Grace"  # unchanged


def test_billing_state_machine_allows_legal_transition():
    from app.services.billing_state_machine import BillingStateMachine

    sub = SimpleNamespace(billing_state="Active")
    BillingStateMachine.transition(sub, "Grace")
    assert sub.billing_state == "Grace"
    BillingStateMachine.transition(sub, "Active")
    assert sub.billing_state == "Active"


def test_unrecognized_event_type_returns_200(client, webhook_mocks, db):
    event = {
        "id": "evt_unrecognized_001",
        "type": "payment_intent.created",
        "data": {"object": {"id": "pi_test_001"}},
    }
    resp = _post_webhook(client, event)
    assert resp.status_code == 200
    # Recorded for idempotency, but no subscription side effects.
    webhook_mocks.celery.send_task.assert_not_called()
    webhook_mocks.upgraded.assert_not_called()
    assert db.get(StripeEvent, "evt_unrecognized_001") is not None
