---
phase: 02-mutation-engine
plan: 04
subsystem: sanctioned-commit-and-grace
tags: [rust, fd-lock, atomic-commit, crash-convergence, grace, ntp-true-day, tdd, rule-05, rule-06]

# Dependency graph
requires:
  - phase: 02-mutation-engine
    plan: 01
    provides: GuardState/LedgerEntry/GraceWindow serde model, MutationError, sign::sign_config, state_hmac A3 recipe
  - phase: 02-mutation-engine
    plan: 02
    provides: classify::Direction, quota::QuotaDecision, week::next_monday_midnight
  - phase: 02-mutation-engine
    plan: 03
    provides: ntp::TrueTime trait, NtpTrueTime, NtpUnreachable, FakeTrueTime
provides:
  - commit::with_commit_lock (fd-lock exclusive single-writer critical section)
  - commit::commit_change (ordered atomic re-signed sanctioned->guard.json->live commit, RULE-06)
  - commit::CommitPaths (the four-path commit target struct, reused by grace)
  - commit::commit_with_limit (test-only crash-convergence seam)
  - grace::use_grace (once-per-true-day 8-min NTP-boxed grace grant, RULE-05)
affects: [02-05-state-parity, 03-enforcement-guard, 04-tauri-app]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "fd-lock RwLock::write() exclusive cross-process single-writer lock (LockFileEx) wrapping the whole ordered commit AND use_grace via with_commit_lock"
    - "ordered atomic multi-file commit (sanctioned->guard.json->live, live LAST) achieving crash-convergence by ordering, not journaling — recovery is the Phase 3 guard's verify-and-revert rule"
    - "commit_with_limit test seam: a #[doc(hidden)] step-bounded variant lets commit_order.rs stop after N of the 3 writes and assert convergence to OLD or NEW"
    - "grace true-day derived from the NTP true-now instant in the configured tz (Pitfall 4), never Local::now()"

key-files:
  created:
    - crates/mutation-engine/tests/commit_order.rs
    - crates/mutation-engine/tests/grace.rs
  modified:
    - crates/mutation-engine/src/commit.rs
    - crates/mutation-engine/src/grace.rs

key-decisions:
  - "commit_with_limit(max_steps) is the crash-convergence test seam: the NEW state is computed up front and returned regardless of how many of the 3 ordered writes ran, so tests stop after N in {0,1,2,3} and run a local copy of the guard's revert rule to assert convergence to OLD or NEW"
  - "CommitPaths bundles config/sanctioned/guard_json/lock_dir; grace reuses it and with_commit_lock so commit and grace share ONE critical section (cannot race)"
  - "build_new_state spends a token + appends a ledger entry ONLY when decision.costs_token (a loosening commit); a tightening/free commit touches neither — the quota decision is authoritative, commit does not re-classify"
  - "grace derives true-day via DateTime::from_timestamp(unix_secs).with_timezone(tz).date_naive() — the configured-tz local date, defensively defaulting to UTC on a bad IANA name (mirrors week::parse_tz); refuses (no write) on NtpUnreachable or same-true-day reuse, leaving guard.json byte-identical"
  - "commit_with_limit refuses a !decision.allowed commit with QuotaExhausted (defense in depth even though the caller is expected to gate on the decision first)"

patterns-established:
  - "Ordered-by-construction multi-file atomicity: write the revert target first, the live file last; prove every crash point converges via the guard rule (commit_order.rs)"
  - "Shared with_commit_lock critical section reused across distinct mutators (commit + grace)"

requirements-completed: [RULE-05, RULE-06]

# Metrics
duration: 5min
completed: 2026-06-05
---

# Phase 2 Plan 04: Ordered Atomic Re-Signed Commit + Once-Per-True-Day Grace Summary

**The two security-critical I/O orchestrators: an fd-lock exclusive single-writer commit that writes config.sanctioned.yaml -> re-signed guard.json -> live config.yaml in that exact order (so every crash point converges to OLD or NEW, never a forged middle), and a once-per-true-day 8-minute grace grant gated on NTP true time in the configured timezone.**

## Performance

- **Duration:** ~5 min
- **Completed:** 2026-06-05
- **Tasks:** 2 (both TDD: RED -> GREEN)
- **Files modified:** 4 (2 placeholder src filled, 2 test files created)
- **Tests:** 13 new (8 commit_order + 5 grace); full crate 62/62 green (1 live NTP test ignored)

## Accomplishments

- **commit.rs (RULE-06):** `with_commit_lock` opens/creates `<lock_dir>/.nightguard.lock` and takes `fd_lock::RwLock::write()` (Windows `LockFileEx` + `LOCKFILE_EXCLUSIVE_LOCK`), an RAII cross-process exclusive lock released on drop/crash. `commit_change` computes the NEW signed state (config_hmac=HMAC(NEW canonical bytes), token++/ledger.append iff `decision.costs_token`, state_hmac via the A3 recipe) and writes **sanctioned -> guard.json -> live** strictly in order, with the live `config.yaml` written LAST via `write_canonical_text` (the same canonical bytes config_hmac was signed over). It orchestrates `trust_kernel::{atomic_write, write_canonical_text}` — no temp+rename reimplemented.
- **Crash-convergence proof (the load-bearing test):** `commit_with_limit(.., max_steps)` performs only the first N of the three writes; `commit_order.rs` stops after N in {0,1,2,3} and runs a local copy of the Phase 3 guard's rule (`HMAC(config.yaml) != guard.json.config_hmac => copy sanctioned over live`), asserting convergence: N=0/1 -> OLD, N=2/3 -> NEW. Named tests `crash_after_sanctioned_converges_to_old` and `crash_after_guardjson_converges_to_new` exist as required.
- **grace.rs (RULE-05):** `use_grace` runs inside the SAME `with_commit_lock`. It sources true time ONLY from the injected `TrueTime` (refuses `NtpUnreachable`, never the app clock), derives `true_today` as the NTP instant's date in the configured tz (Pitfall 4 — boundary test proves a 22:30Z instant lands on the next LOCAL day), refuses a same-true-day reuse with `GraceAlreadyUsedToday` leaving guard.json byte-unchanged, and otherwise writes `grace{date, window_start, window_end=start+480}`, re-signs `state_hmac`, and leaves `weekly_spent` untouched (grace costs no token).

## Task Commits

Each task was committed atomically (TDD RED -> GREEN):

1. **Task 1: commit.rs — fd-lock + ordered atomic re-signed commit (RULE-06)**
   - RED: `1713fff` (test) — 8 failing tests (compile)
   - GREEN: `56ce60d` (feat) — implementation, all 8 green; clippy-clean
2. **Task 2: grace.rs — once-per-true-day 8-min grace grant (RULE-05)**
   - RED: `d548b93` (test) — 5 failing tests (compile)
   - GREEN: `f0c5dbb` (feat) — implementation, all 5 green; clippy-clean

_No REFACTOR commits: both GREEN implementations were minimal and clean. The two new-code clippy lints surfaced during Task 1 (a doc-list-indentation note and the `OpenOptions::create`-without-`truncate` note on the lock file) were resolved before the GREEN commit landed — the lock file is opened `.truncate(false)` because its contents are an irrelevant sentinel and a shared handle must never be truncated._

## Files Created/Modified

- `crates/mutation-engine/src/commit.rs` - `CommitPaths`, `with_commit_lock`, `commit_change`, `commit_with_limit` (test seam), `build_new_state`, `read_state`. `//!` doc cites RULE-06 + the full crash-convergence contract + the forbidden GARD-05 live-first anti-pattern.
- `crates/mutation-engine/src/grace.rs` - `use_grace` + `true_day` helper. `//!` doc cites RULE-05 + Pitfall 4 + the two fail-closed refusals.
- `crates/mutation-engine/tests/commit_order.rs` - 8 tests: full-commit consistency, canonical-bytes parity, loosening token/ledger, tightening neither, crash-convergence N in {0,1,2,3} with a local guard revert rule.
- `crates/mutation-engine/tests/grace.rs` - 5 tests: grant writes window + no token, same-day reuse refused (byte-unchanged), new-day grant, NtpUnreachable refused (byte-unchanged), tz-boundary true-day.

## Decisions Made

- **`commit_with_limit` is the crash-convergence seam.** Rather than mocking a crash mid-`atomic_write`, the three ordered writes are gated on a `max_steps` count. The test stops after N and applies the guard's documented revert rule to the on-disk files, asserting the result equals OLD or NEW bytes. The NEW state is computed before any write so it is always returnable.
- **Commit trusts the supplied `QuotaDecision`.** `build_new_state` spends a token / appends a ledger entry strictly when `decision.costs_token` is true; commit does not re-run the classifier. This keeps the quota logic (plan 02-02) the single authority and commit purely an ordered, locked, re-signing writer. `commit_with_limit` also refuses a `!allowed` decision with `QuotaExhausted` as defense in depth.
- **Grace and commit share one lock + one path struct.** `use_grace` takes `&CommitPaths` and wraps its body in `with_commit_lock(&paths.lock_dir, ..)`, so a grace grant and a config commit can never interleave their `guard.json` writes.
- **True-day from the NTP instant, configured tz.** `true_day` uses `DateTime::from_timestamp(unix_secs, 0).with_timezone(tz).date_naive()`, defaulting to UTC on an invalid IANA name (never panics; mirrors `week::parse_tz`). This closes the clock-manipulation second-grant vector (T-02-12).

## Deviations from Plan

None - plan executed exactly as written.

The plan's Task 1 action sketched commit_change's signature as `commit_change(paths, new_yaml, dirs, decision, key, true_now)`; the implementation matches it, adding a `CommitPaths` struct (the plan referred to "paths") and the `commit_with_limit` test seam the plan explicitly asked for ("expose the ordered steps in a way the test can stop after N (e.g. an internal step function or a test-only hook)"). Neither is a deviation — both are the plan's own stated requirements made concrete.

## Known Stubs

None — both modules are complete, tested implementations. All eight mutation-engine src modules (state, sign, classify, quota, week, ntp, commit, grace) are now fully implemented; no `//!`-only placeholders remain.

## Threat Surface

No new trust-boundary surface beyond the plan's `<threat_model>`. All five register entries are implemented and asserted:
- **T-02-10** (partial/interrupted commit): ordered writes + `commit_order.rs` convergence for stop-after-N in {0,1,2,3}.
- **T-02-11** (concurrent writers racing the critical section): `fd-lock` exclusive lock held across the whole ordered sequence and across `use_grace`; RAII release on drop/crash.
- **T-02-12** (clock manipulation forging a second same-day grace): true-day derived from the NTP instant in the configured tz, not `Local::now()`; same-day reuse and NTP-unreachable both refused (fail-closed); boundary test asserts the local date.
- **T-02-13** (sign-vs-write race / GARD-05): live `config.yaml` written LAST, after re-signing; `commit_order.rs` enforces the ordering and proves a crash between guard.json and live converges to NEW (no legitimate-write revert).
- **T-02-14** (forged/replayed signed state): `state_hmac` re-derived over canonical bytes via the locked A3 recipe on every commit and grace write.

## Issues Encountered

- The initial grace test used wrong UTC epoch constants (off by four days) for its date assertions. Caught before the RED commit by cross-checking the timestamps with a small Python `datetime` computation, then corrected the constants and their comments so each instant maps to the intended LOCAL date. No impact on src.

## User Setup Required

None — pure Rust logic + file I/O under the crate's own scratch dir in tests. Live NTP is never touched by these tests (grace uses the injected `FakeTrueTime`); the only live-network test in the crate remains the `#[ignore]` one in `tests/ntp.rs`.

## Next Phase Readiness

- The mutation engine's write path is complete: a caller (the Phase 4 Tauri `commit_change`/`use_grace` commands) can `use mutation_engine::commit::{commit_change, CommitPaths}` and `mutation_engine::grace::use_grace`, passing a `QuotaDecision` from `quota::decide` and a `TrueTime` (production `SntpTrueTime`).
- Plan 02-05 (state_hmac Rust<->PowerShell parity) consumes the same `GuardState`/A3 recipe these writers re-sign with — no new persisted fields were added here, so the interop contract is unchanged.
- The crash-convergence ordering (sanctioned -> guard.json -> live) is the exact contract the Phase 3 PowerShell guard's verify-and-revert hook must honor; `commit_order.rs`'s local revert rule is the reference behavior to mirror.

## Self-Check: PASSED

- `crates/mutation-engine/src/commit.rs`, `src/grace.rs`, `tests/commit_order.rs`, `tests/grace.rs` all exist on disk.
- All four task commits present in git history: `1713fff` (RED1), `56ce60d` (GREEN1), `d548b93` (RED2), `f0c5dbb` (GREEN2).
- `cargo test -p mutation-engine --test commit_order --test grace` -> 8 + 5 = 13 passed, 0 failed. Full crate suite 62/62 green (1 live NTP test ignored). `cargo clippy -p mutation-engine` reports zero warnings in `commit.rs`/`grace.rs` (the remaining 5 lib lints are pre-existing doc-indentation/closure notes in `state.rs`/`classify.rs`, out of scope per the scope boundary).

---
*Phase: 02-mutation-engine*
*Completed: 2026-06-05*
