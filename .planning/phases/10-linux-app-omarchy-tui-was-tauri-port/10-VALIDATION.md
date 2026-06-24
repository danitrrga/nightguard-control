---
phase: 10
slug: linux-app-omarchy-tui-was-tauri-port
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-24
audited: 2026-06-24
test_count_at_audit: 56
port01_coverage: COVERED
port02_coverage: COVERED
port03_coverage: COVERED
---

# Phase 10 — Validation Strategy

> Nyquist validation contract reconstructed post-phase from artifacts.
> State B entry: no VALIDATION.md existed; reconstructed from 10-01/02/03
> PLAN.md + SUMMARY.md + SECURITY.md + live test run.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 |
| **Config file** | `ngtui/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `cd ngtui && env NIGHTGUARD_STACK_DIR=/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard NIGHTGUARD_DIR=/home/danitrrga/dev/Projects/LifeOS/nightguard .venv/bin/python -m pytest -q` |
| **Full suite command** | same (single test root) |
| **Estimated runtime** | ~0.1 seconds (56 headless unit tests) |

---

## Sampling Rate

- **After every task commit:** Run the quick command above
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** <1 second

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|------|--------|
| 10-01-T1 | 01 | 1 | PORT-02/03 | — | `textual==8.2.7` importable; no system-pip; no `watchfiles` | manual (legitimacy gate) | human checkpoint | — | green (human-verified) |
| 10-01-T2 | 01 | 1 | PORT-02, PORT-03 | T-10-01, T-10-03 | backend.py exposes read_state/sanctioned_config/text/live_verdict/preview_change/tokens_left/commit, all key-less; commit uses exact sudoers argv | unit | `pytest tests/test_port02_commit_argv.py tests/test_port03_no_crypto.py` | ✅ | green |
| 10-01-T3 | 01 | 1 | PORT-02 | T-10-03 | App shell parses; spike confirms inline sudo | automated (parse) + manual (spike) | `pytest tests/test_port01_single_key_bindings.py` (App imports clean) | ✅ | green |
| 10-02-T1 | 02 | 2 | PORT-01 | T-10-07 | colors.toml → Theme role mapping; alacritty fallback; ThemeWatch mtime | unit | `pytest tests/test_theme.py` | ✅ | green |
| 10-02-T2 | 02 | 2 | PORT-01, PORT-02 | T-10-05, T-10-06 | verdict_display / token_meter / ledger_rows pure helpers correct | unit | `pytest tests/test_status.py` | ✅ | green |
| 10-02-T3 | 02 | 2 | PORT-01 | T-10-07 | app.py registers omarchy theme, wires 1s tick, push_screen(StatusScreen) | unit | `pytest tests/test_port01_single_key_bindings.py` (App wiring) | ✅ | green |
| 10-03-T1 | 03 | 3 | PORT-01, PORT-02 | T-10-09 | set_scalar/toggle_bool/list_add/list_remove: format-preserving, round-trip via live yaml_load | unit | `pytest tests/test_lineedit.py` | ✅ | green |
| 10-03-T2 | 03 | 3 | PORT-01, PORT-02, PORT-03 | T-10-02, T-10-11 | preview_line/confirm_copy/result_line exact UI-SPEC strings + roles; action_edit pushes EditScreen | unit | `pytest tests/test_preview.py tests/test_port01_single_key_bindings.py` | ✅ | green |
| 10-03-T3 | 03 | 3 | PORT-01, PORT-02, PORT-03 | T-10-11 | E2E: direction+cost before sudo; inline-sudo commit; 0-token loosen refused; theme repaints | manual (TTY-bound) | human checkpoint (approved live 2026-06-24) | — | green (human-verified) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Requirement Coverage Map

### PORT-01 — Terminal/TUI, omarchy-native, single-key command-driven, live theme

| Sub-requirement | Coverage | Test(s) | Notes |
|-----------------|----------|---------|-------|
| Terminal/TUI (Textual App) | COVERED | `test_nightguard_app_is_textual_app` | NightguardApp subclasses textual.app.App |
| Single-key command-driven (D-03) — e/r/l/q | COVERED | `test_app_bindings_are_single_key` | Asserts all four single-char keys present |
| `e` opens EditScreen | COVERED | `test_action_edit_pushes_edit_screen_not_stub` | Monkeypatches push_screen; asserts EditScreen |
| Live omarchy theme (D-04/D-05) | COVERED (unit) + MANUAL | `test_load_colors_toml_maps_roles`, `test_theme_watch_detects_mtime_change` | Live repaint on desktop switch is TTY-only |
| StatusScreen read-only surface | COVERED | `test_verdict_display_maps_every_state`, `test_token_meter_glyphs_and_caption`, `test_ledger_rows_empty_and_populated`, `test_grace_text_*` | Pure helpers unit-tested |
| Colors from omarchy, no hardcoded hex | COVERED (unit) + MANUAL | `test_load_colors_toml_maps_roles`, `test_falls_back_to_alacritty_when_colors_absent` | CSS $-variables verified via theme load |
| Single-key EditScreen nav (j/k/Enter/Space) | PARTIAL (manual) | 10-03-T3 human checkpoint | Keybinding TTY behavior is TTY-bound |

### PORT-02 — Thin client over Python trust stack; signs via sudo control-CLI only

| Sub-requirement | Coverage | Test(s) | Notes |
|-----------------|----------|---------|-------|
| Imports ngcommon/guard/nightguard_ctl (no vendor) | COVERED | `test_preview_change_uses_live_classify_change`, `test_preview_change_uses_live_quota_decide` | Spy verifies live ctl functions are called |
| preview_change uses signer's classify_change/quota_decide | COVERED | `test_preview_change_uses_live_classify_change`, `test_preview_change_uses_live_quota_decide`, `test_preview_change_identical_text_is_noop` | Full seam test against live stack |
| Diff base is SANCTIONED not live config | COVERED | `test_preview_change_diff_base_is_sanctioned_not_live_config` | Monkeypatches sanctioned_config to sentinel |
| commit() uses exact sudoers argv shape | COVERED | `test_commit_argv_matches_sudoers_shape` | Captures argv; asserts all 6 positions |
| No shell=True in commit | COVERED | `test_commit_uses_no_shell` | Asserts shell not in kwargs |
| Temp file cleaned up (T-10-04) | COVERED | `test_commit_temp_file_is_cleaned_up_after_call` | Checks os.path.exists after call |
| commit() maps returncode+stdout | COVERED | `test_commit_maps_returncode_and_stdout_to_result` | Asserts result dict shape |
| STACK_DIR pinned (CR-02) | COVERED | `test_backend_stackdir.py` (4 tests) | Rejects poisoned path; CTL_SCRIPT under STACK_DIR |
| Anti-impulse preview strings (D-06/D-07) | COVERED | `test_preview.py` (11 tests) | preview_line/confirm_copy/result_line exact strings |
| Format-preserving line edits (no YAML emit) | COVERED | `test_lineedit.py` (11 tests) | Round-trip via live ngcommon.yaml_load; only target field changes |
| Inline-sudo commit via App.suspend() | MANUAL | 10-03-T3 human checkpoint | TTY-bound; cannot be automated headless |

### PORT-03 — TUI never holds HMAC key, never computes HMAC; quota enforced by CLI

| Sub-requirement | Coverage | Test(s) | Notes |
|-----------------|----------|---------|-------|
| No hmac/hashlib import in ngtui source | COVERED | `test_no_hmac_or_hashlib_import_in_ngtui_source` | AST walk of entire ngtui/ package |
| No read_key() call in ngtui source | COVERED | `test_no_read_key_call_in_ngtui_source` | AST walk; detects ng.read_key() too |
| No .hexdigest()/.digest() call in ngtui source | COVERED | `test_no_hexdigest_or_digest_call_in_ngtui_source` | AST walk of all .py files |
| WEEKLY_TOKENS sourced from signer constant | COVERED | `test_backend_reexports_signer_constant`, `test_status_and_edit_use_the_backend_constant` | Object identity check |
| CTL_SCRIPT absolute and under STACK_DIR | COVERED | `test_commit_ctl_script_is_absolute_and_under_stack_dir` | Path.is_absolute() + startswith STACK_DIR |
| Weekly-token quota enforced by CLI (not TUI) | COVERED (display) + MANUAL (enforcement) | `test_confirm_copy_no_tokens_disables_commit_with_monday` (display); 10-03-T3 (CLI enforcement) | Enforcement is the CLI's job; TUI displays the decision |

---

## Test File Index (Post-Audit State)

| # | File | Tests | Type | Requirement(s) |
|---|------|-------|------|----------------|
| 1 | `tests/test_lineedit.py` | 11 | unit | PORT-01, PORT-02, PORT-03 (T-10-09) |
| 2 | `tests/test_preview.py` | 11 | unit | PORT-01, PORT-02, PORT-03 (T-10-11) |
| 3 | `tests/test_status.py` | 6 | unit | PORT-01, PORT-02 (T-10-05/06) |
| 4 | `tests/test_theme.py` | 5 | unit | PORT-01 (T-10-07) |
| 5 | `tests/test_backend_stackdir.py` | 4 | unit | PORT-02 (T-10-03 / CR-02) |
| 6 | `tests/test_weekly_tokens_source.py` | 2 | unit | PORT-03 (WR-03) |
| 7 | `tests/test_port03_no_crypto.py` | 3 | unit | PORT-03 (T-10-01) — **NEW** |
| 8 | `tests/test_port02_commit_argv.py` | 6 | unit | PORT-02/03 (T-10-03/04) — **NEW** |
| 9 | `tests/test_port01_single_key_bindings.py` | 4 | unit | PORT-01 (D-03) — **NEW** |
| 10 | `tests/test_port02_preview_seam.py` | 4 | unit | PORT-02 (T-10-02 / D-07) — **NEW** |
| **Total** | | **56** | | |

---

## Wave 0 Requirements

*Existing infrastructure covered all phase requirements (pytest was installed into the venv in 10-02 as a documented deviation). No Wave 0 stub files needed post-hoc.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Sign-Off |
|----------|-------------|------------|---------|
| sudo password/fingerprint prompt appears inline after App.suspend() | PORT-02 (D-08) | Requires a real TTY + sudo credentials; headless pytest cannot attach to /dev/tty | Approved live 2026-06-24 (operator ran 10-03-T3 walkthrough; spike confirmed A2 in 10-01-T3) |
| Direction + token cost render BEFORE the sudo prompt (anti-impulse, D-06) | PORT-02, PORT-03 | Ordering within an interactive TTY session; requires a real running TUI | Approved live 2026-06-24 (10-03-T3 human checkpoint) |
| Desktop theme change repaints the running TUI (D-05) | PORT-01 | Requires `omarchy-theme-set` and a running Textual app observing the 1s tick | Approved live 2026-06-24 (10-03-T3 human checkpoint; A3 exercise noted in SPIKE-NOTES.md) |
| EditScreen single-key nav (j/k/Enter/Space/c/u/Escape) works in a real terminal | PORT-01 (D-03) | Keybinding TTY behavior requires a real terminal; Textual's headless pilot suppresses key routing | Approved live 2026-06-24 (10-03-T3 walkthrough; operator navigated the EditScreen) |
| 0-token loosen surfaces "available again Monday" and does not silently spend | PORT-03 | Requires real quota state at 3/3 exhausted OR monkeypatching `quota_decide`; the confirm_copy helper is unit-tested (automated); the gate wiring in ConfirmScreen requires a running TUI | Approved live 2026-06-24 (10-03-T3: "Real quota is at 0/3 per STATE.md — a loosen will be REFUSED; confirm the REFUSED (...) available again Monday line renders in $error") |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or manual checkpoint with sign-off
- [x] Sampling continuity: every plan wave has automated tests
- [x] No watch-mode flags
- [x] Feedback latency < 1s (56 headless tests, ~0.1s)
- [x] `nyquist_compliant: true` set in frontmatter
- [x] All 4 Nyquist gaps filled with passing tests (17 new tests, 56 total)

**Approval:** approved 2026-06-24 (Nyquist audit complete)

---

## Audit Trail

| Audit Date | Auditor | Gaps Found | Gaps Filled | Tests Before | Tests After | Status |
|------------|---------|------------|-------------|-------------|------------|--------|
| 2026-06-24 | gsd-nyquist-auditor | 4 | 4 | 39 | 56 | compliant |

### Gaps Audited

| Gap ID | Requirement | Description | Test File | Result |
|--------|-------------|-------------|-----------|--------|
| GAP-01 | PORT-03 / T-10-01 | No test asserting ngtui source never imports hmac/hashlib or calls read_key()/hexdigest() | `test_port03_no_crypto.py` (3 tests) | FILLED |
| GAP-02 | PORT-02/03 / T-10-03/04 | No test capturing the exact sudoers argv shape, no-shell, no stderr-PIPE, temp cleanup | `test_port02_commit_argv.py` (6 tests) | FILLED |
| GAP-03 | PORT-01 / D-03 | No test for BINDINGS single-key contract or that action_edit pushes EditScreen | `test_port01_single_key_bindings.py` (4 tests) | FILLED |
| GAP-04 | PORT-02 / T-10-02/D-07 | No test that preview_change calls live ctl.classify_change/quota_decide (not a stub/vendor) | `test_port02_preview_seam.py` (4 tests) | FILLED |
