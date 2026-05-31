"""Celery notification tasks — SendGrid email dispatch (S2-M).

Registers the four P0 transactional-email tasks on the ``notification`` queue
plus the P1 team-invitation stub:

* ``notification.send_verification_email``     (US-001)
* ``notification.send_password_reset_email``   (US-002)
* ``notification.send_grace_day1_email``       (US-020)
* ``notification.send_grace_day6_email``       (US-020)
* ``notification.send_team_invitation_email``  (US-023 — P1 STUB)

Retry policy (§Performance targets / §Critical implementation notes), applied
uniformly to all four P0 tasks via :func:`_dispatch`:

* 2xx                      -> success
* 429                      -> retry after ``Retry-After`` (fallback 60s), max 3
* 5xx / network / timeout  -> retry, exponential backoff 60s x2 (max 3600s), max 3
* 4xx (except 429)         -> log with user_id/email/status; fail; **no retry**

Email failures never propagate as an *unhandled* crash: every failure is either a
controlled Celery ``retry`` or a logged-and-raised :class:`SendGridError` that
Celery records as task FAILURE without taking down the worker process.

No PostHog/analytics events are emitted from this worker (§1.10).
"""
from __future__ import annotations

import logging

from sendgrid.helpers.mail import Content, Mail

# Import for its side effect (installs BaseTask as the celery_app default base)
# and for the explicit base=BaseTask below.
from app.workers.base import BaseTask
from app.workers.celery_app import celery_app

# S1-D queue constant. The S2-M brief names this ``NOTIFICATION_QUEUE``; the
# merged S1-D module (app.workers.queues) exports it as ``QUEUE_NOTIFICATION``
# with the value "notification". We import the real symbol and use it rather
# than hard-coding the string, so a future queue rename propagates here.
from app.workers.queues import QUEUE_NOTIFICATION

from app.workers.notification.sendgrid_client import (
    SendGridError,
    get_sendgrid_client,
)
from app.workers.notification.templates import (
    EmailContent,
    build_grace_day1_email,
    build_grace_day6_email,
    build_password_reset_email,
    build_verification_email,
)

logger = logging.getLogger("pid.workers.notification")

# Sender identity for all transactional mail. A verified SendGrid sender.
FROM_EMAIL = "no-reply@pidextract.com"

# --- Retry policy constants (single source of truth, mirrored by tests) ---
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 60
RETRY_BACKOFF_MAX_SECONDS = 3600
RATE_LIMIT_FALLBACK_SECONDS = 60


def _backoff_countdown(retries_done: int) -> int:
    """Exponential backoff: base 60s, doubling each attempt, capped at 3600s.

    ``retries_done`` is the number of retries already performed (Celery's
    ``request.retries``): 0 -> 60s, 1 -> 120s, 2 -> 240s, ...
    """
    return min(
        RETRY_BACKOFF_BASE_SECONDS * (2 ** max(retries_done, 0)),
        RETRY_BACKOFF_MAX_SECONDS,
    )


def _retry_after_seconds(headers: dict, fallback: int = RATE_LIMIT_FALLBACK_SECONDS) -> int:
    """Parse a ``Retry-After`` header (case-insensitive) as an int seconds value.

    Falls back to ``fallback`` when the header is absent or unparseable.
    """
    if headers:
        for key, value in headers.items():
            if str(key).lower() == "retry-after":
                try:
                    return int(str(value).strip())
                except (TypeError, ValueError):
                    return fallback
    return fallback


def _build_mail(to_email: str, content: EmailContent) -> Mail:
    """Construct a SendGrid ``Mail`` from rendered :class:`EmailContent`.

    Adds both a plain-text and an HTML part (multipart alternative).
    """
    message = Mail(from_email=FROM_EMAIL, to_emails=to_email, subject=content.subject)
    message.add_content(Content("text/plain", content.plain_text_body))
    message.add_content(Content("text/html", content.html_body))
    return message


def _dispatch(
    task: BaseTask,
    *,
    to_email: str,
    content: EmailContent,
    user_id: str,
    email_kind: str,
) -> None:
    """Send ``content`` to ``to_email`` and apply the shared retry policy.

    Raises :class:`celery.exceptions.Retry` on retriable failures (handled by
    Celery), or re-raises :class:`SendGridError` on permanent 4xx so Celery
    records FAILURE. Never raises an uncontrolled exception.
    """
    message = _build_mail(to_email, content)
    client = get_sendgrid_client()
    try:
        client.send(message)
    except SendGridError as exc:
        status = exc.status_code
        if status == 429:
            countdown = _retry_after_seconds(exc.headers)
            logger.warning(
                "SendGrid rate-limited %s email (user_id=%s); retrying in %ss",
                email_kind,
                user_id,
                countdown,
            )
            raise task.retry(exc=exc, countdown=countdown, max_retries=MAX_RETRIES)
        if status is not None and 400 <= status < 500:
            # Permanent client error (bad address, rejected payload, ...).
            # Log with correlation fields and fail without retry (no autoretry).
            logger.error(
                "SendGrid permanent failure for %s email: status=%s user_id=%s "
                "email=%s body=%s",
                email_kind,
                status,
                user_id,
                to_email,
                exc.body,
            )
            raise
        # 5xx, or transport failure (status is None): transient -> backoff retry.
        countdown = _backoff_countdown(getattr(task.request, "retries", 0) or 0)
        logger.warning(
            "SendGrid transient failure for %s email: status=%s user_id=%s; "
            "retrying in %ss",
            email_kind,
            status,
            user_id,
            countdown,
        )
        raise task.retry(exc=exc, countdown=countdown, max_retries=MAX_RETRIES)
    else:
        logger.info("Sent %s email (user_id=%s)", email_kind, user_id)


# ---------------------------------------------------------------------------
# P0 tasks. ``autoretry_for=()`` disables BaseTask's blanket autoretry so the
# 4xx (no-retry) gate is honored; retries are driven explicitly by ``_dispatch``
# via ``self.retry`` with the correct countdown per failure class.
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="notification.send_verification_email",
    queue=QUEUE_NOTIFICATION,
    autoretry_for=(),
    max_retries=MAX_RETRIES,
)
def send_verification_email(
    self,
    user_id: str,
    email: str,
    display_name: str,
    verification_token: str,
) -> None:
    """US-001: send the account verification email."""
    content = build_verification_email(display_name, verification_token)
    _dispatch(
        self,
        to_email=email,
        content=content,
        user_id=user_id,
        email_kind="verification",
    )


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="notification.send_password_reset_email",
    queue=QUEUE_NOTIFICATION,
    autoretry_for=(),
    max_retries=MAX_RETRIES,
)
def send_password_reset_email(
    self,
    user_id: str,
    email: str,
    display_name: str,
    reset_token: str,
) -> None:
    """US-002: send the password-reset email."""
    content = build_password_reset_email(display_name, reset_token)
    _dispatch(
        self,
        to_email=email,
        content=content,
        user_id=user_id,
        email_kind="password_reset",
    )


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="notification.send_grace_day1_email",
    queue=QUEUE_NOTIFICATION,
    autoretry_for=(),
    max_retries=MAX_RETRIES,
)
def send_grace_day1_email(
    self,
    user_id: str,
    email: str,
    display_name: str,
    grace_period_end: str,
) -> None:
    """US-020: send the grace-period day-1 entry notice."""
    content = build_grace_day1_email(display_name, grace_period_end)
    _dispatch(
        self,
        to_email=email,
        content=content,
        user_id=user_id,
        email_kind="grace_day1",
    )


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="notification.send_grace_day6_email",
    queue=QUEUE_NOTIFICATION,
    autoretry_for=(),
    max_retries=MAX_RETRIES,
)
def send_grace_day6_email(
    self,
    user_id: str,
    email: str,
    display_name: str,
    grace_period_end: str,
) -> None:
    """US-020: send the grace-period day-6 reminder."""
    content = build_grace_day6_email(display_name, grace_period_end)
    _dispatch(
        self,
        to_email=email,
        content=content,
        user_id=user_id,
        email_kind="grace_day6",
    )


# ---------------------------------------------------------------------------
# P1 STUB — registered as a valid Celery task so future sessions can import and
# enqueue it, but raises on execution. The NotImplementedError is raised only in
# the task body (not at import/decoration time).
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="notification.send_team_invitation_email",
    queue=QUEUE_NOTIFICATION,
)
def send_team_invitation_email(
    self,
    invited_email: str,
    inviter_name: str,
    team_name: str,
    invitation_token: str,
    expires_at: str,
) -> None:
    """US-023 (P1): team workspace invitation email. Not implemented for MVP."""
    # P1-STUB: team invitation email not implemented
    raise NotImplementedError("P1-STUB: team invitation email not implemented")


__all__ = [
    "send_verification_email",
    "send_password_reset_email",
    "send_grace_day1_email",
    "send_grace_day6_email",
    "send_team_invitation_email",
    "FROM_EMAIL",
    "MAX_RETRIES",
    "RETRY_BACKOFF_BASE_SECONDS",
    "RETRY_BACKOFF_MAX_SECONDS",
    "RATE_LIMIT_FALLBACK_SECONDS",
]
