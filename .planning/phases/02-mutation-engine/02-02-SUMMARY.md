---
phase: 02-mutation-engine
plan: 02
subsystem: edit-intent-logic
tags: [rust, classifier, quota, dst, chrono-tz, yamlpath, pure-logic, tdd]

# Dependency graph
requires:
  - phase: 02-mutation-engine
    plan: 01
    provides: GuardState/LedgerEntry/GraceWindow serde model, MutationError, mutation-engine crate
provides:
  - classify::Direction enum + classify_change (per-field tighten/loosen/noop, RULE-01)
  - classify::is_loosening_commit (commit-level loosen detection, fail-safe)
  - week::most_recent_monday_midnight + next_monday_midnight (DST-aware, RULE-03)
  - week::reset_decision / ResetDecision (lazy weekly-budget roll)
  - quota::decide + QuotaDecision (commit-rule token state machine, RULE-02/04)
affects: [02-04-commit-grace, 02-05-state-parity, 03-enforcement-guard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "yamlpath query_exact + defensive QueryError absence-mapping (ExhaustedMapping/ExpectedMapping/Exhausted-/ExpectedList) => field-absent Noop (A2)"
    - "chrono-tz from_local_datetime with explicit MappedLocalTime match (Single/Ambiguous->earliest/None->01:00); next-Monday re-derived from the local DATE, never +7*24h"
    - "pure decision structs (QuotaDecision/ResetDecision) returned to a future I/O caller; modules I/O-free for offline matrix tests"

key-files:
  created:
    - crates/mutation-engine/tests/classify.rs
    - crates/mutation-engine/tests/week.rs
    - crates/mutation-engine/tests/quota.rs
  modified:
    - crates/mutation-engine/src/classify.rs
    - crates/mutation-engine/src/week.rs
    - crates/mutation-engine/src/quota.rs

key-decisions:
  - "Defensive A2 covers BOTH a missing final key (query_exact -> Ok(None)) AND structural absence on the path (ExhaustedMapping/ExpectedMapping/Exhausted-/ExpectedList query errors) — all map to field-absent Noop, never a panic and never a silent loosen (T-02-05)"
  - "next_monday_midnight re-derives from the local Monday DATE + 7 calendar days then re-resolves through the tz (DST-aware), so a transition week is 169h, not naive 168h (T-02-06)"
  - "QuotaDecision.next_reset is ALWAYS populated (the upcoming Monday), not only on a block, so the UI can display the reset time on any decision"
  - "Lazy reset derives an EFFECTIVE weekly_spent (0 when the stored anchor predates the current Monday) before applying the cost — a stale spent=3 never blocks a fresh-week loosen (T-02-04 conservative reset trusts the supplied instant)"

patterns-established:
  - "Pure-logic module + offline table tests (mirrors trust-kernel canon.rs / hmac.rs); module //! doc cites the RULE + invariant"
  - "Direction polarity encoded as a FieldKind enum + a single FIELD_TABLE driving classify_change (one row per spec-table field, seven schedule days appended dynamically)"

requirements-completed: [RULE-01, RULE-02, RULE-03, RULE-04]

# Metrics
duration: 14min
completed: 2026-06-05
---

# Phase 2 Plan 02: Direction Classifier + Token Quota + DST-Aware Monday Reset Summary

**Three pure, offline-testable edit-intent modules: a per-field tighten/loosen/noop classifier driven by the verbatim spec table, a DST-aware most-recent-Monday-00:00 week reset (no naive +7*24h), and the commit-rule token-quota state machine that blocks a 0-token loosen with the locked "available again Monday" reason.**

## Performance

- **Duration:** ~14 min
- **Completed:** 2026-06-05
- **Tasks:** 3 (all TDD: RED -> GREEN)
- **Files modified:** 6 (3 placeholder src filled, 3 test files created)
- **Tests:** 43 new (27 classify + 7 week + 9 quota); full crate 47/47 green

## Accomplishments
- **classify.rs (RULE-01):** `Direction { Tighten, Loosen, Noop }` + `classify_change` reads every spec-table field from both YAML documents via `yamlpath` and labels its direction per the verbatim table (booleans, HH:MM times, integers, flow lists, schedule windows, timezone). `is_loosening_commit` is fail-safe — true iff any field loosens. A field absent on either side is `Noop` (defensive A2), covering both missing-key and structural-absence query errors with no panic. 27 tests cover every row.
- **week.rs (RULE-03):** `most_recent_monday_midnight` resolves local Monday 00:00 to UTC via `from_local_datetime` with explicit `MappedLocalTime` handling (Single / Ambiguous->earliest / None->01:00). `next_monday_midnight` re-derives from the Monday DATE (never `+7*24h`), so the fall-back week is correctly 169h. `reset_decision` rolls the budget when the stored anchor predates the current Monday. 7 tests incl. a fall-back DST week. The no-naive-week grep gate returns 0.
- **quota.rs (RULE-02/04):** `decide` -> `QuotaDecision { allowed, reason, costs_token, is_noop, next_reset }`. All-noop writes nothing; no-loosen is free; a loosen at effective `weekly_spent < 3` costs one token; a loosen at `>= 3` is blocked with a reason containing the locked substring `available again Monday` and a DST-aware `next_reset`. A lazy reset derives the effective spent so a stale `spent=3` still allows a fresh-week loosen. 9 tests cover the full matrix.
- All three modules are I/O-free (no `std::fs` / `fd_lock` / file handles) — verified by grep — so the entire spec table and quota matrix run as offline unit tests, mirroring trust-kernel's pure-logic discipline.

## Task Commits

Each task was committed atomically (TDD RED -> GREEN):

1. **Task 1: classify.rs — per-field direction classifier (RULE-01)**
   - RED: `99d780d` (test) — 27 failing tests
   - GREEN: `4eb72f7` (feat) — implementation, all 27 green
2. **Task 2: week.rs — DST-aware Monday reset (RULE-03)**
   - RED: `cab09e6` (test) — 7 failing tests
   - GREEN: `0fb5176` (feat) — implementation, all 7 green
3. **Task 3: quota.rs — commit-rule token quota (RULE-02/04)**
   - RED: `ca69af6` (test) — 9 failing tests
   - GREEN: `3f913b1` (feat) — implementation (incl. trivial pre-commit cleanup), all 9 green

_No separate REFACTOR commits: the Task 3 cleanup (dropping an unused binding/import) was folded into GREEN before it landed; Tasks 1-2 needed none._

## Files Created/Modified
- `crates/mutation-engine/src/classify.rs` - `Direction` enum, `classify_change`, `is_loosening_commit`; `FieldKind`/`FieldSpec`/`FIELD_TABLE` encoding the spec table; defensive yamlpath reads.
- `crates/mutation-engine/src/week.rs` - `most_recent_monday_midnight`, `next_monday_midnight`, `reset_decision`/`ResetDecision`; explicit `MappedLocalTime` handling, no naive week math.
- `crates/mutation-engine/src/quota.rs` - `QuotaDecision`, `decide`; lazy-reset effective spent + commit rule + locked block reason.
- `crates/mutation-engine/tests/{classify,week,quota}.rs` - offline matrix tests, one descriptive #[test] per claim.

## Decisions Made
- **A2 covers structural absence, not just a missing leaf key.** `query_exact` only returns `Ok(None)` when the final key is missing inside an existing mapping; a missing intermediate key or a non-mapping parent surfaces as `ExhaustedMapping`/`ExpectedMapping`/`ExhaustedList`/`ExpectedList`. All four are mapped to field-absent `Noop` so a partial/different-shaped proposed config can never panic or be read as a silent loosen (T-02-05). Genuinely malformed YAML still folds to `MutationError::Serde`.
- **`next_reset` is always present.** Returning the upcoming Monday on every decision (not only blocks) lets the UI show "resets Monday" on allowed and blocked outcomes alike, at zero extra cost (week.rs is pure).
- **Lazy reset before cost.** `decide` computes the effective spent via `reset_decision` first, so the quota matrix and the new-week-after-stale-anchor case share one code path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Imported `chrono::TimeZone` into week.rs**
- **Found during:** Task 2 (week.rs GREEN)
- **Issue:** `Tz::from_local_datetime` is a `TimeZone` trait method; the first compile failed with E0599 because the trait wasn't in scope.
- **Fix:** Added `TimeZone` to the `chrono` import list.
- **Files modified:** crates/mutation-engine/src/week.rs
- **Verification:** `cargo test -p mutation-engine --test week` -> 7/7 green.
- **Committed in:** `0fb5176` (Task 2 GREEN)

---

**Total deviations:** 1 auto-fixed (blocking import). No scope creep — the RESEARCH Pattern 2 snippet omitted the trait import; adding it was required to compile the verbatim pattern.

## Known Stubs
None — all three modules are complete, pure implementations with full test coverage. (`commit.rs`, `grace.rs`, `ntp.rs` remain `//!`-only placeholders owned by later plans 02-03/02-04, unchanged here.)

## Threat Surface
No new trust-boundary surface beyond the plan's `<threat_model>`. The mitigations for T-02-04 (conservative deterministic reset from the supplied instant), T-02-05 (every spec row tested + field-absent Noop + fail-safe `is_loosening_commit`), and T-02-06 (explicit `MappedLocalTime`, no `weeks(1)`, grep gate 0, DST-week test) are all implemented and asserted.

## Issues Encountered
- One compile error (missing `TimeZone` trait import) — fixed inline (deviation 1). No other surprises; yamlpath's `query_exact`/`extract` and chrono-tz `MappedLocalTime` behaved exactly as the RESEARCH patterns documented.

## User Setup Required
None — pure Rust logic, no external service or config.

## Next Phase Readiness
- 02-04 (commit/grace) can `use mutation_engine::classify::{classify_change, is_loosening_commit, Direction}`, `week::{most_recent_monday_midnight, next_monday_midnight, reset_decision}`, and `quota::{decide, QuotaDecision}` directly to drive the ordered locked commit (apply the cost, append the ledger entry, re-sign).
- 02-05 (state parity) consumes the same `GuardState` round-trip; this plan adds no new persisted fields.
- The `Ambiguous->earliest` and `next_monday_midnight` DATE-based math are the canonical DST contract the Phase 3 PowerShell guard's reset display (if any) should mirror.

## Self-Check: PASSED

All six files exist on disk and all six task commits (`99d780d`, `4eb72f7`, `cab09e6`, `0fb5176`, `ca69af6`, `3f913b1`) are present in git history. `cargo test -p mutation-engine` -> 47/47 green (27 classify + 7 week + 9 quota + 4 state). The week.rs naive-week grep gate returns 0.

---
*Phase: 02-mutation-engine*
*Completed: 2026-06-05*
