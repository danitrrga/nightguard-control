# Phase 9: StayFree Desktop - Pattern Map

**Mapped:** 2026-06-23
**Files analyzed:** 2 (1 code edit, 1 spike artifact/notes) — both **gated on the D-09 spike PASS**
**Analogs found:** 2 / 2 (both in-repo)

> **GATING NOTICE (read first).** Per D-09 + RESEARCH, this entire phase is **spike-first,
> branch-on-result**. The *only* unconditional deliverable is the spike (Wave 0) + its recorded
> result. The code edit below (`nightguard_watchdog.py` keep-alive step) is **built ONLY if the
> spike PASSes** (StayFree actively blocks native Wayland apps on Hyprland). RESEARCH predicts
> FAIL/fallback with HIGH confidence. On FAIL: do NOT build the keep-alive — StayFree becomes
> analytics-only, Phase 8 native-kill stays primary, and `09-CONTEXT.md` re-opens. The planner
> must place every pattern in this doc behind a spike-PASS gate.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `LifeOS/scripts/nightguard/nightguard_watchdog.py` (MODIFY — add keep-alive step in `tick()`) | watchdog / supervisor | event-driven (per-tick check-then-act) | same file's existing browser-policy check step + `08-NOTES` runuser bridge | exact (in-file) for shape; verified-design for the bridge |
| `.planning/phases/09-stayfree-desktop/09-spike-*.md` (NEW — spike result notes; Wave 0) | notes / doc artifact | n/a (manual observable record) | `.planning/phases/08-native-blocker/08-NOTES-hyprland-from-root.md` | exact (sibling phase-notes pattern) |

**No new source files are created.** RESEARCH "Don't Hand-Roll" and "Key insight" are explicit: the
runuser bridge and the `tick()` host already exist; the real work is ~15 lines folded into `tick()`
(IF PASS) plus the spike decision. No new systemd service/timer (D-03: a `--user` service would be
user-stoppable, defeating the whole point).

## Pattern Assignments

### `nightguard_watchdog.py` — new keep-alive step in `tick()` (watchdog/supervisor, event-driven) — **ONLY IF SPIKE PASS**

**Analog A (the in-file shape):** the existing browser-policy check step inside the same `tick()`.
**Analog B (the launch bridge):** the verified-but-not-yet-coded runuser bridge in `08-NOTES-hyprland-from-root.md`.

> **IMPORTANT for the planner — the Phase 8 native-kill does NOT exist in live code yet.**
> Grep of `LifeOS/scripts/nightguard/*.py` for `runuser|hyprctl|pgrep|SIGKILL|HYPRLAND` returns
> **nothing** (only `config.yaml` blacklist keys in `nightguard_ctl.py`). The Phase 8
> enumerate→kill step described in `08-CONTEXT.md` is itself still *planned* — its only artifact
> is the proven bridge command in `08-NOTES`. So the keep-alive cannot "copy the Phase 8 kill
> step from code"; it copies (a) the **in-file tick()-step shape** from the live browser-policy
> check and (b) the **bridge invocation** from the `08-NOTES` proof command.

**Imports / module setup pattern** (`nightguard_watchdog.py` lines 16-28) — what the keep-alive adds to:
```python
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ngcommon as ng
import guard

LOG = os.path.join(ng.NIGHTGUARD_DIR, "watchdog.log")
POLICY_PATHS = [ ... ]
```
The keep-alive step needs `import subprocess` added here. It does **not** need `guard` for the
verdict (CONTEXT/RESEARCH lean "every tick" — StayFree's own schedule governs *when* it blocks, so
no curfew gate; see Pitfall 7 — avoids the Phase 8 D-09 double-revert hazard entirely).

**Core "tick-shaped check-then-act" pattern — copy this exact shape** (`nightguard_watchdog.py` lines 37-52, the `_missing_policies` helper + lines 63-70 its call site):
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
**Why this is the analog:** it is a self-contained helper that (1) reads a config sub-tree with the
`(cfg.get("x") or {}).get("y")` null-safe idiom, (2) respects an `enabled` flag (early-return
`[]`), (3) does a side-effect-free check, and (4) returns a result the caller folds into the single
tick log line. The keep-alive is the **same module-level helper + fold-into-tick** structure:
a `_stayfree_running()` probe (RESEARCH lines 113-117) and a `_respawn_stayfree(his)` launcher
(RESEARCH lines 119-123), called from `tick()` and reported via the existing `parts`/`_log` channel.

**Probe pattern** (from RESEARCH lines 113-125 — runs as root, NO bridge needed; the global pid
namespace is visible to root). Match the binary **path**, not bare `comm` (Electron forks children;
Pitfall 2):
```python
import subprocess
def _stayfree_running():
    r = subprocess.run(["pgrep", "-f", "/usr/bin/stayfree"], capture_output=True)
    return r.returncode == 0
```

**$HIS discovery + runuser launch bridge** (from `08-NOTES` lines 12-13, 23, 34 + RESEARCH lines 89-92, 108-123).
**Re-discover `$HIS` every tick — never cache** (it rotates on each Hyprland restart; `08-NOTES`
line 13). Only the *launch* uses the bridge:
```python
# $HIS = the single dir name under /run/user/1000/hypr/ ; root traverses the 0700
# dirs via CAP_DAC_OVERRIDE (08-NOTES lines 11-12). No-Hyprland -> no-op (skip).
HIS = ...  # ls /run/user/1000/hypr -> the one subdir name; skip respawn if absent
RUNUSER = ["runuser", "-u", "danitrrga", "--",
           "env", "XDG_RUNTIME_DIR=/run/user/1000",
           f"HYPRLAND_INSTANCE_SIGNATURE={HIS}"]
if HIS and not _stayfree_running():
    subprocess.Popen(RUNUSER + ["/usr/bin/stayfree"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    _log("keep-alive: respawned StayFree")
```
The live-proof shape (`08-NOTES` line 34) the planner can adapt for the spike's manual respawn gate
(RESEARCH line 251):
```bash
sudo sh -c 'HIS=$(ls /run/user/1000/hypr); runuser -u danitrrga -- env \
  XDG_RUNTIME_DIR=/run/user/1000 HYPRLAND_INSTANCE_SIGNATURE=$HIS /usr/bin/stayfree &'
```
Consider `APPIMAGELAUNCHER_DISABLE=1` in the env if appimagelauncherd intercepts (Pitfall 3 / RESEARCH line 215).

**Logging pattern — reuse verbatim** (`nightguard_watchdog.py` lines 31-34 + the `parts`/`_log` fold at lines 65-70):
```python
def _log(msg):
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (ts, msg))
# ... in tick():  parts.append("keep-alive: respawned StayFree")  -> single line per tick
```
Prefer folding the keep-alive outcome into the **existing single `parts`/`_log("tick: ...")` line**
(lines 65-70) rather than a second log call, matching how `reverted` and `missing` are reported.

**Error handling pattern** (`nightguard_watchdog.py` lines 59-62) — the file swallows config-read
failures and degrades to `cfg = {}`; the keep-alive should be similarly fail-soft (a failed
probe/launch must never hang the oneshot — Anti-pattern "persistent supervisor loop", RESEARCH line 128):
```python
try:
    cfg = ng.yaml_load(ng.file_bytes(ng.CONFIG).decode("utf-8"))
except Exception:
    cfg = {}
```

**Insertion point:** inside `tick()` (lines 55-70), as a new step **after** the browser-policy
`missing` check and **before** the final `_log`. Per `09-CONTEXT` integration note, it sits next to
the (planned) Phase 8 native-kill step; order vs that step is a planning detail. The keep-alive is
**simpler** than the planned Phase 8 step — its probe needs no bridge (root pid view), only the
launch does.

---

### `09-spike-*.md` — spike result notes (Wave 0, doc artifact) — **UNCONDITIONAL (this is the gate itself)**

**Analog:** `.planning/phases/08-native-blocker/08-NOTES-hyprland-from-root.md`

**Structure to copy** (`08-NOTES` lines 1-9, 9-16, 38-49): `# Phase N — <title>` heading with a
**Status / date / what-it-de-risks** line, a "Verified facts (this machine, date)" bullet block,
a "Recommended approach" section, an "Edge cases" list, and a one-line "## Verdict". The spike notes
should follow the same observable-record format: record install behavior, login, tracking test,
**blocking test (the D-09 decision)**, website-block test (RESEARCH lines 152-157), then a decisive
**PASS / FAIL / PARTIAL verdict** (RESEARCH lines 160-166) that gates the code edit above.

The read-only PoC pattern from `09-spike-sf_extract.py` (already in the phase dir) is the model for
any spike helper script: `#!/usr/bin/env python3` + a docstring stating **"Read-only."** + plain
`print()` of an observable verdict. Do not write a leveldb scraper for TRAK-02 (RESEARCH line 184 —
acceptable v1 = "view in StayFree UI").

---

## Shared Patterns

### root→user-session launch bridge (the one reusable mechanism)
**Source:** `.planning/phases/08-native-blocker/08-NOTES-hyprland-from-root.md` lines 11-13, 23, 34
**Apply to:** the keep-alive **respawn launch only** (NOT the probe).
```
runuser -u danitrrga -- env XDG_RUNTIME_DIR=/run/user/1000 \
  HYPRLAND_INSTANCE_SIGNATURE=$HIS  <command>
```
Invariants (hard): re-discover `$HIS` each tick (rotates on Hyprland restart); root traverses the
`0700 /run/user/1000{,/hypr}` dirs via CAP_DAC_OVERRIDE (no chmod); no-Hyprland → no-op skip.

### per-tick check-then-act (never a loop)
**Source:** `nightguard_watchdog.py` `tick()` (lines 55-70) + `_missing_policies` (lines 37-52)
**Apply to:** the keep-alive step.
The watchdog is a **systemd system oneshot** — one `tick()` per fire, then exit. Keep-alive must be
check-then-act, never `while True` (would hang the oneshot). Dedup via the `pgrep` probe before
launch (D-04 / RESEARCH Anti-patterns) so no duplicate StayFree instances.

### single-line tick logging
**Source:** `nightguard_watchdog.py` `_log` (lines 31-34) + `parts` fold (lines 65-70)
**Apply to:** every step in `tick()`, incl. keep-alive — append to `parts`, emit one `tick: …` line.

### null-safe config sub-tree access
**Source:** `nightguard_watchdog.py` line 38 — `(cfg.get("blocking") or {}).get("browser_extension") or {}`
**Apply to:** any config-driven gating the keep-alive adds (e.g. an `enabled` flag), if introduced.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | Both deliverables have strong in-repo analogs. No StayFree-specific or analytics-export code is in scope (RESEARCH: TRAK-02 = "view in StayFree UI", no scraper). |

**Notable absence (not a file, but flag for the planner):** there is **no existing `runuser`/`pgrep`/
`hyprctl` code anywhere in the live nightguard stack** — the Phase 8 native-kill that `09-CONTEXT`
calls the "closest analog" is *itself still unbuilt*. The keep-alive's executable analog is therefore
the **browser-policy step shape** (in-file) + the **`08-NOTES` proof command** (verified design),
not copy-paste from a shipped kill step.

## Metadata

**Analog search scope:** `LifeOS/scripts/nightguard/*.py` (ngcommon, guard, nightguard_ctl,
nightguard_watchdog), `.planning/phases/08-native-blocker/`, `.planning/phases/09-stayfree-desktop/`.
**Files scanned:** 4 Python sources + 3 phase docs + 1 memory note.
**Key verifications:** (1) `nightguard_watchdog.py` `tick()` read in full — keep-alive insertion
point confirmed (after policy check, before final `_log`); (2) grep confirmed **no live
runuser/hyprctl/pgrep/SIGKILL code exists** — Phase 8 kill is still planned; (3) `08-NOTES` bridge
command is the verified launch pattern.
**Pattern extraction date:** 2026-06-23
