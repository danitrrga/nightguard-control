# Phase 8: Native Blocker - Pattern Map

**Mapped:** 2026-06-23
**Files analyzed:** 3 (all MODIFIED, none new) + 1 config (data source)
**Analogs found:** 3 / 3 (all in-file / same-codebase analogs)

> **Critical path note for the planner:** Phase 8 edits the live LifeOS Python trust
> stack, **NOT this repo**. All source paths below are ABSOLUTE under
> `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/`. Only the `.planning/`
> artifacts live in `nightguard-control`. There are **no new files** — every change is
> an edit to an existing Python module.

---

## File Classification

| Modified File (absolute) | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py` | watchdog tick / orchestrator | event-driven (per-tick) + transform + (new) process-control | `_missing_policies(cfg)` + `tick()` body (same file) | exact (in-file) |
| `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/guard.py` | verdict engine | request-response / pure-compute (after D-09 refactor) | `decide()` + `in_curfew()` + grace block (same file) | exact (in-file) |
| `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/ngcommon.py` | shared primitives | utility (read-only) | `yaml_load` / `file_bytes` / `CONFIG` (already used by `tick()`) | exact (reuse, no edit expected) |

**No subprocess/runuser analog exists anywhere in the codebase** (verified by grep:
no `subprocess`, `Popen`, `runuser`, `notify-send`, `hyprctl`, `os.kill`, `SIGKILL`).
The new enumerate→kill→notify step is the first process-control code in the stack. Its
**structural** analog is the file-based policy check `_missing_policies` (read a source →
compute a list → fold into the tick summary); its **invocation** shape comes from
`08-NOTES-hyprland-from-root.md`, not from existing code. See "No Analog Found" below.

---

## Pattern Assignments

### `nightguard_watchdog.py` (watchdog tick — new enumerate→match→kill→notify step)

**Analog:** `_missing_policies(cfg)` (lines 37-52) for the "read source → derive a list →
fold into summary" shape; `tick()` (lines 55-70) for where the new step slots in.

**D-08/D-09 gate must consume the verdict, not re-run revert.** The watchdog **already**
calls `guard.verify_and_revert(key, state)` at the top of `tick()` — the native-kill step
must NOT call it again, and must NOT trigger guard's audit chain. It needs a *new*
side-effect-free verdict entry point from `guard.py` (see guard.py section).

**Imports pattern** (lines 16-28) — keep `runuser`/notify subprocess imports local to the
new helper (the stack's convention: heavy/rare imports are function-local, e.g.
`import fcntl` inside `app_holds_lock`, `import time` inside `decide`):
```python
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ngcommon as ng
import guard
```

**Logging convention** (lines 31-34) — one local-time ISO line appended to `watchdog.log`.
D-07 audit lines (class, pid, mechanism) reuse this exact helper, not guard's HMAC chain:
```python
def _log(msg):
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (ts, msg))
```

**Module-constant convention** (lines 24-28) — declare new paths/lists as module constants
beside `LOG`/`POLICY_PATHS`. The new helper's run-dir glob root belongs here:
```python
LOG = os.path.join(ng.NIGHTGUARD_DIR, "watchdog.log")
POLICY_PATHS = [
    "/etc/chromium/policies/managed/nightguard.json",
    "/etc/brave/policies/managed/nightguard.json",
]
# NEW (Phase 8): root of per-user XDG runtime dirs to discover Hyprland $HIS.
# e.g. RUNTIME_GLOB = "/run/user/*/hypr/*"
```

**Core "read source → derive list → fold into summary" pattern** — the analog the new
`_kill_native_apps(cfg)` helper copies (lines 37-52):
```python
def _missing_policies(cfg):
    be = (cfg.get("blocking") or {}).get("browser_extension") or {}
    if not be.get("enabled", True):
        return []
    ext = be.get("extension_id")
    missing = []
    for p in POLICY_PATHS:
        try:
            with open(p, encoding="utf-8") as fh:
                data = fh.read()
        except OSError:
            missing.append(p)
            continue
        if ext and ext not in data:
            missing.append(p)
    return missing
```
New helper mirrors this: read `(cfg.get("blocking") or {}).get("native_apps") or {}`,
early-return `[]` if `not na.get("enabled", True)` or blacklist empty, then enumerate
clients (via the `runuser` bridge from 08-NOTES), match `class`/`initialClass` substring
case-insensitive (D-03), dedup pids (D-02), SIGKILL each (D-01), and **return the list of
distinct app classes/names killed** so `tick()` folds it into the summary + fires one
notification (D-06). Wrap subprocess calls in `try/except` and no-op on failure (the
no-Hyprland case from 08-NOTES) — same defensive `except OSError: continue` posture as the
analog.

**`tick()` integration point** (lines 55-70) — the new step slots **between the
browser-policy check and the `_log` summary**, gated on the verdict:
```python
def tick():
    key = ng.read_key()
    state = ng.load_state()
    reverted, fail_closed = guard.verify_and_revert(key, state)   # <-- side effects ALREADY done here
    try:
        cfg = ng.yaml_load(ng.file_bytes(ng.CONFIG).decode("utf-8"))   # <-- reuse this exact cfg parse for the blacklist
    except Exception:
        cfg = {}
    missing = _missing_policies(cfg)
    # >>> NEW Phase 8 step slots HERE <<<
    #   verdict = guard.curfew_verdict(cfg, state)   # D-09 side-effect-free entry point
    #   killed = _kill_native_apps(cfg) if (verdict locked AND no active grace) else []
    #   if killed: _notify_user("Cerré %s — es hora de descansar, señor" % ...)  (D-05/D-06)

    parts = []
    if reverted:
        parts.append("REVERTED config.yaml -> " + ("HARD LOCKOUT" if fail_closed else "sanctioned"))
    if missing:
        parts.append("MISSING browser policies: " + ", ".join(missing))
    # NEW: if killed: parts.append("KILLED native: " + ", ".join(killed))  (D-07)
    _log("tick: " + ("; ".join(parts) if parts else "ok"))
```
Note `cfg` is already parsed once via `ng.yaml_load(ng.file_bytes(ng.CONFIG)...)` —
reuse that same `cfg` for `blocking.native_apps.blacklist`; do NOT re-read config.

---

### `guard.py` (D-09 refactor — expose a side-effect-free curfew verdict)

**Analog:** `decide()` (lines 191-233) is the existing verdict pipeline; the refactor
factors its **pure** curfew/grace/true-time core out so the watchdog can consume a verdict
**without** re-running `verify_and_revert` (line 202) or the `_verdict()` audit writes
(lines 242-246). The functions `in_curfew()`, `true_unix()`, `localize()`, and the grace
block are already pure / read-mostly and can be called directly.

**The side-effect boundary** — these are the lines the watchdog must NOT trigger a second
time. `decide()` mixes them with the pure logic; the refactor separates them:
```python
def decide():
    key = ng.read_key()
    state = ng.load_state()
    ...
    reverted, fail_closed = verify_and_revert(key, state)   # SIDE EFFECT (line 202) — watchdog already did this
    ...
    return _verdict(...)                                    # SIDE EFFECT — _verdict() writes the audit chain
```
```python
def _verdict(decision, reason, ...):                        # lines 236-255 — DO NOT re-run for the kill gate
    ...
        ng.append_audit(key, "guard-fire", "...")           # second audit write = D-09 violation
    ...
```
**Planner constraint (D-09, locked):** the new entry point must take an already-parsed
`cfg` + `state` and return ONLY the curfew/grace/true-time verdict (e.g. a dict or enum:
`locked` / `grace_active` / `outside_curfew` / `clock_tamper` / `offline_blocked`), calling
NEITHER `verify_and_revert` NOR `_verdict`/`append_audit`. `decide()` should then be
re-expressed in terms of this pure function so the curfew math is defined once.

**Pure curfew window logic to factor out** (`in_curfew`, lines 153-174) — already pure,
takes `(cfg, true_dt)`, handles per-day schedule + overnight wrap:
```python
def in_curfew(cfg, true_dt):
    """true_dt is an aware datetime already in the config timezone."""
    cur = cfg.get("curfew") or {}
    if not cur.get("enabled", True):
        return False
    start_s, end_s = cur.get("start"), cur.get("end")
    dow = true_dt.strftime("%A").lower()
    sched = (cur.get("schedule") or {}).get(dow)
    if sched == "off":
        return False
    if isinstance(sched, str) and "-" in sched:
        start_s, end_s = sched.split("-", 1)
    elif isinstance(sched, dict):
        start_s, end_s = sched.get("start", start_s), sched.get("end", end_s)
    try:
        start_m, end_m = _hhmm_to_min(start_s), _hhmm_to_min(end_s)
        now_m = true_dt.hour * 60 + true_dt.minute
        if start_m > end_m:
            return now_m >= start_m or now_m < end_m
        return start_m <= now_m < end_m
    except Exception:
        return True
```

**True-time + clock-tamper + offline gating** (`decide()` lines 210-223) — the exact
sequence the pure verdict must reproduce (NTP true-time → clock tamper → curfew → offline
→ grace). This is the D-08 "same full verdict" the kill gate reuses:
```python
    import time
    tnow, source = true_unix()
    verified = tnow is not None
    if not verified:
        tnow = int(time.time())
    if verified and source != "override" and clock.get("enabled", True):
        offset = abs(tnow - int(time.time()))
        if offset > int(clock.get("max_offset_minutes", 5)) * 60:
            return _verdict("deny", "clock tamper", ...)        # -> verdict: clock_tamper (kill fires)
    true_dt = localize(cfg, tnow)
    if not in_curfew(cfg, true_dt):
        return _verdict("allow", "outside_curfew", ...)         # -> verdict: outside_curfew (kill SUPPRESSED)
    if not verified and cur.get("block_when_offline", True):
        return _verdict("deny", "ntp unreachable", ...)         # -> verdict: offline_blocked (kill fires, D-08)
```

**Grace-window override block** (`decide()` lines 224-233) — the kill gate must SUPPRESS
kills when this returns "grace active" (D-08):
```python
    grace = state.get("grace") if state_valid else None
    if isinstance(grace, dict):
        try:
            same_day = grace.get("date") == true_dt.strftime("%Y-%m-%d")
            if same_day and int(grace["window_start"]) <= tnow < int(grace["window_end"]):
                remaining = int(grace["window_end"]) - tnow
                return _verdict("allow", "grace active", ...)   # -> verdict: grace_active (kill SUPPRESSED)
        except Exception:
            pass
    return _verdict("deny", "curfew", ...)                      # -> verdict: locked (kill FIRES)
```

**`true_unix()` reuse** (lines 69-101) — call as-is; it is read-mostly (only writes its own
`.timecache`, which is shared state the watchdog can safely warm). It already has the
monotonic-anchored cache + the `NIGHTGUARD_TEST_NTP_OVERRIDE` test seam the planner should
exercise in tests:
```python
def true_unix():
    if os.environ.get("NIGHTGUARD_TEST_NTP_OVERRIDE") == "1":
        ov = os.environ.get("NIGHTGUARD_NTP_OVERRIDE_UNIX")
        if ov:
            return int(ov), "override"
    ...
    return val, source
```

---

### `ngcommon.py` (reuse only — no edit expected)

**Analog:** N/A — these are the existing primitives the new code consumes. No new helper
is needed here unless the planner chooses to centralize the run-dir glob (not required).

**Config constant + parse + bytes** (lines 21, 58-61, 133) — exactly the primitives `tick()`
already uses; the blacklist comes from the same parse, do not invent a new reader:
```python
CONFIG = os.path.join(NIGHTGUARD_DIR, "config.yaml")     # line 21

def file_bytes(path):                                    # lines 58-61
    """Raw bytes of a file (the unit HMAC'd for config integrity)."""
    with open(path, "rb") as fh:
        return fh.read()

def yaml_load(text):                                     # line 133 — the hand-rolled fixed-shape parser
    ...
```
`yaml_load` already parses `- ` scalar list items (lines 153-163), so
`blocking.native_apps.blacklist` (a scalar list) round-trips correctly through the existing
parser — confirmed against the live config below.

---

## Data Source: the blacklist (read-only)

`/home/danitrrga/dev/Projects/LifeOS/nightguard/config.yaml` (lines 30-36) — the D-10 v1
membership the kill step matches against:
```yaml
  native_apps:
    enabled: true
    # Hyprland window classes killed during curfew (Phase 8 finalizes membership + kill mechanism).
    blacklist:
      - steam
      - discord
```
The CLI's `FIELD_TABLE` (`nightguard_ctl.py` lines 53-54) already governs this field as a
`list_remove` (removing an entry LOOSENS → costs a token), so blacklist membership is a
tighten/loosen the engine governs — no Phase 8 schema change needed.

---

## Shared Patterns

### Logging (watchdog audit — D-07)
**Source:** `nightguard_watchdog.py:_log` (lines 31-34)
**Apply to:** every native-kill audit line (class, pid, mechanism). Use this plain local-time
`watchdog.log` appender — NOT guard's HMAC-chained `append_audit` (that is for guard
verdicts only; reusing it from the watchdog would violate D-09's "no duplicate audit chain").
```python
def _log(msg):
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (ts, msg))
```

### Defensive read / no-op-on-failure
**Source:** `_missing_policies` (`except OSError: ... continue`, lines 47-49) and
`tick()` (`except Exception: cfg = {}`, lines 59-62)
**Apply to:** all subprocess/`runuser`/`hyprctl` calls — wrap in try/except and treat
failure as "no Hyprland / no clients" → empty kill list (08-NOTES "no-Hyprland no-op").
Never let an enumeration failure crash the tick; the tick must still log and return.

### Function-local imports for rare/heavy deps
**Source:** `app_holds_lock` (`import fcntl`, line 110), `decide` (`import time`, line 210),
`append_audit` (`import datetime`, line 123)
**Apply to:** `import subprocess` / `import signal` / `import glob` inside the new
`_kill_native_apps` helper, not at module top — matches the stack's lean-import convention.

### Verdict gating (D-08) — single source of truth
**Source:** `guard.py:decide` lines 210-233 (true-time → tamper → curfew → offline → grace)
**Apply to:** the kill gate consumes the **new side-effect-free verdict** derived from this
exact sequence. Kill FIRES on `locked`, `clock_tamper`, `offline_blocked`; SUPPRESSED on
`outside_curfew`, `grace_active`. No copy-pasted curfew math (D-09).

---

## No Analog Found

The new process-control code has **no existing in-codebase analog** — it is the first
subprocess/IPC code in the nightguard stack (grep across the dir found zero
`subprocess`/`runuser`/`hyprctl`/`notify-send`/`os.kill`/`SIGKILL` usage).

| New code | Role | Data Flow | Reason / where the pattern comes from |
|---|---|---|---|
| `runuser`-to-user Hyprland enumeration | process-control | request-response (shell out) | No subprocess code exists. Invocation shape comes from **`08-NOTES-hyprland-from-root.md` §"Recommended approach"** (per-tick `$HIS` discovery, `runuser -u danitrrga -- env XDG_RUNTIME_DIR=/run/user/1000 HYPRLAND_INSTANCE_SIGNATURE=$HIS hyprctl clients -j`). |
| SIGKILL-by-pid kill (D-01) | process-control | command | No kill code exists. `kill -KILL <pid>` (root signals user pid). Dedup pids first (D-02). |
| Butler notification (D-05/D-06) | notification | command | No notify code exists. `notify-send`/`hyprctl notify` via the same `runuser` bridge; one summary toast per tick. |

**Planner guidance:** for the subprocess invocation shape, treat
`08-NOTES-hyprland-from-root.md` as the authoritative "reference pattern" (it is verified
against this machine). For *code structure* (read source → derive list → fold into summary,
defensive try/except, `_log` audit), copy `_missing_policies` + `tick()` as shown above.

---

## Runtime context (how the modified watchdog runs — for the planner)

- **Runs as root**, systemd **system** oneshot, one `tick()` per 60s timer fire:
  `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/systemd/nightguard-watchdog.service`
  (`Type=oneshot`, `Environment=NIGHTGUARD_DIR=/home/danitrrga/dev/Projects/LifeOS/nightguard`)
  + `.timer` (`OnUnitActiveSec=60`). This is why root can SIGKILL the user pid and why
  `systemctl --user stop` cannot disable native-kill (it lives in the root tick).
- The native-kill step must be **tick-shaped** (enumerate → match → kill → notify → return),
  not a persistent listener (08-NOTES; the event-listener is the deferred upgrade).
- Root reaches the user session via `CAP_DAC_OVERRIDE` traversal of `0700 /run/user/1000`
  — no perms change needed (08-NOTES §"Verified facts").

---

## Metadata

**Analog search scope:** `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/`
(guard.py, ngcommon.py, nightguard_watchdog.py, nightguard_ctl.py, nightguard.sudoers,
systemd/*), plus data source `/home/danitrrga/dev/Projects/LifeOS/nightguard/config.yaml`.
**Files scanned:** 7
**Subprocess/IPC grep:** 0 hits (confirms no native-kill analog exists in-codebase)
**Pattern extraction date:** 2026-06-23
