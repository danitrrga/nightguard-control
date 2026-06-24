---
phase: 09-stayfree-desktop
plan: 03
subsystem: infra
tags: [stayfree, fallback, analytics-only, curfew-layer, wayland, blocklist-import]

# Dependency graph
requires:
  - phase: 09-stayfree-desktop (plan 01)
    provides: the D-09 spike verdict (FAIL) that gates this fallback branch
provides:
  - "Recorded analytics-only fallback resolution (StayFree does not track/block on Wayland)"
  - "Explicit residual: no native-app hard guarantee; hard floor = curfew layer"
  - "09-CONTEXT.md re-opened with the FAIL outcome + the blocklist-import feasibility correction"
affects: [trak-01, trak-02, stayfree-import, curfew-layer]

# Tech tracking
tech-stack:
  added: []
  patterns: ["branch-on-result fallback: record resolution + re-open CONTEXT, build no enforcement"]

key-files:
  created: []
  modified:
    - .planning/phases/09-stayfree-desktop/09-NOTES-spike-verdict.md
    - .planning/phases/09-stayfree-desktop/09-CONTEXT.md

key-decisions:
  - "StayFree = analytics-only (and degraded — 0 live data on Wayland); no keep-alive built"
  - "nightguard_watchdog.py left unchanged (no enforcement added on the FAIL branch)"
  - "No native-app hard guarantee accepted, eyes-open; hard floor = curfew layer"
  - "Blocklist import (StayFree config.db → Nightguard) flagged feasible — deferred to a future phase"

patterns-established:
  - "FAIL-branch resolution is a first-class deliverable: document the residual, refuse false enforcement"

requirements-completed: [TRAK-01, TRAK-02]

# Metrics
duration: ~5min
completed: 2026-06-24
---

# Phase 9 (Plan 03): Analytics-only fallback (D-09 FAIL branch) — Summary

**StayFree recorded as analytics-only (degraded — no live tracking on Wayland); keep-alive moot and NOT built; no native-app hard guarantee accepted; 09-CONTEXT.md re-opened per D-09. No enforcement code added.**

## Performance
- **Duration:** ~5 min
- **Completed:** 2026-06-24
- **Tasks:** 1 (auto)
- **Files modified:** 2 (both planning docs)

## Accomplishments
- Appended `## Fallback resolution (D-09 FAIL branch)` to `09-NOTES-spike-verdict.md`: StayFree analytics-only + degraded; keep-alive moot/not-built; explicit "no native-app hard guarantee" residual with the curfew layer as the hard floor.
- Re-opened `09-CONTEXT.md` with a dated RE-OPENED/RESOLVED banner recording the FAIL outcome and the resolution (history preserved, append/annotate only).
- Recorded the material correction: the desktop app's blocklist **is** offline-recoverable (contradicting the earlier "proven infeasible" sync note), flagged as a future-phase opportunity.
- Confirmed `nightguard_watchdog.py` (LifeOS) is unchanged — no enforcement built on this branch.

## Files Created/Modified
- `.planning/phases/09-stayfree-desktop/09-NOTES-spike-verdict.md` — fallback resolution section appended.
- `.planning/phases/09-stayfree-desktop/09-CONTEXT.md` — re-opened/resolved banner.

## Decisions Made
- Treated the verdict as a clean FAIL (not PARTIAL) since StayFree tracked nothing at all.
- Deliberately built **no** keep-alive — a non-tracking/non-blocking app gains nothing from forced uptime, and building it would imply false enforcement (threat T-09F-01).

## Deviations from Plan
The plan anticipated StayFree would at least serve as an analytics source. Empirically it tracks nothing on Wayland, so "analytics-only" is recorded as *degraded* (no live data). Additionally, the spike disproved the CONTEXT's "blocklist sync infeasible" assumption for the desktop app — recorded as a correction + future opportunity rather than acted on (out of scope).

## Issues Encountered
None.

## User Setup Required
None.

## Next Phase Readiness
- Phase 9 closes on the predicted FAIL without building false enforcement.
- Open follow-up (not a blocker): the doc/code tension on Phase 8 NBLK status (REQUIREMENTS.md has an uncommitted NBLK→Complete edit; live watchdog has no native-kill code) is the user's to reconcile.
- Strong candidate next phase: import StayFree's offline blocklist (`config.db`) into Nightguard's own curfew-layer enforcement.

---
*Phase: 09-stayfree-desktop*
*Completed: 2026-06-24*
