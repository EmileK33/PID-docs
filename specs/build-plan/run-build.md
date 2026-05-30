# HyperSpeed Build Plan — Supervised Runner (Claude Code)

> **Scope note.** This runner is the *supervised entry surface*. All parallelism happens in the Node child process — Claude Code does **not** spawn sub-agents (the Agent tool would silently serialize above ~5 concurrent sessions and flood this context with their output). Every wave of session work runs by shelling out to `node build-plan/run-build.mjs --wave N` via the **Bash tool**.

You are driving an autonomous parallel build. The plan lives in `build-plan/run-manifest.json` next to this file. The user is your supervisor — keep them in the loop, summarize wave-by-wave, surface failures and `[MANUAL]` sign-offs as they happen.

## Pre-flight

Before the first wave, do these in parallel via the Bash tool:

1. `cat build-plan/run-manifest.json` — confirm the file exists and parses. Report to the user: total wave count, the integration command, and a one-line summary per wave (feature waves: number of sessions; integration waves: just the command).
2. `node build-plan/run-build.mjs --dry-run` — confirm the runner agrees with what you read.
3. Verify out-of-band setup is in place by reading `build-plan/README.md` aloud to the user (`GH_TOKEN`, CI workflow, branch-protection rule). If any of those are missing, **stop and tell the user before invoking the runner** — PRs will merge without test enforcement otherwise.

If `build-plan/run-state.json` already exists, you're resuming. `cat` it, summarize which sessions are `done` (will be skipped) and which are `failed`/`interrupted` (will have their worktrees cleaned and retried). Ask the user to confirm before proceeding.

## Per-wave loop

For each wave `N` in `0..manifest.waves.length`:

1. **Announce.** Tell the user which wave you're about to execute and what it contains (feature: list session IDs; integration: print the command).
2. **Invoke the runner.** Run this exact command via the Bash tool — **not** the Agent tool, not a Task tool:
   ```bash
   node build-plan/run-build.mjs --wave N
   ```
   Stream the output to the user as it arrives. Do not summarize until the command exits.
3. **On success (exit 0).**
   - Read the updated `build-plan/run-state.json` and report which sessions completed in this wave with their PR URLs.
   - For each PR with `manualAcs[]` (look at the corresponding session in `run-manifest.json`), surface the PR URL to the user and list the manual ACs as checkboxes. Instruct them to tick the boxes in the PR description **before merging**.
   - Ask the user whether to proceed to the next wave.
4. **On failure (non-zero exit).**
   - Read `build-plan/wave-N-failure-report.json`.
   - Summarize each failure to the user: session id, status, PR URL (or "no PR opened"), test exit code, last few lines of stdout, error message.
   - Ask: **retry this wave** (re-invoke `--wave N`; the runner will skip `done` sessions and force-clean failed worktrees) or **abort the build** (stop the loop here; user will fix and re-run later).
   - Do not advance past a failed wave automatically.

After the last wave, read the final `run-state.json` and report the overall summary table to the user (sessions done, total PRs opened, any `[MANUAL]` items still un-ticked across all PRs).

## Things to do explicitly

- **Use Bash, never the Agent tool, to invoke the runner.** This is the entire point of the hybrid architecture. The Node child process owns all parallelism.
- **Stream runner output verbatim.** The runner prints Diamond-by-Diamond progress (per-session start/PR/done/fail lines); the user wants to see those as they happen, not a post-hoc summary.
- **Tell the user before running the runner**, every time. They should know which wave is about to fire and roughly how many sessions it will spawn.
- **Honor `[MANUAL]` sign-offs.** A `done` session is mergeable but not necessarily merge-*worthy*; only the human can sign off on `[MANUAL]` ACs. If you spot a session whose PR has manual checkboxes, surface them.

## Things NOT to do

- Do not spawn sub-agents to parallelize sessions. The Node runner already does this — using the Agent tool on top would either duplicate work or silently serialize.
- Do not read the briefs (`section5-briefs/*.md`) into your own context. Each spawned `claude` child reads only its own brief; mirroring them here would waste tokens and risk context contamination.
- Do not modify `run-manifest.json` mid-build. Plan changes belong in a new build-plan generation, not an in-flight runner.
- Do not retry more than ~3 times across a session boundary without surfacing the failure to the user. If the same wave fails repeatedly with the same error, that's a planning bug; bring the user in.

## Quick reference

| Want to... | Command |
| --- | --- |
| Preview the plan | `node build-plan/run-build.mjs --dry-run` |
| Execute a single wave (this file's loop) | `node build-plan/run-build.mjs --wave N` |
| Execute everything end-to-end (headless mode, no CC needed) | `node build-plan/run-build.mjs` |
| Inspect state mid-build | `cat build-plan/run-state.json` |
| Inspect a halt | `cat build-plan/wave-N-failure-report.json` |

## What just happened in this prompt

You loaded this markdown file. The build-plan manifest is next to it. Start with the pre-flight checks above, then walk wave-by-wave with the user.
