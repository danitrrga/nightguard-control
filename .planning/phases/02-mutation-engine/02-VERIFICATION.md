---
phase: 02-mutation-engine
verified: 2026-06-05T00:00:00Z
status: passed
score: 5/5
overrides_applied: 0
---

# Phase 2: Mutation Engine — Verification Report

**Phase Goal:** All edit-intent logic lives authoritatively in Rust — every proposed change is classified, loosening is rate-limited against a DST-aware weekly token budget, and grace is granted only against true time, committing atomically in the safe order.
**Verified:** 2026-06-05
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Each per-field change correctly labeled tighten/loosen/noop against the spec field table (unit-tested) | VERIFIED | `classify.rs` implements the full 11-row spec table (booleans, HH:MM times, numerics, lists, schedule days, timezone). 27 classify tests pass covering every row, missing-field=Noop, and `is_loosening_commit` helper. |
| 2 | A loosening commit spends exactly 1 of 3 weekly tokens; all-tighten/neutral free; no-op nothing; 0-token loosening blocked with an "available again Monday" reason | VERIFIED | `quota.rs::decide()` implements the 4-branch matrix. Constant `RESET_HINT = "available again Monday"` in the reason string. 9 quota tests pass: all-tighten free, all-noop is_noop=true, mixed loosen costs_token=true, loosen@3 blocked with reason containing the exact substring. |
| 3 | Weekly budget resets Monday 00:00 in configured tz, DST-aware (never naive +7*24h) | VERIFIED | `week.rs::most_recent_monday_midnight` uses `chrono_tz::Tz::from_local_datetime` with explicit `MappedLocalTime` matching (Single/Ambiguous/None). No `Duration::weeks(1)` in production code. Test `dst_transition_week_is_not_naive_168h` asserts the fall-back week is 169h, not 168h. 7 week tests pass including a DST fall-back case (Ambiguous → earliest, no panic). |
| 4 | "+8" grants once-per-true-day 8-min grace recorded in signed state; refused if used today OR NTP unreachable | VERIFIED | `grace.rs::use_grace` calls `true_time.now()` — refusing on `NtpUnreachable` via `From` impl. Derives `true_today` from the NTP unix_secs instant in the configured tz (not `Local::now()`). Checks `state.grace.date == true_today`. 5 grace tests pass: `ntp_unreachable_refuses_and_leaves_file_unchanged` uses `FakeTrueTime::unreachable()` and asserts `MutationError::NtpUnreachable`; `second_grant_same_true_day_is_refused_and_leaves_file_unchanged` asserts byte-unchanged file; `true_day_is_derived_in_configured_tz_not_utc` confirms tz boundary. |
| 5 | Every sanctioned commit atomically writes sanctioned snapshot + signed state BEFORE live config, re-signing all artifacts under a single-writer lock | VERIFIED | `commit.rs::commit_with_limit` implements 3-step ordered write (sanctioned → guard.json → live) inside `with_commit_lock` (fd-lock `RwLock::write()`). 8 commit_order tests pass including `crash_after_sanctioned_converges_to_old` (N=1, live still OLD) and `crash_after_guardjson_converges_to_new` (N=2, guard reverts live to NEW sanctioned). Full consistency asserted post-commit (config_hmac == HMAC(on-disk bytes)). |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `crates/mutation-engine/src/state.rs` | VERIFIED | `GuardState` + `LedgerEntry` + `GraceWindow` with full serde; `MutationError` thiserror enum; `compute_state_hmac` A3 recipe; `From<StoreError>` + `From<serde_json::Error>` |
| `crates/mutation-engine/src/sign.rs` | VERIFIED | `sign_config` over `canonicalize_bytes`; returns `(hex_tag, canonical_bytes)` so caller writes the signed bytes |
| `crates/mutation-engine/src/classify.rs` | VERIFIED | `pub enum Direction`; full spec table; `classify_change` pure fn; `is_loosening_commit` helper |
| `crates/mutation-engine/src/quota.rs` | VERIFIED | `QuotaDecision` struct; `decide()` pure fn; `RESET_HINT = "available again Monday"` |
| `crates/mutation-engine/src/week.rs` | VERIFIED | `most_recent_monday_midnight` + `next_monday_midnight` + `reset_decision`; `from_local_datetime` DST handling |
| `crates/mutation-engine/src/ntp.rs` | VERIFIED | `TrueTime` trait; `SntpTrueTime` impl; `FakeTrueTime` (ok + unreachable); `NtpUnreachable` with `From` impl |
| `crates/mutation-engine/src/grace.rs` | VERIFIED | `use_grace` under `with_commit_lock`; NTP-only; tz-local true-today; refuses on reuse and unreachable |
| `crates/mutation-engine/src/commit.rs` | VERIFIED | `with_commit_lock` (fd-lock exclusive); `commit_change` / `commit_with_limit` ordered 3-step; `CommitPaths` |
| `crates/mutation-engine/src/bin/state_interop_cli.rs` | VERIFIED | `emit-state-hmac` / `verify-state-hmac` subcommands; reuses `GuardState::compute_state_hmac`; writes `.signbytes` |
| `scripts/interop/run_state_interop_gate.ps1` | VERIFIED | PS 5.1 gate; 3 checks (Rust→PS, PS→Rust, tamper); exits 0; gated on `$LASTEXITCODE` |
| `scripts/interop/state_interop.ps1` | VERIFIED | `Get-StateHmacHex` over `.signbytes` via `Get-FileHmacHex`; ASCII-only; foreach byte construction |
| `crates/mutation-engine/Cargo.toml` | VERIFIED | `trust-kernel = { path = "../trust-kernel" }`; all dep pins present; `[[bin]] state_interop_cli` stanza |
| `Cargo.toml` (workspace root) | VERIFIED | `members = ["crates/trust-kernel", "crates/mutation-engine"]` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `quota.rs` | `classify.rs` | `Direction` + `is_loosening_commit` | WIRED | `use crate::classify::{is_loosening_commit, Direction};` used in `decide()` |
| `quota.rs` | `week.rs` | `next_monday_midnight` + `reset_decision` | WIRED | `use crate::week::{next_monday_midnight, reset_decision};` used in `decide()` |
| `grace.rs` | `ntp.rs` | `TrueTime` trait | WIRED | `use crate::ntp::TrueTime;` in `use_grace` signature; `FakeTrueTime` used in all 5 grace tests |
| `commit.rs` | `trust_kernel::atomic_write` | ordered sanctioned→guard.json→live writes | WIRED | `use trust_kernel::{atomic_write, write_canonical_text};`; called in `commit_with_limit` steps 1/2/3 |
| `sign.rs` | `trust_kernel::hmac::sign_bytes` | `canonicalize_bytes` → `sign_bytes` → `tag_to_hex` | WIRED | Direct call chain in `sign_config`; the `config_hmac` and `state_hmac` recipes both use it |
| `run_state_interop_gate.ps1` | `state_interop_cli` Rust bin | drives via `Invoke-Cli` | WIRED | Gate builds `--bin state_interop_cli`, invokes `emit-state-hmac` and `verify-state-hmac`; confirmed by live gate run |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `commit.rs::commit_with_limit` | `new_state` (GuardState) | `build_new_state` over prior `read_state(guard_json)` + `sign_config` | Yes — HMAC over canonical bytes; increments `weekly_spent`; appends ledger | FLOWING |
| `grace.rs::use_grace` | `window` (GraceWindow) | `true_time.now()` unix_secs → `true_day()` + arithmetic | Yes — NTP timestamp + 480s; no static values | FLOWING |
| `quota.rs::decide` | `QuotaDecision` | `reset_decision` + `is_loosening_commit` + `state.weekly_spent` | Yes — derived from live state and DST-aware Monday computation | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All mutation-engine tests | `cargo test -p mutation-engine` | 62 total: 61 passed, 1 ignored (live NTP), 0 failed | PASS |
| classify tests (27) | `cargo test -p mutation-engine --test classify` | 27 passed | PASS |
| week tests (7) | `cargo test -p mutation-engine --test week` | 7 passed; `dst_transition_week_is_not_naive_168h` asserts 169h | PASS |
| quota tests (9) | `cargo test -p mutation-engine --test quota` | 9 passed; `blocked_decision_reason_mentions_available_again_monday` asserts substring | PASS |
| grace tests (5) | `cargo test -p mutation-engine --test grace` | 5 passed; `ntp_unreachable_refuses_and_leaves_file_unchanged` uses `FakeTrueTime::unreachable()` | PASS |
| commit_order tests (8) | `cargo test -p mutation-engine --test commit_order` | 8 passed; crash-convergence for N in {0,1,2,3} | PASS |
| state tests (4) | `cargo test -p mutation-engine --test state` | 4 passed; round-trip, state_hmac reproducibility, sign-the-bytes, CRLF/LF parity | PASS |
| ntp tests (2+1 ignored) | `cargo test -p mutation-engine --test ntp` | 2 passed (fake-based); 1 ignored (live UDP) | PASS |

---

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| `scripts/interop/run_state_interop_gate.ps1` | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/interop/run_state_interop_gate.ps1` | exit=0; all 3 checks PASS (Rust→PS: identical=True; PS→Rust: exit=0; Tamper: rust exit=2, ps tag differs=True) | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RULE-01 | 02-02 | Per-field tighten/loosen/noop classifier | SATISFIED | `classify.rs` + 27 classify tests green |
| RULE-02 | 02-02 | Loosening commit costs 1 of 3 weekly tokens; tighten/neutral free; no-op nothing | SATISFIED | `quota.rs::decide()` + 9 quota tests green |
| RULE-03 | 02-02 | Weekly reset Monday 00:00 tz DST-aware (no naive +7*24h) | SATISFIED | `week.rs` + 7 week tests including DST 169h assertion |
| RULE-04 | 02-02 | 0-token loosen blocked with "available again Monday" | SATISFIED | `RESET_HINT` constant + `blocked_decision_reason_mentions_available_again_monday` test |
| RULE-05 | 02-03 + 02-04 | "+8" once-per-true-day NTP-boxed grace, refused on reuse or NTP unreachable | SATISFIED | `ntp.rs` TrueTime trait + `grace.rs` + 5 grace tests; `FakeTrueTime::unreachable()` test proves NTP refusal |
| RULE-06 | 02-01 + 02-04 + 02-05 | Atomic ordered commit + re-signing + A3 state_hmac cross-language parity | SATISFIED | `commit.rs` 3-step order under fd-lock + 8 commit_order tests + PS interop gate exit=0 |

---

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `week.rs` lines 9, 34 | Mentions `Duration::weeks(1)` and `+7*24h` | None | These appear only in documentation comments explicitly forbidding the pattern — not in production code. Grep of actual Rust code confirms no forbidden arithmetic is used. |

No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER found in any Phase 2 file.

---

### Human Verification Required

None — all success criteria are mechanically verifiable and all spot-checks were executed.

---

## Gaps Summary

No gaps. All 5 ROADMAP success criteria are VERIFIED with passing tests and a passing PowerShell gate. All 6 requirement IDs (RULE-01 through RULE-06) are covered with real test backing.

The phase delivers exactly what the goal specifies: all edit-intent logic lives in Rust, classification is spec-table-faithful, the weekly token budget is DST-aware with no naive week arithmetic, grace is NTP-boxed and refused on NTP failure or same-day reuse, and every sanctioned commit writes in the safe convergence order under a single-writer lock. The Rust↔PowerShell state_hmac parity gate closes Assumption A3 in-phase.

---

_Verified: 2026-06-05_
_Verifier: Claude (gsd-verifier)_
