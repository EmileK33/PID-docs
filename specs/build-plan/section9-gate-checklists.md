### Gate: Phase 0 → Phase 1

Required sessions: S0-A, S0-B
Non-blocking: none

- [ ] `cd backend && python -m compileall app/ -q` exits 0 (no syntax errors in any stub module)
- [ ] `cd frontend && npx tsc --noEmit` exits 0 (all stub pages and `contracts.ts` type-check cleanly)
- [ ] `cd marketing && npx tsc --noEmit` exits 0
- [ ] `docker compose build api worker ml-worker` exits 0 with no layer errors for all three images
- [ ] `docker compose -f docker-compose.test.yml config --quiet` exits 0 (fixture compose file is valid YAML with no unresolved references)
- [ ] `bash scripts/test-integration.sh` exits 0 and stdout contains `1 passed` from `tests/integration/smoke/test_smoke.py`
- [ ] `docker compose up -d api && sleep 5 && curl -sf http://localhost:8000/health` returns HTTP `200` and a JSON body (app starts and health route is wired)
- [ ] `curl -sf http://localhost:8000/openapi.json | python3 -c "import sys,json; p=json.load(sys.stdin)['paths']; assert '/api/v1/drawings' in p and '/api/v1/auth/register' in p"` exits 0 (stub route manifest covers §1.6 P0+P1 routes)
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/drawings` returns `401` or `501` — never `200` (stubs do not leak data unauthenticated)
- [ ] `.env.example` contains entries for every variable named in §1.12: `diff <(grep -oP '^[A-Z_]+(?==)' .env.example | sort) <(grep -oP '\b[A-Z_]{4,}\b' backend/app/config.py | sort -u) | grep "^>" | wc -l` returns `0` (no undocumented env vars in config)

---

### Gate: Phase 1 → Phase 2

Required sessions: S1-A, S1-B, S1-C, S1-D, S1-E
Non-blocking: S1-F (frontend-only; gates Phase 3 sessions, not Phase 2 backend work)

- [ ] `cd backend && python -m mypy app/ --ignore-missing-imports --no-error-summary` exits 0
- [ ] `cd backend && alembic upgrade head` exits 0 against the test Postgres instance; output contains `Running upgrade -> 0001`, `0002`, `0003`
- [ ] `psql "$TEST_DATABASE_URL" -c "\dt" | grep -cE 'drawings|users|subscriptions|audit_log'` returns `4` (core tables present after migrations)
- [ ] `psql "$TEST_DATABASE_URL" -c "SELECT count(*) FROM tiers"` returns a value ≥ 3 (seed script ran successfully)
- [ ] `python3 -c "from app.storage.s3_client import S3Client; S3Client().head_bucket(Bucket='pid-uploads')"` exits 0 against LocalStack endpoint configured in `.env.test`
- [ ] `redis-cli -u "$REDIS_URL" ping` returns `PONG`
- [ ] `redis-cli -u "$REDIS_URL" publish drawing:status:test '{"state":"queued"}' && redis-cli -u "$REDIS_URL" subscribe drawing:status:test` produces the published message within 2 s (pub/sub channel routing works)
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/drawings -H "Authorization: Bearer invalid.jwt.token"` returns `401`
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/drawings -H "Authorization: Bearer $(python3 -c "import jwt,time; print(jwt.encode({'sub':'uid','exp':int(time.time())-1,'role':'viewer'},'wrong_secret'))")"` returns `401` (expired/wrong-secret token rejected)
- [ ] `pytest tests/integration/test_auth_middleware.py tests/integration/test_storage.py tests/integration/test_redis_pubsub.py tests/integration/test_analytics.py -v` exits 0 (all four Phase 1 integration suites green)
- [ ] `celery -A app.workers.celery_app inspect ping -d celery@worker` returns `{'celery@worker': {'ok': 'pong'}}` (Celery worker starts and responds using queue config from `queues.py`)

---

### Gate: Phase 2 → Phase 3 [S3-A — Auth Pages]

Required sessions: S1-F, S2-A
Non-blocking: none

- [ ] `cd frontend && npx tsc --noEmit` exits 0 (S1-F shared infrastructure compiles; no regressions from new auth service types)
- [ ] `pytest tests/integration/test_auth_endpoints.py -v` exits 0
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/auth/me` returns `401` (unauthenticated profile fetch rejected)
- [ ] `curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"bad","password":"x"}'` returns `422` (validation enforced)
- [ ] `curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"smoke@example.com","password":"ValidPass1!"}'` returns HTTP `201` and a JSON body containing `"id"` (registration creates user)
- [ ] Calling `POST /api/v1/auth/login` five times with wrong credentials within 60 s returns `429` on the sixth attempt (brute-force middleware active)

---

### Gate: Phase 2 → Phase 3 [S3-B, S3-C — Drawing Library & Upload Flow]

Required sessions: S1-F, S2-B
Non-blocking: none

- [ ] `cd frontend && npx tsc --noEmit` exits 0
- [ ] `pytest tests/integration/test_drawings_api.py tests/integration/test_drawings_sse.py -v` exits 0
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/drawings` returns `401`
- [ ] `curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/v1/drawings -H "Authorization: Bearer $VALID_JWT" -H "Content-Type: application/json" -d '{"filename":"p&id.pdf","sha256":"'$(python3 -c "print('a'*64)")'","size_bytes":204800}'` returns `201` with a JSON body containing `"id"` and `"status":"pending_scan"`
- [ ] Issuing the same `sha256` a second time as a different user returns `409` (blocklist two-gate: duplicate hash rejected)
- [ ] `curl -sN "http://localhost:8000/api/v1/drawings/$DRAWING_ID/status/stream" -H "Authorization: Bearer $VALID_JWT" -H "Accept: text/event-stream"` prints at least one `data:` line within 3 s (SSE stream opens and emits)
- [ ] Creating a drawing as a free-tier user who has reached the plan quota returns `402` with `"code":"free_tier_limit_reached"` in the JSON error body

---

### Gate: Phase 2 → Phase 3 [S3-D — Review Canvas]

Required sessions: S1-F, S2-B, S2-C
Non-blocking: none

- [ ] `cd frontend && npx tsc --noEmit` exits 0
- [ ] `pytest tests/integration/test_drawings_api.py tests/integration/test_symbols_api.py -v` exits 0
- [ ] `curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/drawings/$DRAWING_ID/symbols"` returns `401`
- [ ] `curl -s -w "\n%{http_code}" "http://localhost:8000/api/v1/drawings/$DRAWING_ID/symbols" -H "Authorization: Bearer $VALID_JWT"` returns `200` with a JSON array body (even if empty)
- [ ] `curl -s -w "\n%{http_code}" -X POST "http://localhost:8000/api/v1/drawings/$DRAWING_ID/symbols/$SYMBOL_ID/corrections" -H "Authorization: Bearer $VALID_JWT" -H "Content-Type: application/json" -d '{"corrected_class_id":"cls_test","bounding_box":{"x":0,"y":0,"w":20,"h":20}}'` returns `201`
- [ ] Submitting the same correction request with a different user's JWT (no ownership) returns `403`
- [ ] Submitting a correction on a drawing in `processing` state (not `complete`) returns `409` (state-machine guard enforced)

---

### Gate: Phase 2 → Phase 3 [S3-E — Account & Consent]

Required sessions: S1-F, S2-F
Non-blocking: none

- [ ] `cd frontend && npx tsc --noEmit` exits 0
- [ ] `pytest tests/integration/test_account.py -v` exits 0
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/account/me` returns `401`
- [ ] `curl -s -w "\n%{http_code}" http://localhost:8000/api/v1/account/me -H "Authorization: Bearer $VALID_JWT"` returns `200` with `"email"` field present
- [ ] `curl -s -w "\n%{http_code}" -X PATCH http://localhost:8000/api/v1/account/consent -H "Authorization: Bearer $VALID_JWT" -H "Content-Type: application/json" -d '{"ml_training_consent":true}'` returns `200`; re-fetching `GET /api/v1/account/me` shows `"ml_training_consent":true` (consent persisted)
- [ ] `curl -s -w "\n%{http_code}" -X DELETE http://localhost:8000/api/v1/account/me -H "Authorization: Bearer $VALID_JWT"` returns `202` and body contains `"status":"erasure_queued"`

---

### Gate: Phase 2 → Phase 3 [S3-F — Subscription & Upgrade]

Required sessions: S1-F, S2-E
Non-blocking: none

- [ ] `cd frontend && npx tsc --noEmit` exits 0
- [ ] `pytest tests/integration/test_subscription.py tests/integration/test_stripe_webhook.py -v` exits 0
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/subscription` returns `401`
- [ ] `curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/stripe/webhook -H "Stripe-Signature: t=1,v1=badsig" -H "Content-Type: application/json" -d '{}'` returns `400` (signature verification rejects tampered payload)
- [ ] Sending a valid `customer.subscription.updated` test event via `stripe trigger customer.subscription.updated` (Stripe CLI) and immediately re-sending the same event ID returns `200` the second time with no duplicate row: `psql "$TEST_DATABASE_URL" -c "SELECT count(*) FROM stripe_events WHERE stripe_event_id='$EVENT_ID'"` returns `1` (idempotency enforced)
- [ ] `curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/v1/subscription/checkout -H "Authorization: Bearer $VALID_JWT" -H "Content-Type: application/json" -d '{"tier":"pro"}'` returns `200` with `"checkout_url"` pointing to `checkout.stripe.com` (Stripe session created)

---

### Gate: Phase 2 → Phase 3 [S3-G — Exports UI + Notifications]

Required sessions: S1-F, S2-D
Non-blocking: none

- [ ] `cd frontend && npx tsc --noEmit` exits 0
- [ ] `pytest tests/integration/test_exports_api.py -v` exits 0
- [ ] `curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/drawings/$DRAWING_ID/exports"` returns `401`
- [ ] `curl -s -D - -X POST "http://localhost:8000/api/v1/drawings/$SMALL_DRAWING_ID/exports" -H "Authorization: Bearer $VALID_JWT" -H "Content-Type: application/json" -d '{"format":"csv"}'` returns `200` with `Content-Type: text/csv` and non-empty body (sync path for drawings with < 1000 symbols)
- [ ] `curl -s -w "\n%{http_code}" -X POST "http://localhost:8000/api/v1/drawings/$LARGE_DRAWING_ID/exports" -H "Authorization: Bearer $VALID_JWT" -H "Content-Type: application/json" -d '{"format":"xlsx"}'` returns `202` with `"export_id"` in body (async path for drawings with ≥ 1000 symbols)
- [ ] `GET /api/v1/drawings/$LARGE_DRAWING_ID/exports/$EXPORT_ID` returns `200` with `"status":"pending"` immediately after the `202` (export record created before worker picks it up)

---

### Gate: Phase 3 → Phase 4

Required sessions: S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M, S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G
Non-blocking: S3-H (marketing site; not a prerequisite of S4-A)

- [ ] `cd backend && python -m mypy app/ --ignore-missing-imports --no-error-summary` exits 0
- [ ] `cd frontend && npx tsc --noEmit` exits 0
- [ ] `cd frontend && npm run build` exits 0 with no TypeScript or Vite errors; `dist/` directory is non-empty
- [ ] `cd marketing && npx tsc --noEmit` exits 0
- [ ] `pytest tests/integration/ -v --ignore=tests/integration/e2e -x` exits 0 (all ~20 Phase 1–2 integration suites pass before any E2E file is touched)
- [ ] `docker compose up -d` brings all services healthy: `docker compose ps --format json | python3 -c "import sys,json; rows=json.load(sys.stdin); assert all(r['Health']=='healthy' for r in rows if r['Service'] in ['db','redis','localstack'])"` exits 0
- [ ] `celery -A app.workers.celery_app inspect ping` returns pong from workers registered on queues `ingest`, `scan`, `ml`, `export`, `gdpr`, `notifications` (all six worker queues active)
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/drawings -H "Authorization: Bearer invalid.jwt.here"` returns `401`
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/admin/users -H "Authorization: Bearer $VIEWER_JWT"` returns `403` (role matrix enforced; viewer cannot reach admin scope)
- [ ] `python3 -m py_compile tests/integration/e2e/test_upload_to_complete.py tests/integration/e2e/test_correction_flow.py tests/integration/e2e/test_export_sync_and_async.py tests/integration/e2e/test_stripe_lifecycle.py tests/integration/e2e/test_gdpr_erasure.py tests/integration/e2e/test_blocklist_two_gate.py tests/integration/e2e/test_free_tier_limit.py` exits 0 (all seven E2E files parse without syntax errors before S4-A execution begins)
- [ ] `pytest tests/integration/e2e/test_upload_to_complete.py -v --timeout=120` exits 0 (critical-path E2E: upload → ingest → scan → ML → `complete` state transition driven end-to-end)