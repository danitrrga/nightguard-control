---
phase: 10-linux-app-omarchy-tui-was-tauri-port
plan: 03
subsystem: ui
tags: [textual, tui, python, anti-impulse, sudo, line-edit, classifier, omarchy]

# Dependency graph
requires:
  - phase: 10-01
    provides: backend.py adapter (preview_change, commit, sanctioned_text/config) over the live Python trust stack
  - phase: 10-02
    provides: NightguardApp shell + StatusScreen + omarchy theming; action_edit stub to wire
provides:
  - "lineedit.py — format-preserving per-field LINE editors (set_scalar/toggle_bool/list_add/list_remove) over config text, no YAML emitter"
  - "widgets/edit.py — EditScreen (D-09 single-key editing) + per-field anti-impulse preview (D-06/D-07) + ConfirmScreen inline-sudo commit gate (D-08)"
  - "pure copy helpers preview_line/confirm_copy/result_line (exact UI-SPEC strings + colour roles)"
  - "app.py action_edit wired to push_screen(EditScreen) — the `e` binding now opens the editor"
affects: [phase-10-verifier, future-tui-phases, edit-flow]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Format-preserving per-field LINE edits over config TEXT (indentation-tracked dotted-path resolution); NEVER a YAML re-emit (preserves the bytes the HMAC signs)"
    - "Anti-impulse preview driven entirely off the signer's own classifier (backend.preview_change → classify_change/quota_decide); direction + token cost rendered BEFORE any sudo prompt"
    - "Pure copy helpers (preview_line/confirm_copy/result_line) unit-tested headless; Textual screens only compose them"
    - "Commit via App.suspend() so sudo's password/fingerprint prompt is inline; post-commit re-reads sanctioned state (no optimism)"

key-files:
  created:
    - ngtui/ngtui/lineedit.py
    - ngtui/ngtui/widgets/edit.py
    - ngtui/tests/test_lineedit.py
    - ngtui/tests/test_preview.py
  modified:
    - ngtui/ngtui/app.py
    - ngtui/ngtui/app.tcss

key-decisions:
  - "Proposed config is composed by replaying staged line-edit ops on backend.sanctioned_text() — the line-edit transforms always start from the signed bytes (no YAML emitter, T-10-09)"
  - "Dotted-path line resolution tracks indentation nesting so same-named leaf keys (blocking.native_apps.enabled vs blocking.browser_extension.enabled) are disambiguated"
  - "y inside ConfirmScreen is the ONLY commit trigger; a 0-token loosen disables commit with 'available again Monday'; commit runs inside App.suspend()"
  - "Intentional UI-SPEC deviation: REFUSED text stays on the TTY during inline sudo; the in-widget result line is returncode-keyed (result_line), not a verbatim stderr echo"

patterns-established:
  - "Per-field line edit (no YAML emit): set_scalar/toggle_bool/list_add/list_remove preserve indent + quote style + trailing comments; round-trip via ngcommon.yaml_load"
  - "Anti-impulse front-loading: the most-consequential staged direction (loosen > tighten > noop) is surfaced as the preview line before authentication"

requirements-completed: [PORT-01, PORT-02, PORT-03]

# Metrics
duration: ~35min
completed: 2026-06-24
---

# Phase 10 Plan 03: EditScreen — Anti-Impulse Editing + Inline-Sudo Commit Summary

**Textual EditScreen that edits the D-09 field set via single-key nav, composes the proposed config by format-preserving per-field line edits (no YAML emit), front-loads the signer's own tighten/loosen + token-cost verdict BEFORE any sudo prompt, and commits inside App.suspend() so sudo's prompt is inline — the core anti-impulse moment the product exists for.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-06-24
- **Tasks:** 3 (2 auto/TDD + 1 human-verify checkpoint, approved live)
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments
- `lineedit.py`: four pure text-transform editors (`set_scalar`, `toggle_bool`, `list_add`, `list_remove`) that edit only the addressed line — preserving indentation, quote style, and trailing comments — with indentation-tracked dotted-path resolution. Absent field/entry raises `ValueError` (fixed editable set, D-09).
- `widgets/edit.py`: `EditScreen` editing the D-09 fields with `j/k/Enter/Space/c/u/Escape`; each staged edit re-composes the proposed text by replaying line-edit ops on `backend.sanctioned_text()` and renders the per-field direction + token cost from `backend.preview_change` (the signer's own `classify_change`/`quota_decide`) — before any auth.
- `ConfirmScreen`: the deliberate-friction gate; `y` is the only commit trigger, commit runs inside `with self.app.suspend(): backend.commit(...)` so sudo is inline (D-08); a 0-token loosen disables commit with "available again Monday"; post-commit re-reads sanctioned state (no optimism).
- Pure copy helpers `preview_line`/`confirm_copy`/`result_line` return the exact UI-SPEC strings + `$`-variable colour roles, unit-tested headless.
- `app.py` `action_edit` now `push_screen(EditScreen())`; edit-field styling added to `app.tcss` (focus `reverse` + `$accent`, preview/confirm role classes — no hardcoded hex).
- **Task 3 human-verify approved live:** the operator ran the full TUI end to end — direction + token cost render BEFORE the sudo prompt (anti-impulse, D-06), the inline sudo commit completed, the result line is verbatim from the CLI, and token accounting is correct (no silent spend).

## Task Commits

Each task was committed atomically (TDD: test → feat):

1. **Task 1: lineedit.py per-field line edits** — `8b5d2b9` (test, RED), `99c4f3a` (feat, GREEN)
2. **Task 2: EditScreen + preview + ConfirmScreen + app wiring** — `a86e800` (test, RED), `d48a7c1` (feat, GREEN)
3. **Task 3: end-to-end inline-sudo walkthrough** — checkpoint:human-verify, approved live (no code commit)

## Files Created/Modified
- `ngtui/ngtui/lineedit.py` — format-preserving per-field line editors over config text (no YAML emitter)
- `ngtui/ngtui/widgets/edit.py` — EditScreen + ConfirmScreen + the pure preview/confirm/result helpers
- `ngtui/ngtui/app.py` — `action_edit` wired to `push_screen(EditScreen())`; EditScreen import
- `ngtui/ngtui/app.tcss` — edit-field list + focus highlight + preview/confirm/result role classes
- `ngtui/tests/test_lineedit.py` — round-trip line-edit tests (11) via the live `ngcommon.yaml_load`
- `ngtui/tests/test_preview.py` — anti-impulse copy helper tests (11)

## Decisions Made
- Proposed config is built by **replaying staged line-edit ops on the sanctioned base text**, so every transform starts from the bytes the signer HMACs — no YAML re-emit (T-10-09).
- Dotted-path line resolution **tracks indentation nesting** to disambiguate same-named leaf keys under different parents.
- `result_line` keys off the **returncode** (stderr stays on the TTY for inline sudo) rather than echoing a captured `REFUSED` string — an intentional, documented UI-SPEC deviation justified by the inline-auth requirement.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected a malformed test fixture during Task 1**
- **Found during:** Task 1 (lineedit GREEN)
- **Issue:** The originally-authored `test_set_scalar_preserves_trailing_comment` fixture placed `extension_id` at the same indent as its parent `browser_extension:`, so it was not actually nested — the (correct) indentation-tracking resolver rightly could not find it on the dotted path.
- **Fix:** Corrected the fixture to properly nest `extension_id` (indent 4 under `browser_extension:` at indent 2); added an `abc123 not in out` assertion.
- **Files modified:** ngtui/tests/test_lineedit.py
- **Verification:** All 11 lineedit tests green; full suite 28 green.
- **Committed in:** `99c4f3a` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug — test fixture, not production code).
**Impact on plan:** The resolver behaved correctly; only the test fixture was wrong. No production-code change beyond the plan. No scope creep.

## Issues Encountered
- Live quota differs from STATE.md's noted "0/3": the running `quota_decide` reports tokens still available (the confirm gate showed "After commit: 1 left"). This is correct — the helper keys off the live decision, not the stale doc note. No action needed; flagged here so the verifier isn't surprised.

## Known Stubs
None — the EditScreen wires real data end to end (sanctioned config base, live classifier preview, real sudo commit path). The list editor uses the lighter add/delete-last model per UI-SPEC ("Enter to add, d to delete") rather than a full row-cursor editor; this is the spec's sanctioned mechanism, not a stub.

## Threat Flags
None — no new security surface beyond the plan's `<threat_model>`. The commit path uses the exact sudoers argv via `backend.commit` (T-10-03), the `--from` temp is mkstemp 0600 (T-10-04), the preview imports the live classifier (T-10-02), line edits never re-emit YAML (T-10-09), and post-commit re-reads `guard.json` with no optimistic decrement (T-10-10/11).

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Plan 10-03 complete: the editable half of the TUI (anti-impulse preview + inline-sudo commit) ships and was human-verified end to end. Phase 10's three plans (backend adapter, StatusScreen, EditScreen) are done.
- Ready for the phase verifier / code review.

## Self-Check: PASSED

All created files exist on disk (`lineedit.py`, `widgets/edit.py`, `test_lineedit.py`, `test_preview.py`) and all four task commits (`8b5d2b9`, `99c4f3a`, `a86e800`, `d48a7c1`) are present in git history.

---
*Phase: 10-linux-app-omarchy-tui-was-tauri-port*
*Completed: 2026-06-24*
