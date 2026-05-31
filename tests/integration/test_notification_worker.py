"""Integration tests for the S2-M notification worker (SendGrid).

Run: ``pytest tests/integration/test_notification_worker.py -v``

These exercise the four P0 Celery email tasks (verification, password reset,
grace day-1, grace day-6), the SendGrid SDK wrapper, the pure template builders,
and the P1 team-invitation stub.

Design notes (per the S2-M brief's "Independent Test" section):

* ``CELERY_TASK_ALWAYS_EAGER`` is **not** used. Tasks are tested by calling the
  task body directly (``task(**payload)``), which runs the wrapped function
  synchronously in-process without touching the Redis broker. For retriable
  failures we patch the task's ``retry`` method so no broker connection is made.
* Every SendGrid HTTP call is mocked: tests patch ``get_sendgrid_client`` in the
  ``tasks`` module to return a fake whose ``send`` returns a 202 response or
  raises a normalized ``SendGridError``. No live SendGrid / Redis / Postgres
  connection is required; all ACs pass with only S0-A + S1-A + S1-D merged.
* ``app.*`` is imported lazily (inside the ``mods`` fixture) so the shared S0-B
  smoke suite's "no app.* in sys.modules" guard stays green when the whole
  ``tests/integration`` tree runs together.
"""
from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# --- Make the `app` package (rooted at backend/) importable -----------------
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
for _p in (str(BACKEND), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- §1.12 "Refuse to start" env contract -----------------------------------
# The shared conftest seeds most REQUIRED vars but NOT the ML/ODA pair, so set
# every one here (setdefault, so CI/dev overrides win) before app.config loads.
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
    "SENDGRID_API_KEY": "SG.test_key",
    "HMAC_SERVER_SECRET": "high-entropy-secret",
    "ML_MODEL_S3_KEY": "models/pid/v1.onnx",
    "ODA_CONVERTER_PATH": "/opt/oda/ODAFileConverter",
    "ENVIRONMENT": "development",
}
for _k, _v in _REQUIRED_ENV.items():
    os.environ.setdefault(_k, _v)


# --- Payload fixtures (from the brief's Mocking contract) -------------------
VERIFICATION_PAYLOAD = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "user@example.com",
    "display_name": "Test User",
    "verification_token": "tok_verify_abc123",
}

PASSWORD_RESET_PAYLOAD = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "user@example.com",
    "display_name": "Test User",
    "reset_token": "tok_reset_xyz789",
}

GRACE_DAY1_PAYLOAD = {
    "user_id": "00000000-0000-0000-0000-000000000002",
    "email": "user@example.com",
    "display_name": "Grace User",
    "grace_period_end": "2024-01-22T00:00:00Z",
}

GRACE_DAY6_PAYLOAD = {
    "user_id": "00000000-0000-0000-0000-000000000002",
    "email": "user@example.com",
    "display_name": "Grace User",
    "grace_period_end": "2024-01-22T00:00:00Z",
}

TEAM_INVITATION_PAYLOAD = {
    "invited_email": "invite@example.com",
    "inviter_name": "Admin User",
    "team_name": "Acme Corp",
    "invitation_token": "tok_invite_aaa111",
    "expires_at": "2024-01-18T12:00:00Z",
}


# --- Lazy app imports -------------------------------------------------------
@pytest.fixture(scope="session")
def mods():
    """Import the worker modules lazily and expose them as a namespace."""
    from app.workers import base
    from app.workers.notification import sendgrid_client, tasks, templates

    p0_tasks = (
        tasks.send_verification_email,
        tasks.send_password_reset_email,
        tasks.send_grace_day1_email,
        tasks.send_grace_day6_email,
    )
    return SimpleNamespace(
        tasks=tasks,
        templates=templates,
        sg=sendgrid_client,
        BaseTask=base.BaseTask,
        p0_tasks=p0_tasks,
        all_tasks=p0_tasks + (tasks.send_team_invitation_email,),
    )


@pytest.fixture
def success_client(mocker):
    """Fake SendGridClient whose ``send`` returns a 202 response."""
    client = mocker.MagicMock()
    client.send.return_value = mocker.MagicMock(status_code=202)
    return client


def _patch_client(mocker, mods, client):
    """Patch ``tasks.get_sendgrid_client`` to return ``client``."""
    return mocker.patch.object(mods.tasks, "get_sendgrid_client", return_value=client)


def _sent_mail(client):
    """Return the SendGrid ``Mail`` object passed to the last ``send`` call."""
    return client.send.call_args.args[0]


def _sent_mail_json(client) -> str:
    return json.dumps(_sent_mail(client).get())


def _sent_to_email(client) -> str:
    return _sent_mail(client).get()["personalizations"][0]["to"][0]["email"]


# --- Shared retry-policy assertions -----------------------------------------
def _assert_transient_retry(task, payload, mods, mocker, *, status, expected_countdown):
    """A 5xx/transient failure -> a single Celery retry with the given countdown
    and ``max_retries=3``."""
    from celery.exceptions import Retry

    client = mocker.MagicMock()
    client.send.side_effect = mods.sg.SendGridError(status, "transient")
    _patch_client(mocker, mods, client)
    retry = mocker.patch.object(task, "retry", return_value=Retry())

    with pytest.raises(Retry):
        task(**payload)

    assert retry.call_count == 1
    assert retry.call_args.kwargs["countdown"] == expected_countdown
    assert retry.call_args.kwargs["max_retries"] == mods.tasks.MAX_RETRIES


def _assert_429_retry(task, payload, mods, mocker, *, retry_after, expected_countdown):
    from celery.exceptions import Retry

    client = mocker.MagicMock()
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    client.send.side_effect = mods.sg.SendGridError(429, "rate limited", headers)
    _patch_client(mocker, mods, client)
    retry = mocker.patch.object(task, "retry", return_value=Retry())

    with pytest.raises(Retry):
        task(**payload)

    assert retry.call_count == 1
    assert retry.call_args.kwargs["countdown"] == expected_countdown
    assert retry.call_args.kwargs["max_retries"] == mods.tasks.MAX_RETRIES


def _assert_no_retry_on_4xx(task, payload, mods, mocker, *, status=400):
    client = mocker.MagicMock()
    client.send.side_effect = mods.sg.SendGridError(status, "Bad Request")
    _patch_client(mocker, mods, client)
    retry = mocker.patch.object(task, "retry")

    with pytest.raises(mods.sg.SendGridError):
        task(**payload)

    retry.assert_not_called()


# ===========================================================================
# US-001 — verification email
# ===========================================================================
def test_verification_email_sends_to_correct_address(mods, mocker, success_client):
    _patch_client(mocker, mods, success_client)
    mods.tasks.send_verification_email(**VERIFICATION_PAYLOAD)
    assert success_client.send.call_count == 1
    assert _sent_to_email(success_client) == VERIFICATION_PAYLOAD["email"]


def test_verification_email_contains_token_in_body(mods, mocker, success_client):
    _patch_client(mocker, mods, success_client)
    mods.tasks.send_verification_email(**VERIFICATION_PAYLOAD)
    assert VERIFICATION_PAYLOAD["verification_token"] in _sent_mail_json(success_client)


def test_verification_email_retries_on_5xx(mods, mocker):
    # First attempt (request.retries == 0) -> base backoff of 60s; max 3 retries.
    _assert_transient_retry(
        mods.tasks.send_verification_email,
        VERIFICATION_PAYLOAD,
        mods,
        mocker,
        status=500,
        expected_countdown=mods.tasks.RETRY_BACKOFF_BASE_SECONDS,
    )


def test_verification_email_no_retry_on_4xx(mods, mocker):
    _assert_no_retry_on_4xx(
        mods.tasks.send_verification_email, VERIFICATION_PAYLOAD, mods, mocker
    )


def test_verification_email_retries_on_429(mods, mocker):
    # Respect the Retry-After header; fall back to 60s when absent.
    _assert_429_retry(
        mods.tasks.send_verification_email,
        VERIFICATION_PAYLOAD,
        mods,
        mocker,
        retry_after="30",
        expected_countdown=30,
    )
    _assert_429_retry(
        mods.tasks.send_verification_email,
        VERIFICATION_PAYLOAD,
        mods,
        mocker,
        retry_after=None,
        expected_countdown=mods.tasks.RATE_LIMIT_FALLBACK_SECONDS,
    )


def test_verification_email_failure_does_not_crash_worker(mods, mocker):
    from celery.exceptions import Retry

    # A permanent 4xx surfaces only as a controlled SendGridError (Celery records
    # FAILURE) — never an uncontrolled exception that would crash the worker.
    bad = mocker.MagicMock()
    bad.send.side_effect = mods.sg.SendGridError(400, "Bad Request")
    _patch_client(mocker, mods, bad)
    with pytest.raises(mods.sg.SendGridError):
        mods.tasks.send_verification_email(**VERIFICATION_PAYLOAD)

    # A transient 5xx is converted into a controlled Celery Retry, not a crash.
    transient = mocker.MagicMock()
    transient.send.side_effect = mods.sg.SendGridError(503, "Service Unavailable")
    _patch_client(mocker, mods, transient)
    mocker.patch.object(mods.tasks.send_verification_email, "retry", return_value=Retry())
    with pytest.raises(Retry):
        mods.tasks.send_verification_email(**VERIFICATION_PAYLOAD)


# ===========================================================================
# US-002 — password reset email
# ===========================================================================
def test_password_reset_email_sends_to_correct_address(mods, mocker, success_client):
    _patch_client(mocker, mods, success_client)
    mods.tasks.send_password_reset_email(**PASSWORD_RESET_PAYLOAD)
    assert success_client.send.call_count == 1
    assert _sent_to_email(success_client) == PASSWORD_RESET_PAYLOAD["email"]


def test_password_reset_email_contains_reset_token(mods, mocker, success_client):
    _patch_client(mocker, mods, success_client)
    mods.tasks.send_password_reset_email(**PASSWORD_RESET_PAYLOAD)
    assert PASSWORD_RESET_PAYLOAD["reset_token"] in _sent_mail_json(success_client)


def test_password_reset_retry_mirrors_verification_policy(mods, mocker):
    task = mods.tasks.send_password_reset_email
    _assert_transient_retry(
        task, PASSWORD_RESET_PAYLOAD, mods, mocker,
        status=502, expected_countdown=mods.tasks.RETRY_BACKOFF_BASE_SECONDS,
    )
    _assert_no_retry_on_4xx(task, PASSWORD_RESET_PAYLOAD, mods, mocker, status=403)
    _assert_429_retry(
        task, PASSWORD_RESET_PAYLOAD, mods, mocker,
        retry_after="45", expected_countdown=45,
    )


# ===========================================================================
# US-020 — grace period emails
# ===========================================================================
def test_grace_day1_email_sends_to_correct_address(mods, mocker, success_client):
    _patch_client(mocker, mods, success_client)
    mods.tasks.send_grace_day1_email(**GRACE_DAY1_PAYLOAD)
    assert success_client.send.call_count == 1
    assert _sent_to_email(success_client) == GRACE_DAY1_PAYLOAD["email"]


def test_grace_day1_email_contains_grace_period_end(mods, mocker, success_client):
    _patch_client(mocker, mods, success_client)
    mods.tasks.send_grace_day1_email(**GRACE_DAY1_PAYLOAD)
    body = _sent_mail_json(success_client)
    human = mods.templates._format_grace_period_end(GRACE_DAY1_PAYLOAD["grace_period_end"])
    assert human in body
    # Human-readable, not the raw ISO string.
    assert "January 22, 2024" in body


def test_grace_day6_email_sends_to_correct_address(mods, mocker, success_client):
    _patch_client(mocker, mods, success_client)
    mods.tasks.send_grace_day6_email(**GRACE_DAY6_PAYLOAD)
    assert success_client.send.call_count == 1
    assert _sent_to_email(success_client) == GRACE_DAY6_PAYLOAD["email"]


def test_grace_day6_email_contains_urgency_and_grace_period_end(mods, mocker, success_client):
    _patch_client(mocker, mods, success_client)
    mods.tasks.send_grace_day6_email(**GRACE_DAY6_PAYLOAD)
    body = _sent_mail_json(success_client)
    human = mods.templates._format_grace_period_end(GRACE_DAY6_PAYLOAD["grace_period_end"])
    assert human in body
    assert "24 hours" in body  # imminent revocation urgency


def test_grace_day1_and_day6_are_independent_tasks(mods, mocker, success_client):
    day1 = mods.tasks.send_grace_day1_email
    day6 = mods.tasks.send_grace_day6_email
    # Distinct task objects with distinct registered names — no ordering coupling.
    assert day1 is not day6
    assert day1.name != day6.name
    # day6 executes successfully without day1 ever having run.
    _patch_client(mocker, mods, success_client)
    day6(**GRACE_DAY6_PAYLOAD)
    assert success_client.send.call_count == 1


def test_grace_email_retry_policy_matches_verification(mods, mocker):
    for task, payload in (
        (mods.tasks.send_grace_day1_email, GRACE_DAY1_PAYLOAD),
        (mods.tasks.send_grace_day6_email, GRACE_DAY6_PAYLOAD),
    ):
        _assert_transient_retry(
            task, payload, mods, mocker,
            status=500, expected_countdown=mods.tasks.RETRY_BACKOFF_BASE_SECONDS,
        )
        _assert_no_retry_on_4xx(task, payload, mods, mocker)
        _assert_429_retry(
            task, payload, mods, mocker, retry_after="30", expected_countdown=30,
        )


# ===========================================================================
# US-023 — team invitation P1 stub
# ===========================================================================
def test_team_invitation_stub_is_importable(mods):
    from app.workers.notification.tasks import send_team_invitation_email

    assert send_team_invitation_email is not None
    assert send_team_invitation_email is mods.tasks.send_team_invitation_email


def test_team_invitation_stub_raises_not_implemented(mods):
    # Calling the task body executes the stub and raises (the error is raised in
    # the body, never at import/decoration time).
    with pytest.raises(
        NotImplementedError,
        match="P1-STUB: team invitation email not implemented",
    ):
        mods.tasks.send_team_invitation_email(**TEAM_INVITATION_PAYLOAD)


def test_team_invitation_stub_registered_as_celery_task(mods):
    from app.workers.celery_app import celery_app

    assert "notification.send_team_invitation_email" in celery_app.tasks
    assert isinstance(mods.tasks.send_team_invitation_email, mods.BaseTask)


# ===========================================================================
# Technical contracts
# ===========================================================================
def test_all_p0_tasks_bound_to_notification_queue(mods):
    from app.workers.celery_app import celery_app
    from app.workers.queues import QUEUE_NOTIFICATION

    for task in mods.p0_tasks:
        # Bound via the imported S1-D constant, not a hard-coded literal.
        assert task.queue == QUEUE_NOTIFICATION
        assert task.name.startswith("notification.")
        # Routing table resolves the task name to the notification queue.
        route = celery_app.amqp.router.route({}, task.name)
        assert route["queue"].name == QUEUE_NOTIFICATION


def test_sendgrid_client_uses_settings_api_key(mods, mocker):
    from app.config import settings

    sdk = mocker.patch.object(mods.sg, "SendGridAPIClient")
    mods.sg.SendGridClient()
    sdk.assert_called_once_with(settings.SENDGRID_API_KEY)


def test_templates_are_pure_functions(mods, mocker):
    templates = mods.templates

    # No file or network I/O: patch open/socket to explode if touched.
    mocker.patch("builtins.open", side_effect=AssertionError("templates did file I/O"))
    mocker.patch("socket.socket", side_effect=AssertionError("templates did network I/O"))

    builders = (
        lambda: templates.build_verification_email("U", "tok_v"),
        lambda: templates.build_password_reset_email("U", "tok_r"),
        lambda: templates.build_grace_day1_email("U", "2024-01-22T00:00:00Z"),
        lambda: templates.build_grace_day6_email("U", "2024-01-22T00:00:00Z"),
    )
    for build in builders:
        first = build()
        second = build()
        # Deterministic output (pure) and a structured content value.
        assert first == second
        assert first.subject and first.html_body and first.plain_text_body

    # Source contains no DB/network client imports.
    src = inspect.getsource(templates)
    for forbidden in ("requests", "httpx", "sqlalchemy", "boto3", "redis", "sendgrid"):
        assert forbidden not in src


def test_no_posthog_calls_in_tasks(mods, mocker, success_client):
    import posthog

    cap = mocker.patch.object(posthog, "capture", create=True)
    _patch_client(mocker, mods, success_client)

    mods.tasks.send_verification_email(**VERIFICATION_PAYLOAD)
    mods.tasks.send_grace_day1_email(**GRACE_DAY1_PAYLOAD)

    assert cap.call_count == 0
    # The worker module does not even import posthog.
    assert not hasattr(mods.tasks, "posthog")


def test_all_tasks_inherit_from_base_task(mods):
    for task in mods.all_tasks:
        assert isinstance(task, mods.BaseTask)


# --- Pure retry-helper coverage (exponential backoff growth + cap) ----------
def test_backoff_is_exponential_and_capped(mods):
    backoff = mods.tasks._backoff_countdown
    base = mods.tasks.RETRY_BACKOFF_BASE_SECONDS
    assert backoff(0) == base          # 60
    assert backoff(1) == base * 2      # 120
    assert backoff(2) == base * 4      # 240
    assert backoff(100) == mods.tasks.RETRY_BACKOFF_MAX_SECONDS  # capped at 3600
