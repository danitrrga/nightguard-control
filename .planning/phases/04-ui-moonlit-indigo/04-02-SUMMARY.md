---
phase: 04-ui-moonlit-indigo
plan: 02
subsystem: api
tags: [rust, chrono, chrono-tz, yamlpath, curfew, tdd, mutation-engine]

# Dependency graph
requires:
  - phase: 02-mutation-engine
    provides: classify.rs parse_hhmm/parse_window + read_field defensive yamlpath read; week.rs DST-aware MappedLocalTime instant math; grace.rs unix->tz instant pattern
provides:
  - "pure lock_status(config_yaml, now) -> LockStatus curfew-window evaluator in mutation-engine"
  - "LockStatus { locked, grace_active, boundary_unix, boundary_kind } DTO"
  - "written curfew precedence spec (enabled gate, schedule.<day> override, overnight-wrap, fail-safe-locked)"
affects: [04-03-get_state, 04-ui-status-view, ipc-commands]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure (config, now) -> verdict evaluator with offline diff-table tests (mirrors classify/week/quota)"
    - "Single shared HH:MM parser via pub(crate) — no divergent second parser"
    - "Fail-safe-LOCKED on absent/malformed (D-04 / A2): a missing field is never a silent unlock"

key-files:
  created:
    - crates/mutation-engine/src/lock_status.rs
    - crates/mutation-engine/tests/lock_status.rs
  modified:
    - crates/mutation-engine/src/lib.rs
    - crates/mutation-engine/src/classify.rs

key-decisions:
  - "Overnight-wrap inside = minute>=start || minute<end; boundary derived from the wrapped end on the correct calendar day, never naive +24h"
  - "schedule.<day> overrides curfew.start/end: 'off' => unlocked that day, 'HH:MM-HH:MM' => that window applies (overnight-wrap allowed)"
  - "grace_active is always false in this pure fn; get_state overlays the signed guard.json grace window (simpler seam)"
  - "Made classify::parse_hhmm/parse_window pub(crate) and reused them — exactly ONE HH:MM parser in the engine"
  - "Absent/malformed curfew fields => fail-safe LOCKED (boundary_unix=now, kind=curfew_end), never a silent unlock"

patterns-established:
  - "Pattern: highest-risk net-new logic carved into a pure, exhaustively-tested fn so it is verifiable offline and reusable headless"
  - "Pattern: mirror classify::read_field defensive yamlpath read (structural-absence QueryErrors => field-absent, malformed YAML => fail-safe)"

requirements-completed: [UI-01]

# Metrics
duration: 14min
completed: 2026-06-09
---

# Phase 4 Plan 02: lock_status Curfew Evaluator Summary

**Pure `lock_status(config_yaml, now) -> LockStatus` evaluator in mutation-engine answering "locked now?" + next-boundary across overnight-wrap, schedule-day precedence, disabled curfew, and defensive-absent fields, with a written precedence spec and 11 offline tests — fail-safe-LOCKED on any doubt (D-04).**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-06-09T09:28Z
- **Completed:** 2026-06-09T09:42Z
- **Tasks:** 1 feature (TDD: RED -> GREEN)
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- `lock_status` pure evaluator: interprets `curfew.enabled`, `curfew.start/end`, `curfew.schedule.<day>` (x7), and `timezone` against an advisory `now`.
- Overnight-wrap correctness: a window entered late (e.g. 23:30 inside 23:00-07:00) yields a boundary on the NEXT calendar day's 07:00 — proven by test, no naive +24h.
- `schedule.<day>` precedence over `start/end` (off => unlocked; `HH:MM-HH:MM` => that window) — written spec + 2 tests.
- Fail-safe-LOCKED on missing curfew block / malformed window / absent enabled (D-04 / A2): a missing or garbage field is NEVER a silent unlock.
- DST-aware local->unix boundary math via explicit `MappedLocalTime` handling, mirroring `week.rs`; bad tz defaults to UTC with no panic.
- Reused `classify::parse_hhmm`/`parse_window` (made `pub(crate)`) — exactly one HH:MM parser in scope, no divergent copy.

## Task Commits

TDD cycle (RED -> GREEN; no REFACTOR needed — implementation was already minimal):

1. **RED: failing truth-table tests** - `af73a33` (test)
2. **GREEN: pure lock_status implementation** - `ac9db4f` (feat)

## Files Created/Modified
- `crates/mutation-engine/src/lock_status.rs` - The pure evaluator + `LockStatus` struct + written precedence spec in the module doc.
- `crates/mutation-engine/tests/lock_status.rs` - 11 offline tests (inside/outside/overnight-wrap/non-overnight/enabled=false/schedule-off/schedule-window/missing-block/malformed-window/bad-tz).
- `crates/mutation-engine/src/lib.rs` - Added `pub mod lock_status;`.
- `crates/mutation-engine/src/classify.rs` - Made `parse_hhmm`/`parse_window` `pub(crate)` for single-parser reuse (doc-comments only; no logic change).

## Decisions Made
- **Boundary on the correct calendar day for wraps:** when locked inside an overnight window's late part (`minute >= start`), the curfew-end boundary is tomorrow; otherwise today. Derived from the wrapped end, never `+24h`.
- **`grace_active` left `false` here:** the live grace window is signed state in `guard.json`; `get_state` (plan 03) overlays it and may set `boundary_kind = "grace_end"`. This keeps `lock_status` 100% pure (the simpler seam the plan offered).
- **Open-day boundary is advisory:** the `next_lock` boundary is computed from the day's start/end (today if upcoming, else tomorrow); a full forward multi-day schedule scan is out of scope for the advisory display (D-04).

## Deviations from Plan

None - plan executed exactly as written. The two `pub(crate)` doc-comments on `classify.rs` are the plan's explicitly-sanctioned "make them pub(crate) and share" option (avoiding a divergent parser), not a deviation.

## Issues Encountered
- Initial compile error: `hour()`/`minute()` need the `chrono::Timelike` trait in scope — added the import. Resolved immediately; covered by the GREEN commit.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `lock_status` is ready for `get_state` (plan 03) to call: feed verified `config.yaml` + the advisory `now`, then overlay the signed grace window from `guard.json` onto the returned `LockStatus`.
- The boundary instants are unix-secs `i64`, matching `GraceWindow.window_end` / `LedgerEntry` for the UI to format directly.
- No blockers.

## Self-Check: PASSED
- FOUND: crates/mutation-engine/src/lock_status.rs
- FOUND: crates/mutation-engine/tests/lock_status.rs
- FOUND commit: af73a33 (test, RED)
- FOUND commit: ac9db4f (feat, GREEN)
- `cargo test -p mutation-engine --test lock_status`: 11 passed, 0 failed
- `cargo test -p mutation-engine`: full suite green (no regression from pub(crate) change)

---
*Phase: 04-ui-moonlit-indigo*
*Completed: 2026-06-09*
