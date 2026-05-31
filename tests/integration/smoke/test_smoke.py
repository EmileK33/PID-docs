"""Infrastructure smoke tests for the integration harness.

These verify ONLY that the three fixture services respond and that the harness
env contract is satisfied. They intentionally import NO application code from
backend/app, frontend/src, or marketing — S0-B must stay green regardless of
whether S0-A (app scaffold) has merged.
"""

import json
import os
import sys
from pathlib import Path

from sqlalchemy import text

# repo root: tests/integration/smoke/test_smoke.py -> parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]

# §1.12 "Refuse to start" variables the harness must provide.
REQUIRED_ENV_VARS = (
    "DATABASE_URL",
    "REDIS_URL",
    "S3_BUCKET_NAME",
    "S3_REGION",
    "HMAC_SERVER_SECRET",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "JWT_RS256_PUBLIC_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "SENDGRID_API_KEY",
    "ENVIRONMENT",
)


def test_postgres_reachable(db_session):
    """Postgres answers a trivial query."""
    assert db_session.execute(text("SELECT 1")).scalar_one() == 1


def test_pgcrypto_extension_available(db_session):
    """pgcrypto is installed: gen_random_uuid() returns a valid UUID."""
    value = db_session.execute(text("SELECT gen_random_uuid()")).scalar_one()
    assert value is not None
    assert len(str(value)) == 36


def test_redis_reachable(redis_client):
    """Redis answers PING with PONG."""
    assert redis_client.ping() is True


def test_minio_reachable(s3_client):
    """MinIO is up and the auto-created test bucket exists."""
    bucket = os.environ["S3_BUCKET_NAME"]
    names = [b["Name"] for b in s3_client.list_buckets().get("Buckets", [])]
    assert bucket in names


def test_required_env_vars_present():
    """Every §1.12 'Refuse to start' var has a value and ENVIRONMENT is development."""
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    assert not missing, f"missing §1.12 env vars: {missing}"
    assert os.environ["ENVIRONMENT"] == "development"


def test_smoke_does_not_import_app():
    """No application module leaked into sys.modules via the harness."""
    leaked = [
        m
        for m in sys.modules
        if m == "app"
        or m.startswith(("app.", "backend.app", "frontend", "marketing"))
    ]
    assert not leaked, f"application modules imported into smoke test: {leaked}"


def test_root_package_json_has_test_integration_script():
    """Root package.json declares the project-level integration command."""
    pkg = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "test:integration" in pkg.get("scripts", {})
