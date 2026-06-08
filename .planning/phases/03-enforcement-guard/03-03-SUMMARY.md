---
phase: 03-enforcement-guard
plan: 03
subsystem: enforcement-guard
tags: [powershell, sntp, ntp, fail-closed, grace, curfew, hmac-chain, audit-log, fd-lock, exit-gate, anti-me]

# Dependency graph
requires:
  - phase: 03-02
    provides: "Guard clock-free half: $reverted/$failClosed/$weeklySpent/$graceUsed verdict-input vars, $stateValid/$guardObj from state-verify, config-verify->revert/maximal-lockout, Test-LockHeld circuit-breaker"
  - phase: 03-01
    provides: "Runtime state_hmac A3 re-derive recipe (compact -Depth 10 + 0x0A), fd-lock exclusive-open IOException probe shape"
  - phase: 02-mutation-engine
    provides: "state.rs GuardState (grace.window_end), ntp.rs fail-closed contract, commit.rs with_commit_lock, nightguard_interop.ps1 DPAPI/HMAC primitives, state_interop_cli verify-state-hmac"
provides:
  - "nightguard_guard.ps1 clock-dependent half: Get-GuardNtpUnixSecs (48-byte SNTP, fail-closed), A4 clock-tamper, grace/curfew verdict vs window_end, Append-AuditRecord (HMAC-chained, D-08), D-02 JSON+exit-code output"
  - "run_guard_gate.ps1: end-to-end exit gate proving GARD-01/02/03/04/05 against real DPAPI/HMAC fixtures, a -NtpOverrideUnixSecs seam, and a live Rust fd-lock holder"
  - "state_interop_cli hold-commit-lock subcommand: a real with_commit_lock holder (ready/release sentinels) the gate drives for GARD-05"
affects: [03-04, enforcement-guard, instance-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Guard-side SNTP: 48-byte client packet (byte0=0x1B), parse transmit-secs (bytes 40..43 BE), subtract 2208988800 (NTP 1900 -> unix 1970); any exception -> $null -> deny+fail_closed (NEVER falls back to Get-Date)"
    - "Verdict gate keyed on $stateValid (untampered state) AND grace.window_end > trueNow; a state_hmac mismatch can never produce an allow (T-03-15)"
    - "HMAC-chained audit log: record_tag = HMAC(key, prev_tag || payload); first record chains off a fixed 64-zero genesis; AppendAllText UTF-8 no-BOM; pipe-delimited payload with backslash/pipe/newline escaping"
    - "Gate self-signs guard.json in PowerShell (config_hmac = real Get-FileHmacHex of config.yaml, state_hmac via A3) then cross-checks it with Rust verify-state-hmac -- decouples the GARD-01 byte-exact revert from the CLI's fixed dummy config_hmac"
    - "GARD-05 live lock holder = state_interop_cli hold-commit-lock (real with_commit_lock) signalled via ready/release sentinel files, started Start-Process -PassThru and joined with WaitForExit"

key-files:
  created:
    - scripts/guard/run_guard_gate.ps1
  modified:
    - scripts/guard/nightguard_guard.ps1
    - crates/mutation-engine/src/bin/state_interop_cli.rs

key-decisions:
  - "Grace-honored path gated on $stateValid, NOT on (-not $graceUsed): plan-02 sets $graceUsed = ($null -ne grace) in the trusted branch, so an active window forces $graceUsed=true -- the plan's literal '(-not $graceUsed)' condition would make EVERY grace window unreachable. $stateValid is the load-bearing tamper gate (a state_hmac mismatch -> $stateValid=false -> never allow, T-03-15); grace-present + window_end>trueNow is the grant. Correctness fix, fail-closed preserved."
  - "Gate builds guard.json in PowerShell instead of via `state_interop_cli emit-state-hmac` (which the plan key_links named): emit-state-hmac writes a FIXED arbitrary config_hmac (1122..) that is the HMAC of NO real file, so it cannot drive a byte-exact GARD-01 revert against a gate-written config.yaml. The gate self-signs config_hmac = real HMAC(config.yaml) + state_hmac via the proven A3 recipe, and cross-checks the result with Rust verify-state-hmac (exit 0) so PS<->Rust parity is still asserted."
  - "Added a hold-commit-lock subcommand to state_interop_cli (no new [[bin]]) rather than a throwaway cargo test: it takes the REAL with_commit_lock and blocks on a release sentinel, so the gate observes a genuinely-held lock (Test-LockHeld -> skip revert) then a free lock after release, with a 30s safety timeout."
  - "NIGHTGUARD_NTP_SERVER env seam on the guard lets the gate point real SNTP at RFC 5737 TEST-NET (192.0.2.1) to exercise the D-07 offline fail-closed path deterministically; unset in normal operation (production uses the built-in time.cloudflare.com)."

patterns-established:
  - "Verdict ordering: config/state integrity (plan 02) FIRST -> resolve true-now (override seam or SNTP) -> NTP-null/skew fail-closed -> grace/curfew -> append one audit record -> emit D-02 JSON + exit code"
  - "Audit reader forces @() around the split/filter so a single surviving line stays an array (else $lines[0] indexes a CHARACTER) -- the chain-continuity bug guard"

requirements-completed: [GARD-01, GARD-02, GARD-03, GARD-04, GARD-05]

# Metrics
duration: 22min
completed: 2026-06-08
---

# Phase 3 Plan 03: Grace/Curfew Verdict + Guard-Side SNTP + HMAC-Chained Audit + End-to-End Gate Summary

**Completed the clock-dependent half of nightguard_guard.ps1 -- a fail-closed guard-side SNTP true-time query, an A4 clock-tamper check, the grace/curfew verdict against guard.json.grace.window_end, an HMAC-chained tamper-evident audit record per fire, and the host-agnostic D-02 JSON + exit-code output -- then proved every GARD behavior end-to-end with run_guard_gate.ps1 (green) against real DPAPI/HMAC fixtures, a deterministic NTP seam, and a live Rust fd-lock holder.**

## Performance

- **Duration:** ~22 min
- **Tasks:** 2
- **Files created:** 1, **modified:** 2

## Accomplishments

- **Task 1** replaced the temporary `exit 0` tail of the guard with: `Get-GuardNtpUnixSecs` (48-byte SNTP client packet, byte0=0x1B, parse bytes 40..43 big-endian, subtract 2208988800, `$null` on any exception with no Get-Date fallback); true-now resolution via the `-NtpOverrideUnixSecs` seam or real SNTP; the D-07 NTP-unreachable deny+fail_closed branch; the A4 clock-tamper deny (|trueNow-local|>300s, skipped under the override seam); the grace/curfew verdict (allow + `grace_remaining_secs` when a trusted window covers true-now, else re-lock); `Append-AuditRecord` (HMAC-chained, genesis-anchored, D-08); and the D-02 `{decision,reason,grace_remaining_secs,reverted,fail_closed}` JSON on stdout + exit 0=allow/1=deny.
- **Task 2** created `run_guard_gate.ps1`, an end-to-end exit gate copying the state-interop-gate skeleton (Invoke-Cli, Add-Check, `target\` work dir, `=== Summary ===` / exit 0|1). It builds internally-consistent fixtures (DPAPI `.guardkey`, `config.yaml == config.sanctioned.yaml`, a self-signed `guard.json`) and drives the guard for GARD-01 (revert), GARD-02 (maximal-lockout), GARD-03 (state-tamper-inside-window -> deny), GARD-04 (grace honored/expired/offline), and GARD-05 (lock-held -> skip / released -> revert) -- all PASS, gate exits 0, deterministically across repeated runs.
- Added a `hold-commit-lock` subcommand to `state_interop_cli` (real `with_commit_lock` + ready/release sentinels) as the live Rust lock owner the GARD-05 check probes, and a `NIGHTGUARD_NTP_SERVER` env seam on the guard for the deterministic offline fail-closed check.

## Task Commits

1. **Task 1: SNTP verdict + clock-tamper + grace/curfew + HMAC-chained audit + JSON output** - `ccdc4e5` (feat)
2. **Task 2: run_guard_gate.ps1 end-to-end gate + live Rust lock holder** - `206ad10` (feat)

## Files Created/Modified

- `scripts/guard/nightguard_guard.ps1` (modified) - Added the clock-dependent half: `Get-GuardNtpUnixSecs`, `Append-AuditRecord`, true-now resolution + fail-closed NTP/skew branches, the grace/curfew verdict, the audit append, and the D-02 JSON + exit code. ASCII-only, parses clean under WinPS 5.1.
- `scripts/guard/run_guard_gate.ps1` (created) - The GARD-01..05 end-to-end exit gate with `Build-Fixture`, a `-NtpOverrideUnixSecs` deterministic NTP seam, a Rust `verify-state-hmac` cross-check, and a live `hold-commit-lock` holder for GARD-05.
- `crates/mutation-engine/src/bin/state_interop_cli.rs` (modified) - Added the `hold-commit-lock <lock_dir> <ready_path> <release_path>` subcommand (real `with_commit_lock`, ready/release sentinels, 30s safety timeout).

## Decisions Made

- **Grace-honored gate keyed on `$stateValid`, not `(-not $graceUsed)`** (see deviations). The plan's literal condition is self-contradictory given plan-02's `$graceUsed` semantics; `$stateValid` is the correct, load-bearing tamper gate.
- **Gate self-signs guard.json in PowerShell** (config_hmac = real HMAC of the gate's config.yaml, state_hmac via the A3 recipe) and cross-checks with Rust `verify-state-hmac`, rather than using `emit-state-hmac` whose fixed dummy config_hmac cannot drive a byte-exact revert.
- **`hold-commit-lock` subcommand** as the live Rust lock holder (no new `[[bin]]`, reuses the real `with_commit_lock`).
- **`NIGHTGUARD_NTP_SERVER` seam** for the deterministic D-07 offline check (TEST-NET unroutable address).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Grace-honored path was unreachable as the plan specified it**
- **Found during:** Task 1 verdict smoke test (an active window denied when it should allow).
- **Issue:** Plan Task 1 step (4) says "if `$graceUsed` is false-or-window-present ... allow". But plan-02 sets `$graceUsed = ($null -ne grace)` in the trusted branch, so an active window always makes `$graceUsed=true`. The plan's literal `(-not $graceUsed)` allow-condition therefore denies EVERY grace window -- the GARD-04 honored case could never pass.
- **Fix:** Gated the allow on `$stateValid` (state-verify untampered) AND grace-present AND `window_end > trueNow`. This preserves the intended fail-closed posture exactly: a state_hmac mismatch (`$stateValid=false`) can never produce an allow (T-03-15 / GARD-03), while a trusted active window is honored (GARD-04). `$graceUsed` remains the plan-02 worst-case flag; `$stateValid` is the load-bearing discriminator.
- **Files modified:** scripts/guard/nightguard_guard.ps1
- **Verification:** GARD-04 honored=allow(rem=100), GARD-03 state-tamper-inside-window=deny -- both green in the gate.
- **Committed in:** `ccdc4e5`

**2. [Rule 1 - Bug] Audit chain broke after the first record (scalar-string indexing)**
- **Found during:** Task 1 audit-chain smoke test (record 2 chained off genesis, not record 1's tag).
- **Issue:** `Append-AuditRecord` read the previous tag via `$lines = $existing -split "\`n" | Where-Object {...}`. When exactly one line survives the filter, PowerShell collapses `$lines` to a scalar string, so `$lines[$lines.Count-1]` indexed a single CHARACTER instead of the record line; `LastIndexOf('|')` returned -1 and the prev-tag fell back to genesis -- silently breaking the D-08 chain continuity.
- **Fix:** Forced an array with `@(...)` around the split/filter so a single line stays a one-element array.
- **Files modified:** scripts/guard/nightguard_guard.ps1
- **Verification:** Two-fire smoke test -> AUDIT CHAIN VERIFIED: True (2 records), each `record_tag = HMAC(key, prev_tag || payload)`.
- **Committed in:** `ccdc4e5`

**3. [Rule 2 - Missing Critical] Deterministic offline fail-closed path needed an NTP-server seam**
- **Found during:** Task 2 (GARD-04 offline check could not reliably make `time.cloudflare.com` unreachable).
- **Issue:** The D-07 offline-deny behavior is a required GARD-04 acceptance, but the guard hardcoded the SNTP server, leaving no deterministic way to exercise the unreachable path.
- **Fix:** Added a `NIGHTGUARD_NTP_SERVER` env override on the real-SNTP branch (never set in production); the gate points it at RFC 5737 TEST-NET `192.0.2.1` so the 2s timeout deterministically yields `$trueNow=$null` -> deny + fail_closed.
- **Files modified:** scripts/guard/nightguard_guard.ps1, scripts/guard/run_guard_gate.ps1
- **Verification:** GARD-04 offline=True (deny + fail_closed) in the gate.
- **Committed in:** `206ad10`

### Other deviations (mechanism, not behavior)

- **Gate fixture source:** the plan's `key_links` say `run_guard_gate.ps1` generates `guard.json` via Rust `state_interop_cli emit-state-hmac`. That CLI writes a FIXED arbitrary `config_hmac` (`1122..`) that is the HMAC of no real file, so it cannot anchor a byte-exact GARD-01 revert. The gate instead self-signs `guard.json` in PowerShell (real `config_hmac` + A3 `state_hmac`) and cross-checks it with Rust `verify-state-hmac` (exit 0), keeping PS<->Rust parity asserted. The plan artifact's `contains: NtpOverrideUnixSecs` requirement is satisfied (grep PASS).
- **GARD-05 lock holder:** the plan suggested "a short-lived `cargo test`/bin that takes with_commit_lock and sleeps". Implemented as a `hold-commit-lock` subcommand on the existing `state_interop_cli` bin (sentinel-coordinated, real `with_commit_lock`) -- same mechanism, no throwaway test or new bin.

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing-critical) + 2 mechanism deviations. All behaviors match the plan's must-haves; the auto-fixes preserve the fail-closed anti-me posture.

## Issues Encountered

- The Git Bash tool layer intermittently stripped quotes / threw transient EPERM on heredoc writes (same class plan 01/02 hit); resolved by writing harness scripts via the Write tool and invoking with `-File`. No change to the guard or gate.

## User Setup Required

None. The gate runs offline-safe (its only network touch is the deliberate TEST-NET unreachable probe).

## Next Phase Readiness

- Plan 03-04 (the last Phase 3 plan) can now build `verify_hook_integrity.ps1` + the self-registered SHA256 manifest (GARD-06) over the now-complete guard scripts.
- Carry-over (unchanged): verify hook-path resolution under Claude Code junctions before wiring `nightguard_guard.ps1` into the host (`$PSScriptRoot\..` may resolve to the drifted `~/.claude/nightguard`).

## Self-Check: PASSED

All claimed files exist (run_guard_gate.ps1, nightguard_guard.ps1, state_interop_cli.rs, this SUMMARY) and both task commits (ccdc4e5, 206ad10) are present in git history.
