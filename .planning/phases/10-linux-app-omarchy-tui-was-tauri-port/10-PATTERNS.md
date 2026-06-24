# Phase 10: Linux App — omarchy TUI thin-client - Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 7 new TUI files (greenfield package)
**Analogs found:** 7 / 7 (all map to the live Python trust stack — no TUI precedent exists, but every seam the TUI needs already exists as an importable backend function or a fixed subprocess contract)

> **Greenfield note.** Phase 10 creates a brand-new Python Textual package (`ngtui/`). There is **no prior TUI** in either repo, so there is no same-role analog for the Textual widgets/screens themselves — those follow the official Textual docs cited in RESEARCH Patterns 1–6 and the layout in UI-SPEC. **The load-bearing analogs are the backend modules the TUI imports/shells**, in the separate LifeOS repo at `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/`. The correctness of this phase is "import, never re-implement" (RESEARCH "Don't Hand-Roll"). Every excerpt below is the real function signature / contract the TUI must call, not a Textual idiom.

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `ngtui/backend.py` | service (adapter) | request-response (subprocess) + transform | `nightguard_ctl.py` (`classify_change`, `quota_decide`, `cmd_commit` argv) + `ngcommon.py` (`load_state`, `yaml_load`, paths) + `guard.py` (`curfew_verdict`) | exact (it imports these) |
| `ngtui/theme.py` | utility (theme loader + watcher) | file-I/O + event-driven (poll/watch) | RESEARCH Pattern 4 (`colors.toml` → Textual `Theme`); RESEARCH "Detecting a theme change" poll snippet | role-match (no codebase analog — external file format) |
| `ngtui/app.py` | controller (App + BINDINGS + screens) | event-driven (key bindings) | RESEARCH Pattern 5 (`suspend()` commit) + Pattern 6 (`BINDINGS`); UI-SPEC keybinding map | role-match (Textual idiom, no codebase analog) |
| `ngtui/widgets/status.py` | component (read-only status hero/meter/grace/ledger) | read-only display | `guard.curfew_verdict` (verdict strings) + `ngcommon.load_state` (state dict) | role-match (consumes backend) |
| `ngtui/widgets/edit.py` | component (edit panel + per-field line-edit + preview) | transform + read-only preview | `nightguard_ctl.classify_change`/`is_loosening`/`quota_decide`; Windows edit-view per-field **line-edit** pattern (STATE.md Phase 4 04-05) | role-match (consumes backend) |
| `ngtui/__main__.py` | entry point | bootstrap | `nightguard_ctl.py` / `guard.py` `main()` + `sys.path.insert` import bootstrap (lines 24-25 / 36-37) | exact (same sys.path bootstrap) |
| `pyproject.toml` | config | — | RESEARCH "Recommended Project Structure" (textual + optional watchfiles, entry point) | role-match (no codebase analog — first Python package here) |

---

## Pattern Assignments

### `ngtui/backend.py` (service adapter — the single seam to the trust stack)

**Analogs:** `ngcommon.py`, `nightguard_ctl.py`, `guard.py` (all at `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/`).

**CRITICAL — do not vendor. Import the live modules.** RESEARCH "Backend import strategy (load-bearing)": set env + `sys.path` then import the real modules so the preview can never drift from the signer.

**Import bootstrap pattern** — copy from `guard.py` lines 24-25 / `nightguard_ctl.py` lines 36-37:
```python
import os, sys
# Make the LifeOS path configurable (RESEARCH Open Q1) — env override, hardcoded default = author instance.
STACK_DIR = os.environ.get("NIGHTGUARD_STACK_DIR",
                           "/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard")
os.environ.setdefault("NIGHTGUARD_DIR",
                      os.environ.get("NIGHTGUARD_DIR", "/home/danitrrga/dev/Projects/LifeOS/nightguard"))
sys.path.insert(0, STACK_DIR)
import ngcommon as ng          # key-less reads, paths, yaml_load
import guard                   # curfew_verdict
import nightguard_ctl as ctl   # classify_change, is_loosening, quota_decide, WEEKLY_TOKENS
```

**Read-path signatures (key-less, side-effect-free — verified at import only define functions, A4):**
```python
# ngcommon.py:68-73 — raw guard.json dict; {} on missing/garbled. PREFER over shelling `show` (Pitfall 2).
state = ng.load_state()
#   state.get("weekly_spent", 0)  -> int
#   state.get("week_anchor", "")  -> "YYYY-MM-DD" Monday  (ngcommon STATE_FIELDS, line 29)
#   state.get("grace")            -> None | {date, window_start, window_end}
#   state.get("ledger", [])       -> [{ntp_timestamp:int, fields:[label,...]}]   (built in cmd_commit:341)
#   state.get("config_hmac","")   -> hex str (display only — TUI cannot recompute, no key)
#   state.get("state_hmac","")    -> hex str (display only)

# ngcommon.py:133 — the ONLY config parser; sign+verify share it. Use for current values + edit base.
cfg = ng.yaml_load(ng.file_bytes(ng.SANCTIONED).decode("utf-8"))   # SANCTIONED is the diff base (Pitfall 5)
# ngcommon paths (lines 21-26): ng.CONFIG, ng.SANCTIONED, ng.STATE  — all absolute, from NIGHTGUARD_DIR
```

**Lock-status verdict (authoritative, key-less)** — `guard.py:224-278`:
```python
verdict = guard.curfew_verdict(cfg, state)
# returns exactly ONE of:
#   "locked" | "grace_active" | "outside_curfew" | "clock_tamper" | "offline_blocked"
# NOTE: side-effect-free, no key param. Caller worst-cases state itself; for DISPLAY the TUI
# reads grace as-is (it has no key to verify state_hmac — verdict is advisory, UI-SPEC "State unverifiable").
# DO NOT recompute curfew math in the TUI (Anti-Pattern: "never app-local optimism").
```

**Preview-path signatures (no key, no crypto — D-07)** — `nightguard_ctl.py:202-260`:
```python
old_doc = ng.yaml_load(ng.file_bytes(ng.SANCTIONED).decode("utf-8"))  # base = SANCTIONED, not live (Pitfall 5)
new_doc = ng.yaml_load(proposed_text)
dirs = ctl.classify_change(old_doc, new_doc)   # -> [(label, "loosen"|"tighten"|"noop"), ...]  (line 202)
loosening = ctl.is_loosening(dirs)             # -> bool                                        (line 225)
tzname = new_doc.get("timezone") or old_doc.get("timezone") or "Europe/Amsterdam"
decision = ctl.quota_decide(dirs, ng.load_state(), tzname)  # (line 241)
# decision dict keys (verified lines 248-260):
#   allowed:bool  reason:str|None  costs_token:bool  is_noop:bool  effective_spent:int  week_anchor:str
# ctl.WEEKLY_TOKENS == 3 (line 40) -> render (WEEKLY_TOKENS - effective_spent) filled dots.
```

**Lazy week-reset for the meter (Pitfall 4)** — `quota_decide` already does this internally (`nightguard_ctl.py:245-246`); the TUI gets the corrected count for free by reading `decision["effective_spent"]` (call `quota_decide` with empty/`[]` dirs to read it without classifying), OR replicate `_current_week_monday` (lines 231-238). Do **not** display the raw `weekly_spent` — it is stale until the next commit.

**Commit-path subprocess (the write seam, D-08)** — argv **mandated by sudoers** `nightguard.sudoers:20-22`:
```python
import subprocess, tempfile, os
CTL = os.path.join(STACK_DIR, "nightguard_ctl.py")
fd, tmp = tempfile.mkstemp(suffix=".yaml")        # 0600 exclusive (V5/Tampering mitigation)
os.write(fd, proposed_text.encode("utf-8")); os.close(fd)
# argv MUST be exactly this shape or sudoers won't match (RESEARCH Pattern 5, sudoers line 21):
#   ["sudo", "/usr/bin/python3", "<abs>/nightguard_ctl.py", "commit", "--from", tmp]
proc = subprocess.run(["sudo", "/usr/bin/python3", CTL, "commit", "--from", tmp],
                      stdout=subprocess.PIPE, text=True)   # leave stderr ATTACHED to TTY (Pitfall 3 fingerprint)
os.unlink(tmp)
# NEVER shell=True. No interpreter path other than /usr/bin/python3 (won't match Cmnd_Alias).
```

**Exit/stdout contract — map verbatim, never fabricate (verified `nightguard_ctl.py:332-348`):**
| Exit | Stream | Text | UI-SPEC role |
|------|--------|------|--------------|
| 0 | stdout | `committed (<dir><, free \| -1 token>): config_hmac=… \| tokens N/3 used` (346-348) | `$success` |
| 0 | stdout | `no-op: proposed config is identical to sanctioned; nothing written.` (335) | `$text-muted` |
| 1 | stderr | `REFUSED (<direction>): <reason>` e.g. `weekly loosen quota exhausted (3/3 used); available again Monday` (332, reason from 259-260) | `$error` |
| 2 | stderr | `ERROR: cannot read .guardkey …` (304) — should not happen under sudo | `$error` |

After commit, **re-read state** (`load_state` + `curfew_verdict`) and repaint — no optimism (UI-SPEC "Commit success" → auto-refresh).

---

### `ngtui/widgets/edit.py` (component — editable surface + per-field line edit)

**Analog (write strategy):** the Windows edit-view per-field **line edit** (STATE.md Phase 4 04-05), described in RESEARCH "Standard Stack > No YAML library" and Anti-Patterns.

**Hard rule — NO YAML emitter.** Compose `new_yaml` by **format-preserving per-field line edits on the loaded config text**, NOT by re-serializing through pyyaml/ruamel. A re-emit changes the bytes `ngcommon.yaml_load` parses and `ng.hmac_hex` signs → the guard would revert your own commit (Anti-Pattern, `guard.verify_and_revert` line 155). The control-CLI's `canonicalize` (`nightguard_ctl.py:61-66`) only normalizes BOM/CRLF/trailing-newline — it does **not** reformat fields, so the TUI must preserve layout itself.

**Editable field set (D-09)** maps onto `nightguard_ctl.py` `FIELD_TABLE` (lines 44-56) — these are the labels `classify_change` returns, so the preview can key off them directly:
```
curfew.start / curfew.end  -> joint "curfew.window" verdict (classify_change:207-217, locked-set model)
curfew.allow_commands      -> "list_add"     (adding LOOSENS)
curfew.enabled             -> "bool"  (true->false LOOSENS, classify_change:178-183)
clock_protection.enabled   -> "bool"
watchdog.enabled           -> "bool"
blocking.*.enabled         -> "bool"
blocking.native_apps.blacklist -> "list_remove" (removing LOOSENS, classify_change:150-157)
blocking.browser_extension settings
```

**Preview rendering (UI-SPEC "Anti-Impulse Edit Preview")** — drive every glyph/word/color off the classifier result, never recompute:
```python
# per-field, from ctl.classify_change(...) direction + ctl.quota_decide(...)["allowed"]:
#   "tighten" -> "▼ Tightens curfew · free"        $accent
#   "loosen"  -> "▲ Loosens curfew · costs 1 token" $warning
#   "noop"    -> "· no change"                       $text-muted
#   loosen & not allowed -> "▲ Loosens · BLOCKED — weekly tokens exhausted (3/3); available again Monday" $error
```
**Anti-impulse invariant (D-06):** direction + token cost render BEFORE `suspend()`/sudo. The `y` keystroke in the confirm gate is what triggers the commit subprocess — never authenticate first.

---

### `ngtui/widgets/status.py` (component — read-only display, D-10)

**Analogs:** `guard.curfew_verdict` (verdict → hero glyph/word/color) + `ngcommon.load_state` (token meter, grace, ledger, hmacs).

Verdict-string → UI-SPEC status mapping (glyph + word + color, never color alone — UI-SPEC Accessibility):
```
"locked"          -> ● LOCKED  ($error)   + countdown caption "curfew until HH:MM"
"grace_active"    -> ◐ GRACE   ($accent)  + "MM:SS remaining"  (display-only, D-11)
"outside_curfew"  -> ○ OPEN    ($success)
"clock_tamper"    -> ● LOCKED  ($error)   + "clock tamper detected — locked"
"offline_blocked" -> ● LOCKED  ($error)   + "time unverified — guard keeps the house closed" ($warning caption)
```
Token meter: `ctl.WEEKLY_TOKENS` (=3) minus the lazy-reset `effective_spent` → `● ● ○` filled/hollow + `N of 3 left · resets Mon YYYY-MM-DD`. Ledger rows from `state["ledger"]` (`{ntp_timestamp, fields}`); empty → `no audit entries yet`.

---

### `ngtui/theme.py` (utility — colors.toml → Textual Theme + live watch, D-04/D-05)

**Analog:** RESEARCH Pattern 4 (full code) + RESEARCH "Detecting a theme change" poll snippet. No codebase analog (external omarchy file format).

- Source resolved: `~/.config/omarchy/current/theme/colors.toml` (aether dir is empty — RESEARCH A1). Parse with stdlib `tomllib`.
- Map: `accent`→primary/accent, `color1`→error, `color2`→success, `color3`→warning, `background`→background, `foreground`→foreground, `color0`→surface (RESEARCH Pattern 4, schema verified).
- Live repaint: re-register same-named `Theme`, reassign `App.theme` (RESEARCH Pattern 4, A3 flagged for Wave-0 spike).
- Fallback (Pitfall 6): parse `alacritty.toml` (`[colors.primary]`/`[colors.normal]`) if `colors.toml` absent.
- Watch mechanism: stdlib mtime poll on the existing 1s tick (lean-deps default, RESEARCH Alternatives) or optional `watchfiles`.

---

### `ngtui/app.py` (controller — App, BINDINGS, suspend-commit)

**Analog:** RESEARCH Pattern 5 (`with self.suspend(): subprocess.run([...])`) + Pattern 6 (`BINDINGS`); UI-SPEC keybinding map (StatusScreen: `e r l q`; EditScreen: `j k Enter Space c u Escape`). Two screens (`StatusScreen`, `EditScreen`) per UI-SPEC "Screen model". Single-key only (D-03); `Footer` auto-renders the legend.

---

### `ngtui/__main__.py` (entry point)

**Analog (exact):** the `main()` + `sys.path.insert(0, dirname(abspath(__file__)))` bootstrap at `guard.py:24-25` and `nightguard_ctl.py:36-37`. The TUI entry does the same path/env setup (see `backend.py` bootstrap above) then `App().run()`.

---

## Shared Patterns

### Import-the-stack (the single most load-bearing rule)
**Source:** `guard.py:24-25`, `nightguard_ctl.py:36-37` (sys.path bootstrap); RESEARCH "Don't Hand-Roll".
**Apply to:** `backend.py`, `__main__.py` — and transitively every widget that needs a verdict/classification/quota.
The TUI must `import ngcommon, guard, nightguard_ctl` from the live LifeOS dir (env-overridable via `NIGHTGUARD_STACK_DIR`/`NIGHTGUARD_DIR`). **Never** vendor a copy of `classify_change`/`quota_decide`/`curfew_verdict`/`yaml_load` — a second copy drifts from the signer and defeats the anti-impulse preview.

### No-crypto / no-key boundary (PORT-03)
**Source:** `ngcommon.read_key` returns `None` for a non-root reader (lines 32-41); key is root:root 0600.
**Apply to:** all TUI files. The TUI imports only key-less functions (`load_state`, `yaml_load`, `curfew_verdict`, `classify_change`, `quota_decide`). It computes **no** HMAC and reads **no** key. Displayed hmacs come from `state["config_hmac"]`/`state["state_hmac"]` (stored, display-only) — the TUI cannot and must not recompute them.

### Sudoers-exact commit argv (the only write path)
**Source:** `nightguard.sudoers:20-22`.
**Apply to:** `backend.py` commit. argv **must** be `["sudo", "/usr/bin/python3", "<abs>/nightguard_ctl.py", "commit", "--from", tmp]`. Any other interpreter or argv[0] form fails the `Cmnd_Alias` match. No `shell=True`; argv list only (Injection mitigation, RESEARCH Security Domain).

### CLI stdout/exit is the source of truth for result lines
**Source:** `nightguard_ctl.py:332-348`.
**Apply to:** `backend.py` + `status.py`/`edit.py` result rendering. Surface the CLI's literal stdout (success/no-op) and stderr (`REFUSED …`) — never fabricate a result string. Re-read state after every commit (no optimism).

### Edit base = SANCTIONED, not live config (Pitfall 5)
**Source:** `nightguard_ctl.py:321` (`cmd_commit` diffs sanctioned→proposed).
**Apply to:** `edit.py` (current values + preview diff base) and `backend.py`. Load the edit base from `ng.SANCTIONED` so the preview's direction/cost matches what the signer will charge.

---

## No Analog Found

No new file is left without a backing pattern. The two files with **no codebase analog** are backed by RESEARCH/official-docs patterns instead (expected for a greenfield TUI in a Rust/PowerShell-era repo):

| File | Role | Data Flow | Backing (in lieu of codebase analog) |
|------|------|-----------|--------------------------------------|
| `ngtui/theme.py` | utility | file-I/O + event-driven | RESEARCH Pattern 4 + theme-poll snippet; omarchy `colors.toml`/`alacritty.toml` formats |
| `ngtui/app.py` + Textual widgets | controller/component | event-driven | RESEARCH Patterns 5–6 + UI-SPEC composition/keybindings; official Textual docs (suspend, BINDINGS, Theme) |
| `pyproject.toml` | config | — | RESEARCH "Recommended Project Structure" (textual + optional watchfiles, `uv` venv, PEP-668) |

---

## Metadata

**Analog search scope:** `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/` (live Python trust stack — the TUI's backend, separate LifeOS repo); product repo `nightguard-control` confirmed to contain no prior TUI / Python package.
**Files scanned (read in full, small files):** `ngcommon.py` (199), `nightguard_ctl.py` (420), `guard.py` (371), `nightguard.sudoers` (24).
**Backend commit referenced:** `3e64c81` (per RESEARCH).
**Pattern extraction date:** 2026-06-24
