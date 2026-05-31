"""Notification worker package (S2-M).

Celery-based asynchronous notification worker that dispatches transactional
emails (verification, password reset, grace-period day-1/day-6, and the P1
team-invitation stub) via SendGrid. See ``tasks.py`` for the registered Celery
tasks, ``sendgrid_client.py`` for the SDK wrapper, and ``templates.py`` for the
pure email-body builders.

Importing this package does not register the tasks; Celery autodiscovers them
when ``tasks`` is imported by the worker bootstrap.
"""
from __future__ import annotations

__all__: list[str] = []
