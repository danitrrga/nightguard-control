---
phase: 03-enforcement-guard
plan: 04
subsystem: enforcement-guard
tags: [powershell, sha256, integrity-baseline, get-filehash, anti-me, gitattributes, gard-06, d-10]

# Dependency graph
requires:
  - phase: 03-03
    provides: "Final nightguard_guard.ps1 (complete always-firing reader/enforcer) whose bytes are what the baseline hashes"
provides:
  - "verify_hook_integrity.ps1: in-repo SHA256 integrity baseline writer (-Update) + drift checker (default), self-registering nightguard_guard.ps1 AND itself; exit 1 + alert on any drift/missing/unbaselined"
  - "guard.baseline.sha256: committed SHA256 manifest registering both guard scripts"
  - ".gitattributes scripts/guard/*.ps1 -text: keeps the baseline byte-stable across autocrlf checkouts"
affects: [enforcement-guard, instance-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SHA256 integrity baseline: Get-FileHash -Algorithm SHA256 (raw-byte read, no EOL normalization) over each registered script; manifest line form '<sha256-lowercase-hex><two spaces><forward-slash-relpath>', ASCII, LF-only"
    - "Self-registering integrity check: the registered set includes verify_hook_integrity.ps1 itself, so neutering the checker also trips the baseline (T-03-17)"
    - "Baseline byte-stability defense: .gitattributes -text on the hashed scripts mirrors the Pitfall-2 config*.yaml/*.guardkey rule so a fresh autocrlf clone does not LF->CRLF the files into false drift"

key-files:
  created:
    - scripts/guard/verify_hook_integrity.ps1
    - scripts/guard/guard.baseline.sha256
  modified:
    - .gitattributes

key-decisions:
  - "Registered set = nightguard_guard.ps1 + verify_hook_integrity.ps1 ONLY, NOT run_guard_gate.ps1. run_guard_gate.ps1 is a developer test/exit-gate, not part of the runtime enforcement surface; baselining a test harness would create churn (it changes with the test suite) without protecting an attack surface. The plan's registered set names exactly these two; honored as written."
  - "Pinned scripts/guard/*.ps1 to -text in .gitattributes (Rule 2 fix). core.autocrlf=true would rewrite the hashed scripts LF->CRLF on a fresh checkout, breaking the plan's 'clean checkout verifies green' must-have. Mirrors the existing Pitfall-2 defense for config*.yaml/*.guardkey."

patterns-established:
  - "verify_hook_integrity.ps1 -Update regenerates the baseline; run after any sanctioned edit to a registered guard script (the integrity check is intentionally fail-closed on stale baselines)"

requirements-completed: [GARD-06]

# Metrics
duration: 4min
completed: 2026-06-08
---

# Phase 3 Plan 04: In-Repo Guard Integrity Baseline (GARD-06 / D-10) Summary

**Shipped `verify_hook_integrity.ps1` -- an in-repo SHA256 baseline that self-registers `nightguard_guard.ps1` and itself, verifies green on a clean checkout, and raises a non-zero alert naming any guard script that is altered or removed -- plus a `.gitattributes` `-text` pin so the committed `guard.baseline.sha256` stays byte-stable across autocrlf checkouts.**

## Performance

- **Duration:** ~4 min
- **Tasks:** 1
- **Files created:** 2, **modified:** 1

## Accomplishments

- **Task 1** created `scripts/guard/verify_hook_integrity.ps1` (ASCII-only, `Set-StrictMode -Version Latest`, `$ErrorActionPreference = 'Stop'`, `nightguard_interop.ps1` banner style). It defines a registered set of two relative paths (`scripts/guard/nightguard_guard.ps1`, `scripts/guard/verify_hook_integrity.ps1`), resolves the repo root from `$MyInvocation`, and hashes each with `Get-FileHash -Algorithm SHA256` (raw bytes, no EOL normalization).
  - **`-Update` mode** writes `guard.baseline.sha256` with one `"<sha256>  <forward-slash-relpath>"` line per registered script (UTF-8 no-BOM, LF-only), prints what it wrote, exits 0.
  - **Default (verify) mode** parses the manifest, recomputes each entry, and via the `Add-Check` / `=== Summary ===` pattern flags: SHA256 drift, a registered file missing on disk, a malformed manifest line, a missing manifest entirely, and a registered-but-unbaselined script. Exits 0 only if every registered script matches its baseline, else exit 1.
- Generated `scripts/guard/guard.baseline.sha256` against the final plan-02/03 guard scripts via `-Update` and committed it as the checked-in baseline (registers both `nightguard_guard.ps1` and `verify_hook_integrity.ps1`).
- Verified all acceptance criteria on Windows PowerShell 5.1: clean checkout exits 0 (both PASS); a one-byte append to `nightguard_guard.ps1` makes verify exit 1 with an alert naming the drifted path; byte-exact restore returns to exit 0; both new files are ASCII-only (`[IO.File]::ReadAllBytes(...) | Where-Object { $_ -gt 127 }` returns nothing).

## Task Commits

1. **Task 1: verify_hook_integrity.ps1 baseline writer + drift checker + committed baseline** - `cb697bf` (feat)
2. **Rule 2 fix: .gitattributes -text pin for guard scripts** - `00754f2` (fix)

## Files Created/Modified

- `scripts/guard/verify_hook_integrity.ps1` (created) - SHA256 baseline writer (`-Update`) + drift checker (default) that self-registers the two guard scripts; `Get-FileHash -Algorithm SHA256`, `Add-Check`/`=== Summary ===`, exit 0 clean / 1 on drift.
- `scripts/guard/guard.baseline.sha256` (created) - Committed baseline manifest; two lines registering `nightguard_guard.ps1` and `verify_hook_integrity.ps1`.
- `.gitattributes` (modified) - Added `scripts/guard/*.ps1 -text` so a fresh autocrlf checkout does not LF->CRLF the hashed scripts into false drift.

## Decisions Made

- **Registered set is the two enforcement scripts, not the test gate.** `run_guard_gate.ps1` is a developer exit-gate and is intentionally excluded; the plan names exactly `nightguard_guard.ps1` + `verify_hook_integrity.ps1`.
- **`.gitattributes -text` pin** (see deviations) keeps the baseline byte-stable across checkouts, satisfying the "clean checkout verifies green" must-have on any sanctioned host.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Baseline would break on a fresh autocrlf checkout**
- **Found during:** Task 1 commit (Git warned "LF will be replaced by CRLF the next time Git touches it" for the guard `.ps1` files).
- **Issue:** `core.autocrlf=true` is set and the existing `.gitattributes` only pinned `config*.yaml` and `*.guardkey` to `-text`. The guard `.ps1` scripts are LF in both the blob and the current working tree, but a fresh `git clone` on an autocrlf host would check them out as CRLF -- whose `Get-FileHash` would no longer match the LF-derived baseline. That directly breaks the plan's must-have "a clean (untouched) checkout verifies green."
- **Fix:** Added `scripts/guard/*.ps1 -text` to `.gitattributes`, mirroring the existing Pitfall-2 raw-byte defense for the signed config/key files. Confirmed via `git check-attr text` that the attribute applies (`text: unset`) and re-ran the integrity check green.
- **Files modified:** .gitattributes
- **Verification:** `git check-attr text scripts/guard/*.ps1` -> `text: unset`; verify run still exits 0 with both PASS.
- **Committed in:** `00754f2`

## Issues Encountered

- None blocking. The benign "LF will be replaced by CRLF" Git warning on commit is exactly what the Rule 2 `.gitattributes` fix neutralizes for future checkouts; the bytes committed this session are LF and self-consistently verify green.

## User Setup Required

- After any sanctioned edit to `nightguard_guard.ps1` or `verify_hook_integrity.ps1`, regenerate the baseline with `verify_hook_integrity.ps1 -Update` and commit the updated `guard.baseline.sha256` (the check is deliberately fail-closed on a stale baseline).

## Next Phase Readiness

- GARD-06 is now verifiable inside this publishable repo (D-10): the guard self-registers in an in-repo SHA256 baseline that verifies green and alerts on any guard-script drift/removal. Phase 3 (enforcement-guard) plan set is complete.
- Carry-over (unchanged from 03-03): verify hook-path resolution under Claude Code junctions before wiring `nightguard_guard.ps1` into the host (`$PSScriptRoot\..` may resolve to the drifted `~/.claude/nightguard`).

## Threat Model Coverage

- **T-03-16 (replace/disable nightguard_guard.ps1):** mitigated -- registered in the baseline; any drift/removal -> exit 1 alert.
- **T-03-17 (edit verify_hook_integrity.ps1 to neuter the check):** mitigated -- the script self-registers, so editing it alone also trips the baseline.
- **T-03-18 (swap the baseline to match a tampered guard):** accepted per plan -- the committed in-repo baseline is rebaselineable by anyone with repo write + `-Update`; absolute unbreakability is explicitly out of scope (REQUIREMENTS).

## Self-Check: PASSED

All claimed files exist (verify_hook_integrity.ps1, guard.baseline.sha256, .gitattributes, this SUMMARY) and both task commits (cb697bf, 00754f2) are present in git history.
