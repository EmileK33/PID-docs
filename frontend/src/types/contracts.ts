// Shared contracts — verbatim transcription of §1.1 (Distilled Specification).
//
// [LOAD-BEARING] This file is a verbatim copy of the §1.1 TypeScript block and
// must stay in lockstep with backend/app/schemas/contracts.py. The API serves
// snake_case and the frontend consumes snake_case — do NOT rename fields to
// camelCase. Consumed by S1-F and every S3-* session.

// [CRITICAL BOUNDARY] — ML Inference Job Payload
// Written by: FastAPI (API layer at enqueue time)
// Read by: ML Worker, Ingest Worker (for job context), analytics emitters
interface MLInferenceJobPayload {
  storage_reference: string;       // S3 object key
  drawing_id: string;              // UUID
  user_id: string;                 // UUID — MUST be set at enqueue time by API layer
  page_range?: [number, number];   // optional, 1-based inclusive
}

// ML Inference Service Response
interface MLInferenceResult {
  drawing_id: string;
  symbols: DetectedSymbolResult[];
  tables: TableRegionResult[];
}

interface DetectedSymbolResult {
  entity_class_id: string;
  subtype: string;
  tag_label: string | null;
  confidence: number;              // 0.0–1.0
  bbox: BoundingBox;
  page_number: number;
}

interface TableRegionResult {
  bbox: BoundingBox;
  page_number: number;
  cells: TableCellResult[];
}

interface TableCellResult {
  row_label: string;
  column_label: string;
  bbox: BoundingBox;
  extracted_value: string;
}

interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

// Drawing Processing State Machine
type DrawingProcessingState =
  | 'Pending'
  | 'Queued'
  | 'Scanning'
  | 'Processing'
  | 'Complete'
  | 'Under_Review'
  | 'Failed'
  | 'Scan_Failed';

// Subscription Billing State
type BillingState = 'Active' | 'Grace' | 'Canceled';

// Tier IDs
type TierId = 'free' | 'pro' | 'team';

// User Role
type UserRole = 'user' | 'team_member' | 'team_admin';

// Symbol Source
type SymbolSource = 'ml' | 'manual';

// Correction Type
type CorrectionType = 'reclassify' | 'reject' | 'restore' | 'manual_add';

// Export Format
type ExportFormat = 'csv' | 'xlsx';

// Export Status
type ExportStatus = 'Queued' | 'Generating' | 'Complete' | 'Failed';

// Entity Classes (from FR-2 AC-2)
type EntityClassId =
  | 'pipe'
  | 'valve_gate'
  | 'valve_globe'
  | 'valve_ball'
  | 'valve_butterfly'
  | 'valve_check'
  | 'valve_control'
  | 'instrument';

// SSE Drawing Status Event (Redis pub/sub → client)
interface DrawingStatusSSEEvent {
  drawing_id: string;
  state: DrawingProcessingState;
  timestamp: string;               // ISO 8601 UTC
}

// Hash Check Request/Response
interface HashCheckRequest {
  sha256_hash: string;
  filename: string;
  size_bytes: number;
}

interface HashCheckResponse {
  allowed: boolean;
  drawing_id?: string;
}

// Symbols API Response (GET /drawings/{id}/symbols)
interface SymbolsPageResponse {
  symbols: SymbolRecord[];
  corrections_by_symbol_id: Record<string, CorrectionRecord[]>;
  total: number;
  limit: number;
  offset: number;
}

interface SymbolRecord {
  id: string;
  drawing_id: string;
  entity_class_id: EntityClassId;
  subtype: string;
  tag_label: string | null;
  confidence: number;
  bbox: BoundingBox;
  source: SymbolSource;
  rejected: boolean;
  page_number: number;
}

interface CorrectionRecord {
  id: string;
  detected_symbol_id: string | null;
  table_cell_id: string | null;
  user_id: string;
  correction_type: CorrectionType;
  new_class_id: EntityClassId | null;
  training_consent: boolean;
  created_at: string;
}

export type {
  MLInferenceJobPayload,
  MLInferenceResult,
  DetectedSymbolResult,
  TableRegionResult,
  TableCellResult,
  BoundingBox,
  DrawingProcessingState,
  BillingState,
  TierId,
  UserRole,
  SymbolSource,
  CorrectionType,
  ExportFormat,
  ExportStatus,
  EntityClassId,
  DrawingStatusSSEEvent,
  HashCheckRequest,
  HashCheckResponse,
  SymbolsPageResponse,
  SymbolRecord,
  CorrectionRecord,
};
