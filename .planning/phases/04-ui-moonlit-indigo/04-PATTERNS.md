# Phase 4: UI (Moonlit Indigo) - Pattern Map

**Mapped:** 2026-06-09
**Files analyzed:** 13 new/modified files
**Analogs found:** 7 with a real in-repo analog / 13 total (the 5 frontend + Tauri-config files are net-new with NO in-repo analog — see "No Analog Found")

> **Honest framing (greenfield shell):** Phase 4 is a full vertical slice over two existing, fully-tested Rust library crates. The Rust host (`src-tauri/src/*.rs`) and the `lock_status` evaluator have **strong in-repo analogs** in `crates/trust-kernel` + `crates/mutation-engine` (error enums, serde DTOs, module layout, pure-fn + diff-table test style, the entry-point binary). The **frontend (`src/*`) and all Tauri scaffolding (`tauri.conf.json`, `capabilities/`, `package.json`, `vite.config.ts`) are genuinely net-new — there is no `src/`, no `package.json`, no `#[tauri::command]` anywhere in the repo.** For those, the planner should follow RESEARCH.md (04-RESEARCH.md Patterns 1–4) + the UI-SPEC, not force a codebase analog. This document says so explicitly per file rather than inventing a match.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src-tauri/src/commands.rs` (NEW) | IPC controller (4 `#[tauri::command]` fns + DTOs + `IpcError`) | request-response | `crates/mutation-engine/src/state.rs` (error enum + serde DTOs) + `crates/mutation-engine/src/bin/state_interop_cli.rs` (thin arg→engine glue + exit/error mapping) | role-match (no Tauri command exists yet; error/DTO/glue idioms transfer exactly) |
| `src-tauri/src/lib.rs` (NEW) | app host / wiring (`run()`, Builder, `.manage`, `generate_handler!`) | event-driven (Tauri runtime) | `crates/mutation-engine/src/bin/state_interop_cli.rs` (`main()` dispatch + load_or_create_key + AppCtx resolution) | partial (entry-point + key-load + data-dir glue transfer; the `tauri::Builder` shape itself is net-new → RESEARCH Pattern 2) |
| `src-tauri/src/main.rs` (NEW) | bin entry (thin `app_lib::run()`) | — | (none — 3-line v2 shim) | none → RESEARCH "State of the Art" (thin main.rs) |
| `lock_status.rs` — in `crates/mutation-engine/src/` (NEW; Open Q3 places it here, not src-tauri) | service (pure curfew-window evaluator) | transform (config + advisory now → {locked, grace_active, boundary}) | `crates/mutation-engine/src/classify.rs` (yamlpath field reads, `parse_window`/`parse_hhmm`, pure-no-IO, defensive-absent) + `crates/mutation-engine/src/week.rs` (tz/DST instant math, `parse_tz` defensive default) | role-match (closest existing window/time logic; the "is this minute locked" verdict itself is net-new — Open Q1/Pitfall 1) |
| `crates/mutation-engine/tests/lock_status.rs` (NEW) | test | transform (diff/truth table) | `crates/mutation-engine/tests/quota.rs` (table-style helpers `utc()`, `dirs()`, fixed-`now()`, per-case asserts) | exact (same offline diff-table discipline) |
| `Cargo.toml` (root, MODIFIED) | config (workspace members) | — | existing root `Cargo.toml` (the file itself) | exact (add `"src-tauri"` to `members`) |
| `src-tauri/Cargo.toml` (NEW) | config (crate manifest + path deps + `[lib]`) | — | `crates/mutation-engine/Cargo.toml` (path-dep + dep-pinning style) | role-match (dep style transfers; `[lib] crate-type` + `tauri-build` are net-new → RESEARCH Pattern 1) |
| `src-tauri/build.rs` (NEW) | config (tauri-build codegen) | — | (none) | none → RESEARCH (standard `tauri_build::build()`) |
| `src-tauri/tauri.conf.json` (NEW) | config (window/bundle/dist) | — | (none) | none → RESEARCH §Installation + Structure |
| `src-tauri/capabilities/default.json` (NEW) | config (v2 permissions: fs watch + scope) | — | (none) | none → RESEARCH Pattern 4 |
| `src/main.ts` (NEW) | frontend controller (invoke wiring, watch, 1s tick, render) | request-response + event-driven | (none — no frontend in repo) | none → RESEARCH Patterns 2/4 + UI-SPEC |
| `src/index.html` (NEW) | frontend view (shell DOM) | — | (none) | none → UI-SPEC Layout Contract |
| `src/styles.css` (NEW) | frontend styling (Moonlit Indigo tokens) | — | (none) | none → UI-SPEC (palette/type/spacing) |
| `package.json` / `vite.config.ts` (NEW) | config (frontend toolchain) | — | (none) | none → RESEARCH §Installation |

---

## Pattern Assignments

### `src-tauri/src/commands.rs` (IPC controller, request-response)

**Primary analog:** `crates/mutation-engine/src/state.rs` (error enum + serde DTO idioms)
**Secondary analog:** `crates/mutation-engine/src/bin/state_interop_cli.rs` (thin engine glue + error→exit mapping)

**Error-enum pattern — copy the `thiserror` + prefixed-message + `From<engine error>` shape** (`state.rs:79-118`). This is the established voice (`"mutation io error: {0}"`, fold foreign errors via `From`). The IPC layer adds one thing the engine doesn't: a `Serialize` impl that surfaces `.to_string()` to JS (RESEARCH Pattern 2, A2):
```rust
// crates/mutation-engine/src/state.rs:85-118 — copy this enum+From shape
#[derive(Debug, thiserror::Error)]
pub enum MutationError {
    #[error("mutation io error: {0}")]
    Io(String),
    #[error("ntp unreachable: cannot verify true time")]
    NtpUnreachable,
    #[error("weekly loosen quota exhausted")]
    QuotaExhausted,
    #[error("grace already used today")]
    GraceAlreadyUsedToday,
    #[error("mutation serde error: {0}")]
    Serde(String),
}
impl From<serde_json::Error> for MutationError {
    fn from(e: serde_json::Error) -> Self { MutationError::Serde(e.to_string()) }
}
```
→ For `IpcError`: same `#[derive(Debug, thiserror::Error)]` + per-variant `#[error("…")]`, `From<mutation_engine::MutationError>`, **plus** the `impl serde::Serialize` that does `s.serialize_str(&self.to_string())` (RESEARCH 04-RESEARCH.md lines 266-279).

**Serde-DTO pattern — copy `state.rs`'s `#[derive(...Serialize, Deserialize, Clone)]` struct discipline + doc-commented fields** (`state.rs:25-39, 60-77`). `GuardState`/`GraceWindow`/`LedgerEntry` are the template for `StateDto`/`ClassifyDto`:
```rust
// crates/mutation-engine/src/state.rs:25-39 — DTO field-doc + derive style to mirror
#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
pub struct GuardState {
    /// hex(HMAC(canonical `config.yaml` bytes)).
    pub config_hmac: String,
    pub state_hmac: String,
    pub weekly_spent: u8,
    pub week_anchor: String,
    pub ledger: Vec<LedgerEntry>,
    pub grace: Option<GraceWindow>,
}
```
→ `StateDto` proposed shape is in 04-RESEARCH.md lines 314-336 (Claude's discretion, A1). **Timestamps stay unix-secs `i64`** to match `GraceWindow.window_end` / `LedgerEntry.ntp_timestamp` — TS formats.

**Thin-glue + arg-mapping pattern — copy `state_interop_cli.rs`'s "parse input → call the ONE existing engine fn → map result/error"** (`state_interop_cli.rs:43-64, 133-160`). The CLI's `match cmd { … }` dispatch and its `recomputed == expected` verify branch are the exact shape each `#[tauri::command]` body should have (no new logic, just glue):
```rust
// crates/mutation-engine/src/bin/state_interop_cli.rs:147-159 — re-verify-then-branch glue
let state: GuardState = serde_json::from_str(&json).map_err(...)?;
let recomputed = state.compute_state_hmac(&key);   // <- the SAME call get_state makes
if recomputed.trim().eq_ignore_ascii_case(expected_hex.trim()) { Ok(0) } else { /* mismatch */ }
```

**`get_state` read-and-verify body — the two HMAC checks** (RESEARCH Code Examples lines 437-450; primitives live in `trust-kernel/src/hmac.rs:36-39` `verify_bytes` constant-time, and `mutation-engine/src/state.rs:49-56` `compute_state_hmac`):
```rust
// re-verify config (trust_kernel::hmac::verify_bytes — NEVER `==`, hmac.rs:36)
let canon = canonicalize_bytes(&raw_config_bytes);
let config_verified = verify_bytes(&key, &canon, &stored_config_tag);
// re-verify state (state.rs:49 recipe — recompute over blanked clone)
let state_verified = guard_state.compute_state_hmac(&key) == guard_state.state_hmac;
```

**Worst-casing parity — load-bearing (Pitfall 2).** When `state_verified == false`, the DTO MUST present `weekly_spent = 3 / tokens_remaining = 0 / grace_available_today = false`, mirroring the guard's substitution:
```powershell
# scripts/guard/nightguard_guard.ps1:204-205, 217-222 — the worst-case the DTO must match
$weeklySpent = 3       # default to worst-case until state-verify proves otherwise
$graceUsed   = $true
# ... if (-not $stateValid) { $weeklySpent = 3; $graceUsed = $true }
```
And `grace_available_today` mirrors `$graceUsed = ($null -ne $guardObj.grace)` (guard line 216) when verified.

**`commit_change` gate-then-commit body** (RESEARCH Code Examples lines 452-464; defense-in-depth re-check mirrors `commit.rs:148`):
```rust
let dirs = classify::classify_change(&old_yaml, &new_yaml)?;
let decision = quota::decide(&dirs, &current_state, now_utc, &tz);
if !decision.allowed { return Err(IpcError::Engine(decision.reason.unwrap())); } // 0-token loosen
let true_now = SntpTrueTime::default().now().map(|t| t.unix_secs)
    .map_err(|_| IpcError::Engine("ntp unreachable".into()))?;  // fail-closed for the ledger
let new_state = commit::commit_change(&paths, &new_yaml, &dirs, &decision, &key, true_now)?;
// then RE-READ freshly-signed state (D-09) and return StateDto
```
> `commit.rs:148` already guards `if !decision.allowed { return Err(QuotaExhausted) }` — the command re-checking `decision.allowed` is the SAME defense-in-depth, not a new rule.

**`use_grace` body** (RESEARCH lines 466-472; `grace.rs:45-50` signature):
```rust
let window = grace::use_grace(&paths, &SntpTrueTime::default(), &tz, &key)?; // NtpUnreachable / AlreadyUsedToday
// re-read state (D-09) → StateDto { grace_active=true, boundary=window.window_end }
```

---

### `src-tauri/src/lib.rs` (app host / wiring, event-driven)

**Primary analog:** `crates/mutation-engine/src/bin/state_interop_cli.rs` (entry + key-load + data-dir resolution glue)

**Key-load + data-dir glue — copy the CLI's `load_or_create_key(Path::new(...))` usage** (`state_interop_cli.rs:108, 144`; lifecycle in `trust-kernel/src/key.rs:41-60`). `AppCtx::load()` resolves the data dir (same `NIGHTGUARD_DIR` the guard reads — `nightguard_guard.ps1:42-56`), loads the key ONCE, and builds `CommitPaths`:
```rust
// trust_kernel::key::load_or_create_key — the ONE key path; do not add a second (Pitfall 4)
let key = load_or_create_key(&data_dir.join(".guardkey"))?;  // Scope::User, None entropy
```
Data-dir resolution mirrors the guard exactly (`nightguard_guard.ps1:42-56`): `NIGHTGUARD_DIR` env (or override), then fixed filenames `config.yaml` / `config.sanctioned.yaml` / `guard.json` / `.nightguard.lock` / `.guardkey`. `CommitPaths` is defined at `commit.rs:42-52`.

**The `tauri::Builder` / `run()` shape itself is NET-NEW** — follow 04-RESEARCH.md lines 294-304 verbatim:
```rust
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let ctx = AppCtx::load();
    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .manage(ctx)
        .invoke_handler(tauri::generate_handler![get_state, classify_change, commit_change, use_grace])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

---

### `lock_status.rs` — in `crates/mutation-engine/src/` (service, transform) — HIGHEST-RISK, net-new logic

**Open Q3 decision:** put it in `mutation-engine` (not `src-tauri`) so it gets the same offline unit-test treatment as `classify`/`quota`/`week`. Add `pub mod lock_status;` to `mutation-engine/src/lib.rs:18-25`.

**Primary analog:** `crates/mutation-engine/src/classify.rs` — reuse its **private window/time parsing** (the only existing curfew-window code in the repo). `parse_window` (`classify.rs:362-365`) and `parse_hhmm` (`classify.rs:270-279`) are exactly the `HH:MM-HH:MM` / `HH:MM` parsers `lock_status` needs:
```rust
// crates/mutation-engine/src/classify.rs:270-279 + 362-365 — lift this parsing approach
fn parse_hhmm(s: &str) -> Option<i64> {        // -> minutes since midnight
    let (h, m) = s.split_once(':')?;
    let h: i64 = h.trim().parse().ok()?; let m: i64 = m.trim().parse().ok()?;
    if (0..24).contains(&h) && (0..60).contains(&m) { Some(h*60 + m) } else { None }
}
fn parse_window(s: &str) -> Option<(i64, i64)> {  // "HH:MM-HH:MM" -> (start_min, end_min)
    let (start, end) = s.split_once('-')?;
    Some((parse_hhmm(start.trim())?, parse_hhmm(end.trim())?))
}
```
> These are currently `fn` (private). The planner should either make them `pub(crate)` and share, or duplicate the two tiny parsers into `lock_status.rs` — **do not introduce a second, divergent HH:MM parser with different bounds checking.**

**yamlpath field-read pattern — copy `classify.rs`'s `read_field` defensive-absent reader** (`classify.rs:194-220`). `lock_status` reads `curfew.enabled`, `curfew.start/end`, `curfew.schedule.<day>`, `timezone` the same way (Route + `query_exact`, missing path → treat as absent, NEVER panic, NEVER silently unlock):
```rust
// crates/mutation-engine/src/classify.rs:194-209 — the defensive read to reuse (A2: absent != loosen)
let route = Route::default().with_keys(keys.iter().map(|k| (*k).into()));
match doc.query_exact(&route) {
    Ok(Some(feat)) => Ok(Some(normalize(doc.extract(&feat)))),
    Ok(None) => Ok(None),
    Err(QueryError::ExhaustedMapping(_) | QueryError::ExpectedMapping(_)
        | QueryError::ExhaustedList(_, _) | QueryError::ExpectedList(_)) => Ok(None),
    Err(e) => Err(yaml_err(e)),
}
```

**tz / DST instant math — copy `week.rs`'s tz-resolution discipline** (`week.rs:47-60, 102-104`). Advisory "now in config tz" + boundary→unix conversion must use the same explicit `MappedLocalTime` handling and the `parse_tz` defensive default; the `true_day` helper in `grace.rs:91-96` is the closest "unix→tz date" converter to mirror for the boundary instant:
```rust
// crates/mutation-engine/src/week.rs:102-104 — never panic on bad tz (mirror this default)
fn parse_tz(tz_name: &str) -> Tz { tz_name.parse().unwrap_or(chrono_tz::UTC) }
```
```rust
// crates/mutation-engine/src/grace.rs:91-96 — unix-secs -> "in this tz" instant, defensive
let tz: Tz = tz_name.parse().unwrap_or(chrono_tz::UTC);
let instant = DateTime::<Utc>::from_timestamp(unix_secs, 0).unwrap_or(/* epoch */);
instant.with_timezone(&tz) // ... derive the local minute-of-day + weekday for the window check
```

**Pure-fn + module-doc discipline — copy the `classify.rs` / `week.rs` header style** ("This module is 100% pure — no file I/O … so the whole matrix runs offline"; `classify.rs:29-31`, `week.rs:12-13`). `lock_status` is pure: `(config_yaml: &str, now: DateTime<Utc>) -> LockStatus`.

**NET-NEW (no analog — Open Q1 / Pitfall 1):** the actual "is this minute inside the curfew window, including overnight-wrap (`23:00-07:00`), with `schedule.<day>` precedence over `start/end`, and `enabled=false`" verdict, **and** the "next boundary" computation. There is **no** curfew evaluator anywhere in the repo (grep-confirmed in RESEARCH). The classifier only *compares* two windows for direction; it never asks "are we in one now." Treat the boundary minute as advisory (D-04) and budget this as its own plan task with a written precedence spec.

---

### `crates/mutation-engine/tests/lock_status.rs` (test, transform)

**Analog:** `crates/mutation-engine/tests/quota.rs` — EXACT match for the offline diff/truth-table style.

**Copy the table helpers + fixed-`now()` + per-case asserts** (`quota.rs:18-55`):
```rust
// crates/mutation-engine/tests/quota.rs:18-43 — mirror these helpers for lock_status cases
const TZ: &str = "Europe/Amsterdam";
fn utc(y: i32, mo: u32, d: u32, h: u32, mi: u32) -> DateTime<Utc> {
    Utc.with_ymd_and_hms(y, mo, d, h, mi, 0).single().unwrap()
}
fn now() -> DateTime<Utc> { utc(2026, 6, 9, 12, 0) }   // a fixed, documented instant

#[test]
fn all_tighten_commit_is_free_and_allowed() {
    let dec = decide(&d, &state_current_week(0), now(), TZ);
    assert!(dec.allowed); assert!(!dec.costs_token);
}
```
→ For `lock_status`: one `#[test]` per case (inside-window / outside-window / overnight-wrap boundary / `enabled=false` / `schedule.<day>` override / bad-tz default), each building a config literal + a fixed `now()` and asserting `{locked, grace_active, boundary_unix, boundary_kind}`. Mirror the `quota.rs` discipline of a small builder + explicit per-case asserts.

---

### `Cargo.toml` (root, MODIFIED) — config

**Analog:** the file itself. Add the third member, do NOT add a nested `[workspace]` in `src-tauri` (RESEARCH Pattern 1 anti-pattern guard):
```toml
[workspace]
resolver = "2"
members = ["crates/trust-kernel", "crates/mutation-engine", "src-tauri"]
```

### `src-tauri/Cargo.toml` (NEW) — config

**Analog:** `crates/mutation-engine/Cargo.toml` for **dep-declaration style** (path deps + pinned versions). Note the existing crate lives at `crates/`, so the path dep is `../crates/...`:
```toml
# style mirror: crates/mutation-engine/Cargo.toml:12-24 (path dep + pinned versions + features arrays)
[dependencies]
trust-kernel    = { path = "../crates/trust-kernel" }
mutation-engine = { path = "../crates/mutation-engine" }
serde      = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror  = "1"
chrono     = "0.4"
chrono-tz  = "0.10"
```
The `[lib] crate-type = ["staticlib","cdylib","rlib"]`, `[build-dependencies] tauri-build`, and `tauri`/`tauri-plugin-fs` deps are **net-new** → copy verbatim from 04-RESEARCH.md lines 228-253.

---

## Shared Patterns

### Re-verify, never re-implement crypto (applies to: `commands.rs`)
**Source:** `crates/trust-kernel/src/hmac.rs:36-39` (`verify_bytes`, constant-time) + `crates/mutation-engine/src/state.rs:49-56` (`compute_state_hmac`).
**Apply to:** every `get_state` call and the read-back after commit/grace.
```rust
// hmac.rs:36-39 — constant-time; the `==`-on-tags anti-pattern is FORBIDDEN (CLAUDE.md)
pub fn verify_bytes(key: &[u8; 32], msg: &[u8], tag: &[u8; 32]) -> bool {
    let mut mac = HmacSha256::new_from_slice(key).expect("HMAC accepts any key length");
    mac.update(msg);
    mac.verify_slice(tag).is_ok()   // subtle-backed; NOT `==`
}
```

### Error enum: thiserror + prefixed message + `From` folding (applies to: `commands.rs`, `lock_status.rs`)
**Source:** `crates/mutation-engine/src/state.rs:85-118` (and the twin `KernelError` in `trust-kernel/src/key.rs:17-37`).
**Apply to:** `IpcError` (add `Serialize`-as-string), and any error `lock_status` surfaces (fold YAML errors into `MutationError::Serde` exactly like `classify.rs:368-370`).

### Defensive-absent / fail-safe field reads (applies to: `lock_status.rs`, `commands.rs`)
**Source:** `crates/mutation-engine/src/classify.rs:194-220` (`read_field` + `normalize`), echoed by `parse_tz`/`true_day` defaults.
**Apply to:** every config-field read. A missing/malformed field is **never** a silent unlock — it degrades to the locked/“time unverified” caveat (D-04), mirroring the engine’s A2 "absent → Noop, never silent loosen."

### Worst-case-on-tamper parity with the guard (applies to: `commands.rs` `StateDto`)
**Source:** `scripts/guard/nightguard_guard.ps1:204-222`.
**Apply to:** `get_state` DTO assembly — on `state_verified == false` substitute `weekly_spent=3 / tokens_remaining=0 / grace_available_today=false`. The app must never look *less* locked than the guard.

### Use the engine's ordered locked commit — never hand-roll a writer (applies to: `commands.rs`)
**Source:** `crates/mutation-engine/src/commit.rs:184-193` (`commit_change`) + `grace.rs:45-85` (`use_grace`), both wrapping `with_commit_lock` (`commit.rs:61-81`).
**Apply to:** `commit_change`/`use_grace` commands — call these directly; do NOT reopen the sign-vs-write race the guard's circuit-breaker is calibrated for (RULE-06 / GARD-05).

### Pure-module + offline-test discipline (applies to: `lock_status.rs` + its test)
**Source:** `classify.rs:29-31`, `week.rs:12-13`, `quota.rs` test table.
**Apply to:** `lock_status` as a pure `(config, now) -> LockStatus` fn with a diff-table test, so the highest-risk net-new logic is exhaustively testable offline.

---

## No Analog Found

These have NO in-repo analog (no `src/`, no `package.json`, no `#[tauri::command]`, no `tauri.conf.json` exist). The planner should use 04-RESEARCH.md + 04-UI-SPEC.md, not force a codebase match.

| File | Role | Data Flow | Reason / Source to use instead |
|------|------|-----------|--------------------------------|
| `src/main.ts` | frontend controller | request-response + event-driven | No frontend exists. Use RESEARCH Patterns 2 (`invoke` from `@tauri-apps/api/core`) + 4 (`watch` + 1s tick), UI-SPEC interaction/copy contract. |
| `src/index.html` | frontend view | — | No HTML in repo. Use UI-SPEC §Layout Contract (56px left-rail, centered hero countdown, single edit `--surface`). |
| `src/styles.css` | frontend styling | — | No CSS in repo. Use UI-SPEC palette tokens / 4-size type scale / 8-pt spacing; bundle Roboto woff2 locally (no CDN — Pitfall 6). |
| `src-tauri/main.rs` | bin entry | — | 3-line v2 shim → RESEARCH "State of the Art". |
| `src-tauri/build.rs` | config | — | Standard `tauri_build::build()` → RESEARCH §Installation. |
| `src-tauri/tauri.conf.json` | config | — | RESEARCH §Recommended Structure + Installation (window/bundle.targets/frontendDist/devUrl). |
| `src-tauri/capabilities/default.json` | config | — | RESEARCH Pattern 4 (`core:default` + `fs:allow-watch`/`fs:allow-unwatch` + scoped `fs:scope`); Pitfall 5 (scope to resolved data dir). |
| `package.json` / `vite.config.ts` | config | — | RESEARCH §Installation (scaffold via `create-tauri-app` vanilla-TS, then re-home). |

> **Note:** the `tauri::Builder` body in `lib.rs` and the `#[tauri::command]` attribute/`generate_handler!` macro in `commands.rs` are themselves net-new Tauri idioms (no analog) — only the *error/DTO/glue/key-load* substance inside them has analogs. The table above lists files that are net-new end-to-end; `lib.rs`/`commands.rs` are hybrids (analog substance + net-new Tauri shell).

---

## Metadata

**Analog search scope:** `crates/trust-kernel/src/`, `crates/trust-kernel/tests/`, `crates/mutation-engine/src/` (incl. `bin/`), `crates/mutation-engine/tests/`, `scripts/guard/nightguard_guard.ps1`, root `Cargo.toml`, crate `Cargo.toml`s.
**Files scanned (read in full):** `mutation-engine/src/{lib,state,classify,quota,commit,grace,ntp,week,sign}.rs`, `mutation-engine/src/bin/state_interop_cli.rs`, `mutation-engine/tests/{quota,lock_probe}.rs`, `mutation-engine/Cargo.toml`, `trust-kernel/src/{lib,hmac,key}.rs`, root `Cargo.toml`, `nightguard_guard.ps1` (relevant ranges).
**Grep-confirmed gaps:** no `#[tauri::command]`, no `src/` frontend, no `package.json`/`tauri.conf.json`, no curfew-window evaluator (only private `parse_window` in `classify.rs`).
**Pattern extraction date:** 2026-06-09
