"""Shared contracts — Pydantic v2 mirror of §1.1.

[LOAD-BEARING] Field names, types, and ``Literal`` values are a verbatim mirror
of §1.1 and of ``frontend/src/types/contracts.ts``. The API serves ``snake_case``
and the frontend consumes ``snake_case`` — do NOT rename fields to ``camelCase``.

Any rename here cascades into S2-B, S2-C, S2-J, S2-D and the frontend. Consumed
by every API / service / worker session.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Literal type aliases
# ---------------------------------------------------------------------------
DrawingProcessingState = Literal[
    "Pending",
    "Queued",
    "Scanning",
    "Processing",
    "Complete",
    "Under_Review",
    "Failed",
    "Scan_Failed",
]

BillingState = Literal["Active", "Grace", "Canceled"]

TierId = Literal["free", "pro", "team"]

UserRole = Literal["user", "team_member", "team_admin"]

SymbolSource = Literal["ml", "manual"]

CorrectionType = Literal["reclassify", "reject", "restore", "manual_add"]

ExportFormat = Literal["csv", "xlsx"]

ExportStatus = Literal["Queued", "Generating", "Complete", "Failed"]

EntityClassId = Literal[
    "pipe",
    "valve_gate",
    "valve_globe",
    "valve_ball",
    "valve_butterfly",
    "valve_check",
    "valve_control",
    "instrument",
]


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
class BoundingBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


# ---------------------------------------------------------------------------
# ML inference job payload + result (CRITICAL BOUNDARY)
# ---------------------------------------------------------------------------
class MLInferenceJobPayload(BaseModel):
    """Written by the FastAPI API layer at enqueue time; read by ML/Ingest
    workers and analytics emitters."""

    storage_reference: str  # S3 object key
    drawing_id: str  # UUID
    user_id: str  # UUID — MUST be set at enqueue time by API layer
    page_range: Optional[tuple[int, int]] = None  # optional, 1-based inclusive


class DetectedSymbolResult(BaseModel):
    entity_class_id: str
    subtype: str
    tag_label: Optional[str] = None
    confidence: float  # 0.0–1.0
    bbox: BoundingBox
    page_number: int


class TableCellResult(BaseModel):
    row_label: str
    column_label: str
    bbox: BoundingBox
    extracted_value: str


class TableRegionResult(BaseModel):
    bbox: BoundingBox
    page_number: int
    cells: list[TableCellResult]


class MLInferenceResult(BaseModel):
    drawing_id: str
    symbols: list[DetectedSymbolResult]
    tables: list[TableRegionResult]


# ---------------------------------------------------------------------------
# SSE drawing status event (Redis pub/sub → client)
# ---------------------------------------------------------------------------
class DrawingStatusSSEEvent(BaseModel):
    drawing_id: str
    state: DrawingProcessingState
    timestamp: str  # ISO 8601 UTC


# ---------------------------------------------------------------------------
# Hash check request / response
# ---------------------------------------------------------------------------
class HashCheckRequest(BaseModel):
    sha256_hash: str
    filename: str
    size_bytes: int


class HashCheckResponse(BaseModel):
    allowed: bool
    drawing_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Symbols API response (GET /drawings/{id}/symbols)
# ---------------------------------------------------------------------------
class SymbolRecord(BaseModel):
    id: str
    drawing_id: str
    entity_class_id: EntityClassId
    subtype: str
    tag_label: Optional[str] = None
    confidence: float
    bbox: BoundingBox
    source: SymbolSource
    rejected: bool
    page_number: int


class CorrectionRecord(BaseModel):
    id: str
    detected_symbol_id: Optional[str] = None
    table_cell_id: Optional[str] = None
    user_id: str
    correction_type: CorrectionType
    new_class_id: Optional[EntityClassId] = None
    training_consent: bool
    created_at: str


class SymbolsPageResponse(BaseModel):
    symbols: list[SymbolRecord]
    corrections_by_symbol_id: dict[str, list[CorrectionRecord]] = Field(default_factory=dict)
    total: int
    limit: int
    offset: int


__all__ = [
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
