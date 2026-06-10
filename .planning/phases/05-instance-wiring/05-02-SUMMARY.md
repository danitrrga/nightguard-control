---
phase: 05-instance-wiring
plan: 02
subsystem: hooks
tags: [powershell, claude-code-hook, adapter, watchdog, deploy, fail-closed, stayfree, integrity-baseline]

# Dependency graph
requires:
  - phase: 05-instance-wiring
    plan: 01
    provides: NIGHTGUARD_DIR (User scope) set + LifeOS/nightguard instance (config.yaml, sanctioned, guard.json, .guardkey) verifying in Rust+PS
  - phase: 03-guard
    provides: nightguard_guard.ps1 host-agnostic oracle (verdict JSON + exit 0/1) + verify_hook_integrity.ps1 SHA256 baseline
provides:
  - nightguard_adapter.ps1 — the Claude-Code UserPromptSubmit seam translating guard verdict to block/allow (stderr + exit 2)
  - nightguard_watchdog.ps1 — rewritten StayFree liveness loop reading the single canonical config via NIGHTGUARD_DIR
  - scripts/deploy/install_nightguard.ps1 — byte-exact deploy + repo-source baseline re-stamp + staged (uncalled) watchdog re-register
  - Confirmed Claude-Code block contract (stderr + exit 2; exit 1 / {continue:false} rejected as fail-open on this install)
affects: [05-03-PLAN, cutover, instance-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Host-adapter seam: a thin PowerShell hook fronts the host-agnostic guard oracle, owning the Claude-Code block protocol and the allow-command pass, sourcing all butler strings from the single canonical config"
    - "Deploy = byte-exact [IO.File]::Copy from repo source into LifeOS/hooks + repo-source integrity re-stamp; live wiring (settings.json swap, task re-register/Start) staged as uncalled functions for the gated cutover"

key-files:
  created:
    - "scripts/guard/nightguard_adapter.ps1 (repo source; byte-copied to LifeOS/hooks at deploy)"
    - "scripts/guard/nightguard_watchdog.ps1 (repo source; byte-copied to LifeOS/hooks at deploy)"
    - "scripts/deploy/install_nightguard.ps1 (deploy helper)"
    - "C:/Users/20252128/dev/Projects/LifeOS/hooks/nightguard_adapter.ps1 (INERT deploy-target copy)"
    - "C:/Users/20252128/dev/Projects/LifeOS/hooks/nightguard_watchdog.ps1 (INERT deploy-target copy)"
  modified:
    - ".gitattributes (pin scripts/deploy/*.ps1 -text)"

key-decisions:
  - "A2 RESOLVED: the Claude-Code UserPromptSubmit BLOCK contract on this install is `stderr + exit 2`, empirically confirmed against the currently-live curfew_guard.ps1 (wired in settings.json UserPromptSubmit today). exit 1 and {continue:false} JSON were REJECTED: on this install exit 1 is a NON-blocking (fail-OPEN) error, so the RESEARCH D-02 text ('exit-1 -> {continue:false}') is wrong for this version. The adapter translates guard-deny (guard exit 1) into adapter exit 2 + stderr, and EVERY fail-closed path exits 2 (never 1)."
  - "A5/Pitfall-5 disposition: re-stamp the integrity baseline at REPO-SOURCE scope (run the repo verify_hook_integrity.ps1 -Update against scripts/guard + scripts/interop where $repoRoot=$here\\..\\.. resolves). Sound because deployed copies are byte-identical to the re-stamped repo bytes (guaranteed by [IO.File]::Copy + the .gitattributes -text pins). Parameterizing the verifier for the deployed layout was deferred as unnecessary."
  - "Adapter + watchdog are authored as repo-source files under scripts/guard/ (alongside the guard they front, already -text pinned) so they are version-controlled AND are the byte-copy source the deploy script reads — mirroring how guard/verifier/interop are repo-source + deploy-copied. The LifeOS/hooks copies are inert deploy outputs, untracked here (same as Plan 01's instance data files)."

patterns-established:
  - "Adapter-fronts-oracle: the guard stays host-agnostic (verdict JSON + exit); the host adapter is the single place that knows the Claude-Code block protocol and owns the allow-command pass + butler-message presentation."

requirements-completed: [WIRE-01]

# Metrics
duration: ~53min
completed: 2026-06-10
---

# Phase 5 Plan 02: Deployable PowerShell Artifacts Summary

**Built the three deployable hook artifacts the cutover needs — the Claude-Code adapter (guard-verdict translation with the empirically-confirmed `stderr + exit 2` block contract, `/shutdown` allow-pass, config-sourced butler messages, fail-closed on any error), the rewritten StayFree watchdog (reads the single canonical config via NIGHTGUARD_DIR, stale `~/.claude` path removed), and a byte-exact `install_nightguard.ps1` deploy script (repo-source integrity re-stamp + staged-but-uncalled watchdog re-register) — all 5.1-clean and WITHOUT wiring anything live.**

## Performance

- **Duration:** ~53 min
- **Completed:** 2026-06-10
- **Tasks:** 3 (1 pre-resolved checkpoint + 2 auto)
- **Files created:** 3 repo-source scripts + 2 inert LifeOS/hooks deploy copies; 1 modified (.gitattributes)

## Accomplishments

- **Task 1 (A2) resolved by the orchestrator, not stopped for.** The live Claude-Code UserPromptSubmit BLOCK contract was empirically confirmed against the currently-active `curfew_guard.ps1` (wired in settings.json today): **block = write message to stderr via `[Console]::Error.WriteLine`, then `exit 2`**; allow = `exit 0`. `exit 1` / `{continue:false}` were rejected — on this install `exit 1` is a non-blocking (fail-OPEN) error, contradicting the RESEARCH D-02 text. The adapter uses the confirmed contract throughout.
- **nightguard_adapter.ps1:** resolves `$env:NIGHTGUARD_DIR` fail-closed (verbatim guard stanza, never `$PSScriptRoot`); reads the prompt once and runs the `/shutdown` allow-command pass BEFORE invoking the guard (A4 — the published guard does not read `allow_commands`); invokes the sibling `nightguard_guard.ps1`, captures exit + verdict JSON; translates exit 0 -> allow, exit 1 + reason {curfew/clock tamper/ntp unreachable} -> block with the matching config butler message ({start}/{end} substituted), any guard throw / non-{0,1} / no-JSON -> fail-closed block. Whole body wrapped in try/catch + a terminal defensive block, so ANY exception emits `stderr + exit 2` (Pitfall 1 / T-05-07). All butler strings read from `config.yaml` — none hardcoded (T-05-11).
- **nightguard_watchdog.ps1:** rewrote the legacy watchdog keeping the `-Loop`/while/Start-Sleep shape, the `Get-Process -Name StayFree` probe, the `explorer.exe shell:AppsFolder\...` UWP relaunch, and the minimal `apps[]` parser — but replaced the stale `~/.claude\nightguard\config.yaml` path (the D-05 root cause) and the log path with the `NIGHTGUARD_DIR` fail-closed stanza. The `watchdog.enabled` gate now reads the canonical `enabled:true`, so it proceeds and relaunches StayFree (the WIRE-01 proof-case).
- **scripts/deploy/install_nightguard.ps1:** `[IO.File]::Copy` byte-exact deploy of guard+verifier+baseline+adapter+watchdog into LifeOS/hooks (never `Set-Content`); preserves the `hooks/interop/` sibling (Pitfall 4); re-stamps the baseline at repo-source scope with the A5/Pitfall-5 disposition documented inline; defines a `Register-NightguardWatchdog` function that is DELIBERATELY NOT CALLED (Plan 03 fires it post-gate); documents inline that the settings.json swap + task Start are deferred to Plan 03 (D-11).
- **Nothing wired live (verified):** live `curfew_guard.ps1` unchanged (May 24), `settings.json` still references `curfew_guard.ps1` with 0 adapter refs, the `NightguardWatchdog` task still points at the legacy `nightguard_app_watchdog.ps1`, and the LifeOS/nightguard instance files were untouched.

## Task Commits

1. **Task 2: nightguard_adapter.ps1 (Claude-Code seam)** — `7dc61ec` (feat)
2. **Task 3: rewrite watchdog + install_nightguard deploy script** — `350c73c` (feat)
3. **(Rule 3 follow-on) pin scripts/deploy/*.ps1 -text** — `baa17a1` (chore)

**Plan metadata:** this commit (docs: complete plan)

## Files Created/Modified

- `scripts/guard/nightguard_adapter.ps1` — NEW. The Claude-Code UserPromptSubmit seam. Repo source; the deploy script byte-copies it into LifeOS/hooks. Confirmed block contract baked in (stderr + exit 2).
- `scripts/guard/nightguard_watchdog.ps1` — NEW. Rewritten StayFree watchdog reading the canonical config via NIGHTGUARD_DIR. Repo source; deploy byte-copies it into LifeOS/hooks.
- `scripts/deploy/install_nightguard.ps1` — NEW. Byte-exact deploy helper + repo-source baseline re-stamp + staged (uncalled) NightguardWatchdog re-register. Settings.json swap + task Start deferred to Plan 03.
- `C:/Users/20252128/dev/Projects/LifeOS/hooks/nightguard_adapter.ps1` — INERT deploy-target copy (byte-identical to the repo source). NOT referenced by settings.json. Untracked here (lives outside the repo, same as Plan 01 instance files).
- `C:/Users/20252128/dev/Projects/LifeOS/hooks/nightguard_watchdog.ps1` — INERT deploy-target copy. NOT yet pointed at by the NightguardWatchdog task. Untracked here.
- `.gitattributes` — added `scripts/deploy/*.ps1 -text` pin (mirrors the guard/interop pins) so the install script stays LF byte-stable.

## Verification Evidence (all PASS)

- **Parse (PS 5.1 scriptblock-create):** adapter PARSE OK; watchdog (LifeOS + repo) + install all PARSE OK.
- **ASCII-clean:** byte-level check — adapter / watchdog / install each have 0 non-ASCII bytes.
- **Adapter greps:** contains `$env:NIGHTGUARD_DIR` (7x) + 1 fail-closed throw; references `message` / `tamper_message` (3x) / `offline_message` (9x) read from the parsed config (no hardcoded butler literals); `allow_commands` pass present (exits 0 on `/shutdown` match before the guard); all `exit 1` occurrences are in comments documenting the rejection — every block path uses `exit 2`.
- **Watchdog greps:** `$env:NIGHTGUARD_DIR` (4x) + fail-closed throw; `Get-Process` (2x) + `StayFree` (7x) present; the stale `\.claude\nightguard\config.yaml` literal returns 0 after stripping comments (gone).
- **Install greps:** `[IO.File]::Copy` (4x) present; 0 non-comment `Set-Content`; `hooks/interop` sibling target referenced; `Register-ScheduledTask` + `NightguardWatchdog` + `nightguard_watchdog.ps1` + `Plan 03` deferral note all present; A5/Pitfall-5 disposition documented.
- **Nothing-live-wired:** curfew_guard.ps1 LastWriteTime = May 24 (unchanged); settings.json adapter refs = 0, curfew_guard refs = 1; NightguardWatchdog task Arguments still `...\nightguard_app_watchdog.ps1 -Loop`.

## Decisions Made

- See key-decisions in frontmatter: A2 confirmed as `stderr + exit 2` (exit 1 / {continue:false} rejected as fail-open on this install); A5/Pitfall-5 resolved as repo-source baseline re-stamp; adapter+watchdog authored as repo-source under `scripts/guard/` with inert deploy copies in LifeOS/hooks.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adapter + watchdog authored as repo-source files, not only at the LifeOS/hooks deploy target**
- **Found during:** Task 2 commit attempt (the LifeOS/hooks path is outside this git repo and cannot be committed).
- **Issue:** The plan's `files_modified` named the adapter and watchdog ONLY at the LifeOS/hooks deploy target. But (a) this repo is the publishable product (the artifacts must be version-controlled), and (b) Task 3's deploy script must byte-copy them FROM a repo source. With no repo source they would be untrackable and undeployable — a blocking gap.
- **Fix:** Authored both as repo-source files under `scripts/guard/` (alongside the guard they front; already `-text` pinned for byte-stability), committed them, and the deploy script byte-copies them into LifeOS/hooks — mirroring exactly how guard/verifier/interop are repo-source + deploy-copied. The LifeOS/hooks copies remain as inert deploy outputs (untracked, like Plan 01's instance data files).
- **Files modified:** scripts/guard/nightguard_adapter.ps1, scripts/guard/nightguard_watchdog.ps1.
- **Commits:** 7dc61ec, 350c73c.

**2. [Rule 3 - Blocking] Pinned scripts/deploy/*.ps1 -text**
- **Found during:** Task 3 commit (git warned LF would be replaced by CRLF for install_nightguard.ps1; the existing -text pins only cover scripts/guard + scripts/interop).
- **Issue:** The new scripts/deploy/ dir had no autocrlf protection; an autocrlf checkout could churn the install script's line endings.
- **Fix:** Added `scripts/deploy/*.ps1 -text` to .gitattributes (mirrors the guard/interop pins) and renormalized.
- **Files modified:** .gitattributes.
- **Commit:** baa17a1.

## Issues Encountered

None blocking. The `git-bash` `grep -P` could not run in the active locale; the ASCII verification was done at byte level via PowerShell instead (0 non-ASCII bytes in all three scripts).

## Known Stubs

None. The `Register-NightguardWatchdog` function in install_nightguard.ps1 is intentionally defined-but-uncalled (a STAGED live-wiring action), not a stub — it is complete and is invoked by Plan 03 behind the D-11 gate. Documented inline as deferred.

## User Setup Required

None — no live wiring in this plan. Plan 03 (behind the D-11 verify gate) runs install_nightguard.ps1, fires the watchdog re-register, and swaps settings.json.

## Carry-forward for Plan 03

- **The adapter's block contract is confirmed: `stderr + exit 2`.** When Plan 03 swaps settings.json UserPromptSubmit to nightguard_adapter.ps1, blocks WILL register; do not second-guess with exit 1 / {continue:false}.
- **install_nightguard.ps1 is ready to run** — it byte-deploys all five scripts, preserves interop, and re-stamps the baseline at repo-source scope. Run it, then call `Register-NightguardWatchdog` (defined inside it) to repoint + Start the task so a fresh process inherits NIGHTGUARD_DIR (Pitfall 2).
- **verify_hook_integrity.ps1's $registered does NOT yet cover the adapter/watchdog.** Extending the trust surface (and re-stamping) is a follow-up if those scripts should be integrity-protected too; the current baseline covers the four existing trust-surface scripts.
- **The D-11 prove-then-switch gate is the precondition** for Plan 03's live cutover (settings.json swap + watchdog task re-register/Start). The legacy curfew gate keeps protecting until then.

## Next Phase Readiness

- All three deployable artifacts exist, parse 5.1-clean, and meet every acceptance criterion. The cutover (Plan 03) has its consumers built; phase NOT marked complete (Plan 03 remains).

## Self-Check: PASSED

- FOUND: scripts/guard/nightguard_adapter.ps1
- FOUND: scripts/guard/nightguard_watchdog.ps1
- FOUND: scripts/deploy/install_nightguard.ps1
- FOUND: C:/Users/20252128/dev/Projects/LifeOS/hooks/nightguard_adapter.ps1 (inert deploy copy)
- FOUND: C:/Users/20252128/dev/Projects/LifeOS/hooks/nightguard_watchdog.ps1 (inert deploy copy)
- FOUND: commit 7dc61ec (Task 2)
- FOUND: commit 350c73c (Task 3)
- FOUND: commit baa17a1 (Rule 3 follow-on)
