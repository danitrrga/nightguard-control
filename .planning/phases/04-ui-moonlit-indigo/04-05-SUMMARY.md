---
phase: 04-ui-moonlit-indigo
plan: 05
subsystem: ui
tags: [tauri, frontend, edit-view, classify, commit, grace, debounce, gating, moonlit-indigo, d-07, d-08, d-09, d-10]

# Dependency graph
requires:
  - phase: 04-ui-moonlit-indigo
    plan: 03
    provides: "Real classify_change (per-field ClassifyDto: fields[]/allowed/reason/costs_token), commit_change (re-read StateDto, D-09), use_grace (re-read StateDto, D-09)"
  - phase: 04-ui-moonlit-indigo
    plan: 04
    provides: "src/styles.css tokens + 56px left rail + render()/refresh()/renderEmpty() loop + frozen StateDto TS interface + status-view DOM"
provides:
  - "Edit view: single --surface per-field curfew editor (curfew.enabled/start/end) with live debounced classify_change feedback (tighten=accent / loosen=warn / noop=silent)"
  - "Commit gating: disable-with-reason at 0 tokens (UI-04), 'Commit (spends 1 token)' loosen label, one-step loosen confirm (D-08), re-render from returned StateDto (D-09)"
  - "'+8 minutes' grace button: enabled IFF locked && grace_available_today (D-10), use_grace -> re-render from re-verified StateDto, non-punitive error surfacing"
  - "read_config IPC command (read-only config-text seam for the edit pair)"
  - "Left-rail view switching (Status default / Edit)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Edit composes new_yaml from the loaded config text via per-field line edits (classifier reads fields by yamlpath, so a line edit is faithful + format-preserving) — never a re-serialization"
    - "every write action (commit_change / use_grace) re-renders ONLY from the returned re-verified StateDto (D-09); no optimistic token decrement or grace flip"
    - "the +8 enable rule lives in render() and sets the real `disabled` attribute (gate), not styling-only; accent .enabled fill applied only when enabled"
    - "loosen confirm (D-08) gated on lastClassify.fields containing a 'loosen'; tighten-only/neutral commits skip the confirm"

key-files:
  created: []
  modified:
    - src/main.ts
    - src/index.html
    - src/styles.css
    - src-tauri/src/commands.rs
    - src-tauri/src/lib.rs

key-decisions:
  - "Added a read-only `read_config` IPC command as the edit seam (Rule 3 — the Edit view cannot build the classify old/new pair without the live config text; the plan's action sanctions 'a small command; document the seam'). Carries no secret; HMAC re-verification stays server-side in get_state/commit_change."
  - "new_yaml is composed by per-field line replacement on the loaded config (setYamlField regex on the indented `enabled:`/`start:`/`end:` lines), not by re-emitting YAML — keeps comments/formatting intact and matches the classifier's yamlpath field reads. Absent field => left untouched (absent != loosen; the server decides)."
  - "The +8 button keeps a static `disabled` attribute in HTML as the safe pre-render default; render() owns the live enable state (locked && grace_available_today) on every refresh."
  - "Used real UI glyphs in feedback copy: middle-dot '·' and em-dash '—' (UI-SPEC typography), matching the exact UI-SPEC strings."

requirements-completed: [UI-03, UI-04, UI-05]

# Metrics
duration: 8min
completed: 2026-06-09
---

# Phase 4 Plan 05: Edit View + Write Actions Summary

**The Edit view completes the vertical slice: a single `--surface` per-field curfew editor that runs `classify_change` debounced per field (live tighten=accent / loosen=warn+"costs 1 token" / noop=silent feedback), disables Commit with the locked "available again Monday" reason when a loosen is pending at 0 tokens (UI-04), confirms once before a loosening commit (D-08), and — like the new "+8 minutes" grace button (enabled only when `locked && grace_available_today`, D-10) — re-renders the Status view purely from the command's returned re-verified StateDto, never an optimistic local mutation (D-09).**

## Performance

- **Duration:** ~8 min
- **Tasks:** 2 auto + 1 checkpoint (human-verify, auto-approved under AUTO_MODE)
- **Files created:** 0
- **Files modified:** 5

## Accomplishments

- **Task 1 — Edit view + gated/confirmed commit (`75c246c`):**
  - Added the read-only `read_config` IPC command (+ registered in `lib.rs`) so the frontend can load the live config text — the classifier's `old` side and the input seed.
  - `src/index.html`: the Edit view as ONE `--surface` panel (`.edit-panel`) with `curfew.enabled` (checkbox), `curfew.start` / `curfew.end` (`<input type=time>`) per-field rows, each with a feedback slot, plus the Commit button (40px hit target). Wired the existing `rail-edit` item to view switching.
  - `src/styles.css`: edit-panel + `.action-btn` (40px) + tighten(accent)/loosen(warn) feedback + amber disabled-reason styles (no second design system; reuses the plan-04 tokens/scale).
  - `src/main.ts`: view switching (`showView`), `read_config` load + input seeding, `composeNewYaml` (per-field line edit), debounced (~250ms) `classify_change` per input, `applyClassify` rendering the exact UI-SPEC strings and gating Commit (disable + "available again Monday" reason at 0-token loosen, "Commit (spends 1 token)" loosen label), and `onCommit` (one-step confirm ONLY on loosen → `commit_change` → re-render from returned StateDto, switch back to Status; server refusals surface inline).
- **Task 2 — "+8 minutes" grace button (`47645d9`):**
  - Enable rule derived in `render()` as `s.locked && s.grace_available_today` (D-10); sets the real `disabled` attribute and the accent `.enabled` fill only when enabled. `renderEmpty()` also disables it.
  - `onGrace()`: `invoke('use_grace')` → re-render the Status view from the returned re-verified StateDto (D-09, `grace_active`/`grace_end`); no optimistic flip. `NtpUnreachable` / `GraceAlreadyUsedToday` surface as an inline amber caveat with the displayed state unchanged.
- **Build green:** `npx tsc --noEmit` exit 0; `npm run build` (tsc && vite build) succeeds; `cargo check -p nightguard-control` finishes with zero warnings (the new `read_config` command compiles).

## Task Commits

1. **Task 1: Edit view — per-field editor + debounced classify + gated/confirmed commit** — `75c246c` (feat)
2. **Task 2: +8 minutes grace button — enable rule + use_grace handler + re-render** — `47645d9` (feat)

## Files Created/Modified

- `src/main.ts` (modified) — ClassifyDto interface; edit-view DOM handles; `read_config` load + seed; `composeNewYaml`/`setYamlField`/`seedInputsFromConfig`; debounced `runClassify`/`applyClassify` (exact feedback strings + Commit gating); `onCommit` (loosen confirm + `commit_change` + D-09 re-render); `showView`; `+8` enable derivation in `render()` + `onGrace` (`use_grace` + D-09 re-render).
- `src/index.html` (modified) — Edit `--surface` panel DOM (per-field inputs + feedback slots + Commit) + the `+8 minutes` button in the status view.
- `src/styles.css` (modified) — `.action-btn` (40px) + `#grace-btn.enabled` accent fill + `#commit-btn.loosen` warn + edit-panel + per-field feedback tighten/loosen + amber `.edit-reason`.
- `src-tauri/src/commands.rs` (modified) — added the read-only `read_config` command.
- `src-tauri/src/lib.rs` (modified) — imported + registered `read_config` in `generate_handler!`.

## Decisions Made

- **`read_config` seam:** the Edit view needs the live config text to build the classify `old`/`new` pair and to seed inputs. No prior command surfaced it (`data_dir` returns only a path). Added a tiny read-only command — the plan's `<action>` explicitly sanctions "a small command; document the seam." No secret crosses the boundary; HMAC re-verification stays server-side.
- **Per-field line edit, not re-serialization:** `new_yaml` is composed by replacing the value on the indented `enabled:`/`start:`/`end:` lines of the loaded config. This preserves comments/formatting (the human-readable config the PowerShell parser also reads) and matches the classifier's yamlpath per-field reads. An absent field is left untouched (absent != loosen).
- **Confirm gating source:** `onCommit` keys the one-step confirm off `lastClassify.fields` containing a `loosen`, so tighten-only/neutral commits proceed without a dialog (D-08).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added a `read_config` IPC command for the edit seam**
- **Found during:** Task 1.
- **Issue:** The Edit view must pass the live config text as `classify_change`'s `oldYaml` and seed the inputs, but no existing command surfaced the config text (only `data_dir` exists, returning a path; reading via plugin-fs would also require widening `fs:scope` for file reads). Without a seam the Edit view cannot classify.
- **Fix:** Added a read-only `read_config` `#[tauri::command]` returning the config text, registered in `lib.rs`. The plan's `<action>` explicitly anticipated this ("reuse the data-dir read seam from plan 04 / a small command; document the seam"). It carries no secret; the authoritative HMAC re-verification remains server-side in `get_state`/`commit_change`.
- **Files modified:** src-tauri/src/commands.rs, src-tauri/src/lib.rs
- **Verification:** `cargo check -p nightguard-control` exits 0, zero warnings.
- **Committed in:** `75c246c`

**Total deviations:** 1 auto-fixed (Rule 3 blocking — the edit seam). No signature changes to the four frozen commands; `read_config` is additive and read-only.

## Checkpoint (Task 3 — human-verify, auto-approved under AUTO_MODE)

The plan's `checkpoint:human-verify` (`gate="blocking"`) asks for a live `npx tauri dev` walkthrough (tighten → free + no confirm; loosen → amber + "Commit (spends 1 token)" + "Spend a weekly token?" confirm + token decrement; 0-token loosen → disabled Commit with "available again Monday"; locked+grace → +8 enabled accent → countdown retargets to grace end; open → +8 disabled "unavailable (not locked)"). Per the orchestrator's AUTO_MODE / `<checkpoint_note>` directive this is auto-approved. Automated checks run in lieu of the live check:

- `npx tsc --noEmit` — exit 0 (edit pipeline + grace handler type-correct against StateDto/ClassifyDto).
- `npm run build` (tsc && vite build) — succeeds; bundle emitted.
- `cargo check -p nightguard-control` — zero warnings (the `read_config` command compiles).
- grep gates: debounced `classify_change` (`setTimeout(..., 250)` wrapping the invoke); exact feedback strings "Tightens curfew · free" / "Loosens curfew · costs 1 token"; disabled-reason substring "available again Monday"; loosen confirm title "Spend a weekly token?"; `invoke<StateDto>('commit_change')` + `last = s; render(s)` (D-09, no local token mutation); `+8` enable conjunction `s.locked && s.grace_available_today` + `graceBtn.disabled = !graceEnabled` (real gate); `invoke<StateDto>('use_grace')` + re-render.

**The live visual/behavioral verification (live feedback timing, the confirm dialog, the token-meter decrement, the +8 countdown retarget, accent rendering) is DEFERRED to the phase verifier** — it requires a running `tauri dev` against a signed fixture with tokens available + a locked-with-grace state, which the automated gate cannot substitute.

## Threat Surface

Plan threat-model mitigations applied (the UI gates are advisory; the plan-03 Rust commands re-enforce every gate — defense in depth):

- **T-04-18** (UI bypasses the 0-token gate): the UI disables Commit at 0 tokens for clarity, but `commit_change` re-checks `decision.allowed` server-side (plan-03), so a forced invoke is still refused inline.
- **T-04-19** (optimistic token/grace mutation): `onCommit`/`onGrace` re-render ONLY from the returned re-verified StateDto (`last = s; render(s)`); grep shows no local token decrement / no pre-result grace flip.
- **T-04-20** (+8 outside an active lock / already used): the UI enables +8 only on `locked && grace_available_today` with the real `disabled` attribute; `use_grace` refuses `NtpUnreachable`/`GraceAlreadyUsedToday` server-side regardless of UI state, surfaced non-punitively.
- **T-04-21** (a loosen slips through unnoticed): one explicit confirm step ("Spend a weekly token?") on loosening commits naming the cost; tighten-only commits are free and unconfirmed.
- **T-04-22** (UI shows success on a rejected commit): commit/grace errors surface inline and the displayed Status state stays the pre-action re-verified DTO; the success path re-renders the returned StateDto.

No security surface beyond the plan's threat_model was introduced. The new `read_config` command returns config text only (already human-readable on disk; no key, no HMAC material).

## Known Stubs

None. All Edit-view actions are wired to the real plan-03 commands (`classify_change` / `commit_change` / `use_grace`) and re-render from re-verified state. The visible field subset is `curfew.enabled` / `curfew.start` / `curfew.end` per Open Q2 (the full table is still classified, so untouched fields read Noop) — an intentional scope choice, not a stub.

## Self-Check: PASSED

- FOUND: src/main.ts (Edit view + grace handler)
- FOUND: src/index.html (Edit panel + +8 button)
- FOUND: src/styles.css (edit-panel + action-btn styles)
- FOUND: src-tauri/src/commands.rs (read_config command)
- FOUND: src-tauri/src/lib.rs (read_config registered)
- FOUND commit: 75c246c (Task 1, feat)
- FOUND commit: 47645d9 (Task 2, feat)
- tsc --noEmit exit 0; npm run build green; cargo check zero warnings
- grep gates: debounced classify_change; exact tighten/loosen strings; "available again Monday"; "Spend a weekly token?"; commit_change/use_grace re-render from returned StateDto; +8 enable conjunction + real disabled attribute

---
*Phase: 04-ui-moonlit-indigo*
*Completed: 2026-06-09*
