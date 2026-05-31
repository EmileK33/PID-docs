"""S2-E — Stripe webhook integration tests.

Run with:  poetry run pytest tests/integration/test_stripe_webhook.py -v

Self-contained at the infrastructure level (project memory: the ``session-tests``
gate boots no Docker services, and the integration smoke suite forbids importing
``app.*`` during collection):

* DB is an in-memory SQLite engine with only the S2-E tables + seeded tiers and a
  ``JSONB → JSON`` compile shim — no live Postgres / S1-A migration needed.
* Redis cache writes, the analytics emitters and the Celery dispatcher are
  mocked, so neither Redis nor the S2-M notification package is required.
* All ``app.*`` imports are deferred into a fixture so a module-level import does
  not pull ``app`` into ``sys.modules`` during collection (smoke-suite contract).

Webhook payloads are signed with the test ``STRIPE_WEBHOOK_SECRET`` using
Stripe's header format (``t=<ts>,v1=<hmac_sha256("{ts}.{payload}")>``).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# --- make `app` importable + §1.12 env BEFORE any app import ---------------
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(BACKEND), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

TEST_WEBHOOK_SECRET = "whsec_test_secret"
PRO_PRICE_ID = "price_pro_test"
TEAM_PRICE_ID = "price_team_test"
CUSTOMER = "cus_test_xxx"
STRIPE_SUB = "sub_test_pro_001"

# Only the §1.12 vars the shared conftest omits (ML_MODEL_S3_KEY,
# ODA_CONVERTER_PATH) plus the S2-E Stripe price IDs. We do NOT touch
# DATABASE_URL/REDIS_URL etc.: the integration harness owns those and sibling
# tests (test_db_schema) connect to the real Postgres via DATABASE_URL — this
# module gets its own isolated in-memory SQLite engine in the fixture and
# overrides get_db, so the app's configured engine is never exercised here.
_REQUIRED_ENV = {
    "STRIPE_PRO_PRICE_ID": PRO_PRICE_ID,
    "STRIPE_TEAM_PRICE_ID": TEAM_PRICE_ID,
    "ML_MODEL_S3_KEY": "models/pid/v1.onnx",
    "ODA_CONVERTER_PATH": "/opt/oda/ODAFileConverter",
}
for _k, _v in _REQUIRED_ENV.items():
    os.environ.setdefault(_k, _v)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # noqa: ANN001
    return "JSON"


def _sign(event: dict, secret: str) -> tuple[bytes, str]:
    payload_str = json.dumps(event)
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload_str}".encode(), hashlib.sha256).hexdigest()
    return payload_str.encode(), f"t={ts},v1={sig}"


@pytest.fixture()
def harness():
    """Deferred app import + isolated SQLite app + mocked external boundaries."""
    from fastapi.testclient import TestClient

    from app.api.routers import stripe_webhook as webhook_module
    from app.config import settings
    from app.db.models import StripeEvent, Subscription, Team, Tier, User
    from app.db.session import get_db
    from app.main import app

    # Sign with the secret the app actually verifies against: the integration
    # conftest seeds STRIPE_WEBHOOK_SECRET via setdefault before this module
    # loads, so a hardcoded test secret would not match.
    secret = settings.STRIPE_WEBHOOK_SECRET

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    tables = [Team.__table__, Tier.__table__, User.__table__, Subscription.__table__, StripeEvent.__table__]
    Tier.metadata.create_all(engine, tables=tables)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = Session()
    db.add_all(
        [
            Tier(id="free", name="Free", monthly_drawing_limit=3, team_features=False, api_access=False),
            Tier(id="pro", name="Pro", monthly_drawing_limit=None, team_features=False, api_access=False),
            Tier(id="team", name="Team", monthly_drawing_limit=None, team_features=True, api_access=False),
        ]
    )
    db.commit()

    mocks = SimpleNamespace(
        invalidate=AsyncMock(), set_flags=AsyncMock(),
        upgraded=MagicMock(), downgraded=MagicMock(), celery=MagicMock(),
    )
    webhook_module.invalidate_subscription_flags = mocks.invalidate
    webhook_module.set_subscription_flags = mocks.set_flags
    webhook_module.emit_subscription_upgraded = mocks.upgraded
    webhook_module.emit_subscription_downgraded = mocks.downgraded
    webhook_module.celery_app = mocks.celery

    def _override_db():
        yield db  # shared session; the fixture owns its lifecycle

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app, raise_server_exceptions=False)

    def post(event: dict):
        body, header = _sign(event, secret)
        return client.post(
            "/webhooks/stripe", content=body,
            headers={"Stripe-Signature": header, "Content-Type": "application/json"},
        )

    h = SimpleNamespace(
        db=db, client=client, post=post, mocks=mocks,
        models=SimpleNamespace(User=User, Subscription=Subscription, StripeEvent=StripeEvent),
    )
    try:
        yield h
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def _seed_user_sub(h, tier="pro", state="Active", **kw):
    User, Subscription = h.models.User, h.models.Subscription
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4().hex}@e.com", display_name="T", role="user", email_verified=True)
    h.db.add(user)
    h.db.flush()
    sub = Subscription(id=uuid.uuid4(), user_id=user.id, tier_id=tier, billing_state=state, **kw)
    h.db.add(sub)
    h.db.commit()
    return user, sub


def _checkout_completed(user_id, tier="pro", event_id="evt_co_1"):
    return {
        "id": event_id, "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_abc123", "client_reference_id": user_id, "customer": CUSTOMER,
            "subscription": STRIPE_SUB, "payment_status": "paid",
            "metadata": {"user_id": user_id, "tier_id": tier},
        }},
    }


def test_checkout_completed_upgrades_and_caches(harness):
    user, sub = _seed_user_sub(harness, tier="free")
    resp = harness.post(_checkout_completed(str(user.id)))
    assert resp.status_code == 200, resp.text
    harness.db.expire_all()
    refreshed = harness.db.get(harness.models.Subscription, sub.id)
    assert refreshed.tier_id == "pro"
    assert refreshed.billing_state == "Active"
    assert refreshed.stripe_customer_id == CUSTOMER
    harness.mocks.invalidate.assert_awaited_once_with(str(user.id))
    harness.mocks.set_flags.assert_awaited_once()


def test_invalid_signature_returns_400(harness):
    body = json.dumps(_checkout_completed("00000000-0000-0000-0000-000000000000")).encode()
    resp = harness.client.post(
        "/webhooks/stripe", content=body,
        headers={"Stripe-Signature": "t=1,v1=bad", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400


def test_duplicate_event_is_idempotent_200(harness):
    user, sub = _seed_user_sub(harness, tier="free")
    event = _checkout_completed(str(user.id), event_id="evt_dup_int_1")
    first = harness.post(event)
    second = harness.post(event)
    assert first.status_code == 200
    assert second.status_code == 200
    # Second delivery must not re-run side effects.
    assert harness.mocks.set_flags.await_count == 1


def test_invoice_payment_failed_enters_grace_and_enqueues(harness):
    user, sub = _seed_user_sub(harness, tier="pro", state="Active", stripe_customer_id=CUSTOMER)
    event = {
        "id": "evt_inv_fail_int_1", "type": "invoice.payment_failed",
        "data": {"object": {"id": "in_1", "customer": CUSTOMER, "subscription": STRIPE_SUB}},
    }
    resp = harness.post(event)
    assert resp.status_code == 200, resp.text
    harness.db.expire_all()
    refreshed = harness.db.get(harness.models.Subscription, sub.id)
    assert refreshed.billing_state == "Grace"
    assert refreshed.grace_period_start is not None
    names = [c.args[0] for c in harness.mocks.celery.send_task.call_args_list]
    assert "notification.send_grace_period_started_email" in names
    assert "notification.send_grace_period_reminder_email" in names


def test_subscription_deleted_cancels_to_free(harness):
    user, sub = _seed_user_sub(harness, tier="pro", state="Active", stripe_customer_id=CUSTOMER)
    event = {
        "id": "evt_del_int_1", "type": "customer.subscription.deleted",
        "data": {"object": {"id": STRIPE_SUB, "customer": CUSTOMER}},
    }
    resp = harness.post(event)
    assert resp.status_code == 200, resp.text
    harness.db.expire_all()
    refreshed = harness.db.get(harness.models.Subscription, sub.id)
    assert refreshed.billing_state == "Canceled"
    assert refreshed.tier_id == "free"


def test_unrecognized_event_returns_200(harness):
    event = {"id": "evt_unk_int_1", "type": "payment_intent.created", "data": {"object": {}}}
    resp = harness.post(event)
    assert resp.status_code == 200
    assert harness.db.get(harness.models.StripeEvent, "evt_unk_int_1") is not None
    harness.mocks.celery.send_task.assert_not_called()
