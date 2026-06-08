---
phase: 03-enforcement-guard
plan: 02
subsystem: testing
tags: [powershell, hmac, dpapi, fd-lock, config-revert, fail-closed, state-hmac, circuit-breaker, anti-me]

# Dependency graph
requires:
  - phase: 03-01
    provides: "Runtime state_hmac re-derivation recipe (compact ConvertTo-Json -Depth 10 + 0x0A), fd-lock exclusive-open IOException probe shape"
  - phase: 02-mutation-engine
    provides: "commit.rs revert rule + live-last ordering, state.rs compute_state_hmac (A3) + locked guard.json fields, classify.rs config schema, nightguard_interop.ps1 DPAPI/HMAC primitives"
provides:
  - "scripts/guard/nightguard_guard.ps1 clock-free integrity half: data-dir resolution, DPAPI key load (32-canary), Test-LockHeld circuit-breaker, Get-RuntimeStateHmac, config-verify->revert/maximal-lockout, state worst-case substitution"
  - "Test-SanctionedValid predicate (file exists AND HMAC == config_hmac) -- the locked GARD-02 sanctioned-validity test"
  - "Write-MaximalLockoutDefault: hardcoded 24/7-curfew D-03 literal in canonical bytes that the minimal YAML parser reads"
  - "$reverted / $failClosed / $weeklySpent / $graceUsed verdict-input variables for plan 03"
affects: [03-03, 03-04, enforcement-guard, instance-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Guard config-verify: Get-FileHmacHex(live raw bytes) vs guard.json.config_hmac; direction-agnostic revert by [IO.File]::Copy(sanctioned, live) -- guard never re-signs"
    - "Circuit-breaker BEFORE revert: Test-LockHeld exclusive-open probe gates any file touch (GARD-05 sign-vs-write race)"
    - "config_hmac is trusted only when state-verify passes; an unverifiable guard.json folds straight to maximal-lockout (no permissive path)"
    - "Maximal-lockout default written as canonical bytes (UTF-8 no BOM, LF-only, one trailing 0x0A) via Write-RawBytes -- never Set-Content"

key-files:
  created: []
  modified:
    - scripts/guard/nightguard_guard.ps1

key-decisions:
  - "config_hmac is trustworthy ONLY when state-verify passes -- on a state_hmac mismatch the revert target is untrustworthy, so the guard falls straight to maximal-lockout rather than trusting a possibly-forged config_hmac (closes the forged-guard.json-points-at-attacker-bytes hole)"
  - "Maximal-lockout literal = 24/7 curfew (every schedule day 00:00-23:59 + curfew.enabled true + block_when_offline true + clock_protection/watchdog enabled); grace/zero-tokens are enforced at runtime via the state worst-case substitution since guard.json is never written"
  - "$graceUsed derived from on-disk grace presence ($null -ne grace) only when state is valid; any tamper forces grace-used=true"

patterns-established:
  - "Guard ordering: state-verify FIRST (establishes config_hmac trust) -> config-verify+circuit-breaker+revert/lockout -- both clock-free, before any plan-03 SNTP verdict"
  - "Sanctioned-validity predicate reuses Get-FileHmacHex against the same config_hmac the live file is checked against (sanctioned is the revert target = the signed bytes)"

requirements-completed: [GARD-01, GARD-02, GARD-03, GARD-05]

# Metrics
duration: 12min
completed: 2026-06-08
---

# Phase 3 Plan 02: Guard Core (Config-Verify + Revert + Fail-Closed) Summary

**Built the clock-free integrity half of nightguard_guard.ps1: a hand-edit to config.yaml reverts to the valid sanctioned snapshot, double-corruption fails closed to a hardcoded 24/7 maximal-lockout, an in-progress app commit is never reverted (lock circuit-breaker), and a tampered guard.json is runtime-treated as weekly_spent=3 + grace-used -- all without the guard ever signing.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-08T13:50:00Z (approx)
- **Completed:** 2026-06-08T14:02:00Z (approx)
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Task 1 scaffold (data-dir resolution, DPAPI key load + 32-not-64 canary, Test-LockHeld plan-01-proven exclusive-open probe, Get-RuntimeStateHmac compact-re-derive) committed as the guard's reusable primitives, ASCII-only and clean under WinPS 5.1.
- Task 2 wired the unconditional, clock-free config-integrity path: state-verify -> config-verify -> circuit-breaker -> idempotent sanctioned revert or hardcoded maximal-lockout, plus the D-04 state worst-case substitution. The guard re-signs NOTHING (revert is a byte copy; lockout is a literal; state mismatch substitutes runtime values only).
- Behaviorally smoke-verified end-to-end against a real DPAPI-key + signed-config + signed-guard.json fixture: untampered => no revert (GARD-05), hand-edit => revert-to-sanctioned (GARD-01), both-files-corrupt => 24/7 maximal-lockout written (GARD-02/D-03). Full GARD-01/02/05 gate assertions land in plan 03's run_guard_gate.ps1 as planned.

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold guard + data-dir resolution + DPAPI key load + Test-LockHeld + state-verify** - `f11253c` (feat)
2. **Task 2: Config-verify + circuit-breaker + revert + maximal-lockout + state worst-case** - `5ed8c43` (feat)

**Plan metadata:** (final docs commit follows this summary)

## Files Created/Modified
- `scripts/guard/nightguard_guard.ps1` - The always-firing reader/enforcer's clock-free half. Resolves a single data dir (D-09), loads + canary-checks the DPAPI key, exposes Test-LockHeld (D-06) and Get-RuntimeStateHmac (A3), runs config-verify -> circuit-breaker -> revert/maximal-lockout (GARD-01/02/05), and substitutes worst-case state on a state_hmac mismatch (GARD-03/D-04). Leaves $reverted/$failClosed/$weeklySpent/$graceUsed for plan 03's verdict; ends with a temporary `exit 0`.

## Decisions Made
- **config_hmac trust gating (correctness, beyond the bare plan text):** The plan said "if guard.json itself failed to parse/verify so config_hmac is untrustworthy -> maximal-lockout". I enforced this concretely by computing `$configHmacTrusted = $stateValid -and config_hmac non-empty` and ONLY trusting the on-disk config_hmac (for both the match check and the sanctioned predicate) when that holds. A forged guard.json that points config_hmac at an attacker's bytes therefore cannot drive a "revert to the attacker's file" -- it folds to maximal-lockout. This is the fail-closed posture the threat model (T-03-06/07/08) demands.
- **Maximal-lockout shape:** 24/7 curfew expressed as `curfew.enabled: true`, `block_when_offline: true`, every `curfew.schedule.<day>: "00:00-23:59"`, `clock_protection.enabled: true`, `watchdog.enabled: true`, derived from the real field schema in `classify.rs`. "No grace, zero tokens" is a guard.json (state) property, which the guard never writes -- it is enforced at runtime by the worst-case substitution, so the lockout literal is purely the most-restrictive config.
- **$graceUsed semantics:** when state is valid, grace-used = (an active grace window exists on disk); any state tamper forces grace-used = true. weekly_spent reads the on-disk u8 only when valid, else 3.

## Deviations from Plan

### Pre-existing uncommitted Task 1 work

The repository already contained an untracked, complete, and correct `scripts/guard/nightguard_guard.ps1` matching Task 1 exactly (scaffold + data-dir + DPAPI canary + Test-LockHeld + Get-RuntimeStateHmac + defensive parse + worst-case defaults). Rather than rewrite identical code, I verified it against every Task 1 acceptance criterion (grep checks PASS, WinPS 5.1 parse PASS, ASCII-only PASS, dot-sources both interop libs, reimplements no forbidden primitive) and committed it as the Task 1 commit. No content change was needed.

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] config_hmac trust gate against a forged guard.json**
- **Found during:** Task 2 (config-verify path)
- **Issue:** A naive implementation that always trusts the on-disk `config_hmac` would let a forged guard.json (whose state_hmac does not re-derive) steer the live==config_hmac comparison and the sanctioned predicate toward attacker-chosen bytes -- a permissive path the threat model forbids (T-03-06/07/08).
- **Fix:** Gated all config_hmac use behind `$stateValid` (the runtime state-verify result). An untrusted/forged config_hmac folds straight to maximal-lockout instead of trusting it. The plan called for this ("config_hmac untrustworthy -> maximal-lockout"); the deviation note records the concrete mechanism (`$configHmacTrusted`) since it is load-bearing for the anti-me guarantee.
- **Files modified:** scripts/guard/nightguard_guard.ps1
- **Verification:** Smoke test CASE3 (both invalid) writes the lockout; CASE1 (valid state) trusts config_hmac and does not revert.
- **Committed in:** `5ed8c43` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing-critical, security/correctness). Plus one pre-existing-work note (Task 1 was already implemented; verified and committed unchanged).
**Impact on plan:** The auto-fix is exactly the fail-closed posture the plan and threat model require, expressed concretely. No scope creep -- the SNTP verdict, audit log, and JSON output remain deferred to plan 03 as written, and the temporary `exit 0` tail is preserved.

## Issues Encountered
- The inline-PowerShell smoke harness initially failed because the bash tool layer stripped single-quotes from a `-Command` string (the same class of quirk plan 01 hit). Resolved by writing the harness to a temp `.ps1` and running it with `-File`; all three behavioral cases then passed. No change to the guard itself.

## User Setup Required
None - no external service configuration required. (No network/UDP is exercised in this plan; SNTP is plan 03.)

## Next Phase Readiness
- Plan 03 can wire the grace/curfew verdict + guard-side SNTP + HMAC-chained audit log + JSON stdout onto the `$reverted/$failClosed/$weeklySpent/$graceUsed` variables this plan computes, replacing the temporary `exit 0` tail.
- Plan 03's `run_guard_gate.ps1` should drive the GARD-01/02/05 behavioral assertions against real fixtures (the branches they exercise now exist and were smoke-proven).
- Carry-over (from STATE.md, unchanged): verify hook-path resolution under Claude Code junctions before wiring `nightguard_guard.ps1` into the host (`$PSScriptRoot\..` may resolve to the drifted `~/.claude/nightguard`).

## Self-Check: PASSED

All claims verified below.

---
*Phase: 03-enforcement-guard*
*Completed: 2026-06-08*
