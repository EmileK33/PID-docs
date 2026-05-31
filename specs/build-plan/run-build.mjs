#!/usr/bin/env node
/**
 * HyperSpeed Build Plan — Node Runner (Track B, issue #37)
 *
 * Executes a `run-manifest.json` wave-by-wave. Each feature wave fans out
 * `Promise.all` across its sessions (worktree → claude CLI → independent
 * test → `gh pr create`). Each integration wave runs a single project-level
 * test command and gates downstream waves.
 *
 * Resumability via `run-state.json` (per-session status persisted to disk;
 * `done` sessions skipped on restart, `failed` sessions get their worktree
 * force-cleaned before retry). SIGINT/SIGTERM trap writes `interrupted`
 * state and force-removes in-progress worktrees before exit.
 *
 * Usage:
 *   node build-plan/run-build.mjs              # execute all waves
 *   node build-plan/run-build.mjs --wave 0     # execute a single wave (CC entry surface)
 *   node build-plan/run-build.mjs --dry-run    # print the wave plan, exit
 *
 * Pre-requisites for the runner's PR-gating guarantee — see README.md.
 *
 * Read-only deps: Node stdlib + `gh` CLI + `claude` CLI. No npm deps.
 */

import * as fs from 'node:fs/promises';
import * as fssync from 'node:fs';
import * as path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

// ─── Constants ───────────────────────────────────────────────────────────────

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const MANIFEST_PATH = path.join(SCRIPT_DIR, 'run-manifest.json');
const STATE_PATH = path.join(SCRIPT_DIR, 'run-state.json');
const STDOUT_TAIL_LINES = 50;
const GH_RETRY_DELAYS_MS = [5_000, 15_000, 45_000]; // 3 attempts (initial + 2 retries-after)
const GH_RETRY_CODES = new Set([403, 429]);
const CLAUDE_CLI = process.env.HS_CLAUDE_CLI || 'claude';
// Tokenize HS_CLAUDE_CLI_ARGS like a tiny shell — supports `"double-quoted args"`
// so paths with spaces (common on Windows) survive. parseShellCmd is defined
// later in this file; we inline its regex here to avoid a forward-reference.
const CLAUDE_CLI_ARGS = (() => {
  const raw = process.env.HS_CLAUDE_CLI_ARGS || '--dangerously-skip-permissions -p';
  const out = [];
  const re = /"([^"]*)"|(\S+)/g;
  let m;
  while ((m = re.exec(raw)) !== null) out.push(m[1] ?? m[2]);
  return out;
})();
const REPO_ROOT = process.env.HS_REPO_ROOT || process.cwd();

// ─── State ───────────────────────────────────────────────────────────────────

/**
 * @typedef {'pending' | 'in_progress' | 'done' | 'failed' | 'interrupted'} SessionStatus
 * @typedef {{
 *   status: SessionStatus;
 *   prUrl: string | null;
 *   worktreePath: string | null;
 *   branch: string | null;
 *   startedAt: string | null;
 *   completedAt: string | null;
 *   attempt: number;
 *   testExitCode: number | null;
 *   error: string | null;
 * }} SessionState
 * @typedef {{ runId: string; createdAt: string; sessions: Record<string, SessionState> }} RunState
 */

/** @returns {Promise<RunState | null>} */
export async function loadState(statePath = STATE_PATH) {
  try {
    const raw = await fs.readFile(statePath, 'utf-8');
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && typeof parsed.runId === 'string') {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

/** @param {RunState} state */
export async function saveState(state, statePath = STATE_PATH) {
  // Per-call unique tmp suffix. Parallel saveState across concurrent sessions
  // (Promise.all over the feature wave) would otherwise race on a single
  // `.tmp` path: A writes, B writes (overwrites), A renames (clears tmp),
  // B renames → ENOENT. Track D Session 2 finding. PID + timestamp +
  // counter is enough — none of these are reused across processes.
  const tmp = `${statePath}.${process.pid}.${Date.now()}.${_saveCounter++}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(state, null, 2), 'utf-8');
  await renameAtomic(tmp, statePath);
}
let _saveCounter = 0;

/**
 * Cross-platform atomic-ish rename. On POSIX, fs.rename overwrites the
 * destination. On Windows, fs.rename can fail with EPERM when the destination
 * exists and any other process (antivirus, indexer, a stale handle from this
 * runner) has it briefly open. We unlink the destination first on those
 * errors and retry once. This loses true atomicity in the failure window
 * (sub-millisecond gap between unlink and rename), which is acceptable for
 * run-state.json — a partial state file is recoverable by deleting it.
 *
 * `deps` lets tests inject a rename function that simulates EPERM.
 *
 * @param {string} from
 * @param {string} to
 * @param {{ rename?: (from: string, to: string) => Promise<void>, unlink?: (p: string) => Promise<void> }} [deps]
 */
export async function renameAtomic(from, to, deps = {}) {
  const rename = deps.rename ?? fs.rename.bind(fs);
  const unlink = deps.unlink ?? fs.unlink.bind(fs);
  try {
    await rename(from, to);
    return;
  } catch (e) {
    const code = e && typeof e === 'object' && 'code' in e ? e.code : null;
    if (code !== 'EPERM' && code !== 'EEXIST' && code !== 'EACCES') throw e;
  }
  // Fallback: unlink destination, retry rename. If unlink fails (e.g. dest
  // never existed), ignore — the retry will surface a meaningful error.
  try { await unlink(to); } catch {}
  await rename(from, to);
}

export function makeEmptySessionState() {
  return {
    status: /** @type {SessionStatus} */ ('pending'),
    prUrl: null,
    worktreePath: null,
    branch: null,
    startedAt: null,
    completedAt: null,
    attempt: 0,
    testExitCode: null,
    error: null,
  };
}

/** @param {string} runId */
export function makeFreshState(runId) {
  return /** @type {RunState} */ ({
    runId,
    createdAt: new Date().toISOString(),
    sessions: {},
  });
}

// ─── gh exponential backoff ──────────────────────────────────────────────────

/**
 * Run a `gh` mutation command with exponential backoff on rate-limit codes.
 * 3 attempts total (initial + 2 retries) at 5s/15s/45s. Retries only on 403/429.
 *
 * The sleeper is injectable for tests; the runner exec is also injectable so
 * we can validate retry behavior without spawning real gh.
 *
 * @param {string[]} args
 * @param {{ sleep?: (ms: number) => Promise<void>, exec?: typeof runProcess }} [deps]
 * @returns {Promise<{ exitCode: number; stdout: string; stderr: string; attempts: number }>}
 */
export async function ghWithBackoff(args, deps = {}) {
  const sleep = deps.sleep ?? ((ms) => new Promise(r => setTimeout(r, ms)));
  const exec = deps.exec ?? runProcess;
  let lastResult = null;
  for (let attempt = 0; attempt < GH_RETRY_DELAYS_MS.length; attempt++) {
    /** @type {{ exitCode: number; stdout: string; stderr: string }} */
    const result = await exec('gh', args);
    lastResult = result;
    if (result.exitCode === 0) {
      return { ...result, attempts: attempt + 1 };
    }
    const code = parseGhHttpCode(result.stderr) ?? parseGhHttpCode(result.stdout);
    if (code === null || !GH_RETRY_CODES.has(code)) {
      return { ...result, attempts: attempt + 1 };
    }
    if (attempt < GH_RETRY_DELAYS_MS.length - 1) {
      await sleep(GH_RETRY_DELAYS_MS[attempt]);
    }
  }
  return { ...lastResult, attempts: GH_RETRY_DELAYS_MS.length };
}

/** Extract HTTP status code from gh stderr/stdout. */
export function parseGhHttpCode(text) {
  if (!text) return null;
  // gh emits things like "HTTP 403:" or "HTTP/2.0 429" or "gh: ... (HTTP 429)"
  const m = text.match(/HTTP[\/\d.]*\s+(\d{3})/i) ?? text.match(/\((\d{3})\)/);
  return m ? parseInt(m[1], 10) : null;
}

// ─── Windows binary resolution ───────────────────────────────────────────────

/**
 * On Windows, Node 20+ refuses to `spawn` a `.cmd`/`.bat` file directly with
 * `shell: false` (EINVAL, post CVE-2024-27980). Using `shell: true` works
 * but concatenates args without quoting, which mangles anything with a
 * space (e.g. PR titles, multi-line bodies).
 *
 * The robust pattern is what cross-spawn does: resolve the bare command
 * to its absolute path with extension, and if it's a `.cmd`/`.bat`, wrap
 * with `cmd.exe /d /s /c` and pre-quote each arg per cmd's rules. The
 * result spawns with `shell: false` and arg boundaries are preserved.
 *
 * Cache the `where` lookup per command — `spawnSync` is non-trivial cost.
 *
 * @returns {{ cmd: string; args: string[] }} command + args ready for spawn
 */
const _binResolveCache = new Map();
export function resolveWindowsCommand(cmd, args) {
  // Bare command like `git`/`npm`/`gh`/`claude` — look it up with `where`.
  let resolvedPath = cmd;
  if (!cmd.includes(path.sep) && !cmd.includes('/')) {
    if (_binResolveCache.has(cmd)) {
      resolvedPath = _binResolveCache.get(cmd);
    } else {
      try {
        const r = spawnSync('where.exe', [cmd], { encoding: 'utf-8' });
        if (r.status === 0) {
          const lines = r.stdout.split(/\r?\n/).filter(Boolean);
          // Prefer .exe > .cmd > .bat (real binaries first).
          lines.sort((a, b) => {
            const w = (p) => /\.exe$/i.test(p) ? 0 : /\.cmd$/i.test(p) ? 1 : /\.bat$/i.test(p) ? 2 : 3;
            return w(a) - w(b);
          });
          resolvedPath = lines[0] || cmd;
        }
      } catch { /* fall through with bare cmd */ }
      _binResolveCache.set(cmd, resolvedPath);
    }
  }
  // .cmd/.bat shims need cmd.exe wrap; .exe and friends spawn directly.
  if (/\.(cmd|bat)$/i.test(resolvedPath)) {
    // Port of cross-spawn's escape — see https://github.com/moxystudio/node-cross-spawn
    // - The command path is only caret-escaped (no wrapping quotes) so cmd's
    //   parser treats it as one token; spaces in the path become `^ `.
    // - Each arg is quote-wrapped and then caret-escaped. CRT will dequote
    //   the wrapping `"` back to real argv on the called program's side.
    // - The whole line is wrapped in `"..."` so `cmd /s` strips them and
    //   parses the inner verbatim.
    const line = '"' + [escapeCmdCommand(resolvedPath), ...args.map(escapeCmdArgument)].join(' ') + '"';
    return {
      cmd: process.env.ComSpec || 'cmd.exe',
      args: ['/d', '/s', '/c', line],
      // Tell Node to pass these args verbatim to CreateProcess. Without
      // this Node would re-quote the line, breaking cmd's /s outer-strip.
      windowsVerbatimArguments: true,
    };
  }
  return { cmd: resolvedPath, args };
}

const _cmdMetaCharsRe = /([()\][%!^"`<>&|;, ])/g;
/** Cross-spawn escapeCommand — caret-escape metachars, no wrapping. */
export function escapeCmdCommand(cmd) {
  return String(cmd).replace(_cmdMetaCharsRe, '^$1');
}
/** Cross-spawn escapeArgument — CRT-quote then caret-escape metachars. */
export function escapeCmdArgument(arg) {
  let s = `${arg}`;
  s = s.replace(/(\\*)"/g, '$1$1\\"');   // escape embedded " + double preceding backslashes
  s = s.replace(/(\\*)$/, '$1$1');       // double trailing backslashes
  s = `"${s}"`;
  return s.replace(_cmdMetaCharsRe, '^$1');
}

// ─── Process exec helper ─────────────────────────────────────────────────────

/**
 * Spawn a process, capture stdout/stderr, return result. Inherits stdin only.
 * @param {string} cmd
 * @param {string[]} args
 * @param {{ cwd?: string, env?: NodeJS.ProcessEnv, input?: string, onStdout?: (chunk: string) => void }} [opts]
 * @returns {Promise<{ exitCode: number; stdout: string; stderr: string }>}
 */
export function runProcess(cmd, args, opts = {}) {
  return new Promise((resolve) => {
    // Windows binary resolution — see resolveWindowsCommand for the why.
    // Outside Windows we spawn the command directly with shell:false.
    const resolved = process.platform === 'win32'
      ? resolveWindowsCommand(cmd, args)
      : { cmd, args };
    const child = spawn(resolved.cmd, resolved.args, {
      cwd: opts.cwd,
      env: opts.env ?? process.env,
      stdio: ['pipe', 'pipe', 'pipe'],
      shell: false,
      windowsVerbatimArguments: resolved.windowsVerbatimArguments ?? false,
    });
    let stdout = '';
    let stderr = '';
    child.stdout?.on('data', (d) => {
      const s = d.toString();
      stdout += s;
      opts.onStdout?.(s);
    });
    child.stderr?.on('data', (d) => { stderr += d.toString(); });
    child.on('error', (err) => {
      resolve({ exitCode: -1, stdout, stderr: stderr + `\nspawn error: ${err.message}` });
    });
    child.on('close', (code) => {
      resolve({ exitCode: code ?? -1, stdout, stderr });
    });
    if (opts.input !== undefined) {
      child.stdin?.write(opts.input);
      child.stdin?.end();
    } else {
      child.stdin?.end();
    }
  });
}

// ─── [MANUAL] AC PR body template ────────────────────────────────────────────

/**
 * @param {{ id: string; name?: string; checkpoint: string; manualAcs: { id: string; text: string }[] }} session
 */
export function formatPrBody(session) {
  const lines = [];
  lines.push(`## Checkpoint`);
  lines.push('');
  lines.push(session.checkpoint);
  lines.push('');
  if (session.manualAcs && session.manualAcs.length > 0) {
    lines.push(`## Manual sign-off required`);
    lines.push('');
    lines.push('The following acceptance criteria cannot be automatically verified. The reviewer must tick each box before merging.');
    lines.push('');
    for (const ac of session.manualAcs) {
      lines.push(`- [ ] [${ac.id}] ${ac.text}`);
    }
    lines.push('');
  }
  lines.push(`---`);
  lines.push(`Generated by HyperSpeed build runner for session **${session.id}**.`);
  return lines.join('\n');
}

// ─── Failure report ──────────────────────────────────────────────────────────

/**
 * @param {{ wave: { kind: string; phase: number | string }; failures: Array<{ sessionId: string; state: SessionState; stdoutTail: string }> }} input
 */
export function formatFailureReport(input) {
  return {
    wave: input.wave,
    generatedAt: new Date().toISOString(),
    failures: input.failures.map(f => ({
      sessionId: f.sessionId,
      status: f.state.status,
      prUrl: f.state.prUrl,
      testExitCode: f.state.testExitCode,
      worktreePath: f.state.worktreePath,
      error: f.state.error,
      stdoutTail: f.stdoutTail,
    })),
  };
}

export function tailLines(text, n = STDOUT_TAIL_LINES) {
  if (!text) return '';
  const lines = text.split(/\r?\n/);
  return lines.slice(-n).join('\n');
}

// ─── Worktree lifecycle ──────────────────────────────────────────────────────

/** @returns {Promise<{ ok: boolean; stderr: string }>} */
export async function worktreeAdd(repoRoot, worktreePath, branch, baseBranch = 'main', exec = runProcess) {
  // Create a new branch from base; -B re-creates if it exists (resume case).
  const res = await exec('git', ['worktree', 'add', '-B', branch, worktreePath, baseBranch], { cwd: repoRoot });
  return { ok: res.exitCode === 0, stderr: res.stderr };
}

export async function worktreeRemove(repoRoot, worktreePath, exec = runProcess) {
  const res = await exec('git', ['worktree', 'remove', '--force', worktreePath], { cwd: repoRoot });
  return { ok: res.exitCode === 0, stderr: res.stderr };
}

// ─── Manifest loader ─────────────────────────────────────────────────────────

export async function loadManifest(manifestPath = MANIFEST_PATH) {
  const raw = await fs.readFile(manifestPath, 'utf-8');
  const parsed = JSON.parse(raw);
  if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.waves)) {
    throw new Error(`Invalid manifest at ${manifestPath} — expected version: 1 and waves[].`);
  }
  return parsed;
}

// ─── CLI parsing ─────────────────────────────────────────────────────────────

export function parseArgs(argv) {
  const out = { dryRun: false, wave: null, help: false, requireQualityScore: false, qualityThreshold: 20 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--dry-run') out.dryRun = true;
    else if (a === '--wave') {
      const v = argv[++i];
      const n = parseInt(v, 10);
      if (Number.isNaN(n)) throw new Error(`--wave expects an integer, got "${v}"`);
      out.wave = n;
    } else if (a === '-h' || a === '--help') {
      out.help = true;
    } else if (a === '--require-quality-score') {
      out.requireQualityScore = true;
      // Optional numeric threshold follows the flag.
      const next = argv[i + 1];
      if (next !== undefined && /^\d+$/.test(next)) {
        out.qualityThreshold = parseInt(next, 10);
        i++;
      }
    } else if (a.startsWith('--')) {
      throw new Error(`Unknown flag: ${a}`);
    }
  }
  return out;
}

// ─── Brief quality gate (#37 ↔ #39) ──────────────────────────────────────────

/**
 * Read the JSON sidecar emitted by `hyperspeed --score-briefs` (Track C, #39).
 * Returns:
 *   - { ok: true, summary } when every brief scored ≥ threshold and there are no errors,
 *   - { ok: false, reason } when the report is missing, malformed, or any brief is below
 *     threshold / errored — the runner refuses to fire in that case.
 *
 * `threshold` overrides whatever was baked into the report at scoring time.
 *
 * Default location: `<build-plan-dir>/brief-quality-report.json` alongside the markdown
 * report. Pass `summaryPath` explicitly in tests.
 */
export async function checkQualityGate(threshold, summaryPath = path.join(SCRIPT_DIR, 'brief-quality-report.json')) {
  let raw;
  try {
    raw = await fs.readFile(summaryPath, 'utf-8');
  } catch {
    return {
      ok: false,
      reason: `--require-quality-score is set but ${path.basename(summaryPath)} was not found. ` +
        `Run \`hyperspeed --score-briefs <build-plan-dir>\` first.`,
    };
  }
  let summary;
  try { summary = JSON.parse(raw); }
  catch (e) {
    return { ok: false, reason: `Quality summary at ${summaryPath} is not valid JSON: ${e.message}` };
  }
  if (!summary || !Array.isArray(summary.briefs)) {
    return { ok: false, reason: `Quality summary at ${summaryPath} is missing a briefs[] array.` };
  }
  const below = summary.briefs.filter(b => typeof b.total === 'number' && b.total < threshold);
  const errors = summary.briefs.filter(b => b.error);
  if (below.length > 0 || errors.length > 0) {
    const belowMsg = below.length
      ? `${below.length} brief(s) below threshold ${threshold}: ${below.map(b => `${b.briefId}=${b.total}`).join(', ')}`
      : '';
    const errMsg = errors.length
      ? `${errors.length} brief(s) errored: ${errors.map(b => b.briefId).join(', ')}`
      : '';
    return { ok: false, reason: [belowMsg, errMsg].filter(Boolean).join(' · ') };
  }
  return { ok: true, summary };
}

const HELP = `HyperSpeed Build Plan Runner

Usage:
  node build-plan/run-build.mjs                      Execute all waves end-to-end
  node build-plan/run-build.mjs --wave N             Execute a single wave (used by run-build.md)
  node build-plan/run-build.mjs --dry-run            Print the wave plan and exit
  node build-plan/run-build.mjs --require-quality-score [N]
                                                    Gate: refuse to fire unless every brief in
                                                    brief-quality-report.json scored ≥ N (default 20).
                                                    Generate that report with: hyperspeed --score-briefs <build-plan-dir>

Environment:
  HS_CLAUDE_CLI         Override claude CLI binary (default: claude)
  HS_CLAUDE_CLI_ARGS    Override claude CLI args (default: "--dangerously-skip-permissions -p")
  HS_REPO_ROOT          Override repo root for worktree creation (default: cwd)

See build-plan/README.md for required out-of-band setup (GH_TOKEN, CI workflow,
branch-protection rule on main).
`;

// ─── Dry-run printer ─────────────────────────────────────────────────────────

export function formatDryRunPlan(manifest) {
  const lines = [];
  lines.push(`Run manifest: ${manifest.waves.length} waves, integrationCmd="${manifest.integrationCmd}"`);
  for (const w of manifest.waves) {
    if (w.kind === 'feature') {
      lines.push(`  [feature]    phase ${w.phase} — ${w.sessions.length} session(s)`);
      for (const s of w.sessions) {
        const manualCount = (s.manualAcs ?? []).length;
        lines.push(`     • ${s.id}  test=${s.test.cmd}  manualACs=${manualCount}  brief=${s.brief}`);
      }
    } else {
      lines.push(`  [integration] ${w.phase} — cmd: ${w.test.cmd}`);
    }
  }
  return lines.join('\n');
}

// ─── Wave / session execution ────────────────────────────────────────────────

/** @param {RunState} state */
function ensureSessionEntry(state, id) {
  if (!state.sessions[id]) state.sessions[id] = makeEmptySessionState();
  return state.sessions[id];
}

/**
 * Reconcile state against the manifest before running:
 *   - Existing `done` sessions: skip on rerun.
 *   - Existing `failed` / `interrupted` / `in_progress` sessions: force-remove
 *     their worktree (if any) so the next attempt can recreate it cleanly.
 */
export async function reconcileState(state, manifest, deps = {}) {
  const exec = deps.exec ?? runProcess;
  const repoRoot = deps.repoRoot ?? REPO_ROOT;
  for (const wave of manifest.waves) {
    if (wave.kind !== 'feature') continue;
    for (const s of wave.sessions) {
      const cur = ensureSessionEntry(state, s.id);
      if (cur.status !== 'done' && cur.worktreePath) {
        await worktreeRemove(repoRoot, cur.worktreePath, exec);
      }
    }
  }
}

/**
 * Execute a feature wave with Promise.all over sessions.
 * @returns {Promise<{ ok: boolean; failures: Array<{ sessionId: string; state: SessionState; stdoutTail: string }> }>}
 */
export async function runFeatureWave(wave, manifest, state, deps = {}) {
  const log = deps.log ?? console.log;
  log(`\n▶ Feature wave (phase ${wave.phase}) — ${wave.sessions.length} session(s)`);
  const results = await Promise.all(
    wave.sessions.map(s => runSession(s, state, deps)),
  );
  const failures = [];
  for (let i = 0; i < results.length; i++) {
    if (!results[i].ok) {
      failures.push({
        sessionId: wave.sessions[i].id,
        state: state.sessions[wave.sessions[i].id],
        stdoutTail: results[i].stdoutTail,
      });
    }
  }
  await deps.saveState?.(state);
  return { ok: failures.length === 0, failures };
}

/**
 * Execute an integration wave: a single command run.
 * @returns {Promise<{ ok: boolean; exitCode: number; stdoutTail: string }>}
 */
export async function runIntegrationWave(wave, deps = {}) {
  const exec = deps.exec ?? runProcess;
  const log = deps.log ?? console.log;
  const repoRoot = deps.repoRoot ?? REPO_ROOT;
  log(`\n▶ Integration gate (${wave.phase}) — ${wave.test.cmd}`);
  // Execute via shell to honor compound commands in test.cmd (e.g. `npm run test:integration`).
  const [cmd, ...args] = parseShellCmd(wave.test.cmd);
  const res = await exec(cmd, args, { cwd: repoRoot });
  return {
    ok: res.exitCode === 0,
    exitCode: res.exitCode,
    stdoutTail: tailLines(res.stdout + '\n' + res.stderr),
  };
}

/** Naive shell tokenizer: handles unquoted args + simple "double quoted" args. Sufficient for npm/pnpm/yarn commands. */
export function parseShellCmd(cmd) {
  const tokens = [];
  const re = /"([^"]*)"|(\S+)/g;
  let m;
  while ((m = re.exec(cmd)) !== null) tokens.push(m[1] ?? m[2]);
  return tokens;
}

/**
 * Execute a single session: worktree → claude → test → PR.
 * @returns {Promise<{ ok: boolean; stdoutTail: string }>}
 */
export async function runSession(sessionEntry, state, deps = {}) {
  const exec = deps.exec ?? runProcess;
  const repoRoot = deps.repoRoot ?? REPO_ROOT;
  const log = deps.log ?? console.log;
  const cur = ensureSessionEntry(state, sessionEntry.id);

  if (cur.status === 'done') {
    log(`  ✓ ${sessionEntry.id} — already done (PR: ${cur.prUrl})`);
    return { ok: true, stdoutTail: '' };
  }

  cur.attempt += 1;
  cur.status = 'in_progress';
  cur.startedAt = new Date().toISOString();
  cur.error = null;
  cur.testExitCode = null;
  await deps.saveState?.(state);

  const branch = `bp/${state.runId}/${sessionEntry.id}`;
  const worktreePath = path.join(repoRoot, '.bp-worktrees', state.runId, sessionEntry.id);
  cur.branch = branch;
  cur.worktreePath = worktreePath;

  log(`  → ${sessionEntry.id} starting (worktree: ${worktreePath})`);

  // 1) Create worktree on new branch.
  const wt = await worktreeAdd(repoRoot, worktreePath, branch, 'main', exec);
  if (!wt.ok) {
    cur.status = 'failed';
    cur.error = `worktree add failed: ${wt.stderr.slice(0, 500)}`;
    cur.completedAt = new Date().toISOString();
    return { ok: false, stdoutTail: cur.error };
  }

  // 2) Read brief content; brief path is relative to the build-plan dir.
  const briefAbs = path.join(SCRIPT_DIR, sessionEntry.brief);
  let briefContent = '';
  try { briefContent = await fs.readFile(briefAbs, 'utf-8'); }
  catch (e) {
    cur.status = 'failed';
    cur.error = `brief read failed: ${e.message}`;
    cur.completedAt = new Date().toISOString();
    return { ok: false, stdoutTail: cur.error };
  }

  // 3) Spawn claude CLI with the brief as the SOLE context (passed via stdin to
  //    avoid argv length limits). The worktree is the cwd — claude sees the
  //    session's repo only, not the specs.
  const claudeArgs = [...CLAUDE_CLI_ARGS];
  const claudeRes = await exec(CLAUDE_CLI, claudeArgs, { cwd: worktreePath, input: briefContent });
  const claudeStdoutTail = tailLines(claudeRes.stdout + '\n' + claudeRes.stderr);

  // 3b) Commit anything claude left uncommitted. The brief instructs claude
  //     to commit, but real claude (vs the fake-claude shim) sometimes makes
  //     file changes without committing — in which case `git push` succeeds
  //     vacuously and `gh pr create` rejects "No commits between main and
  //     <branch>". Auto-committing here closes that gap and surfaces the
  //     legitimate failure (no changes at all) as a clear session error.
  //     Track D finding (#40 Session 2).
  await exec('git', ['add', '-A'], { cwd: worktreePath });
  const diffRes = await exec('git', ['diff', '--cached', '--quiet'], { cwd: worktreePath });
  if (diffRes.exitCode === 0) {
    // No staged changes — also nothing in HEAD relative to main means claude produced nothing.
    const aheadRes = await exec('git', ['rev-list', '--count', 'main..HEAD'], { cwd: worktreePath });
    const ahead = parseInt((aheadRes.stdout || '').trim(), 10) || 0;
    if (ahead === 0) {
      cur.status = 'failed';
      cur.error = `claude produced no commits and no uncommitted changes in worktree (brief: ${sessionEntry.brief})`;
      cur.completedAt = new Date().toISOString();
      return { ok: false, stdoutTail: `[claude]\n${claudeStdoutTail}\n[runner]\n${cur.error}` };
    }
  } else {
    // Stage exists — commit it for claude.
    const commitRes = await exec('git', [
      '-c', 'user.email=hyperspeed-runner@local',
      '-c', 'user.name=hyperspeed-runner',
      'commit', '-m', `${sessionEntry.id}: autonomous build (auto-commit by runner)`,
    ], { cwd: worktreePath });
    if (commitRes.exitCode !== 0) {
      cur.status = 'failed';
      cur.error = `auto-commit failed: ${tailLines(commitRes.stderr, 10)}`;
      cur.completedAt = new Date().toISOString();
      return { ok: false, stdoutTail: cur.error };
    }
  }

  // 4) Run the independent test in the worktree.
  const [testCmd, ...testArgs] = parseShellCmd(sessionEntry.test.cmd);
  const testRes = await exec(testCmd, testArgs, { cwd: worktreePath });
  cur.testExitCode = testRes.exitCode;

  if (testRes.exitCode !== 0) {
    // Local test failed — push and open PR anyway. Branch protection on
    // `main` requires the `session-tests` CI check to pass before merge,
    // and CI runs on ubuntu-latest with a real Docker + Python + Postgres
    // env, so it's the authoritative gate. The local test step on Windows
    // is too fragile (WSL vs Git Bash shell selection, Docker socket
    // mounts, OneDrive path locks, etc.) to be trusted as a hard gate.
    const testTail = tailLines(testRes.stdout + '\n' + testRes.stderr);
    log(`  ⚠ ${sessionEntry.id} — local test failed exit ${testRes.exitCode}; pushing anyway (CI will gate). Tail:\n${testTail}`);
    cur.error = `Local test failed with exit ${testRes.exitCode} (CI session-tests is the gate; local advisory only)`;
  }

  // 5) Push branch + open PR.
  const pushRes = await exec('git', ['push', '-u', 'origin', branch], { cwd: worktreePath });
  if (pushRes.exitCode !== 0) {
    cur.status = 'failed';
    cur.error = `git push failed: ${tailLines(pushRes.stderr, 10)}`;
    cur.completedAt = new Date().toISOString();
    return { ok: false, stdoutTail: cur.error };
  }

  const prBody = formatPrBody({
    id: sessionEntry.id,
    checkpoint: sessionEntry.checkpoint,
    manualAcs: sessionEntry.manualAcs ?? [],
  });
  // Write the body to a temp file and pass --body-file. Inline --body
  // is fragile across platforms once shell wrapping enters the picture
  // (Windows .cmd shim resolution requires shell:true, which mangles
  // multi-line / quoted args). --body-file sidesteps the whole issue.
  // Surfaced by tests/e2e/run-canary.mjs Track D Session 2.
  const bodyFile = path.join(worktreePath, '.bp-pr-body.md');
  await fs.writeFile(bodyFile, prBody, 'utf-8');
  const prRes = await ghWithBackoff(
    ['pr', 'create', '--head', branch, '--base', 'main',
     '--title', `${sessionEntry.id}: autonomous build`,
     '--body-file', bodyFile],
    { exec },
  );
  // Body file is inside the worktree, which gets removed below on success;
  // on failure we leave the worktree for inspection so the file persists too.
  if (prRes.exitCode !== 0) {
    cur.status = 'failed';
    cur.error = `gh pr create failed after ${prRes.attempts} attempt(s): ${tailLines(prRes.stderr, 10)}`;
    cur.completedAt = new Date().toISOString();
    return { ok: false, stdoutTail: cur.error };
  }

  const prUrl = (prRes.stdout.match(/https?:\/\/\S+/) ?? [null])[0];
  cur.prUrl = prUrl;
  cur.status = 'done';
  cur.completedAt = new Date().toISOString();

  // 6) Best-effort cleanup of worktree on success.
  await worktreeRemove(repoRoot, worktreePath, exec);

  log(`  ✓ ${sessionEntry.id} — PR ${prUrl}`);
  return { ok: true, stdoutTail: '' };
}

// ─── Summary table ───────────────────────────────────────────────────────────

export function formatSummaryTable(state) {
  const rows = [['Session', 'Status', 'Attempts', 'Test exit', 'PR']];
  for (const [id, s] of Object.entries(state.sessions)) {
    rows.push([id, s.status, String(s.attempt), s.testExitCode === null ? '—' : String(s.testExitCode), s.prUrl ?? '—']);
  }
  const widths = rows[0].map((_, i) => Math.max(...rows.map(r => r[i].length)));
  return rows.map(r => r.map((c, i) => c.padEnd(widths[i])).join('  ')).join('\n');
}

// ─── SIGINT handler ──────────────────────────────────────────────────────────

function installInterruptHandler(state, saveStateFn) {
  let cleaningUp = false;
  const handle = async (sig) => {
    if (cleaningUp) return;
    cleaningUp = true;
    console.error(`\n${sig} received — marking in-progress sessions interrupted and cleaning worktrees...`);
    for (const [, s] of Object.entries(state.sessions)) {
      if (s.status === 'in_progress') {
        s.status = 'interrupted';
        s.completedAt = new Date().toISOString();
        if (s.worktreePath) {
          await worktreeRemove(REPO_ROOT, s.worktreePath).catch(() => {});
        }
      }
    }
    try { await saveStateFn(state); } catch {}
    process.exit(130);
  };
  process.on('SIGINT', () => handle('SIGINT'));
  process.on('SIGTERM', () => handle('SIGTERM'));
}

// ─── Main ────────────────────────────────────────────────────────────────────

async function main() {
  let args;
  try { args = parseArgs(process.argv.slice(2)); }
  catch (e) {
    console.error(e.message);
    process.exit(2);
  }
  if (args.help) {
    console.log(HELP);
    return;
  }

  const manifest = await loadManifest();

  if (args.requireQualityScore) {
    const gate = await checkQualityGate(args.qualityThreshold);
    if (!gate.ok) {
      console.error(`✗ Brief-quality gate refused to start runner: ${gate.reason}`);
      process.exit(1);
    }
    console.log(`✓ Brief-quality gate passed (threshold ${args.qualityThreshold}).`);
  }

  if (args.dryRun) {
    console.log(formatDryRunPlan(manifest));
    return;
  }

  let state = await loadState();
  if (!state) {
    const runId = new Date().toISOString().replace(/[^0-9]/g, '').slice(0, 14);
    state = makeFreshState(runId);
  }
  installInterruptHandler(state, saveState);

  await reconcileState(state, manifest);
  await saveState(state);

  const waves = args.wave === null
    ? manifest.waves.map((w, i) => ({ w, idx: i }))
    : [{ w: manifest.waves[args.wave], idx: args.wave }];

  if (args.wave !== null && !manifest.waves[args.wave]) {
    console.error(`--wave ${args.wave} out of range (manifest has ${manifest.waves.length} waves)`);
    process.exit(2);
  }

  for (const { w, idx } of waves) {
    if (w.kind === 'feature') {
      const res = await runFeatureWave(w, manifest, state, { saveState });
      if (!res.ok) {
        const report = formatFailureReport({ wave: { kind: w.kind, phase: w.phase }, failures: res.failures });
        const reportPath = path.join(SCRIPT_DIR, `wave-${idx}-failure-report.json`);
        await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf-8');
        console.error(`\n✗ Feature wave ${idx} failed. Report: ${reportPath}\n`);
        console.error(formatSummaryTable(state));
        process.exit(1);
      }
    } else {
      const res = await runIntegrationWave(w);
      if (!res.ok) {
        const report = {
          wave: { kind: w.kind, phase: w.phase, cmd: w.test.cmd },
          generatedAt: new Date().toISOString(),
          exitCode: res.exitCode,
          stdoutTail: res.stdoutTail,
        };
        const reportPath = path.join(SCRIPT_DIR, `wave-${idx}-failure-report.json`);
        await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf-8');
        console.error(`\n✗ Integration gate ${w.phase} failed (exit ${res.exitCode}). Report: ${reportPath}\n`);
        process.exit(1);
      }
    }
  }

  console.log(`\n✓ All waves complete.`);
  console.log(formatSummaryTable(state));
}

// CLI guard — only run main() when invoked directly (not when imported by tests).
const isMain = (() => {
  try { return import.meta.url === `file://${process.argv[1]}` || import.meta.url === fileURLToPath(import.meta.url); }
  catch { return false; }
})();

// Normalize: on Windows, argv[1] may have different slashes/drive case from import.meta.url.
const argvUrl = (() => {
  try { return fssync.realpathSync(process.argv[1] || ''); } catch { return process.argv[1] || ''; }
})();
const selfUrl = (() => {
  try { return fssync.realpathSync(fileURLToPath(import.meta.url)); } catch { return ''; }
})();

if (isMain || (argvUrl && selfUrl && argvUrl === selfUrl)) {
  main().catch(err => {
    console.error(err?.stack || String(err));
    process.exit(1);
  });
}
