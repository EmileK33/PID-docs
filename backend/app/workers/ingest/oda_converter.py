"""DWG→PDF conversion via the ODA File Converter in an isolated Docker sandbox.

Security posture (§1.13 P0 — DWG parsing in isolated Docker sandbox):

* **No network egress** — ``docker run --network none``.
* **Non-root** — ``--user 1000:1000`` (matches the ``odauser`` UID baked into
  ``ops/oda-sandbox/Dockerfile``).
* **Read-only host filesystem** — ``--read-only`` makes the container root
  filesystem read-only; the *only* writable paths are the bind-mounted work
  directory (``-v <workdir>:/work``) and an in-memory ``--tmpfs /tmp``. The host
  filesystem is never otherwise mounted, and the Docker socket is never mounted.
* **No privilege escalation** — ``--privileged`` is never used.

The ODA binary is **never** executed directly on the host process — only inside
the sandbox container (technology constraint §1.8).

License monitoring (§1.7 / US-003-AC-7): ``ODA_LICENSE_EXPIRY_DATE`` is checked
at module import (worker startup) and again at the start of each conversion. A
``WARNING`` is logged when the license expires within 30 days, and a ``WARNING``
is logged (without blocking) when the env var is absent.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from datetime import date
from typing import List, Optional

from app.config import settings

logger = logging.getLogger("pid.workers.ingest.oda")

# ── Configuration ──────────────────────────────────────────────────────────
# Image built from ops/oda-sandbox/Dockerfile (owned by S0-A). Overridable via
# env for deploy environments that tag the image differently.
ODA_SANDBOX_IMAGE = os.environ.get("ODA_SANDBOX_IMAGE", "pid-oda-sandbox:latest")

# Mount point of the work directory inside the sandbox (matches the Dockerfile's
# VOLUME/WORKDIR /work).
_CONTAINER_WORKDIR = "/work"
_CONTAINER_INPUT_DIR = "/work/in"
_CONTAINER_OUTPUT_DIR = "/work/out"

# Non-root UID:GID declared by ops/oda-sandbox/Dockerfile (USER 1000:1000).
_SANDBOX_USER = "1000:1000"

# ODA File Converter CLI positional args:
#   <InputDir> <OutputDir> <OutputVersion> <OutputType> <Recurse> <Audit> [filter]
_ODA_OUTPUT_VERSION = "ACAD2018"
_ODA_OUTPUT_TYPE = "PDF"
_ODA_RECURSE = "0"
_ODA_AUDIT = "1"
_ODA_INPUT_FILTER = "*.DWG"

# Conversion wall-clock budget. Generous enough for complex DWGs but bounded so
# a hung converter cannot pin a worker forever.
ODA_TIMEOUT_SECONDS = 600

# License-expiry alert threshold (§1.7 / US-003-AC-7).
LICENSE_ALERT_THRESHOLD_DAYS = 30


class ODAConversionError(RuntimeError):
    """Raised when the ODA sandbox fails to launch or the conversion fails.

    Treated by the ingest task as a *business* failure → ``Scanning → Failed``
    (no automatic Celery retry); the user re-submits via S2-B.
    """


# ── License expiry monitoring (US-003-AC-7) ─────────────────────────────────
_UNSET = object()


def check_oda_license_expiry(expiry_date_str: object = _UNSET, *, today: Optional[date] = None) -> None:
    """Log a ``WARNING`` if the ODA license expires within 30 days, or is absent.

    With no argument the value is read from ``settings.ODA_LICENSE_EXPIRY_DATE``.
    An absent (``None``/empty) value logs a warning and skips the check — it does
    NOT block conversion. A malformed value is logged and skipped. Never raises.
    """
    if expiry_date_str is _UNSET:
        expiry_date_str = settings.ODA_LICENSE_EXPIRY_DATE
    today = today or date.today()

    if not expiry_date_str:
        logger.warning(
            "ODA_LICENSE_EXPIRY_DATE absent; 30-day license expiry alerting "
            "disabled. Conversion not blocked."
        )
        return

    try:
        expiry = date.fromisoformat(str(expiry_date_str))
    except ValueError:
        logger.warning(
            "ODA_LICENSE_EXPIRY_DATE=%r is not a valid YYYY-MM-DD date; "
            "skipping expiry check.",
            expiry_date_str,
        )
        return

    days_remaining = (expiry - today).days
    if days_remaining <= LICENSE_ALERT_THRESHOLD_DAYS:
        logger.warning(
            "ODA File Converter license expires in %d day(s) on %s "
            "(within the %d-day alert threshold) — renew before it lapses.",
            days_remaining,
            expiry.isoformat(),
            LICENSE_ALERT_THRESHOLD_DAYS,
        )


# Run the expiry check once at worker startup (module import).
check_oda_license_expiry()


# ── Docker sandbox command construction ─────────────────────────────────────
def _build_oda_command(host_workdir: str) -> List[str]:
    """Build the ``docker run`` command for one sandboxed conversion.

    Encodes every §1.13 P0 security requirement: no network, non-root,
    read-only root filesystem, a writable bind-mounted work dir, a tmpfs /tmp,
    and no ``--privileged`` / Docker-socket mount.
    """
    return [
        "docker",
        "run",
        "--rm",
        # No network egress.
        "--network",
        "none",
        # Non-root user (matches the sandbox image's odauser).
        "--user",
        _SANDBOX_USER,
        # Read-only container root filesystem.
        "--read-only",
        # Writable scratch (in-memory) for /tmp only.
        "--tmpfs",
        "/tmp",
        # Drop all Linux capabilities; defence in depth.
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        # The ONLY host path exposed to the container — the per-job work dir.
        "-v",
        f"{host_workdir}:{_CONTAINER_WORKDIR}",
        ODA_SANDBOX_IMAGE,
        # Entry command + ODA File Converter positional args.
        settings.ODA_CONVERTER_PATH,
        _CONTAINER_INPUT_DIR,
        _CONTAINER_OUTPUT_DIR,
        _ODA_OUTPUT_VERSION,
        _ODA_OUTPUT_TYPE,
        _ODA_RECURSE,
        _ODA_AUDIT,
        _ODA_INPUT_FILTER,
    ]


def _run_oda_subprocess(cmd: List[str]) -> "subprocess.CompletedProcess[bytes]":
    """Execute the sandboxed conversion. Seam for tests to patch."""
    return subprocess.run(  # noqa: S603 — fixed command, no shell.
        cmd,
        capture_output=True,
        timeout=ODA_TIMEOUT_SECONDS,
        check=False,
    )


def _read_single_pdf(output_dir: str) -> Optional[bytes]:
    """Return the bytes of the single PDF the converter wrote, or ``None``."""
    for name in sorted(os.listdir(output_dir)):
        if name.lower().endswith(".pdf"):
            with open(os.path.join(output_dir, name), "rb") as fh:
                return fh.read()
    return None


def convert_dwg_to_pdf(dwg_bytes: bytes, drawing_id: str) -> bytes:
    """Convert ``dwg_bytes`` to PDF inside the ODA sandbox and return PDF bytes.

    Raises :class:`ODAConversionError` if the sandbox cannot be launched, the
    converter exits non-zero, or no PDF is produced.
    """
    # Re-assert license monitoring at conversion time (US-003-AC-7).
    check_oda_license_expiry()

    workdir = tempfile.mkdtemp(prefix=f"oda-{drawing_id}-")
    try:
        input_dir = os.path.join(workdir, "in")
        output_dir = os.path.join(workdir, "out")
        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        with open(os.path.join(input_dir, "drawing.dwg"), "wb") as fh:
            fh.write(dwg_bytes)

        cmd = _build_oda_command(workdir)
        try:
            result = _run_oda_subprocess(cmd)
        except FileNotFoundError as exc:
            # Docker binary missing / sandbox cannot launch.
            raise ODAConversionError(f"failed to launch ODA sandbox: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ODAConversionError(
                f"ODA conversion timed out after {ODA_TIMEOUT_SECONDS}s"
            ) from exc

        if result.returncode != 0:
            stderr = (result.stderr or b"").decode("utf-8", "replace")[:2000]
            raise ODAConversionError(
                f"ODA File Converter exited with code {result.returncode}: {stderr}"
            )

        pdf_bytes = _read_single_pdf(output_dir)
        if not pdf_bytes:
            raise ODAConversionError("ODA File Converter produced no PDF output")
        return pdf_bytes
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


__all__ = [
    "convert_dwg_to_pdf",
    "check_oda_license_expiry",
    "ODAConversionError",
    "ODA_SANDBOX_IMAGE",
    "LICENSE_ALERT_THRESHOLD_DAYS",
]
