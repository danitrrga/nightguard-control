---
phase: 08-native-blocker
reviewed: 2026-06-23T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - /home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/guard.py
  - /home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
critical_resolved: 1
status: issues_found
---

> **CR-01 RESOLVED (2026-06-23, commit `27da8ad` in LifeOS):** `curfew_verdict` now
> checks `in_curfew` BEFORE the clock-tamper gate, so `outside_curfew` always wins
> outside the window and the watchdog kill can never fire in daytime. Verified: an
> NTP-verified daytime clock skew now returns `outside_curfew` (kill suppressed); an
> in-curfew skew still returns `clock_tamper`. `decide()` hook contract intact for the
> in-curfew/daytime cases. The 4 warnings + 3 info findings below remain open (advisory).

# Phase 8: Code Review Report

**Reviewed:** 2026-06-23T00:00:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Phase 08 added a pure, key-less `curfew_verdict(cfg, state)` to `guard.py` and re-expressed
`decide()` in terms of it (with a per-tick `true_unix()` memo), then wired a verdict-gated
native-app kill (`_kill_native_apps` + `_notify_user`) into the root `nightguard_watchdog.py`
`tick()`. Security is load-bearing: this code runs as ROOT and SIGKILLs user processes.

The subprocess/`runuser` bridge is implemented correctly — list-argv everywhere, no `shell=True`,
no f-string commands, username derived from `pwd.getpwuid` (not hardcoded), and both subprocess
calls carry explicit timeouts. The verdict gate fails closed on exceptions and `None`. The
state.grace worst-casing is present and mirrors `decide()`.

However, the refactor introduced **one genuine behavioral divergence that the watchdog inherits as
an over-kill**: because `curfew_verdict` evaluates the clock-tamper check *before* the in-curfew
check (behavior-preserving for `decide()`'s deny, but NOT safe as a kill gate), a clock skew at any
time of day — including broad daylight, outside curfew — drives the verdict to `clock_tamper`,
which is in the watchdog's firing set. The root watchdog will then SIGKILL the user's blacklisted
apps *outside* the curfew window. This directly contradicts the phase's own D-08 ("suppressed
outside curfew") and is the one finding that breaches the "don't kill outside the lock" invariant
the 08-NOTES explicitly called out.

## Critical Issues

### CR-01: `clock_tamper` fires the watchdog SIGKILL outside the curfew window

**File:** `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/guard.py:258-264`
and `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py:188-189`

**Issue:**
In `curfew_verdict`, the clock-tamper gate returns *before* the in-curfew gate:

```python
if verified and source != "override" and clock.get("enabled", True):
    offset = abs(tnow - int(time.time()))
    if offset > int(clock.get("max_offset_minutes", 5)) * 60:
        return "clock_tamper"        # returns BEFORE in_curfew()
true_dt = localize(cfg, tnow)
if not in_curfew(cfg, true_dt):
    return "outside_curfew"
```

For `decide()` this is behavior-preserving and harmless: a clock-tamper just denies the Claude
Code hook. But the watchdog reuses the *same* verdict to gate a destructive action:

```python
if verdict in ("locked", "clock_tamper", "offline_blocked"):
    killed = _kill_native_apps(cfg)
```

`clock_tamper` is independent of the curfew window. So if the system clock drifts/jumps more than
`max_offset_minutes` (default 5) at, say, 3pm — well outside any curfew — the root watchdog
enumerates and **SIGKILLs the user's blacklisted apps in broad daylight**. NTP/HTTP fetch failures
can also produce a stale monotonic-anchored cache that later reads as a large offset, so this is
reachable without deliberate tampering (e.g. suspend/resume clock jumps, DST edge, a flaky network
producing a stale `.timecache`). This violates the phase's own D-08 ("suppressed outside curfew and
during an active grace window") and the 08-NOTES "Don't kill outside the lock / during grace"
edge-case requirement.

`offline_blocked` does NOT have this problem because `in_curfew` is checked first and short-circuits
to `outside_curfew`. Only `clock_tamper` leaks across the curfew boundary.

**Fix:** Decouple the kill gate from the raw verdict so that destructive action only fires when the
clock-tamper *also* coincides with the curfew window. Two options:

Option A — re-order `curfew_verdict` so clock-tamper does not pre-empt the window check (preferred,
keeps one source of truth, still denies the hook the same way because `decide()` maps both branches
to deny):

```python
true_dt = localize(cfg, tnow)
in_window = in_curfew(cfg, true_dt)
if verified and source != "override" and clock.get("enabled", True):
    offset = abs(tnow - int(time.time()))
    if offset > int(clock.get("max_offset_minutes", 5)) * 60:
        # Only report clock_tamper inside the window; outside it, fall through.
        if in_window:
            return "clock_tamper"
if not in_window:
    return "outside_curfew"
```

Option B — narrow the watchdog firing set and add an explicit in-window guard before killing, so a
`clock_tamper` verdict alone cannot trigger SIGKILL outside curfew. Either way, add a test:
`source != "override"`, offset > threshold, `true_dt` outside the curfew window ⇒ kill suppressed.

## Warnings

### WR-01: `curfew_verdict` purity claim is undermined by module-global tick state

**File:** `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/guard.py:69-104, 224-278`

**Issue:** The docstring advertises `curfew_verdict` as "Pure, side-effect-free." It is not: it
reads and (via `_begin_tick`/`_end_tick`) writes the module globals `_TICK_OPEN`/`_TICK_TIME`, and
through `true_unix()` it performs network I/O and writes `.timecache`. The `own_tick = not _TICK_OPEN`
guard also makes the function's behavior depend on hidden global state set by a *different* caller
(`decide()`), which is the opposite of pure. This is not a crash, but the misleading contract makes
the clock-tamper ordering issue (CR-01) easy to miss and makes the function unsafe to reason about
or reuse concurrently. The globals are also not reentrancy/thread safe — fine for the current
single-threaded oneshot, but the docstring should not claim purity.

**Fix:** Soften the docstring to "deterministic verdict given resolved true-time; performs network
I/O via `true_unix()` and mutates a module-level per-tick memo." Better, pass the resolved
`(tnow, source)` in as parameters so the function is genuinely pure and the memo lives only in the
caller — that also removes the `_TICK_OPEN` cross-caller coupling entirely.

### WR-02: hyprctl exit status is ignored before parsing stdout

**File:** `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py:105-109`

**Issue:** `subprocess.run(..., capture_output=True, timeout=10)` is called without `check=True`, and
`proc.returncode` is never inspected; the code goes straight to `json.loads(proc.stdout...)`. If
`runuser`/`hyprctl` fails (wrong `$HIS`, hyprctl missing, permission edge) it may exit non-zero with
empty or partial stdout. The empty/garbled case happens to be swallowed by the broad
`except Exception: continue`, so it degrades to a no-op — but that means a genuine enumeration
failure is silently indistinguishable from "no blacklisted windows," with no diagnostic in
`watchdog.log`. For a root tool whose whole job is enforcement, a silently failing enumeration is a
correctness/observability gap.

**Fix:** Check `proc.returncode` and log a distinct diagnostic on non-zero exit before falling
through, e.g.:

```python
if proc.returncode != 0:
    _log("ENUM FAILED rc=%d stderr=%s" % (proc.returncode, proc.stderr.decode("utf-8", "replace")[:200]))
    continue
```

### WR-03: notification re-derives uid/his from a fresh glob, mismatching the killing session under multi-session

**File:** `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py:190-202`

**Issue:** `_kill_native_apps` loops over *all* `/run/user/*/hypr/*` sessions and aggregates
`killed_classes` across them. The notification block then re-globs and `break`s on the *first* match,
sending the summary toast to a single (arbitrary) session. On a multi-session box (the very case
`_kill_native_apps` loops to support), apps killed in session B produce a toast delivered only to
session A, and session B's user sees nothing. The code comment acknowledges only the empty-glob race,
not the wrong-session delivery. The plan documents the personal box as single-session, so impact is
low today, but the kill path is written to be multi-session and the notify path silently is not.

**Fix:** Have `_kill_native_apps` return (or the gate collect) the `(uid, his)` of each session that
actually had kills, and notify each of those sessions — or document explicitly that notification is
single-session-only and gate the multi-session kill loop accordingly so the two halves agree.

### WR-04: PID-reuse race kills by a possibly-reassigned pid (documented, but unmitigated in code)

**File:** `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py:121-123`

**Issue:** Between `hyprctl clients -j` enumeration and `os.kill(pid, signal.SIGKILL)` the pid can be
reaped and reassigned to an unrelated process, which root then SIGKILLs. This is acknowledged and
"accept-and-document" in T-08-05, so it is not a blocker — but flagging it per review policy: the
worst case is root SIGKILLing an arbitrary innocent user process. Running as root makes the blast
radius larger than the threat-model text implies (it is not limited to the user's own relaunchable
apps if the reassigned pid is a different service the user started).

**Fix (if/when it bites, as the plan notes):** re-read `/proc/<pid>/comm` (or
`/proc/<pid>/cgroup`) and re-confirm the class/identity immediately before `os.kill`, skipping the
kill on mismatch.

## Info

### IN-01: notification message dropped its accents/diacritics (mojibake-avoidance regression)

**File:** `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py:196`

**Issue:** The plan (D-05) specifies the Spanish toast `"Cerré %s — es hora de descansar, señor"`,
but the code ships ASCII-only `"Cerre %s - es hora de descansar, senor"` (no accents, hyphen instead
of em dash, "senor" not "señor"). Cosmetic, but it is a visible deviation from the specified
butler-style message and reads as a typo to the end user.

**Fix:** Use the specified UTF-8 string (the file is already declared `encoding="utf-8"` on its
writes): `"Cerré %s — es hora de descansar, señor"`.

### IN-02: `killed_classes` falls back to the raw blacklist entry, mislabeling audit/notification

**File:** `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py:119`

**Issue:** When a client matches but has neither `class` nor `initialClass` (both null/empty),
`killed_classes.add(... or entry)` records the lowercased *blacklist substring* (e.g. `"steam"`) as
the "killed class." The subsequent `.title()` toast and the `KILLED native:` log line then show the
blacklist pattern rather than the real window identity. Minor labeling inaccuracy; does not affect
which pids are killed.

**Fix:** Prefer the real client identity for the audit label, or omit the entry-fallback from the
display set (keep it only for the match decision).

### IN-03: repeated inline imports inside the kill path

**File:** `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py:92-96, 149-150, 195`

**Issue:** `glob`, `json`, `pwd`, `signal`, `subprocess` are imported inside functions, and `glob`/
`pwd`/`subprocess` are re-imported across `_kill_native_apps`, `_notify_user`, and the `tick()`
notify block. Inline imports are a reasonable choice to keep the guard's cold-start lean, but the
duplication is inconsistent and slightly obscures the module's real dependency surface. Style only.

**Fix:** Hoist the small, always-needed stdlib imports (`glob`, `pwd`, `subprocess`, `json`,
`signal`) to module top, or keep them inline consistently in one place. No behavior change.

---

_Reviewed: 2026-06-23T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
