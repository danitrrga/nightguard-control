---
phase: 04-ui-moonlit-indigo
plan: 01
subsystem: ui
tags: [tauri, tauri-v2, vite, typescript, ipc, vanilla-ts, dpapi, hmac]

# Dependency graph
requires:
  - phase: 01-trust-kernel
    provides: trust_kernel::key::load_or_create_key (DPAPI Scope::User key load)
  - phase: 02-mutation-engine
    provides: mutation_engine::{MutationError, commit::CommitPaths} (error folding + commit paths)
  - phase: 03-enforcement-guard
    provides: NIGHTGUARD_DIR data-dir resolution + fixed filenames the app must mirror
provides:
  - Tauri v2 app shell as the third Cargo workspace member (nightguard-control)
  - Fixed IPC contract — IpcError, AppCtx, StateDto/ClassifyDto, four #[tauri::command] stubs
  - Frontend toolchain (package.json, vite.config.ts, tsconfig.json, index.html, main.ts)
  - TS StateDto interface mirroring the Rust DTO (shared invoke contract)
affects: [04-02-lock-status, 04-03-status-view, 04-04-edit-panel, 04-05-actions]

# Tech tracking
tech-stack:
  added: [tauri 2.11.2, tauri-plugin-fs 2.5.1 (watch), tauri-build 2, "@tauri-apps/api 2.11", "@tauri-apps/plugin-fs 2.5", "@tauri-apps/cli 2.11", vite ^7, typescript ^5]
  patterns: ["thin main.rs + run() in lib.rs (v2 layout)", "IpcError = thiserror + Serialize-as-string + From<MutationError>", "AppCtx loaded once + .manage()d (key never crosses invoke)", "unix-secs i64 DTO timestamps", "command stubs with FINAL signatures filled by later plans"]

key-files:
  created:
    - src-tauri/Cargo.toml
    - src-tauri/build.rs
    - src-tauri/tauri.conf.json
    - src-tauri/capabilities/default.json
    - src-tauri/icons/icon.ico
    - src-tauri/src/main.rs
    - src-tauri/src/lib.rs
    - src-tauri/src/commands.rs
    - package.json
    - vite.config.ts
    - tsconfig.json
    - src/index.html
    - src/main.ts
  modified:
    - Cargo.toml
    - .gitignore

key-decisions:
  - "src-tauri is the third workspace member; root Cargo.toml stays the single [workspace] table (no nested workspace)"
  - "AppCtx::load fails closed when NIGHTGUARD_DIR is unset/empty (IpcError::NotInitialized) — mirrors the guard, never guesses"
  - "Placeholder get_state ships fail-closed (maximal_lockout=true, tokens=0, weekly_spent=3) so the scaffold never looks LESS locked than the guard (Pitfall 2 / T-04-03)"
  - "fs:scope left broad (**) with a deferred TODO to tighten to the resolved data dir in plan 03 (T-04-04)"

patterns-established:
  - "IpcError: thiserror enum + impl Serialize (serialize_str of to_string) + From<MutationError> — JS catch() receives the message"
  - "AppCtx holds key:[u8;32] + data_dir + CommitPaths + tz, built once and .manage()d; the key is host-memory only and never serialized into any DTO (T-04-01)"
  - "DTO timestamps are unix seconds i64 (engine/guard speak unix secs); TS formats them"
  - "Command stubs carry their FINAL signatures so downstream plans fill bodies without changing the contract (D-01)"

requirements-completed: [UI-01, UI-02, UI-03, UI-04]

# Metrics
duration: 7min
completed: 2026-06-09
---

# Phase 4 Plan 01: Tauri v2 App Shell + IPC Contract Summary

**Tauri v2 vanilla-TS app scaffolded as the third Cargo workspace member with the four named IPC commands registered against a fixed StateDto/ClassifyDto/IpcError contract, AppCtx resolving the guard's NIGHTGUARD_DIR data dir and loading the DPAPI .guardkey once.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-09T09:18:41Z
- **Completed:** 2026-06-09T09:25:33Z
- **Tasks:** 2 auto + 1 checkpoint (auto-approved in AUTO_MODE)
- **Files created:** 13
- **Files modified:** 2

## Accomplishments
- `src-tauri` added as the third workspace member; `cargo metadata` lists `nightguard-control`; exactly one `[workspace]` table (root).
- The four IPC commands (`get_state`, `classify_change`, `commit_change`, `use_grace`) registered in `generate_handler!` with their FINAL signatures; `cargo check -p nightguard-control` exits 0.
- `AppCtx::load` resolves the data dir from `NIGHTGUARD_DIR` (mirroring the guard's resolution), builds `CommitPaths`, and loads the `.guardkey` once via `trust_kernel::key::load_or_create_key` (Scope::User, single key path — T-04-02).
- `StateDto` (13 fields) + `ClassifyDto` defined as serde DTOs with unix-secs timestamps; the TS `interface StateDto` mirrors them field-for-field; `src/main.ts` invokes `get_state` from `@tauri-apps/api/core` (v2 path).
- Frontend toolchain installed and type-checks clean (`npm install` 0 vulnerabilities, `tsc --noEmit` exit 0).

## Task Commits

1. **Task 1: Scaffold src-tauri as third workspace member + frontend toolchain** - `9154769` (feat)
2. **Task 2: Define the IPC contract — AppCtx, DTOs, IpcError, four command stubs** - `e68c1ca` (feat)

**Plan metadata:** (final docs commit — see below)

## Files Created/Modified
- `Cargo.toml` - Added `"src-tauri"` to workspace `members`.
- `src-tauri/Cargo.toml` - tauri 2.11.2 + tauri-plugin-fs (watch) + path deps on ../crates/*; `[lib] crate-type` + tauri-build.
- `src-tauri/build.rs` - `tauri_build::build()`.
- `src-tauri/tauri.conf.json` - Window "main" titled "Nightguard Control", NSIS target, `../dist` frontendDist, devUrl :1420.
- `src-tauri/capabilities/default.json` - `core:default` + `fs:allow-watch`/`fs:allow-unwatch` + broad `fs:scope` (TODO: tighten in plan 03).
- `src-tauri/icons/icon.ico` - Minimal accent-colored ICO required by tauri-build (Rule 3 fix).
- `src-tauri/src/main.rs` - Thin v2 shim calling `nightguard_control_lib::run()`.
- `src-tauri/src/lib.rs` - `run()`: plugin-fs + `.manage(AppCtx)` + `generate_handler![4 cmds]`.
- `src-tauri/src/commands.rs` - IpcError, AppCtx, StateDto/ClassifyDto/FieldDirection, four command stubs.
- `package.json` / `vite.config.ts` / `tsconfig.json` - Frontend toolchain (api 2.11, plugin-fs, cli 2.11, vite 7, ts 5).
- `src/index.html` / `src/main.ts` - Shell DOM + `invoke<StateDto>('get_state')` wiring + TS StateDto contract.
- `.gitignore` - node_modules, dist, src-tauri/target, src-tauri/gen.

## Decisions Made
- Identifier set to `eu.tarraga.nightguard-control` (author domain, own brand — no borrowed identifiers).
- Bundle target NSIS only, unsigned (defer Authenticode per CLAUDE.md / for a publishable repo later).
- `AppCtx.tz` defaults to `Europe/Amsterdam` as advisory placeholder; plan 03 reads `config.timezone` and fills it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added src-tauri/icons/icon.ico**
- **Found during:** Task 2 (`cargo check`)
- **Issue:** `tauri-build` failed: `icons/icon.ico` not found; required for generating the Windows Resource file. The plan listed no icon asset.
- **Fix:** Generated a minimal valid 16x16 32bpp ICO filled with the Moonlit Indigo accent (#7aa2ff) and pointed `tauri.conf.json` `bundle.icon` at it.
- **Files modified:** src-tauri/icons/icon.ico, src-tauri/tauri.conf.json
- **Verification:** `cargo check -p nightguard-control` exits 0.
- **Committed in:** `e68c1ca`

**2. [Rule 3 - Blocking] Added tsconfig.json**
- **Found during:** Checkpoint automated verification (frontend build)
- **Issue:** `npm run build` runs `tsc && vite build`, but no `tsconfig.json` existed for `tsc` to resolve.
- **Fix:** Added a vanilla-TS-template tsconfig (strict, bundler resolution, `include: ["src"]`).
- **Files modified:** tsconfig.json
- **Verification:** `npx tsc --noEmit -p tsconfig.json` exits 0.
- **Committed in:** `e68c1ca`

---

**Total deviations:** 2 auto-fixed (both Rule 3 blocking)
**Impact on plan:** Both are standard scaffold assets the plan omitted; required for the Tauri build and the frontend `tsc` step. No scope creep — no behavior beyond the scaffold contract.

## Issues Encountered
- Initial `cargo metadata` failed because the `[lib]` manifest had no `src/lib.rs` yet — created a minimal placeholder `lib.rs` in Task 1, then fully replaced it with the real `run()` in Task 2.

## Checkpoint (human-verify, blocking) — AUTO_MODE

The plan's blocking `checkpoint:human-verify` (window opens, dev console logs a StateDto, no `invoke is not a function` / allowlist errors) was treated as auto-approved per the orchestrator's AUTO_MODE directive. Automated checks performed and passing:
- `cargo check -p nightguard-control` exits 0 (build + types compile).
- `cargo metadata --no-deps` lists `nightguard-control` as a workspace member.
- Four commands registered in `generate_handler!`; exactly 4 `#[tauri::command]` attributes.
- No `@tauri-apps/api/tauri` (v1) import in any source file.
- `npm install` succeeds (0 vulnerabilities); `npx tsc --noEmit -p tsconfig.json` exits 0.

**Deferred to the phase verifier:** the live `npx tauri dev` visual/runtime check (window titled "Nightguard Control" opens via WebView2 and the dev console logs the placeholder StateDto). This requires a display and a populated `NIGHTGUARD_DIR` and was not executed headlessly.

## Known Stubs
These are intentional contract stubs (D-01); each is tracked to a follow-up plan and the file/line is the FINAL signature, not a placeholder shape:
- `src-tauri/src/commands.rs` `get_state` — returns a fail-closed placeholder StateDto (config_verified/state_verified=false, maximal_lockout=true, tokens=0, weekly_spent=3). Real read/verify/derive path lands in plan 03 (T-04-03).
- `src-tauri/src/commands.rs` `classify_change` — returns an empty allowed-noop ClassifyDto. Wraps `classify::classify_change` + `quota::decide` in plan 04.
- `src-tauri/src/commands.rs` `commit_change` / `use_grace` — return `IpcError::NotInitialized`. Wrap `commit::commit_change` / `grace::use_grace` in plan 05.
- `src-tauri/src/main.ts` — logs the StateDto only; the Status view render lands in plan 03.
- `IpcError::VerifyFailed` and `AppCtx.paths` are part of the fixed contract, currently unused (compiler dead-code warnings expected) until plans 03/05 consume them.

## Threat Flags
None — no security surface beyond the plan's threat_model was introduced. The placeholder DTO (T-04-03) and broad fs:scope (T-04-04) are already registered/accepted in the plan with plan-03 follow-ups.

## Next Phase Readiness
- The IPC contract is fixed: downstream plans fill command bodies and the UI against `StateDto`/`ClassifyDto` without re-deriving signatures (D-01 satisfied).
- Open follow-ups carried into later plans: tighten `fs:scope` to the resolved data dir (plan 03), replace the placeholder `get_state` read path (plan 03), wire `classify_change` (plan 04) and `commit_change`/`use_grace` (plan 05), and write the net-new `lock_status` evaluator (plan 02).

## Self-Check: PASSED

All 13 created files present on disk; both task commits (`9154769`, `e68c1ca`) present in git history.

---
*Phase: 04-ui-moonlit-indigo*
*Completed: 2026-06-09*
