---
phase: 10-linux-app-omarchy-tui-was-tauri-port
plan: 02
subsystem: ui
tags: [textual, tui, python, omarchy, theme, status-screen, read-only]

requires:
  - phase: 10-01
    provides: backend.py seam (read_state, sanctioned_config, live_verdict, tokens_left) + NightguardApp shell
provides:
  - theme.py — load_omarchy_theme(colors.toml|alacritty.toml -> Textual Theme) + ThemeWatch mtime detector
  - widgets/status.py — StatusScreen + pure helpers verdict_display / token_meter / ledger_rows
  - app.tcss — $-variable role styling bound to the live omarchy theme
  - app.py wired: omarchy theme on mount + 1s tick (countdown-only refresh + theme repaint)
affects: [10-03, edit-screen]

tech-stack:
  added: []
  patterns:
    - "Pure display helpers separated from Textual widgets so the load-bearing read-surface logic unit-tests headless (no App, no TTY)"
    - "omarchy-native theming: no fixed brand hex; colours come from the live desktop colors.toml via tomllib -> Theme, repainted on an mtime poll"
    - "Countdown is the only 1s-tick-refreshed cell; the status word/meter never re-render on tick (anti-flicker)"

key-files:
  created:
    - ngtui/ngtui/theme.py
    - ngtui/ngtui/widgets/__init__.py
    - ngtui/ngtui/widgets/status.py
    - ngtui/ngtui/app.tcss
    - ngtui/tests/test_theme.py
    - ngtui/tests/test_status.py
    - ngtui/tests/conftest.py
  modified:
    - ngtui/ngtui/app.py
    - ngtui/pyproject.toml

key-decisions:
  - "Installed pytest into the ngtui venv (uv pip --python ngtui/.venv) — the venv shipped with textual only; added pytest pythonpath/testpaths to pyproject so headless unit tests resolve the in-tree package without an editable install"
  - "action_refresh re-composes StatusScreen rather than mutating cells in place — guarantees every value is re-read from the guard/state (no optimistic partial update)"
  - "alacritty fallback reuses the colors.toml role-mapper (single source of truth for the role table) and borrows normal.blue as accent (== omarchy accent/color4 on this box)"

patterns-established:
  - "Verdict/token/ledger rendering is pure-function-first; widgets are thin compositions over those helpers"
  - "Theme load failure degrades to Textual's default theme rather than crashing (T-10-07, cosmetic)"

requirements-completed: [PORT-01, PORT-02]

duration: ~20min
completed: 2026-06-24
---

# Phase 10 — Plan 02 Summary

**The read-only StatusScreen (lock status / countdown / token meter / grace / hmacs / ledger) sourced entirely from the guard verdict + signed state, painted in live omarchy desktop colours that repaint the running TUI when the desktop theme changes.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-06-24
- **Tasks:** 3 (all autonomous, TDD-style)
- **Files created:** 7 · **modified:** 2
- **Tests:** 6 passing headless (3 theme + 3 status)

## Accomplishments

- **`theme.py`** — `load_omarchy_theme(path=None)` parses the live `colors.toml` into a Textual `Theme` named `"omarchy"` (accent→primary/accent, background, foreground, color0→surface, color1→error, color2→success, color3→warning); falls back to `alacritty.toml` (`[colors.primary]`/`[colors.normal]`) when `colors.toml` is absent (Pitfall 6). `ThemeWatch` is a stdlib mtime poll on the omarchy `colors.toml` that fires `changed()` once per desktop-theme swap. Pure module — no App import — so it tests headless.
- **`widgets/status.py`** — three pure helpers carry the load-bearing display logic: `verdict_display` (each verdict → glyph + word + colour-role + caption; unknown/tamper/offline fail closed to `● LOCKED`/error — never optimistic OPEN, T-10-05), `token_meter` (filled `●` / hollow `○` + `N of 3 left · resets Mon YYYY-MM-DD`), `ledger_rows` (`{ntp_timestamp, fields}` → dated rows, or `no audit entries yet`). `StatusScreen` composes them into a hero band (`border: round $primary`), a tick-only countdown cell, tokens/grace rows, a truncated-hmac integrity panel, a scrollable ledger, an advisory caption, and a full-screen not-initialized state.
- **`app.tcss`** — colour expressed only through `$`-variable roles bound to the omarchy theme; accent reserved to the hero border / countdown tint / grace word per the UI-SPEC reserved list. No hardcoded hex anywhere.
- **`app.py`** — registers the omarchy theme on mount, shows `StatusScreen` as home, runs a single 1s interval that refreshes **only** the countdown and polls `ThemeWatch` (a detected swap re-registers the same-named theme and reassigns `App.theme` to repaint — RESEARCH Pattern 4, D-05). `action_refresh` re-reads state with no optimism; `action_ledger` toggles the ledger; `action_edit` stays a stub for 10-03.
- **Verified live headless** via Textual's `run_test()` pilot: `app.theme == "omarchy"`, `StatusScreen` mounts, the CSS `$variables` resolve against the registered theme, and the countdown refresh + ledger toggle run without error.

## Task Commits

1. **Task 1: theme.py + change detector** — `2db7369` (feat)
2. **Task 2: status.py helpers + StatusScreen + app.tcss** — `dcd3e4f` (feat)
3. **Task 3: wire StatusScreen + theme + 1s tick into app.py** — `3206700` (feat)

## Files Created/Modified

- `ngtui/ngtui/theme.py` — colors.toml/alacritty.toml → Textual Theme + `ThemeWatch`
- `ngtui/ngtui/widgets/__init__.py` — package marker
- `ngtui/ngtui/widgets/status.py` — StatusScreen + pure verdict/token/ledger helpers
- `ngtui/ngtui/app.tcss` — `$`-variable role styling (accent reserved list)
- `ngtui/tests/test_theme.py` — role mapping, alacritty fallback, mtime detection
- `ngtui/tests/test_status.py` — verdict/token/ledger helper behaviours
- `ngtui/tests/conftest.py` — sets the stack env vars before collection
- `ngtui/ngtui/app.py` — CSS_PATH, theme registration, 1s tick, refresh/ledger actions
- `ngtui/pyproject.toml` — pytest `pythonpath`/`testpaths`

## Decisions Made

- Installed `pytest` into the ngtui venv (it shipped with `textual` only) and declared `pythonpath`/`testpaths` in `pyproject.toml` so the headless helper tests resolve the in-tree package without an editable install.
- `action_refresh` re-composes the whole `StatusScreen` (re-reads the guard/state) rather than mutating individual cells — eliminates any chance of an optimistic stale value surviving a refresh.
- The alacritty fallback reuses the same role-mapper as `colors.toml` (one source of truth for the role table) and borrows `normal.blue` as the accent (== omarchy `accent`/`color4` on this box).

## Deviations from Plan

- **[Rule 3 — Blocking] pytest not in the venv.** The plan's `<environment>` anticipated this; installed `pytest==9.1.1` into `ngtui/.venv` via `uv pip install --python ngtui/.venv` (never system pip / `--break-system-packages`) and added pytest config to `pyproject.toml` so `cd ngtui && .venv/bin/python -m pytest` works as the plan's verify commands expect. No package-legitimacy concern (pytest is the canonical test runner, sanctioned in the plan environment).

No other deviations — the StatusScreen contract, theme role map, and tick semantics were implemented exactly as specified.

## Issues Encountered

- Parsing `app.tcss` in isolation raises `UnresolvedVariableError` for `$background` — expected, because the `$variables` only exist once a `Theme` is registered on a running App. Validated correctly by mounting the app through Textual's headless pilot (which registers the omarchy theme first); CSS then resolves cleanly.

## Known Stubs

- `action_edit` intentionally `self.bell()`s — the EditScreen (anti-impulse preview + inline-sudo commit) is the explicit deliverable of plan 10-03. Documented in the plan; not a blocker for this read-only surface.

## User Setup Required

None — the author's instance already provides the LifeOS trust stack; the status surface is read-only and key-less.

## Next Phase Readiness

- The read surface and live theming are in place; 10-03 builds the `EditScreen` (per-field line-edit + classifier-driven preview + `App.suspend()` commit) on the same `backend` seam and theme.
- `action_edit` is the single wired hook awaiting the real EditScreen push.
- The 1s tick and theme-repaint mechanism are proven headless; the interactive omarchy walkthrough (live theme switch repaints the running TUI) is a human verification step.

## Self-Check: PASSED

All 9 declared files exist on disk; all 3 task commits (`2db7369`, `dcd3e4f`, `3206700`) present in the git log. 6/6 headless tests pass.

---
*Phase: 10-linux-app-omarchy-tui-was-tauri-port*
*Completed: 2026-06-24*
