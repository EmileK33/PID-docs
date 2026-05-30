---

#### S1-C — Storage & Hash Utilities

**Phase 1 | Infrastructure | Needs: S0-A, S0-B**

##### Objective

Provide the shared S3 client, pre-signed URL generator, SHA-256 hashing utilities, and file-hash blocklist lookup that all upload-path sessions (drawings API, ingest worker, export worker, GDPR worker) depend on.

##### Scope

P0 MVP. All exports in this session are P0. No P1 work in this session.

##### Technology constraints

- **AWS S3 / S3-compatible** (per §1.8): use `boto3` (Python). Use IAM role auth by default; fall back to `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` if present.
- Pre-signed URLs **must** expire in 15 minutes (`PRESIGNED_URL_EXPIRY_SECONDS` env, default `900`) — hard security constraint.
- SSE-S3 or SSE-KMS encryption required on all `PutObject` calls (`ServerSideEncryption='AES256'` minimum). Buckets must never be publicly accessible.
- SHA-256 hashing must use Python stdlib `hashlib.sha256` — stream chunks (do not load entire file into memory).
- Blocklist lookup uses PostgreSQL `file_hash_blocklist` table (model exported by S1-A is **NOT** available yet at this session's prerequisite tier — see Critical Implementation Notes; this session uses raw SQL via SQLAlchemy `text()` against table name `file_hash_blocklist`).
- Do **NOT** use the AWS CLI subprocess, `aws-sdk-js`, `s3fs`, or `smart_open` — they bypass our IAM/SSE configuration discipline.

##### Performance targets

- Pre-signed URL expiry = 15 minutes (hard constraint, §1.9).
- SHA-256 streaming hash must not exceed memory proportional to chunk size (8 MiB chunk recommended); a 100 MB file (max upload per `MAX_UPLOAD_SIZE_BYTES`) must hash without loading the whole file into RAM.
- No SLA owned beyond the 15-min expiry constraint — see downstream sessions S2-B (drawings API), S2-H (ingest worker).

##### Owned files

- `backend/app/storage/__init__.py`
- `backend/app/storage/s3_client.py`
- `backend/app/storage/presigned.py`
- `backend/app/storage/hashing.py`
- `backend/app/storage/blocklist.py`
- `tests/integration/test_storage.py`

##### Read-only imports

- **From S0-A**:
  - `backend/app/config.py` — settings object exposing `S3_BUCKET_NAME`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `PRESIGNED_URL_EXPIRY_SECONDS`, `MAX_UPLOAD_SIZE_BYTES`.
  - `backend/app/db/session.py` — DB session factory (for blocklist queries).
  - `backend/app/schemas/contracts.py` — `HashCheckRequest`, `HashCheckResponse` pydantic models.
- **From S0-B**:
  - `tests/integration/conftest.py` — pytest fixtures.
  - `tests/integration/fixtures/db.py` — DB fixture.
  - `tests/integration/fixtures/s3.py` — moto/localstack-backed S3 fixture.

##### Do not touch

- `backend/app/main.py` (entry point — S0-A)
- `backend/app/api/routers/*` (router files — S0-A stubs / S2-* owners)
- `backend/app/db/models/*` (owned by S1-A; this session uses raw SQL not ORM models)
- `backend/app/auth/*` (S1-B)
- `backend/app/redis/*` (S1-D)
- `backend/app/analytics/*` (S1-E)
- All worker files under `backend/app/workers/*` except this session does not own any
- All files owned by S1-A, S1-B, S1-D, S1-E, S1-F

##### Architecture context

From §1.8 Technology Stack:

> **Object Storage** | AWS S3-compatible | Pre-signed URL pattern, IAM role scoping, SSE encryption, lifecycle policies; client-direct upload pattern avoids API byte-proxy

From §1.7 Third-Party Dependencies:

> **AWS S3 / S3-Compatible** | IAM role (ML workers); pre-signed URLs (clients, 15-min expiry) | Standard S3 quotas | Never publicly accessible; SSE-S3 or SSE-KMS encryption required; no CDN for export files (confidential)

From §1.4 Critical Ordering Rules:

> 1. **Hash check before pre-signed URL issuance.** "Client calls `POST /drawings/hash-check` with `{sha256_hash, filename, size_bytes}`. Server checks `FILE_HASH_BLOCKLIST`. If the hash is present, returns `409 Conflict` — no Drawing record is created, no S3 URL is issued." A `POST /drawings` without a valid prior hash-check pass returns `400`.
>
> 2. **Pre-signed URL issued only after hash-check pass.** "The upload flow enforces FR-17 AC-2 (no blocked file byte reaches S3) through a mandatory hash pre-check before pre-signed URL issuance."
>
> 3. **Server-side SHA-256 re-verification after storage.** "Ingest Worker performs a server-side SHA-256 verification of the stored object against the client-supplied hash... hash is also checked a second time against the blocklist to handle newly-added entries between steps 3 and 7."

From §1.2 Database Schema (relevant tables this session queries):

```sql
CREATE TABLE file_hash_blocklist (
  sha256_hash  VARCHAR PRIMARY KEY,
  blocked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reason       VARCHAR NOT NULL
);

CREATE TABLE stored_file (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  bucket       VARCHAR NOT NULL,
  object_key   VARCHAR NOT NULL,
  sha256_hash  VARCHAR NOT NULL,
  file_type    VARCHAR NOT NULL,
  size_bytes   BIGINT NOT NULL,
  CONSTRAINT stored_file_object_key_unique UNIQUE (bucket, object_key)
);

CREATE INDEX idx_stored_file_hash ON stored_file(sha256_hash);
```

From §1.1 Shared Contracts:

```typescript
interface HashCheckRequest {
  sha256_hash: string;
  filename: string;
  size_bytes: number;
}
interface HashCheckResponse {
  allowed: boolean;
  drawing_id?: string;
}
```

##### User stories and acceptance criteria

This is an infrastructure session — no user stories are implemented directly. It exists to satisfy the cross-cutting requirements of US-003 (file upload validation, two-gate blocklist), US-005 (GDPR object deletion), US-016 (export pre-signed download URL), and US-017 (async export storage). All ACs are technical, derived from §1.4 ordering rules and §1.7/§1.8/§1.9 constraints.

##### UX and design specification

N/A — backend infrastructure session, no frontend component.

##### Critical implementation notes

- **Pre-signed URL TTL is exactly `PRESIGNED_URL_EXPIRY_SECONDS` (default 900).** Quoting §1.9: "Pre-signed S3 URL expiry | 15 minutes | Hard constraint (security)". The generator must not accept a caller-supplied override that exceeds the env value.
- **SSE on every PutObject.** Per §1.7: "SSE-S3 or SSE-KMS encryption required". Both direct `put_object` calls and pre-signed PUT URLs must enforce `ServerSideEncryption=AES256`. For pre-signed PUTs, set `ServerSideEncryption` in `Params` so the URL signature commits to the header.
- **Streaming hash, not full-buffer.** `hashlib.sha256` updated in 8 MiB chunks from a file-like / iterator. Loading a 100 MB file into memory is a silent perf regression that will appear to work in dev.
- **Blocklist lookup is a hot path.** Use indexed PK lookup (`SELECT 1 FROM file_hash_blocklist WHERE sha256_hash = :h`). Return `bool`. Do not return the row payload — consumers only need allow/deny.
- **Hash comparison is case-insensitive on the hex form but stored lowercase.** Normalize all incoming hashes to lowercase before lookup or insert. Quoted hex from `hashlib.hexdigest()` is already lowercase — clients may send uppercase; downcase on entry.
- **The `file_hash_blocklist` table is created by S1-A migration 0001.** This session must NOT import any SQLAlchemy model from `backend/app/db/models/` — those files belong to S1-A and may not exist at session-start in some merge orders. Use `sqlalchemy.text()` with the bare table name. This is a deliberate intra-wave decoupling.
- **Object key convention** (load-bearing for S2-B and S2-H): drawings stored at `drawings/{drawing_id}/original.{ext}`; exports at `exports/{export_id}.{csv|xlsx}`. Provide helpers `drawing_object_key(drawing_id, ext)` and `export_object_key(export_id, ext)` so downstream sessions don't reinvent.
- **No public-read ACL.** Never set `ACL='public-read'` on any object. Pre-signed GET is the only download path. A silent failure mode: setting public ACL "for convenience" — exports contain confidential drawings.
- **Bucket must exist; do not auto-create at runtime.** S3 bucket creation is infra/IaC concern, not application concern. If the bucket is missing, surface the boto3 error.
- **Re-verification helper signature** consumed by S2-H ingest worker: `verify_object_sha256(bucket, key, expected_hash) -> bool` — streams the object body through `hashlib.sha256` and compares; never trusts S3 ETag (it's not always SHA-256 with multipart uploads).

##### Mocking contract

Backend infra session — defines contracts, consumed by S2-B (drawings API), S2-D (export API), S2-H (ingest worker), S2-K (export worker), S2-L (GDPR worker).

This session itself depends only on external S3 (mocked via `moto` in tests) and PostgreSQL (real, via `tests/integration/fixtures/db.py`). No internal-event contracts consumed.

##### Acceptance criteria checklist

- [ ] `is_hash_blocked(sha256_hash)` returns `True` when hash exists in `file_hash_blocklist`, `False` otherwise [tech, §1.4 rule 1]
- [ ] `is_hash_blocked` normalizes input to lowercase before query [tech, §1.4 rule 1]
- [ ] `generate_presigned_put_url(bucket, key, content_length, content_type)` returns a URL with expiry == `PRESIGNED_URL_EXPIRY_SECONDS` [tech, §1.9 hard constraint]
- [ ] `generate_presigned_put_url` signature includes `ServerSideEncryption=AES256` in signed params [tech, §1.7]
- [ ] `generate_presigned_get_url(bucket, key)` returns a URL with expiry == `PRESIGNED_URL_EXPIRY_SECONDS` [tech, §1.9]
- [ ] Pre-signed PUT URL cannot be used after expiry (simulated; verifies expiry param is propagated to boto3) [tech, §1.9]
- [ ] `compute_sha256_stream(file_like, chunk_size=8MiB)` returns correct lowercase hex digest for known input [tech]
- [ ] `compute_sha256_stream` does not load entire file into memory (chunked iteration verified via mock read tracking) [tech]
- [ ] `verify_object_sha256(bucket, key, expected_hash)` returns `True` when stored object SHA-256 matches `expected_hash` [tech, §1.4 rule 3]
- [ ] `verify_object_sha256` returns `False` on mismatch (does not raise) [tech, §1.4 rule 3]
- [ ] `verify_object_sha256` normalizes `expected_hash` to lowercase before comparison [tech]
- [ ] `drawing_object_key(drawing_id, ext)` returns `drawings/{drawing_id}/original.{ext}` [tech, load-bearing for S2-B/S2-H]
- [ ] `export_object_key(export_id, ext)` returns `exports/{export_id}.{ext}` [tech, load-bearing for S2-D/S2-K]
- [ ] `put_object(bucket, key, body, content_type)` direct upload sets `ServerSideEncryption=AES256` [tech, §1.7]
- [ ] `delete_object(bucket, key)` removes the object (used by GDPR worker) [tech]
- [ ] No method on `s3_client` ever sets `ACL='public-read'` or any public ACL [tech, §1.7 — no publicly accessible]
- [ ] S3 client falls back to IAM role when `AWS_ACCESS_KEY_ID` env unset [tech, §1.12]
- [ ] S3 client uses explicit credentials when both env vars set [tech, §1.12]

##### Independent Test

- **Test file path** (TDD — written first, must fail before implementation): `tests/integration/test_storage.py`
- **Exact CI command**: `cd backend && poetry run pytest ../tests/integration/test_storage.py -v`
- **AC → assertion mapping**:
  - blocked-hash returns True → `it("test_is_hash_blocked_returns_true_when_present")`
  - blocked-hash returns False → `it("test_is_hash_blocked_returns_false_when_absent")`
  - lowercase normalization on lookup → `it("test_is_hash_blocked_normalizes_uppercase_input")`
  - presigned PUT expiry → `it("test_presigned_put_url_uses_configured_expiry")`
  - presigned PUT SSE → `it("test_presigned_put_url_signs_sse_aes256")`
  - presigned GET expiry → `it("test_presigned_get_url_uses_configured_expiry")`
  - expiry propagation → `it("test_presigned_put_expiry_param_propagated_to_boto3")`
  - SHA-256 known input → `it("test_compute_sha256_stream_known_value")`
  - SHA-256 streaming → `it("test_compute_sha256_stream_chunked_no_full_load")`
  - verify match → `it("test_verify_object_sha256_match")`
  - verify mismatch → `it("test_verify_object_sha256_mismatch_returns_false")`
  - verify lowercase → `it("test_verify_object_sha256_lowercase_normalization")`
  - drawing key fmt → `it("test_drawing_object_key_format")`
  - export key fmt → `it("test_export_object_key_format")`
  - direct put SSE → `it("test_put_object_sets_sse_aes256")`
  - delete object → `it("test_delete_object_removes_object")`
  - no public ACL → `it("test_no_method_sets_public_acl")`
  - IAM fallback → `it("test_s3_client_iam_role_fallback")`
  - explicit creds → `it("test_s3_client_uses_explicit_credentials")`
- **Fixtures / test doubles**: `moto.mock_aws` for S3 (already wired in `tests/integration/fixtures/s3.py`); real PostgreSQL from `tests/integration/fixtures/db.py` with `file_hash_blocklist` table created via raw `CREATE TABLE IF NOT EXISTS` in test setup (does NOT depend on S1-A migrations being merged — test is self-contained).
- **Pre-conditions**: `DATABASE_URL`, `S3_BUCKET_NAME=test-bucket`, `S3_REGION=us-east-1`, `PRESIGNED_URL_EXPIRY_SECONDS=900` set in test env. Test creates the `file_hash_blocklist` table inline if missing so the test passes in true isolation (this session's PR alone, S1-A not yet merged).
- **Isolation rule**: Test passes when only this session's PR is merged. The `file_hash_blocklist` table schema is duplicated in test setup as a CREATE-IF-NOT-EXISTS — when S1-A merges later with the canonical migration, both definitions are compatible (same columns, same PK).

##### Checkpoint

- **Observable outcome**: A developer can `from backend.app.storage import generate_presigned_put_url, is_hash_blocked, compute_sha256_stream, verify_object_sha256` and obtain a working 15-minute SSE-encrypted pre-signed URL against the configured bucket; a hash inserted into `file_hash_blocklist` is detected by `is_hash_blocked`.
- **Shippability claim**: this PR is independently mergeable to main even if no other session in the same wave has merged.

##### Output and handoff

- `backend/app/storage/blocklist.py::is_hash_blocked(sha256_hash: str) -> bool` [LOAD-BEARING] — consumed by S2-B (hash-check endpoint), S2-H (ingest re-check)
- `backend/app/storage/presigned.py::generate_presigned_put_url(bucket: str, key: str, content_length: int, content_type: str) -> str` [LOAD-BEARING] — consumed by S2-B
- `backend/app/storage/presigned.py::generate_presigned_get_url(bucket: str, key: str) -> str` [LOAD-BEARING] — consumed by S2-D, S2-K (export download)
- `backend/app/storage/hashing.py::compute_sha256_stream(file_like, chunk_size: int = 8*1024*1024) -> str` — consumed by S2-H
- `backend/app/storage/hashing.py::verify_object_sha256(bucket: str, key: str, expected_hash: str) -> bool` [LOAD-BEARING] — consumed by S2-H (§1.4 rule 3)
- `backend/app/storage/s3_client.py::put_object(bucket, key, body, content_type) -> None` — consumed by S2-K, S2-J
- `backend/app/storage/s3_client.py::delete_object(bucket, key) -> None` — consumed by S2-L (GDPR)
- `backend/app/storage/s3_client.py::get_s3_client() -> boto3.client` — consumed by any worker needing raw client
- `backend/app/storage/presigned.py::drawing_object_key(drawing_id: str, ext: str) -> str` [LOAD-BEARING] — consumed by S2-B, S2-H
- `backend/app/storage/presigned.py::export_object_key(export_id: str, ext: str) -> str` [LOAD-BEARING] — consumed by S2-D, S2-K

---

```json
{
  "test": { "cmd": "cd backend && poetry run pytest ../tests/integration/test_storage.py -v", "file": "tests/integration/test_storage.py" },
  "checkpoint": "Developers can import storage helpers to obtain a 15-minute SSE-encrypted pre-signed URL and check a SHA-256 hash against the file_hash_blocklist table.",
  "manualAcs": [],
  "exports": [
    { "kind": "function", "name": "is_hash_blocked", "shape": "(sha256_hash: str) -> bool" },
    { "kind": "function", "name": "generate_presigned_put_url", "shape": "(bucket: str, key: str, content_length: int, content_type: str) -> str" },
    { "kind": "function", "name": "generate_presigned_get_url", "shape": "(bucket: str, key: str) -> str" },
    { "kind": "function", "name": "compute_sha256_stream", "shape": "(file_like: IO[bytes], chunk_size: int = 8388608) -> str" },
    { "kind": "function", "name": "verify_object_sha256", "shape": "(bucket: str, key: str, expected_hash: str) -> bool" },
    { "kind": "function", "name": "put_object", "shape": "(bucket: str, key: str, body: bytes | IO[bytes], content_type: str) -> None" },
    { "kind": "function", "name": "delete_object", "shape": "(bucket: str, key: str) -> None" },
    { "kind": "function", "name": "get_s3_client", "shape": "() -> Any" },
    { "kind": "function", "name": "drawing_object_key", "shape": "(drawing_id: str, ext: str) -> str" },
    { "kind": "function", "name": "export_object_key", "shape": "(export_id: str, ext: str) -> str" },
    { "kind": "module", "name": "backend/app/storage", "shape": "backend/app/storage/__init__.py" }
  ]
}
```