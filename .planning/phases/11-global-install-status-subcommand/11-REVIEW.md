---
phase: 11-global-install-status-subcommand
reviewed: 2026-06-25T17:47:31Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - ngtui/ngtui/__main__.py
  - ngtui/ngtui/backend.py
  - ngtui/ngtui/status.py
  - ngtui/tests/conftest.py
  - ngtui/tests/test_status_cli.py
findings:
  critical: 0
  warning: 4
  info: 2
  total: 6
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-06-25T17:47:31Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 11 adds a key-less `ngtui status [--json]` subcommand and an argv front-controller
in `__main__.py`, plus the non-blocking `cache_only_verdict` seam in `backend.py`. I
reviewed the four load-bearing properties the task called out and traced each across the
live trust stack (`guard.py` / `nightguard_ctl.py` / `ngcommon.py`).

**The security-critical properties hold.** Fail-closed behavior is correct on every path:
unknown verdict → `"locked"`, import/read failure → `"unavailable"`, and a cold time-cache
falls through to `"offline_blocked"` rather than ever showing the unlocked state. The
status path reads no key (verified by the `read_key_explodes` fixture + AST guard) and
performs no HMAC. I also verified two non-obvious correctness claims:

- **`tokens_left()` is genuinely non-blocking even though it runs OUTSIDE the
  `cache_only_verdict` seam.** `ctl.quota_decide` resolves the week-reset via
  `_current_week_monday()` → `datetime.now()` (local wall clock), never the
  network-touching `guard.true_unix()`. So the unwrapped `tokens_left()` call in `_status`
  cannot hang the Waybar poll. (Had it used `true_unix()`, this would have been a BLOCKER —
  worth a regression test to pin the invariant.)
- **The `cache_only_verdict` global-mutation seam is safe** because it is only ever called
  from `__main__._status` (a separate, single-threaded subprocess). The TUI process uses
  `backend.live_verdict` instead (`widgets/status.py`), so there is no concurrent
  `decide()` that the `guard._sntp` / `guard._http_time` swap could leak into. The
  save/swap/restore-in-`finally` is correct and re-raise-safe.

No BLOCKERs found. The findings below are robustness, fail-closed-presentation, and
quality issues.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: TTY guard checks only stdin — the documented "a pipe" case still spews escape codes

**File:** `ngtui/ngtui/__main__.py:42`
**Issue:** `_run_tui` guards on `sys.stdin.isatty()` only, but the module docstring (lines
10-11) explicitly promises that "a non-TTY launch (a Waybar exec, **a pipe**) fails with
`SystemExit(2)`". Textual renders to **stdout**, not stdin. For `ngtui | cat`, stdin is the
inherited terminal (isatty → True) while stdout is the pipe, so the guard does **not** fire
and Textual writes raw escape sequences into the pipe — exactly the failure mode the guard
is meant to prevent. The stdin-only check catches the headless/Waybar `exec` case (no
controlling terminal at all) but misses the stdout-redirected case named in the contract.
**Fix:**
```python
if not sys.stdin.isatty() or not sys.stdout.isatty():
    sys.stderr.write("ngtui must be run in an interactive terminal (TTY required on stdin+stdout).\n")
    raise SystemExit(2)
```

### WR-02: `UNAVAILABLE` reuses the OPEN glyph "○" for the fail-closed display

**File:** `ngtui/ngtui/status.py:55` (cf. `_VERDICT_LABEL` line 45)
**Issue:** `UNAVAILABLE = {"text": "○ —", "class": "unavailable"}` uses the hollow circle
`○`, which `_VERDICT_LABEL` assigns to `outside_curfew` → `("○", "OPEN")` — the *unlocked*
state. The whole point of `status.py` is fail-closed presentation (the docstring stresses
that an unknown verdict maps to `"locked"`, "never an optimistic `outside_curfew`"). Yet the
"I could not even ask the guard" object renders the same open-circle glyph as the unlocked
state. A late-night glance at the bar (the project's core adversary) could read the open
circle as "open/unlocked". The CSS `class` differs (`unavailable`), so styling *can* recover
the signal, but the glyph itself should fail closed visually to match the module's own
contract — use the filled `●` that `locked`/`clock_tamper`/`offline_blocked` already use.
**Fix:**
```python
UNAVAILABLE: dict[str, str] = {"text": "● —", "class": "unavailable"}
```

### WR-03: `sys.stdout.write` sits outside the broad-except — a BrokenPipe violates the always-exit-0 contract

**File:** `ngtui/ngtui/__main__.py:76`
**Issue:** SC-3 is "ALWAYS return 0 / never a traceback". The build-the-object work is inside
`try/except Exception`, but the actual `sys.stdout.write(...)` (line 76) is outside it. If the
reader closes the pipe (Waybar restart/kill mid-poll), the write raises `BrokenPipeError`,
which escapes uncaught as a traceback and a non-zero exit — the one statement that can break
the "always exit 0" guarantee. `BrokenPipeError` is an `OSError`, exactly the class the
function is otherwise careful to swallow.
**Fix:**
```python
    try:
        sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    except (BrokenPipeError, OSError):
        pass
    return 0
```

### WR-04: stack-dir pin validates only `nightguard_ctl.py` existence, not the modules actually imported

**File:** `ngtui/ngtui/backend.py:32-54`
**Issue:** `_resolve_stack_dir()` resolves `NIGHTGUARD_STACK_DIR`, then "PINs" it by
requiring `nightguard_ctl.py` to exist — and the comment (lines 21-28) claims it "Refuses to
import — and sudo-run — a substituted stack." But the existence check covers only one of the
three modules: lines 53-58 prepend `STACK_DIR` to `sys.path[0]` and then
`import ngcommon` / `import guard` / `import nightguard_ctl`. An actor who controls the env
var and can drop a directory containing a benign `nightguard_ctl.py` plus a malicious
`ngcommon.py` / `guard.py` passes the pin and still gets those modules imported (and
`sys.path[0]` is poisoned process-wide, never removed). The check is existence-only, not an
integrity/anchoring check, so the comment overstates the guarantee.
This is **not** a curfew-weakening boundary — the status path is advisory and key-less, and
the root watchdog remains authoritative — which is why it is a WARNING, not a BLOCKER. But
the same `STACK_DIR` feeds the `sudo` argv in `commit()` (lines 185-197), so the gap between
"a file exists" and "this is the trusted stack" is worth closing or, at minimum, not
overstating in the comment.
**Fix:** Either anchor to a fixed/owner-checked location instead of trusting the env value
for the import path, or down-scope the comment to what is actually enforced. A cheap
hardening step: assert the resolved dir (and the three module files) are owned by root/the
expected uid and are not group/world-writable before inserting on `sys.path`.

## Info

### IN-01: `_status`'s `args` parameter is never used — no arg validation

**File:** `ngtui/ngtui/__main__.py:50` (param), `:29` (call site passes `argv[1:]`)
**Issue:** `_status(args)` declares `args: list[str]` but never references it. `--json` is
documented as the only flag yet is ignored; so is everything else — `ngtui status --help`,
`ngtui status typo`, and `ngtui status` all emit the same JSON line and exit 0. This is
*consistent* with the "always exit 0, always emit JSON" robustness goal (a Waybar misconfig
shouldn't crash the bar), so it is not a bug — but the dead parameter reads like forgotten
flag handling, and silently accepting `--help`/typos can mask user error.
**Fix:** Either drop the parameter (`def _status() -> int`) to make "args are intentionally
ignored" explicit, or add a minimal allow-list (`{"", "--json"}`) that still exits 0 but
notes an unknown flag to stderr.

### IN-02: `UNAVAILABLE` is a shared mutable dict and omits the `tooltip` key

**File:** `ngtui/ngtui/status.py:55`; `ngtui/ngtui/__main__.py:64,74`
**Issue:** Two minor consistency points on the same object:
1. `obj = status.UNAVAILABLE` aliases a module-level mutable dict; `_status` currently only
   reassigns `obj` (never mutates in place), so it is safe today, but any future in-place
   edit of `obj` would silently corrupt the shared constant for the whole process.
2. The healthy `_shape` output is `{text, tooltip, class}` while `UNAVAILABLE` is
   `{text, class}` — no `tooltip`. Acceptable for Waybar (tooltip is optional), but the
   shape is inconsistent between branches.
**Fix:** Return a fresh dict (a small factory or `dict(status.UNAVAILABLE)`), and consider
adding a `tooltip` (e.g. `"nightguard status unavailable"`) so both branches share a shape.

---

_Reviewed: 2026-06-25T17:47:31Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
