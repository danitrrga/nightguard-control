---
phase: 11-global-install-status-subcommand
verified: 2026-06-25T18:30:00Z
status: passed
score: 5/5
overrides_applied: 0
re_verification: false
---

# Phase 11: Global Install + Status Subcommand — Verification Report

**Phase Goal:** `ngtui` becomes a globally-installed command that resolves the LifeOS trust stack from a bare login shell, and exposes a new key-less `ngtui status --json` subcommand that emits Waybar-shaped JSON — the keystone substrate every later phase stands on.
**Verified:** 2026-06-25T18:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `uv tool install --python 3.14 .` puts a real `ngtui` on `PATH`; installed shim launches TUI from clean login shell with no `NIGHTGUARD_*` dev-shell env (SC-1) | VERIFIED (human-approved) | User-approved Plan 03 Task 1 checkpoint: shim at `~/.local/bin/ngtui` confirmed on live box; `backend.py` hardcoded `_DEFAULT_STACK_DIR` resolves the LifeOS stack; `pyproject.toml` entry `ngtui = "ngtui.__main__:main"` is the shim source |
| 2 | `ngtui status --json` prints a single-line, jq-valid Waybar object `{text,tooltip,class}` sourced key-lessly — never reads `.guardkey`, never computes HMAC, never calls sudo (SC-2) | VERIFIED | 11 tests in `test_status_cli.py` all PASS; behavioral spot-check emits `{"text":"○ 2","tooltip":"OPEN · 2 tokens left","class":"outside_curfew"}` (single line, rc=0); `test_port03_no_crypto.py` AST guard (3 PASS) confirms no HMAC/hashlib/hexdigest in `status.py` |
| 3 | Status reader fails closed: any stack/read error emits `{"text":"○ —","class":"unavailable"}` and exits 0 (SC-3) | VERIFIED | `test_status_fail_closed_on_bad_stack`: poisoned `NIGHTGUARD_STACK_DIR` causes in-try import to raise `RuntimeError`, degrades to `unavailable` + exit 0; `test_status_exit_zero_on_arbitrary_error`: any `read_state` raise degrades to `unavailable` + exit 0; `UNAVAILABLE = {"text": "○ —", "class": "unavailable"}` (status.py:55) matches the exact contract |
| 4 | Real loosen-with-token commit succeeds end-to-end from installed `ngtui` (inline-sudo PTY survives); bare `ngtui` with no TTY fails loudly (SC-4) | VERIFIED (human-approved + automated) | Live commit: user-approved Plan 03 Task 2 checkpoint — inline `sudo` prompt appeared in terminal, commit landed with token decremented by 1, guard did not revert; TTY guard: `test_tui_requires_tty` confirms `_run_tui()` raises `SystemExit(code=2)` when `sys.stdin.isatty()` is False |
| 5 | `guard.json` + sanctioned config are user-readable from isolated-venv process; `_DEFAULT_STACK_DIR` resolves from a clean login shell (SC-5) | VERIFIED (human-approved) | User-approved Plan 03 Task 1 checkpoint: `guard.json` and `config.sanctioned.yaml` confirmed `root:root 0644` (readable); `.guardkey` confirmed `root:root 0600` (Permission denied); `_DEFAULT_STACK_DIR = "/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard"` hardcoded in `backend.py:29` |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `ngtui/ngtui/status.py` | Pure Waybar `{text,tooltip,class}` builder + `_VERDICT_CLASS` + `UNAVAILABLE` + `_shape` | VERIFIED | 88 lines; defines `_VERDICT_CLASS` (5-verdict dict), `UNAVAILABLE = {"text": "○ —", "class": "unavailable"}`, `_shape(verdict, tokens_left, state) -> dict`; stdlib-only at module top (no textual, no top-level backend import) |
| `ngtui/ngtui/backend.py` | `cache_only_verdict(cfg, state)` seam neutralizing guard network fall-through | VERIFIED | 203 lines; `cache_only_verdict` at line 109 swaps `guard._sntp`/`guard._http_time` for instant-raising stubs, restores in `finally`; cold cache resolves to `offline_blocked` in <0.2s (proven by `test_status_no_blocking_ntp`) |
| `ngtui/tests/test_status_cli.py` | 11 headless tests covering status builder + router | VERIFIED | 275 lines; 11 tests all PASS: `test_status_json_shape`, `test_verdict_class_map`, `test_unavailable_object`, `test_empty_data_is_locked_not_unavailable`, `test_status_no_blocking_ntp`, `test_status_never_reads_key`, `test_status_fail_closed_on_bad_stack`, `test_status_exit_zero_on_arbitrary_error`, `test_status_jq_valid_single_line`, `test_tui_requires_tty`, `test_status_does_not_import_textual` |
| `ngtui/tests/conftest.py` | `ng_data_dir` + `read_key_explodes` fixtures; original `setdefault` bootstrap retained | VERIFIED | Has `os.environ.setdefault` bootstrap (lines 13-18); adds `ng_data_dir` (line 109), `ng_data_dir_outside` (line 123), `ng_data_dir_empty` (line 131), `read_key_explodes` (line 144) |
| `ngtui/ngtui/__main__.py` | `main`/`_run_tui`/`_status` argv front-controller | VERIFIED | 81 lines; `main()` routes `status` argv to `_status()`, bare invocation to `_run_tui()`; `import ngtui.backend` inside `_status`'s try-block (line 66); `isatty()` count = 1 (only in `_run_tui`); lazy `from ngtui.app import NightguardApp` inside `_run_tui` (line 45); `cache_only_verdict` used (not `live_verdict`) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ngtui/ngtui/status.py` | 5 backend verdict strings | `_VERDICT_CLASS` dict + `dict.get(verdict, "locked")` fail-closed | VERIFIED | `_VERDICT_CLASS` maps all 5 verdict strings; `_verdict_class()` uses `.get(verdict, "locked")`; `test_verdict_class_map` confirms unknown `"???"` → `"locked"` |
| `ngtui/ngtui/backend.py::cache_only_verdict` | `guard._sntp` / `guard._http_time` | saves originals, swaps in `_no_network` instant-raisers, restores in `finally` | VERIFIED | Lines 129-142 of backend.py; `test_status_no_blocking_ntp` confirms cold cache resolves in <0.2s; LifeOS `guard.py` is never edited |
| `ngtui/ngtui/__main__.py::_status` | `ngtui.status._shape` / `ngtui.backend.cache_only_verdict` | `import ngtui.backend as b` INSIDE `try` block (Pitfall 2); `status._shape` called after verdict resolve | VERIFIED | Line 66: `import ngtui.backend as b` inside try; line 70: `b.cache_only_verdict(cfg, state)`; line 72: `status._shape(verdict, tokens, state)`; `test_status_fail_closed_on_bad_stack` confirms import-time RuntimeError degrades to unavailable |
| `ngtui/ngtui/__main__.py::_run_tui` | `sys.stdin.isatty()` | Guard on TUI branch ONLY, before lazy textual import | VERIFIED | Line 42: `if not sys.stdin.isatty():`; grep confirms isatty count = 1; `test_tui_requires_tty` confirms `SystemExit(2)` fires before ngtui.app is imported (ExplodingModule guard) |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ngtui/ngtui/__main__.py::_status` | `obj` (the emitted JSON dict) | `backend.read_state()` → state; `backend.sanctioned_config()` → cfg; `backend.cache_only_verdict(cfg, state)` → verdict; `backend.tokens_left()` → tokens; `status._shape(verdict, tokens, state)` → obj | Yes — behavioral spot-check confirms real verdict `"outside_curfew"` and real token count `2` in live output | FLOWING |
| `ngtui/ngtui/status.py::_shape` | `WEEKLY_TOKENS` for token clamp | Deferred local `from ngtui.backend import WEEKLY_TOKENS` inside `_shape()` (line 78) | Yes — sources signer constant via backend, never a hardcoded literal `3` | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `_status(['--json'])` produces single-line jq-valid JSON, exits 0 | `python -c "...cli._status(['--json'])..."` | `{"text":"○ 2","tooltip":"OPEN · 2 tokens left","class":"outside_curfew"}` (rc=0, one `\n`) | PASS |

---

### Probe Execution

Step 7c: No conventional probe scripts found (`scripts/*/tests/probe-*.sh` absent); no probe commands declared in PLAN files. SKIPPED — not applicable to this phase (headless unit-test-validated).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DESK-01 | Plans 11-02, 11-03 | `uv tool install` exposes global `ngtui` command resolving LifeOS trust stack from clean login shell | SATISFIED | SC-1 human-verified PASS (Plan 03 Task 1); `pyproject.toml` entry point `ngtui = "ngtui.__main__:main"` in place; SC-4 live commit human-verified (Plan 03 Task 2) |
| DESK-02 | Plans 11-01, 11-02, 11-03 | Key-less `ngtui status --json` subcommand emitting Waybar JSON | SATISFIED | SC-2 + SC-3 verified by 11 automated tests (all PASS); behavioral spot-check PASS; no `read_key`/HMAC confirmed by `test_port03_no_crypto.py` + `test_status_never_reads_key` |

No orphaned requirements: REQUIREMENTS.md traceability table maps only DESK-01 and DESK-02 to Phase 11; both are satisfied.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `ngtui/ngtui/__main__.py` | 73-77 | `sys.stdout.write()` outside `except Exception` — a `BrokenPipeError` on pipe-close (Waybar restart/kill mid-poll) escapes uncaught; could produce traceback + non-zero exit (WR-03 from code review) | WARNING | Does NOT block the phase goal. SC-3's "any stack/read error" contract is met; this is a write-path edge case not covered by SC-3. The Waybar poll restart case is the only trigger. Recommended fix: wrap the write in `try: ... except (BrokenPipeError, OSError): pass`. |
| `ngtui/ngtui/__main__.py` | 42 | `sys.stdin.isatty()` only — stdout pipe case (`ngtui \| cat`) not caught (WR-01 from code review) | WARNING | The must-have "bare `ngtui` with no TTY fails loudly" maps to the headless/Waybar exec case (stdin has no TTY), which IS caught. The stdout-only-pipe case is an edge case not specified in SC-4. |
| `ngtui/ngtui/status.py` | 55 | `UNAVAILABLE` uses `"○ —"` (open/unlocked glyph) same as `outside_curfew` label — visually optimistic at a glance (WR-02 from code review) | WARNING | The glyph is specified exactly in every plan's artifact definition; tests assert this value. The fix (use filled circle `●`) would require updating tests. Not a goal failure — the `class` field (`"unavailable"`) carries the Waybar styling signal. |

No `TBD`, `FIXME`, or `XXX` markers found in any phase-modified file.

---

### Human Verification Required

No items pending human verification. All packaging-level criteria (SC-1, SC-4 live commit, SC-5) were confirmed by the user-approved blocking-human checkpoint in Plan 11-03 before this verification report was generated. The Plan 03 SUMMARY documents the user reply "approved" for both Task 1 (install + clean-env + readability) and Task 2 (live token-spending commit).

---

### Gaps Summary

No gaps. All 5 ROADMAP success criteria are verified — SC-2 and SC-3 by 11 automated unit tests (all passing; full suite 67 passed), SC-1, SC-4 (live commit), and SC-5 by user-approved human checkpoint. DESK-01 and DESK-02 are both satisfied.

Three code review warnings (WR-01, WR-02, WR-03) were found in the code review report (11-REVIEW.md, `status: issues_found`). None is a blocker for the phase goal:
- WR-03 (BrokenPipeError on write) is the most actionable and should be fixed before Phase 12 ships the Waybar module that polls `ngtui status --json` continuously.
- WR-01 and WR-02 are cosmetic/edge-case robustness issues.

These are carry-forward quality items, not phase-blocking gaps.

---

_Verified: 2026-06-25T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
