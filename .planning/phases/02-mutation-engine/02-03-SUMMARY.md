---
phase: 02-mutation-engine
plan: 03
subsystem: ntp-true-time
tags: [rust, sntpc, ntp, true-time, trait-injection, fail-closed, rule-05]

# Dependency graph
requires:
  - phase: 02-mutation-engine
    plan: 01
    provides: MutationError (NtpUnreachable variant), mutation-engine crate w/ sntpc 0.10.1 + sntpc-net-std 1.2 pins
provides:
  - TrueTime trait (offline-injectable true-time provider abstraction)
  - NtpTrueTime { unix_secs, frac, offset } verified-instant type
  - NtpUnreachable typed refusal + From<NtpUnreachable> for MutationError
  - SntpTrueTime production impl (sntpc sync get_time over UdpSocketWrapper, fallback host list)
  - FakeTrueTime test helper for deterministic offline quota/grace tests
affects: [02-04-commit-grace]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Live UDP hidden behind a TrueTime trait so downstream time-gated logic is offline-testable with an injected fake"
    - "Fail-closed true-time: every sntpc error (incl. non_exhaustive variants via catch-all Err(_)) maps to NtpUnreachable; no system/local clock fallback path exists"
    - "Built-in NTP fallback host list, try-each first-success-wins, all-fail = refuse"

key-files:
  created:
    - crates/mutation-engine/tests/ntp.rs
  modified:
    - crates/mutation-engine/src/ntp.rs

key-decisions:
  - "TrueTime trait is the seam: SntpTrueTime (real UDP) in production, FakeTrueTime in tests — only the #[ignore] live test touches a real socket"
  - "NtpUnreachable kept as its own zero-size type AND folded into MutationError via From, so callers can pattern-match the refusal locally yet still `?` it upward"
  - "i64::from(res.sec()) widens the u32 NTP seconds to the i64 ledger/grace timestamp type used in guard.json (unix_secs)"
  - "sntpc::Error is #[non_exhaustive]; the catch-all Err(_) arm is mandatory and intentional (any SNTP error = unverified time = refuse)"

requirements-completed: [RULE-05]

# Metrics
duration: 6min
completed: 2026-06-05
---

# Phase 2 Plan 03: NTP True-Time Module (TrueTime trait, RULE-05 time half) Summary

**SNTP true-time obtained via `sntpc 0.10.1` + `sntpc-net-std` and hidden behind a `TrueTime` trait, so any SNTP error fails closed to a typed `NtpUnreachable` (never the app clock) and plan 02-04's grace logic stays offline-testable with an injected fake.**

## Performance

- **Duration:** ~6 min
- **Completed:** 2026-06-05
- **Tasks:** 1 (TDD: RED -> GREEN)
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- Defined the `TrueTime` trait + `NtpTrueTime`/`NtpUnreachable` types in `ntp.rs`, turning the Phase 1 placeholder into the RULE-05 true-time source.
- Implemented `SntpTrueTime` following RESEARCH Pattern 1 verbatim: bind `0.0.0.0:0`, 2s read timeout, `UdpSocketWrapper`, `NtpContext::new(StdTimestampGen::default())`, IPv4 `to_socket_addrs()`, `sntpc::sync::get_time`, reading `.sec()/.sec_fraction()/.offset()`.
- Mapped EVERY `sntpc::Error` variant (Network, AddressResolve, timeout-as-Network, malformed response, KissOfDeath, and any future `#[non_exhaustive]` variant) to `NtpUnreachable` via a mandatory catch-all — confirmed no path returns system/local time (threat T-02-08 fail-closed).
- Added a built-in fallback host list (time.cloudflare.com, time.google.com, pool.ntp.org per A4) tried first-success-wins; all-fail (or empty list) = refuse.
- Added `FakeTrueTime::{ok, unreachable}` so plan 02-04's quota/grace tests run deterministically offline.
- Added `From<NtpUnreachable> for MutationError` so the refusal `?`-propagates into the engine error surface.

## Task Commits

Each task was committed atomically:

1. **Task 1: ntp.rs sntpc sync wrapper + TrueTime trait (TDD)**
   - RED: `94fb5f5` (test) -- 2 fake-based tests fail to compile (trait/types absent) + 1 `#[ignore]` live test
   - GREEN: `00b4c9b` (feat) -- trait, types, SntpTrueTime, FakeTrueTime; fake tests green, live ignored

_No REFACTOR commit: the GREEN implementation was already minimal and clean (zero clippy warnings in `ntp.rs`)._

## Files Created/Modified
- `crates/mutation-engine/src/ntp.rs` - `TrueTime` trait, `NtpTrueTime`, `NtpUnreachable` (+`From<...> for MutationError`), `SntpTrueTime` (real SNTP w/ fallback list), `FakeTrueTime` (offline test helper). `//!` doc cites RULE-05 + the "never trust app clock" invariant + the no-analog note.
- `crates/mutation-engine/tests/ntp.rs` - 2 always-run fake-based tests (fixed-instant consumed offline; unreachable propagates as refusal) + 1 `#[ignore]` live SNTP test (asserts plausible post-2025 unix time).

## Decisions Made
- **TrueTime trait is the seam (offline-testability):** `SntpTrueTime` is the only thing that touches a socket; everything downstream depends on the trait, so grace logic in 02-04 injects `FakeTrueTime` and runs with zero network. Only the `#[ignore]` live test exercises real UDP.
- **NtpUnreachable is both a local type and a MutationError variant:** kept as a zero-size struct so callers can `matches!(.., Err(NtpUnreachable))` precisely, plus `From<NtpUnreachable> for MutationError` for `?`-ergonomics in the commit/grace path.
- **Mandatory catch-all on `sntpc::Error`:** the enum is `#[non_exhaustive]` (verified in the vendored 0.10.1 source), so `Err(_) => NtpUnreachable` is both required to compile and the correct fail-closed semantics — any SNTP error means unverified time means refuse.
- **`i64::from(res.sec())`:** widens the u32 NTP `seconds` to the i64 `unix_secs` used by `guard.json` ledger/grace timestamps, keeping the true-time type aligned with the locked state model.

## Deviations from Plan

None - plan executed exactly as written. (The plan offered "or fold into MutationError::NtpUnreachable -- expose a conversion"; both were done: the standalone type AND the `From` conversion, which is the union of the plan's stated options, not a deviation.)

## API Verification Note (pre-implementation)
Before writing code, the exact `sntpc 0.10.1` + `sntpc-net-std 1.2.1` API was re-confirmed against the vendored crate sources in the local cargo registry (not training data): `sync::get_time(addr, &socket, ctx)`, `NtpResult::{sec, sec_fraction, offset}` accessors, `Error::{Network, AddressResolve, ...}` (`#[non_exhaustive]`), and `UdpSocketWrapper::new(UdpSocket)`. All matched RESEARCH Pattern 1 exactly.

## Issues Encountered
- None. The pre-existing `cargo clippy` `doc_lazy_continuation` warnings in `state.rs` (from plan 02-01) are out of scope for this plan and were left untouched per the scope boundary; `ntp.rs` and `tests/ntp.rs` are clippy-clean.

## User Setup Required
None - no external service configuration required. Live NTP is exercised only by the `#[ignore]` test, run on demand with `cargo test -p mutation-engine --test ntp -- --ignored`.

## Next Phase Readiness
- Plan 02-04 (commit + grace) can now `use mutation_engine::ntp::{TrueTime, NtpTrueTime, SntpTrueTime, FakeTrueTime}` to derive the grace true-day from verified true time and to test the once-per-day / NTP-unreachable refusal paths offline.
- The fail-closed guarantee (no clock fallback) is established and tested; the Phase 3 PowerShell guard will independently re-check timing with its own NTP per the design-spec defense-in-depth (threat T-02-09 residual).

## Self-Check: PASSED

- `crates/mutation-engine/src/ntp.rs` exists; `crates/mutation-engine/tests/ntp.rs` exists.
- Commits `94fb5f5` (RED) and `00b4c9b` (GREEN) are present in git history.
- `cargo test -p mutation-engine --test ntp` -> 2 passed, 1 ignored; `cargo build -p mutation-engine` exits 0; full crate suite green.

---
*Phase: 02-mutation-engine*
*Completed: 2026-06-05*
