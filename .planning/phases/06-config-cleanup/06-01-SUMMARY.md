---
phase: 06-config-cleanup
plan: 01
subsystem: api
tags: [rust, classifier, yaml, mutation-engine, linux-port, blocking]

# Dependency graph
requires:
  - phase: 02-mutation-engine
    provides: the RULE-01 direction classifier (FIELD_TABLE, read_field, classify_field) that this plan re-points
provides:
  - "FIELD_TABLE classifies the Linux `blocking:` model (browser_extension + native_apps) instead of the dead Windows `watchdog.apps` (uwp/package_id) list"
  - "Stable key path `blocking.native_apps.blacklist` for Phase 8's native blocker to read"
  - "mutation-engine package now compiles on the Linux port (Windows-only state_interop_cli bin gated to #[cfg(windows)])"
affects: [08-native-blocker, 06-02-instance-rebaseline, phase-10-tauri-linux-port]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Windows-only interop bins gated with #[cfg(windows)] + a no-op non-Windows main so the package still links on Linux"

key-files:
  created:
    - .planning/phases/06-config-cleanup/06-01-SUMMARY.md
  modified:
    - crates/mutation-engine/src/classify.rs
    - crates/mutation-engine/tests/classify.rs
    - crates/mutation-engine/tests/quota.rs
    - crates/mutation-engine/src/bin/state_interop_cli.rs

key-decisions:
  - "extension_id is NOT a FIELD_TABLE row — an id change is neither tighten nor loosen, so it reads Noop by omission (D-2)"
  - "blocking.browser_extension.enabled + blocking.native_apps.enabled = BoolTrueIsStrict; blocking.native_apps.blacklist = ListRemoveLoosens; watchdog.enabled/check_interval_seconds kept unchanged (D-2)"
  - "Rule-3 blocker fix: the Windows-only state_interop_cli bin (#[cfg(windows)] DPAPI key path) was gated to Windows so cargo test could run on Linux at all — Windows behavior byte-for-byte unchanged"

patterns-established:
  - "Linux-port: a Windows-only bin that imports a #[cfg(windows)] symbol is gated to #[cfg(windows)] with a stub non-Windows main rather than deleted, preserving the Windows interop gate"

requirements-completed: [LXCF-01]

# Metrics
duration: 14 min
completed: 2026-06-22
---

# Phase 6 Plan 01: Config Cleanup (classifier product half) Summary

**Re-pointed the Rust direction-classifier's FIELD_TABLE from the dead Windows `watchdog.apps` (uwp/package_id) list to the Linux `blocking:` model (`browser_extension` + `native_apps`), so loosening/tightening of the new keys classifies correctly and no product code carries the Windows shape.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-06-22T17:50:00Z (approx)
- **Completed:** 2026-06-22T18:04:18Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments
- `FIELD_TABLE` now classifies `blocking.browser_extension.enabled` + `blocking.native_apps.enabled` (BoolTrueIsStrict) and `blocking.native_apps.blacklist` (ListRemoveLoosens), per D-2; the `watchdog.apps` FieldSpec is gone.
- `//!` doc table + stale doc strings updated; `extension_id` intentionally omitted (id change = Noop).
- `watchdog.enabled` + `watchdog.check_interval_seconds` classification left untouched (revert-watchdog cadence preserved).
- Grep gate clean: zero `watchdog\.apps` / `uwp` / `package_id` in `crates/mutation-engine`.
- mutation-engine now compiles on Linux (the Windows-only `state_interop_cli` bin was the only thing blocking `cargo test`).

## Task Commits

Each task was committed atomically (TDD: test → feat):

1. **RED — failing classifier tests for the blocking.* model** - `44b9180` (test)
2. **GREEN — re-point FIELD_TABLE + Rule-3 bin blocker fix** - `1634c6b` (feat)

_No REFACTOR commit — the GREEN implementation was already minimal and clean._

## Files Created/Modified
- `crates/mutation-engine/src/classify.rs` - Removed the `watchdog.apps` FieldSpec; added the three `blocking.*` rows; updated the `//!` field table and the `ListRemoveLoosens` / `compare_lists` doc strings.
- `crates/mutation-engine/tests/classify.rs` - Replaced the `watchdog.apps` remove/add tests with `blocking.native_apps.blacklist` remove(Loosen)/add(Tighten); added `blocking.native_apps.enabled` + `blocking.browser_extension.enabled` true↔false cases, an `extension_id`-only Noop case, and a 3-deep absent-field Noop case.
- `crates/mutation-engine/tests/quota.rs` - Swapped the `watchdog.apps` loosen/tighten fixture labels for `blocking.native_apps.blacklist` (synthetic `dirs()` tuples, so still exercises the quota matrix).
- `crates/mutation-engine/src/bin/state_interop_cli.rs` - Gated the Windows-only DPAPI interop bin to `#[cfg(windows)]` with a no-op non-Windows `main` (blocker fix, see Deviations).

## Decisions Made
- Followed D-1/D-2 exactly: the three `blocking.*` rows with the specified kinds; `extension_id` omitted; `watchdog.enabled` + `watchdog.check_interval_seconds` retained.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Gate the Windows-only `state_interop_cli` bin to `#[cfg(windows)]`**
- **Found during:** Task 1 (running the plan's `cargo test -p mutation-engine` verification)
- **Issue:** `src/bin/state_interop_cli.rs` imports `trust_kernel::key::load_or_create_key`, which is `#[cfg(windows)]`-only. On the Linux port the whole `mutation-engine` package failed to compile (`E0432`), so **no** test target in the crate could run — the plan's verification command was unrunnable. Confirmed pre-existing on the clean tree at HEAD `57a4ade` (not introduced by this plan).
- **Fix:** Gated the entire bin body to `#[cfg(windows)]` and added a `#[cfg(not(windows))]` no-op `main` that prints a "Windows-only" notice. Windows compilation/behavior is byte-for-byte unchanged.
- **Files modified:** crates/mutation-engine/src/bin/state_interop_cli.rs
- **Verification:** `cargo build -p mutation-engine --bin state_interop_cli` clean on Linux; `cargo test -p mutation-engine --test classify --test quota` now runs (37 + 9 green).
- **Committed in:** `1634c6b` (GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 Rule-3 blocking).
**Impact on plan:** Necessary to make the plan's own verification command runnable on Linux. The fix is confined to a Windows-only test harness bin and does not touch any product classification logic. No scope creep.

## Issues Encountered
- **Pre-existing, out-of-scope Linux-port build debt (NOT fixed — outside this plan's `crates/mutation-engine` scope):**
  - `crates/trust-kernel/src/bin/interop_cli.rs` fails to compile on Linux (same `load_or_create_key` `#[cfg(windows)]` issue) → `cargo build --workspace` does not link on Linux.
  - `crates/trust-kernel/src/key.rs:14` has a pre-existing `unused import: std::path::Path` warning.
  - `crates/mutation-engine/tests/lock_probe.rs` fails on Linux (spawns `powershell`, absent) — a Windows-only interop test.
  - These all reproduce on the clean tree at HEAD and are unrelated to LXCF-01. The plan's acceptance criterion "`cargo build` (workspace) is warning-clean" is satisfied **for the in-scope `mutation-engine` crate** (zero warnings); the broader workspace's pre-existing Windows-only bins/tests are Linux-port debt for later phases (Phase 7/10 retire the DPAPI/PowerShell paths).

## Next Phase Readiness
- LXCF-01 product half is complete: the classifier names `blocking.native_apps.blacklist`, the stable path Phase 8's native blocker will read.
- 06-02 (instance re-baseline + re-sign) remains blocked by P0 — the Linux Python trust stack (`ngcommon`/`guard`/control-CLI/`nightguard_watchdog` `.py`) is absent from disk and untracked in git (see STATE.md Blockers). 06-02 must not execute until those `.py` sources are restored and the watchdog is quiescent.

---
*Phase: 06-config-cleanup*
*Completed: 2026-06-22*
