"""Magic-byte file-format detection (US-003-AC-3).

Format is decided from the *content* of the downloaded bytes — never from the
filename extension. This is the trust boundary: a ``.pdf`` extension on a file
that does not begin with ``%PDF`` must not be treated as a PDF.

Classification rules (§1.13 / US-003-AC-3):

* a file beginning with ``%PDF``        → ``"pdf"``
* a file beginning with ``AC`` (the AutoCAD DWG binary version header,
  e.g. ``AC1027`` for the 2013 format) → ``"dwg"``
* anything else                          → ``"unsupported"``
"""
from __future__ import annotations

from typing import Literal

DetectedFormat = Literal["pdf", "dwg", "unsupported"]

# PDF files start with the "%PDF" header (optionally "%PDF-1.x").
_PDF_MAGIC = b"%PDF"
# DWG files start with a 6-byte version tag "ACxxxx" (AC1027 = AutoCAD 2013,
# AC1032 = 2018, ...). The §-level rule keys only on the "AC" prefix.
_DWG_MAGIC = b"AC"


def detect_format(file_bytes: bytes) -> DetectedFormat:
    """Classify ``file_bytes`` by leading magic bytes.

    Returns ``"pdf"``, ``"dwg"`` or ``"unsupported"``.
    """
    if file_bytes.startswith(_PDF_MAGIC):
        return "pdf"
    if file_bytes.startswith(_DWG_MAGIC):
        # P1 STUB: enforce supported DWG version range per ops policy.
        # The 6-byte header (e.g. b"AC1027") encodes the AutoCAD format version;
        # a structured rejection of versions outside the ODA-supported range
        # belongs here. For P0, ODA handles whatever it handles, so any
        # "AC"-prefixed file is accepted as DWG.
        return "dwg"
    return "unsupported"


__all__ = ["detect_format", "DetectedFormat"]
