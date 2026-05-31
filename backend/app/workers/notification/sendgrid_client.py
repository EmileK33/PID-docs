"""SendGrid SDK wrapper with retry-aware error normalization (S2-M).

This module is the *only* place the notification worker talks to SendGrid. It
uses the official ``sendgrid`` SDK (``SendGridAPIClient``) for the HTTP call —
never ``httpx``/``requests`` directly — so SDK header/retry handling is
preserved (per the S2-M technology constraints).

The SDK raises ``python_http_client.exceptions.HTTPError`` subclasses on non-2xx
responses, whose constructor and attributes are awkward to reason about at the
call site. We normalize every failure into a single :class:`SendGridError`
carrying ``status_code`` / ``body`` / ``headers`` so the Celery tasks
(``tasks.py``) can gate their retry policy on a stable contract:

* 2xx                      -> success (``send`` returns the response)
* 429                      -> :class:`SendGridError` (status 429, ``Retry-After``)
* 5xx / network / timeout  -> :class:`SendGridError` (status 5xx or ``None``)
* 4xx (except 429)         -> :class:`SendGridError` (status 4xx)

The API key is read from ``app.config.settings.SENDGRID_API_KEY`` (S0-A), never
from ``os.environ`` directly. ``config.py`` is responsible for refusing to start
when the key is absent, so this wrapper assumes it is present.
"""
from __future__ import annotations

from typing import Any, Optional

from python_http_client.exceptions import HTTPError
from sendgrid import SendGridAPIClient

from app.config import settings


class SendGridError(Exception):
    """Normalized SendGrid failure.

    ``status_code`` is the HTTP status returned by SendGrid, or ``None`` for a
    transport-level failure (network error / timeout) where no response was
    received — which the tasks treat the same as a 5xx (retry with backoff).
    """

    def __init__(
        self,
        status_code: Optional[int],
        body: str = "",
        headers: Optional[dict] = None,
    ) -> None:
        self.status_code = status_code
        self.body = body
        self.headers = headers or {}
        super().__init__(f"SendGrid request failed (status={status_code}): {body}")


def _coerce_headers(raw: Any) -> dict:
    """Best-effort conversion of SDK header containers to a plain dict.

    ``HTTPError.headers`` may be a dict, an ``email.message.Message``-like
    object, or ``None`` depending on the failure mode. We only need
    case-insensitive ``Retry-After`` lookup downstream, so normalize keys to a
    dict here and let the caller handle casing.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    # urllib HTTPMessage / email.message.Message expose .items()
    items = getattr(raw, "items", None)
    if callable(items):
        try:
            return {str(k): str(v) for k, v in items()}
        except Exception:  # pragma: no cover - defensive
            return {}
    return {}


class SendGridClient:
    """Thin wrapper over ``SendGridAPIClient``.

    Parameters
    ----------
    api_key:
        SendGrid Bearer API key. Defaults to ``settings.SENDGRID_API_KEY`` so
        callers never need to touch the environment.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key if api_key is not None else settings.SENDGRID_API_KEY
        self._client = SendGridAPIClient(self._api_key)

    def send(self, message: Any) -> Any:
        """Send a SendGrid ``Mail`` message.

        Returns the SDK ``Response`` on success (2xx). Raises
        :class:`SendGridError` on any non-2xx status or transport failure so the
        caller can apply the retry policy. Never raises a raw SDK/transport
        exception.
        """
        try:
            response = self._client.send(message)
        except HTTPError as exc:
            status = getattr(exc, "status_code", None)
            body = getattr(exc, "body", "")
            if isinstance(body, (bytes, bytearray)):
                body = body.decode("utf-8", errors="replace")
            raise SendGridError(
                status_code=status,
                body=str(body) if body is not None else "",
                headers=_coerce_headers(getattr(exc, "headers", None)),
            ) from exc
        except Exception as exc:  # network error / timeout: no HTTP status
            raise SendGridError(status_code=None, body=str(exc)) from exc

        status_code = getattr(response, "status_code", None)
        if status_code is not None and status_code >= 300:
            # SDK returned a response object rather than raising (defensive).
            raise SendGridError(
                status_code=status_code,
                body=str(getattr(response, "body", "")),
                headers=_coerce_headers(getattr(response, "headers", None)),
            )
        return response


# Module-level lazy singleton. Built on first use so importing this module (e.g.
# during Celery task registration) does not require a real API key, and tests
# can patch ``SendGridClient`` / ``get_sendgrid_client`` before first call.
_client_singleton: Optional[SendGridClient] = None


def get_sendgrid_client() -> SendGridClient:
    """Return the process-wide :class:`SendGridClient`, creating it on demand."""
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = SendGridClient()
    return _client_singleton


__all__ = ["SendGridClient", "SendGridError", "get_sendgrid_client"]
