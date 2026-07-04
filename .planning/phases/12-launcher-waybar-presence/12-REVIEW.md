---
phase: 12-launcher-waybar-presence
reviewed: 2026-07-04T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - ngtui/ngtui/backend.py
  - ngtui/tests/test_backend_signal.py
  - ngtui/tests/test_installer_idempotent.py
  - ngtui/tests/fixtures/config.jsonc
  - ngtui/tests/fixtures/hyprland.conf
  - ngtui/tests/fixtures/style.css
  - ngtui/.gitignore
  - packaging/omarchy/install.sh
  - packaging/omarchy/bin/ngtui-menu
  - packaging/omarchy/hypr/nightguard.windowrule.conf
  - packaging/omarchy/icons/nightguard.svg
  - packaging/omarchy/nightguard.desktop
  - packaging/omarchy/waybar/custom-nightguard.jsonc
  - packaging/omarchy/waybar/style-nightguard.css
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-07-04
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Reviewed the Phase 12 omarchy launcher/Waybar-presence surface: the `ngtui` backend
seam, the author-facing installer, the read-only right-click menu, the Waybar/Hyprland
artifacts, and the two new test modules.

I traced the three security-sensitive surfaces called out in the task and **confirmed
they hold** — this was verified, not assumed:

1. **Commit fail-safe (BAR-04/D-11).** `backend.commit()` gates the `pkill -RTMIN+11
   waybar` refresh strictly on `proc.returncode == 0`, and the swallow-all try/except
   around the signal means a raising/absent `pkill` cannot perturb the returned
   `{returncode, stdout}`. I checked the *signer's* contract too: `nightguard_ctl.cmd_commit`
   returns `1` on `REFUSED` (quota-denied) — so a refused commit exits non-zero and the
   bar genuinely never flips. The signal path is correct.
2. **Installer idempotency / comment preservation (D-07/T-12-11).** The marker guard,
   backup-first `cp -a`, and text-only (never jq) JSONC merge behave as specified; the
   idempotency test suite passes (3/3), including the inline-array live-config shape.
3. **Menu read-only (BAR-03).** `ngtui-menu` exposes only open-the-TUI actions — no
   loosen/commit/grace/token mutation. The anti-self guarantee is intact.

No BLOCKER-class defect is provable in these files. The findings below are real, but
they are coupling/robustness/quality issues, not correctness or security breaks. I did
not manufacture a Critical to appear thorough.

## Warnings

### WR-01: `cache_only_verdict` reaches into private cross-repo internals and mutates module globals

**File:** `ngtui/ngtui/backend.py:129-142`
**Issue:** The non-blocking status path monkeypatches `guard._sntp` and
`guard._http_time` — *private* (`_`-prefixed) names owned by a separate repo
(`LifeOS/scripts/nightguard/guard.py`) that this repo imports at runtime. This
save/patch/restore of module globals is the *only* thing preventing the ~4s cold-cache
network fall-through from hanging the 30s Waybar poll (documented DESK-02/Pitfall 1). It
is silently coupled to undocumented internals: a rename or refactor in `guard.py` (e.g.
`_sntp` → `_query_ntp`, or moving the `for fn in ((lambda: _sntp(...)...))` dispatch)
would either (a) reintroduce the 4s hang undetected, or (b) raise `AttributeError` at
line 129 and crash `ngtui status --json` (degrading the bar to `unavailable`). The mutation
is also non-reentrant — if two verdict computations ever overlap, one `finally`-restore
clobbers the other. (Today the status reader is a separate short-lived process, so the
concurrency angle is latent, not live.)
**Fix:** Prefer a supported seam over private-global patching, e.g. a keyword flag through
`curfew_verdict`/`true_unix` (`offline_only=True`) added upstream in `guard.py`, or read a
pre-fetched `.timecache` directly. At minimum, guard the coupling explicitly:
```python
for name in ("_sntp", "_http_time"):
    if not hasattr(guard, name):
        raise RuntimeError(
            f"cache_only_verdict: guard.{name} missing — the non-blocking status "
            "seam is out of sync with the trust stack; refusing to risk a blocking poll."
        )
```
so a drift fails loud at the seam instead of silently reintroducing a hang.

### WR-02: Installer backup filename has 1-second granularity — a sub-second re-run can overwrite the pristine backup

**File:** `packaging/omarchy/install.sh:70` and `:99`
**Issue:** Backups are named `"$f.bak.$(date +%s)"`. If the installer runs, is
interrupted/edited so the marker is removed, and is re-run within the same wall-clock
second, the second `cp -a` writes to the identical `.bak.<epoch>` path and overwrites the
*original* backup with the already-mutated file — losing the only pristine copy. The
"backup-first" data-loss protection is defeated in that (narrow) window. The idempotency
test only asserts *at least one* `.bak.*` exists, so it does not catch this.
**Fix:** Add sub-second/nonce entropy and never clobber:
```bash
local bak="$f.bak.$(date +%s).$$"
[ -e "$bak" ] && bak="$bak.$RANDOM"
cp -a "$f" "$bak"
```

### WR-03: Waybar-config merge anchors are brittle — valid configs abort the whole installer

**File:** `packaging/omarchy/install.sh:113`, `:145`, `:158`, `:163`
**Issue:** Two structural assumptions can make the installer `exit 1` on a perfectly valid
config: (a) step (a) requires a *brace-only* root line (`^[[:space:]]*{[[:space:]]*$`), so a
config whose root object opens inline (`{ "layer": "top", ...`) yields "no root '{' line"
and aborts; (b) the inline membership `sed` matches only a comma-terminated `"clock",`
(`s@"clock",[[:space:]]*@...@`), so an inline `modules-center` where `clock` is the last or
sole element (`[..., "clock"]` / `["clock"]`) matches the `inline_line` grep but the `sed`
substitutes nothing, then the fail-loud recheck at :168 aborts. Failing closed/loud is the
right posture, but the anchor is coupled to one exact hand-format of the author's live file;
any reasonable reformat bricks the installer. Since this only ever runs against the author's
own config the blast radius is small, but it is fragile.
**Fix:** Broaden step (a) to also accept a same-line root object, and make step (b) tolerate
`clock` as the terminal array element (match `"clock"` optionally followed by `,` or `]` and
reinsert the correct separator), or anchor on the opening `[` of `modules-center` rather than
on the `clock` element specifically.

### WR-04: `ngtui-menu` aborts under `set -e` if `ngtui status` emits invalid JSON with exit 0

**File:** `packaging/omarchy/bin/ngtui-menu:9,16-17`
**Issue:** Line 13 fails closed only when `ngtui status --json` *exits non-zero*
(`|| echo '{...}'`). If the status shim ever exits 0 while printing malformed JSON, the
`python3 -c 'json.load(...)'` on line 16 raises → the pipeline exits non-zero → under
`set -euo pipefail` the `tooltip="$(...)"` assignment aborts the whole script, so the
right-click menu silently never renders (no error to the user). The two separate
`python3` parses also double the exposure.
**Fix:** Parse once, defensively, and never let a parse failure kill the script:
```bash
read -r text tooltip < <(printf '%s' "$json" | python3 -c '
import sys, json
try: d = json.load(sys.stdin)
except Exception: d = {}
print(d.get("text","○ —"), d.get("tooltip",""), sep="\t")' ) || { text="○ —"; tooltip=""; }
```

## Info

### IN-01: Author's absolute home paths hardcoded as defaults in the "clean, publishable" repo

**File:** `ngtui/ngtui/backend.py:29,51`
**Issue:** `_DEFAULT_STACK_DIR = "/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard"`
and the `NIGHTGUARD_DIR` default leak the author's machine layout into the repo CLAUDE.md
designates as "the clean, publishable product." A fresh clone with the env unset fails
closed via the `_resolve_stack_dir()` RuntimeError (good), but the personal path should not
ship as the baked-in default.
**Fix:** Default to a repo-relative or XDG path (or leave unset and require the env), and
keep the personal path only in the author's LifeOS instance config.

### IN-02: `yaml_load(proposed_text)` has no error handling in the preview path

**File:** `ngtui/ngtui/backend.py:153` (also `preview_change`)
**Issue:** `ng.yaml_load(proposed_text)` on unparseable proposed YAML raises an uncaught
exception into the TUI's preview flow. The commit path tolerates a bad edit (the signer
rejects it), but the *preview* will surface a raw traceback instead of a friendly
"invalid YAML" state.
**Fix:** Wrap the parse and return a structured error (e.g. `{"error": "..."}`) the TUI can
render, rather than propagating the exception.

### IN-03: `.gitignore` excludes `uv.lock`, undermining reproducible tool installs

**File:** `ngtui/.gitignore:4`
**Issue:** The tool is installed via `uv tool install` (per install.sh's prereq message),
but ignoring `uv.lock` means dependency versions are unpinned across installs — a
reproducibility gap for a security-adjacent tool. (Commit `2c0ffef` added this
deliberately; flagging as a tradeoff to reconsider, not a mistake.)
**Fix:** Commit `uv.lock` for the application to pin the resolved dependency set.

---

_Reviewed: 2026-07-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
