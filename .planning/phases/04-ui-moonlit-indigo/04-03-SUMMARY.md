---
phase: 04-ui-moonlit-indigo
plan: 03
subsystem: ui
tags: [tauri, ipc, hmac, verify, quota, grace, commit, fail-closed, dto]

# Dependency graph
requires:
  - phase: 04-ui-moonlit-indigo
    plan: 01
    provides: "AppCtx (.manage()d key+paths+tz), StateDto/ClassifyDto/FieldDirection DTOs, IpcError (thiserror + From<MutationError>), four frozen #[tauri::command] signatures"
  - phase: 04-ui-moonlit-indigo
    plan: 02
    provides: "pure lock_status(config_yaml, now) -> LockStatus (locked + boundary, grace_active=false left for get_state to overlay)"
  - phase: 01-trust-kernel
    provides: "canonicalize_bytes, hmac::verify_bytes (constant-time)"
  - phase: 02-mutation-engine
    provides: "classify::classify_change, quota::decide, commit::commit_change, grace::use_grace, ntp::SntpTrueTime/TrueTime, GuardState::compute_state_hmac"
provides:
  - "Real get_state: read + re-verify both HMACs, worst-case on tamper, derive StateDto"
  - "Real classify_change: per-field directions + quota preview (allowed/reason/costs_token)"
  - "Real commit_change: gate -> true-time -> engine ordered writer -> re-read (D-09)"
  - "Real use_grace: grace::use_grace -> re-read (D-09)"
  - "Private build_state_dto helper — the single read/verify/derive/worst-case path"
affects: [04-04-status-view, 04-05-edit-panel-and-actions]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "build_state_dto = single source of truth for re-verification + guard worst-casing parity (one place sets weekly_spent=3)"
    - "commit_change/use_grace ALWAYS re-read freshly-signed state via build_state_dto (D-09) — never an optimistic local DTO"
    - "defense-in-depth: command re-checks decision.allowed before the engine writer (commit.rs:148 parity)"
    - "true time fail-closed (SntpTrueTime + map_err) for the ledger; app-side display time stays advisory (time_unverified=true)"
    - "managed AppCtx added to classify_change as a body-fill (Tauri-injected; JS invoke shape unchanged)"

key-files:
  created: []
  modified:
    - src-tauri/src/commands.rs

key-decisions:
  - "build_state_dto is the ONE read/verify/derive/worst-case helper; get_state + commit_change + use_grace all return its output so verification + worst-casing live in a single place"
  - "config_hmac re-verified with constant-time verify_bytes over canonicalize_bytes(raw_config); state_hmac via the A3 string-hex compare of compute_state_hmac (the sanctioned recipe, not a == on a config tag)"
  - "On state_hmac mismatch the DTO worst-cases token/grace EXACTLY like the guard (weekly_spent=3, tokens_remaining=0, grace_available_today=false, grace_active=false, maximal_lockout=true); lock/boundary still come from lock_status (a tampered guard.json never relaxes the curfew window)"
  - "classify_change takes a managed AppCtx arg (quota::decide needs the live state + tz); allowed as a body-fill because Tauri injects managed state and the JS call shape is unchanged"
  - "Frozen-contract dead code (AppCtx.data_dir, IpcError::VerifyFailed) annotated #[allow(dead_code)] rather than removed — keeps the plan-01 contract intact while clearing warnings"
  - "guard.json re-read for the DTO uses serde_json directly (commit::read_state is private to the engine); same GuardState model, same compute_state_hmac recipe"

patterns-established:
  - "IPC command = thin glue: classify/decide/commit/grace are the engine's; the command only gates, sources true time, and re-reads"
  - "grace overlay seam: lock_status leaves grace_active=false; get_state overlays an active signed guard.json window (boundary_kind=grace_end, boundary_unix=window_end)"

requirements-completed: [UI-01, UI-02, UI-03, UI-04]

# Metrics
duration: 5min
completed: 2026-06-09
---

# Phase 4 Plan 03: IPC Command Bodies (get_state / classify_change / commit_change / use_grace) Summary

**The four frozen IPC commands now wrap the kernel + engine exactly: `get_state` reads and re-verifies both HMACs and derives a guard-parity StateDto through one `build_state_dto` helper that worst-cases on any tamper; `classify_change` previews direction + quota; `commit_change` gates -> true-time -> the engine's ordered locked writer -> re-read; `use_grace` grants -> re-read. The app is now a faithful, never-optimistic mirror of enforced state (D-03/D-09).**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-09T09:39:35Z
- **Completed:** 2026-06-09T09:44:30Z
- **Tasks:** 2 auto
- **Files created:** 0
- **Files modified:** 1 (`src-tauri/src/commands.rs`)

## Accomplishments

- **`get_state` (real body):** reads `config.yaml` + `guard.json` from the resolved data dir; either absent => `IpcError::NotInitialized`. Re-verifies `config_hmac` with constant-time `verify_bytes` over `canonicalize_bytes(raw_config)` and `state_hmac` via the A3 `compute_state_hmac` recipe. Derives `locked`/`boundary` from `lock_status`, overlays an active signed grace window (`boundary_kind="grace_end"`), and reads `effective_spent`/`next_reset` from `quota::decide(&[], ...)`.
- **`build_state_dto` helper:** the SINGLE read/verify/derive/worst-case assembly. On `state_hmac` mismatch it worst-cases the token/grace surface EXACTLY like the guard (`weekly_spent=3, tokens_remaining=0, grace_available_today=false, grace_active=false, maximal_lockout=true`) — applied in exactly one place (grep: literal `WEEKLY_TOKENS` worst-case set once). On `config_hmac` mismatch: `config_verified=false`, `maximal_lockout=true`.
- **`classify_change` (real body):** `classify::classify_change` -> per-field `tighten`/`loosen`/`noop`; `quota::decide` against the live `GuardState` -> `allowed`/`reason`/`costs_token` so the UI can disable-with-reason at 0 tokens (UI-04).
- **`commit_change` (real body):** classifies `new_yaml` vs the live config, re-checks `decision.allowed` IN the command before any write (defense in depth, `commit.rs:148` parity), sources TRUE NTP time fail-closed for the ledger, commits via the engine's ONLY ordered fd-locked writer `commit::commit_change`, then RE-READS the freshly-signed state via `build_state_dto` (D-09).
- **`use_grace` (real body):** `grace::use_grace` (NtpUnreachable / GraceAlreadyUsedToday fold to `IpcError` via `From<MutationError>`), then RE-READS via `build_state_dto` (D-09); the overlay surfaces `grace_active=true`.
- `cargo check -p nightguard-control` exits 0 with ZERO warnings; `cargo clippy -p nightguard-control` reports ZERO warnings for the modified crate.

## Task Commits

1. **Task 1: Real get_state body + shared build_state_dto helper** - `b27fe11` (feat)
2. **Task 2: Real classify_change / commit_change / use_grace bodies** - `4dbc5b9` (feat)

## Files Created/Modified

- `src-tauri/src/commands.rs` (modified) - Filled all four command bodies; added private helpers `build_state_dto`, `read_guard_state`, `direction_str`, `today_in_tz`, `hex_to_tag32`, and a `WEEKLY_TOKENS` const; imported `verify_bytes`, `canonicalize_bytes`, `lock_status`, `quota`, `classify`, `commit`, `grace`, `SntpTrueTime`+`TrueTime`, `GuardState`, `Utc`. All command SIGNATURES preserved except the sanctioned managed-state body-fill on `classify_change`.

## Decisions Made

- **One verification path:** `get_state`, `commit_change`, and `use_grace` all return `build_state_dto(&ctx)`, so re-verification and the guard worst-casing parity live in exactly one place (single source of truth for "never look less locked than the guard").
- **State re-read via serde_json, not `commit::read_state`:** the engine's `read_state` is private; the DTO path deserializes `guard.json` directly into the same `GuardState` model and uses the same `compute_state_hmac` recipe, so verification is identical.
- **`classify_change` managed-state body-fill:** added `state: tauri::State<AppCtx>` because `quota::decide` needs the live state + tz. Tauri injects managed state and the JS `invoke('classify_change', { oldYaml, newYaml })` shape is unchanged — this is a body fill, not a contract change (the plan explicitly sanctions it).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Imported `mutation_engine::ntp::TrueTime`**
- **Found during:** Task 2 (`cargo check`)
- **Issue:** `SntpTrueTime::default().now()` failed to resolve (`E0599`) — the `now()` method comes from the `TrueTime` trait, which must be in scope to call it on the concrete type.
- **Fix:** Changed the import to `use mutation_engine::ntp::{SntpTrueTime, TrueTime};`.
- **Files modified:** src-tauri/src/commands.rs
- **Verification:** `cargo check -p nightguard-control` exits 0.
- **Committed in:** `4dbc5b9`

**2. [Rule 1 - Warning hygiene] Annotated frozen-contract dead code**
- **Found during:** Task 2 (`cargo check` warnings)
- **Issue:** Replacing the stubs left `AppCtx.data_dir` and `IpcError::VerifyFailed` unread (the stubs touched `data_dir`; the real read path surfaces verification failure in the DTO rather than returning `VerifyFailed`). Both are frozen plan-01 contract surface, not removable.
- **Fix:** Added `#[allow(dead_code)]` + a doc note to each (reserved contract surface; `data_dir` is consumed by plan-03's fs:scope tightening, `VerifyFailed` is for callers preferring a hard error). The signatures/contract are unchanged.
- **Files modified:** src-tauri/src/commands.rs
- **Verification:** `cargo check -p nightguard-control` exits 0 with zero warnings.
- **Committed in:** `4dbc5b9`

**Total deviations:** 2 auto-fixed (1 Rule 3 blocking, 1 Rule 1 warning hygiene). No signature contract changes; no scope creep.

## Deferred Issues

Pre-existing clippy warnings in `crates/mutation-engine` (NOT this plan's crate, NOT touched here) logged to `.planning/phases/04-ui-moonlit-indigo/deferred-items.md`:
- `classify.rs:304` redundant_closure; `state.rs:13-15` doc-list-item-without-indentation (x3).
`cargo clippy -p nightguard-control` (the crate this plan modified) reports ZERO warnings.

## Threat Surface

All plan threat-model mitigations applied in `build_state_dto` / the command bodies:
- **T-04-08** (tampered guard.json looks less-locked): `state_hmac` re-verified via `compute_state_hmac`; mismatch worst-cases `weekly_spent=3 / tokens_remaining=0 / grace_available_today=false / grace_active=false / maximal_lockout` in the one helper.
- **T-04-09** (hand-edited config shown valid): `config_hmac` re-verified with constant-time `verify_bytes` over `canonicalize_bytes`; `config_verified=false` => `maximal_lockout`.
- **T-04-10** (timing side-channel): `verify_bytes` (subtle-backed) for the config tag; no `==` on a config tag byte array (grep-confirmed — the only `==` is the sanctioned A3 state hex-string compare).
- **T-04-11** (quota bypass via bespoke write): `if !decision.allowed` re-check before the writer + write ONLY via `commit::commit_change` (grep: no `fs::write`/`atomic_write`/`write_canonical_text` in commands.rs).
- **T-04-12** (sign-vs-write race): both mutating commands use the engine's `with_commit_lock`-wrapped `commit_change` / `use_grace`; no config write in the command.
- **T-04-13** (grace/commit without true time): `use_grace` uses `SntpTrueTime` (fail-closed); `commit_change` ledger timestamp requires true time fail-closed; display time stays advisory (`time_unverified=true`).

No security surface beyond the plan's threat_model was introduced.

## Known Stubs

None — all four command bodies are now real. The frontend Status-view render + edit panel remain for plans 04/05 (out of this plan's scope); the IPC contract they consume is now fully implemented.

## Self-Check: PASSED

- FOUND: src-tauri/src/commands.rs (435 lines; all four bodies filled)
- FOUND commit: b27fe11 (Task 1, feat)
- FOUND commit: 4dbc5b9 (Task 2, feat)
- `cargo check -p nightguard-control` exits 0, zero warnings
- grep: `verify_bytes` (config) + `compute_state_hmac` (state) present; `lock_status` called; worst-case `WEEKLY_TOKENS` set once in build_state_dto; `if !decision.allowed` before `commit::commit_change`; `SntpTrueTime` + `.map_err` fail-closed; both commit/grace end in `build_state_dto`; no hand-rolled writer.

---
*Phase: 04-ui-moonlit-indigo*
*Completed: 2026-06-09*
