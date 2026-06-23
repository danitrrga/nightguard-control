---
phase: 08-native-blocker
plan: 01
subsystem: guard
tags: [python, guard.py, curfew-verdict, ntp-true-time, refactor, single-source-of-truth]

# Dependency graph
requires:
  - phase: 07.1-curfew-hook
    provides: guard.py decide() verdict pipeline wired as the live Linux curfew hook
provides:
  - "Pure side-effect-free curfew_verdict(cfg, state) in guard.py returning locked / grace_active / outside_curfew / clock_tamper / offline_blocked"
  - "decide() re-expressed in terms of curfew_verdict so the curfew GATING math is defined once (D-09)"
  - "Per-tick true_unix() memo (_begin_tick/_end_tick/_TICK_OPEN) keeping a single true-time resolution per decide() call"
affects: [08-02-native-kill, nightguard_watchdog]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Side-effect-free verdict extraction: pure (cfg, state) -> verdict-string function the watchdog and decide() both call"
    - "Per-tick true-time memo so a single true_unix() resolution is shared across the verdict + grace_remaining recompute"

key-files:
  created: []
  modified:
    - /home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/guard.py

key-decisions:
  - "curfew_verdict signature locked to (cfg, state) — no key parameter (C1); HMAC verification is the caller's job"
  - "curfew_verdict returns the verdict STRING only — grace_remaining_secs arithmetic stays decide()-local (C2)"
  - "true_unix() invoked at most ONCE per decide() via a per-tick memo; decide() reads the memo for grace_remaining instead of re-calling true_unix()"
  - "curfew_verdict opens a private tick when called standalone (08-02 watchdog) and tears it down — no module-global memo leak"

patterns-established:
  - "Single-source curfew gating: decide() and the 08-02 kill gate consume one pure curfew_verdict; no copy-pasted curfew math (D-09)"
  - "Behavior-preserving refactor proven by byte-identical decide() JSON parity (original vs refactored) across curfew boundaries + HARD_LOCKOUT"

requirements-completed: [NBLK-02]

# Metrics
duration: 18min
completed: 2026-06-23
---

# Phase 8 Plan 01: guard.py D-09 Refactor — Pure curfew_verdict Summary

**Extracted a pure, key-less, string-only `curfew_verdict(cfg, state)` from `guard.py`'s `decide()` and re-expressed `decide()` in terms of it, so the curfew/grace/true-time/clock-tamper/offline gating math is defined exactly once and the Phase-8 watchdog native-kill gate can consume the same verdict without re-running `verify_and_revert` or the HMAC audit chain.**

## Performance

- **Duration:** ~18 min
- **Tasks:** 2 (both `tdd="true"`)
- **Files modified:** 1 (`guard.py` in the LifeOS repo)
- **Code commits:** 2 (LifeOS repo)

## Accomplishments
- New pure `curfew_verdict(cfg, state)` returning one of `locked` / `grace_active` / `outside_curfew` / `clock_tamper` / `offline_blocked`, reproducing `decide()`'s exact gating sequence via the existing pure helpers (`true_unix`, `localize`, `in_curfew`) — no `verify_and_revert`, no `_verdict`/`append_audit`, no `key`, no `grace_remaining` arithmetic (D-08 / D-09 / C1 / C2).
- `decide()` re-expressed to source its verdict from `curfew_verdict` and map the string back onto the existing `_verdict()` JSON + exit contract; the inline gating sequence is gone (gating math now single-sourced).
- `grace_remaining_secs` stays `decide()`-local (recomputed from `state["grace"]["window_end"] - tnow`).
- Added a per-tick `true_unix()` memo (`_begin_tick`/`_end_tick`/`_TICK_OPEN`) so a single true-time resolution is shared between the verdict and the grace_remaining recompute — `true_unix()` invoked exactly once per `decide()`.
- `curfew_verdict` is safe as a standalone entry point for 08-02: it opens a private tick when no tick is open and leaves no module-global memo leak.

## Task Commits

Each task committed atomically in the **LifeOS** repo (`/home/danitrrga/dev/Projects/LifeOS`), per the cross-repo convention (guard.py lives there, not in nightguard-control):

1. **Task 1: Extract pure curfew_verdict** — `7c2bc05` (feat)
2. **Task 2: Re-express decide() via curfew_verdict** — `faec552` (feat)

**Plan metadata** (SUMMARY/STATE/ROADMAP) committed separately in **nightguard-control**.

_Note: both tasks were `tdd="true"`. RED was confirmed before each (curfew_verdict absent; decide parity baseline captured from the pre-refactor original); the function is the deliverable, so each task is one behavior-adding `feat` commit (GREEN)._

## Files Created/Modified
- `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/guard.py` — added `curfew_verdict(cfg, state)`; rewrote `decide()`'s gating body to call it; added `_begin_tick`/`_end_tick`/`_TICK_OPEN` + a per-tick memo inside `true_unix()`.

## Decisions Made
- **Locked `(cfg, state)` signature kept literally** so 08-02's `curfew_verdict(cfg, state)` call and the plan's signature grep both hold; the per-tick sharing was solved with a module-level memo rather than an extra parameter (which would have changed the def line and broken the acceptance grep).
- **`true_unix()` exactly-once via a tick memo:** decide() reads the memo (`_TICK_TIME`) for `grace_remaining` instead of calling `true_unix()` a second time, satisfying the "invoked at most once per decide()" acceptance literally (not just relying on the existing 120s `.timecache`).
- **Standalone safety for 08-02:** `curfew_verdict` opens its own tick when none is open and restores state in a `finally`, so a watchdog call leaves `_TICK_OPEN=False`/`_TICK_TIME=None`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan C3 verification (offline_blocked) was time-of-day dependent**
- **Found during:** Task 1 (curfew_verdict verification)
- **Issue:** The plan's C3 test (PLAN.md lines 147-149) monkeypatches `guard.true_unix` to return `(None, "offline")`, but the offline branch falls back to `int(time.time())` for the curfew-window check. The monkeypatch can't reach that wall-clock fallback, so the assertion only passes when the test is actually run during curfew hours (20:45-05:30). Run in the afternoon it yields `outside_curfew`, not `offline_blocked`.
- **Fix:** Ran the offline assertion with the system clock pinned inside the curfew window (`time.time` patched to the 02:00 `TNOW`), which is exactly the runtime condition the branch guards. The **product code is faithful to `decide()`** and was not changed — `decide()` uses the same `int(time.time())` fallback, so the refactored and original code are behavior-identical here. This is a test-fixture gap, not a code defect.
- **Files modified:** none (test-execution adjustment only)
- **Verification:** With the clock pinned, all five verdicts (`locked`/`grace_active`/`outside_curfew`/`clock_tamper`/`offline_blocked`) pass.
- **Committed in:** n/a (no product change)

**2. [Rule 1 - Bug] Plan T2 check2 needed a seeded config.yaml**
- **Found during:** Task 2 (decide() re-expression verification)
- **Issue:** The plan's T2 check2 (PLAN.md line 206) runs full `guard.py` against an empty `$NIGHTGUARD_DIR`. With no `config.yaml`, `decide()` falls into the `HARD_LOCKOUT` (24/7 curfew) path and returns `deny/curfew`, never `outside_curfew` — so the assertion can't pass regardless of the refactor.
- **Fix:** Seeded a real `config.yaml` (curfew 20:45-05:30) in the test dir before asserting `reason=="outside_curfew"` at 14:00. Confirmed the **pre-refactor original `guard.py` behaves identically** on an empty dir (also `HARD_LOCKOUT`/`deny`), proving this is a fixture gap, not a regression.
- **Files modified:** none (test-execution adjustment only)
- **Verification:** With a seeded config, 14:00 → `allow/outside_curfew`, 02:00 → `deny/curfew exit 1`; byte-identical decide() JSON parity vs the original across 8 boundary times + the HARD_LOCKOUT path.
- **Committed in:** n/a (no product change)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — test-fixture bugs in the plan's verification commands; zero product-code deviations).
**Impact on plan:** No scope creep. Product behavior is exactly as specified and proven behavior-preserving against the pre-refactor original; only the plan's two verification commands had latent environment assumptions (system clock / seeded config) that were corrected at run time.

## Issues Encountered
- **true_unix double-invocation on the grace path:** the first design recomputed `tnow` in `decide()`'s grace branch by calling `true_unix()` again. Resolved by introducing the explicit `_TICK_OPEN`/`_TICK_TIME` per-tick memo (distinguishing "tick open" from "value resolved") and having `decide()` read the memo directly — single resolution, correct `remaining=600` on the grace path. Verified via instrumented counts (`verify_and_revert=1`, `true_unix=1`).

## Threat Flags
None — pure-stdlib Python refactor of an existing module; no new network endpoints, auth paths, file access, or schema. The new surface (`curfew_verdict`) is read-only and key-less; T-08-01/T-08-02/T-08-03 from the plan's threat register are honored (caller worst-cases state; in_curfew fail-closes to in-curfew on parse error; the single-fire audit path is reused verbatim).

## TDD Gate Compliance
Both tasks are `tdd="true"`. RED was established before implementation (curfew_verdict absent → grep exit 1; decide() parity baseline captured from `git show HEAD~1`). GREEN = the two `feat` commits. No separate `test(...)` commit exists because the deliverable IS the function and the verification is the plan's automated `<verify>` blocks (run green) rather than a committed test file — consistent with this stack's no-pytest convention (guard.py ships no test module). The behavior assertions in `<behavior>`/`<acceptance_criteria>` were all executed and pass.

## Next Phase Readiness
- 08-02 can call `guard.curfew_verdict(cfg, state)` to gate the native-kill step: **FIRE** on `locked` / `clock_tamper` / `offline_blocked`, **SUPPRESS** on `outside_curfew` / `grace_active`. The function is side-effect-free (no second revert, no duplicate audit) and standalone-safe (no memo leak).
- The kill gate must still worst-case `state` (grace=None) before calling, mirroring `decide()`'s state-validity handling (curfew_verdict performs no HMAC).

## Self-Check: PASSED

- `08-01-SUMMARY.md` exists.
- LifeOS commits `7c2bc05` (Task 1) and `faec552` (Task 2) present in git.
- `def curfew_verdict(cfg, state):` present in guard.py.

---
*Phase: 08-native-blocker*
*Completed: 2026-06-23*
