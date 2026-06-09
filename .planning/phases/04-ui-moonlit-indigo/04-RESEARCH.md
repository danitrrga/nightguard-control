# Phase 4: UI (Moonlit Indigo) - Research

**Researched:** 2026-06-09
**Domain:** Tauri v2 desktop app (vanilla-TS + Vite) wrapping existing Rust crates as IPC; minimalist hand-CSS UI
**Confidence:** HIGH (stack locked + verified; one MEDIUM open question on lock-window evaluation — see Open Questions)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Full vertical slice — scaffold the Tauri v2 **vanilla-TS + Vite** app, add `src-tauri/`, wrap the existing crate functions as exactly four IPC commands: `get_state`, `classify_change`, `commit_change`, `use_grace`. IPC is thin glue over already-built `trust-kernel` / `mutation-engine`. ~3–4 plans (scaffold+IPC contract → status view → edit panel → actions/wiring).
- **D-02:** Rust backend is the **sole writer/signer**. Frontend only `invoke()`s; never touches files or HMAC directly.
- **D-03:** `get_state` reads the **same signed `config.yaml` + `guard.json`** the guard reads, **re-verifies the HMAC via the Rust kernel** (`verify_bytes` / `compute_state_hmac` / `canonicalize_bytes`), derives lock/countdown/token/grace from verified state. **No shelling out to the guard** (would trigger reverts/audit/SNTP side-effects). On verify-fail or maximal-lockout, display as-is — never app-local optimism.
- **D-04:** Clock-tamper/offline detection is the **guard's** authority. App-side time is **advisory only**; when true time can't be confirmed, show a quiet "time unverified" caveat rather than asserting a countdown as truth.
- **D-05:** **Watch the data dir** (`config.yaml` + `guard.json`) via Tauri fs-watch — any change triggers immediate re-read + re-verify. A **1-second client tick** animates the countdown between changes. Fallback to short poll only if the watcher proves unreliable.
- **D-06:** The **countdown is the hero element**, targeting the next state-change boundary: LOCKED → curfew-window end; grace active → grace-window end; OPEN → next lock time. Token meter is the **3-dot weekly** indicator with next-reset + today's grace availability (UI-02).
- **D-07:** `classify_change` runs **live, debounced, per field**. Tighten → quiet accent; loosen → warning + token cost. Loosening at **0 tokens disables commit with an inline reason** (UI-04).
- **D-08:** **One confirm step on loosening commits** (spends a token); tightening commits freely.
- **D-09:** After **any** `commit_change` or `use_grace`, **re-read the freshly-signed state** so display equals enforced truth (no optimistic local mutation).
- **D-10:** The **"+8 minutes" button** is enabled **only during an active lock when grace is available**, grants the window via `use_grace` (UI-03), then re-fetches (D-09).
- **D-11:** **Minimalist, typographic, whitespace-led.** Very **few containers — no card soup.** The CLAUDE.md "flat-card layout" hint is **superseded** by this direction. Countdown dominates; everything else recedes.
- **D-12:** Keep the **Moonlit Indigo palette + Roboto** (locked). Left-icon-rail retained but **sparse** (status + edit). Visual contract is in 04-UI-SPEC.md.

### Claude's Discretion
- Exact IPC payload shapes for `get_state` (the state DTO: lock bool, boundary timestamps, weekly_spent/remaining, grace availability, fail_closed/verify status) — designed in planning against existing engine return types + guard.json schema. **(A proposed shape is provided below in Architecture Patterns — still Claude's discretion to refine.)**
- File-watch debounce window, countdown formatting, component decomposition.

### Deferred Ideas (OUT OF SCOPE)
- Usage analytics / screen-time tracking / app-blocking — that's StayFree's domain, not this product.
- General-purpose settings editor — out (curfew config only).
- Phase 5 (Instance Wiring) — pointing the author's live LifeOS hook at the canonical config is its own phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Main screen shows lock status (🌙 LOCKED / OPEN) + live countdown reflecting hook-enforced reality (never app-local optimism). | `get_state` DTO carries verified lock state + boundary timestamps; countdown is client-ticked off a server-supplied boundary. **Lock-window evaluation is net-new code** (no engine fn exists — Open Q1). |
| UI-02 | 3-dot weekly token meter with next-reset + today's grace availability. | `quota::decide` yields `effective_spent` + `next_reset`; `guard.json.grace.date` vs today's true-day gives grace availability. DTO surfaces `tokens_remaining`, `next_reset`, `grace_available_today`. |
| UI-03 | "+8 minutes" button enabled only during active lock + grace available; grants on press. | `grace::use_grace(paths, &dyn TrueTime, tz, key)` → `GraceWindow`; wrapped as `use_grace` command. Enable gate = `lock_active && grace_available_today` from DTO. |
| UI-04 | Edit panel: per-field inputs, live tighten/loosen feedback, disables commit w/ reason at 0 tokens loosen. | `classify::classify_change(old, new)` → `Vec<(String, Direction)>`; `quota::decide` → `allowed`/`reason`/`costs_token`. Wrapped as `classify_change` command (debounced). |
| UI-05 | Moonlit Indigo palette + Roboto + left-icon-rail layout. | Fully specified in 04-UI-SPEC.md (palette tokens, type scale, spacing, copy). Hand CSS, no UI framework. |
</phase_requirements>

## Summary

Phase 4 is a full vertical slice with a **deliberately thin IPC seam**: four `#[tauri::command]` functions wrap already-built, already-tested `trust-kernel` + `mutation-engine` code, and a single-screen vanilla-TS UI renders on top. The locked stack (Tauri 2.11.2, `@tauri-apps/cli`/`api` ^2.11, hand CSS) is verified current as of this research; all five new packages (`tauri`, `tauri-build`, `tauri-plugin-fs` crates + `@tauri-apps/api`/`cli`/`plugin-fs` npm) pass slopcheck clean.

The two non-trivial unknowns resolve as follows. **(1) Workspace wiring:** `src-tauri/` becomes a **third workspace member**; its `Cargo.toml` declares `path` deps on `../trust-kernel` and `../mutation-engine` and a `[lib]` with `crate-type = ["staticlib","cdylib","rlib"]` + a thin `main.rs` calling `lib.rs::run()` (the standard v2 layout). `tauri dev` watches dependent workspace crates and rebuilds on change. **(2) Liveness:** the `@tauri-apps/plugin-fs` `watch`/`watchImmediate` API (debounced, `watch` feature flag + `fs:allow-watch` capability) monitors the data dir; a 1-second client `setInterval` ticks the countdown between file events.

The **one genuine gap** the planner must budget for: **there is no curfew-window / lock-status evaluation function anywhere in the engine** (verified by grep — only a private `parse_window` in the classifier). Computing "are we locked right now?" and "when is the next boundary?" from `config.yaml`'s `curfew.start/end` + `curfew.schedule.<day>` is **net-new Rust code that must agree byte-for-semantics with the guard's curfew interpretation**, against advisory app-side time (D-04). This is the highest-risk task in the phase and is called out in Open Questions + Pitfalls.

**Primary recommendation:** Scaffold `src-tauri/` as a third workspace member via `npm create tauri-app@latest` (vanilla-TS) then re-home it, wire the two crates as path deps, expose the four commands returning serde DTOs with a `Serialize`-able error enum, drive liveness with `plugin-fs` `watch` + a 1 s tick, and write a single shared `lock_status(config, now_advisory)` evaluator (mirroring the guard's window logic) — keep everything else thin.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HMAC sign/verify, DPAPI, atomic write | Rust host (`trust-kernel`) | — | Sole writer/signer (D-02); key never crosses the JS boundary. |
| Classify / quota-decide / commit / grace | Rust host (`mutation-engine`) | — | Authoritative edit-intent logic already built; UI only submits intent. |
| Read + re-verify signed artifacts (`get_state`) | Rust host (new IPC) | — | D-03: re-verification must use the same kernel the guard trusts; no JS-side crypto. |
| Lock-status + next-boundary evaluation | Rust host (NEW shared fn) | — | Must agree with the guard's curfew semantics; do once in Rust, not in TS (Open Q1). |
| File-change liveness (data dir watch) | Webview (`plugin-fs watch`) | Rust host (notify, fallback) | Plugin-fs exposes watch to the frontend directly; debounced events trigger re-`invoke('get_state')`. |
| Countdown tick (1 s animation) | Webview (`setInterval`) | — | Pure presentation between server-truth refreshes; never invents a state transition (D-05). |
| Per-field live feedback (debounced classify) | Webview (debounce) → Rust (`classify_change`) | — | Debounce is UI concern; classification is authoritative Rust. |
| Status word / token meter / countdown render | Webview (hand CSS/DOM) | — | UI-05 / UI-SPEC; no framework. |
| Curfew **enforcement** | (out of scope — PowerShell guard) | — | The app is a reader; the guard enforces. Never duplicate enforcement here. |

## Standard Stack

> All versions are LOCKED in CLAUDE.md and re-verified against the registries on 2026-06-09. Do not substitute.

### Core (new this phase)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@tauri-apps/cli` | `2.11.2` `[VERIFIED: npm registry]` `[CITED: CLAUDE.md]` | `tauri dev` / `tauri build` | Major-matched to the locked `tauri 2.11.2` crate. |
| `@tauri-apps/api` | `2.11.0` `[VERIFIED: npm registry]` `[CITED: CLAUDE.md]` | `invoke()` IPC + event listeners on the frontend | The v2 JS API; import `invoke` from `@tauri-apps/api/core`. |
| `tauri` (crate) | `2.11.2` `[CITED: CLAUDE.md]` `[VERIFIED: crates.io]` | Desktop shell; Rust backend holds signing key off the JS surface | Current stable v2; the only supported major. |
| `tauri-build` (crate) | `2.x` (matched to `tauri`) `[VERIFIED: crates.io]` | `build.rs` codegen for the v2 app | Standard v2 build dep. |
| `vite` | `^7` (whatever `create-tauri-app` scaffolds) `[CITED: CLAUDE.md]` | Frontend bundler/dev server | Tauri's recommended frontend tooling for the vanilla-ts template. |
| `typescript` | `^5` `[CITED: CLAUDE.md]` | Frontend language | Type safety over the `invoke()` boundary. |

### Supporting (liveness — D-05)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tauri-plugin-fs` (crate) | `2.5.1` `[VERIFIED: crates.io]` | Host-side fs plugin registration; enable `features = ["watch"]` | Register in `lib.rs` `Builder`. Required for `watch`/`watchImmediate`. |
| `@tauri-apps/plugin-fs` (npm) | `2.5.1` `[VERIFIED: npm registry]` | Frontend `watch` / `watchImmediate` of the data dir | Subscribe to data-dir changes → re-`invoke('get_state')`. |

### Already in the workspace (reused, no new install)
| Crate | Purpose for Phase 4 |
|-------|---------------------|
| `trust-kernel` (path dep) | `canonicalize_bytes`, `hmac::{verify_bytes, sign_bytes, tag_to_hex}`, `key::load_or_create_key`, `dpapi_*` — the `get_state` re-verify path + key load. |
| `mutation-engine` (path dep) | `classify::classify_change`, `quota::decide`, `commit::{commit_change, CommitPaths}`, `grace::use_grace`, `ntp::{SntpTrueTime, TrueTime}`, `week::*`, `state::{GuardState, GraceWindow, MutationError}`. |
| `serde` / `serde_json` | DTO (de)serialization across IPC + reading `guard.json`. Already transitive via the engine; declare explicitly in `src-tauri/Cargo.toml`. |
| `chrono` / `chrono-tz` | Advisory local-time + tz math for the countdown boundary (already engine deps). |
| `thiserror` | The IPC error enum (engine already uses it; pattern is established). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `plugin-fs watch` (frontend) | `notify` crate in the host emitting Tauri events | More control + no plugin/capability surface, but more host code and you re-implement debounce. **Use plugin-fs first** (D-05); fall back to host `notify` only if the plugin watcher proves unreliable on the target host (D-05 explicitly allows a poll fallback). |
| `SntpTrueTime` for the countdown | System clock, advisory | D-04 says app-side time is advisory only — you may show the system clock with a "time unverified" caveat. **Do not** make a blocking SNTP call on every `get_state` refresh; that would stall the 1 s tick and duplicate the guard's authority. SNTP at most lazily/optionally to label the caveat. |

**Installation:**
```bash
# 0. Prereqs already satisfied by Phases 1–3: MSVC Rust toolchain, MS C++ Build Tools, WebView2 (Win11).
# 1. Scaffold a throwaway vanilla-TS Tauri app, then re-home src-tauri/ + frontend into this repo.
npm create tauri-app@latest        # → TypeScript → Vanilla → TypeScript
#    (or: npm install -D @tauri-apps/cli@latest  &&  npx tauri init  against an existing Vite frontend)
# 2. Frontend deps (repo root or frontend dir, wherever package.json lands)
npm install @tauri-apps/api@2.11 @tauri-apps/plugin-fs@2.5
npm install -D @tauri-apps/cli@2.11
# 3. Backend deps — add to src-tauri/Cargo.toml (see workspace wiring snippet below)
#    tauri = { version = "2.11.2", features = [] }
#    tauri-plugin-fs = { version = "2.5.1", features = ["watch"] }
#    trust-kernel = { path = "../trust-kernel" }
#    mutation-engine = { path = "../mutation-engine" }
#    serde / serde_json / thiserror / chrono / chrono-tz
# 4. Run / build
npx tauri dev
npx tauri build       # → standalone .exe (+ NSIS/MSI per bundle.targets); unsigned OK for personal use
```

## Package Legitimacy Audit

> slopcheck 0.6.1 available and run on all five new packages (2026-06-09). All clean.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `@tauri-apps/api` | npm | mature (v2 line) | very high | github.com/tauri-apps/tauri | OK | Approved |
| `@tauri-apps/cli` | npm | mature | very high | github.com/tauri-apps/tauri | OK | Approved |
| `@tauri-apps/plugin-fs` | npm | mature (plugins v2) | high | github.com/tauri-apps/plugins-workspace | OK | Approved |
| `tauri` | crates.io | mature | very high | github.com/tauri-apps/tauri | OK | Approved |
| `tauri-build` | crates.io | mature | very high | github.com/tauri-apps/tauri | OK | Approved |
| `tauri-plugin-fs` | crates.io | mature | high | github.com/tauri-apps/plugins-workspace | OK | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*All packages are the official Tauri org packages discovered via official docs + CLAUDE.md (authoritative), version-confirmed on the correct ecosystem registry, and slopcheck-clean → `[VERIFIED]`.*

## Architecture Patterns

### System Architecture Diagram

```
                          DATA DIR (NIGHTGUARD_DIR — same dir the guard reads, D-03)
                          ├── config.yaml          (live, signed)
                          ├── config.sanctioned.yaml
                          ├── guard.json           (signed state: config_hmac/state_hmac/weekly_spent/week_anchor/ledger/grace)
                          ├── .guardkey            (DPAPI raw blob)
                          └── .nightguard.lock     (fd-lock single-writer sentinel)
                                   │  ▲
                fs change events   │  │  atomic ordered writes (sanctioned→guard.json→live)
                                   │  │  by commit_change / use_grace ONLY (D-02 sole writer)
                                   ▼  │
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │  RUST HOST (src-tauri)  — sole writer/signer, holds the 32-byte key in memory │
   │                                                                               │
   │   load_or_create_key(.guardkey)  ── key:[u8;32]  (managed Tauri State)        │
   │                                                                               │
   │   #[tauri::command] get_state ──► read config.yaml+guard.json                 │
   │        │                          ├─ verify_bytes(key, canon(config), tag)    │
   │        │                          ├─ guardstate.compute_state_hmac == stored? │
   │        │                          ├─ quota::decide → effective_spent/next_reset│
   │        │                          ├─ lock_status(config, advisory_now) [NEW]  │
   │        │                          └─ grace_available_today?                   │
   │        ▼ StateDto (serde)                                                     │
   │   #[tauri::command] classify_change(old,new) ──► classify::classify_change +  │
   │        ▼ ClassifyDto                              quota::decide (preview)      │
   │   #[tauri::command] commit_change(new_yaml) ──► classify → decide → gate →    │
   │        ▼ StateDto (re-read)                       commit::commit_change        │
   │   #[tauri::command] use_grace() ──► grace::use_grace(SntpTrueTime)            │
   │        ▼ StateDto (re-read)                                                    │
   └───────────────────────────────────────────────────────────────────────────────┘
                                   │  invoke<T>()  /  events
                                   ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │  WEBVIEW (vanilla TS + Vite)  — pure reader/intent-submitter (D-02)           │
   │                                                                               │
   │   on load → invoke('get_state') → render Status view                         │
   │   plugin-fs watch(dataDir) ──► (debounced) re-invoke('get_state') (D-05)      │
   │   setInterval(1s) ──► re-render countdown digits from last StateDto boundary  │
   │   edit field (debounced) → invoke('classify_change') → tighten/loosen badge   │
   │   Commit (loosen → confirm) → invoke('commit_change') → re-render (D-09)      │
   │   +8 button (enabled iff lock_active && grace_available) → invoke('use_grace')│
   └───────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
nightguard-control/
├── Cargo.toml                 # workspace root — add "src-tauri" as 3rd member
├── crates/
│   ├── trust-kernel/          # (existing)
│   └── mutation-engine/       # (existing)
├── src-tauri/                 # NEW — Tauri host crate (3rd workspace member)
│   ├── Cargo.toml             # path deps on ../crates/trust-kernel + ../crates/mutation-engine
│   ├── build.rs               # tauri-build
│   ├── tauri.conf.json        # window, bundle.targets, frontendDist, devUrl
│   ├── capabilities/
│   │   └── default.json       # core + fs:allow-watch + fs:scope for the data dir
│   └── src/
│       ├── main.rs            # thin: app_lib::run()
│       ├── lib.rs             # run(): Builder, .manage(key), invoke_handler![4 cmds]
│       ├── commands.rs        # the 4 #[tauri::command] fns + DTOs + IpcError
│       └── lock_status.rs     # NEW shared curfew-window evaluator (Open Q1)
├── src/                       # NEW — frontend (vanilla TS)
│   ├── index.html
│   ├── main.ts                # invoke wiring, watch, 1s tick, render
│   └── styles.css             # Moonlit Indigo tokens (UI-SPEC)
├── package.json               # NEW
└── vite.config.ts             # NEW
```
> **NOTE on crate path:** the existing crates live under `crates/`. `src-tauri/Cargo.toml` path deps are therefore `path = "../crates/trust-kernel"` and `path = "../crates/mutation-engine"` (one level up from `src-tauri/`, then into `crates/`). Confirm the relative path at scaffold time.

### Pattern 1: Workspace wiring (src-tauri as 3rd member)
**What:** Make `src-tauri/` a member of the existing workspace so `tauri dev` rebuilds when the two library crates change, and the host can `path`-depend on them.
**When to use:** This phase, once.
```toml
# Cargo.toml (workspace root) — edit the existing file
[workspace]
resolver = "2"
members = ["crates/trust-kernel", "crates/mutation-engine", "src-tauri"]
```
```toml
# src-tauri/Cargo.toml (scaffolded, then edited)
[package]
name = "nightguard-control"
version = "0.1.0"
edition = "2021"

# v2 desktop+mobile-parity layout: thin main.rs + run() in lib.rs.
# The _lib suffix keeps the lib name distinct from the bin.  [VERIFIED: crates.io tauri 2.11.2 scaffold; CITED: tauri-apps discussion #11450]
[lib]
name = "nightguard_control_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2.11.2", features = [] }
tauri-plugin-fs = { version = "2.5.1", features = ["watch"] }
trust-kernel    = { path = "../crates/trust-kernel" }
mutation-engine = { path = "../crates/mutation-engine" }
serde      = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror  = "1"
chrono     = "0.4"
chrono-tz  = "0.10"
```
**Anti-pattern guard:** do NOT nest a second `[workspace]` table inside `src-tauri/Cargo.toml` — that creates a workspace-within-workspace conflict. The root `[workspace]` owns all three members. `[VERIFIED: codebase — root Cargo.toml is the only workspace table]`

### Pattern 2: The four IPC commands (thin wrappers + serde DTOs)
**What:** Each command is a few lines over an existing engine function, returning a `Serialize` DTO or a `Serialize` error.
**When to use:** The IPC contract plan (plan 1).
```rust
// src-tauri/src/commands.rs
// Source: [CITED: v2.tauri.app/develop/calling-rust] command/Result<_,SerializableError> pattern
use serde::Serialize;
use mutation_engine::{classify, quota, commit, grace, state::{GuardState}};

/// IPC error: thiserror message + Serialize so the JS catch() receives a string. [ASSUMED shape]
#[derive(Debug, thiserror::Error)]
pub enum IpcError {
    #[error("{0}")] Engine(String),
    #[error("verify failed")] VerifyFailed,
    #[error("not initialized")] NotInitialized,
}
impl serde::Serialize for IpcError {
    fn serialize<S: serde::Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        s.serialize_str(&self.to_string())   // surface the message to JS
    }
}
impl From<mutation_engine::MutationError> for IpcError {
    fn from(e: mutation_engine::MutationError) -> Self { IpcError::Engine(e.to_string()) }
}

#[tauri::command]
fn classify_change(old_yaml: String, new_yaml: String) -> Result<ClassifyDto, IpcError> { /* classify + decide preview */ }

#[tauri::command]
fn get_state(state: tauri::State<'_, AppCtx>) -> Result<StateDto, IpcError> { /* read+verify+derive */ }

#[tauri::command]
fn commit_change(new_yaml: String, state: tauri::State<'_, AppCtx>) -> Result<StateDto, IpcError> { /* gate → commit → re-read (D-09) */ }

#[tauri::command]
fn use_grace(state: tauri::State<'_, AppCtx>) -> Result<StateDto, IpcError> { /* grace::use_grace → re-read (D-09) */ }
```
```rust
// src-tauri/src/lib.rs
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let ctx = AppCtx::load();   // resolves data dir, load_or_create_key, builds CommitPaths
    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .manage(ctx)
        .invoke_handler(tauri::generate_handler![get_state, classify_change, commit_change, use_grace])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```
```typescript
// src/main.ts  — Source: [CITED: v2.tauri.app/develop/calling-rust]
import { invoke } from '@tauri-apps/api/core';     // NOTE: /core, NOT v1's /tauri
const s = await invoke<StateDto>('get_state');
```

### Pattern 3: Proposed `get_state` DTO (Claude's discretion — refine in planning)
**What:** A flat, serde-friendly state object derived from the verified `GuardState` + `config.yaml` + advisory time. Timestamps as **unix seconds** (the engine/guard already speak unix seconds — `GraceWindow.window_end`, `LedgerEntry.ntp_timestamp`), so the TS side does its own formatting.
```rust
// [ASSUMED shape — Claude's discretion per CONTEXT; aligns with guard.json + guard verdict fields]
#[derive(Serialize)]
pub struct StateDto {
    // ── verification / fail-closed (D-03) ──
    pub config_verified: bool,     // verify_bytes(key, canon(config.yaml), config_hmac)
    pub state_verified: bool,      // recomputed state_hmac == stored (A3 recipe)
    pub maximal_lockout: bool,     // config is the hardcoded 24/7 lockout literal (or verify failed)
    // ── lock status + countdown (UI-01 / D-06) ──  [from NEW lock_status.rs — Open Q1]
    pub locked: bool,
    pub grace_active: bool,
    pub boundary_unix: i64,        // next state-change boundary the countdown targets
    pub boundary_kind: String,     // "curfew_end" | "grace_end" | "next_lock"
    pub time_unverified: bool,     // D-04 advisory caveat (true when no SNTP confirmation)
    // ── token meter (UI-02) ──  [from quota::decide]
    pub tokens_remaining: u8,      // 3 - effective_spent
    pub weekly_spent: u8,          // effective_spent (post lazy-reset)
    pub next_reset_unix: i64,      // quota::decide().next_reset
    // ── grace availability (UI-02 / UI-03 / D-10) ──
    pub grace_available_today: bool,  // guard.json.grace.date != true/advisory today
    pub grace_remaining_secs: i64,    // if grace_active: window_end - now, else 0
}
```
> **Worst-casing parity (Phase 3 D-03/D-04):** when `state_verified == false`, the DTO MUST present `weekly_spent = 3`, `tokens_remaining = 0`, `grace_available_today = false` — the SAME worst-case substitution the guard makes (guard.ps1 lines 217–222). The app must never look *less* locked than the guard. `[CITED: nightguard_guard.ps1]`

### Pattern 4: Liveness — fs-watch + 1 s tick (D-05)
**What:** Watch the data dir; debounced file events re-fetch verified state; a 1 s interval re-renders only the countdown digits.
```typescript
// Source: [CITED: v2.tauri.app/plugin/file-system] watch()
import { watch } from '@tauri-apps/plugin-fs';
let last: StateDto;
await watch(dataDir, () => { refresh(); }, { delayMs: 250, recursive: false }); // debounced
async function refresh() { last = await invoke<StateDto>('get_state'); render(last); }
setInterval(() => { if (last) renderCountdownOnly(last); }, 1000); // tick never invents transitions (D-05)
```
```json
// src-tauri/capabilities/default.json — Source: [CITED: v2.tauri.app/plugin/file-system]
{
  "identifier": "default",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "fs:allow-watch",
    "fs:allow-unwatch",
    { "identifier": "fs:scope", "allow": [{ "path": "**" }] }
  ]
}
```
> Scope the `fs:scope` `path` to the resolved data dir, not `**`, once the dir is known (least privilege). The frontend needs the absolute data-dir path — surface it from a tiny command or a Tauri config, since the watch target is outside the app's default scoped dirs. `[ASSUMED — confirm scope mechanics at integration]`

### Anti-Patterns to Avoid
- **JS-side crypto or file writes.** All HMAC/DPAPI/writes stay in Rust (D-02). The frontend only `invoke()`s.
- **Importing `@tauri-apps/api/tauri`** (v1 path) — v2 is `@tauri-apps/api/core`.
- **Shelling out to `nightguard_guard.ps1` for state** (D-03) — it has revert/audit/SNTP side-effects every run. Read the files + re-verify in-process instead.
- **A second `[workspace]` in `src-tauri/Cargo.toml`** — root owns all members.
- **Blocking SNTP on the `get_state` hot path** — app time is advisory (D-04); a blocking network call would stall the 1 s tick.
- **Optimistic local mutation after commit/grace** — always re-read (D-09).
- **Inventing the app's own atomic write** for commits — call `commit::commit_change` (RULE-06 ordered, fd-locked); a bespoke writer reopens the sign-vs-write race the guard's circuit-breaker is calibrated for.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HMAC sign/verify | Custom HMAC over the config | `trust_kernel::hmac::{sign_bytes, verify_bytes}` + `canonicalize_bytes` | Byte-parity with the guard is the whole product; the canonical-bytes invariant is already proven (Phases 1–3). |
| DPAPI key load | New key handling | `trust_kernel::key::load_or_create_key` | CurrentUser scope + 32-not-64 canary already enforced; the guard reads the same blob. |
| Atomic ordered commit | App-specific write | `mutation_engine::commit::commit_change` | RULE-06 ordering (sanctioned→guard.json→live) + fd-lock + circuit-breaker parity; any other order reverts a legit write. |
| Token quota / week reset | Re-derive Monday math | `mutation_engine::quota::decide` + `week::*` | DST-aware reset + lazy-reset persistence (CR-01) already correct. |
| Grace grant | Timestamp logic | `mutation_engine::grace::use_grace` | once-per-true-day + NTP fail-closed already correct. |
| Direction classify | Re-diff fields in TS | `mutation_engine::classify::classify_change` | The full field table + defensive-Noop semantics live in Rust; the UI must show the SAME verdict it will commit. |
| File watching/debounce | Manual polling loop | `@tauri-apps/plugin-fs` `watch` | Native, debounced, cross-target; poll only as the D-05 fallback. |

**Key insight:** This phase's entire value is being a *faithful mirror* of what the guard enforces. Every re-implementation in TS/Rust that diverges from the existing crates is a place where the display can lie. Wrap, don't reinvent — **except** the one thing no crate provides: lock-window evaluation (below).

## Runtime State Inventory

> Greenfield app shell over existing state; this is not a rename/refactor. Included briefly because the app *consumes* existing runtime state it must not corrupt.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `config.yaml`, `config.sanctioned.yaml`, `guard.json`, `.guardkey`, `.nightguard.lock` in the single `NIGHTGUARD_DIR` (Phase 3 D-09). | App READS all; WRITES only via `commit_change`/`use_grace` (which already write atomically). Never write directly. |
| Live service config | The PowerShell guard reads the same dir on every Claude-Code SessionStart/UserPromptSubmit. | App must use the engine's fd-lock'd ordered commit so a guard fire mid-write doesn't revert (GARD-05). No new action — using `commit_change` is sufficient. |
| OS-registered state | None for the app itself. (WebView2 is system runtime, assumed present on Win11.) | None — verified by stack (CLAUDE.md: WebView2 evergreen preinstalled). |
| Secrets/env vars | `NIGHTGUARD_DIR` env var selects the data dir (guard reads `$env:NIGHTGUARD_DIR` / `-DataDir`). DPAPI key in `.guardkey`. | App must resolve the SAME data dir the guard uses (single base-dir, Phase 3 D-09). Data-dir resolution is an explicit task. |
| Build artifacts | None yet (no `package.json`/`tauri.conf.json` exist). Scaffolding creates them fresh. | New files; ensure `src-tauri/target` / `node_modules` are gitignored. |

**Data-dir resolution (load-bearing):** the app MUST resolve the identical directory the guard resolves — `NIGHTGUARD_DIR` (with the guard's `-DataDir` override semantics). Mis-resolving the dir means the UI mirrors a different (or empty) state than the guard enforces. `[CITED: nightguard_guard.ps1 lines 42–56; 03-CONTEXT D-09]`

## Common Pitfalls

### Pitfall 1: No engine function computes "are we locked right now?"
**What goes wrong:** The planner assumes `get_state` can read lock status off an existing function; it can't. Grep confirms only a private `parse_window` in the classifier and no curfew evaluator anywhere.
**Why it happens:** The engine is edit-intent logic; the *guard* (PowerShell) computes the live curfew verdict, and the app is forbidden from calling it (D-03).
**How to avoid:** Write a small **new** `lock_status(config_yaml, now) -> { locked, grace_active, boundary }` in `src-tauri` (or, better, a pure fn in `mutation-engine` so it's unit-testable alongside the classifier). It must interpret `curfew.enabled`, `curfew.start/end`, and `curfew.schedule.<day>` (`off` | `HH:MM-HH:MM`, possibly overnight-wrapping windows) **exactly** as the guard would, against advisory local time in `config.timezone`. Budget this as its own task with a diff-table unit test mirroring the classifier's test style.
**Warning signs:** UI lock state disagrees with the guard's verdict on the same files; overnight windows (`23:00-07:00`) handled wrong; `schedule.<day>` ignored.

### Pitfall 2: App looks less-locked than the guard after state tamper
**What goes wrong:** `get_state` trusts a tampered `guard.json` and shows tokens/grace the guard would refuse.
**Why it happens:** Forgetting the guard's worst-case substitution (state_hmac mismatch → `weekly_spent=3`, grace-as-used).
**How to avoid:** Re-verify `state_hmac` with `GuardState::compute_state_hmac`; on mismatch surface `weekly_spent=3 / tokens_remaining=0 / grace_available_today=false / maximal_lockout`-style worst case in the DTO (UI-SPEC "State unverified" copy). Never show optimism the guard wouldn't honor. `[CITED: nightguard_guard.ps1 217–222]`
**Warning signs:** Token meter shows remaining tokens while the guard treats you as exhausted.

### Pitfall 3: v1/v2 API drift in scaffold
**What goes wrong:** Copied snippets import `@tauri-apps/api/tauri`, use v1 allowlist, or omit the `[lib]` crate-type → build/runtime failures.
**How to avoid:** Import `invoke` from `@tauri-apps/api/core`; use v2 `capabilities/` permissions (not v1 `allowlist`); keep the `[lib] crate-type = ["staticlib","cdylib","rlib"]` + thin `main.rs` v2 layout. `[CITED: tauri-apps discussion #11450; v2 calling-rust docs]`
**Warning signs:** "invoke is not a function", Android/mobile `[lib]` not detected, allowlist errors.

### Pitfall 4: DPAPI scope must stay CurrentUser on the app side too
**What goes wrong:** The app loads/creates the key under a different DPAPI scope than the guard → `Unprotect` fails or the security property weakens.
**How to avoid:** The app reuses `trust_kernel::dpapi` (already `Scope::User`, `None` entropy). Do not add a second key path. Same `.guardkey`, same scope, same (absent) entropy as the guard. `[CITED: dpapi.rs; CLAUDE.md interop invariants]`
**Warning signs:** key load fails in-app but the guard reads it fine, or vice-versa.

### Pitfall 5: fs-watch scope / data dir outside default scope
**What goes wrong:** `watch(dataDir, …)` silently no-ops because the data dir isn't in the plugin's allowed `fs:scope`, or the frontend doesn't know the absolute path.
**How to avoid:** Add an `fs:scope` allow entry for the resolved data dir in `capabilities/`, and surface the absolute data-dir path to the frontend (small command or config). Confirm the watcher actually fires on the target host; if not, use the D-05 poll fallback (e.g. re-`invoke('get_state')` every N seconds).
**Warning signs:** edits/reverts don't refresh the UI until a manual reload.

### Pitfall 6: Tabular-nums jitter on the countdown
**What goes wrong:** The 64px countdown digits shift width each second, making the hero element twitch.
**How to avoid:** `font-variant-numeric: tabular-nums` on the countdown + any numeric value (already in UI-SPEC). Bundle Roboto woff2 (weights 400/500) locally — don't fetch from a CDN (offline-first, lean-deps). `[CITED: 04-UI-SPEC.md]`

## Code Examples

### Re-verify the signed config in `get_state` (D-03 read path)
```rust
// Source: [CITED: trust-kernel hmac.rs / sign.rs; mutation-engine state.rs]
use trust_kernel::canon::canonicalize_bytes;
use trust_kernel::hmac::{verify_bytes};   // constant-time
// 1. read live config bytes, canonicalize, verify against guard.json.config_hmac
let raw = std::fs::read(&paths.config)?;
let canon = canonicalize_bytes(&raw);
let stored_tag = hex::decode(&guard_state.config_hmac).ok()
    .and_then(|v| <[u8;32]>::try_from(v).ok());
let config_verified = stored_tag.map_or(false, |t| verify_bytes(&key, &canon, &t));
// 2. re-verify state_hmac (A3 recipe — recompute over blanked clone)
let recomputed = guard_state.compute_state_hmac(&key);
let state_verified = recomputed == guard_state.state_hmac;
```

### Gate + commit (D-07/D-08 enforced in Rust, not just UI)
```rust
// Source: [CITED: mutation-engine classify.rs / quota.rs / commit.rs]
let dirs = classify::classify_change(&old_yaml, &new_yaml)?;          // Vec<(String,Direction)>
let decision = quota::decide(&dirs, &current_state, now_utc, &tz);    // QuotaDecision
if !decision.allowed { return Err(IpcError::Engine(decision.reason.unwrap())); } // 0-token loosen blocked
// loosening commit needs true time for the ledger timestamp:
let true_now = SntpTrueTime::default().now().map(|t| t.unix_secs)
    .map_err(|_| IpcError::Engine("ntp unreachable".into()))?;       // fail-closed for the ledger
let new_state = commit::commit_change(&paths, &new_yaml, &dirs, &decision, &key, true_now)?;
// then re-read freshly-signed state (D-09) and return StateDto
```
> The UI also gates (disables the button at 0 tokens, UI-04), but the Rust command re-checks `decision.allowed` so the UI can never force a disallowed commit. Defense in depth mirrors `commit_with_limit`'s own `if !decision.allowed` guard. `[CITED: commit.rs line 148]`

### `use_grace` command (UI-03 / D-10)
```rust
// Source: [CITED: mutation-engine grace.rs]
use mutation_engine::ntp::SntpTrueTime;
let window = grace::use_grace(&paths, &SntpTrueTime::default(), &tz, &key)?; // NtpUnreachable / AlreadyUsedToday → IpcError
// re-read state (D-09) → StateDto with grace_active=true, boundary=window.window_end
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tauri v1 `allowlist` + `@tauri-apps/api/tauri` | v2 `capabilities/` permissions + `@tauri-apps/api/core` | Tauri v2 (stable 2024+) | Scaffold/imports differ; use v2 throughout. |
| `main.rs` holds `fn main()` with the Builder | thin `main.rs` → `lib.rs::run()` (`#[cfg_attr(mobile, mobile_entry_point)]`), `[lib] crate-type=[staticlib,cdylib,rlib]` | Tauri v2 mobile parity | Required layout even for a desktop-only app; `create-tauri-app` already emits it. |
| `tauri-plugin-fs` always-on watch | `watch`/`watchImmediate` gated behind the `watch` feature flag + `fs:allow-watch` capability | plugin-fs v2 | Must enable the feature + permission or watch silently fails. |

**Deprecated/outdated:**
- v1 import paths, allowlist config — replaced by v2 core/permissions.

## Project Constraints (from CLAUDE.md)

- **Lean deps:** no UI framework, no component library, no icon package; hand CSS with Moonlit Indigo tokens, inline SVG icons. (UI-SPEC enforces.)
- **Tauri v2 only:** `tauri 2.11.2`, `@tauri-apps/api`/`cli ^2.11`; `invoke` from `@tauri-apps/api/core`.
- **Rust backend = sole writer/signer.** Frontend never touches files/HMAC. (D-02.)
- **DPAPI:** CurrentUser scope, `None` entropy, raw blob — on the app side too (reuse `trust_kernel::dpapi`).
- **MSVC toolchain** (`x86_64-pc-windows-msvc`), Windows-only. WebView2 assumed present.
- **Atomic writes / fail-closed** — use the engine's ordered `commit_change`; never hand-roll a writer.
- **`==` on HMAC tags forbidden** — use `verify_bytes` (constant-time).
- **Bundling:** `tauri build` → `.exe`; unsigned OK for personal use; defer Authenticode. (CLAUDE.md.)
- **Commit attribution:** NO `Co-Authored-By` trailers (global CLAUDE.md). The research-commit step must omit them.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `get_state` StateDto shape (fields/types) | Pattern 3 | Low — explicitly Claude's discretion; refine in planning. Wrong shape = rework, not a correctness bug. |
| A2 | `IpcError` serialize-as-string pattern | Pattern 2 | Low — standard v2 pattern; alternative is a structured error object. |
| A3 | `fs:scope` for an arbitrary external data dir works via capabilities + surfacing the absolute path | Pattern 4 / Pitfall 5 | Medium — if the plugin can't watch outside scoped base dirs, fall back to host `notify` or polling (D-05 allows poll fallback). |
| A4 | crate path deps are `../crates/trust-kernel` (src-tauri at repo root, crates under `crates/`) | Pattern 1 | Low — verify relative path at scaffold; trivially correctable. |
| A5 | The new `lock_status` evaluator can faithfully mirror the guard's curfew/schedule semantics from `config.yaml` alone | Pitfall 1 / Open Q1 | **Medium-High** — this is net-new logic with no reference impl in Rust; divergence makes the UI lie. Mitigate with a diff-table unit test + cross-check against guard behavior. |
| A6 | WebView2 present on the target Win11 host (no bundling) | Stack | Low — CLAUDE.md states evergreen preinstalled on Win11. |

## Open Questions (RESOLVED)

> RESOLVED at planning (Phase 4 plans): Q1 → Plan 04-02 (dedicated `lock_status` TDD evaluator in `mutation-engine`); Q2 → Plan 04-05 Task 1 (curfew.* visible field set, Claude's Discretion); Q3 → Plan 04-02 (`lock_status` lives in `mutation-engine`, not `src-tauri`).

1. **Lock-window evaluation has no existing implementation.** (HIGHEST RISK)
   - What we know: The engine has the classifier's private `parse_window` only; the *guard* computes the live curfew verdict in PowerShell, but D-03 forbids calling it. So `locked` / `grace_active` / `boundary_unix` must be computed fresh in Rust from `config.yaml` + advisory time.
   - What's unclear: Exact guard semantics for `curfew.schedule.<day>` precedence vs `curfew.start/end`, overnight-wrapping windows (`23:00-07:00`), and how `enabled=false` interacts. The guard's *integrity* half (the script read) doesn't itself evaluate the daily window in a way the app can copy line-for-line — the verdict half checks `grace.window_end > trueNow` and otherwise defaults to `curfew`/deny; the actual "is this minute inside the curfew window" logic for a normal (non-grace) lock is the live hook's job.
   - Recommendation: Make `lock_status` its **own plan task** with: (a) a written spec of window precedence (schedule.<day> overrides start/end? both?), confirmed against the design-spec field table and the live hook's behavior; (b) a pure, unit-tested `mutation-engine` function (diff-table style); (c) explicit overnight-wrap handling. Treat the UI as *advisory* on the exact boundary minute (D-04 caveat) so a small disagreement degrades to "time unverified," not a false unlock.

2. **Exact `config.yaml` field set the edit panel exposes (UI-04).**
   - What we know: The classifier's field table is the authoritative set: `curfew.{enabled,start,end,allow_commands,block_when_offline}`, `curfew.schedule.<day>` ×7, `clock_protection.{enabled,max_offset_minutes}`, `watchdog.{enabled,check_interval_seconds,apps}`, `timezone`.
   - What's unclear: Whether the minimalist UI exposes ALL of these or a curated subset (D-11 "no card soup"). REQUIREMENTS scopes it to "curfew config only," and UI-SPEC implies a lean per-field panel.
   - Recommendation: Planner decides the exposed subset; whatever is exposed, classification/commit still runs the full table (a hidden field simply never changes → Noop). Start with the curfew.* fields as the visible set.

3. **Where `lock_status` lives: `src-tauri` vs `mutation-engine`.**
   - Recommendation: Put it in `mutation-engine` as a pure fn so it gets the same offline unit-test treatment as `classify`/`quota`/`week`, and so a future headless consumer can reuse it. The IPC command just calls it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Rust (MSVC) toolchain | All Rust builds | ✓ (Phases 1–3 built) | stable msvc | — |
| MS C++ Build Tools | Native linking | ✓ (assumed; prior phases linked) | — | — |
| WebView2 runtime | Webview render | ✓ (Win11 evergreen) | system | — |
| Node.js + npm | Vite frontend + tauri CLI | ✓ (npm verified this session) | npm present | — |
| `@tauri-apps/cli` | dev/build | ✗ (not yet installed) | 2.11.2 (target) | install step (Installation §) |
| `tauri-plugin-fs` (`watch`) | D-05 liveness | ✗ (not yet added) | 2.5.1 (target) | host `notify` or poll fallback (D-05) |
| Authenticode cert | Signed bundle | ✗ (not needed) | — | unsigned `.exe` (CLAUDE.md: OK for personal) |

**Missing dependencies with no fallback:** none (all installable; toolchain present).
**Missing dependencies with fallback:** `tauri-plugin-fs watch` → host `notify`/poll (D-05); code signing → unsigned exe.

## Security Domain

> `security_enforcement` absent from config → treat as enabled. This phase is a **non-authoritative reader**; the security-critical writes/crypto are inherited from Phases 1–3. The new attack surface is the IPC boundary + the webview.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-operator local desktop tool; OS user is the principal (DPAPI CurrentUser binds the key to the user). |
| V3 Session Management | no | No sessions. |
| V4 Access Control | yes (self-binding) | The whole product IS access control against the user's impulsive self. The app must never present a path that bypasses the quota/grace the guard enforces — enforce `decision.allowed` in the Rust command, not just the UI. |
| V5 Input Validation | yes | The edit panel feeds YAML into `classify_change`/`commit_change`. The classifier already treats malformed/absent fields defensively (Noop, never silent loosen); the command must surface parse errors, not swallow them. |
| V6 Cryptography | yes (reuse only) | HMAC/DPAPI come exclusively from `trust-kernel`. **Never** hand-roll crypto or compare tags with `==` (use `verify_bytes`). |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| UI shows optimistic state the guard won't honor (false unlock) | Spoofing/Repudiation | Re-verify both HMACs every `get_state`; worst-case substitution on state mismatch (Pitfall 2); advisory time caveat (D-04). |
| App bypasses quota via a bespoke write | Elevation of Privilege (against the self-bind) | Only write via `commit::commit_change`; re-check `decision.allowed` in-command (defense in depth). |
| Sign-vs-write race with a guard fire | Tampering | Use the engine's fd-lock ordered commit (RULE-06/GARD-05); never write `config.yaml` first. |
| Webview loads remote content / CDN font | Tampering/STRIDE-Info | Bundle Roboto woff2 locally; no remote assets; lean `capabilities` (no shell/http unless needed). |
| Over-broad `fs:scope` capability | Elevation | Scope `fs:scope` to the resolved data dir, not `**` (Pitfall 5 / least privilege). |
| Calling the guard for state (side effects) | Tampering | Forbidden by D-03; read+verify in-process. |

## Sources

### Primary (HIGH confidence)
- **Codebase (read this session):** `crates/trust-kernel/src/{lib,hmac,key,dpapi}.rs`, `crates/mutation-engine/src/{lib,state,commit,classify,quota,grace,week,ntp,sign}.rs`, `scripts/guard/nightguard_guard.ps1`, root `Cargo.toml`, crate `Cargo.toml`s, `.planning/config.json` — authoritative function signatures, DTO shapes, guard verdict schema, worst-casing, workspace layout. **(grep confirmed: no curfew-evaluation fn exists.)**
- **CLAUDE.md** — locked stack table, versions, IPC pattern, interop invariants, bundling.
- **04-CONTEXT.md / 04-UI-SPEC.md / REQUIREMENTS.md / ROADMAP.md / 03-CONTEXT.md** — decisions, UI contract, requirement wording, data-dir resolution.
- **Registry verification (2026-06-09):** `npm view` → `@tauri-apps/cli 2.11.2`, `@tauri-apps/api 2.11.0`, `@tauri-apps/plugin-fs 2.5.1`; `cargo search` → `tauri 2.11.2`, `tauri-plugin-fs 2.5.1`. slopcheck 0.6.1 → all six packages `OK`.
- **v2.tauri.app/develop/calling-rust** — `#[tauri::command]`, `generate_handler`, `Result<_, SerializableError>`, `invoke` from `@tauri-apps/api/core`, async + `State`.
- **v2.tauri.app/plugin/file-system** — `watch`/`watchImmediate`, `watch` feature flag, `fs:allow-watch`/`fs:scope` capabilities.
- **v2.tauri.app/start/create-project** — `npm create tauri-app@latest` vanilla-TS; `npx tauri init` for existing frontends.

### Secondary (MEDIUM confidence)
- **GitHub tauri-apps discussion #11450 + WebSearch (Project Structure / workspace)** — `[lib] crate-type=["staticlib","cdylib","rlib"]`, thin `main.rs` → `lib.rs::run()`, `src-tauri` as a workspace member; `tauri dev` rebuilds dependent workspace crates. (Verified against the established v2 scaffold; treat exact member-path as confirm-at-scaffold.)

### Tertiary (LOW confidence)
- None relied upon for load-bearing claims.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions locked in CLAUDE.md and re-verified on both registries + slopcheck.
- IPC contract: HIGH — official v2 docs + the actual engine signatures read from source.
- Workspace wiring: HIGH — official structure + the existing root `Cargo.toml` read directly; exact member relative-path is confirm-at-scaffold (Low risk).
- Liveness (fs-watch): MEDIUM-HIGH — API confirmed; watching an external data dir via capabilities is the one integration detail to validate (A3 / Pitfall 5; poll fallback exists per D-05).
- Lock-window evaluation: MEDIUM — confirmed there is NO existing impl; the semantics to mirror are the main open question (Open Q1 / A5). This is the planner's highest-attention task.
- Pitfalls: HIGH — derived from the actual guard worst-casing, the locked interop invariants, and v1→v2 drift.

**Research date:** 2026-06-09
**Valid until:** 2026-07-09 (stack is stable/locked; re-verify Tauri patch versions if scaffolding much later)
