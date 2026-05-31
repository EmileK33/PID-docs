"""S2-E — Subscription API integration tests (GET /subscription, checkout).

Run with:  poetry run pytest tests/integration/test_subscription.py -v

Self-contained at the infrastructure level and defers every ``app.*`` import into
a fixture (see ``test_stripe_webhook.py`` for the rationale): in-memory SQLite,
mocked Stripe SDK, no live Postgres/Redis required.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(BACKEND), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PRO_PRICE_ID = "price_pro_test"
TEAM_PRICE_ID = "price_team_test"
CUSTOMER = "cus_test_xxx"

# Only the §1.12 vars the shared conftest omits, plus the S2-E Stripe price IDs.
# DATABASE_URL/REDIS_URL belong to the harness; this module uses an isolated
# in-memory SQLite engine via the fixture and overrides get_db.
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


@pytest.fixture()
def harness():
    from fastapi.testclient import TestClient

    from app.auth.dependencies import CurrentUser, get_current_user
    from app.db.models import StripeEvent, Subscription, Team, Tier, User
    from app.db.session import get_db
    from app.main import app

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

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app, raise_server_exceptions=False)

    def login(user):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=user.id, email=user.email, role=user.role, team_id=user.team_id
        )

    h = SimpleNamespace(
        db=db, client=client, login=login,
        models=SimpleNamespace(User=User, Subscription=Subscription),
    )
    try:
        yield h
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        db.close()
        engine.dispose()


def _seed(h, tier="free", state="Active", **kw):
    User, Subscription = h.models.User, h.models.Subscription
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4().hex}@e.com", display_name="T", role="user", email_verified=True)
    h.db.add(user)
    h.db.flush()
    sub = Subscription(id=uuid.uuid4(), user_id=user.id, tier_id=tier, billing_state=state, **kw)
    h.db.add(sub)
    h.db.commit()
    return user, sub


@pytest.fixture()
def mock_checkout(monkeypatch):
    import stripe

    created = MagicMock(return_value={
        "id": "cs_test_abc123",
        "url": "https://checkout.stripe.com/pay/cs_test_abc123",
        "customer": CUSTOMER, "payment_status": "unpaid",
    })
    monkeypatch.setattr(stripe.checkout.Session, "create", created)
    return created


def test_get_subscription_returns_current_state(harness):
    user, sub = _seed(
        harness, tier="pro", state="Active",
        stripe_customer_id=CUSTOMER,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    harness.login(user)
    resp = harness.client.get("/subscription")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tier_id"] == "pro"
    assert body["billing_state"] == "Active"
    assert body["current_period_end"] is not None
    assert body["id"] == str(sub.id)


def test_get_subscription_unauthenticated_returns_401(harness):
    resp = harness.client.get("/subscription")
    assert resp.status_code == 401


def test_checkout_returns_url_for_pro(harness, mock_checkout):
    user, _ = _seed(harness, tier="free")
    harness.login(user)
    resp = harness.client.post("/subscription/checkout", json={"tier_id": "pro"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["checkout_url"].startswith("https://checkout.stripe.com/")
    assert mock_checkout.call_args.kwargs["line_items"][0]["price"] == PRO_PRICE_ID


def test_checkout_does_not_mutate_subscription(harness, mock_checkout):
    user, sub = _seed(harness, tier="free")
    harness.login(user)
    resp = harness.client.post("/subscription/checkout", json={"tier_id": "team"})
    assert resp.status_code == 200
    harness.db.expire_all()
    refreshed = harness.db.get(harness.models.Subscription, sub.id)
    assert refreshed.tier_id == "free"
    assert refreshed.stripe_subscription_id is None


def test_checkout_unauthenticated_returns_401(harness, mock_checkout):
    resp = harness.client.post("/subscription/checkout", json={"tier_id": "pro"})
    assert resp.status_code == 401
