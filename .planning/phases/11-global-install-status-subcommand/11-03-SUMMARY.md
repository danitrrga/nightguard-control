---
phase: 11-global-install-status-subcommand
plan: 03
subsystem: ngtui-install-verification
tags: [desk-01, desk-02, uv-tool-install, waybar, status, pty, sudo, checkpoint, human-verified]
requires:
  - phase: 11-01
    provides: ngtui.status._shape / UNAVAILABLE (the Waybar object the installed shim emits)
  - phase: 11-02
    provides: ngtui.__main__ argv front-controller (status --json router + TTY guard)
  - phase: 10
    provides: backend.commit inline-sudo App.suspend() PTY path + hardcoded /usr/bin/python3 signer
provides:
  - "Human-verified confirmation that `uv tool install` exposes a real global `ngtui` shim (SC-1)"
  - "Human-verified key-less `ngtui status --json` Waybar JSON from the installed shim under a scrubbed env (DESK-02/SC-3)"
  - "Human-verified fail-closed `unavailable` on a poisoned stack (SC-3)"
  - "Human-verified SC-5 readability GREEN: guard.json + sanctioned config 0644, .guardkey 0600"
  - "Human-verified live loosen-with-token commit end-to-end from the installed shim — inline-sudo PTY survives (SC-4)"
affects: [phase-12-launcher-waybar, phase-13-autostart-aur-packaging]
tech-stack:
  added: []
  patterns:
    - "packaging-level Success Criteria validated by a blocking-human checkpoint, not pytest (real isolated venv + real token spend cannot run in-process)"
    - "clean-env resolution proof: `env -i HOME=$HOME PATH=$HOME/.local/bin:/usr/bin:/bin ngtui status --json | jq -e .`"
key-files:
  created:
    - .planning/phases/11-global-install-status-subcommand/11-03-SUMMARY.md
  modified: []
key-decisions:
  - "No code change in this plan — it validates the install/PTY boundary only; Plans 01-02 already proved the status-core and router green."
  - "SC-4 (real loosen-with-token commit) and SC-1/SC-5 (real isolated-venv install + scrubbed env) are reserved as the two manual blocking-human checkpoints because each consumes real state (a weekly token) or a real install not reproducible in pytest."
patterns-established:
  - "Pattern: install-boundary Success Criteria are confirmed on the live box via blocking-human checkpoints before /gsd:verify-work, never auto-approved."
requirements-completed: [DESK-01, DESK-02]
duration: ~1min
completed: 2026-06-25
---

# Phase 11 Plan 03: Global-Install + Live-Commit Verification Summary

**Live-box human verification that the `uv tool install` global `ngtui` shim resolves the LifeOS stack from a clean login shell, emits key-less Waybar JSON, fails closed on a bad stack, keeps `.guardkey` 0600 while the read artifacts are 0644, and still survives a real loosen-with-token commit through the inline-`sudo` PTY (SC-1/SC-3/SC-4/SC-5 all PASS).**

## Performance

- **Duration:** ~1 min (documentation only — verification performed manually by the user on the live box)
- **Started:** 2026-06-25
- **Completed:** 2026-06-25
- **Tasks:** 2 (both `checkpoint:human-verify`, `gate="blocking-human"`)
- **Files modified:** 0 source files (no code change — checkpoint-only plan)

## Accomplishments

- **SC-1 (global shim + clean-env resolution) — PASS.** `uv tool install --python 3.14 .`
  produces a real `ngtui` on `PATH` (`~/.local/bin/ngtui`) that launches the TUI from a
  bare login shell with NO `NIGHTGUARD_*` dev env; the `backend.py` hardcoded defaults
  resolve the LifeOS stack under a scrubbed `env -i` environment.
- **DESK-02 / SC-3 (key-less Waybar JSON) — PASS.** `ngtui status --json` from the installed
  shim emits a single-line, `jq`-valid Waybar object (`text`/`tooltip`/`class`) with a real
  verdict class (not `unavailable`), and fails closed to exactly
  `{"text":"○ —","class":"unavailable"}` (exit 0) when pointed at a nonexistent stack.
- **SC-5 (readability flag) — PASS / GREEN.** `guard.json` and the sanctioned config are
  user-readable `root:root 0644` (the status path can read them key-lessly); `.guardkey`
  stays `root:root 0600` (cat is Permission denied) — the isolated-venv process never
  gains read access to the signing key.
- **SC-4 (live PTY-surviving commit) — PASS.** A REAL loosen-with-token commit succeeded
  end-to-end from the installed shim: the inline-`sudo` prompt appeared in the terminal
  (proving `App.suspend()` released a genuine PTY despite the global-install interpreter),
  the commit landed (guard did NOT revert the sanctioned signed change), and the token count
  decremented by 1.
- **Requirements DESK-01 and DESK-02 satisfied** — Phase 11 is functionally complete; the
  global `ngtui` command and its key-less `status --json` subcommand are proven on the live box.

## Task Commits

This plan contains no code-task commits — both tasks are `checkpoint:human-verify` gates with
`files_modified: []`. The only commit is the plan-completion metadata commit.

1. **Task 1: Install the global shim + confirm clean-env resolution and SC-5 readability** — manually verified on the live box, user reply "approved" (no commit; no code change)
2. **Task 2: Live loosen-with-token commit from the installed shim (PTY survival, SC-4)** — manually verified on the live box, user reply "approved" (no commit; no code change)

**Plan metadata:** committed with this SUMMARY + STATE + ROADMAP (`docs(11-03): ...`).

## Files Created/Modified

- `.planning/phases/11-global-install-status-subcommand/11-03-SUMMARY.md` — this verification record.
- No source files touched — the status-core (`status.py`) and router (`__main__.py`) shipped in Plans 01-02.

## Decisions Made

- **No code change in this plan.** It exists solely to confirm the packaging-level Success
  Criteria (SC-1/SC-3/SC-4/SC-5) that cannot be unit-tested in the pytest process — a real
  isolated-venv install, a real scrubbed login env, and a real weekly-token-spending commit.
- **Both checkpoints kept as blocking-human gates** (not auto-approved) because SC-4 consumes
  a real weekly token and SC-1/SC-5 require a real install + live filesystem permissions on
  the author's LifeOS box. The user verified all six numbered steps of each task and replied
  "approved".

## Deviations from Plan

None — plan executed exactly as written. Both `checkpoint:human-verify` gates were reached,
presented to the user, and approved on the live box with no failing output.

## Authentication / Checkpoint Gates

- **Task 1 (SC-1/SC-3/SC-5):** blocking-human checkpoint — user ran the install + clean-env
  status + readability + TTY-guard steps and confirmed PASS ("approved").
- **Task 2 (SC-4):** blocking-human checkpoint — user performed a live loosen-with-token
  commit from the installed shim, entered the inline `sudo` credential in the terminal, and
  confirmed the commit succeeded with the token decremented and no guard revert ("approved").

These are normal checkpoint flow, not deviations.

## Issues Encountered

None — every verification step passed on first run per the user's approval.

## Known Stubs

None — no source code in this plan; the verified surfaces (`ngtui status --json`, the inline
sudo commit path) are fully wired live, not stubbed.

## User Setup Required

The plan's `user_setup` (run `uv tool install --python 3.14 .` in `ngtui/` and verify the
shim on PATH) was performed by the user as part of the Task 1 checkpoint and is confirmed
done — `~/.local/bin/ngtui` is installed and on the bare login PATH.

## Next Phase Readiness

- Phase 11 is COMPLETE (3/3 plans). The global `ngtui` command, the key-less
  `ngtui status --json` Waybar emitter, and the PTY-surviving commit path are all proven on
  the live box.
- **Ready for Phase 12 (Launcher + Waybar Presence):** the `.desktop` launcher can
  `-e ngtui` against the installed shim, and the `custom/nightguard` bar module can `exec`
  `ngtui status --json` (single-line JSON, never non-zero, non-blocking) with confidence the
  install/PTY boundary holds.
- No blockers or concerns carried forward from this plan.

## Self-Check: PASSED

- `.planning/phases/11-global-install-status-subcommand/11-03-SUMMARY.md` exists on disk.
- No code commits to verify (checkpoint-only plan); the metadata commit is created alongside
  STATE.md and ROADMAP.md updates.

---
*Phase: 11-global-install-status-subcommand*
*Completed: 2026-06-25*
