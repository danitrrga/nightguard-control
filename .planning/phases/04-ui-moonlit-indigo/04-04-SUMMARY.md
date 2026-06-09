---
phase: 04-ui-moonlit-indigo
plan: 04
subsystem: ui
tags: [tauri, frontend, status-view, countdown, plugin-fs, watch, moonlit-indigo, render, liveness]

# Dependency graph
requires:
  - phase: 04-ui-moonlit-indigo
    plan: 01
    provides: "Tauri v2 shell, frozen StateDto TS interface (src/main.ts), AppCtx (.manage()d data_dir+key+paths+tz), capabilities/default.json scaffold"
  - phase: 04-ui-moonlit-indigo
    plan: 03
    provides: "Real get_state -> fully re-verified StateDto (lock/boundary, weekly_spent/tokens, grace, time_unverified, maximal_lockout worst-cased on tamper)"
provides:
  - "Default Status view: hero countdown (64px Display, tabular-nums) + 🌙 LOCKED / · grace / OPEN status word + 3-dot accent token meter + grace/verify/time captions"
  - "Liveness loop: plugin-fs watch(dataDir) re-invokes get_state on any data-dir change (D-05/D-09); 1s tick re-renders ONLY countdown digits (D-05, never invents a transition)"
  - "Moonlit Indigo design system in hand CSS (palette tokens + 4-size type scale + 8pt spacing + 56px left rail), locally-bundled Roboto 400/500 woff2 (no CDN)"
  - "New data_dir IPC command surfacing the absolute watch target to the frontend"
  - "fs:scope narrowed off bare ** to the conventional nightguard data dirs (least-privilege)"
affects: [04-05-edit-panel-and-actions]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "render() derives every assertion SOLELY from a freshly invoked get_state DTO; the !state_verified || maximal_lockout branch shows fully-locked 'State unverified' copy — no app-local optimism (D-03)"
    - "renderCountdownOnly() is the ONLY thing the 1s tick calls; it recomputes boundary_unix - now and NEVER touches the status word or lock state (D-05/T-04-14)"
    - "refresh() is the single place `last` is assigned (a fresh get_state); the watch callback always re-invokes get_state, never mutates local state (T-04-15)"
    - "data_dir command = read-only path surface (no secret) so the webview can target plugin-fs watch at the enforced dir (Pitfall 5)"
    - "fail-soft render: NotInitialized -> empty state; any other get_state error keeps the last good render rather than asserting a false transition"

key-files:
  created:
    - src/styles.css
    - src/assets/roboto-400.woff2
    - src/assets/roboto-500.woff2
  modified:
    - src/index.html
    - src/main.ts
    - src-tauri/src/commands.rs
    - src-tauri/src/lib.rs
    - src-tauri/capabilities/default.json

key-decisions:
  - "data_dir surfaced via a tiny new IPC command (the simpler seam) rather than a Tauri-config path; AppCtx.data_dir already existed (plan-01 reserved it for exactly this), so its #[allow(dead_code)] was removed once consumed"
  - "fs:scope narrowed to \$HOME/.nightguard + \$APPDATA/nightguard (+ /**) because NIGHTGUARD_DIR is only known at runtime; bare ** removed (T-04-17). Residual: a non-conventional NIGHTGUARD_DIR is out of watch scope — the 1s tick + load-time fetch still keep the display advisory-live, and the watch failure degrades gracefully (logged, not fatal)"
  - "Roboto 400/500 woff2 fetched once from the fontsource jsdelivr mirror and BUNDLED locally (src/assets/); no runtime CDN reference — vite emits them into dist/assets (T-04-16/Pitfall 6)"
  - "1s tick is countdown-digits-only and clamps at 00:00:00 on a passed boundary, waiting for the watch-driven re-read; it never flips the status word itself (T-04-14)"

patterns-established:
  - "DTO -> DOM render keeps the fail-closed posture: verify-fail toggles a .verify-fail class + warm-tone 'State unverified' copy; the time_unverified caveat is advisory-appended only when state itself verified (D-04)"
  - "left-rail active state is the one accent use in the shell (aria-current=page -> --accent); accent otherwise reserved to filled token dots"

requirements-completed: [UI-01, UI-02, UI-05]

# Metrics
duration: 6min
completed: 2026-06-09
---

# Phase 4 Plan 04: Status View + Liveness Loop Summary

**The default Status view now renders the re-verified `StateDto` in the Moonlit Indigo aesthetic — a 64px tabular-nums hero countdown as the emotional center, the 🌙 LOCKED / · grace / OPEN status word, and a 3-dot accent token meter with grace/verify/time captions — kept live by a `plugin-fs` watch of the data dir (re-invokes `get_state` on any change, D-05/D-09) and a 1-second tick that animates only the countdown digits and never invents a state transition (D-05/T-04-14).**

## Performance

- **Duration:** ~6 min
- **Tasks:** 2 auto + 1 checkpoint (auto-approved under AUTO_MODE)
- **Files created:** 3 (styles.css + 2 woff2)
- **Files modified:** 5

## Accomplishments

- **Task 1 — Moonlit Indigo design system (`311be93`):** `src/styles.css` defines the locked palette as CSS custom properties (`--bg #0c0e14 / --surface #161a24 / --border #242a38 / --text #e8eaf0 / --dim #8b91a3 / --accent #7aa2ff` + derived `--warn #f0a35e`), the 4-size type scale (Display 64/500/1.1, Heading 20/500/1.2, Body 16/400/1.5, Label 14/400/1.4), the 8-pt spacing scale, and `font-variant-numeric: tabular-nums` on the countdown (Pitfall 6). Two `@font-face` rules load Roboto 400/500 from local `src/assets/roboto-{400,500}.woff2` — no CDN. `src/index.html` gained the 56px left rail (`<nav>` with two icon-only `<button>`s carrying `aria-label="Status"` / `aria-label="Edit"`, hand-drawn inline-SVG strokes, hover `title`s, Status `aria-current="page"`) and the centered status view DOM (status word → hero countdown → hairline divider → 3-dot meter + captions). No UI framework / icon package added (lean-deps; `package.json` untouched).
- **Task 2 — render + liveness (`bf32304`):** `src/main.ts` implements `render()` deriving the status word (`s.locked && s.grace_active` → "🌙 LOCKED · grace"; `s.locked` → "🌙 LOCKED"; else "OPEN" + "next lock at {time}"), the hero `renderCountdownOnly()` (HH:MM:SS, clamped at 00:00:00), the 3-dot meter (`tokens_remaining` filled accent of 3 + "{n} of 3 tokens · resets Monday {date}"), the grace caption ("+8 available/used today" / "+8 unavailable (not locked)"), the fail-closed "State unverified" copy on `!state_verified || maximal_lockout`, the advisory "Time unverified" caveat, and the "No signed config yet" empty state on `NotInitialized`. `refresh()` (the single `last` assignment) re-invokes `get_state`; `watch(dataDir, () => void refresh(), { delayMs: 250 })` re-reads on any data-dir change; `setInterval(() => { if (last) renderCountdownOnly(last); }, 1000)` ticks digits only. Added the `data_dir` IPC command (surfaces the absolute watch target) + registered it in `lib.rs`. Narrowed `capabilities/default.json` `fs:scope` off bare `**`.
- **Build green:** `npx tsc --noEmit` exits 0; `npm run build` (tsc && vite build) succeeds and emits both woff2 into `dist/assets` (confirming local bundling, no CDN); `cargo build -p nightguard-control` compiles the new `data_dir` command with zero warnings.

## Task Commits

1. **Task 1: Moonlit Indigo styles + shell DOM + bundled Roboto** — `311be93` (feat)
2. **Task 2: Status render + plugin-fs watch + 1s countdown tick** — `bf32304` (feat)

## Files Created/Modified

- `src/styles.css` (created) — Moonlit Indigo tokens + type scale + 8pt spacing + left rail + countdown/meter layout + 2× `@font-face`.
- `src/assets/roboto-400.woff2`, `src/assets/roboto-500.woff2` (created) — locally-bundled Roboto Latin 400/500 (no CDN).
- `src/index.html` (modified) — 56px aria-labelled left rail (inline SVG) + centered status-view DOM; links styles.css.
- `src/main.ts` (modified) — full render pipeline + countdown-only tick + plugin-fs watch + empty/fail-closed states (StateDto interface retained from plan 01).
- `src-tauri/src/commands.rs` (modified) — added `data_dir` command; removed the now-obsolete `#[allow(dead_code)]` on `AppCtx.data_dir` (now consumed).
- `src-tauri/src/lib.rs` (modified) — registered `data_dir` in `generate_handler!`.
- `src-tauri/capabilities/default.json` (modified) — `fs:scope` narrowed off bare `**`.

## Decisions Made

- **data_dir seam:** chose the tiny `data_dir` IPC command over reading a Tauri config path — `AppCtx.data_dir` already existed and plan-01 explicitly reserved it for "plan-03's fs:scope tightening / the watch seam," so the change is consume-the-reserved-field, not new surface. The command returns a path only (no secret).
- **fs:scope narrowing strategy:** `NIGHTGUARD_DIR` resolves at runtime, so a statically-exact scope is impossible. Narrowed to the conventional `$HOME/.nightguard` and `$APPDATA/nightguard` (plus `/**`) and removed bare `**`. See residual below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] No Roboto woff2 assets existed in-repo**
- **Found during:** Task 1 (the plan lists `src/assets/roboto-{400,500}.woff2` as inputs; neither existed).
- **Issue:** The `@font-face` rules and the "no CDN" mandate require local woff2 files; the repo had no `src/assets/` and no fonts.
- **Fix:** Fetched Roboto Latin 400/500 woff2 once from the fontsource jsdelivr mirror and committed them under `src/assets/` (validated as WOFF2/TrueType, ~22 KB each). They are bundled locally; the running app references them only via the local `@font-face` `url("./assets/...")` — no runtime CDN reference (vite emits them into `dist/assets`, confirmed in the build output). The body `font-family` also carries a `system-ui` fallback stack for safety.
- **Files modified:** src/assets/roboto-400.woff2, src/assets/roboto-500.woff2, src/styles.css
- **Verification:** `npm run build` emits both fonts into `dist/assets`; the no-CDN grep over styles.css/index.html returns none.
- **Committed in:** `311be93`

**2. [Rule 1 - Warning hygiene] Removed obsolete `#[allow(dead_code)]` on `AppCtx.data_dir`**
- **Found during:** Task 2 (adding the `data_dir` command).
- **Issue:** `AppCtx.data_dir` was annotated `#[allow(dead_code)]` (reserved contract surface). The new `data_dir` command now reads it, so the annotation became misleading.
- **Fix:** Removed the annotation and updated the field doc to note it is the watch seam consumed by the `data_dir` command.
- **Files modified:** src-tauri/src/commands.rs
- **Verification:** `cargo build -p nightguard-control` compiles with zero warnings.
- **Committed in:** `bf32304`

**Total deviations:** 2 auto-fixed (1 Rule 3 blocking — fonts; 1 Rule 1 warning hygiene). No signature/contract changes to the four frozen commands; the new `data_dir` command is additive.

## Residual / Documented Trade-off

- **fs:scope vs runtime NIGHTGUARD_DIR:** the watch scope covers the conventional data dirs (`$HOME/.nightguard`, `$APPDATA/nightguard`). If `NIGHTGUARD_DIR` is set to a non-conventional path, `watch()` falls outside scope and the callback won't fire there — `startWatch()` catches this, logs a warning, and degrades gracefully; the load-time `refresh()` + the 1s tick keep the display advisory-live, and any commit/grace action re-reads explicitly (D-09), so correctness of *displayed* state is preserved (it just won't auto-refresh on an out-of-scope external hand-edit until the next user action). This is the least-privilege trade-off the plan sanctions ("scope to the parent of NIGHTGUARD_DIR's expected location and document the residual").

## Checkpoint (Task 3 — human-verify, auto-approved under AUTO_MODE)

The plan's `checkpoint:human-verify` gate asks for a live visual/behavioral check (`npx tauri dev` against a signed fixture: countdown is the jitter-free hero, status word correct, 3-dot meter in accent, and a hand-edit flips the UI to "State unverified" within ~1s). Per the orchestrator's AUTO_MODE directive this is auto-approved. Automated checks run in lieu of the live check:

- `npx tsc --noEmit` — exit 0 (render pipeline type-correct against StateDto).
- `npm run build` (tsc && vite build) — succeeds; both Roboto woff2 emitted into `dist/assets` (local-bundle confirmed, no CDN).
- `cargo build -p nightguard-control` — compiles the new `data_dir` command, zero warnings.
- plugin-fs watch wired: `data_dir` command + `watch(dir, refresh, {delayMs:250})`; `fs:allow-watch`/`fs:allow-unwatch` retained, `fs:scope` narrowed off `**`.
- grep gates: tick body has no `invoke`/status-word/`locked` mutation (T-04-14 clean); watch callback re-invokes `get_state` (T-04-15); status-word + token-caption + verify/time copy literals present.

**The live visual/behavioral verification (jitter, accent rendering, the ~1s hand-edit flip to "State unverified") is DEFERRED to the phase verifier** — it requires a running `tauri dev` against a signed fixture and a human eye, which the automated gate cannot substitute.

## Threat Surface

Plan threat-model mitigations applied:
- **T-04-14** (tick false-unlock): the 1s tick calls only `renderCountdownOnly` (boundary-digit recompute); grep-confirmed it sets no status word and calls no `invoke` — a passed boundary shows 00:00:00 and waits for the watch-driven re-read.
- **T-04-15** (optimistic render after local edit): `render()` derives solely from a freshly invoked `get_state` DTO; `!state_verified || maximal_lockout` → fully-locked "State unverified" copy; `last` is assigned only in `refresh()`.
- **T-04-16** (remote asset injection): Roboto woff2 bundled locally; no `https://`/CDN URL in styles.css or index.html (grep returns none); webview loads no remote content.
- **T-04-17** (over-broad fs:scope): bare `"path": "**"` removed; scope narrowed to the conventional nightguard dirs; only watch/unwatch fs permissions granted.

No security surface beyond the plan's threat_model was introduced (the `data_dir` command returns a path only — no key, no file contents).

## Known Stubs

None for this plan's scope. The Edit view (the second left-rail item) is intentionally inert here — its render + actions land in plan 05; the `rail-edit` button is present and aria-labelled but not yet wired (documented, not a stub blocking UI-01/UI-02/UI-05, which are this plan's requirements and are fully realized).

## Self-Check: PASSED

- FOUND: src/styles.css
- FOUND: src/index.html
- FOUND: src/main.ts
- FOUND: src/assets/roboto-400.woff2
- FOUND: src/assets/roboto-500.woff2
- FOUND: src-tauri/capabilities/default.json (fs:scope narrowed off **)
- FOUND commit: 311be93 (Task 1, feat)
- FOUND commit: bf32304 (Task 2, feat)
- tsc --noEmit exit 0; npm run build green (fonts in dist/assets); cargo build zero warnings

---
*Phase: 04-ui-moonlit-indigo*
*Completed: 2026-06-09*
