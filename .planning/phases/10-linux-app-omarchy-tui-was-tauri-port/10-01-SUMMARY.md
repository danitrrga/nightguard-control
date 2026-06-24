---
phase: 10-linux-app-omarchy-tui-was-tauri-port
plan: 01
subsystem: ui
tags: [textual, tui, python, sudo, trust-stack, hmac, omarchy]

requires:
  - phase: 09-native-blocker (and the LifeOS Python trust stack)
    provides: ngcommon/guard/nightguard_ctl modules + nightguard.sudoers Cmnd_Alias
provides:
  - ngtui/ greenfield Python Textual package inside the product repo
  - backend.py — the single key-less seam to the trust stack (read_state, sanctioned_config/text, live_verdict, preview_change, tokens_left, commit)
  - NightguardApp runnable shell with single-key BINDINGS (e/r/l/q)
  - Wave-0 spike validating inline sudo via App.suspend() + the stdout/stderr capture strategy
affects: [10-02, 10-03, status-screen, edit-screen, theme]

tech-stack:
  added: [textual==8.2.7]
  patterns:
    - "Import-the-stack, never vendor: preview/verdict/quota come from the live nightguard_ctl/guard/ngcommon so the TUI cannot drift from the signer"
    - "Key-less TUI: no read_key, no HMAC; commit only via the sudoers-mandated argv"
    - "Env-overridable stack paths (NIGHTGUARD_STACK_DIR/NIGHTGUARD_DIR) for portability"

key-files:
  created:
    - ngtui/pyproject.toml
    - ngtui/.python-version
    - ngtui/.gitignore
    - ngtui/ngtui/__init__.py
    - ngtui/ngtui/backend.py
    - ngtui/ngtui/app.py
    - ngtui/ngtui/__main__.py
    - ngtui/spike/inline_sudo_spike.py
    - ngtui/SPIKE-NOTES.md
  modified: []

key-decisions:
  - "Pinned the venv to Python 3.14 (matches .python-version) instead of uv's default 3.13"
  - "Added ngtui/.gitignore (.venv/, __pycache__/) — hygiene, keeps the isolated venv untracked"
  - "commit() leaves stderr on the TTY (stdout piped) so the sudo prompt + REFUSED line reach the user (Pitfall 3)"

patterns-established:
  - "backend.py is the ONLY module that touches the trust stack (single seam)"
  - "Per-field edit base is SANCTIONED config, never live config.yaml (Pitfall 5)"

requirements-completed: [PORT-02, PORT-03]

duration: ~20min
completed: 2026-06-24
---

# Phase 10 — Plan 01 Summary

**Greenfield `ngtui/` Textual package with `backend.py` as the single key-less seam to the LifeOS Python trust stack, plus a Wave-0 spike that proved inline sudo via `App.suspend()` works.**

## Performance

- **Duration:** ~20 min (interactive)
- **Completed:** 2026-06-24
- **Tasks:** 3 (1 human-verify checkpoint + 2 auto)
- **Files created:** 9

## Accomplishments
- Isolated uv venv (Python 3.14) with `textual==8.2.7` only — no system pip, `watchfiles` deliberately omitted (stdlib mtime poll chosen). Install legitimacy human-verified.
- `backend.py` imports the live `ngcommon`/`guard`/`nightguard_ctl` (never vendored) and exposes `read_state`, `sanctioned_config`, `sanctioned_text`, `live_verdict`, `preview_change`, `tokens_left`, `commit` — all key-less; commit shells the exact sudoers argv.
- Verified live: backend prints a valid verdict (`outside_curfew`), an integer token count (`2`), and `is_noop=True` for an identical-config preview — no key/HMAC call anywhere.
- `NightguardApp` runnable shell (single-key BINDINGS e/r/l/q, guard-sourced verdict placeholder) + `__main__` entry point.
- Wave-0 spike confirmed (A2): the sudo password/fingerprint prompt appears **inline** after `App.suspend()` and the verify exit code is readable on resume.

## Task Commits

1. **Task 1: venv + Textual install (legitimacy gate)** — no commit (venv on disk; human-verified)
2. **Task 2: ngtui scaffold + backend seam** — `51fdfe5` (feat)
3. **Task 3: app shell + inline-sudo spike** — `41e5496` (feat)

## Files Created/Modified
- `ngtui/pyproject.toml` — package metadata, `textual==8.2.7` dep, `ngtui` entry point
- `ngtui/.python-version` — `3.14`
- `ngtui/.gitignore` — excludes `.venv/`, `__pycache__/`
- `ngtui/ngtui/backend.py` — the single trust-stack seam (key-less)
- `ngtui/ngtui/app.py` — `NightguardApp` shell + BINDINGS
- `ngtui/ngtui/__main__.py` — console entry point
- `ngtui/spike/inline_sudo_spike.py` — Wave-0 suspend+sudo spike
- `ngtui/SPIKE-NOTES.md` — A2 capture strategy + A3 theme-repaint approach (A2 confirmed live)

## Decisions Made
- Recreated the venv pinned to Python 3.14 so the runtime matches `.python-version` (uv defaulted to 3.13).
- Added `ngtui/.gitignore` (minor deviation, hygiene) so the isolated `.venv` never gets tracked.

## Deviations from Plan
Two minor, non-scope deviations: (1) venv re-pinned to 3.14 to match the declared `.python-version`; (2) added `ngtui/.gitignore` for venv hygiene. Neither alters the plan's contract.

## Issues Encountered
None — backend verification and the spike both passed on first run.

## User Setup Required
None for this plan — the author's instance already provides the LifeOS trust stack; paths are env-overridable via `NIGHTGUARD_STACK_DIR`/`NIGHTGUARD_DIR`.

## Next Phase Readiness
- `backend.py` is a proven adapter; Waves 2-3 build screens against it.
- A2 (inline sudo) and the capture strategy are settled; the real `commit()` path in Wave 3 can rely on `App.suspend()`.
- A3 (live theme repaint) approach is recorded and will be exercised in 10-02's `theme.py`.

---
*Phase: 10-linux-app-omarchy-tui-was-tauri-port*
*Completed: 2026-06-24*
