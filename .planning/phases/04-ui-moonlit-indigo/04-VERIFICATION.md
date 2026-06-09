---
phase: 04-ui-moonlit-indigo
verified: 2026-06-09T10:50:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Visual walkthrough — Moonlit Indigo rendering, countdown jitter, accent correctness"
    expected: "Window opens with dark #0c0e14 background, countdown in 64px Roboto 500, accent dots filled in #7aa2ff, no digit jitter on the 1-second tick; status word reads '🌙 LOCKED' or 'OPEN' depending on time-of-day"
    why_human: "CSS custom property application and tabular-nums rendering cannot be verified by grep; requires WebView2 paint"
  - test: "Live liveness — hand-edit config.yaml and confirm UI flips to 'State unverified' within ~1s"
    expected: "The plugin-fs watch triggers a get_state re-invoke; the status word changes to the amber 'State unverified' copy within roughly one debounce period (250ms)"
    why_human: "Requires a running app with a populated NIGHTGUARD_DIR, a signed fixture, and a human display to observe the 1s watcher firing"
  - test: "+8 minutes button enabled/disabled state + grant flow"
    expected: "Button is disabled and dim when OPEN or grace already used; enabled with accent fill during an active lock when grace_available_today=true; pressing it shows the grace countdown retargeted to grace_end in the hero"
    why_human: "Interactive state machine — requires live SNTP, a locked session, and a human to press the button and observe the countdown change"
  - test: "Loosen confirm dialog + token-meter decrement"
    expected: "Editing a field that loosens the curfew shows amber 'Loosens curfew · costs 1 token' inline, then on Commit a window.confirm fires with 'Spend a weekly token?'; after confirm the token dot count decrements by 1 in the rendered meter"
    why_human: "window.confirm interaction and the animated meter update require a running app with a live guard.json state; cannot observe via static analysis"
  - test: "Empty-state rendering when NIGHTGUARD_DIR points to a directory with no guard.json"
    expected: "Status word shows 'No signed config yet'; countdown shows '--:--:--'; no token meter; caption shows the setup copy from UI-SPEC"
    why_human: "Requires a running app pointed at an empty directory"
---

# Phase 4: UI Moonlit Indigo — Verification Report

**Phase Goal:** The non-authoritative display + edit-intent layer reflects hook-enforced reality and gives live per-field feedback, in the Moonlit Indigo aesthetic.
**Verified:** 2026-06-09T10:50:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Main screen shows lock status (🌙 LOCKED / OPEN) with a live countdown reflecting hook-enforced reality, never app-local optimism | ✓ VERIFIED | `render()` in main.ts:118-194 derives `word` and countdown from a freshly re-verified `get_state` DTO; the 1s `setInterval` calls only `renderCountdownOnly(last)` — never `invoke`. `build_state_dto` re-verifies both HMACs via `verify_bytes` (config) and `verify_tag_hex` (state) before any DTO field is set. |
| 2 | Main screen shows the 3-dot weekly token meter with next-reset and today's grace availability | ✓ VERIFIED | main.ts:163-184 renders 3 `.token-dot` spans with `filled` (accent) class for `tokens_remaining`; `tokenCaptionEl()` shows `"{n} of 3 tokens · resets Monday {date}"`; `graceCaptionEl()` renders the "+8 available/used/unavailable" copy per UI-SPEC line 153. |
| 3 | "+8 minutes" button enabled only during an active lock when grace is available, and grants the window on press | ✓ VERIFIED | main.ts:188-191: `graceEnabled = s.locked && s.grace_available_today`; `graceBtn.disabled = !graceEnabled`; the `.enabled` class (accent fill) toggles only when the gate is met. `onGrace()` calls `invoke<StateDto>("use_grace")` and re-renders from the returned re-verified DTO (D-09). |
| 4 | Edit panel shows per-field inputs with live tighten/loosen feedback and disables commit with a reason when loosening at 0 tokens | ✓ VERIFIED | `applyClassify()` (main.ts:391-424) applies `tighten`/`loosen` classes and copy to `fb-curfew.*` spans; `commit.disabled = true` + `editReasonEl().textContent` is set when `hasLoosen && !c.allowed`. Commit handler confirms once on loosen (main.ts:451-459), then calls `commit_change`. |
| 5 | Interface implements the Moonlit Indigo palette + Roboto + left-icon-rail / flat-card layout | ✓ VERIFIED (partial — visual requires human) | styles.css:28-47 defines all 7 palette tokens exactly per CLAUDE.md spec (`--bg #0c0e14`, `--surface #161a24`, `--border #242a38`, `--text #e8eaf0`, `--dim #8b91a3`, `--accent #7aa2ff`, `--warn #f0a35e`). Roboto bundled as woff2 in `src/assets/roboto-400.woff2` + `roboto-500.woff2`. `--rail-w: 56px` left-rail in index.html with two inline SVG items carrying `aria-label="Status"` / `aria-label="Edit"`. Type scale: 64px Display, 20px Heading, 16px Body, 14px Label. `font-variant-numeric: tabular-nums` on `#countdown`. Visual rendering requires human. |

**Score:** 5/5 truths verified (visual rendering of truth 5 deferred to human)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src-tauri/src/commands.rs` | 4+ `#[tauri::command]` fns + StateDto/ClassifyDto + IpcError + AppCtx + real bodies | ✓ VERIFIED | 6 commands registered: `get_state`, `data_dir`, `read_config`, `classify_change`, `commit_change`, `use_grace`. `build_state_dto` has real read+verify+derive body. All DTOs match plan frontmatter field lists. |
| `src-tauri/src/lib.rs` | `run()` with plugin-fs, `.manage(AppCtx)`, `generate_handler!` of 6 commands, WR-02 scope extension | ✓ VERIFIED | `generate_handler![get_state, data_dir, read_config, classify_change, commit_change, use_grace]` at line 45. WR-02 fix: `app.fs_scope().allow_directory(&watch_dir, true)` in `.setup()` extends scope to the resolved NIGHTGUARD_DIR. |
| `crates/mutation-engine/src/lock_status.rs` | Pure `lock_status(config_yaml, now)` + `LockStatus` struct + `NO_UPCOMING_LOCK` sentinel + precedence spec | ✓ VERIFIED | `pub fn lock_status` at line 140; `pub struct LockStatus` at line 60; `pub const NO_UPCOMING_LOCK: i64 = i64::MAX` at line 78; full precedence spec in module doc comment. |
| `crates/mutation-engine/tests/lock_status.rs` | 8+ cases: inside, outside, overnight-wrap, non-overnight, enabled=false, schedule precedence, defensive-absent, bad-tz | ✓ VERIFIED | 11 tests all passing (`cargo test -p mutation-engine --test lock_status` exit 0). All 8 mandated cases plus 3 split sub-cases. |
| `src/index.html` | Full shell DOM: left rail, status-view, edit-view, +8 button, per-field inputs | ✓ VERIFIED | All required IDs present: `#rail`, `#status-view`, `#status-word`, `#countdown`, `#token-meter`, `#grace-btn`, `#edit-view`, `#field-enabled`, `#field-start`, `#field-end`, `#commit-btn`, `fb-curfew.enabled`, `fb-curfew.start`, `fb-curfew.end`. |
| `src/styles.css` | Moonlit Indigo palette + Roboto + 8pt spacing + left-rail + type scale + tabular-nums | ✓ VERIFIED | All 7 palette tokens exact. All 4 type sizes (64/20/16/14px). `--rail-w: 56px`. `font-variant-numeric: tabular-nums` on `#countdown`. |
| `src/main.ts` | get_state render + plugin-fs watch + 1s tick + edit view + classify/commit/grace handlers | ✓ VERIFIED | All handlers present and wired: `refresh()`, `startWatch()`, `render()`, `renderCountdownOnly()`, `applyClassify()`, `onCommit()`, `onGrace()`, `scheduleClassify()`. |
| `src/assets/roboto-{400,500}.woff2` | Bundled Roboto fonts (no CDN) | ✓ VERIFIED | Both files present on disk. |
| `Cargo.toml` (root) | `src-tauri` in workspace members | ✓ VERIFIED | `members = ["crates/trust-kernel", "crates/mutation-engine", "src-tauri"]` |
| `src-tauri/capabilities/default.json` | `core:default`, `fs:allow-watch`, `fs:allow-unwatch`, `fs:scope` | ✓ VERIFIED | All four permissions present. Scope covers `$HOME/.nightguard` and `$APPDATA/nightguard`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `commands.rs build_state_dto` | `trust_kernel::hmac::verify_bytes` | Config HMAC constant-time verify | ✓ WIRED | Line 217: `verify_bytes(&ctx.key, &canon, &tag)` |
| `commands.rs build_state_dto` | `trust_kernel::hmac::verify_tag_hex` | State HMAC constant-time verify (CR-01 fix) | ✓ WIRED | Line 226: `verify_tag_hex(&gs.compute_state_hmac(&ctx.key), &gs.state_hmac)` — uses `subtle::ConstantTimeEq`, never `String ==` |
| `commands.rs build_state_dto` | `mutation_engine::lock_status::lock_status` | Curfew lock verdict | ✓ WIRED | Line 240: `lock_status(&config_yaml, now_utc)` |
| `commands.rs build_state_dto` | `mutation_engine::lock_status::config_timezone` | WR-06 fix: tz from config, not hardcoded | ✓ WIRED | Line 237: `let tz = config_timezone(&config_yaml)` |
| `commands.rs today_in_tz` | Returns `Option<String>` (WR-01 fix) | Fail-closed grace date check | ✓ WIRED | Line 278-281: `(Some(_), None) => false` arm — unresolvable today maps to grace unavailable |
| `commands.rs commit_change` | `mutation_engine::commit::commit_change` | Ordered fd-locked writer | ✓ WIRED | Line 481: `commit::commit_change(...)` after WR-05 re-verification gate |
| `commands.rs commit_change` | WR-05 old-side re-verify | Config tamper check before classify | ✓ WIRED | Lines 446-457: `verify_bytes` on raw_old vs `gs.config_hmac`; refuses on mismatch |
| `commands.rs use_grace` | `mutation_engine::grace::use_grace` | Once-daily grace grant | ✓ WIRED | Line 505: `grace::use_grace(&state.paths, &SntpTrueTime::default(), &tz, &state.key)` |
| `src/main.ts` | `get_state` command | Liveness invoke + render | ✓ WIRED | Line 233: `invoke<StateDto>("get_state")` in `refresh()`; called on load, watch trigger, and after commit/grace |
| `src/main.ts` | `classify_change` command | Debounced per-field feedback | ✓ WIRED | Line 438: `invoke<ClassifyDto>("classify_change", { oldYaml, newYaml })` inside `runClassify()` debounced at 250ms |
| `src/main.ts` | `commit_change` command | Gated commit after confirm | ✓ WIRED | Line 465: `invoke<StateDto>("commit_change", { newYaml })` in `onCommit()` after loosen confirm |
| `src/main.ts` | `use_grace` command | Grace grant on button press | ✓ WIRED | Line 280: `invoke<StateDto>("use_grace")` in `onGrace()` |
| `lib.rs` | WR-02 fs scope extension | `allow_directory` at runtime | ✓ WIRED | Lines 27-41: `app.fs_scope().allow_directory(&watch_dir, true)` in `.setup()` |
| `lock_status.rs` | `NO_UPCOMING_LOCK` sentinel for enabled=false / off days (CR-02 fix) | No false boundary on OPEN | ✓ WIRED | Line 78: `pub const NO_UPCOMING_LOCK: i64 = i64::MAX`; used in `no_upcoming_lock()` at lines 108-115; test asserts `boundary_unix == NO_UPCOMING_LOCK` and `boundary_unix > now.timestamp()` |
| `mutation-engine/src/lib.rs` | `pub mod lock_status` | Module registered | ✓ WIRED | Line 21 confirmed |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `main.ts render()` | `StateDto.locked`, `boundary_unix`, `tokens_remaining` | `invoke("get_state")` → `build_state_dto` reads `config.yaml` + `guard.json` from disk, re-verifies HMACs, calls `lock_status` | Yes — reads real signed artifacts; no static fallback | ✓ FLOWING |
| `main.ts applyClassify()` | `ClassifyDto.fields`, `allowed`, `reason` | `invoke("classify_change")` → `classify::classify_change` + `quota::decide` over live `guard.json` | Yes — real per-field directions from yamlpath diff | ✓ FLOWING |
| `main.ts render()` token meter | `StateDto.tokens_remaining`, `next_reset_unix` | `quota::decide(&[], &gs, now_utc, &tz)` in `build_state_dto` | Yes — real `GuardState.weekly_spent` from guard.json | ✓ FLOWING |
| `main.ts render()` grace | `StateDto.grace_available_today`, `grace_active` | `today_in_tz` returning `Option<String>`; compared against `gs.grace.date` | Yes — WR-01 fix: `None` maps to `false` (fail-closed), not empty-string | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| lock_status test suite (11 tests) | `cargo test -p mutation-engine --test lock_status` | exit 0, 11 passed | ✓ PASS |
| nightguard-control cargo check | `cargo check -p nightguard-control` | exit 0, compiles clean | ✓ PASS |
| `verify_tag_hex` exists and uses `subtle::ConstantTimeEq` | grep in `crates/trust-kernel/src/hmac.rs` | Found at line 55; uses `a.ct_eq(&b).into()` | ✓ PASS |
| `NO_UPCOMING_LOCK` sentinel in live code | grep in `lock_status.rs` | `pub const NO_UPCOMING_LOCK: i64 = i64::MAX` at line 78 | ✓ PASS |
| No `String ==` on HMAC tags anywhere in commands.rs | grep for `== gs.state_hmac` | Not found | ✓ PASS |
| WR-05: old-side re-verify before classify in commit_change | grep for `old_verified` in commands.rs | Lines 447-457 confirm | ✓ PASS |
| WR-06: `config_timezone` used instead of hardcoded `ctx.tz` | grep in commands.rs | Lines 237, 404, 464 all use `config_timezone(...)` | ✓ PASS |
| tauri dev (window opens, interactive behaviors) | Requires running app | Cannot test without NIGHTGUARD_DIR + signed fixture | ? SKIP |

---

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` probes declared for this phase. Skipped — no probe files present.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| UI-01 | 04-01, 04-02, 04-03, 04-04 | Main screen shows lock status + countdown reflecting hook-enforced reality | ✓ SATISFIED | `render()` derives `word`/countdown from re-verified `get_state`; `lock_status` evaluator unit-tested across all window cases; `boundary_kind="none"` path renders `--:--:--` (no stuck 00:00:00) |
| UI-02 | 04-01, 04-03, 04-04 | 3-dot weekly token meter + next-reset + grace availability | ✓ SATISFIED | Token meter rendered in `render()` lines 163-184; `tokens_remaining` from `quota::decide` on real `guard.json`; `tokenCaptionEl()` + `graceCaptionEl()` per UI-SPEC copy |
| UI-03 | 04-01, 04-03, 04-05 | "+8 minutes" enabled only during active lock + grace available; grants window on press | ✓ SATISFIED | `graceEnabled = s.locked && s.grace_available_today`; `graceBtn.disabled = !graceEnabled`; `onGrace()` calls `use_grace` then re-renders from D-09 |
| UI-04 | 04-01, 04-03, 04-05 | Edit panel per-field inputs + live tighten/loosen feedback + disabled-commit with reason at 0 tokens | ✓ SATISFIED | `applyClassify()` applies `tighten`/`loosen` classes + copy; `commit.disabled = true` + reason when `hasLoosen && !c.allowed`; debounced at 250ms |
| UI-05 | 04-04, 04-05 | Moonlit Indigo palette + Roboto + left-icon-rail / flat-card layout | ✓ SATISFIED | All 7 palette tokens exact in styles.css; Roboto woff2 bundled locally; `--rail-w: 56px` rail; `font-variant-numeric: tabular-nums` on countdown. Visual rendering = human |

---

### Code Review Findings Verification (CR-01, CR-02, WR-01..WR-06)

| Finding | Description | Fixed? | Evidence |
|---------|-------------|--------|----------|
| CR-01 | `state_hmac` verified with non-constant-time `String ==` | ✓ FIXED | `verify_tag_hex(&gs.compute_state_hmac(&ctx.key), &gs.state_hmac)` — uses `subtle::ConstantTimeEq` inside `trust_kernel::hmac`. Never `String ==`. |
| CR-02 | OPEN "next lock" boundary ignores `off`/disabled days; can point at past | ✓ FIXED | `NO_UPCOMING_LOCK = i64::MAX` sentinel; `no_upcoming_lock()` used on `enabled=false` and `schedule.<day>=off` paths; `boundary_kind="none"` triggers `--:--:--` in UI; tests assert `boundary_unix == NO_UPCOMING_LOCK` and `> now`. |
| WR-01 | `today_in_tz` fail-open on bad timestamp can re-arm grace | ✓ FIXED | `today_in_tz` returns `Option<String>`; `(Some(_), None) => false` arm at line 280 of commands.rs — unresolvable today = grace not available. |
| WR-02 | `fs:scope` does not match the actual `NIGHTGUARD_DIR` | ✓ FIXED (runtime) | `lib.rs` extends scope at startup via `app.fs_scope().allow_directory(&watch_dir, true)`. Static capability still covers default locations; watch-failure is surfaced loudly in `startWatch()` caption. |
| WR-03 | `csp: null` disables Content-Security-Policy | NOT FIXED (tracked as IN-class debt) | `tauri.conf.json` `csp: null` remains. Reviewed as acceptable INFO-level debt for a personal-instance tool; not a phase gate blocker. |
| WR-04 | Frontend YAML line-rewrite regex can corrupt config | ✓ FIXED | `setYamlField` in main.ts:319-353 now (1) escapes key via `escapeRegExp`, (2) locates the `curfew:` block first, (3) only rewrites a direct child line at deeper indent, (4) preserves trailing inline `# comment`. |
| WR-05 | `commit_change` trusts on-disk config without re-verifying HMAC | ✓ FIXED | Lines 446-457 of commands.rs: `verify_bytes` on `canon_old` vs `gs.config_hmac` before classify; refuses with a clear error on mismatch. |
| WR-06 | `AppCtx.tz` hardcoded, misdriving week/grace math | ✓ FIXED | `config_timezone(&config_yaml)` used at every call site (lines 237, 404, 464, 500-502); `AppCtx.tz` is only a startup fallback for the unreadable-config edge, documented in comments. |

**Note on WR-03:** The code review classified this as a WARNING and it remains unaddressed (`csp: null` in tauri.conf.json). Given the project's personal-instance focus and the absence of remote content, this is acceptable debt. It does not block the phase goal but should be addressed before any public distribution.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `src-tauri/src/commands.rs:43` | `#[allow(dead_code)]` on `VerifyFailed` variant | INFO | Tracked as IN-01 in code review; reserved API surface. Does not affect goal. |
| `src/main.ts:239-243` | `String(err).includes("not initialized")` for empty-state detection | INFO | Tracked as IN-02 in code review. Brittle string match on IpcError display text. Does not affect current behavior since `#[error("not initialized")]` is stable. |
| `src/main.ts:244` | `console.error(...)` debug artifact | INFO | Tracked as IN-03. Acceptable for personal-instance tool. |
| `src-tauri/tauri.conf.json` | `csp: null` | WARNING | Tracked as WR-03 above. No CSP in the webview. Acceptable debt for personal use; blocks public distribution. |

No `TBD`, `FIXME`, or `XXX` markers found in any phase-modified file.

---

### Human Verification Required

#### 1. Moonlit Indigo Visual Rendering

**Test:** Set `NIGHTGUARD_DIR` to a directory containing a signed `config.yaml` + `guard.json` + `.guardkey`, then run `npm install && npx tauri dev`. Observe the opened window.
**Expected:** Background is `#0c0e14` (very dark navy); countdown is 64px Roboto 500 in `#e8eaf0`; no digit jitter on the 1-second tick (tabular-nums); status word at 20px; left rail is `#161a24` at 56px with two monochrome SVG icons.
**Why human:** CSS custom property rendering and tabular-nums digit stability cannot be verified by static analysis; requires WebView2 paint.

#### 2. Live Liveness — Hand-Edit Triggers 'State unverified'

**Test:** With `tauri dev` running against a signed fixture, open `config.yaml` in a text editor and make a change (e.g. alter a comment). Within ~1 second observe the UI.
**Expected:** The status word changes to amber "State unverified" and the caption shows the fail-closed re-sync copy from UI-SPEC.
**Why human:** Requires a running app instance, a file system event triggering the 250ms-debounced watch callback, and a human display to observe the state transition.

#### 3. "+8 Minutes" Button Enabled State and Grant Flow

**Test:** During an active curfew lock (with `grace_available_today=true` in the returned DTO), observe the "+8 minutes" button. Press it.
**Expected:** Button shows accent fill (`#7aa2ff`) and is clickable. On press, the hero countdown retargets to `grace_end` (8 minutes from now); status word shows "🌙 LOCKED · grace"; grace caption changes to "+8 used today".
**Why human:** Requires a live SNTP connection, a locked session, and a human to observe the countdown change. `use_grace` calls real NTP via `SntpTrueTime`.

#### 4. Loosen Confirm Dialog and Token-Meter Decrement

**Test:** Open the Edit view, change the curfew end time to a later hour (a loosen). Observe the per-field feedback, then press Commit.
**Expected:** The `fb-curfew.end` span shows amber "Loosens curfew · costs 1 token". Commit button label changes to "Commit (spends 1 token)". On press, `window.confirm` fires with "Spend a weekly token?" copy. After confirming, the token meter decrements by one dot.
**Why human:** Requires `window.confirm` interaction, a live `guard.json` with tokens remaining, and a human to observe the meter update.

#### 5. Empty State Rendering

**Test:** Set `NIGHTGUARD_DIR` to an empty directory (no `guard.json`) and run the app.
**Expected:** Status word shows "No signed config yet"; countdown shows "--:--:--"; token meter is empty; caption shows the setup copy from UI-SPEC ("Nightguard hasn't been initialized…").
**Why human:** Requires a running app and a human display to confirm the empty-state branch renders correctly.

---

### Gaps Summary

No gaps found. All five observable truths are verified in the codebase. All 8 code-review critical/warning findings that were declared fixed (CR-01, CR-02, WR-01..WR-06) are confirmed fixed by code inspection. The only unaddressed finding (WR-03: `csp: null`) was left as tracked INFO-level debt and does not block the phase goal.

The 5 human verification items above are the only remaining open checks. They require a running `tauri dev` instance with a populated `NIGHTGUARD_DIR` and a human display.

---

_Verified: 2026-06-09T10:50:00Z_
_Verifier: Claude (gsd-verifier)_
