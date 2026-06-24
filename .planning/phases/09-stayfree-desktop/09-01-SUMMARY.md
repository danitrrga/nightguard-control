---
phase: 09-stayfree-desktop
plan: 01
subsystem: infra
tags: [stayfree, hyprland, wayland, spike, screen-time, sqlite, blocklist, aur]

# Dependency graph
requires:
  - phase: 08-native-blocker
    provides: the verified root→user runuser/$HIS launch bridge (used for the spike launch observation)
provides:
  - "D-09 gating verdict: FAIL — StayFree does not track or block on Hyprland/Wayland (usage.db has 0 sessions)"
  - "Empirical routing signal: execute 09-03 (analytics-only fallback), skip 09-02 (keep-alive)"
  - "Finding: StayFree blocklist/config is clean offline SQLite, fully recoverable without the cloud"
  - "REQUIREMENTS.md TRAK-01/02 re-scoped from ActivityWatch to StayFree terms"
affects: [09-02, 09-03, stayfree-import, curfew-layer, trak-01, trak-02]

# Tech tracking
tech-stack:
  added: [stayfree-desktop 3.4.0-1 (AUR)]
  patterns: ["spike-first branch-on-result gating", "read-only SQLite inspection of an Electron app's local store"]

key-files:
  created:
    - .planning/phases/09-stayfree-desktop/09-NOTES-spike-verdict.md
  modified:
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Verdict FAIL: StayFree records 0 sessions on Hyprland/Wayland; cannot track ⇒ cannot block"
  - "StayFree is not even a useful live-analytics source on Wayland; durable value is its offline-recoverable blocklist config"
  - "Keep-alive (09-02) will NOT be built; route to 09-03"

patterns-established:
  - "Branch-on-result spike: a recorded ## Verdict line gates downstream plans (09-02 PASS vs 09-03 FAIL/PARTIAL)"

requirements-completed: [TRAK-01, TRAK-02]

# Metrics
duration: ~20min
completed: 2026-06-24
---

# Phase 9 (Plan 01): D-09 StayFree Wayland-blocking spike — Summary

**VERDICT: FAIL — `stayfree-desktop` records 0 sessions on Hyprland/Wayland (usage.db empty, Dashboard shows 0s), so it cannot track and therefore cannot block native or XWayland apps. Routes to 09-03 (analytics-only fallback); 09-02 keep-alive is NOT built.**

## Performance
- **Duration:** ~20 min (interactive spike)
- **Completed:** 2026-06-24
- **Tasks:** 3 (2 human-verify checkpoints + 1 auto)
- **Files modified:** 2 (verdict notes created, REQUIREMENTS.md edited)

## Accomplishments
- Installed and launched `stayfree-desktop 3.4.0-1` (AUR) under Hyprland after the human legitimacy gate (T-09-SC) — needs `APPIMAGELAUNCHER_DISABLE=1` to bypass appimagelauncherd.
- Established the D-09 verdict empirically: **FAIL**. StayFree's Dashboard shows `Usage Time: 0s` / "No usage history"; `usage.db.sessions` has **0 rows** after a 10+ min active session. Blocking is therefore moot (no detection signal).
- Discovered (TRAK-02 upside): StayFree's local store is **clean knex SQLite** (`config.db`, `usage.db`), not opaque leveldb. The full blocklist — `preferences/categories` (2,493 memberships), `app-groups` (1,147 brands), exported `genericWebsiteLimits` (schedules) — resolves **entirely offline**, no cloud. Custom category "Sleep Dont" (28 members) + 2 active schedule rules resolved live. Snapshot saved to scratchpad (`stayfree-resolved-blocklist.json`).
- Re-scoped REQUIREMENTS.md TRAK-01/02 from stale ActivityWatch to StayFree terms, recording the Wayland-tracking-dead caveat and the offline-blocklist-recoverable upside.

## Files Created/Modified
- `.planning/phases/09-stayfree-desktop/09-NOTES-spike-verdict.md` — the gate: install/login/tracking/blocking/store observations + `## Verdict: FAIL` line.
- `.planning/REQUIREMENTS.md` — TRAK-01/02 rewritten to StayFree (ActivityWatch text removed).

## Decisions Made
- **PARTIAL was not reached** — StayFree tracked nothing at all (not even XWayland), so this is a clean FAIL, not the "XWayland-only" PARTIAL case.
- Per user direction, finished the spike (kept the gate intact) before considering the blocklist-import pivot.

## Deviations from Plan
None on the spike mechanics. Note: the plan/RESEARCH predicted StayFree would at least *track* (and possibly block XWayland); empirically it tracked **nothing** on this box — a stronger FAIL than predicted. Also, the local store was richer/cleaner than RESEARCH's "opaque leveldb" guess (it is queryable SQLite), which is recorded as a TRAK-02 upside.

## Issues Encountered
- `appimagelauncherd` (pid 998) intercepts the launch; resolved with `APPIMAGELAUNCHER_DISABLE=1` in the launch env.
- `paru -S` build succeeded non-interactively but the final `pacman -U` step needed an interactive sudo password — completed by the user in-session.

## User Setup Required
StayFree account login is account-based (cloud), but irrelevant to the verdict — tracking produced no data regardless.

## Next Phase Readiness
- **Routes to 09-03** (analytics-only fallback): record StayFree analytics-only, keep-alive moot/not-built, re-open 09-CONTEXT.md per D-09. No `nightguard_watchdog.py` change.
- **Surfaced opportunity (not in scope of 09-03):** StayFree's curated blocklist is fully importable offline and could seed Nightguard's own curfew-layer enforcement — a candidate future phase, deferred for explicit scoping.

---
*Phase: 09-stayfree-desktop*
*Completed: 2026-06-24*
