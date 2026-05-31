"""S0-A scaffold acceptance tests.

Run with:  pytest tests/sessions/s0-a.test.py -v

These tests prove the scaffold is sound *in isolation* — no sibling session
(S0-B's pyproject, S1-* models, etc.) needs to be merged for them to pass.
They therefore self-configure sys.path so the `app` package (rooted at
``backend/``) is importable, and set dummy values for every REQUIRED env var so
``app.config`` does not ``sys.exit(1)`` on import.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
FRONTEND = REPO_ROOT / "frontend"

# Make the `app` package (backend/app) importable from the repo root.
for _p in (str(BACKEND), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Dummy values for every REQUIRED (§1.12 "Refuse to start") variable so that
# importing app.config succeeds inside this process.
REQUIRED_ENV = {
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
}


# ---------------------------------------------------------------------------
# §1.6 Route Manifest — every backend endpoint (P0 + P1)
# ---------------------------------------------------------------------------
# (method, path-with-dummy-ids).  Excludes GET /healthz (the one non-501 route).
ROUTE_MANIFEST: list[tuple[str, str]] = [
    # --- Auth (S2-A) ---
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("POST", "/auth/oauth/google"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),
    ("POST", "/auth/password-reset/request"),
    ("POST", "/auth/password-reset/confirm"),
    # --- Drawings (S2-B) ---
    ("POST", "/drawings/hash-check"),
    ("GET", "/drawings"),
    ("POST", "/drawings"),
    ("GET", "/drawings/abc"),
    ("PATCH", "/drawings/abc"),
    ("DELETE", "/drawings/abc"),
    ("POST", "/drawings/abc/retry"),
    ("GET", "/drawings/abc/status"),
    ("POST", "/drawings/abc/upload-complete"),
    # --- Symbols / corrections (S2-C) ---
    ("GET", "/drawings/abc/symbols"),
    ("PATCH", "/symbols/abc"),
    ("POST", "/drawings/abc/symbols"),
    # --- Exports (S2-D) ---
    ("POST", "/drawings/abc/exports"),
    ("GET", "/exports/abc"),
    # --- Account / consent / GDPR (S2-F) ---
    ("GET", "/account"),
    ("PATCH", "/account"),
    ("DELETE", "/account"),
    ("GET", "/account/consent"),
    ("PATCH", "/account/consent"),
    # --- Subscription / Stripe (S2-E) ---
    ("GET", "/subscription"),
    ("POST", "/subscription/checkout"),
    ("POST", "/webhooks/stripe"),
    # --- Entity classes (S2-G) ---
    ("GET", "/entity-classes"),
    # --- P1 backend endpoints ---
    ("GET", "/teams"),
    ("POST", "/teams"),
    ("GET", "/teams/abc/members"),
    ("POST", "/teams/abc/members"),
    ("DELETE", "/teams/abc/members/u1"),
    ("GET", "/teams/abc/consent"),
    ("PATCH", "/teams/abc/consent"),
    ("POST", "/drawings/compare"),
    ("GET", "/comparisons/abc"),
    ("GET", "/drawings/abc/tables"),
    ("PATCH", "/table-cells/abc"),
    ("GET", "/exports/abc/comparison-csv"),
]

# §1.6 SPA routes (Next.js marketing "/" excluded — owned by marketing app).
SPA_ROUTES = [
    "/register",
    "/login",
    "/verify-email",
    "/dashboard",
    "/upload",
    "/drawings/:id/review",
    "/account",
    "/subscription",
    # P1
    "/teams",
    "/teams/:id/members",
    "/teams/invite/accept",
    "/comparisons/:id",
]

# §1.1 contract type names (Pydantic models + Literal aliases).
SECTION_1_1_TYPES = [
    "MLInferenceJobPayload",
    "MLInferenceResult",
    "DetectedSymbolResult",
    "TableRegionResult",
    "TableCellResult",
    "BoundingBox",
    "DrawingProcessingState",
    "BillingState",
    "TierId",
    "UserRole",
    "SymbolSource",
    "CorrectionType",
    "ExportFormat",
    "ExportStatus",
    "EntityClassId",
    "DrawingStatusSSEEvent",
    "HashCheckRequest",
    "HashCheckResponse",
    "SymbolsPageResponse",
    "SymbolRecord",
    "CorrectionRecord",
]

# §1.12 environment variables.
SECTION_1_12_VARS = [
    "DATABASE_URL",
    "REDIS_URL",
    "S3_BUCKET_NAME",
    "S3_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "JWT_RS256_PUBLIC_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "SENDGRID_API_KEY",
    "POSTHOG_API_KEY",
    "POSTHOG_HOST",
    "HMAC_SERVER_SECRET",
    "ML_MODEL_S3_KEY",
    "ML_MODEL_VERSION",
    "ODA_CONVERTER_PATH",
    "ODA_LICENSE_EXPIRY_DATE",
    "MAX_UPLOAD_SIZE_BYTES",
    "PRESIGNED_URL_EXPIRY_SECONDS",
    "ML_JOB_TIMEOUT_SECONDS",
    "CELERY_BROKER_URL",
    "DATA_REGION",
    "ENVIRONMENT",
]

CELERY_QUEUES = ["ingest", "scan", "ml_inference", "export", "gdpr_erasure", "notification"]


@pytest.fixture(scope="module")
def client():
    for k, v in REQUIRED_ENV.items():
        os.environ.setdefault(k, v)
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


# --- healthz_returns_200_with_ok_status ------------------------------------
def test_healthz_returns_200_with_ok_status(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- every_route_manifest_endpoint_returns_501 -----------------------------
@pytest.mark.parametrize("method,path", ROUTE_MANIFEST, ids=lambda x: x if isinstance(x, str) else None)
def test_every_route_manifest_endpoint_returns_501(client, method, path):
    resp = client.request(method, path, json={})
    assert resp.status_code == 501, f"{method} {path} -> {resp.status_code} (expected 501)"
    body = resp.json()
    assert "detail" in body
    assert "implement" in body["detail"].lower()


def test_hash_check_detail_names_owning_session(client):
    """Checkpoint signal: POST /drawings/hash-check 501 detail names S2-B."""
    resp = client.request("POST", "/drawings/hash-check", json={})
    assert resp.status_code == 501
    assert "S2-B" in resp.json()["detail"]


def test_healthz_is_only_non_501_endpoint(client):
    """Every manifest endpoint is 501; only /healthz is 200."""
    non_501 = []
    for method, path in ROUTE_MANIFEST:
        resp = client.request(method, path, json={})
        if resp.status_code != 501:
            non_501.append((method, path, resp.status_code))
    assert non_501 == []


# --- backend_schemas_export_all_section_1_1_types --------------------------
def test_backend_schemas_export_all_section_1_1_types():
    from app.schemas import contracts

    for name in SECTION_1_1_TYPES:
        assert hasattr(contracts, name), f"contracts.py missing §1.1 type {name}"


# --- frontend_contracts_ts_contains_all_section_1_1_type_names -------------
def test_frontend_contracts_ts_contains_all_section_1_1_type_names():
    text = (FRONTEND / "src" / "types" / "contracts.ts").read_text(encoding="utf-8")
    for name in SECTION_1_1_TYPES:
        assert name in text, f"contracts.ts missing §1.1 type {name}"
    # Parity guard: snake_case fields must NOT be camelCased.
    assert "storage_reference" in text
    assert "entity_class_id" in text
    assert "corrections_by_symbol_id" in text


# --- celery_app_declares_all_six_queue_routes ------------------------------
def test_celery_app_declares_all_six_queue_routes():
    for k, v in REQUIRED_ENV.items():
        os.environ.setdefault(k, v)
    from app.workers.celery_app import celery_app

    routes = celery_app.conf.task_routes or {}
    declared_queues = {spec.get("queue") for spec in routes.values() if isinstance(spec, dict)}
    for q in CELERY_QUEUES:
        assert q in declared_queues, f"celery task_routes missing queue {q}"


# --- config_exits_when_database_url_missing --------------------------------
def test_config_exits_when_database_url_missing():
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL",)}
    for k, v in REQUIRED_ENV.items():
        if k != "DATABASE_URL":
            env.setdefault(k, v)
    env.pop("DATABASE_URL", None)
    env["PYTHONPATH"] = str(BACKEND)
    proc = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}\n{proc.stderr}"
    assert "DATABASE_URL" in (proc.stderr + proc.stdout)


# --- env_example_lists_every_section_1_12_variable -------------------------
def test_env_example_lists_every_section_1_12_variable():
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for var in SECTION_1_12_VARS:
        assert var in text, f".env.example missing {var}"


# --- alembic_env_imports_base_declarative_base -----------------------------
def test_alembic_env_imports_base_declarative_base():
    text = (BACKEND / "alembic" / "env.py").read_text(encoding="utf-8")
    assert "from app.db.base import Base" in text
    assert "target_metadata" in text
    assert "Base.metadata" in text


# --- frontend_router_registers_every_section_1_6_spa_route -----------------
@pytest.mark.parametrize("route", SPA_ROUTES)
def test_frontend_router_registers_every_section_1_6_spa_route(route):
    text = (FRONTEND / "src" / "router.tsx").read_text(encoding="utf-8")
    # React Router uses ":id" param syntax; manifest uses "{id}".
    assert route in text, f"router.tsx missing SPA route {route}"
