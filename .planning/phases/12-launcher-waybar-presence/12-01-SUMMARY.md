---
phase: 12-launcher-waybar-presence
plan: 01
subsystem: infra
tags: [uv-tool, ngtui, waybar, pytest, install-gate]

# Dependency graph
requires:
  - phase: 11-global-install
    provides: "ngtui uv-tool package (pyproject [project.scripts] ngtui) + key-less `ngtui status --json` Waybar substrate"
provides:
  - "`~/.local/bin/ngtui` resolvable on the login PATH (the bare `ngtui` command all P12 surfaces invoke)"
  - "Proven jq-valid `ngtui status --json`, exit 0, fail-closed"
  - "GREEN ngtui pytest baseline (67 passed) — the D-10 no-change regression anchor for later P12 plans"
affects: [12-02, 12-03, 12-04, 12-05, 12-06, waybar-module, desktop-launcher, ngtui-menu]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Install-gate plan: (re)install the uv-tool shim + hard-verify PATH resolution before any live wiring"
    - "Full-suite green baseline captured pre-change as the D-10 regression anchor"

key-files:
  created:
    - .planning/phases/12-launcher-waybar-presence/12-01-SUMMARY.md
  modified:
    - ngtui/.gitignore

key-decisions:
  - "ngtui reinstalled via `uv tool install --python 3.14 .` (idempotent, first-party wheel only — T-12-SC accept, T-12-01 verified: resolves into ~/.local/bin)"
  - "D-10 baseline locked at 67 passing ngtui tests; later plans must not drop this count"
  - "Generated `ngtui/uv.lock` (emitted by `uv run pytest`) gitignored rather than tracked — deps already pinned in pyproject.toml; no new tracked artifact in a pure-gate plan"

patterns-established:
  - "Gate-before-wire: a BLOCKING prerequisite plan proves the shared command resolves + answers before dependent live-wiring plans run"

requirements-completed: [DESK-03, BAR-01]

# Metrics
duration: 2min
completed: 2026-07-04
---

# Phase 12 Plan 01: ngtui Install Gate + D-10 Baseline Summary

**Reinstalled `ngtui` as a uv-tool so bare `ngtui` resolves to `~/.local/bin/ngtui`, hard-verified `ngtui status --json` is jq-valid + fail-closed exit 0, and locked a GREEN 67-test baseline as the D-10 regression anchor.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-04T09:27:07Z
- **Completed:** 2026-07-04T09:28:35Z
- **Tasks:** 2
- **Files modified:** 1 (ngtui/.gitignore)

## Accomplishments
- `command -v ngtui` now resolves to `/home/danitrrga/.local/bin/ngtui` — the blocking gate that unblocks every P12 live-wiring surface (`.desktop` Exec, Waybar module exec, `ngtui-menu`) that invokes bare `ngtui`.
- `ngtui status --json` emits exactly one jq-valid Waybar object (`{"text":"○ 3","tooltip":"OPEN · 3 tokens left","class":"outside_curfew"}`), exit 0, with `class` + `text` keys present (fail-closed contract holds).
- Locked the D-10 no-change regression baseline: **67 tests pass** (`uv run pytest -q`, exit 0). Later plans must keep this count from dropping.

## Task Commits

Both tasks are verification/install gates whose primary artifact (`~/.local/bin/ngtui`) lives OUTSIDE the git tree, so neither produced a repo code change. The only committed repo change was housekeeping for a generated lockfile side-effect of the test-baseline run.

1. **Task 1: (Re)install ngtui + verify it resolves + answers** — no repo artifact (installs to `~/.local/bin/ngtui`, outside the tree); acceptance criteria all verified live.
2. **Task 2: Capture the green pre-change test baseline** — 67 passed, exit 0; no code change.

**Housekeeping commit:** `2c0ffef` (chore — gitignore generated `ngtui/uv.lock`)

## Files Created/Modified
- `ngtui/.gitignore` — added `uv.lock` (generated runtime output of `uv run`; deps pinned in pyproject.toml)
- `.planning/phases/12-launcher-waybar-presence/12-01-SUMMARY.md` — this summary

## Acceptance Verification (Task 1)
- `command -v ngtui` → `/home/danitrrga/.local/bin/ngtui` (ends in `/ngtui`, inside `~/.local/bin` — T-12-01 mitigated).
- `ngtui status --json | python3 -c '...assert "class" in o and "text" in o...'` → `ok`.
- `ngtui status --json >/dev/null; echo $?` → `0` (fail-closed always-exit-0 contract).

## D-10 Baseline (Task 2)
- **67 tests passed**, 0 failed (`cd ngtui && uv run pytest -q`, exit 0).
- Later P12 plans (esp. any touching the backend) must assert this count does not drop; a red baseline would invalidate the phase's no-change contract for `status.py`.

## Decisions Made
- Used the exact Phase 11 install command `uv tool install --python 3.14 .` (idempotent re-install upgrades in place). First-party wheel only — no third-party package install (T-12-SC accept).
- Gitignored the generated `ngtui/uv.lock` (never previously tracked) instead of committing it — keeps this pure-gate plan free of a new tracked artifact; dependency pins already live in `pyproject.toml`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Gitignore generated `ngtui/uv.lock`**
- **Found during:** Task 2 (test baseline)
- **Issue:** `uv run pytest` syncs the environment and emits an untracked `ngtui/uv.lock`; leaving a generated file untracked violates the clean-tree hygiene rule, and it was never previously tracked.
- **Fix:** Added `uv.lock` to `ngtui/.gitignore` (deps already pinned in pyproject.toml; this uv-tool project committed no lockfile in Phase 11).
- **Files modified:** ngtui/.gitignore
- **Verification:** `git status --short` no longer lists `ngtui/uv.lock`.
- **Committed in:** `2c0ffef`

---

**Total deviations:** 1 auto-fixed (1 blocking/housekeeping)
**Impact on plan:** No scope creep; no code touched (`status.py`/`__main__.py`/`backend.py` unchanged, honoring D-10). The gate and baseline are the plan's sole deliverables.

## Issues Encountered
None. Both acceptance gates passed on the first run.

## User Setup Required
None - no external service configuration required. The `~/.local/bin/ngtui` install is a local uv-tool step performed by this plan.

## Next Phase Readiness
- `ngtui` resolves on the login PATH and answers `status --json` fail-closed — every P12 live-wiring plan (12-02..12-06: `.desktop` launcher, Waybar module, `ngtui-menu`, icon, autostart) is now unblocked.
- D-10 baseline (67 tests) recorded as the regression anchor.
- No blockers.

---
*Phase: 12-launcher-waybar-presence*
*Completed: 2026-07-04*

## Self-Check: PASSED
- FOUND: `.planning/phases/12-launcher-waybar-presence/12-01-SUMMARY.md`
- FOUND: `ngtui/.gitignore` (uv.lock ignored)
- FOUND: `~/.local/bin/ngtui` (executable, resolves on PATH)
- FOUND commit: `2c0ffef` (chore — gitignore uv.lock)
- FOUND commit: `70efa6c` (docs — summary)
