---
phase: 10-linux-app-omarchy-tui-was-tauri-port
verified: 2026-06-24T00:00:00Z
status: human_needed
score: 13/13 must-haves verified
overrides_applied: 0
human_verification:
  - test: "End-to-end edit→preview→inline-sudo commit walkthrough"
    expected: |
      1. ngtui launches showing StatusScreen with lock word+glyph, 3-dot token meter, grace, hmacs, ledger.
      2. Press e — EditScreen opens showing D-09 fields with their current sanctioned values.
      3. Stage a TIGHTEN (e.g. curfew.start to a later time) — preview reads "▼ Tightens curfew · free" BEFORE any prompt.
      4. Press c — ConfirmScreen shows the free-tighten gate with no token language.
      5. Press y — app suspends, sudo password prompt appears inline, commit completes; result line is verbatim from the CLI ("committed (...)"); token meter unchanged (re-read from guard.json, no optimism).
      6. At 0 tokens, a LOOSEN surfaces "available again Monday" and disables y.
    why_human: |
      D-06 anti-impulse ordering (direction+cost BEFORE sudo), D-08 inline-sudo TTY behaviour,
      and post-commit meter re-read require a live terminal run. The Task 3 human-verify checkpoint
      in 10-03-PLAN was approved live by the operator per 10-03-SUMMARY, but this is the gate's
      documented accepted_by evidence: the verifier records it as human_needed for the REVIEW record.
  - test: "Desktop theme change repaints the running TUI (D-05)"
    expected: "After running omarchy-theme-set (or touching ~/.config/omarchy/current/theme/colors.toml), the running TUI repaints within ~1s with the new colors."
    why_human: "Requires a live desktop session with omarchy installed; cannot be verified headlessly."
---

# Phase 10: Linux App — omarchy TUI Verification Report

**Phase Goal:** The Linux app is the sole sanctioned editor as a terminal/TUI — omarchy-native, command-driven, minimal, themed live via aether — built as a thin client over the one Python trust stack (it calls the control-CLI to sign via sudo; never holds the key).
**Verified:** 2026-06-24
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

All truths from 10-01/02/03 PLAN must_haves, plus roadmap requirements PORT-01/02/03, plus security invariants.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The TUI package imports ngcommon/guard/nightguard_ctl from the live LifeOS stack without vendoring a copy | VERIFIED | `backend.py:29-31` imports `ngcommon as ng`, `guard`, `nightguard_ctl as ctl` after a `sys.path.insert(STACK_DIR)` bootstrap. No `ngcommon.py`, `guard.py`, or `nightguard_ctl.py` found anywhere inside `ngtui/` (grep + find confirmed). |
| 2 | backend.read_state() returns the guard.json dict without reading any key | VERIFIED | `backend.py:43-45` delegates directly to `ng.load_state()`. AST scan: zero calls to `read_key()`, `hmac.*`, or `hexdigest()` across all six source files. Live run confirmed: verdict, tokens, noop preview all returned without error. |
| 3 | backend.live_verdict() returns one of guard.curfew_verdict's verdict strings | VERIFIED | `backend.py:68-74` delegates to `guard.curfew_verdict(cfg, state)`. Live run returned `outside_curfew`. |
| 4 | backend.preview_change() returns direction labels + quota decision computed by the CLI's own classify_change/quota_decide | VERIFIED | `backend.py:77-90` calls `ctl.classify_change`, `ctl.is_loosening`, `ctl.quota_decide`. Live run: `preview_is_noop: True` for identical-config case. |
| 5 | backend.commit() shells exactly ['sudo','/usr/bin/python3',<abs ctl.py>,'commit','--from',tmp] with no shell=True | VERIFIED | AST-verified subprocess.run argv: `['sudo', '/usr/bin/python3', os.path.join(STACK_DIR, 'nightguard_ctl.py'), 'commit', '--from', tmp]`. No `shell` keyword argument present at line 117. |
| 6 | The StatusScreen shows lock status (glyph + word + color) derived from guard.curfew_verdict, never local curfew math | VERIFIED | `widgets/status.py:152-157` calls `backend.live_verdict(cfg, state)` to get the verdict, then `verdict_display()` to map to `(glyph, word, role, caption)`. No local curfew time math. `test_status.py::test_verdict_display_maps_every_state` passes. |
| 7 | The token meter shows WEEKLY_TOKENS minus the lazy-reset effective_spent as filled/hollow glyphs with a resets-Monday caption | VERIFIED | `widgets/status.py:74-85` `token_meter()`: `["●"]*left + ["○"]*(3-left)` with caption `"N of 3 left · resets Mon YYYY-MM-DD"`. `backend.tokens_left()` uses `ctl.quota_decide([], ...)["effective_spent"]` (Pitfall 4: not raw `weekly_spent`). Test `test_token_meter_glyphs_and_caption` passes. |
| 8 | Grace status, config/state hmacs, and the audit ledger render read-only | VERIFIED | `widgets/status.py`: grace text via `_grace_text(state)`, integrity via `_integrity_text(state)` (truncated display only — `_truncate_hmac()`), ledger via `ledger_rows(state)`. No write or compute operations. Tests pass. |
| 9 | Colors come from the live omarchy colors.toml parsed into a Textual Theme; no fixed hex hardcoded | VERIFIED | `theme.py:83-104` reads `~/.config/omarchy/current/theme/colors.toml` via `tomllib`. `app.tcss`: zero hardcoded `#RRGGBB` values (grep confirmed 0 matches). All styling is via `$primary`, `$error`, `$success`, `$warning`, `$accent`, `$background`, `$text`, `$surface-lighten-1`. |
| 10 | Changing the desktop theme repaints the running TUI via mtime poll on the 1s tick | VERIFIED (code path) | `theme.py:107-131` `ThemeWatch.changed()` re-stats the colors.toml mtime. `app.py:79-80` calls `_apply_omarchy_theme()` when changed. `test_theme_watch_detects_mtime_change` passes. Live repaint requires human walkthrough (see Human Verification). |
| 11 | The EditScreen edits D-09 fields via single-key navigation (j/k/Enter/Space/c/u/Escape) | VERIFIED | `widgets/edit.py:236-243` BINDINGS confirmed. `EDITABLE_FIELDS` covers all D-09 fields (curfew.enabled/start/end/allow_commands, clock_protection.enabled, watchdog.enabled, blocking.browser_extension.enabled/extension_id, blocking.native_apps.enabled/blacklist). |
| 12 | Proposed config composed by format-preserving per-field LINE edits on sanctioned text — never a YAML re-emit | VERIFIED | `lineedit.py`: `set_scalar`, `toggle_bool`, `list_add`, `list_remove` all operate on raw text via `text.split("\n")`, never import pyyaml/ruamel. `widgets/edit.py:305-315` replays staged ops on `backend.sanctioned_text()`. 11 lineedit round-trip tests pass via live `ngcommon.yaml_load`. |
| 13 | Commit runs inside App.suspend() so sudo's password prompt appears inline; result comes from CLI stdout/exit | VERIFIED | `widgets/edit.py:209-210`: `with self.app.suspend(): res = backend.commit(self._proposed_text)`. `backend.commit()` does NOT capture stderr (stays on TTY). Task 3 human-verify checkpoint approved live (per 10-03-SUMMARY). |

**Score:** 13/13 truths verified (code path; 2 items require human walkthrough for live behavioral confirmation)

### Required Artifacts

| Artifact | Expected | Lines | Status | Details |
|----------|----------|-------|--------|---------|
| `ngtui/pyproject.toml` | textual==8.2.7 dep + ngtui entry point | — | VERIFIED | `dependencies = ["textual==8.2.7"]`; `ngtui = "ngtui.__main__:main"` |
| `ngtui/ngtui/backend.py` | Single seam to trust stack, all key-less | 134 | VERIFIED | All 6 functions present; imports live stack; no key/hmac calls |
| `ngtui/ngtui/app.py` | NightguardApp with BINDINGS, CSS_PATH, theme wiring, 1s tick, EditScreen | 107 | VERIFIED | `register_theme`, `self.theme = "omarchy"`, `set_interval(1.0, self._tick)`, `push_screen(EditScreen())` |
| `ngtui/ngtui/theme.py` | load_omarchy_theme() + ThemeWatch | 131 | VERIFIED | `load_omarchy_theme()` with alacritty fallback; `ThemeWatch.changed()` mtime poll |
| `ngtui/ngtui/widgets/status.py` | StatusScreen + verdict_display + token_meter + ledger_rows | 299 | VERIFIED | All pure helpers + Textual composition; not-initialized guard; refresh_countdown() for tick |
| `ngtui/ngtui/app.tcss` | Textual CSS using $-variable roles; contains $primary | 172 | VERIFIED | 34 `$`-variable references; zero hardcoded hex; `$primary` on hero border + countdown |
| `ngtui/ngtui/lineedit.py` | Format-preserving per-field line editors | 234 | VERIFIED | `set_scalar`, `toggle_bool`, `list_add`, `list_remove`; indentation-tracked dotted-path resolution |
| `ngtui/ngtui/widgets/edit.py` | EditScreen + ConfirmScreen + pure copy helpers | 535 | VERIFIED | `preview_line`, `confirm_copy`, `result_line`; `ConfirmScreen` with `App.suspend()`; `EditScreen` full D-09 field set |
| `ngtui/SPIKE-NOTES.md` | Recorded capture strategy | — | VERIFIED | A2 capture strategy (stdout=PIPE, stderr on TTY) documented and confirmed live |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend.py` | `nightguard_ctl.classify_change / quota_decide` | `import nightguard_ctl as ctl` after sys.path.insert(STACK_DIR) | VERIFIED | Lines 31, 86-89 |
| `backend.py` | `sudo nightguard_ctl.py commit` | `subprocess.run` argv list (no shell) | VERIFIED | Lines 117-128; argv confirmed by AST parse |
| `widgets/status.py` | `backend.live_verdict / read_state / tokens_left` | `from ngtui import backend` | VERIFIED | Lines 27, 139, 154, 165 |
| `theme.py` | `~/.config/omarchy/current/theme/colors.toml` | `tomllib.load` | VERIFIED | Lines 34, 91-93 |
| `app.py` | `theme.load_omarchy_theme` | `register_theme + self.theme` | VERIFIED | Lines 61-62 |
| `widgets/edit.py` | `backend.preview_change / backend.commit` | `from ngtui import backend, lineedit` | VERIFIED | Lines 39, 346, 210 |
| `widgets/edit.py` | `App.suspend()` wrapping `backend.commit` | `with self.app.suspend(): res = backend.commit(...)` | VERIFIED | Lines 209-210 |
| `lineedit.py` | sanctioned config text | per-field line replacement (no yaml emitter) | VERIFIED | `text.split("\n")` throughout; no yaml imports |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `widgets/status.py StatusScreen` | `state` | `backend.read_state()` → `ng.load_state()` → `guard.json` | Yes — reads live guard.json | FLOWING |
| `widgets/status.py StatusScreen` | `cfg` | `backend.sanctioned_config()` → `ng.file_bytes(ng.SANCTIONED)` | Yes — reads live sanctioned config | FLOWING |
| `widgets/status.py token_meter` | `tokens_left` | `backend.tokens_left()` → `ctl.quota_decide([], state, tz)["effective_spent"]` | Yes — lazy-reset real count | FLOWING |
| `widgets/edit.py EditScreen` | `_base_text` | `backend.sanctioned_text()` → `ng.file_bytes(ng.SANCTIONED)` | Yes — real sanctioned file bytes | FLOWING |
| `widgets/edit.py _refresh_preview` | `preview` | `backend.preview_change(proposed_text)` → `ctl.classify_change/quota_decide` | Yes — live classifier | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| backend imports live stack and returns real verdict | `cd ngtui && env NIGHTGUARD_STACK_DIR=... .venv/bin/python -c "from ngtui import backend as b; ..."` | `verdict: outside_curfew`, `tokens_left: 2`, `preview_is_noop: True` | PASS |
| All 28 unit tests pass | `cd ngtui && env ... .venv/bin/python -m pytest -q` | `28 passed in 0.09s` | PASS |
| textual 8.2.7 importable from venv | `.venv/bin/python -c "import textual; print(textual.__version__)"` | `8.2.7` | PASS |
| No shell=True in subprocess.run | AST parse of backend.py | `subprocess.run at line 117: no shell kwarg` | PASS |
| No read_key/hmac/hexdigest calls | AST parse of all 6 source files | `CLEAN — no read_key/hmac/hexdigest calls found` | PASS |
| No vendored trust-stack modules | `find ngtui -name "ngcommon.py" -o -name "guard.py" -o -name "nightguard_ctl.py"` | empty | PASS |
| No hardcoded hex colors in app.tcss | `grep "#[0-9a-fA-F]{3,6}" app.tcss` | 0 matches | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PORT-01 | 10-02, 10-03 | Terminal/TUI app — omarchy-native, command-driven, minimal, themed live via aether | SATISFIED | Textual TUI with single-key BINDINGS (D-03); omarchy colors.toml theme (D-04); live ThemeWatch mtime poll (D-05); EditScreen j/k/Enter/Space/c/u/Escape (D-03) |
| PORT-02 | 10-01, 10-02, 10-03 | Thin client over the one Python trust stack — reads state from guard.json/guard; signs via sudo control-CLI; no second crypto stack | SATISFIED | `backend.py` imports live stack modules; commit shells the exact sudoers argv; preview uses `ctl.classify_change/quota_decide`; no vendored copies found |
| PORT-03 | 10-01 | Never holds the signing key; weekly quota enforced by control-CLI | SATISFIED | Zero calls to `read_key()`, `hmac.*`, `hexdigest()` in all ngtui source (AST-verified); commit exclusively via `sudo nightguard_ctl.py commit`; quota returned by `ctl.quota_decide` |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `ngtui/ngtui/app.py:3` | Word "placeholder" in docstring | INFO | Refers to Wave-1 history ("Wave-1 placeholder shell"); current code is the real implementation |
| `ngtui/ngtui/widgets/edit.py:391,480,488` | Word "placeholder" | INFO | Used as the `Input(placeholder=...)` widget constructor parameter — not a stub indicator; this is the Textual API parameter name |

No TBD, FIXME, XXX, or TODO markers found anywhere in `ngtui/ngtui/`. No empty return stubs. No `return null`/`return []`/`return {}` patterns in output paths.

### Human Verification Required

The Task 3 checkpoint in 10-03 was approved live by the operator (per 10-03-SUMMARY.md: "checkpoint:human-verify, approved live"). The verifier records the following items as human_needed per the standard gate — they need a live terminal session to confirm behavioral ordering (not code existence):

#### 1. Anti-impulse ordering: direction+cost BEFORE the sudo prompt

**Test:** Run `cd ngtui && env NIGHTGUARD_STACK_DIR=... NIGHTGUARD_DIR=... .venv/bin/python -m ngtui`. Press `e`, stage a tighten (change curfew.start to a later HH:MM). Observe the preview line. Then press `c`. Press `y`. Watch the ordering.
**Expected:** The "▼ Tightens curfew · free" preview line is visible on the EditScreen BEFORE `c` is pressed and BEFORE the sudo prompt appears (i.e., direction+cost render before any authentication). On `y`, sudo prompts inline; on completion, the result line shows "✓ committed (...)" and the token meter reflects the re-read guard.json count.
**Why human:** D-06 anti-impulse temporal ordering and D-08 inline TTY behavior require a live terminal run; grep cannot verify temporal ordering of UI events vs subprocess spawning.

#### 2. Live theme repaint on desktop theme change (D-05)

**Test:** Run the TUI. In another terminal, switch the desktop theme (`omarchy-theme-set <theme>`) or manually touch `~/.config/omarchy/current/theme/colors.toml`. Wait up to 2 seconds.
**Expected:** The running TUI repaints with the new colors within one 1s tick cycle.
**Why human:** Requires a live omarchy desktop session; the mtime-poll code path is unit-tested but the actual repaint depends on the Textual `register_theme`/`self.theme` reassignment behavior in a running App.

### Gaps Summary

No gaps found. All 13 must-have truths are VERIFIED in the codebase. All required artifacts exist and are substantive, wired, and carrying real data. Security invariants (no key read, no hmac computation, exact sudoers argv, no shell=True, no vendored trust-stack modules) confirmed by AST analysis. 28 tests pass. The two human_needed items above are live-behavioral confirmations of an already-approved walkthrough — not new gaps.

---

## Security Invariant Summary

The three critical security invariants required by the phase context were verified as follows:

**1. TUI never calls read_key / computes no HMAC**
AST-parsed all six ngtui source files (`backend.py`, `app.py`, `theme.py`, `widgets/status.py`, `widgets/edit.py`, `lineedit.py`) for actual function calls (not comments) to `read_key`, `hmac`, `hexdigest`, `HMAC`. Result: CLEAN — zero calls found. The word "hmac" appears only in comments and display strings (truncated hmac display from state is read-only, not computed).

**2. commit() shells the exact sudoers argv with no shell=True**
AST-extracted the subprocess.run call in `backend.commit()`. Argv: `['sudo', '/usr/bin/python3', os.path.join(STACK_DIR, 'nightguard_ctl.py'), 'commit', '--from', tmp]`. No `shell` keyword argument. The mention of `shell=True` at line 110 is inside the function's docstring (a prohibition statement), not a code invocation.

**3. preview uses the imported classifier (no vendored copy)**
`backend.preview_change()` calls `ctl.classify_change(old_doc, new_doc)` and `ctl.quota_decide(dirs, ng.load_state(), tzname)` where `ctl` is `nightguard_ctl` imported from the live LifeOS stack. No `ngcommon.py`, `guard.py`, or `nightguard_ctl.py` exist anywhere inside `ngtui/` (find returned empty).

---

_Verified: 2026-06-24_
_Verifier: Claude (gsd-verifier)_
