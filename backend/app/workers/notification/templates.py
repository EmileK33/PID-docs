"""Pure email-body builders for the notification worker (S2-M).

Every function in this module is **pure**: it performs no I/O, no DB access, and
no network calls. All variable content (recipient names, tokens, dates) is
supplied via parameters and the result is a plain :class:`EmailContent` value
object. The Celery tasks (``tasks.py``) turn an :class:`EmailContent` into a
SendGrid ``Mail`` and dispatch it; keeping rendering pure makes the templates
trivially unit-testable and free of cross-session coupling.

Per the S2-M brief: "Template module must be pure (no I/O)".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

# Public-facing links embed tokens. The host is a build-time constant rather
# than a runtime env var because templates must remain pure (no settings/IO
# lookups) and the link host is identical across all transactional mail.
APP_BASE_URL = "https://app.pidextract.com"
VERIFY_PATH = "/verify-email"
RESET_PATH = "/reset-password"
SUPPORT_EMAIL = "support@pidextract.com"


@dataclass(frozen=True)
class EmailContent:
    """Rendered, transport-agnostic email content.

    ``subject`` plus an HTML and a plain-text body. The plain-text body is a
    deliverability best-practice (multipart alternative) and also guarantees the
    token/link is present even for text-only clients.
    """

    subject: str
    html_body: str
    plain_text_body: str


def _format_grace_period_end(grace_period_end: str) -> str:
    """Render an ISO-8601 UTC timestamp as a human-readable UTC date string.

    Accepts values like ``"2024-01-22T00:00:00Z"`` (trailing ``Z``) or an
    explicit ``+00:00`` offset. Output example: ``"January 22, 2024 at 00:00
    UTC"``. Pure: parsing/formatting only, no I/O.
    """
    normalized = grace_period_end.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    # %-d / %-m are not portable to Windows; format the day without padding by
    # hand to keep the builder OS-independent.
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year} at {parsed.strftime('%H:%M')} UTC"


def build_verification_email(
    display_name: str, verification_token: str
) -> EmailContent:
    """Email confirming a new registration (US-001).

    The ``verification_token`` is embedded in the confirmation link (AC-2).
    """
    link = f"{APP_BASE_URL}{VERIFY_PATH}?token={verification_token}"
    subject = "Verify your email address"
    html_body = (
        f"<p>Hi {display_name},</p>"
        f"<p>Welcome to P&amp;ID Extract. Please confirm your email address by "
        f'clicking the link below:</p>'
        f'<p><a href="{link}">Verify my email</a></p>'
        f"<p>If the button does not work, paste this URL into your browser:</p>"
        f"<p>{link}</p>"
        f"<p>If you did not create this account, you can ignore this email.</p>"
    )
    plain_text_body = (
        f"Hi {display_name},\n\n"
        f"Welcome to P&ID Extract. Confirm your email address by visiting:\n"
        f"{link}\n\n"
        f"If you did not create this account, you can ignore this email."
    )
    return EmailContent(subject=subject, html_body=html_body, plain_text_body=plain_text_body)


def build_password_reset_email(
    display_name: str, reset_token: str
) -> EmailContent:
    """Email with a password-reset link (US-002).

    The ``reset_token`` is embedded in the reset link (AC-2).
    """
    link = f"{APP_BASE_URL}{RESET_PATH}?token={reset_token}"
    subject = "Reset your password"
    html_body = (
        f"<p>Hi {display_name},</p>"
        f"<p>We received a request to reset your password. Click the link below "
        f"to choose a new one:</p>"
        f'<p><a href="{link}">Reset my password</a></p>'
        f"<p>If the button does not work, paste this URL into your browser:</p>"
        f"<p>{link}</p>"
        f"<p>If you did not request a password reset, you can safely ignore this "
        f"email; your password will not change.</p>"
    )
    plain_text_body = (
        f"Hi {display_name},\n\n"
        f"We received a request to reset your password. Visit the link below to "
        f"choose a new one:\n{link}\n\n"
        f"If you did not request a password reset, you can ignore this email."
    )
    return EmailContent(subject=subject, html_body=html_body, plain_text_body=plain_text_body)


def build_grace_day1_email(
    display_name: str, grace_period_end: str
) -> EmailContent:
    """Day-1 grace-period notice on entry (US-020).

    Body includes the human-readable ``grace_period_end`` so the user knows when
    access will be revoked (AC-2).
    """
    end_human = _format_grace_period_end(grace_period_end)
    subject = "Action needed: your payment could not be processed"
    html_body = (
        f"<p>Hi {display_name},</p>"
        f"<p>We were unable to process the most recent payment for your "
        f"subscription, so your account has entered a grace period.</p>"
        f"<p>You will keep full access until <strong>{end_human}</strong>. Please "
        f"update your payment method before then to avoid any interruption.</p>"
        f"<p>You can update your billing details from your account settings.</p>"
    )
    plain_text_body = (
        f"Hi {display_name},\n\n"
        f"We were unable to process the most recent payment for your "
        f"subscription, so your account has entered a grace period.\n\n"
        f"You will keep full access until {end_human}. Please update your payment "
        f"method before then to avoid any interruption."
    )
    return EmailContent(subject=subject, html_body=html_body, plain_text_body=plain_text_body)


def build_grace_day6_email(
    display_name: str, grace_period_end: str
) -> EmailContent:
    """Day-6 grace-period reminder communicating urgency (US-020).

    Body includes the ``grace_period_end`` and stresses that access will be
    revoked within 24 hours (AC-4).
    """
    end_human = _format_grace_period_end(grace_period_end)
    subject = "Final reminder: access ends within 24 hours"
    html_body = (
        f"<p>Hi {display_name},</p>"
        f"<p><strong>This is your final reminder.</strong> Your payment is still "
        f"outstanding and your access will be revoked within the next 24 hours.</p>"
        f"<p>Your grace period ends on <strong>{end_human}</strong>. Update your "
        f"payment method now to keep your account active and avoid losing access "
        f"to your drawings and exports.</p>"
    )
    plain_text_body = (
        f"Hi {display_name},\n\n"
        f"This is your final reminder. Your payment is still outstanding and your "
        f"access will be revoked within the next 24 hours.\n\n"
        f"Your grace period ends on {end_human}. Update your payment method now to "
        f"keep your account active."
    )
    return EmailContent(subject=subject, html_body=html_body, plain_text_body=plain_text_body)


__all__ = [
    "EmailContent",
    "APP_BASE_URL",
    "VERIFY_PATH",
    "RESET_PATH",
    "build_verification_email",
    "build_password_reset_email",
    "build_grace_day1_email",
    "build_grace_day6_email",
]
