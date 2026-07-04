---
phase: 12-launcher-waybar-presence
plan: 02
subsystem: ngtui-backend
tags: [waybar, signal, commit, bar-04, d-11, tdd]
requires:
  - "ngtui/ngtui/backend.py commit() (sudoers argv seam, Phase 10/11)"
provides:
  - "backend.commit() success-only SIGRTMIN+11 Waybar refresh (BAR-04)"
affects:
  - "custom/nightguard Waybar module (Plan 04, declares signal: 11)"
tech-stack:
  added: []
  patterns:
    - "success-only fire-and-forget subprocess signal (check=False + swallow-all try/except)"
    - "result dict built independently of the signal so the push can never perturb the outcome"
key-files:
  created:
    - "ngtui/tests/test_backend_signal.py"
  modified:
    - "ngtui/ngtui/backend.py"
decisions:
  - "D-11: post-commit Waybar refresh fires ONLY on returncode==0, errors fully swallowed, never alters the commit result or exit code"
metrics:
  duration: ~4 min
  completed: 2026-07-04
  tasks: 2
  files: 2
requirements: [BAR-04]
---

# Phase 12 Plan 02: Instant Post-Commit Waybar Refresh Summary

Wired a success-only, non-perturbing `pkill -RTMIN+11 waybar` push into
`backend.commit()` so the bar reflects a token spend the instant it happens
(not on the next 30s poll) — without the signal ever faking or corrupting the
anti-impulse commit outcome. TDD: the failing contract test landed first.

## What Was Built

- **BAR-04 contract test** (`ngtui/tests/test_backend_signal.py`, 4 tests): the
  mock branches on `argv[0]` (`sudo` = commit, `pkill` = signal) and asserts
  (A) success fires `pkill -RTMIN+11 waybar` exactly once, (B) a non-zero commit
  fires NO signal and returns the real `{returncode: 1}`, (C) a raising pkill is
  swallowed and the commit result is unchanged, (D) the result dict stays exactly
  `{returncode, stdout}` with stdout stripped. Proven RED before implementation.
- **Success-only refresh signal** in `commit()`: after `proc = subprocess.run(...)`
  returns, `if proc.returncode == 0` it runs `pkill -RTMIN+11 waybar`
  (`stdout/stderr=DEVNULL`, `check=False`) inside a bare `try/except Exception: pass`.
  The returned dict is built independently below, so the signal can neither flip
  the bar on a refused commit nor propagate into / alter the commit result. Uses
  the literal `-RTMIN+11` (SIGRTMIN+11 confirmed free; live config uses 7/8/9/10).
  The sudo call's stderr stays uncaptured (TTY prompt) — untouched.

## Verification

- `uv run pytest tests/test_backend_signal.py -x -q` → 4 passed (GREEN).
- `uv run pytest tests/test_port02_commit_argv.py -x -q` → 6 passed (commit
  argv/return contract unchanged).
- `grep -q 'RTMIN+11' ngtui/ngtui/backend.py` → present; the pkill call is guarded
  by `proc.returncode == 0` and wrapped in try/except.
- Full ngtui suite: `uv run pytest -q` → **71 passed** (67 D-10 baseline + 4 new;
  baseline not regressed).

## Threat Mitigations Applied

| Threat ID | Disposition | How |
|-----------|-------------|-----|
| T-12-02 (Tampering — signal perturbs/fakes commit) | mitigated | Fire only on `proc.returncode == 0`; result dict built independently of the signal — unit-tested (Test B/D). A refused commit never flips the bar. |
| T-12-03 (DoS — pkill of absent waybar raises into commit) | mitigated | `check=False` + `except Exception: pass` — best-effort, never propagates (Test C). |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- FOUND: ngtui/tests/test_backend_signal.py
- FOUND: ngtui/ngtui/backend.py (contains `RTMIN+11`)
- FOUND commit 9b7b123 (test RED)
- FOUND commit a73b9ec (feat GREEN)
