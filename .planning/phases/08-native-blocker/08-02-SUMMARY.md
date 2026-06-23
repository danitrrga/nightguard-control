---
phase: 08-native-blocker
plan: 02
subsystem: watchdog
tags: [python, nightguard_watchdog, hyprland, runuser, sigkill, native-blocker, curfew-gate]

# Dependency graph
requires:
  - phase: 08-native-blocker
    plan: 01
    provides: "pure key-less guard.curfew_verdict(cfg, state) the kill gate consumes"
  - phase: 07.1-curfew-hook
    provides: "live Linux curfew verdict pipeline (decide) the watchdog already integrates"
provides:
  - "_kill_native_apps(cfg) — runuser->user Hyprland enumerate -> substring class match -> pid dedup -> SIGKILL-by-pid -> per-pid watchdog.log audit, returns distinct killed class names"
  - "_notify_user(uid, his, message) — one summary butler toast into the user session via the same runuser bridge"
  - "verdict-gated native-kill step folded into the root watchdog tick() (fires on locked/clock_tamper/offline_blocked, suppressed on outside_curfew/grace_active/exception)"
affects: [nightguard_watchdog]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Root->user Hyprland bridge: runuser -u <runtime-derived user> -- env XDG_RUNTIME_DIR/HYPRLAND_INSTANCE_SIGNATURE hyprctl/notify-send (list argv, no shell)"
    - "Per-tick $HIS discovery via RUNTIME_GLOB (/run/user/*/hypr/*), never cached"
    - "Verdict-gated side effect inside the existing root tick (no separate user service) — un-stoppable from user space"
    - "State worst-casing (grace=None on state_hmac mismatch) before a side-effect-free verdict, mirroring decide()"

key-files:
  created: []
  modified:
    - /home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py

key-decisions:
  - "RUNTIME_GLOB = /run/user/*/hypr/* declared beside LOG/POLICY_PATHS; uid = path segment after /run/user/, $HIS = basename — re-discovered every tick (HIS rotates on Hyprland restart)"
  - "Username derived at runtime via pwd.getpwuid(int(uid)).pw_name in ONE place (used by both kill and notify) — never hardcoded danitrrga (C7)"
  - "Fail-closed enabled default: na.get('enabled', True) — a missing/corrupt native_apps node still kills while curfew is locked; only a missing/empty blacklist short-circuits (C8/T-08-06)"
  - "Kill gate is an explicit allowlist {locked, clock_tamper, offline_blocked}; None/unknown/exception -> suppressed (never widen on uncertainty)"
  - "uid/his for the toast are RE-DERIVED once from RUNTIME_GLOB after a non-empty killed (C6) — _kill_native_apps signature unchanged"
  - "state.grace worst-cased to None on a state_hmac mismatch before curfew_verdict, mirroring guard.decide() lines 285-291 (forged grace cannot suppress the kill; C5)"

requirements-completed: [NBLK-01, NBLK-02, NBLK-03]

# Metrics
duration: 14min
completed: 2026-06-23
---

# Phase 8 Plan 02: Native-App Kill in the Root Watchdog Tick Summary

**Folded a verdict-gated, root->user Hyprland native-app kill into `nightguard_watchdog.py`'s `tick()` — each ≤60s tick during an active curfew lock enumerates the user's Hyprland clients via a `runuser` bridge, SIGKILLs blacklisted (steam/discord) windows by deduped pid, logs each kill, and fires one Spanish-butler toast — gated on the same key-less `guard.curfew_verdict` decide() uses, suppressed outside curfew / during grace / on any verdict error, and un-stoppable from user space because it lives in the root system service.**

## Performance

- **Duration:** ~14 min
- **Tasks:** 2 (both `tdd="true"`)
- **Files modified:** 1 (`nightguard_watchdog.py` in the LifeOS repo)
- **Code commits:** 2 (LifeOS repo)

## Accomplishments

- **`_kill_native_apps(cfg)`** (NBLK-01): for each `/run/user/<uid>/hypr/<HIS>` found via `RUNTIME_GLOB`, derives the uid (path segment) + `$HIS` (basename) + username (`pwd.getpwuid`), shells out with a **list argv** to `runuser -u <user> -- env XDG_RUNTIME_DIR=… HYPRLAND_INSTANCE_SIGNATURE=… hyprctl clients -j` (timeout=10), matches each client's `class`/`initialClass` against the lower-cased blacklist by **substring, case-insensitive** (D-03), **dedups pids** into a set (D-02), `os.kill(pid, SIGKILL)` each (D-01) wrapped against ProcessLookupError/PermissionError, and writes **one `watchdog.log` line per killed pid** (`KILLED native class=… pid=… mechanism=SIGKILL`, D-07). Returns the sorted distinct killed class names.
- **`_notify_user(uid, his, message)`** (D-05/D-06): delivers ONE summary toast via `notify-send "Nightguard" <message>` through the same `runuser` bridge (timeout=5), username derived the same way, fully try/except-wrapped so a notification failure never affects the kill or the tick.
- **`tick()` verdict gate** (NBLK-02/D-08/D-09): after `_missing_policies`, worst-cases `state["grace"] = None` on a `state_hmac` mismatch (mirrors `decide()` lines 285-291), calls `guard.curfew_verdict(cfg, state)` (key-less — C1) ONCE reusing the already-loaded key/state and already-parsed cfg, then `killed = _kill_native_apps(cfg)` only when `verdict in (locked, clock_tamper, offline_blocked)`. On a non-empty `killed`, re-derives uid/his once from `RUNTIME_GLOB` (C6), composes the butler message (`"Cerre Steam, Discord - es hora de descansar, senor"`), fires one toast, and folds `KILLED native: …` into the single `_log` line.
- **Un-stoppable from user space** (NBLK-03): the kill is a step inside the existing root *system*-service tick — no `--user` unit to `systemctl --user stop`.
- **Security posture:** all subprocess calls use list argv (no `shell=True`, no f-string command — T-08-04); bounded timeouts (10s enum / 5s notify — C4 / T-08-08) so a hung hyprctl/notify-send can never stall the ROOT tick; runtime-derived username (C7); fail-closed `enabled` default (C8/T-08-06); the kill runs AFTER `verify_and_revert` so a kill failure can never block the integrity revert.

## Task Commits

Each task committed atomically in the **LifeOS** repo (`/home/danitrrga/dev/Projects/LifeOS`), per the cross-repo convention (`nightguard_watchdog.py` lives there, not in nightguard-control):

1. **Task 1: `_kill_native_apps` + `_notify_user` helpers** — `d7bb61b` (feat)
2. **Task 2: gate the kill on `guard.curfew_verdict` in `tick()`** — `b6d819f` (feat)

**Plan metadata** (SUMMARY/STATE/ROADMAP) committed separately in **nightguard-control**.

_Both tasks `tdd="true"`. RED was implicit (the helpers / the gate did not exist → the plan's `<behavior>` assertions could not pass); GREEN = the two `feat` commits. No separate `test(...)` commit exists because the deliverable IS the code and the verification is the plan's automated `<verify>` stub tests (run green), consistent with this stack's no-pytest convention (08-01 precedent)._

## Files Created/Modified

- `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py` — added `RUNTIME_GLOB` constant, `_runuser_argv` builder, `_kill_native_apps(cfg)`, `_pid_class(clients, pid)` audit helper, `_notify_user(uid, his, message)`; wired the verdict-gated kill step into `tick()` between the browser-policy check and the `_log` summary.

## Decisions Made

- **One `_runuser_argv(uid, his, user, *cmd)` builder** for both enumeration and notification — single place that constructs the `runuser … env XDG_RUNTIME_DIR=… HYPRLAND_INSTANCE_SIGNATURE=… <cmd>` list argv, guaranteeing no shell anywhere on the root->user path (T-08-04).
- **`_pid_class` audit helper** so the per-pid `watchdog.log` line carries a real class string even though pids are deduped into a set before killing (D-07).
- **Re-derive (not return) uid/his for the toast** (C6): `_kill_native_apps` keeps its `(cfg) -> [classes]` signature; `tick()` re-globs `RUNTIME_GLOB` once and breaks after the first session (personal box has one). A now-empty glob (rare race after a non-empty `killed`) skips only the toast — the kills + their log lines already happened.
- **Verdict allowlist, not denylist:** `verdict in ("locked", "clock_tamper", "offline_blocked")`; `None`/`grace_active`/`outside_curfew`/any exception all fall through to no kill — the gate never widens on uncertainty (T-08-06).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan `<verify>` greps for `shell=True` and a single `verify_and_revert` would have failed on doc/comment mentions of those literals**
- **Found during:** Task 1 (`! grep shell=True`) and Task 2 (`grep -c verify_and_revert == 1`).
- **Issue:** My initial helper docstrings/comments contained the literal strings `shell=True` and `verify_and_revert` as prose. The plan's acceptance greps are literal substring counts, so a comment mention would fail the gate (`shell=True` found → gate trips; `verify_and_revert` count = 3 instead of 1) even though the actual code has zero `shell=True` and exactly one `verify_and_revert` call.
- **Fix:** Reworded the prose to "never a shell" / "guard's verify-and-revert" / "integrity-revert call" so the only literal `shell=True` / `verify_and_revert` occurrences are absent from code-as-prose; the real code (one `guard.verify_and_revert(...)` call, all subprocess calls list-argv) is unchanged.
- **Files modified:** `nightguard_watchdog.py` (comments/docstring only — no behavior change).
- **Verification:** `! grep shell=True` → no match; `grep -c verify_and_revert` → 1. Both gates green.
- **Committed in:** folded into the Task 1 (`d7bb61b`) and Task 2 (`b6d819f`) commits respectively.

---

**Total deviations:** 1 auto-fixed (Rule 3 — a literal-substring collision between the plan's verification greps and explanatory prose; zero behavior deviation).
**Impact on plan:** No scope or behavior change. The product code matches the plan exactly; only the wording of comments was adjusted so the plan's own grep gates pass cleanly.

## Known Stubs

None. Both helpers are fully wired: `_kill_native_apps` reads the live `blocking.native_apps.blacklist` (steam/discord, D-10) from the cfg `tick()` already parses, enumerates the real Hyprland session via the verified `runuser` bridge, and SIGKILLs real pids; `_notify_user` delivers a real `notify-send` toast. The only no-op path is the intentional, documented "no Hyprland session" defensive fallback (08-NOTES).

## Threat Flags

None beyond the plan's `<threat_model>`. The new surface (root->user `runuser` to `hyprctl`/`notify-send`, `os.kill` by pid) is exactly T-08-04/05/06/07/08, all mitigated/accepted as documented: list argv only (no shell injection), explicit subprocess timeouts (no tick stall), explicit verdict allowlist (no fire-open), runtime-derived username, fail-closed enabled default. The PID-reuse race (T-08-05) is the one accepted-and-documented residual (few-ms window; worst case is one relaunchable stray SIGKILL on a single-user desktop).

## Verification Results

- `python3 -c "import nightguard_watchdog"` → PASS.
- Stubbed-enumeration test: dedup to one pid (4242) despite two matching windows, substring case-insensitive class+initialClass match (`steamwebhelper`/`steam`), `firefox` untouched, timeout kwarg present on the enumeration `subprocess.run` → PASS (`['steam', 'steamwebhelper'] [4242] {'t': 10}`).
- Stubbed-verdict gate test: kill SUPPRESSED on `outside_curfew`, FIRES on `locked`, SUPPRESSED on a raising verdict (no new call) → PASS (`{'kill': 1}`).
- Single-cfg-read test: `ng.file_bytes` called exactly once per tick (no second config read in the kill path) → PASS.
- greps: `def _kill_native_apps` / `def _notify_user` / `RUNTIME_GLOB` present; no `shell=True`; no literal `danitrrga`; `timeout=10` + `timeout=5` present; exactly one `verify_and_revert`; a `state["grace"] = None` worst-casing in tick → all PASS.
- **Manual smoke** (executor, while in curfew with Steam open — the 08-NOTES live-proof): deferred to the phase verifier, not blocking (no live curfew window / Steam session available during this autonomous run).

## TDD Gate Compliance

Both tasks are `tdd="true"`. RED was established by absence (the helpers + the gate did not exist; the plan's `<behavior>`/`<verify>` stub assertions could not pass against the pre-edit file). GREEN = the two `feat` commits, each making its `<verify>` block pass. No separate committed `test(...)` file — the deliverable IS the code and the verification is the plan's executable `<verify>` stubs (run green here), consistent with this stack's no-pytest convention (guard.py / nightguard_watchdog.py ship no test module; matches 08-01).

## Next Phase Readiness

- Native blocking (NBLK-01/02/03) is now live in the root tick: blacklisted Hyprland classes are SIGKILLed by pid each ≤60s tick during curfew, gated on the same verdict guard uses, with one butler toast + per-pid audit, and cannot be stopped from user space.
- The deferred sub-60s `.socket2.sock` `openwindow` event-listener (08-CONTEXT `<deferred>`) remains the only acceleration upgrade — build it only if ≤60s leakage proves inadequate with evidence; it would reuse this same `runuser` bridge inside the root watchdog.
- Phase 8 plan count complete (2/2).

## Self-Check: PASSED

- `.planning/phases/08-native-blocker/08-02-SUMMARY.md` exists.
- LifeOS commits `d7bb61b` (Task 1) and `b6d819f` (Task 2) present in git.
- `def _kill_native_apps`, `def _notify_user`, and `RUNTIME_GLOB` present in `nightguard_watchdog.py`; `_kill_native_apps` is called inside `tick()` gated on `guard.curfew_verdict`.

---
*Phase: 08-native-blocker*
*Completed: 2026-06-23*
