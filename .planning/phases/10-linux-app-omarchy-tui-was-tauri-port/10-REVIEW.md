---
phase: 10-linux-app-omarchy-tui-was-tauri-port
reviewed: 2026-06-24T00:00:00Z
depth: deep
files_reviewed: 9
files_reviewed_list:
  - ngtui/ngtui/backend.py
  - ngtui/ngtui/app.py
  - ngtui/ngtui/__main__.py
  - ngtui/ngtui/theme.py
  - ngtui/ngtui/lineedit.py
  - ngtui/ngtui/widgets/status.py
  - ngtui/ngtui/widgets/edit.py
  - ngtui/ngtui/app.tcss
  - ngtui/spike/inline_sudo_spike.py
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: resolved
fixed:
  - CR-01
  - CR-02
  - WR-01
  - WR-02
  - WR-03
  - WR-04
  - WR-05
deferred:
  - IN-01
  - IN-02
  - IN-03
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-24
**Depth:** deep
**Files Reviewed:** 9
**Status:** resolved (2 critical + 5 warnings fixed; 3 info items deferred)

> **Resolution (2026-06-24):** All 2 critical and 5 warning findings fixed and
> committed atomically; the ngtui suite grew from 28 to 39 passing tests. The 3
> info items (IN-01..03) are deferred as cosmetic/non-load-bearing (no live
> injection path, advisory-only clock display, repo-clone ergonomics). Trust-model
> invariants preserved: the TUI still reads no key, computes no HMAC, re-emits no
> YAML, and the sudo commit argv shape is byte-identical.

## Summary

Phase 10 delivers the omarchy Textual TUI thin-client over the Python trust stack. The
security-critical invariants are mostly sound: the TUI never reads the HMAC key, never
calls `ngcommon.read_key()`, never computes an HMAC, and never emits YAML through a
serializer. `backend.commit()` uses a list-based argv with no `shell=True`, and
`mkstemp` produces a 0600 exclusive file. The classifier delegate chain (preview →
`classify_change`/`quota_decide` → signer) is correctly wired with no vendored logic.

Two blockers are present. The first is a malformed-TOML path that crashes the entire
app on startup (unhandled `tomllib.TOMLDecodeError` in `load_omarchy_theme`). The
second is a security-relevant issue: the script path passed into the sudo argv is read
from an environment variable (`NIGHTGUARD_STACK_DIR`) that is never validated, meaning
an attacker who can inject that variable at session start can redirect the sudo command
at a script the sudoers rule was not written for. Five warnings cover a silent staged-
edit discard bug, a navigation regression when `r` is pressed from the EditScreen, a
`WEEKLY_TOKENS` constant duplicated out of sync with the signer, a `_pending` attribute
not initialized in `__init__`, and an inaccurate grace-status display cell.

---

## Critical Issues

### CR-01: Unhandled `tomllib.TOMLDecodeError` crashes app on malformed colors.toml  — ✅ FIXED (5e15be7)

**File:** `ngtui/ngtui/theme.py:91-93` / `ngtui/ngtui/app.py:63`

**Issue:** `load_omarchy_theme()` wraps the `colors.toml` open+parse in a `try` that
catches only `(FileNotFoundError, IsADirectoryError)`. If `colors.toml` **exists but
is malformed**, `tomllib.load()` raises `tomllib.TOMLDecodeError` (a `ValueError`
subclass), which escapes the inner try block and propagates to the caller in `app.py`.
The caller's except is `(FileNotFoundError, OSError, KeyError)` — `ValueError` is not
in that tuple, so the exception is uncaught and the app crashes on `on_mount()` before
displaying anything.

The same hole applies to `alacritty.toml`: if that file is malformed, the fallback
branch (outside any try) raises `TOMLDecodeError` and it also propagates to the
`(FileNotFoundError, OSError, KeyError)` catch in the app, which still does not catch
`ValueError`.

This will trigger on any omarchy theme in transition (partial write during an atomic
dir-swap), since the dir-swap is non-atomic at the file level even though the symlink
flip is.

**Fix:**
```python
# theme.py: widen the inner except to cover parse errors
try:
    with open(colors_path, "rb") as fh:
        return _theme_from_colors(tomllib.load(fh))
except (FileNotFoundError, IsADirectoryError, tomllib.TOMLDecodeError, KeyError):
    pass

# ... fallback:
try:
    with open(alacritty_path, "rb") as fh:
        return _theme_from_alacritty(tomllib.load(fh))
except (FileNotFoundError, OSError, tomllib.TOMLDecodeError, KeyError):
    raise  # let the app-level handler decide

# app.py: widen to also cover ValueError
except (FileNotFoundError, OSError, KeyError, ValueError):
    pass
```

---

### CR-02: `NIGHTGUARD_STACK_DIR` env var controls the script path placed in the sudo argv  — ✅ FIXED (0214e8f)

**File:** `ngtui/ngtui/backend.py:19-27`, `ngtui/ngtui/backend.py:117-125`

**Issue:** `STACK_DIR` is taken directly from the `NIGHTGUARD_STACK_DIR` environment
variable with no validation. The resulting path is used in two places: (a) inserted
into `sys.path` so `nightguard_ctl` can be imported at module import time, and (b)
joined with `"nightguard_ctl.py"` to build the script argument passed to `sudo`:

```python
os.path.join(STACK_DIR, "nightguard_ctl.py"),  # argv[2] in the sudo call
```

If an attacker can set `NIGHTGUARD_STACK_DIR` before the process starts (e.g. via a
malicious `.env`, a compromised `.bashrc`, or a parent-process injection), the sudo
command will be invoked with a different script path. Whether this becomes a privilege
escalation depends entirely on how the sudoers `Cmnd_Alias` is written:

- If the alias pins the **exact** path (e.g.
  `NOPASSWD: /usr/bin/python3 /home/danitrrga/.../nightguard_ctl.py commit --from *`),
  sudo will refuse any other path and the impact is a denial-of-service only.
- If the alias uses a wildcard for the script argument (e.g.
  `NOPASSWD: /usr/bin/python3 * commit --from *`), an attacker can substitute any
  script and gain root execution.

The codebase does not document the required sudoers stanza with a concrete fixed path,
so the second form cannot be ruled out. Because the consequence if the wildcarded form
is used is root-code execution, this must be classified as a blocker.

Additionally, the same `STACK_DIR` path is prepended to `sys.path`, so a poisoned
`NIGHTGUARD_STACK_DIR` also controls which `ngcommon`/`guard`/`nightguard_ctl` modules
are imported, allowing the trust-stack import chain to be replaced silently.

**Fix:**
```python
import pathlib

_ALLOWED_STACK_DIR = pathlib.Path("/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard").resolve()

STACK_DIR = os.environ.get("NIGHTGUARD_STACK_DIR", str(_ALLOWED_STACK_DIR))
resolved = pathlib.Path(STACK_DIR).resolve()
if resolved != _ALLOWED_STACK_DIR:
    raise RuntimeError(
        f"NIGHTGUARD_STACK_DIR resolves to {resolved!r}, "
        f"which is not the sanctioned stack directory. "
        "Set NIGHTGUARD_STACK_DIR to the correct path or unset it."
    )
STACK_DIR = str(resolved)
```

Alternatively, remove the env-var override entirely and hard-code the canonical path,
accepting that portability is an operational concern rather than a runtime-injection
surface. If portability is required, document the exact required sudoers `Cmnd_Alias`
with a fixed script path so reviewers can verify the wildcard is not used.

---

## Warnings

### WR-01: `action_back` silently discards staged edits while lying to the user  — ✅ FIXED (8ba1308)

**File:** `ngtui/ngtui/widgets/edit.py:461-469`

**Issue:** When the user has staged edits and presses `Escape`, `action_back` displays
the message `"staged edits pending — press u to discard, then Escape to leave"` and
then **immediately clears `self._staged`** on line 467. On the next `Escape` the
screen pops. The instruction to "press u to discard" is incorrect — the discard already
happened on the first `Escape`. This means:

1. The user is told to take an action that is already done.
2. Staged edits that represented work (and potentially a loosen direction the user
   intended to review) are lost without an explicit confirmation.

The `_ConfirmDiscard` modal exists precisely for this purpose; the first-Escape path
should push it instead of silently clearing.

**Fix:**
```python
def action_back(self) -> None:
    if self._staged:
        # Show the discard confirmation gate rather than silently clearing.
        self.app.push_screen(_ConfirmDiscard(), self._on_back_discard)
        return
    self.app.pop_screen()

def _on_back_discard(self, discard: bool | None) -> None:
    if discard:
        self._staged.clear()
        self.app.pop_screen()
    # else: user said 'n' / Escape — stay on EditScreen with edits intact.
```

---

### WR-02: `action_refresh` pushes `StatusScreen` on top of `EditScreen` instead of replacing it  — ✅ FIXED (4cd2cb6)

**File:** `ngtui/ngtui/app.py:84-93`

**Issue:** `action_refresh` is bound at the App level and is accessible from all
screens (including `EditScreen`). Its implementation is:

```python
def action_refresh(self) -> None:
    if isinstance(self.screen, StatusScreen):
        self.pop_screen()
    self.push_screen(StatusScreen())
```

If `EditScreen` is the active screen, `isinstance` is `False`, so the `pop_screen`
is skipped and a new `StatusScreen` is pushed **on top** of `EditScreen`. The screen
stack becomes `[..., EditScreen, StatusScreen]`. Pressing `Escape` on the new
`StatusScreen` pops back to the stale `EditScreen` (with its pre-refresh base state)
rather than discarding it. This is a navigation regression: pressing `r` from the
edit surface produces confusing double-stack behaviour.

**Fix:**
```python
def action_refresh(self) -> None:
    # Replace whatever is on top with a fresh StatusScreen.
    if not isinstance(self.screen, StatusScreen):
        self.pop_screen()   # discard EditScreen / any other screen
    else:
        self.pop_screen()   # discard the existing StatusScreen
    self.push_screen(StatusScreen())
```

Or more simply, always pop then push, guarding against an empty stack:

```python
def action_refresh(self) -> None:
    if self.screen_stack:
        self.pop_screen()
    self.push_screen(StatusScreen())
```

---

### WR-03: `WEEKLY_TOKENS` duplicated in display modules, can drift from signer's constant  — ✅ FIXED (46e0bb2)

**File:** `ngtui/ngtui/widgets/status.py:28`, `ngtui/ngtui/widgets/edit.py:41`

**Issue:** Both `status.py` and `edit.py` define `WEEKLY_TOKENS = 3` as a module-level
literal. `backend.tokens_left()` correctly reads `ctl.WEEKLY_TOKENS` from the live
signer module, but the display logic in `confirm_copy()` (edit.py line 90) and
`token_meter()` (status.py lines 82-85) uses the local copies to compute `left`:

```python
# edit.py:90 — uses local WEEKLY_TOKENS=3
left = max(0, WEEKLY_TOKENS - spent_after)
```

If the signer's `ctl.WEEKLY_TOKENS` is ever changed to 2 (or any other value), the
`confirm_copy` line will tell the user "1 left" after a commit while the signer (and
`backend.tokens_left`) will report "0 left". The confirm gate — the load-bearing anti-
impulse surface — would show an incorrect post-commit token count.

**Fix:** Export `WEEKLY_TOKENS` through `backend.py` and import it in the display
modules:

```python
# backend.py — add after trust-stack import:
WEEKLY_TOKENS: int = ctl.WEEKLY_TOKENS

# status.py and edit.py — replace the local literals:
from ngtui.backend import WEEKLY_TOKENS
```

---

### WR-04: `_pending` attribute not initialized in `EditScreen.__init__`  — ✅ FIXED (d3b1a48)

**File:** `ngtui/ngtui/widgets/edit.py:246-254`, `ngtui/ngtui/widgets/edit.py:404-413`

**Issue:** `self._pending` is assigned in `action_edit_field` (lines 395, 401) and
read in `_on_inline_value` (line 407), but it is never declared in `__init__`. Under
normal flow the callback is always registered after `_pending` is set, so the bug is
latent. However:

- Any future refactor that calls `_on_inline_value` directly (e.g. in tests) will get
  an `AttributeError` on line 407 with no helpful message.
- The Textual framework's dismiss machinery is asynchronous; if a screen is dismissed
  in an unexpected order (e.g. during a race in tests or a future async path), the
  attribute read will fail.

**Fix:**
```python
def __init__(self) -> None:
    super().__init__()
    self._base_cfg = backend.sanctioned_config()
    self._base_text = backend.sanctioned_text()
    self._staged: list[tuple[str, str, str]] = []
    self._focus = 0
    self._pending: tuple[str, str, str] | None = None  # add this line
```

And guard the read:

```python
def _on_inline_value(self, value: str | None) -> None:
    if value is None or value == "" or self._pending is None:
        return
    op, dotted, kind = self._pending
    ...
```

---

### WR-05: `_grace_text` displays "◐ grace active" even when the grace window has expired  — ✅ FIXED (9394c32)

**File:** `ngtui/ngtui/widgets/status.py:280-284`

**Issue:** `_grace_text` checks only whether `state["grace"]` is truthy (i.e. a
non-empty dict), not whether the grace window is currently open:

```python
def _grace_text(self, state: dict) -> str:
    grace = state.get("grace")
    if not grace:
        return "grace unavailable today"
    return "◐ grace active"
```

The `state["grace"]` dict is written by the signer when grace is **activated** and
persists (with `window_end`) until the next day's reset. After the grace window closes
the dict is still present but `window_end` is in the past. The GRACE row in the KV
panel will show "◐ grace active" even though the actual verdict (from `live_verdict`)
is "locked" or "outside_curfew". A user who looks at the GRACE row in isolation will
believe a grace bypass is available when it is not.

**Fix:** Cross-reference `window_end` against the current time:

```python
def _grace_text(self, state: dict) -> str:
    grace = state.get("grace")
    if not grace:
        return "grace unavailable today"
    end = grace.get("window_end")
    if end is not None:
        try:
            from datetime import datetime, timezone
            target = datetime.fromtimestamp(float(end), tz=timezone.utc)
            if target <= datetime.now(tz=timezone.utc):
                return "grace used today"
        except (ValueError, TypeError, OSError):
            pass
    return "◐ grace active"
```

---

## Info

### IN-01: `set_scalar` / `list_add` do not reject values containing newlines  — ⏭️ DEFERRED (cosmetic)

**File:** `ngtui/ngtui/lineedit.py:142-151`, `ngtui/ngtui/lineedit.py:192-205`

**Issue:** `set_scalar` and `list_add` do no validation on the `value` argument. A
value containing `\n` followed by valid YAML will inject extra lines into the proposed
text. For example:

```python
list_add(text, "curfew.allow_commands", "/ok\n  rogue_key: evil")
# produces:   - /ok
#               rogue_key: evil
```

In practice Textual's `Input` widget is single-line and will not deliver a newline from
keyboard input, so this is not a live injection path. It is still a latent API hazard:
any caller that passes a programmatic string (e.g. a future clipboard-paste feature)
could produce malformed YAML. The signer will reject files that fail its schema
validation, so the trust guarantee holds, but the proposed text passed to
`backend.preview_change` could produce confusing classifier output.

**Suggestion:** Add a guard at the top of `set_scalar` and `list_add`:

```python
if "\n" in str(value):
    raise ValueError(f"value must be a single line; got newline in {value!r}")
```

---

### IN-02: `_remaining_to_hhmm` uses naive local time, ignoring the config timezone  — ⏭️ DEFERRED (cosmetic)

**File:** `ngtui/ngtui/widgets/status.py:234-249`

**Issue:** `_remaining_to_hhmm` calls `datetime.now()` (no `tz=` argument) to
compute how many seconds remain until the curfew `end` wall time. The config stores a
`timezone` field (e.g. `Europe/Amsterdam`). If the system clock's local timezone
differs from the config timezone (e.g. system set to UTC while the curfew timezone is
CET/CEST), the countdown will be off by the UTC offset (up to several hours). The
advisory label "curfew until HH:MM" would show the correct wall time from the config,
but the countdown number would be wrong.

This is advisory-only (the guard enforces time independently), but a user who trusts
the countdown to plan around curfew end could be misled.

**Suggestion:**
```python
import zoneinfo
tz = zoneinfo.ZoneInfo(cfg.get("timezone") or "Europe/Amsterdam")
now = datetime.now(tz=tz)
target = now.replace(hour=eh, minute=em, second=0, microsecond=0)
```

(Requires passing `cfg` into `_remaining_to_hhmm`.)

---

### IN-03: Hardcoded author machine path in spike and test bootstrap  — ⏭️ DEFERRED (cosmetic)

**File:** `ngtui/spike/inline_sudo_spike.py:18`, `ngtui/tests/test_lineedit.py:25`,
`ngtui/tests/conftest.py:14-17`

**Issue:** Several files hard-code `/home/danitrrga/dev/Projects/LifeOS/...` as the
fallback path. The env-var bootstrap in `backend.py` already documents this pattern
and the spike is not production code, so this is a cosmetic issue for the publishable
repo. Anyone cloning this repo and running the tests without setting
`NIGHTGUARD_STACK_DIR` will get a `ModuleNotFoundError` from the conftest rather than
a clean "missing environment variable" message.

**Suggestion:** In `tests/conftest.py`, if the stack directory does not exist, emit a
`pytest.skip` with a human-readable message rather than letting the import fail
downstream with a cryptic path error:

```python
import pathlib
stack = pathlib.Path(os.environ.get("NIGHTGUARD_STACK_DIR", ""))
if not stack.is_dir():
    pytest.skip(
        "NIGHTGUARD_STACK_DIR not set or not found; "
        "set it to the nightguard scripts directory to run integration tests.",
        allow_module_level=True,
    )
```

---

_Reviewed: 2026-06-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
