---
phase: 03-enforcement-guard
plan: 01
subsystem: testing
tags: [powershell, hmac, fd-lock, interop, state-hmac, circuit-breaker, sntp-adjacent]

# Dependency graph
requires:
  - phase: 02-mutation-engine
    provides: GuardState::compute_state_hmac (A3 recipe), with_commit_lock (fd-lock single-writer), run_state_interop_gate.ps1 (.signbytes gate)
provides:
  - "Runtime state_hmac re-derivation proven byte-identical PS<->Rust (parse pretty guard.json -> compact ConvertTo-Json -Depth 10 -> +0x0A -> HMAC)"
  - "fd-lock presence probe proven: [IO.File]::Open(...,'None') IOException == held against a live Rust with_commit_lock holder; existence != held"
affects: [03-02 guard core (Test-LockHeld, state-verify path), 03-03, 03-04, enforcement-guard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Runtime guard.json state-verify: read pretty bytes -> ConvertFrom-Json -> blank state_hmac -> ConvertTo-Json -Compress -Depth 10 -> UTF-8 no BOM -> append one 0x0A -> HMACSHA256 -> lowercase hex"
    - "Cross-language lock probe: exclusive-open (FileShare.None) IOException = held; the lock file persists, so file existence is NOT the held-signal"

key-files:
  created:
    - crates/mutation-engine/tests/lock_probe.rs
  modified:
    - scripts/interop/run_state_interop_gate.ps1

key-decisions:
  - "Runtime state-verify (Check 4) reconstructs the compact pre-sign bytes from the pretty on-disk guard.json alone; it never reads .signbytes, matching what the Phase 3 guard actually has at runtime."
  - "Lock-probe PowerShell path is embedded as a single-quoted PS literal (backslash-safe), not passed via -Command trailing tokens (which do NOT populate $args)."

patterns-established:
  - "RUNTIME state-verify recipe parity check appended to the A3 gate, distinct from the sign-side .signbytes check."
  - "Live-Rust-holder + spawned-PowerShell-probe pattern for cross-language lock/IO contract spikes."

requirements-completed: [GARD-03, GARD-05]

# Metrics
duration: 6min
completed: 2026-06-08
---

# Phase 3 Plan 01: De-risk Runtime state_hmac + fd-lock Probe Summary

**Proved both un-spiked cross-language mechanisms green: the RUNTIME state_hmac re-derivation (pretty guard.json -> compact ConvertTo-Json -Depth 10 -> +0x0A -> HMAC) matches the on-disk tag, and the exclusive-open IOException lock probe reports held-while-locked / free-after-release against a live Rust `with_commit_lock` holder.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-08T12:14:00Z (approx)
- **Completed:** 2026-06-08T12:20:12Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- Added Check 4 (`state_hmac RUNTIME re-derive`) to `run_state_interop_gate.ps1`: re-derives the state_hmac purely from the pretty on-disk guard.json (blank field -> `ConvertTo-Json -Compress -Depth 10` -> UTF-8 no BOM -> one trailing `0x0A` -> HMAC) and asserts it equals `guard.json.state_hmac` without reading `.signbytes`. Gate stays GREEN (4/4 PASS) under Windows PowerShell 5.1.
- Created `lock_probe.rs`: holds `.nightguard.lock` via `with_commit_lock` and spawns a PowerShell exclusive-open probe; asserts `HELD` while locked and `FREE` after release with the lock file still on disk (proving existence != held).
- Both RESEARCH Open Questions (1: lock probe, 2: runtime state recipe / MEDIUM-confidence risks) are now empirically closed before plans 02-04 build on them (threats T-03-01, T-03-02 mitigated).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add runtime state-verify Check 4 to run_state_interop_gate.ps1** - `407c044` (test)
2. **Task 2: Spike the fd-lock presence probe with a Rust lock-holder + PowerShell exclusive-open** - `346072a` (test)

**Plan metadata:** (final docs commit follows this summary)

## Files Created/Modified
- `scripts/interop/run_state_interop_gate.ps1` - Added Check 4 proving the RUNTIME (pretty->compact) state_hmac re-derivation equals the on-disk tag; ASCII-only; reuses `$knownKey`/`$guardJson`, never `$signBytes`.
- `crates/mutation-engine/tests/lock_probe.rs` - Rust integration test holding `.nightguard.lock` while a spawned PowerShell `[IO.File]::Open($p,'Open','ReadWrite','None')` probe asserts held/free detection.

## Decisions Made
- Check 4 reconstructs compact bytes from the pretty JSON alone (no `.signbytes`), because that is exactly the runtime input the Phase 3 guard sees; the `.signbytes` path (Checks 1-3) only proves the sign-side.
- The lock-probe inline PowerShell embeds the lock path as a single-quoted literal (backslash-safe, `'` doubled) rather than relying on `powershell -Command <script> <arg>` trailing tokens — those do NOT populate `$args` (see Deviations).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PowerShell `$args` plumbing for the lock probe did not work via `-Command` trailing tokens**
- **Found during:** Task 2 (lock_probe.rs)
- **Issue:** Initial implementation passed the lock path as a trailing process argument expecting `$args[0]` to be populated (the plan's "inline probe" shape). With `powershell -Command <script> <token>`, `$args` is NOT populated the way `-File` does — the probe failed first with "Empty path name is not legal" and "-args not recognized", then with empty stdout (path still empty).
- **Fix:** Embedded the lock path into the script body as a single-quoted PowerShell literal (`$p = '<path>'`, with any literal `'` doubled). Backslash is not an escape char in PS single-quoted strings, so Windows paths are safe. The probe shape itself (`[IO.File]::Open($p,'Open','ReadWrite','None')` catching `[System.IO.IOException]`) is unchanged and matches the D-06 pattern exactly.
- **Files modified:** crates/mutation-engine/tests/lock_probe.rs
- **Verification:** `cargo test -p mutation-engine --test lock_probe` exits 0; HELD asserted while locked, FREE after release.
- **Committed in:** 346072a (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix was confined to the probe's argument-passing mechanism in test code; the proven probe shape lifted into plan 02's `Test-LockHeld` is byte-for-byte the plan's `[IO.File]::Open(...,'None')` / `[IO.IOException]` contract. No scope creep.

## Issues Encountered
None beyond the deviation above (a PowerShell argument-passing quirk, resolved in-task).

## User Setup Required
None - no external service configuration required. (The state gate's live NTP path is untouched; no UDP is exercised here.)

## Next Phase Readiness
- Both load-bearing cross-language mechanisms for GARD-03 (runtime state-verify) and GARD-05 (lock circuit-breaker) are proven green. Plan 02 can lift the `[IO.File]::Open(...,'None')` probe into `Test-LockHeld` and the compact-re-derive recipe into the guard's state-verify path with no remaining MEDIUM-confidence risk.
- Open carry-over (from STATE.md): verify hook-path resolution under Claude Code junctions before wiring `nightguard_guard.ps1` (`$PSScriptRoot\..` may resolve to the drifted `~/.claude/nightguard`).

## Self-Check: PASSED

All created/modified files exist on disk; both task commits (`407c044`, `346072a`) are present in git history.

---
*Phase: 03-enforcement-guard*
*Completed: 2026-06-08*
