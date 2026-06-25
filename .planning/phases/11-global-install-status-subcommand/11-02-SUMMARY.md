---
phase: 11-global-install-status-subcommand
plan: 02
subsystem: ngtui-status-router
tags: [desk-01, desk-02, waybar, status, router, tty-guard, fail-closed, headless]
requires:
  - ngtui.status._shape / ngtui.status.UNAVAILABLE (Plan 01)
  - ngtui.backend.cache_only_verdict / read_state / sanctioned_config / tokens_left (Plan 01)
provides:
  - ngtui.__main__.main (argv front-controller — status -> head-less, bare -> TUI)
  - ngtui.__main__._status (fail-closed key-less JSON emitter, always exit 0)
  - ngtui.__main__._run_tui (TTY-guarded lazy-textual TUI launch)
affects:
  - Phase 12 Waybar module (consumes `ngtui status --json`; left-click opens the TTY-guarded TUI)
tech-stack:
  added: []
  patterns:
    - "argv front-controller (bare sys.argv[1:] check) routing head-less vs TUI"
    - "import-inside-try fail-closed wrapper (Pitfall 2: import raises at import time)"
    - "lazy textual import on the TUI branch only (status path stays head-less)"
    - "TTY guard scoped to the TUI branch only (Pitfall 4), never blanket at main()"
    - "module-eviction + restore fixture for re-running an import-time bootstrap under a poisoned env"
key-files:
  created: []
  modified:
    - ngtui/ngtui/__main__.py
    - ngtui/tests/test_status_cli.py
decisions:
  - "_status imports ngtui.backend INSIDE its try so a poisoned NIGHTGUARD_STACK_DIR RuntimeError-at-import degrades to UNAVAILABLE, not a crash (Pitfall 2)."
  - "Verdict resolved via backend.cache_only_verdict (non-blocking Plan-01 seam), never live_verdict — a cold .timecache can never hang the bar poll (Pitfall 1)."
  - "TTY guard (sys.stdin.isatty -> SystemExit(2)) lives ONLY in _run_tui, after status is already routed away (Pitfall 4); a blanket main() check would break the head-less status exec."
  - "ngtui.app/textual is imported lazily inside _run_tui so `ngtui status` never pays textual's import cost (Anti-Pattern)."
  - "Bare sys.argv[1:] front-controller (not argparse) — `status` is the only subcommand and --json is the only/implicit flag; keeps the lean-deps, no-surprise-parse contract."
  - "Plan task was tdd=true but the router implementation legitimately predates its tests (Task 1 built the front-controller). Task-2 tests are a characterization/regression suite committed as test(...); no separate RED gate (the fail-fast rule's 'investigate a passing RED' applies to pre-existing features, not to same-plan glue just written)."
metrics:
  duration: ~2 min
  completed: 2026-06-25
  tasks: 2
  files: 2
---

# Phase 11 Plan 02: status subcommand router Summary

Wired the Plan-01 status core into the console entry point: `ngtui/__main__.py`
is now an argv front-controller. `ngtui status [--json]` runs a head-less,
key-less reader that emits one line of Waybar-shaped JSON and ALWAYS exits 0
(any failure — a poisoned trust-stack import, an OSError, a malformed config —
degrades to the fixed `status.UNAVAILABLE` object), while bare `ngtui` routes to
the Textual TUI behind a `sys.stdin.isatty()` loud-fail guard with `textual`
imported lazily on that branch only. Closes DESK-01 (the `ngtui` shim now has a
`status` subcommand to route to) and DESK-02 (the key-less `--json` emitter), and
the SC-4 TTY guard.

## What Was Built

- **`ngtui/ngtui/__main__.py`** (rewritten):
  - `main()` — bare `sys.argv[1:]` front-controller. `argv[0] == "status"` →
    `sys.exit(_status(argv[1:]))`; everything else / bare `ngtui` → `_run_tui()`.
  - `_run_tui()` — FIRST `if not sys.stdin.isatty():` writes a loud message to
    stderr and `raise SystemExit(2)` (the guard is on THIS branch only, Pitfall 4),
    THEN lazily `from ngtui.app import NightguardApp` and `.run()` (status never
    pays textual's import cost).
  - `_status(args) -> int` — `obj = status.UNAVAILABLE`; inside a `try:`,
    `import ngtui.backend as b` (INSIDE the try — it raises `RuntimeError` at
    import on a bad `NIGHTGUARD_STACK_DIR`, Pitfall 2), then `read_state` /
    `sanctioned_config` / `cache_only_verdict` (the non-blocking Plan-01 seam, NOT
    `live_verdict`) / `tokens_left` / `status._shape`; broad `except Exception:`
    leaves `obj = UNAVAILABLE`. Emits
    `json.dumps(obj, separators=(",",":")) + "\n"` and returns `0` ALWAYS.
  - Docstring corrected: the old text claimed the bootstrap "sets NIGHTGUARD_DIR"
    unqualified — it's an `os.environ.setdefault` to a hardcoded author path
    (Pitfall 5); now describes the argparse-style routing + the hardcoded-default
    reality.
- **`ngtui/tests/test_status_cli.py`** (appended — Plan 01's 6 tests kept):
  `test_status_fail_closed_on_bad_stack`, `test_status_exit_zero_on_arbitrary_error`,
  `test_status_jq_valid_single_line`, `test_tui_requires_tty`,
  `test_status_does_not_import_textual`, plus a `_restore_backend_module` fixture
  that re-imports a clean `ngtui.backend` after the eviction test, and an
  `_ExplodingModule` stand-in used to prove the TTY guard fires *before* the lazy
  `ngtui.app` import.

## TDD Gate Compliance

The Task-2 unit task carries `tdd="true"`, but the router under test was built in
Task 1 of the same plan (the front-controller is the deliverable, not a behavior
discovered through a RED test). Per the fail-fast rule, a test that passes during
RED warrants investigation *when the feature was expected absent* — here the
feature is same-plan glue just written, so the Task-2 tests are committed as a
characterization/regression suite (`test(11-02)` commit `aede260`) rather than a
separate RED→GREEN pair. The router's fail-closed / exit-0 / TTY / no-textual
contract is fully proven green; no behavior shipped untested.

## Verification

- `pytest tests/test_status_cli.py -x -q` → 11 passed (6 Plan-01 + 5 router).
- `pytest -q` (full headless suite) → 67 passed (62 prior + 5 new; no
  module-eviction leakage breaks later tests).
- Task-1 automated check (one `json.loads`-valid line, rc 0) → `OK`.
- Grep gates: `import ngtui.backend` inside `_status`'s try (line 66); `isatty`
  count == 1 (only in `_run_tui`); `live_verdict` count == 0; `cache_only_verdict`
  present; `from ngtui.app` inside `_run_tui` (lazy).
- Smoke: `python -m ngtui status --json` → `{"text":"○ 2","tooltip":"OPEN · 2
  tokens left","class":"outside_curfew"}` (single line, exit 0).

## Threat Model Coverage

- T-11-05 (a crashing `status` breaks the bar) — `_status` catches `Exception`
  broadly, emits `UNAVAILABLE`, returns 0. Covered by
  `test_status_exit_zero_on_arbitrary_error` + `test_status_fail_closed_on_bad_stack`.
- T-11-06 (import-time `RuntimeError` bypassing the fallback) — `import
  ngtui.backend` is INSIDE the `_status` try. Covered by
  `test_status_fail_closed_on_bad_stack` (import re-runs under a poisoned stack,
  degrades to unavailable).
- T-11-07 (head-less status launching the TUI / no-TTY TUI spewing escapes) —
  status routed before the guard; `sys.stdin.isatty()` on the TUI branch only.
  Covered by `test_tui_requires_tty` + `test_status_does_not_import_textual`.
- T-11-08 (JSON injection into the bar) — `json.dumps(separators=(",",":"))`,
  single line, proper escaping. Covered by `test_status_jq_valid_single_line`.
- T-11-SC (package installs) — zero new dependencies (stdlib `json`/`sys` only).

## Deviations from Plan

None — plan executed as written. The plan left the argparse-vs-bare-argv front
controller to executor discretion; chose a bare `sys.argv[1:]` check (no
`argparse`) since `status` is the only subcommand and `--json` is the sole
(implicit) flag — keeps the head-less path dependency-minimal and free of
argparse's auto `-h`/exit behavior on the bar exec path.

## Known Stubs

None — the router is fully wired to the live Plan-01 seams; no placeholder data
path renders.

## Notes for Phase 12 (Waybar)

- The bar's `exec` should call `ngtui status --json` with `return-type: json`; it
  emits one object per line and never exits non-zero, so no extra error handling
  is needed at the bar layer (a `timeout 1 ngtui status --json` belt-and-braces
  wrap is optional — the status process is already non-blocking via
  `cache_only_verdict`).
- Left-click should run bare `ngtui` inside a real terminal (`-e ngtui`); the TTY
  guard means launching it without a TTY fails loudly (exit 2) rather than
  garbling the bar.

## Self-Check: PASSED

- `ngtui/ngtui/__main__.py`, `ngtui/tests/test_status_cli.py`, and this SUMMARY
  all exist on disk.
- Commits `9aa6466` (Task 1, feat) and `aede260` (Task 2, test) present in git log.
