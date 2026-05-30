## Build Summary — PID Analyzer

### Phase Table

| Phase | Sessions | Max parallel | Gate requirement | Est. Claude Code hours |
|-------|----------|-------------|-----------------|----------------------|
| 0 — Scaffold | S0-A (L), S0-B (M) | 2 | Both S0-A **and** S0-B must merge; harness must exit green | 5 h |
| 1 — Core Infrastructure | S1-A (L), S1-B (M), S1-C (M), S1-D (M), S1-E (S), S1-F (M) | 6 | S1-A + S1-B + S1-C + S1-D + S1-E must merge before Phase 2 backend; S1-F must merge before Phase 3 frontend (non-blocking for Phase 2) | 12 h |
| 2 — Services, Workers & API | S2-A (M), S2-B (L), S2-C (M), S2-D (M), S2-E (L), S2-F (M), S2-G (S), S2-H (L), S2-I (S), S2-J (L), S2-K (M), S2-L (M), S2-M (M) | 13 | All 13 sessions must merge; per-session unblock available for their specific Phase 3 dependents as they land | 28 h |
| 3 — Frontend & Marketing | S3-A (M), S3-B (M), S3-C (M), S3-D (L), S3-E (S), S3-F (M), S3-G (M), S3-H (M) | 8 | All 8 sessions must merge before Phase 4 (S3-H can start at Phase 1; S3-A can start as soon as S2-A merges) | 16 h |
| 4 — E2E Hardening | S4-A (L) | 1 | Delivery gate — all prior sessions merged and green | 3 h |

**Total Claude Code hours: 64 h**

---

### Calendar Time

Assuming same-day human gate reviews (~30 min per gate) and full parallelism within each phase:

| Segment | Wall-clock |
|---------|-----------|
| Phase 0 execution (bottleneck: S0-A, L) | 3 h |
| Gate review 0→1 | 0.5 h |
| Phase 1 execution (bottleneck: S1-A, L) | 3 h |
| Gate review 1→2 | 0.5 h |
| Phase 2 execution (bottleneck: any L session) | 3 h |
| Gate review 2→3 | 0.5 h |
| Phase 3 execution (bottleneck: S3-D, L) | 3 h |
| Gate review 3→4 | 0.5 h |
| Phase 4 execution (S4-A, L) | 3 h |
| **Total estimated calendar time** | **~17 h (~2 working days)** |

> **Early-start optimisation saves ~1 calendar day:** S3-H (marketing, M) can run during Phase 1; S3-A can unblock as soon as S2-A lands mid-Phase 2; S2-G and S2-L/S2-M have lighter prerequisite sets and can start slightly ahead of the rest of Phase 2.

---

### Critical Path

```
S0-A (L, 3 h) → S1-A (L, 3 h) → S2-B (L, 3 h) → S3-D (L, 3 h) → S4-A (L, 3 h)
```

**Critical path execution: 15 h + 4 × 0.5 h gate reviews = 17 h total calendar.**
Every session on this chain is complexity L with no slack; any slip propagates 1:1 to delivery.

---

### Cost Estimate

Using midpoint rates (S ≈ $0.75, M ≈ $1.50, L ≈ $3.00):

| Phase | S sessions | M sessions | L sessions | Phase cost |
|-------|-----------|-----------|-----------|-----------|
| 0 | 0 | 1 | 1 | $4.50 |
| 1 | 1 | 4 | 1 | $10.50 |
| 2 | 2 | 7 | 4 | $24.00 |
| 3 | 1 | 6 | 1 | $12.75 |
| 4 | 0 | 0 | 1 | $3.00 |
| **Total** | **4** | **18** | **8** | **~$54.75** |

**Range: $36 (all-low) – $72 (all-high).** The 8 large sessions account for ~44% of expected cost despite being only 27% of session count.

---

### Risk Summary

#### Critical-path sessions (zero float — any delay = schedule slip)
| Session | Risk factor |
|---------|------------|
| **S0-A** | Largest scaffold session; mistakes in stub contracts propagate to all 28 downstream sessions. Every consumer imports from these files. |
| **S1-A** | 22 model/migration files; schema errors are expensive to fix once Phase 2 consumers are in flight. RLS policies (0002) touch security surface. |
| **S2-B** | Most complex API session (state machine, SSE, free-tier counter, hash-check); gates the highest-value user-facing feature. |
| **S3-D** | Review Canvas (Konva); 9 files, real-time rendering, keyboard shortcuts, bounding-box interaction — highest frontend complexity. |
| **S4-A** | Cannot start until all 20 prior sessions merge; integration failures here require root-cause across the full stack. |

#### Highest dependency fan-out (most downstream sessions blocked if late)
| Session | Direct dependents |
|---------|-----------------|
| **S0-A** | 28 sessions (everything) |
| **S1-A** | 13 Phase 2 sessions |
| **S1-D** | 11 Phase 2 sessions (Redis/Celery consumed by nearly all workers and APIs) |
| **S1-B** | 9 Phase 2 sessions (auth middleware is a dependency for most API routers) |
| **S1-F** | 8 Phase 3 frontend sessions |

#### Highest intrinsic complexity (most likely to require iteration)
1. **S2-E** (Stripe + billing state machine + idempotency) — external payment integration, webhook replay, grace-period logic
2. **S2-H** (Ingest Worker) — ODA conversion sandbox, format detection, hash re-verify chain
3. **S2-J** (ML Worker) — model loading, GPU/CPU inference path, result persistence schema
4. **S2-B** (Drawings API + SSE) — state machine correctness, SSE fan-out, concurrent upload edge cases
5. **S1-A** (DB Models) — 17 models + 3 migration files including RLS and partitioned audit log

---

### Recommended Execution Strategy

**Do not launch all parallel sessions simultaneously within Phase 2.**

**Recommended approach — prioritised wave execution:**

1. **Phase 0:** Launch S0-A and S0-B simultaneously. Gate is hard; do not proceed until both are green and contracts are locked. This is the only phase where a stub error can silently corrupt every downstream session.

2. **Phase 1:** Launch all 6 sessions simultaneously. S1-A is the bottleneck; S1-E (analytics, S) will finish first — let it merge immediately. S1-F can be reviewed and merged independently as it only gates Phase 3.

3. **Phase 2 — staggered in two waves:**
   - **Wave 2a (launch immediately at gate):** S2-B, S2-H, S2-J, S2-E — the four L-complexity sessions. These are the longest and highest-risk; start them first to surface integration problems early. Also launch S2-G and S2-L/S2-M (lighter prerequisites) immediately.
   - **Wave 2b (launch within 30 min of gate):** S2-A, S2-C, S2-D, S2-F, S2-I, S2-K — all M/S sessions. Slight stagger reduces reviewer overload and gives Wave 2a a head start on shared Redis/DB infrastructure that might require hot-fixes.
   - **Early unblocking:** As individual Phase 2 sessions merge, unblock their specific Phase 3 dependents immediately (e.g., S3-A can start the moment S2-A merges, without waiting for the full Phase 2 gate).

4. **Phase 3:** Launch all 7 remaining sessions in parallel once the Phase 2 gate clears (S3-H should already be in progress or done). S3-D (L) is the bottleneck; prioritise its review.

5. **Phase 4:** Single sequential session — schedule S4-A immediately after the Phase 3 gate to avoid idle time.

> **Rationale for staggering Phase 2:** 13 simultaneous L+M sessions generate high reviewer concurrency. Surfacing S2-B/S2-H/S2-J failures early (they touch the core pipeline) allows other sessions to absorb any contract corrections before they are too far along. The ~30-minute stagger costs nothing on the critical path.