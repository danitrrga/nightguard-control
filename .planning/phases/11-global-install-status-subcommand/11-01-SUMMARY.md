---
phase: 11-global-install-status-subcommand
plan: 01
subsystem: ngtui-status-core
tags: [desk-02, waybar, status, cache-only, fail-closed, headless, tdd]
requires:
  - ngtui/ngtui/backend.py (live_verdict, tokens_left, WEEKLY_TOKENS, guard/ng/ctl seams)
  - LifeOS guard.curfew_verdict / true_unix override seam (read-only)
provides:
  - ngtui.status._shape (pure Waybar {text,tooltip,class} builder)
  - ngtui.status._VERDICT_CLASS (5-verdict map, fail-closed to "locked")
  - ngtui.status.UNAVAILABLE (the except-branch object Plan 02 emits)
  - ngtui.backend.cache_only_verdict (non-blocking verdict seam)
affects:
  - Plan 11-02 (the `ngtui status --json` __main__ router consumes these)
tech-stack:
  added: []
  patterns:
    - "pure-helper-first read surface (mirrors Phase 10 verdict_display/token_meter)"
    - "deferred local import of WEEKLY_TOKENS to keep module top dependency-free"
    - "swap-and-restore neutralization of guard network seams in a finally"
key-files:
  created:
    - ngtui/ngtui/status.py
    - ngtui/tests/test_status_cli.py
  modified:
    - ngtui/ngtui/backend.py
    - ngtui/tests/conftest.py
decisions:
  - "_VERDICT_CLASS maps each verdict to a class equal to its own name; dict.get(verdict,'locked') fails closed on unknown (never 'unavailable', never 'outside_curfew')."
  - "Empty/uninitialized data dir renders 'locked' (Pitfall 3): backend.live_verdict({},{}) -> 'locked' with a warm/override time; 'unavailable' is reserved for Plan 02's import/read except branch."
  - "cache_only_verdict neutralizes guard._sntp/_http_time (instant-raise) only for the call; a cold cache falls through to 'offline_blocked' in <0.2s instead of a ~4s 2s+2s timeout block. The LifeOS guard.py is never edited; stubs restored in finally so decide() is unaffected."
  - "Token clamp sourced from backend.WEEKLY_TOKENS via a deferred local import — never a literal 3 — so status.py top stays textual/backend-free."
metrics:
  duration: ~43 min
  completed: 2026-06-25
  tasks: 2
  files: 4
---

# Phase 11 Plan 01: Key-less Status Core Summary

Built and headless-unit-tested the pure core of `ngtui status --json`: a stdlib-only
`status.py` that maps a guard verdict + remaining-token count into a Waybar-shaped
`{text,tooltip,class}` object (fail-closed to `locked` on any unknown verdict), plus a
`backend.cache_only_verdict()` seam that resolves the verdict without ever issuing a
synchronous SNTP/HTTP query — so a cold time cache can never hang the bar poll.

## What Was Built

- **`ngtui/ngtui/status.py`** (new, pure, stdlib-only at module top):
  - `_VERDICT_CLASS` — the 5 guard verdict strings each mapped to a CSS-safe class equal
    to its own name; `dict.get(verdict, "locked")` fails closed (unknown → `locked`).
  - `UNAVAILABLE = {"text": "○ —", "class": "unavailable"}` — the single object Plan 02
    emits from its import/read except branch (distinct from any verdict).
  - `_shape(verdict, tokens_left, state) -> {text,tooltip,class}` — `class` from the
    fail-closed map; `text` = glyph + clamped token count (clamp via
    `max(0, min(WEEKLY_TOKENS, tokens_left))`, `WEEKLY_TOKENS` deferred-imported from the
    signer, never a literal `3`); `tooltip` = verdict word + "N token(s) left".
- **`ngtui/ngtui/backend.py`** — added `cache_only_verdict(cfg, state)`: swaps
  `guard._sntp`/`guard._http_time` for instant-raising stubs for the call's duration
  (restored in `finally`) so a cold `true_unix()` falls straight through to
  `(None, "offline")` → `offline_blocked` instead of the ~4s network block. The LifeOS
  `guard.py` trust stack is untouched.
- **`ngtui/tests/conftest.py`** — appended (kept the original `os.environ.setdefault`
  bootstrap): `ng_data_dir` / `ng_data_dir_outside` / `ng_data_dir_empty` fixtures
  (crafted `guard.json` + `config.sanctioned.yaml`, trust-stack `STATE`/`SANCTIONED`/
  `CONFIG`/`TIMECACHE` re-pointed, deterministic verdict via the
  `NIGHTGUARD_TEST_NTP_OVERRIDE` seam) + `read_key_explodes` (makes any `read_key` raise).
- **`ngtui/tests/test_status_cli.py`** (new) — 6 headless tests:
  `test_status_json_shape`, `test_verdict_class_map`, `test_unavailable_object`,
  `test_empty_data_is_locked_not_unavailable`, `test_status_no_blocking_ntp`,
  `test_status_never_reads_key`.

## TDD Gate Compliance

- RED gate: `test(11-01)` commit `53ed84b` — the 6 tests fail at import (`ngtui.status`
  and `backend.cache_only_verdict` absent). Verified RED before implementing.
- GREEN gate: `feat(11-01)` commit `524941b` — all 6 pass; the full headless suite is
  62 passed (56 prior + 6 new); `test_port03_no_crypto.py` stays green (status.py adds no
  `read_key`/`hmac`/`hashlib`/`hexdigest`).
- No REFACTOR commit needed (implementation landed clean).

## Verification

- `pytest tests/test_status_cli.py -x -q` → 6 passed.
- `pytest tests/test_port03_no_crypto.py -x -q` → 3 passed (no crypto introduced).
- `pytest -q` (full headless suite) → 62 passed.
- Grep gates: `status.py` has no `import textual` and no top-level `from ngtui import
  backend`; defines `_VERDICT_CLASS`, `UNAVAILABLE`, `_shape`; `backend.py` defines
  `cache_only_verdict`.

## Threat Model Coverage

- T-11-02 (status becomes a curfew lever) — `status.py` is pure read-shaping, no commit
  path, no key. Covered by `test_status_never_reads_key` + `test_port03_no_crypto.py`.
- T-11-03 (JSON injection into the bar) — object is a flat str-keyed dict;
  `json.dumps(separators=(",",":"))` is single-line + round-trips. Covered by
  `test_status_json_shape` / `test_unavailable_object`.
- T-11-04 (DoS-by-poll on a cold NTP cache) — `cache_only_verdict` suppresses the
  synchronous network query; verdict resolves in <0.2s to the fail-closed
  `offline_blocked`. Covered by `test_status_no_blocking_ntp`.
- T-11-SC (package installs) — zero new dependencies (stdlib `json` only).

## Deviations from Plan

None — plan executed as written. The plan left glyph/word/tooltip copy to executor
discretion within the Waybar contract; chosen labels: `● LOCKED / ◐ GRACE / ○ OPEN /
● TAMPER / ● OFFLINE`, text `"<glyph> <tokens_left>"`, tooltip `"<WORD> · N token(s) left"`.

## Known Stubs

None — `_shape` accepts `state` for forward-compatibility (a future grace countdown in the
tooltip) but the current contract is fully wired; no placeholder/empty data path renders.

## Notes for Plan 02

- The `__main__` router resolves the verdict via `backend.cache_only_verdict(cfg, state)`
  (NOT `live_verdict`) to stay non-blocking, then `_shape` + `json.dumps`.
- Emit `status.UNAVAILABLE` ONLY from the except branch (trust-stack import/read failed) —
  empty data is already `locked` via the normal path, do not conflate.

## Self-Check: PASSED

- status.py, test_status_cli.py, 11-01-SUMMARY.md all exist.
- Commits 53ed84b (RED) and 524941b (GREEN) present in git log.
