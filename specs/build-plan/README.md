# HyperSpeed Autonomous Build — Runner README

This directory is the executable artifact emitted from a HyperSpeed `--generate-build-plan` run. It contains:

| File | What it is |
| --- | --- |
| `run-manifest.json` | The wave-by-wave plan: feature waves (parallel sessions) interleaved with integration waves (project-level test gates). Don't edit by hand. |
| `run-build.mjs` | Node runner. Single execution engine. Runs all OS-level fan-out, worktree lifecycle, PR creation, gh backoff, resumability. Two entry surfaces: direct (`node run-build.mjs`) or supervised via `run-build.md`. |
| `run-build.md` | Claude Code-loaded prompt. Drives the runner wave-by-wave for supervised execution. Shells out to `run-build.mjs --wave N` per wave via the Bash tool. |
| `section5-briefs/` | Per-session implementation briefs. Each spawned `claude` child reads only its own brief (no PRD, no architecture, no siblings). |
| `autonomous-build-plan.md` | Top-level summary doc for humans. Not consumed by the runner. |
| `run-state.json` *(created at runtime)* | Per-session status — enables resumability across restarts. |
| `wave-N-failure-report.json` *(created on halt)* | Structured failure context for the wave that failed. |
| `.bp-worktrees/` *(in your repo root, created at runtime)* | Isolated git worktrees, one per session. Cleaned automatically on session success or SIGINT. |

## Two entry surfaces, one engine

You pick per project — they consume the same manifest and produce the same PRs.

**Headless / multi-day / CI.** Run the Node runner directly:
```bash
node build-plan/run-build.mjs              # execute every wave end-to-end
node build-plan/run-build.mjs --wave 0     # execute one wave
node build-plan/run-build.mjs --dry-run    # preview the plan, no side effects
```

**Supervised in Claude Code.** Load `build-plan/run-build.md` into Claude Code. It will walk you wave-by-wave, shelling out to `run-build.mjs --wave N` via the Bash tool. You get real-time Diamond progress in chat and can interrupt at any wave boundary.

## One-time per-repo setup (required for PR gating)

The runner opens a PR per session. Those PRs do **not** enforce their Independent Test by themselves — that's a GitHub-side concern. Without the three items below, the runner will open PRs but they can be merged without test enforcement.

### 1. `GH_TOKEN`

The runner uses the `gh` CLI for PR creation. Either:

- `gh auth login` once, interactively, on the machine that runs the build, OR
- Export `GH_TOKEN=<personal-access-token>` with `repo` scope.

The runner wraps `gh` mutations in exponential backoff (3 attempts, 5s/15s/45s) on 403/429, so transient rate limiting won't fail a build — but **persistent auth failures will halt the wave**.

### 2. CI workflow that runs the Independent Test

Add a workflow that runs each session's `test.cmd` on PR events. Minimum viable workflow:

```yaml
# .github/workflows/session-tests.yml
name: Session tests
on:
  pull_request:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npm test
```

Each session's PR title is `<session-id>: autonomous build` and the branch is `bp/<run-id>/<session-id>`. The workflow above runs the full test suite on every PR; if you'd rather scope tighter, parse the session id from the branch and shell into `npm test -- tests/sessions/<id>`.

The integration-wave gate is the project-level `npm run test:integration` (or equivalent — check `integrationCmd` in `run-manifest.json`). The runner invokes it directly on the host before advancing to the next feature wave; CI does not need a separate integration job unless you want a second layer.

### 3. Required-status-check branch protection on `main`

Without this, a PR can be merged before its CI job finishes — defeating the test gate.

GitHub Settings → Branches → Branch protection rule for `main`:
- **Require a pull request before merging** ✅
- **Require status checks to pass before merging** ✅
- Pick the `Session tests` check (or whatever you named the workflow job) as required.

A scriptable equivalent (run once with admin permissions):
```bash
gh api -X PUT "repos/{OWNER}/{REPO}/branches/main/protection" \
  -F required_status_checks.strict=true \
  -F required_status_checks.contexts[]='test' \
  -F enforce_admins=false \
  -F required_pull_request_reviews.required_approving_review_count=1 \
  -F restrictions= 
```

## Resumability

`run-state.json` is rewritten after every session transition. If the runner exits cleanly (success or `gh halt`), you can re-run the same command — `done` sessions are skipped, `failed` / `interrupted` sessions get their worktrees force-removed before retry. SIGINT / SIGTERM cleans up worktrees of in-progress sessions before exit (exit code 130).

If `run-state.json` survives across `git pull`s or branch switches, that's fine — the runner reconciles against the current manifest.

## `[MANUAL]` ACs

Some acceptance criteria can't be auto-verified (screenshots, accessibility, vibe). The runner emits these in each PR's body as `## Manual sign-off required` with `- [ ]` checkboxes:

```markdown
## Manual sign-off required

The following acceptance criteria cannot be automatically verified. The reviewer must tick each box before merging.

- [ ] [US-001 AC-3] Login page screenshot matches design system.
- [ ] [US-002 AC-1] Accessibility audit clean.
```

GitHub renders these as interactive task lists. **Tick every box before clicking Merge.** This is a load-bearing part of the workflow — no automation will catch a regression in `[MANUAL]` items.

## Brief Quality Scoring (optional pre-flight)

A separate command, `hyperspeed --score-briefs <build-plan-dir>`, runs a Haiku judge over every brief in `section5-briefs/` and grades it against the source specs on a six-dimension rubric. Use it as a pre-flight before you fire the runner — `[MANUAL]` vagueness, hand-waved Independent Tests, and under-specified `exports[]` blocks are the failure modes structural validators miss.

### How to run it

```bash
hyperspeed --score-briefs ./Projects/MyProject/specs/build-plan/
# Options:
#   --spec-dir <path>   default: parent dir of <build-plan-dir>
#   --threshold N       default: 20 — minimum total to count as "ship"
#   --output <path>     default: <build-plan-dir>/brief-quality-report.md
```

Cost is negligible (~$0.06 for a 15-session plan, single Haiku call per brief). Outputs:
- `brief-quality-report.md` — per-brief score table, dimension-level commentary, ship/borderline/regenerate roll-up.
- `brief-quality-report.json` — machine-readable sidecar consumed by the runner gate below.

### The six dimensions

| Dimension | Catches |
| --- | --- |
| Checkpoint specificity | Boilerplate "feature works" sentences that name no observable behavior. |
| Independent Test traceability | `test.cmd` that doesn't actually exercise the ACs listed. |
| Exports completeness | Missing exports the prose section names; vague shapes (`function`) that defeat `validateIntraWaveExports`. |
| Mocking contract realism | Shapes that contradict the architecture spec or are obviously placeholder. |
| AC fidelity | Silent paraphrasing or omission of source-story AC text. |
| Phase 0 harness usefulness *(S0 only)* | Smoke tests that don't touch real services; missing fixture exports. |

Each dimension is scored 0–5. Max total: 25 for normal briefs, 30 for Phase 0 (which adds the 6th).

### Threshold tuning

- **20** (default) — strict but achievable. Use for production builds where you want a real pre-merge bar.
- **18** — relaxed. Use early in a project when prompts are still being tuned and you want signal without blocking.
- **23+** — only realistic if you're iterating on the brief generator itself. A typical Haiku judge run hovers around 20–23 for well-formed briefs; pushing higher will flag too much.

A brief in the "borderline" band (threshold − 4 ≤ total < threshold) is salvageable — read the dimension comments to decide whether to regenerate or accept. Anything below that should be regenerated.

### Gating the runner (`--require-quality-score`)

Once a `brief-quality-report.json` exists, you can force the runner to refuse to fire on a low-quality plan:

```bash
node build-plan/run-build.mjs --require-quality-score         # threshold 20 (default)
node build-plan/run-build.mjs --require-quality-score 22      # custom threshold
```

If the JSON sidecar is missing, malformed, or any brief is below threshold (or errored at scoring time), the runner exits non-zero before opening any worktree. The gate runs once at startup, before reconcileState and before the first wave.

This flag is **opt-in** — without it the runner behaves exactly as before. It's intended as a power-user safety rail for unattended runs.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `gh: command not found` | gh CLI not installed on the runner host | Install `gh` and `gh auth login` (or set `GH_TOKEN`). |
| `error: no such ref: main` during worktree add | Default branch isn't `main` | Set `HS_BASE_BRANCH=master` (or your default) in env before running. *(coming soon)* |
| Persistent 403 from gh | Token missing `repo` scope, or org SSO not authorized | Re-issue token with `repo`; authorize SSO in token settings. |
| Sessions failing with "claude: command not found" | Claude Code CLI not in PATH | Install Claude Code CLI; or set `HS_CLAUDE_CLI=/path/to/claude` in env. |
| Want to point at a non-cwd repo | Default is `process.cwd()` | Set `HS_REPO_ROOT=/path/to/repo` in env. |

## Environment variables

| Var | Default | Purpose |
| --- | --- | --- |
| `HS_CLAUDE_CLI` | `claude` | Override the Claude Code CLI binary. |
| `HS_CLAUDE_CLI_ARGS` | `--dangerously-skip-permissions -p` | Override the args passed to the CLI. The brief is piped via stdin. |
| `HS_REPO_ROOT` | `process.cwd()` | The repo into which worktrees and PRs are created. |
| `GH_TOKEN` | — | Used by `gh` if `gh auth login` isn't set up. |

## Need to bail mid-build?

`Ctrl-C` once. The runner's SIGINT handler will:
1. Mark every in-progress session `interrupted` in `run-state.json`.
2. Force-remove their worktrees.
3. Exit 130.

On the next run, those sessions are retried from a clean worktree. `done` sessions are skipped.
