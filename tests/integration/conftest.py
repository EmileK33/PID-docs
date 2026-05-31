"""Integration-harness fixtures shared by every Phase 1+ session.

Exposes session-scoped ``db_engine`` / ``redis_client`` / ``s3_client`` and a
function-scoped transactional ``db_session``. Also installs test-safe values for
every §1.12 "Refuse to start" environment variable so downstream application
code can import and boot under pytest.
"""

import os

import pytest

# §1.12 environment contract. Every variable whose missing-value behavior is
# "Refuse to start" gets a test-safe value. Set at import time so module-level
# `import app...` during collection sees them, and re-applied via the autouse
# fixture below (per the brief's acceptance criteria).
_TEST_ENV_DEFAULTS = {
    # Backing services — point at the fixture compose (docker-compose.fixtures.yml).
    "DATABASE_URL": "postgresql://pidtest:pidtest@localhost:55432/pidtest",
    "REDIS_URL": "redis://localhost:56379/0",
    "S3_BUCKET_NAME": "pidtest-bucket",
    "S3_REGION": "us-east-1",
    # MinIO connection details (not in §1.12 but needed to reach the fixture).
    "S3_ENDPOINT_URL": "http://localhost:59000",
    "AWS_ACCESS_KEY_ID": "minioadmin",
    "AWS_SECRET_ACCESS_KEY": "minioadmin",
    # Secrets / third-party — fake but well-formed test values.
    "HMAC_SERVER_SECRET": "test-secret-do-not-use",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key-do-not-use",
    "JWT_RS256_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\nTESTKEYDONOTUSE\n-----END PUBLIC KEY-----",
    "STRIPE_SECRET_KEY": "sk_test_FAKE",
    "STRIPE_WEBHOOK_SECRET": "whsec_test_FAKE",
    "SENDGRID_API_KEY": "SG.test_FAKE",
    # Never `production` under test — production default enables strict checks.
    "ENVIRONMENT": "development",
}

# §1.12 "Refuse to start" variables (the subset the spec marks load-bearing).
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


def _apply_test_env() -> None:
    # setdefault so CI / a developer can override any value from the real env.
    for key, value in _TEST_ENV_DEFAULTS.items():
        os.environ.setdefault(key, value)


_apply_test_env()

# tests/integration is on sys.path (pytest prepend import mode), so the
# fixtures package is importable. Imported after env setup; no app code touched.
from fixtures.db import make_engine, make_session_factory  # noqa: E402
from fixtures.redis import make_redis_client  # noqa: E402
from fixtures.s3 import make_s3_client  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_environment():
    """Guarantee the §1.12 env contract for the whole test session."""
    _apply_test_env()
    yield


@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped SQLAlchemy Engine bound to the Postgres fixture."""
    engine = make_engine(os.environ["DATABASE_URL"])
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Function-scoped Session wrapped in a transaction that is rolled back.

    Each test runs inside its own transaction so tests never pollute one another.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = make_session_factory(bind=connection)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="session")
def redis_client():
    """Session-scoped Redis client bound to the Redis fixture."""
    client = make_redis_client(os.environ["REDIS_URL"])
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def s3_client():
    """Session-scoped boto3 S3 client bound to the MinIO fixture."""
    return make_s3_client(
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        region_name=os.environ["S3_REGION"],
        access_key=os.environ["AWS_ACCESS_KEY_ID"],
        secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )
