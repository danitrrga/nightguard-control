# Phase 10: Linux App — omarchy TUI thin-client - Research

**Researched:** 2026-06-24
**Domain:** Python TUI (Textual) thin-client over the existing Python nightguard trust stack; live desktop theming; inline `sudo` commit flow
**Confidence:** HIGH (backend interfaces read from live source; runtime probed on this box; Textual APIs confirmed against official docs)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Build the TUI with **Textual**. Its CSS-like styling maps cleanly onto live aether colors; rich interactive widgets. Accepted as the heaviest dep in exchange for look/feel + theming ease.
- **D-02:** Aesthetic is **omarchy-native, minimal**. Not the Windows Moonlit Indigo palette — colors come from the live desktop theme.
- **D-03:** **Single-key command-driven**, keyboard-only (one keystroke per action: edit, quit, etc.). No arrow-key menu navigation as the primary model.
- **D-04:** Colors come from **aether's theme output** (`~/.config/aether/theme`); `/usr/bin/aether` is the desktop theme generator. omarchy's `~/.config/omarchy/current/theme` is the broader desktop theme system — researcher to confirm which is canonical. **→ RESOLVED below: omarchy is canonical on this box (aether dir is empty).**
- **D-05:** Theming is **live-watched** — watch the theme output and **repaint the running TUI** when the desktop theme changes (not read-once-at-launch).
- **D-06:** **Preview before commit** — show **tighten/loosen direction + token cost** BEFORE the sudo prompt (mirrors Windows UI-04 anti-impulse clarity).
- **D-07:** The preview is computed by **importing the Python classifier** (`guard.py` / `ngcommon.py` / the control-CLI's classifier) directly — reuses the single Python stack, needs **no key** and **no crypto**, requires **no control-CLI change**. (Do NOT add a `ctl --dry-run`.)
- **D-08:** On confirm, the TUI writes the proposed config to a temp file and runs **`sudo nightguard_ctl.py commit --from <temp>`**, surfacing the **password prompt inline** (no NOPASSWD). Show `REFUSED (<direction>): <reason>` on nonzero exit; show `committed … tokens N/3 used` on success.
- **D-09:** Editable fields: **curfew window (`curfew.start`/`curfew.end`)**, **`curfew.allow_commands`**, **enabled toggles** (`curfew.enabled`, `clock_protection.enabled`, `watchdog.enabled`, `blocking.*.enabled`), and **blocking blacklists** (`blocking.native_apps.blacklist`, `browser_extension` settings).
- **D-10:** Read-only display: lock status, countdown, token meter + weekly reset, grace status/remaining, config/state hmacs, audit ledger. Messages (`message`/`tamper_message`/`offline_message`) and `timezone` are not part of the editable surface this phase.
- **D-11:** **Grace is display-only this phase.** The TUI shows grace status/remaining but does **not** grant grace. The control-CLI has no grace-granting command; wiring grant is a deferred follow-up.

### Claude's Discretion
- Exact Textual screen/layout composition, widget choices, and keybinding letters (single-key model per D-03).
- Which of aether vs omarchy is the canonical live-color source (D-04) — **resolved: omarchy**.
- How config edits are entered per field (inline field editor vs prompt) — within the single-key model.

### Deferred Ideas (OUT OF SCOPE)
- **Grace granting** — a `nightguard_ctl.py grace` command + a TUI key. Out of scope (display-only, D-11).
- **StayFree blocklist import** — separate future phase.
- **`ctl --dry-run`** — rejected; D-07 imports the classifier instead.
- Do NOT add a second crypto stack, hold the key, or re-implement signing/HMAC.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PORT-01 | Linux app is a **terminal/TUI** (not Tauri) — omarchy-native, command-driven, minimal, themed live via the desktop theme | Textual 8.2.7 confirmed installable; single-key `BINDINGS` model (Architecture Patterns); live theme source resolved to omarchy `colors.toml`; live-repaint via `register_theme` + `App.theme` (Pattern 4) |
| PORT-02 | TUI is a **thin client over the one Python trust stack** — reads state via `show`/the guard, signs via `sudo` control-CLI; no second crypto stack | Read path = `nightguard_ctl.py show` JSON + import `guard.curfew_verdict`/`lock_status` for the live lock (Pattern 1); write path = `sudo … commit --from` (Pattern 5). Zero crypto in the TUI. |
| PORT-03 | TUI never holds the key; quota enforced by the control-CLI | `ngcommon.read_key()` returns `None` for a non-root reader — confirmed live (`show` printed state but no hashes). TUI imports only key-less functions. Quota lives in `quota_decide()` inside the root CLI. |
</phase_requirements>

## Summary

Phase 10 is a **Python Textual TUI** that is a strict thin client over the already-built, version-controlled Python trust stack in the **separate LifeOS repo** (`/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/`). All four backend modules were read directly from disk and their interfaces are confirmed real and current (last commit `3e64c81`).

The architecture is unusually clean because the backend already exposes exactly the two seams the TUI needs: (1) a **read path** — `nightguard_ctl.py show` emits the `guard.json` state as JSON, and `guard.py`/`nightguard_ctl.py` expose **importable, key-less, side-effect-free** classification + verdict functions; and (2) a **write path** — `sudo nightguard_ctl.py commit --from <file>` signs and commits under flock, enforcing the weekly quota in-process. The TUI holds no key, runs no crypto, and changes no backend code.

Two runtime risks were de-risked against authoritative sources. **Theming (D-04/D-05):** the `~/.config/aether/theme` directory is **empty** on this box — aether has never rendered into it — while **`~/.config/omarchy/current/theme/colors.toml` is fully populated, fresh, and atomically swapped** on every theme change. omarchy is therefore the canonical live-color source; watch it and repaint via Textual's `register_theme()` + `App.theme` reassignment. **Inline sudo (D-08):** Textual's `App.suspend()` context manager releases the TTY so `sudo` can prompt for the password (and, on this box, a **fingerprint reader** via PAM) inline, then restores the app.

**Primary recommendation:** Build a single-screen Textual 8.2.7 app (Python 3.14, isolated via `uv`/venv — system Python is PEP-668 externally-managed) that (a) reads state by importing `guard.py`/`ngcommon.py` for the live verdict + shelling `nightguard_ctl.py show` for the signed state, (b) computes the tighten/loosen+token preview by importing the control-CLI's `classify_change`/`quota_decide` (no key, no crypto), and (c) commits via `with self.suspend(): subprocess.run(["sudo","/usr/bin/python3", CTL, "commit", "--from", tmp])`, mapping the CLI's stdout/exit code to the result line. Theme = parse `colors.toml` → a Textual `Theme`, live-watch the omarchy theme dir (or the `theme-set.d` hook), re-register, reassign `App.theme`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Display lock status / countdown / token meter / grace | TUI (read) | Python guard (`curfew_verdict`, `lock_status`) | The verdict is authoritative and key-less; the TUI must never compute its own optimistic lock state (mirrors Windows UI-01 "never app-local optimism"). |
| Read signed state (`weekly_spent`, `grace`, `ledger`, hmacs) | Python control-CLI (`show`) | — | `guard.json` is root-owned 0644; only the CLI's `show` formats it. TUI shells out and parses JSON. |
| Edit-direction + token-cost preview | TUI (in-process import) | control-CLI's `classify_change`/`quota_decide` | Classification ≠ signing; it needs no key. Importing the CLI's own functions guarantees the preview matches what the signer will decide (D-07). |
| Sign / commit an edit | Python control-CLI (root, via `sudo`) | — | Sole signer; holds the root key; enforces quota under flock. The TUI shells `sudo … commit` (PORT-02/03, ROOT-03). |
| Live desktop theming | TUI (parse + apply) | omarchy theme files / hook | Colors are owned by the desktop (omarchy); the TUI is a consumer that watches + repaints (D-04/D-05). |
| Key storage / HMAC / quota enforcement | Python trust stack (root) | — | Explicitly NOT the TUI's job (PORT-03). The TUI must add no crypto path. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Textual** | `8.2.7` | The TUI framework (D-01 locked) | Current stable (released 2026-05-19); CSS-like theming maps directly to omarchy colors; supports Python 3.9–3.14. `pip index versions textual` → 8.2.7 latest. [VERIFIED: PyPI] |
| **Python** | `3.14.6` (system) | Runtime | Already on the box; the trust stack is pure-stdlib Python 3 and imports cleanly. [VERIFIED: `python3 --version`] |
| **Rich** | (bundled with Textual) | Renderables under Textual | Textual depends on Rich; no separate pin needed. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **watchfiles** | `1.2.0` | Live-watch the omarchy theme dir for D-05 repaint | Rust-backed, async-friendly (`awatch`), integrates with a Textual `@work` worker. `pip index versions watchfiles` → 1.2.0. [VERIFIED: PyPI]. **Alternative:** stdlib polling (`os.stat` mtime on `colors.toml` every ~1s) — zero deps, fits the lean-deps ethos; see Alternatives. |
| **tomllib** | stdlib (3.11+) | Parse omarchy `colors.toml` | No external TOML dep needed on Python 3.14. [VERIFIED: stdlib] |

> **No YAML library.** The trust stack ships its own minimal `ngcommon.yaml_load()` (read) and the control-CLI owns canonical writes. The TUI must compose `new_yaml` by **format-preserving per-field line edits** on the loaded config text (exactly as the Windows edit view did — see STATE.md Phase 4 04-05), NOT by re-serializing through a YAML emitter. Do **not** add `pyyaml`/`ruamel` — a re-emit would change bytes the HMAC signs and could break `ngcommon.yaml_load`'s minimal parser.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `watchfiles` (theme watch) | stdlib mtime polling on `colors.toml` (1s tick, reuse the countdown tick) | Zero new deps, honors lean-deps; cost is a 1s detection latency on theme change (irrelevant for a cosmetic repaint). **Recommended default given the project's lean-deps constraint** unless instant repaint is wanted. |
| `watchfiles`/polling | omarchy `theme-set.d` hook writing a sentinel/signal | Cleanest trigger (fires exactly on `omarchy-theme-set`), but couples the product repo to a user-side omarchy hook install — more moving parts. Viable but heavier to wire. |
| Shelling `nightguard_ctl.py show` for state | Importing `ngcommon.load_state()` directly | `load_state()` is importable and key-less (returns the `guard.json` dict) — **simpler and avoids the trailing-comment parsing issue** in `show`'s stdout (see Pitfall 2). Recommended for the raw state read; keep `show` only if you want the CLI's formatting. |

**Installation:**
```bash
# System Python is PEP-668 externally-managed (EXTERNALLY-MANAGED present) — DO NOT pip-install system-wide.
# Use uv (already on the box at ~/.local/bin/uv) or a venv:
uv venv /home/danitrrga/dev/Projects/LifeOS/nightguard-tui/.venv   # path is illustrative
uv pip install textual==8.2.7 watchfiles==1.2.0   # watchfiles optional (see Alternatives)
```

**Version verification:** `pip index versions textual` → **8.2.7** (latest, 2026-05-19); `pip index versions watchfiles` → **1.2.0**. Both confirmed against PyPI in this session.

## Package Legitimacy Audit

> slopcheck could not be installed in this environment (system Python is PEP-668 externally-managed; no `--break-system-packages` attempted to avoid polluting the system interpreter). Per protocol, packages are graded by registry age + downloads + source repo + ecosystem-correct registry, and the planner should gate the (single) new external install behind a `checkpoint:human-verify` task.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `textual` | PyPI | ~4 yrs (since 2021) | ~5M/mo | github.com/Textualize/textual | unavailable | Approved — D-01 locked, ubiquitous, verified on PyPI |
| `watchfiles` | PyPI | ~5 yrs | ~30M/mo | github.com/samuelcolvin/watchfiles | unavailable | Approved (optional) — well-known (Samuel Colvin / pydantic author) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was unavailable; the planner should add one `checkpoint:human-verify` before the `uv pip install` step. Both packages are long-established with high downloads and known maintainers, so risk is low.*

## Architecture Patterns

### System Architecture Diagram

```
                          ┌──────────────────────────────────────────┐
   desktop theme change   │            TUI process (user, NO key)      │
   (omarchy-theme-set) ─┐ │                                            │
                        │ │   ┌────────────────────────────────────┐  │
  ~/.config/omarchy/    │ │   │  Theme watcher (watchfiles/poll)   │  │
   current/theme/       └─┼──▶│  colors.toml → Textual Theme       │──┼─▶ register_theme()+App.theme  (LIVE REPAINT, D-05)
   colors.toml            │   └────────────────────────────────────┘  │
                          │                                            │
        READ PATH         │   ┌────────────────────────────────────┐  │
  guard.json (root 0644)  │   │  Status widgets (read-only, D-10)  │  │
  config.yaml (user 0644) │   │  lock / countdown / tokens / grace │  │
        │  ▲              │   └──────────▲─────────────────────────┘  │
        │  │              │              │ import (key-less)           │
        │  │  import      │   ┌──────────┴─────────────────────────┐  │
        │  └──────────────┼───│  guard.curfew_verdict / lock eval  │  │   (no crypto, no key — PORT-03)
        │  ngcommon.      │   │  ngcommon.load_state()             │  │
        │  load_state()   │   └────────────────────────────────────┘  │
        │                 │                                            │
        │   EDIT + PREVIEW│   ┌────────────────────────────────────┐  │
        │   (D-06/D-07)   │   │  Edit flow (single-key, D-03)      │  │
        └─────────────────┼──▶│  per-field line-edit on config.yaml│  │
       import classify    │   │  import classify_change+quota_decide│ │──▶ "Loosens · costs 1 token" preview
                          │   │  → temp file                       │  │
                          │   └──────────────┬─────────────────────┘  │
                          │                  │ on confirm (D-08)        │
                          │   ┌──────────────▼─────────────────────┐  │
                          │   │  with self.suspend():              │  │
                          │   │    subprocess sudo … commit --from │──┼─▶ TTY released → sudo password / fingerprint
                          │   └──────────────┬─────────────────────┘  │     (inline, intentional friction)
                          └──────────────────┼────────────────────────┘
                                             │ shells (sudoers-scoped)
                          ┌──────────────────▼────────────────────────┐
                          │  ROOT: nightguard_ctl.py commit  (sole     │
                          │  signer; reads root key; quota under flock;│
                          │  sanctioned→guard.json→config; chown-back) │
                          │  stdout: "committed (loosen -1 token)…"    │
                          │  exit 1 + stderr: "REFUSED (loosen): …"    │
                          └────────────────────────────────────────────┘
```

A reader can trace the core anti-impulse use case: user edits a field → in-process `classify_change`+`quota_decide` show direction+cost BEFORE auth → confirm → `suspend()` → `sudo` prompt → root CLI signs or refuses → result line repainted from the CLI's actual stdout/exit.

### Recommended Project Structure
```
nightguard-tui/                 # NEW (placement TBD by planner — see Open Q1)
├── pyproject.toml              # textual + (optional) watchfiles; entry point `ngtui`
├── ngtui/
│   ├── __main__.py             # App() entry
│   ├── app.py                  # NightguardApp(App): BINDINGS, on_mount, theme
│   ├── backend.py              # thin adapters: imports guard/ngcommon/ctl; shells sudo commit
│   ├── theme.py                # colors.toml → Theme; watcher
│   └── widgets/                # status, token meter, edit panel
└── .venv/                      # uv-managed, isolated from system Python
```

> **Backend import strategy (load-bearing):** `backend.py` must put the LifeOS nightguard dir on `sys.path` and import the real modules — it must NOT vendor a copy (that would create a second classifier to drift). Set `NIGHTGUARD_DIR=/home/danitrrga/dev/Projects/LifeOS/nightguard` in the process env (ngcommon reads it) and `sys.path.insert(0, "/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard")`, then `import ngcommon, guard, nightguard_ctl as ctl`.

### Pattern 1: Key-less read of live lock status (the authoritative verdict)
**What:** Compute the LOCKED/OPEN/grace status by importing `guard.curfew_verdict(cfg, state)` — the same pure, side-effect-free function the watchdog uses (08-01). No key, no revert, no audit write.
**When to use:** The status hero + countdown (D-10, Success Criterion 2).
```python
# Source: read from /home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/guard.py (lines 224-279)
import os, sys
os.environ.setdefault("NIGHTGUARD_DIR", "/home/danitrrga/dev/Projects/LifeOS/nightguard")
sys.path.insert(0, "/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard")
import ngcommon as ng, guard

state = ng.load_state()                 # key-less; reads guard.json dict (root 0644, world-readable)
# worst-case grace if state can't be trusted — but TUI has NO key to verify state_hmac.
# Display-only: read grace as-is for the meter; the GUARD enforces the real verdict.
cfg = ng.yaml_load(ng.file_bytes(ng.CONFIG).decode("utf-8"))
verdict = guard.curfew_verdict(cfg, state)   # "locked" | "grace_active" | "outside_curfew" | "clock_tamper" | "offline_blocked"
```
**Caveat (display vs enforcement):** the TUI cannot verify `config_hmac`/`state_hmac` (no key, PORT-03), so its displayed verdict is advisory. That is acceptable and correct — the **authoritative** verdict is the root watchdog + the Claude Code curfew hook (Phase 7.1/8). The TUI must present its status as "what the guard will enforce," never claim authority. Mirror Windows UI-01's "never app-local optimism" by reading the verdict from `guard.py` rather than recomputing curfew math in TS/Python.

### Pattern 2: Read signed state for the token meter / grace / ledger (D-10)
**What:** Get `weekly_spent`, `week_anchor`, `grace`, `ledger`, and the stored `config_hmac`/`state_hmac` directly.
**When to use:** Token meter (n/3 + reset), grace remaining, audit ledger, hmac display.
```python
# Source: ngcommon.load_state (lines 68-73) — preferred over shelling `show`
state = ng.load_state()
weekly_spent = state.get("weekly_spent", 0)      # int
week_anchor  = state.get("week_anchor", "")      # "YYYY-MM-DD" Monday
grace        = state.get("grace")                # None or {date, window_start, window_end}
ledger       = state.get("ledger", [])           # [{ntp_timestamp, fields:[...]}]
config_hmac  = state.get("config_hmac", "")      # hex (display only)
state_hmac   = state.get("state_hmac", "")       # hex (display only)
# Next-reset = the upcoming Monday in the configured tz (mirror quota_decide's _current_week_monday).
```
**Tokens-used → tokens-left:** `WEEKLY_TOKENS = 3` (in `nightguard_ctl.py`); display `3 - weekly_spent` dots. Apply the same lazy week-reset semantics the CLI uses (`week_anchor < current_monday` ⇒ effectively 0 used) so a stale `weekly_spent=3` from last week doesn't show an empty meter on a fresh week. [VERIFIED: `quota_decide`, lines 241-260]

### Pattern 3: Edit-direction + token-cost preview, in-process (D-06/D-07)
**What:** Before any sudo prompt, classify sanctioned-vs-proposed using the CLI's OWN functions and run its quota logic.
**When to use:** The live per-field feedback ("Tightens · free" / "Loosens · costs 1 token" / 0-token block reason).
```python
# Source: nightguard_ctl.py classify_change (lines 202-222), is_loosening (225-226), quota_decide (241-260)
import nightguard_ctl as ctl
old_doc = ng.yaml_load(ng.file_bytes(ng.SANCTIONED).decode("utf-8"))  # sanctioned = the diff base the CLI uses
new_doc = ng.yaml_load(proposed_text)
dirs = ctl.classify_change(old_doc, new_doc)          # [(label, "loosen"|"tighten"|"noop"), ...]
loosening = ctl.is_loosening(dirs)
tzname = new_doc.get("timezone") or old_doc.get("timezone") or "Europe/Amsterdam"
decision = ctl.quota_decide(dirs, ng.load_state(), tzname)
# decision: {allowed, reason, costs_token, is_noop, effective_spent, week_anchor}
# UI: costs_token=True  -> "Loosens curfew · costs 1 token"
#     allowed=False     -> disable commit, show decision["reason"]  ("…available again Monday")
#     all noop          -> "no change"
#     loosening=False & not noop -> "Tightens · free"
```
**Why this is exactly right:** the CLI's `cmd_commit` diffs **sanctioned → proposed** (line 321) and calls the *same* `classify_change`+`quota_decide` — so importing them gives a byte-for-byte-faithful preview of what the signer will decide. No `--dry-run` needed (D-07). No key touched. [VERIFIED: nightguard_ctl.py source]

### Pattern 4: Live desktop theming — colors.toml → Textual Theme, re-register on change (D-04/D-05)
**What:** Parse omarchy's `colors.toml` into a Textual `Theme`, register it, set `App.theme`; on theme change, re-parse, re-register the same name, reassign `App.theme` to force a repaint.
**When to use:** App mount + every detected theme change.
```python
# Source: https://textual.textualize.io/guide/design/  (Theme, register_theme, App.theme)
import tomllib
from textual.theme import Theme

def load_omarchy_theme() -> Theme:
    p = "/home/danitrrga/.config/omarchy/current/theme/colors.toml"
    with open(p, "rb") as fh:
        c = tomllib.load(fh)
    return Theme(
        name="omarchy",
        primary=c["accent"],          # e.g. "#7fbbb3"
        background=c["background"],    # "#2d353b"
        foreground=c["foreground"],    # "#d3c6aa"
        surface=c.get("color0", c["background"]),
        accent=c["accent"],
        success=c.get("color2", c["accent"]),
        warning=c.get("color3", c["accent"]),
        error=c.get("color1", c["accent"]),
        dark=True,
    )

class NightguardApp(App):
    def on_mount(self) -> None:
        self.register_theme(load_omarchy_theme())
        self.theme = "omarchy"

    def reload_theme(self) -> None:        # called by the watcher worker (on the app thread)
        self.register_theme(load_omarchy_theme())   # re-register same name = overwrite
        self.theme = "omarchy"                       # reassign reactive -> Textual refreshes CSS + repaints
```
**Repaint mechanism:** setting `App.theme` (a reactive) "immediately refreshes the application to use the new color scheme, with all CSS variables automatically updated" [CITED: textual.textualize.io/guide/design]. Re-registering a theme of the same name overwrites the prior definition, so reassigning `App.theme` to it picks up the new colors. Use thread-safe `app.call_from_thread(app.reload_theme)` if the watcher runs in a thread worker.
**colors.toml schema (verified on this box):** `accent, cursor, foreground, background, selection_foreground, selection_background, color0..color15` — all `#rrggbb` strings. Map terminal ANSI colors to Textual roles: `color1`=red→error, `color2`=green→success, `color3`=yellow→warning, `accent`/`color4`→primary/accent. [VERIFIED: `~/.config/omarchy/current/theme/colors.toml`]

### Pattern 5: Inline sudo commit with TTY release (D-08)
**What:** Suspend the Textual app (releasing the terminal), run `sudo … commit --from <temp>` so its password/fingerprint prompt appears inline, restore the app, then map exit code + stdout to the result line.
**When to use:** On commit confirm.
```python
# Source: https://textual.textualize.io/guide/app/  (App.suspend context manager)
import subprocess, tempfile, os
CTL = "/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_ctl.py"

def do_commit(self, proposed_text: str):
    fd, tmp = tempfile.mkstemp(suffix=".yaml")
    os.write(fd, proposed_text.encode("utf-8")); os.close(fd)
    with self.suspend():                         # releases the TTY; sudo can prompt inline
        proc = subprocess.run(
            ["sudo", "/usr/bin/python3", CTL, "commit", "--from", tmp],
            capture_output=True, text=True,       # capture for the result line
        )
    os.unlink(tmp)
    if proc.returncode == 0:
        self.show_result(proc.stdout.strip())     # "committed (loosen -1 token): … | tokens 2/3 used"
    else:
        self.show_result(proc.stderr.strip())     # "REFUSED (loosen): weekly loosen quota exhausted …"
    self.refresh_state()                          # re-read guard.json -> repaint meter/status (no optimism)
```
**Exact command form is mandated by sudoers** (`/etc/sudoers.d/nightguard`, in-repo as `nightguard.sudoers`): `Cmnd_Alias NIGHTGUARD_CTL = /usr/bin/python3 <abs>/nightguard_ctl.py commit *`. The argv **must** be `["sudo", "/usr/bin/python3", "<abs>/nightguard_ctl.py", "commit", "--from", tmp]` — any other interpreter path or argv[0] form will not match the rule and sudo will demand a password for a disallowed command (or refuse). [VERIFIED: nightguard.sudoers lines 20-24]
**TTY caveat with `capture_output`:** `capture_output=True` pipes stdout/stderr, but `sudo`'s prompt goes to the **controlling TTY / stderr-as-tty**, which `suspend()` has restored to the real terminal — the password prompt still appears. The fingerprint reader (PAM, see Pitfall 3) also drives the real TTY. If capturing ever swallows the prompt in testing, fall back to NOT capturing (let sudo own the screen) and parse the CLI's machine-readable lines another way (e.g. re-run `verify`/`show` after). **Recommended:** capture stdout only, leave stderr attached to the terminal (`stderr=None`) so the prompt + any `REFUSED` line are visible; then re-read state for the meter.
**Exit/stdout contract (verified from source):**
- success: exit `0`, stdout `committed (<dir><, free| -1 token>): config_hmac=… | tokens N/3 used` (line 346-348)
- refused (quota): exit `1`, stderr `REFUSED (loosen): weekly loosen quota exhausted (3/3 used); available again Monday` (line 332)
- no-op: exit `0`, stdout `no-op: proposed config is identical to sanctioned; nothing written.` (line 335)
- key unreadable (should not happen under sudo): exit `2`, stderr `ERROR: cannot read .guardkey …` (line 304)

### Pattern 6: Single-key command-driven bindings (D-03)
**What:** One keystroke per action via Textual `BINDINGS`; no arrow-key menu as the primary model.
```python
# Source: https://textual.textualize.io/guide/input/ (BINDINGS / Binding / action_*)
class NightguardApp(App):
    BINDINGS = [
        ("e", "edit", "Edit a field"),
        ("r", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
        # field entry within edit uses inline Input widgets (Claude's discretion, D-03)
    ]
    def action_edit(self) -> None: ...
    def action_refresh(self) -> None: ...
```
A `Footer` widget auto-renders the BINDINGS as the single-key legend — idiomatic for the "command-driven, minimal" feel (PORT-01).

### Anti-Patterns to Avoid
- **Re-emitting YAML with pyyaml/ruamel.** Changes the bytes the HMAC signs and can break `ngcommon.yaml_load`'s minimal parser → guard would revert your own commit. Do per-field **line edits** on the loaded text (the Windows app did exactly this — 04-05).
- **Recomputing curfew/lock math in the TUI.** Import `guard.curfew_verdict` instead — one source of truth, no drift, "never app-local optimism."
- **Vendoring a copy of `classify.rs`/`classify_change`.** Import the live `nightguard_ctl.classify_change` so the preview can never disagree with the signer.
- **Holding/reading the key or computing any HMAC in the TUI.** Forbidden by PORT-03; `ngcommon.read_key()` returns `None` for the user anyway (key is root:root 0600).
- **Hardcoding Moonlit Indigo or any fixed palette.** D-02: colors come from the live desktop theme.
- **Running a Textual app over a non-interactive pipe** while expecting sudo to prompt — the password prompt needs the controlling TTY (handled by `suspend()`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Curfew lock/grace evaluation | A second TS/Python curfew evaluator | `import guard; guard.curfew_verdict(cfg, state)` | Pure, side-effect-free, already unit-tested (08-01); avoids drift from the enforced verdict |
| Edit-direction classification | A reimplemented direction table | `import nightguard_ctl as ctl; ctl.classify_change(...)` | The signer uses the same function; the preview is then exact (D-07) |
| Token-quota math (lazy week reset, 3-token cap, "available again Monday") | A reimplemented quota | `ctl.quota_decide(dirs, state, tz)` | Identical to what the root CLI charges; copying it risks a preview that disagrees with the commit |
| Signing / HMAC / atomic ordered commit / chown-back | Anything | `sudo nightguard_ctl.py commit --from` | Sole signer; flock; crash-safe order; PORT-03 forbids a second crypto stack |
| State read | A `guard.json` schema reimpl | `ngcommon.load_state()` | Returns the dict directly, key-less |
| TUI theming system | A bespoke ANSI color manager | Textual `Theme` + `register_theme` + `App.theme` | Built-in CSS-variable repaint; D-01 chose Textual precisely for this |
| File-change watching | A bespoke inotify wrapper | `watchfiles` OR a 1s stat-mtime poll | Edge cases (atomic dir-swap, debounce) already solved |

**Key insight:** This phase's correctness comes almost entirely from **importing the existing trust stack rather than re-implementing it**. The single biggest failure mode is a TUI that builds its own classifier/quota/verdict and silently disagrees with the signer — defeating the anti-impulse preview. Every computation the TUI shows must trace back to a function the root CLI or guard actually runs.

## Runtime State Inventory

> Phase 10 is a **net-new app** (greenfield TUI) that reads existing runtime state but renames/migrates nothing. Included for completeness because it reads root-owned live state.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `guard.json` (root:root 0644), `config.yaml` (user 0644), `config.sanctioned.yaml` (root 0644), `guard-audit.log`, `.timecache` — all under `/home/danitrrga/dev/Projects/LifeOS/nightguard/` | None — TUI **reads** these (no migration). Writes only via the root CLI. |
| Live service config | systemd **system** service `nightguard-watchdog.{service,timer}` (active, 60s) enforces revert/kill independently of the TUI | None — TUI does not touch the watchdog. Verified `active (waiting)`. |
| OS-registered state | `/etc/sudoers.d/nightguard` (in-repo as `nightguard.sudoers`) defines the exact allowed sudo command surface | None to create — already installed (Phase 7). TUI's commit argv **must match** the alias exactly (Pattern 5). |
| Secrets/env vars | `.guardkey` (root:root 0600 — TUI cannot read, by design); `NIGHTGUARD_DIR` env var consumed by ngcommon | TUI sets `NIGHTGUARD_DIR=/home/danitrrga/dev/Projects/LifeOS/nightguard` for its imports/subprocess; never reads the key |
| Build artifacts / installed packages | None yet (new app). System Python is PEP-668 externally-managed | TUI deps go in a `uv`/venv — never system-wide pip |

**Nothing found requiring data migration:** verified — the TUI is purely additive; no existing record stores a TUI-owned string.

## Common Pitfalls

### Pitfall 1: PEP-668 externally-managed system Python
**What goes wrong:** `pip install textual` fails or, worse, with `--break-system-packages` pollutes the Arch system interpreter.
**Why it happens:** CachyOS/Arch marks `/usr/lib/python3.14/EXTERNALLY-MANAGED` (confirmed present). System packages are pacman-managed.
**How to avoid:** Use `uv` (already at `~/.local/bin/uv`) or `python -m venv`. The TUI runs from its venv; the venv interpreter still imports the LifeOS trust modules via `sys.path` (they're pure-stdlib, no third-party deps).
**Warning signs:** `error: externally-managed-environment` on install.

### Pitfall 2: `nightguard_ctl.py show` stdout is JSON **plus trailing comment lines**
**What goes wrong:** `json.loads(subprocess output)` raises `Extra data` because `show` prints the `indent=2` JSON, then `# live config_hmac: …` / `# (key unreadable …)` comment lines after it (lines 375-381).
**Why it happens:** `show` is human-oriented; the hashes are appended as `#`-prefixed lines outside the JSON.
**How to avoid:** **Prefer `ngcommon.load_state()`** for the raw state dict (no parsing fragility, no subprocess). If you must shell `show`, parse only up to the closing brace, or split on the first `\n#`. The TUI cannot get the live `config_hmac` from `show` as the user anyway (key unreadable) — read the stored `config_hmac` from `load_state()` for display.
**Warning signs:** `json.decoder.JSONDecodeError: Extra data`.

### Pitfall 3: sudo on this box triggers a **fingerprint reader** (PAM), not just a password
**What goes wrong:** During testing, `sudo` printed `Place your right index finger on the fingerprint reader` and `Verification timed out` before falling back to password — a non-interactive or captured-stderr invocation can hang or appear frozen.
**Why it happens:** `/etc/pam.d/sudo` includes `pam_fprintd` (verified `fprintd in pam sudo`). The prompt drives the TTY.
**How to avoid:** `suspend()` MUST own the real terminal for the commit subprocess (Pattern 5). Leave `stderr` attached to the terminal so the fingerprint/password prompt and timeout are visible to the user. Do not run the commit from a worker thread that has no controlling TTY. Accept the multi-second fingerprint timeout as part of the (intentional) friction.
**Warning signs:** The app appears to hang on commit; no visible prompt.

### Pitfall 4: Stale `weekly_spent` across a week boundary
**What goes wrong:** The token meter shows 0 tokens left on a fresh week because `guard.json` still has `weekly_spent=3` from last week (the CLI applies a **lazy** reset only at commit time).
**Why it happens:** `quota_decide` computes `effective_spent = 0 if week_anchor < current_monday else weekly_spent` (lines 245-246) — but `guard.json` on disk isn't rewritten until the next commit.
**How to avoid:** The TUI must apply the same lazy reset for display: if `week_anchor < current_monday_in_tz`, show 3 tokens available regardless of stored `weekly_spent`. Reuse `quota_decide`'s logic (call it with an empty `dirs` to read `effective_spent`, or replicate `_current_week_monday`).
**Warning signs:** Meter disagrees with what a fresh commit would allow.

### Pitfall 5: Editing the wrong diff base
**What goes wrong:** The preview classifies against `config.yaml` (live) but the CLI classifies against `config.sanctioned.yaml` — mismatched direction/cost if the two differ (e.g. after a hand-edit pending revert).
**Why it happens:** `cmd_commit` diffs **sanctioned → proposed** (line 321), not live → proposed.
**How to avoid:** Load the edit base from `ngcommon.SANCTIONED` for both the displayed current values AND the preview diff. (The live `config.yaml` is what the user sees in their editor, but the *signer's* baseline is sanctioned; they're normally identical because the watchdog reverts drift, but be explicit.)
**Warning signs:** Preview says "free/noop" but the commit charges a token, or vice versa.

### Pitfall 6: `colors.toml` may be absent for some themes
**What goes wrong:** A theme switched to may ship only `alacritty.toml`; `colors.toml` is generated on-demand.
**Why it happens:** `omarchy-theme-set` generates `colors.toml` from `alacritty.toml` only if missing (verified in the script). The current `everforest` theme has it, but robustness matters.
**How to avoid:** On theme load, fall back to parsing `alacritty.toml` (`[colors.primary] background/foreground`, `[colors.normal] red/green/...`) if `colors.toml` is missing. Both are TOML.
**Warning signs:** `FileNotFoundError` on `colors.toml` after a theme change.

## Code Examples

(See Patterns 1–6 above — each carries a verified source reference to the live backend file + line numbers or the official Textual docs URL.)

### Detecting a theme change (stdlib poll — recommended lean default)
```python
# Reuse the app's existing refresh tick (status/countdown). No new dependency.
import os
class _ThemeWatch:
    PATH = "/home/danitrrga/.config/omarchy/current/theme/colors.toml"
    def __init__(self): self._mtime = self._stat()
    def _stat(self):
        try: return os.stat(self.PATH).st_mtime
        except OSError: return 0
    def changed(self) -> bool:
        m = self._stat()
        if m != self._mtime:
            self._mtime = m; return True
        return False
# in the 1s tick: if theme_watch.changed(): self.reload_theme()
```
> Note: omarchy swaps the theme via `rm -rf current/theme && mv next-theme current/theme` (atomic dir replacement). An mtime poll on `current/theme/colors.toml` catches this because the new file has a new mtime. `watchfiles.awatch` on the `current` dir also works (watch the parent, since the dir itself is replaced). [VERIFIED: omarchy-theme-set source]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tauri v2 + Rust + a 2nd Rust crypto stack | omarchy Textual TUI thin-client over the one Python stack | 2026-06-22 curation (REVIEWS.md) | One HMAC implementation; the TUI adds no crypto |
| Windows Moonlit Indigo fixed palette | Live desktop theme (omarchy colors.toml) | This phase (D-02) | Colors track the desktop, repaint live |
| Unix-socket commit helper | `sudo` → control-CLI (the prompt IS the friction) | Phase 7 (ROOT-03) | TUI shells sudo; no daemon |
| `aether --generate` → `~/.config/aether/theme` | omarchy `current/theme` is the live source on this box | Verified 2026-06-24 | aether theme dir is empty; use omarchy |

**Deprecated/outdated:**
- Anything in CLAUDE.md's "Technology Stack" referencing Tauri/Rust/DPAPI/`windows-dpapi`/`yamlpatch` — **superseded for this phase** by the omarchy TUI curation. The trust-model invariants (single HMAC, sole signer, no second crypto, fail-closed) still hold.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `~/.config/aether/theme` being empty means aether is *not* the live color source on this box (D-04) — omarchy is canonical | Theming (D-04 resolution) | If the user later runs `aether --generate`, the aether dir would populate. **Mitigation:** the TUI reads omarchy `current/theme`, which omarchy keeps authoritative regardless (aether can write *into* omarchy via `--as_omarchy_theme`). Low risk. |
| A2 | `with self.suspend(): subprocess.run([...], stderr=None)` lets sudo's password+fingerprint prompt reach the user inline | Pattern 5 / Pitfall 3 | If capture swallows the prompt, the app appears to hang. **Mitigation:** keep stderr attached to the terminal; verify live in a Wave-0 spike (recommended). |
| A3 | Re-registering a same-named Textual `Theme` and reassigning `App.theme` forces a full repaint on 8.2.7 | Pattern 4 | A 2023 issue (#2583) reported "set theme twice" not working; long-resolved in 8.x but unverified live here. **Mitigation:** Wave-0 spike — if reassign doesn't repaint, toggle to a throwaway theme then back, or call `self.refresh(layout=True)` / `App.get_css_variables()` reload. |
| A4 | The TUI process can `import ngcommon, guard, nightguard_ctl` without side effects (no key read, no audit write) merely by importing | Pattern 1/3 | Importing runs module top-level code. Verified: all three only define functions + module-level path constants at import; `read_key()`/`append_audit()` fire only when called. `classify_change`/`quota_decide`/`curfew_verdict`/`load_state` are all key-less and side-effect-free. Low risk. |
| A5 | `everforest` colors map sensibly to Textual roles (accent→primary, color1→error, etc.) | Pattern 4 | Cosmetic only; wrong mapping = ugly, not broken. |

## Open Questions

1. **Where does the TUI repo/package live?**
   - What we know: the backend is in the **separate LifeOS repo** (`scripts/nightguard/`); this product repo (`nightguard-control`) is the publishable Windows-era codebase.
   - What's unclear: does the TUI ship in `nightguard-control` (publishable product) or in LifeOS (instance)? The TUI imports LifeOS paths by absolute path today.
   - Recommendation: build the TUI as a product in `nightguard-control` (it's the "Linux App" deliverable), but make the LifeOS path configurable via `NIGHTGUARD_STACK_DIR`/`NIGHTGUARD_DIR` env so the published product isn't hardcoded to the author's machine. The author's instance sets those env vars. **Planner to confirm with user.**

2. **Inline-sudo + capture interaction (A2/A3) — Wave-0 spike recommended.**
   - What we know: `suspend()` releases the TTY; sudo uses PAM fingerprint+password here.
   - What's unclear: exact stdout/stderr capture combo that both shows the prompt AND lets the result line be parsed.
   - Recommendation: a tiny Wave-0 spike — a 30-line Textual app that suspends, runs `sudo … verify` (allowed by sudoers, harmless), confirms the prompt appears inline and the exit code is readable. Settle the capture strategy before building the edit flow.

3. **Theme-watch mechanism: poll vs watchfiles vs omarchy hook.**
   - What we know: all three work; poll is zero-dep, watchfiles is instant, the hook is cleanest-but-couples.
   - Recommendation: stdlib mtime poll on the existing 1s tick (lean-deps default). Planner picks; not load-bearing.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | The whole TUI + trust-stack imports | ✓ | 3.14.6 | — |
| Textual | TUI framework (D-01) | ✗ (installable) | 8.2.7 on PyPI | none — D-01 locked; must install in venv |
| watchfiles | Live theme watch (optional) | ✗ (installable) | 1.2.0 on PyPI | stdlib mtime poll (recommended) |
| `uv` | Isolated venv (PEP-668) | ✓ | at `~/.local/bin/uv` | `python -m venv` |
| The Python trust stack (`ngcommon`/`guard`/`nightguard_ctl`) | Read + classify + commit | ✓ | committed, `3e64c81` | none — hard dependency (separate LifeOS repo) |
| `/etc/sudoers.d/nightguard` rule | Commit via sudo (D-08) | ✓ | installed (Phase 7) | none — must exist for commit |
| `nightguard-watchdog` systemd system service | Enforcement (independent of TUI) | ✓ | active (waiting), 60s | — (not the TUI's concern) |
| omarchy `current/theme/colors.toml` | Live theming (D-04) | ✓ | fresh (everforest) | parse `alacritty.toml` if colors.toml absent |
| `~/.config/aether/theme` | (D-04 candidate) | ✗ (empty dir) | — | **not used — omarchy is canonical** |
| `pkexec` | Alt to sudo (D-08 mentions pkexec) | ✓ | present | sudo is the chosen path (sudoers rule is sudo-scoped) |
| `tomllib` | Parse colors.toml | ✓ | stdlib 3.14 | — |

**Missing dependencies with no fallback:** none blocking — Textual is the only required net-new install and it's a routine venv install.
**Missing dependencies with fallback:** `watchfiles` (→ stdlib poll); `aether/theme` (→ omarchy).

## Security Domain

> `security_enforcement` is not set in config.json (treat as enabled). This phase's security posture is dominated by the fact that the TUI is **deliberately unprivileged** — it holds no key and runs no crypto (PORT-03).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `sudo` password + PAM fingerprint is the privilege boundary for commits (ROOT-03/04). The TUI never authenticates; it delegates to sudo. |
| V3 Session Management | no | No sessions; single local operator. |
| V4 Access Control | yes | Key is root:root 0600 (TUI can't read it); commit scoped by `/etc/sudoers.d/nightguard` to a fixed command. TUI must use the exact allowed argv. |
| V5 Input Validation | yes | The proposed config is written to a temp file and validated **by the root CLI** (argparse + its own classifier + `ngcommon.yaml_load`). The TUI should still avoid passing untrusted paths. |
| V6 Cryptography | yes (by delegation) | Never hand-roll — all HMAC lives in `ngcommon`; the TUI imports nothing crypto. |

### Known Threat Patterns for a thin-client TUI over a root signer

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| sudoers arg-injection via a wildcard rule | Elevation of Privilege | The rule scopes to `nightguard_ctl.py commit *`; the CLI validates args with argparse and only writes inside NIGHTGUARD_DIR (verified). TUI passes a single `--from <tmp>`; no shell, use argv list (no `shell=True`). |
| Temp-file race / symlink on `--from` path | Tampering | Use `tempfile.mkstemp` (0600, exclusive), write, pass the path, unlink after. The CLI re-canonicalizes the bytes it signs. |
| TUI presenting an optimistic (false) lock state | Spoofing / Repudiation | Read the verdict from `guard.curfew_verdict` and the meter from `guard.json`; never compute locally; re-read after every commit. |
| Command-injection via field values (e.g. a blacklist entry with shell metachars) | Injection | No shell anywhere; argv lists only. Field values land in YAML text validated by the CLI's parser, not a shell. |
| Stale preview disagreeing with the signer | Tampering (of intent) | Import the CLI's own `classify_change`/`quota_decide`; diff against `sanctioned` (the CLI's base). |

## Sources

### Primary (HIGH confidence)
- **Live backend source** (read this session, separate LifeOS repo, committed `3e64c81`):
  - `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_ctl.py` — subcommands `init/verify/show/commit --from [--rebaseline]`; `classify_change` (202), `is_loosening` (225), `quota_decide` (241), `cmd_commit` (300), `cmd_show` (372), exit/stdout contract (332-348), `WEEKLY_TOKENS=3` (40)
  - `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/guard.py` — `curfew_verdict(cfg, state)` key-less side-effect-free verdict (224-279), `decide()` (281), verdict strings
  - `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/ngcommon.py` — `read_key` (32, returns None for non-root), `load_state` (68), `yaml_load` (133), `config_hmac`/`state_hmac`, `NIGHTGUARD_DIR`/`CONFIG`/`SANCTIONED`/`STATE` paths (18-26)
  - `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard.sudoers` — exact allowed sudo command alias (20-24)
- **Live system probe** (this box, 2026-06-24): `python3 --version`=3.14.6; `pip index versions textual`=8.2.7; `pip index versions watchfiles`=1.2.0; `EXTERNALLY-MANAGED` present; `~/.config/aether/theme` empty; `~/.config/omarchy/current/theme/colors.toml` populated (everforest); `omarchy-theme-set` swap mechanism; `nightguard-watchdog.timer` active; `fprintd in pam sudo`; `nightguard_ctl.py show` real output (state JSON + trailing `#` comments).
- **Textual official docs:**
  - https://textual.textualize.io/guide/app/ — `App.suspend()` context manager, `action_suspend_process`
  - https://textual.textualize.io/guide/design/ — `Theme`, `register_theme`, `App.theme` reactive auto-refresh, CSS `$variables`, shade variants
- **PyPI:** https://pypi.org/project/textual/ — 8.2.7 (2026-05-19), Python 3.9–3.14 supported

### Secondary (MEDIUM confidence)
- WebSearch (Textual themes/reactivity) — confirmed `register_theme` + `App.theme` runtime refresh, `watch_` reactive superpower; surfaced historical issue #2583 (resolved).

### Tertiary (LOW confidence)
- None load-bearing. (Theme-watch mechanism choice is discretion, not a claim.)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Textual 8.2.7 / watchfiles 1.2.0 verified on PyPI; backend is pure-stdlib, read from source
- Architecture: HIGH — every seam (read/preview/commit/theme) traced to verified live source + official Textual APIs
- Pitfalls: HIGH — PEP-668, the `show` trailing-comment parse, fingerprint-sudo, and lazy week-reset were all observed/verified live this session
- Theming: HIGH — omarchy is the live source (aether dir empty, verified); repaint API cited from official docs (live-repaint behavior flagged A3 for a Wave-0 confirm)

**Research date:** 2026-06-24
**Valid until:** 2026-07-24 (stable; Textual minor releases are frequent but the suspend/theme APIs are stable; re-check Textual version at integration)
