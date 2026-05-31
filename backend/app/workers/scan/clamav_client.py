"""ClamAV TCP client for the malware-scan sidecar (S2-I, §1.7 / §1.13).

Thin wrapper over :mod:`pyclamd` that streams bytes straight to the clamd daemon
over TCP (the sidecar pattern). The contract:

* **No subprocess** — we never shell out to the ``clamscan`` binary.
* **No disk write** — :meth:`ClamAVClient.scan_stream` forwards a file-like
  object (e.g. an S3 ``StreamingBody``) directly to ``INSTREAM`` so infected
  bytes never touch the worker filesystem.
* **Connection config from the environment, no hard failures** (§1.12 does not
  mandate these): ``CLAMAV_HOST`` (default ``"clamav"``) and ``CLAMAV_PORT``
  (default ``3310``). Missing values fall back silently — the worker must not
  refuse to start because they are absent.

Transient connectivity problems surface as :class:`ClamAVConnectionError` so the
Celery task can drive the retry → ``Failed`` branch of the state machine; a
positive detection is *not* an error — it returns a :class:`ScanResult` with
``clean=False``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import IO, Optional

import pyclamd

# §1.7 sidecar defaults — not in §1.12's mandatory manifest, so read leniently.
DEFAULT_CLAMAV_HOST = "clamav"
DEFAULT_CLAMAV_PORT = 3310


class ClamAVConnectionError(Exception):
    """The clamd daemon was unreachable or the connection dropped mid-scan.

    Distinct from a positive malware detection: this signals a *transient*
    failure the scan worker should retry, never a terminal ``Scan_Failed``.
    """


@dataclass
class ScanResult:
    """Outcome of a single stream scan.

    ``infection`` is ``None`` on a clean result and the malware signature name
    (e.g. ``"Eicar-Test-Signature"``) on a positive detection.
    """

    clean: bool
    infection: Optional[str]


def _env_host() -> str:
    return os.environ.get("CLAMAV_HOST") or DEFAULT_CLAMAV_HOST


def _env_port() -> int:
    raw = os.environ.get("CLAMAV_PORT")
    if not raw:
        return DEFAULT_CLAMAV_PORT
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_CLAMAV_PORT


class ClamAVClient:
    """TCP client for a clamd sidecar.

    Host/port default to ``CLAMAV_HOST`` / ``CLAMAV_PORT`` from the environment,
    falling back to ``clamav:3310``. A fresh ``pyclamd`` socket is opened per
    call (the constructor itself never connects), so the client is cheap to
    create and holds no long-lived sockets.
    """

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        self.host = host if host is not None else _env_host()
        self.port = port if port is not None else _env_port()

    def _socket(self) -> "pyclamd.ClamdNetworkSocket":
        # Construction does not open a connection; ping()/scan_stream() do.
        return pyclamd.ClamdNetworkSocket(host=self.host, port=self.port)

    def ping(self) -> bool:
        """Return ``True`` when clamd answers a PING.

        Raises :class:`ClamAVConnectionError` if the TCP connection fails.
        """
        try:
            return bool(self._socket().ping())
        except pyclamd.ConnectionError as exc:  # subclass of OSError
            raise ClamAVConnectionError(
                f"clamd unreachable at {self.host}:{self.port}: {exc}"
            ) from exc

    def scan_stream(self, stream: IO[bytes]) -> ScanResult:
        """Stream ``stream`` to clamd's ``INSTREAM`` and classify the result.

        ``stream`` is any file-like object yielding bytes (e.g. an S3
        ``StreamingBody``); it is forwarded chunk-by-chunk without buffering to
        disk. Returns a :class:`ScanResult`; raises
        :class:`ClamAVConnectionError` on a connectivity/protocol failure.
        """
        try:
            result = self._socket().scan_stream(stream)
        except pyclamd.ConnectionError as exc:  # subclass of OSError
            raise ClamAVConnectionError(
                f"clamd scan failed at {self.host}:{self.port}: {exc}"
            ) from exc

        # pyclamd returns None when nothing was found.
        if not result:
            return ScanResult(clean=True, infection=None)

        # Otherwise: {filename: (status, reason)}. A FOUND status is a detection;
        # an ERROR status is a daemon/protocol problem we treat as transient.
        for status, reason in result.values():
            if status == "FOUND":
                return ScanResult(clean=False, infection=reason)
        raise ClamAVConnectionError(f"clamd reported a scan error: {result!r}")


__all__ = [
    "ClamAVClient",
    "ClamAVConnectionError",
    "ScanResult",
    "DEFAULT_CLAMAV_HOST",
    "DEFAULT_CLAMAV_PORT",
]
