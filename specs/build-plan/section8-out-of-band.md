# Out-of-Band Validation Tasks — PID Analyzer

---

## OOB-01 — ODA File Converter: License Procurement + 50-File Prototype

**Name**: ODA File Converter commercial license obtained and DWG conversion success rate validated on 50 representative drawings.

**Gates**: Any session implementing the Ingest Worker DWG-to-raster/PDF conversion path; any session implementing the DWG upload validation flow (version range check, raster output verification).

**Pass condition**:
- Commercial ODA File Converter license is in hand with a confirmed expiry date (for `ODA_LICENSE_EXPIRY_DATE` env var and 30-day alert).
- A test harness running ODA File Converter in the isolated Docker sandbox (no network egress, non-root, read-only filesystem) successfully converts ≥90% of 50 real-world DWGs spanning AutoCAD versions 2010–2024 from ≥3 distinct companies to raster/PDF output without subprocess hang or corrupt output.
- `ODA_CONVERTER_PATH` resolves to a working binary in the Docker image that will be used in engineering.

**Fail condition**:
- License is not obtainable, is cost-prohibitive, or trial expires before launch window.
- Conversion success rate on the 50-file prototype is below the team's accepted threshold (e.g., <80% success on real complex DWGs).
- ODA binary cannot run in the isolated sandbox constraints (network-off, non-root, read-only FS).

**Fallback architecture**:
- Drop native DWG support from P0; accept DXF uploads only, parsed via `ezdxf` (Python, open-source, no license dependency).
- Change session briefs for: Ingest Worker session (remove ODA subprocess path; implement ezdxf DXF-to-raster), Upload Validation session (remove DWG version range check; add DXF format detection), and the File Upload UI session (remove `.dwg` from accepted types; add `.dxf`; update copy).
- DWG support becomes a P1 item dependent on license resolution.

---

## OOB-02 — AWS S3 Bucket Provisioning and IAM Role Configuration

**Name**: S3 bucket provisioned with correct encryption, ACL policy, and IAM roles for pre-signed URL generation and worker access.

**Gates**: Upload flow session (pre-signed URL issuance); Ingest Worker session (post-upload hash verification, object read); ML Worker session (model weights fetch via `ML_MODEL_S3_KEY`); Export Worker session (export file write and pre-signed URL for download).

**Pass condition**:
- S3 bucket exists in the configured `DATA_REGION` with:
  - SSE-S3 or SSE-KMS encryption enabled.
  - All public access blocked (no public ACLs or bucket policy permitting public reads).
  - An IAM role usable by ECS Fargate task definitions with `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on the bucket.
  - Pre-signed URL generation (15-minute expiry, `PRESIGNED_URL_EXPIRY_SECONDS=900`) verified by generating a test URL and confirming it expires correctly.
- A separate path/prefix for ML model weights is readable by the ML Worker IAM role, and `ML_MODEL_S3_KEY` resolves to a test object.
- `S3_BUCKET_NAME` and `S3_REGION` env vars are populated in the target deployment environment.

**Fail condition**:
- Bucket creation fails (account quota, region unavailability).
- IAM role cannot be attached to ECS task definitions.
- Pre-signed URLs are either publicly readable without expiry or fail to generate.

**Fallback architecture**:
- Use a local MinIO instance for development/staging only; production is blocked until AWS S3 is available.
- No alternative architecture for production — S3-compatible object storage is architecturally irreversible per §1.8.

---

## OOB-03 — PostgreSQL (RDS/Aurora) Instance Provisioning

**Name**: PostgreSQL instance provisioned, `pgcrypto` extension available, RLS supported, and connection URI verified.

**Gates**: All backend API sessions; all worker sessions; any session writing to or reading from the database.

**Pass condition**:
- A PostgreSQL instance (RDS or Aurora PostgreSQL) is running in the target environment.
- `CREATE EXTENSION IF NOT EXISTS "pgcrypto"` executes without error (required for `gen_random_uuid()`).
- RLS (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`) executes without error.
- `PARTITION BY RANGE` on `audit_log` executes without error and at least the current month + 2 forward months of partitions (`audit_log_YYYY_MM`) are created.
- PgBouncer is deployed as connection pooler, and the `DATABASE_URL` in the deployment environment routes through PgBouncer.
- All Alembic migrations run cleanly against the provisioned instance.

**Fail condition**:
- `pgcrypto` unavailable (e.g., managed service restriction).
- RLS not supported in the selected PostgreSQL version.
- PgBouncer fails to pool connections at projected concurrency.
- Alembic migration against a fresh instance fails.

**Fallback architecture**:
- If `pgcrypto` is unavailable: replace `gen_random_uuid()` with application-layer UUID generation (`uuid.uuid4()` in Python); update all session briefs that touch schema creation.
- If RLS is unavailable: enforce ownership exclusively in FastAPI middleware (spec already states "enforce ownership server-side in middleware as primary control"); remove `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` from migration scripts.

---

## OOB-04 — Redis (ElastiCache) Instance Provisioning

**Name**: Redis instance provisioned, pub/sub functional, and connection URI verified.

**Gates**: Celery worker sessions (broker); SSE session (`drawing:status:{drawing_id}` pub/sub); subscription flag cache session (`subscription:flags:{user_id}`); brute-force lockout session (`brute_force:{email}` TTL key).

**Pass condition**:
- A Redis instance is running and reachable from ECS Fargate task definitions.
- `SUBSCRIBE` / `PUBLISH` on a test channel confirms pub/sub working.
- `SET key value EX 900` / `GET key` confirms TTL-based key expiry.
- `CELERY_BROKER_URL` (or fallback `REDIS_URL`) is populated and a test Celery worker can connect and receive a task.
- `REDIS_URL` env var is populated in all deployment environments.

**Fail condition**:
- ElastiCache instance unavailable in region.
- Pub/sub blocked by network ACL or security group between ECS tasks and ElastiCache.
- Celery cannot connect to the broker URL.

**Fallback architecture**:
- For development/staging: local Redis container acceptable.
- For production: no alternative broker without requiring worker session rewrites — Redis is architecturally irreversible per §1.8 (three-in-one dependency). Production is blocked until resolved.

---

## OOB-05 — Supabase Auth Self-Hosted Instance Setup

**Name**: Supabase Auth self-hosted instance running with Google OAuth provider configured, JWT RS256 key pair generated, and `admin.signOut(userId)` API confirmed functional.

**Gates**: Auth sessions (registration, login, OAuth, password reset, logout, session invalidation); any session validating JWTs via `JWT_RS256_PUBLIC_KEY`; password reset session (requires `admin.signOut(userId)`).

**Pass condition**:
- Supabase self-hosted instance is running and reachable.
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are populated in deployment environment.
- A test user can register, receive a verification email (forwarded via SendGrid or SMTP), and log in.
- Google OAuth provider is configured with the Google OAuth credentials from OOB-06; a test OAuth flow completes successfully.
- JWT RS256 key pair is generated; `JWT_RS256_PUBLIC_KEY` (PEM) is populated in deployment environment; a test JWT validates against it.
- `supabase.auth.admin.signOut(userId)` API call on a test user successfully invalidates all sessions.
- Brute-force: 5 failed login attempts result in the expected lockout behavior (this is Redis-based per §1.11, but confirmed through integrated test).

**Fail condition**:
- Self-hosted Supabase cannot be provisioned in the target infrastructure.
- `admin.signOut(userId)` is not available on the self-hosted version.
- Google OAuth callback URL is rejected by Google (requires OOB-06 to complete first).

**Fallback architecture**:
- Switch to Auth0 (managed) as noted in spec §1.7; update all session briefs touching auth to use Auth0 SDK instead of Supabase Auth client; `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` env vars replaced with Auth0 equivalents; `admin.signOut(userId)` replaced with Auth0 Management API user session revocation.

---

## OOB-06 — Google OAuth 2.0 Credentials

**Name**: Google Cloud project created, OAuth 2.0 client ID and secret issued, redirect URIs approved for all target environments.

**Gates**: OAuth login session; Supabase Auth Google provider configuration (OOB-05 depends on this).

**Pass condition**:
- Google Cloud Console project exists with OAuth 2.0 credentials (Web Application type) issued.
- Client ID and client secret are available for injection into Supabase Auth Google provider configuration.
- Redirect URIs for `staging` and `production` environments are registered and approved (no "redirect_uri_mismatch" on test auth code exchange).
- OAuth consent screen is configured (app name, logo, privacy policy URL, scopes: `openid`, `email`, `profile`).

**Fail condition**:
- OAuth consent screen is in "Testing" mode and target test users are not added (blocks real user onboarding).
- Redirect URIs rejected or not yet approved.
- Google app requires verification review that blocks launch timeline.

**Fallback architecture**:
- Disable Google OAuth at P0 launch; email/password only. Update the auth session brief to remove the Google OAuth button and the account-link flow. Post-verification, re-enable as a zero-downtime feature flag.

---

## OOB-07 — Stripe Account + Test/Live Keys + Checkout + Customer Portal Activation

**Name**: Stripe account activated, test and live API keys issued, Stripe Checkout and Customer Portal enabled, webhook endpoint registered, and required event subscriptions confirmed.

**Gates**: Subscription/billing session (Checkout, Customer Portal, webhook handler); grace period email session; `subscription_upgraded` / `subscription_downgraded` analytics event session.

**Pass condition**:
- `STRIPE_SECRET_KEY` (`sk_test_*` for staging, `sk_live_*` for production) and `STRIPE_WEBHOOK_SECRET` (`whsec_*`) are available.
- Stripe Checkout is enabled on the account with Pro and Team products + recurring monthly prices created; price IDs are recorded in configuration.
- Stripe Customer Portal is activated and configured to allow downgrades (deferred to period end).
- A webhook endpoint is registered for `checkout.session.completed`, `customer.subscription.updated`, `invoice.payment_failed`, and `customer.subscription.deleted` events.
- A test webhook delivery of `invoice.payment_failed` is received, signature verified with `STRIPE_WEBHOOK_SECRET`, and the event ID stored for idempotency — confirming the idempotency flow works end-to-end.
- Test mode: Stripe CLI or dashboard confirms webhook retries are observable.

**Fail condition**:
- Stripe account not approved for live payments before launch.
- Customer Portal not available on the account plan.
- Webhook endpoint unreachable from Stripe's IPs (network/firewall issue in deployment).

**Fallback architecture**:
- No viable alternative to Stripe per §1.8 (architecturally irreversible). If live key approval is delayed, P0 launches in test mode only; billing session brief updated to add a feature flag that disables the Checkout button in production until live key is confirmed.

---

## OOB-08 — SendGrid Account + API Key + Transactional Template IDs

**Name**: SendGrid account active, sending domain verified (SPF/DKIM), API key with `mail.send` scope issued, and all required transactional email templates created with their template IDs recorded.

**Gates**: Auth sessions (email verification, password reset); notification worker session (grace period day-1 and day-6 emails, team invitation emails, export-ready notification).

**Pass condition**:
- `SENDGRID_API_KEY` is available with `mail.send` scope.
- Sending domain is verified (SPF and DKIM DNS records confirmed active; MX records not rejected).
- The following transactional templates exist in SendGrid with known template IDs (for injection into worker configuration):
  - Email verification link
  - Password reset link
  - Grace period day-1 warning
  - Grace period day-6 final warning
  - Team invitation (P1, but template can be created ahead)
  - Export ready notification
- A test send to a controlled inbox confirms delivery (not spam folder).

**Fail condition**:
- Sending domain fails SPF/DKIM verification.
- Account flagged / reputation issue blocks delivery.
- Template IDs not recorded before session starts (worker session hardcodes unknown values).

**Fallback architecture**:
- AWS SES as drop-in alternative; update the Notification Worker session brief to use `boto3` SES client instead of `sendgrid-python`; replace `SENDGRID_API_KEY` env var with `AWS_SES_REGION` and sending identity ARN; templates become SES templates.

---

## OOB-09 — EC2 G4dn Instance Type Quota Confirmation in Target Region

**Name**: AWS account quota for `g4dn.xlarge` (or equivalent) EC2 instance type confirmed sufficient in `DATA_REGION` for at least 1 on-demand instance (dev/staging) and the planned production pool size.

**Gates**: ML Worker deployment session; any session depending on GPU inference throughput.

**Pass condition**:
- AWS Service Quotas console shows `Running On-Demand G and VT instances` vCPU quota ≥ (pool size × 4 vCPUs per g4dn.xlarge) in `DATA_REGION`.
- A test `g4dn.xlarge` instance launches successfully in the target VPC/subnet.
- NVIDIA driver + CUDA toolkit are confirmed installable on the base AMI selected for ML workers.
- IAM role for the EC2 instance can read from S3 at `ML_MODEL_S3_KEY`.

**Fail condition**:
- Quota is 0 (default for new accounts); quota increase request is pending or denied.
- `g4dn.xlarge` is not available in `DATA_REGION` (e.g., AZ capacity issue).
- CUDA version required by ML framework not supported on available AMI.

**Fallback architecture**:
- Use `g5.xlarge` (A10G GPU, better availability) if `g4dn` is unavailable — update ML Worker session brief with correct instance type and AMI.
- Short-term fallback: CPU inference on ECS Fargate with `c5.4xlarge` — update ML Worker session brief to remove GPU Celery configuration, expect 5–10× slower throughput, and add a throughput-based capacity warning.

---

## OOB-10 — PostHog API Key + Ingestion Endpoint Verification

**Name**: PostHog instance (cloud or self-hosted) available, API key issued, and a test event ingestion confirmed.

**Gates**: Analytics instrumentation session (all nine structured events).

**Pass condition**:
- `POSTHOG_API_KEY` is available and non-empty.
- `POSTHOG_HOST` resolves and accepts HTTP `POST /capture` with the API key.
- A test event payload matching the `drawing_uploaded` schema is ingested and visible in the PostHog UI within 30 seconds.

**Fail condition**:
- Self-hosted instance cannot be provisioned; cloud account cannot be created.
- API key rejected by ingestion endpoint.

**Fallback architecture**:
- Per spec §1.12, analytics failure must not surface to users and `POSTHOG_API_KEY` absence only logs a warning; analytics is disabled gracefully.
- If PostHog is entirely unavailable: update analytics session brief to wrap all PostHog calls behind a dead-letter queue and a feature flag; no session is blocked (analytics is non-blocking per §1.10), but the analytics session brief should note that the dead-letter queue implementation is required.

---

## OOB-11 — ClamAV Docker Image + Virus Definition Update Verification in Isolated Network

**Name**: ClamAV sidecar container image builds successfully, virus definitions update on startup, and scan function is verified in the network-constrained Ingest Worker environment.

**Gates**: Ingest/Scan Worker session (ClamAV sidecar malware scan step in the `scan` Celery queue).

**Pass condition**:
- ClamAV Docker image (`clamav/clamav` or custom build) starts successfully as a sidecar container.
- `freshclam` virus definition update completes on container init (requires outbound HTTPS to `database.clamav.net`; confirm this is permitted from the Ingest Worker security group — the DWG sandbox has no egress, but the ClamAV sidecar is a separate container).
- `clamscan` on a known-clean test PDF returns exit code 0 ("OK").
- `clamscan` on an EICAR test file returns exit code 1 ("FOUND").
- Definition update does not interfere with the isolated DWG sandbox container (separate network namespace confirmed).

**Fail condition**:
- Network egress to `database.clamav.net` is blocked by security group, and a private mirror is not available.
- ClamAV definition files exceed container ephemeral storage limits in Fargate.
- Scan sidecar cannot communicate with Ingest Worker over the inter-container socket/volume.

**Fallback architecture**:
- Per spec §1.7: Trend Micro File Security (managed, per-scan cost, enterprise compliance). Update Ingest/Scan Worker session brief to use Trend Micro SDK instead of ClamAV subprocess; add `TREND_MICRO_API_KEY` to env var schema.

---

## OOB-12 — ML Model ≥85% F1 Pre-Launch Validation

**Name**: The trained ML symbol detection model achieves ≥85% F1 score on an external validation dataset of ≥20 P&ID drawings from ≥3 distinct companies.

**Gates**: This is the production launch gate per §1.9 ("Pre-launch gate" hard SLA). It does not block engineering sessions but blocks any production release session or go-live checklist.

**Pass condition**:
- An external test dataset of ≥20 drawings from ≥3 companies exists with ground-truth symbol annotations.
- Model inference on the complete test set produces F1 ≥ 0.85 for symbol detection across all `EntityClassId` types.
- Results are documented and signed off by a named ML engineer.
- `ML_MODEL_S3_KEY` and `ML_MODEL_VERSION` point to the validated model artifact.

**Fail condition**:
- F1 < 0.85 on external dataset.
- Test dataset has insufficient diversity (fewer than 3 companies or fewer than 20 drawings).
- No external dataset exists (only internal training data available).

**Fallback architecture**:
- Launch is blocked. Engineering sessions can proceed, but no production traffic routes to ML inference.
- Interim: lower-confidence model deployed in a "preview" mode where all detections are shown with explicit low-confidence warnings and correction is mandatory before export — update Drawing Review Canvas session brief and ML Worker session brief with this degraded mode. F1 threshold must still be met before removing the preview mode gate.

---

## OOB-13 — Audit Log Monthly Partition Pre-Creation + Automated Partition Job

**Name**: `audit_log` table partition strategy implemented: current month + 3 forward months pre-created, and an automated monthly partition creation job is scheduled and verified.

**Gates**: Any backend API session that writes to `audit_log`; GDPR erasure session (reads audit_log); any session implementing `GDPR 2-year retention` enforcement.

**Pass condition**:
- At least 4 monthly partitions (`audit_log_YYYY_MM`) exist in the provisioned PostgreSQL instance covering now through 3 months forward.
- `INSERT INTO audit_log ...` with `occurred_at = NOW()` succeeds without "no partition of relation found for row" error.
- A scheduled job (pg_cron, or an external cron in ECS) that creates the next month's partition on the 1st of each month is deployed and its next execution verified in the scheduler.
- A partition cleanup job that `DROP`s partitions older than 2 years (`occurred_at < NOW() - INTERVAL '2 years'`) is scheduled and verified.

**Fail condition**:
- `pg_cron` is not available on the RDS/Aurora instance (requires enabling the extension or a separate scheduler).
- First `INSERT` to `audit_log` fails due to missing partition, causing API startup errors.

**Fallback architecture**:
- Replace `PARTITION BY RANGE` with a non-partitioned `audit_log` table with a `created_at` index; add a background Celery task on the `gdpr_erasure` queue that deletes rows older than 2 years. Update the database schema session brief and GDPR Worker session brief accordingly.

---

## OOB-14 — Production Environment Variables Fully Populated + Startup Check Verification

**Name**: All "Refuse to start" environment variables from §1.12 are populated in staging and production deployment environments, and a dry-run API startup confirms no missing-variable crashes.

**Gates**: Any session performing integration testing against staging; the deployment/go-live session.

**Pass condition**:
- All 18 "Refuse to start" env vars (`DATABASE_URL`, `REDIS_URL`, `S3_BUCKET_NAME`, `S3_REGION`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_RS256_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `SENDGRID_API_KEY`, `HMAC_SERVER_SECRET`, `ML_MODEL_S3_KEY`, `ODA_CONVERTER_PATH`, `CELERY_BROKER_URL`, `DATA_REGION`) are set in the secrets manager / ECS task definition environment for both staging and production.
- FastAPI process starts in staging without crashing on startup validation.
- Celery workers start in staging without crashing on startup validation.
- `HMAC_SERVER_SECRET` is a cryptographically random, high-entropy string (≥32 bytes) — confirmed not a placeholder.
- `DATA_REGION` is set to `eu-central-1` or `us-east-1` — confirmed consistent with S3 bucket region and RDS region.

**Fail condition**:
- Any "Refuse to start" var is absent or contains a placeholder (`"TODO"`, `"changeme"`, `""`).
- `HMAC_SERVER_SECRET` is low-entropy (used for `anonymous_id` derivation — critical for GDPR erasure irreversibility).
- `DATA_REGION` is inconsistent with the S3 bucket's actual region (causes cross-region request failures and latency).

**Fallback architecture**:
- No alternative — this must be resolved. Any session blocked by a missing secret cannot proceed to integration or deployment.