# Phase 11: Global Install + Status Subcommand - Research

**Researched:** 2026-06-25
**Domain:** Python packaging (`uv tool install`) + Waybar custom-module JSON contract + argv routing in a Textual TUI, over a root-coupled-but-key-less Python trust stack
**Confidence:** HIGH (every success criterion was verified empirically on the live instance, not from training data)

## Summary

Phase 11 is packaging + a new read-only subcommand — no new crypto, no new editing. Every load-bearing unknown was **resolved by running the real commands on the author's live box**, not inferred. The headline: **all five success criteria are already structurally satisfiable with the code as it stands today**, with exactly two small code changes required (a `status` subcommand + a `sys.stdin.isatty()` TTY guard) and one design decision to make (how the status reader handles the cold-NTP-cache blocking window).

The keystone result: with a **fully scrubbed environment** (`env -i`, no `NIGHTGUARD_*`), the installed shim resolves the LifeOS trust stack via `backend.py`'s hardcoded author-instance defaults (`_DEFAULT_STACK_DIR` + the `NIGHTGUARD_DIR` `setdefault`), and every key-less read works (`live_verdict` → `"outside_curfew"`, `tokens_left` → `2`). `uv tool install --python 3.14 .` was run for real: it builds an isolated venv at `~/.local/share/uv/tools/ngtui/`, lands a shim at `~/.local/bin/ngtui`, and that directory is on the bare login PATH in **both** `bash -l` and `fish -l`. SC-5 — the single highest-risk flag — is **GREEN**: `guard.json` and `config.sanctioned.yaml` are `root:root 0644` (world-readable), while `.guardkey` is `root:root 0600` (correctly denied to the user).

**Primary recommendation:** Add a `status` subcommand to `__main__.py` that (1) wraps `import ngtui.backend` in try/except so a stack-resolution `RuntimeError` degrades to `{"text":"○ —","class":"unavailable"}` exit 0; (2) sources `text`/`tooltip`/`class` key-lessly from `live_verdict`/`tokens_left`; and (3) **guards the cold-cache NTP blocking window** (measured at ~2.1s, up to ~4s) — the status path must never block a Waybar poll. Add a `sys.stdin.isatty()` loud-fail to the TUI launch path **only** (status runs head-less). Keep the author-instance hardcoded defaults as-is for now (they make SC-1/SC-5 pass for the author); flag the publishable-product default as a Phase 13 concern.

## User Constraints

> No `*-CONTEXT.md` exists for Phase 11 (research is running standalone / ahead of discuss-phase). Constraints below are lifted from PROJECT.md, REQUIREMENTS.md, and the ROADMAP Phase 11 success criteria — treat the success criteria as the locked spec.

### Locked Decisions (from PROJECT.md / ROADMAP / REQUIREMENTS)

- **One Python trust stack.** The TUI is a thin client that **holds no key and computes no HMAC** (PORT-02/03). The status reader must be key-less.
- **`sudo` is the anti-impulse threshold.** No surface may loosen the curfew without the TUI's `sudo`-gated commit. The status path must **never** call `sudo`, read `.guardkey`, or prompt.
- **The bar/launcher is a window, never a lever** (REQUIREMENTS, load-bearing invariant #2).
- **The inline-`sudo` commit needs a real PTY** (load-bearing invariant #1) — the global install must not break it (SC-4).
- **Linux-only** (CachyOS + Hyprland/omarchy).
- **Lean deps.** Only third-party dep is `textual==8.2.7`. Do not add packages for the status subcommand — stdlib `json`/`argparse` only.
- **Publishable product vs. author instance split.** Hardcoded `/home/danitrrga/...` paths are *instance* config, not product surface (mirrors the Phase 5 decision: "instance-level config, not product surface").

### Claude's Discretion

- Exact `text`/`tooltip`/`class` string content (glyphs, token rendering) — within the Waybar JSON contract.
- How to structure the cold-cache NTP guard (subprocess timeout vs. env flag vs. cache-only read) — see Pitfall 1 for the options.
- Whether the TTY guard is a bare `sys.stdin.isatty()` check or `sys.stdout.isatty()` too.

### Deferred Ideas (OUT OF SCOPE for Phase 11)

- The `.desktop` launcher, brand icon, Hyprland windowrule, the actual Waybar module wiring, the `SIGRTMIN+N` signal push → **Phase 12**.
- Autostart, AUR `PKGBUILD`, the publishable-product default stack path, `optdepends` declaration → **Phase 13**.
- Any new editing feature, grace-as-action → out of milestone.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DESK-01 | `uv tool install` exposes a global `ngtui` that runs outside the dev venv and resolves the LifeOS trust stack from a clean login shell | **VERIFIED live**: `uv tool install --python 3.14 .` builds an isolated venv + `~/.local/bin/ngtui` shim; the shim's interpreter imports `backend.py` under a scrubbed `env -i` and resolves the stack via hardcoded defaults (Architecture Pattern 1). `~/.local/bin` is on `bash -l` AND `fish -l` PATH. |
| DESK-02 | A **key-less** `ngtui status --json` emits Waybar-shaped JSON (`text`/`tooltip`/`class`) from `live_verdict`/`tokens_left` — never reads the key, never needs root | **VERIFIED live**: monkeypatching `ng.read_key` to raise proved the status path (`read_state`/`sanctioned_config`/`live_verdict`/`tokens_left`) makes **zero** `read_key()` calls. `quota_decide` is pure (no key/NTP/sudo). Waybar JSON contract confirmed from the live `~/.config/waybar/config.jsonc` + Waybar wiki. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| PATH shim + isolated venv | OS package layer (`uv tool`) | — | `uv tool install` owns venv isolation + shim generation; not app code |
| Stack/data-dir resolution from clean env | `backend.py` module bootstrap | OS env (`environment.d`, instance) | `_resolve_stack_dir` + `NIGHTGUARD_DIR setdefault` resolve at import; the *product* default vs *instance* override is an OS/env concern (Phase 13) |
| Key-less verdict/token read | `backend.py` → trust stack (`guard.curfew_verdict`, `ctl.quota_decide`) | `.timecache` (NTP cache) | The trust stack owns all curfew/quota math; the TUI only re-exports it (PORT-02) |
| `status --json` shaping + fail-closed | `__main__.py` (new `status` cmd) | — | argv routing + JSON emission is entry-point glue, not trust logic |
| TTY guard | `__main__.py` (TUI path only) | — | Interactive launch precondition; status must run head-less |
| Inline-`sudo` commit (PTY) | `backend.commit()` → root control-CLI | terminal emulator (PTY) | The signer is root-only; the PTY is supplied by the launching terminal (Phase 12's `-e ngtui`) |
| Waybar poll cadence + signal refresh | Waybar config (Phase 12) | — | Out of scope here; constrains the JSON shape only |

## Standard Stack

### Core (already present — nothing new to install)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `uv` | `0.11.23` [VERIFIED: `uv --version` on live box] | Build wheel from `pyproject.toml`, create isolated tool venv, generate PATH shim | The project's mandated package manager (PROJECT.md); `uv tool install` is the idiomatic "global CLI from a project" path |
| CPython | `3.14.6` [VERIFIED: `uv python list`] | The `--python 3.14` interpreter for the isolated venv | `requires-python >=3.11`; 3.14 is the live venv version; `uv` auto-fetches if absent |
| `textual` | `8.2.7` [VERIFIED: pinned in `pyproject.toml`, installed by `uv tool install`] | The TUI runtime (status subcommand does NOT import it) | Already the sole third-party dep |
| `hatchling` | (build backend) [VERIFIED: `pyproject.toml`] | Builds the wheel `uv tool install` consumes | Already configured; `[tool.hatch.build.targets.wheel] packages = ["ngtui"]` |

### Supporting (stdlib only — honors lean-deps)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `argparse` | stdlib | Route `ngtui` (→ TUI) vs `ngtui status --json` (→ status) | In `__main__.py`; see Pattern 3 |
| `json` | stdlib | Emit the single-line Waybar object | In the `status` handler |
| `sys` | stdlib | `sys.stdin.isatty()` TTY guard; `sys.exit(0)` | TUI launch guard + status exit-0 |

**Installation (verified end-to-end on the live box):**
```bash
cd /home/danitrrga/dev/Projects/nightguard-control/ngtui
uv tool install --python 3.14 .
# → Installed 11 packages; "Installed 1 executable: ngtui"
# → shim: ~/.local/bin/ngtui -> ~/.local/share/uv/tools/ngtui/bin/ngtui
# (test install was run and then `uv tool uninstall ngtui`'d to leave the repo clean)
```

**Version verification (run live this session):** `uv 0.11.23`; `cpython-3.14.6` available; `textual==8.2.7` resolved with its 10 transitive deps (rich, pygments, markdown-it-py, linkify-it-py, mdit-py-plugins, mdurl, platformdirs, typing-extensions, uc-micro-py) — all pulled into the *isolated* tool venv, invisible to the system Python.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `uv tool install .` | `pipx install .` | Equivalent isolation/shim model, but `uv` is the project's mandated tool and is already installed; no reason to introduce `pipx` |
| `argparse` subcommand | bare `sys.argv` check (`if "status" in argv`) | argparse is stdlib, gives `--json` flag parsing + `-h` for free, and cleanly separates the head-less path; bare-argv is more brittle |
| `status` reading `live_verdict` (NTP-coupled) | `status` reading a cache-only verdict | `live_verdict` is the single source of truth (PORT-02) — but it can block ~2-4s on a cold NTP cache. See Pitfall 1 for the guard, not a replacement. |

## Package Legitimacy Audit

> Phase 11 installs **no new external packages**. The `status` subcommand is stdlib-only; the TUI dep (`textual==8.2.7`) was vetted and locked in Phase 10. `uv tool install` pulls textual's transitive deps into an isolated venv, but these are not *new* project dependencies — they are textual's own locked tree.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (none new) | — | N/A — Phase 11 adds zero dependencies |

**Packages removed due to slopcheck [SLOP] verdict:** none (no new packages)
**Packages flagged as suspicious [SUS]:** none

*slopcheck was not run because no new package is introduced. The textual transitive tree (rich, pygments, etc.) is the standard, widely-deployed textual dependency set already vetted in Phase 10.*

## Architecture Patterns

### System Architecture Diagram

```
                       ┌─────────────────────────────────────────────┐
   clean login shell   │  PATH = …:~/.local/bin:…  (bash -l & fish -l)│
   (NO NIGHTGUARD_* env)└──────────────────┬──────────────────────────┘
                                           │ runs
                              ~/.local/bin/ngtui  (shim, symlink)
                                           │ #!~/.local/share/uv/tools/ngtui/bin/python
                                           ▼
                              ngtui.__main__:main()
                                           │ argparse routes
                    ┌──────────────────────┴───────────────────────┐
                    │ (no subcommand)                    status --json│
                    ▼                                                ▼
            sys.stdin.isatty()?                        try: import ngtui.backend
            ├─ no  → loud fail, exit≠0                 │   (module bootstrap resolves
            └─ yes → NightguardApp().run()             │    STACK_DIR + NIGHTGUARD_DIR
                         │                             │    from hardcoded defaults)
                         │ App.suspend()               ├─ RuntimeError/OSError
                         ▼                             │   → {"text":"○ —",
              backend.commit()                         │      "class":"unavailable"}  exit 0
              sudo /usr/bin/python3 CTL commit         └─ ok → read_state()  ──┐ KEY-LESS
              (root signer; PTY from terminal)                                │ (no read_key,
                         │                                sanctioned_config() ─┤  no sudo,
                         ▼                                live_verdict() ──────┤  no HMAC)
              root control-CLI (sole signer)             tokens_left() ───────┘
                         │                                         │
                         ▼                                         ▼
   ┌────────────────────────────────────────┐        {"text","tooltip","class"} single line
   │ NIGHTGUARD_DIR = .../LifeOS/nightguard  │        → stdout → Waybar custom/nightguard (P12)
   │  guard.json          root:root 0644 ◄───┼────────── read_state()      (world-readable ✓)
   │  config.sanctioned.yaml root:root 0644 ◄┼────────── sanctioned_config (world-readable ✓)
   │  .guardkey           root:root 0600  ✗──┼────────── NEVER touched by the status path
   │  .timecache  (NTP cache, ≤120s TTL) ◄───┼── warmed every 60s by the root watchdog timer
   └────────────────────────────────────────┘
```

### Pattern 1: Clean-env stack resolution via module-level bootstrap (SC-1, SC-5)

**What:** `backend.py` resolves the trust stack at **import time**, before any subcommand runs. `_resolve_stack_dir()` reads `NIGHTGUARD_STACK_DIR` or falls back to `_DEFAULT_STACK_DIR` (hardcoded author path), then **pins** it (must contain `nightguard_ctl.py`, else `RuntimeError`). `NIGHTGUARD_DIR` is set via `os.environ.setdefault(...)` to a hardcoded author path.

**When to use:** This is the existing mechanism — Phase 11 relies on it; it does not need changing for the author.

**Verified behavior (run live under `env -i HOME=$HOME PATH=/usr/bin:/bin`, no `NIGHTGUARD_*`):**
```text
STACK_DIR      = /home/danitrrga/dev/Projects/LifeOS/scripts/nightguard
NIGHTGUARD_DIR = /home/danitrrga/dev/Projects/LifeOS/nightguard
verdict        = outside_curfew      tokens_left = 2      WEEKLY_TOKENS = 3
```
The installed-venv interpreter (`~/.local/share/uv/tools/ngtui/bin/python`) produced the identical result — proving the shim, not just `python -m ngtui`, resolves the stack from a clean shell (SC-1).

**Product-vs-instance note (Phase 13 flag, not a Phase 11 fix):** the hardcoded `/home/danitrrga/...` defaults are **author-instance config baked into product code**. They make SC-1/SC-5 pass *for the author* today (good — that is what Phase 11 needs). The publishable product must not ship those literals; Phase 13's README/`environment.d` route is where the generic default + "set `NIGHTGUARD_STACK_DIR`" guidance belongs. Do not rip the defaults out in Phase 11 — that would *break* the author's SC-1.

### Pattern 2: Key-less status data path (SC-2)

**What:** The four functions the status reader needs — `read_state()`, `sanctioned_config()`, `live_verdict(cfg, state)`, `tokens_left()` — source entirely from `root:root 0644` files and pure functions. None reads `.guardkey`.

**Verified (live, by monkeypatching `ngcommon.read_key`/`guard.ng.read_key`/`ctl.ng.read_key` to raise `AssertionError`):**
```text
PASS: status path made NO read_key() call.  verdict=outside_curfew tokens=2
```
- `read_state()` → `ng.load_state()` → `json.load(guard.json)` — file read only.
- `sanctioned_config()` / `sanctioned_text()` → `ng.file_bytes(SANCTIONED)` — file read only.
- `live_verdict()` → `guard.curfew_verdict(cfg, state)` — **no key**, but DOES resolve true-time (see Pitfall 1).
- `tokens_left()` → `ctl.quota_decide([], state, tz)` — **pure**: lazy week-reset arithmetic only, no key/NTP/sudo (verified by reading `nightguard_ctl.py:241-260`).

### Pattern 3: argv routing without disturbing the bare-`ngtui` launch (SC-2, SC-4)

**What:** Add an argparse layer in `__main__.py`. Bare `ngtui` (no subcommand) → TUI (current behavior, preserved). `ngtui status [--json]` → the head-less status handler. The status handler **must not** import `ngtui.app`/`textual`, and **must** wrap `import ngtui.backend` in try/except (the import itself can raise — see Pitfall 2).

**Example (pattern — planner finalizes):**
```python
# Source: synthesized from the verified import/fail-closed behavior this session
import sys

def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] == "status":
        sys.exit(_status(argv[1:]))   # head-less; emits JSON, exits 0
    _run_tui()                         # bare `ngtui`

def _run_tui() -> None:
    if not sys.stdin.isatty():         # SC-4 loud fail — TUI path ONLY
        sys.stderr.write("ngtui must be run in a terminal (no TTY on stdin).\n")
        raise SystemExit(2)
    from ngtui.app import NightguardApp   # import textual lazily, after the guard
    NightguardApp().run()

def _status(args) -> int:
    import json
    UNAVAIL = {"text": "○ —", "class": "unavailable"}
    try:
        import ngtui.backend as b          # can raise RuntimeError (bad STACK_DIR)
        state = b.read_state()
        cfg = b.sanctioned_config()
        verdict = b.live_verdict(cfg, state)   # see Pitfall 1: guard the cold-cache path
        tokens = b.tokens_left()
        obj = _shape(verdict, tokens, state)   # {"text","tooltip","class"}
    except Exception:                          # broad on purpose — fail closed
        obj = UNAVAIL
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    return 0                                   # ALWAYS exit 0 (SC-3)
```

**Textual/argparse note:** Textual's `App.run()` does **not** parse `sys.argv` itself, so adding an argparse front controller does not conflict. Keep `from ngtui.app import NightguardApp` *inside* `_run_tui()` (lazy import) so `ngtui status` never pays textual's import cost or pulls a GUI dependency onto the head-less path.

### Pattern 4: PTY-independent commit interpreter (SC-4)

**What:** The global install changes the *launching* interpreter (shim → `~/.local/share/uv/tools/ngtui/bin/python`), but `backend.commit()` hardcodes the *sudo-target* interpreter as `/usr/bin/python3` (sudoers `Cmnd_Alias` shape). These are independent.

**Verified (live):** `inspect.getsource(backend.commit)` confirms `/usr/bin/python3` is in the argv; the shim launches via the isolated venv python. The sudoers match therefore survives the global install — the commit's interpreter never changes. The *real* SC-4 risk is not the interpreter but whether `App.suspend()` still releases a genuine PTY when the shim is launched inside a terminal — which is a Phase-12 launch-path concern (`-e ngtui` in a real terminal) and was already de-risked for `python -m ngtui` in the Wave-0 spike (`SPIKE-NOTES.md`, A2 CONFIRMED).

### Anti-Patterns to Avoid

- **Ripping out the hardcoded `_DEFAULT_STACK_DIR` in Phase 11.** It is what makes the author's clean-shell SC-1/SC-5 pass. Generic-default work is Phase 13.
- **Importing `textual`/`ngtui.app` on the `status` path.** Slows every bar poll and couples a head-less reader to a GUI runtime. Lazy-import the app only on the TUI branch.
- **Calling `read_key()`, `sudo`, or `backend.commit()` from `status`.** Violates DESK-02 and the "window, never a lever" invariant.
- **Letting `status` exit non-zero or raise.** A crashing exec breaks the eventual Waybar module (SC-3). Catch broadly, emit `unavailable`, exit 0.
- **A naked `live_verdict()` call with no cold-cache guard.** Can block the bar ~2-4s. See Pitfall 1.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Global command + isolated venv + PATH shim | A hand-written launcher script + manual venv | `uv tool install --python 3.14 .` | Verified to produce exactly the isolated venv + `~/.local/bin/ngtui` shim with textual's full tree; reproducible, uninstallable |
| Curfew verdict / token math | A reimplemented classifier in the status reader | `backend.live_verdict` / `backend.tokens_left` (→ trust stack) | PORT-02: a second implementation would drift from the root signer; these are the single source of truth and proven key-less |
| Waybar JSON schema | A custom bar protocol | The documented `{text,alt,tooltip,class,percentage}` object, `return-type: json` | Verified against the live `~/.config/waybar/config.jsonc` (weather/voxtype/indicators) and the Waybar wiki |
| NTP / true-time | A new clock query in the status path | The trust stack's `.timecache` (warmed every 60s by the root watchdog) | Reuses the existing monotonic-anchored cache; a new query would re-introduce the blocking problem |

**Key insight:** Phase 11 is glue. Almost everything load-bearing already exists and was proven working on the live instance this session — the work is wiring an entry-point and a JSON shape around it, plus one TTY guard.

## Runtime State Inventory

> Phase 11 installs a command and adds a subcommand — it does **not** rename or migrate stored state. This inventory confirms nothing is silently left behind.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `guard.json` (`weekly_spent`, `week_anchor`, `ledger`, `grace`), `config.sanctioned.yaml`, `.timecache` — all read-only from the status path; **no writes, no schema change** | None — status is read-only |
| Live service config | The root `nightguard-watchdog.timer` (every 60s) keeps `.timecache` fresh, which the status path depends on for a warm (non-blocking) read. **Not modified by this phase.** | None — but note the dependency (Pitfall 1) |
| OS-registered state | `uv tool install` registers a shim at `~/.local/bin/ngtui` and a venv at `~/.local/share/uv/tools/ngtui/`. A re-install/upgrade requires `uv tool install --force` or `uv tool upgrade`. | Document the (re)install command; `uv tool uninstall ngtui` to remove |
| Secrets/env vars | `NIGHTGUARD_STACK_DIR` / `NIGHTGUARD_DIR` are read at import. The installed shim has **neither** in a clean shell → falls back to hardcoded author defaults (verified). No secret is read by the status path. | None for the author; generic default is a Phase 13 concern |
| Build artifacts | `ngtui/.venv/` (the dev venv) is separate from the `uv tool` venv. No stale egg-info issue (hatchling wheel build, no editable install in `pyproject.toml` except the pytest `pythonpath`). | None |

## Common Pitfalls

### Pitfall 1: `live_verdict` blocks the bar on a cold NTP cache (the #1 design risk)

**What goes wrong:** `backend.live_verdict` → `guard.curfew_verdict` → `guard.true_unix()`. On a **warm** `.timecache` (≤120s old, same boot_id) the read is instant. On a **cold** cache (boot_id change, >120s gap, or the watchdog stalled) it falls through to a live SNTP query (2s timeout) and then an HTTP `HEAD` (2s timeout).

**Measured this session (live):**
- Warm cache: `live_verdict` = **0.001s** (total `status` process incl. import ≈ 40ms).
- Cold cache (forced miss + unreachable NTP): `live_verdict` = **2.094s**; with HTTP also unreachable it can reach ~4s.

**Why it happens:** The status reader reuses the same true-time path the guard uses. Normally the root watchdog timer (`OnUnitActiveSec=60`, TTL 120s) keeps the cache warm, so the bar never pays the cost — but a sleep/resume, a reboot, or a stalled timer opens a window where a bar poll would hang for seconds.

**How to avoid (planner picks one — discretion):**
1. **Bound it at the bar layer (Phase 12):** wrap the exec in `timeout 1 ngtui status --json` and treat a timeout as `unavailable`. Simple, but Phase 12's concern; Phase 11 should still not hang the *process*.
2. **Cache-only read in `status`:** have the status reader prefer the cached `.timecache` and skip the network fall-through (e.g. an env flag the status path sets, or a read that tolerates a stale/`offline` source rather than querying). Keeps the status reader self-contained and always fast.
3. **Internal timeout/`unavailable` fallback:** run the verdict resolution under a short watchdog and degrade to `unavailable` past ~500ms.

**Recommendation:** Phase 11 should make the `status` path **not perform a synchronous network query** — option 2 (read the cache, never trigger the SNTP/HTTP fall-through). This keeps SC-2/SC-3 robust regardless of how Phase 12 wires the poll. **Flag for discuss-phase** — this is the one genuine design decision in Phase 11.

**Warning signs:** A Waybar module that stutters/freezes for ~2s after a reboot or resume; `ngtui status` taking >100ms in `time ngtui status --json`.

### Pitfall 2: The stack-resolution `RuntimeError` is raised at *import*, not at call

**What goes wrong:** A bogus/unset stack (e.g. `NIGHTGUARD_STACK_DIR=/nonexistent`) makes `import ngtui.backend` raise `RuntimeError` at module top-level (`_resolve_stack_dir`). If the `status` handler only wraps the *function calls* in try/except (not the import), the `unavailable` fallback is bypassed and the process crashes — breaking SC-3.

**Verified (live):** `NIGHTGUARD_STACK_DIR=/nonexistent python -c "import ngtui.backend"` → `RuntimeError: ... does not contain nightguard_ctl.py`.

**How to avoid:** Put `import ngtui.backend` **inside** the `try:` block of the status handler (as in Pattern 3). Catch broadly (`except Exception`).

**Warning signs:** A traceback on stdout/stderr instead of the `unavailable` JSON when the stack path is wrong.

### Pitfall 3: Missing data dir yields `"locked"`, not `"unavailable"`

**What goes wrong:** If `NIGHTGUARD_DIR` points at a dir with no `guard.json`/`config.sanctioned.yaml`, the reads degrade gracefully but **not** to `unavailable`: `read_state()` → `{}`, `sanctioned_config()` → `{}`, `live_verdict()` → `"locked"` (fail-safe locked), `tokens_left()` → `3`.

**Verified (live):** `NIGHTGUARD_DIR=/tmp/nonexistent-ng` → `live_verdict=locked, tokens_left=3`, no exception.

**Why it matters:** The `unavailable` class is reserved for *errors that prevent reading* (import failure, OSError, malformed stack) — driven by the **exception** path, not by empty data. Empty/uninitialized data correctly maps to a (fail-safe) locked verdict, which the bar should render as locked, not as `unavailable`. Do not conflate the two.

**How to avoid:** Map verdict strings to `class` explicitly (`locked`/`grace_active`/`outside_curfew`/`clock_tamper`/`offline_blocked`), and only emit `unavailable` from the `except` branch.

### Pitfall 4: The TTY guard must be on the TUI path only

**What goes wrong:** A blanket `sys.stdin.isatty()` check at the top of `main()` would (a) break the head-less `ngtui status` (it runs from a Waybar exec with no TTY) and (b) potentially break a piped TUI launch. The guard belongs **only** on the interactive `_run_tui()` branch.

**Verified (live):** `ngtui < /dev/null` today does **not** fail loudly — Textual starts writing escape sequences into the non-TTY pipe (garbage), confirming the guard is genuinely missing and that the fix must be scoped to the TUI branch so `status` stays head-less.

**How to avoid:** Guard inside `_run_tui()` after argparse has already routed `status` elsewhere (Pattern 3).

### Pitfall 5: Stale `__main__.py` docstring

**What goes wrong:** The current `__main__.py` docstring says the bootstrap "sets NIGHTGUARD_DIR" — but `backend.py` uses `os.environ.setdefault` (only if unset) with a hardcoded path, and `_DEFAULT_STACK_DIR` is also hardcoded. The docstring undersells the instance-coupling. When the planner edits `__main__.py`, update the docstring to reflect the argparse routing + the hardcoded-default reality.

## Code Examples

### Verified key-less status read (the data path the subcommand wraps)
```python
# Source: live verification this session, env -i (no NIGHTGUARD_*), proven key-less
import ngtui.backend as b
state   = b.read_state()                       # json.load(guard.json) — root:root 0644, readable
cfg     = b.sanctioned_config()                # file_bytes(config.sanctioned.yaml) — 0644, readable
verdict = b.live_verdict(cfg, state)           # guard.curfew_verdict — no key (see Pitfall 1 for NTP)
tokens  = b.tokens_left()                       # ctl.quota_decide([], state, tz) — pure, no key/NTP/sudo
# verdict ∈ {"locked","grace_active","outside_curfew","clock_tamper","offline_blocked"}
```

### Waybar single-line JSON contract (from the live config + wiki)
```jsonc
// Source: ~/.config/waybar/config.jsonc (custom/weather, custom/voxtype) + Waybar wiki Module:Custom
{"text": "🌙 2", "tooltip": "Locked · 2 tokens left", "class": "locked"}
// fields: text (bar label) · alt (selects format-icons) · tooltip (hover) ·
//         class (→ CSS #custom-nightguard.locked) · percentage (array icon select)
// MUST be a single line. return-type: "json" in the module. Exit code is not significant for json.
```

### Fail-closed unavailable object (SC-3)
```python
# Source: ROADMAP SC-3 — emitted from the except branch, exit 0
{"text": "○ —", "class": "unavailable"}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `python -m ngtui` from the dev venv with explicit `NIGHTGUARD_*` env | `uv tool install` shim resolving the stack from a clean shell | This phase | The dev-shell env crutch is removed; resolution relies on `backend.py` hardcoded defaults (author) / `environment.d` (product, Phase 13) |
| `pipx` for global Python CLIs | `uv tool install` | Project-wide (PROJECT.md) | Single mandated package manager; faster, already installed |

**Deprecated/outdated:**
- The `__main__.py` docstring's claim that the bootstrap "sets NIGHTGUARD_DIR" without qualification — it's a `setdefault` to a hardcoded author path (update when editing).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Keeping the hardcoded `_DEFAULT_STACK_DIR`/`NIGHTGUARD_DIR` author defaults is acceptable for Phase 11 (generic default deferred to Phase 13) | Pattern 1, Anti-Patterns | If the product must ship generic defaults *now*, Phase 11 scope grows; but ROADMAP explicitly scopes the generic README/`environment.d` path to Phase 13 — low risk |
| A2 | The cold-cache NTP blocking window is best solved by making `status` cache-only (option 2) vs. a bar-layer `timeout` (option 1) | Pitfall 1 | If discuss-phase prefers the bar-layer timeout, the status reader stays simpler but can still hang the process briefly — surface to the user |
| A3 | Phase 12's `-e ngtui` real-terminal launch preserves the PTY for `App.suspend()` (SC-4 commit path), as the Wave-0 spike confirmed for `python -m ngtui` | Pattern 4 | The interpreter-independence is *verified*; the PTY-via-real-terminal is *carried* from the spike — re-verify end-to-end from the installed shim during Phase 11 execution (it is SC-4's literal requirement) |

## Open Questions

1. **Cache-only vs. bar-timeout for the NTP blocking window (Pitfall 1).**
   - What we know: warm = 0.001s, cold = ~2-4s; the watchdog keeps the cache warm every 60s.
   - What's unclear: whether the status reader should self-limit (option 2) or rely on Phase 12's exec `timeout` (option 1).
   - Recommendation: make `status` cache-only so it is robust independent of the bar wiring; raise in discuss-phase.

2. **Does the installed shim's `App.suspend()` still hand sudo a real PTY end-to-end?** (SC-4)
   - What we know: interpreter independence is verified; the Wave-0 spike confirmed suspend→sudo→resume for `python -m ngtui`.
   - What's unclear: the *installed-shim* end-to-end commit was not exercised this session (it would consume a real weekly token).
   - Recommendation: execute SC-4 as a live human-verify checkpoint during the phase (a real loosen-with-token commit from `~/.local/bin/ngtui` inside a terminal), not in research.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | SC-1 global install | ✓ | 0.11.23 | — |
| CPython 3.14 | `--python 3.14` venv | ✓ | 3.14.6 (also 3.14.5 at `/usr/bin/python3.14`) | `uv` auto-downloads if absent |
| `~/.local/bin` on login PATH | SC-1 shim resolution | ✓ | bash -l AND fish -l | — |
| LifeOS trust stack (`nightguard_ctl.py` etc.) | backend import | ✓ | at `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard` | RuntimeError → `unavailable` (status); loud fail (TUI) |
| `guard.json` + `config.sanctioned.yaml` user-readable | SC-5 status reads | ✓ | `root:root 0644` (world-readable) | none needed — flag is GREEN |
| `.guardkey` user-readable | (must be DENIED) | ✗ (correct) | `root:root 0600` | n/a — denial is the desired state |
| Root `nightguard-watchdog.timer` warming `.timecache` | warm (non-blocking) `live_verdict` | ✓ | every 60s; last ticks 18:22/18:23/18:24 | cache-only status read (Pitfall 1) |
| `/usr/bin/python3` (sudo commit target) | SC-4 commit | ✓ | 3.14.5 | none — sudoers `Cmnd_Alias` hardcodes this path |

**Missing dependencies with no fallback:** none — every dependency Phase 11 needs is present.
**Missing dependencies with fallback:** none blocking; the only graceful-degradation path is the `unavailable` status fallback when the stack is absent (which is the SC-3 design, not a missing dep).

## Validation Architecture

> `workflow.nyquist_validation: true` in config.json — this section is required. The critical failure modes for Phase 11 are: **key-lessness** of the status path, **fail-closed** behavior, **clean-env resolution**, and **PTY survival**.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` (configured in `ngtui/pyproject.toml` → `[tool.pytest.ini_options]`, `pythonpath=["."]`, `testpaths=["tests"]`) |
| Config file | `ngtui/pyproject.toml` |
| Quick run command | `cd ngtui && .venv/bin/python -m pytest -x -q` |
| Full suite command | `cd ngtui && .venv/bin/python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DESK-02 | status path makes ZERO `read_key()` calls (key-less) | unit | `pytest tests/test_status.py::test_status_never_reads_key -x` (monkeypatch `ng.read_key`→raise; assert no raise) | ❌ Wave 0 |
| DESK-02 | `status --json` emits a single-line, `jq`-valid `{text,tooltip,class}` | unit | `pytest tests/test_status.py::test_status_json_shape -x` | ❌ Wave 0 |
| SC-3 | import/stack failure → `{"text":"○ —","class":"unavailable"}` exit 0 | unit | `pytest tests/test_status.py::test_status_fail_closed_on_bad_stack -x` (`NIGHTGUARD_STACK_DIR=/nonexistent`) | ❌ Wave 0 |
| SC-3 | empty data dir → `locked` class, NOT `unavailable` | unit | `pytest tests/test_status.py::test_empty_data_is_locked_not_unavailable -x` | ❌ Wave 0 |
| DESK-02 | verdict→class mapping covers all 5 verdict strings | unit | `pytest tests/test_status.py::test_verdict_class_map -x` | ❌ Wave 0 |
| SC-2/Pitfall 1 | `status` does not perform a synchronous network query (fast on cold cache) | unit | `pytest tests/test_status.py::test_status_no_blocking_ntp -x` (assert no `_sntp`/`_http_time` call, or runtime < threshold) | ❌ Wave 0 |
| SC-4 | bare `ngtui` with no TTY fails loudly (exit≠0) | unit | `pytest tests/test_status.py::test_tui_requires_tty -x` (monkeypatch `sys.stdin.isatty`→False; assert `SystemExit`) | ❌ Wave 0 |
| SC-1 | `uv tool install` shim resolves stack from clean env | integration/manual | `env -i HOME=$HOME PATH=$HOME/.local/bin:/usr/bin:/bin ngtui status --json` returns valid JSON | manual (verified this session) |
| SC-4 | real loosen-with-token commit from the installed shim (PTY) | manual / human-verify | live walkthrough in a real terminal (consumes a token) | manual checkpoint |

### Sampling Rate
- **Per task commit:** `cd ngtui && .venv/bin/python -m pytest -x -q`
- **Per wave merge:** `cd ngtui && .venv/bin/python -m pytest`
- **Phase gate:** Full suite green + the two manual checkpoints (SC-1 clean-env shim, SC-4 live commit) before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `ngtui/tests/test_status.py` — covers DESK-02, SC-2, SC-3, SC-4 (the new subcommand + TTY guard). The status handler should be structured so its core (verdict/tokens → JSON shape, and the fail-closed wrapper) is a **pure, importable function** unit-testable without a TTY or a subprocess (mirrors Phase 10's `verdict_display`/`token_meter` pure-helper pattern).
- [ ] `ngtui/tests/conftest.py` — fixtures for a temp `NIGHTGUARD_DIR` with crafted `guard.json`/`config.sanctioned.yaml` (locked / grace / outside / empty), and a `read_key`-explodes monkeypatch fixture.
- [ ] Framework install: already present (`.venv` has pytest; tests dir exists with prior Phase 10 headless tests).

## Security Domain

> `security_enforcement` not set to `false` → included. Phase 11 is a read-only reader + a packaging step; the security surface is small but real (a key-less status path that must never become a lever).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | The status path is unprivileged-by-design; the only auth is the existing `sudo` commit gate (unchanged) |
| V3 Session Management | no | No sessions |
| V4 Access Control | **yes** | Least privilege: status reads only `root:root 0644` artifacts; `.guardkey` (`0600`) stays inaccessible; `status` never calls `sudo`/`commit` (verified key-less) |
| V5 Input Validation | **yes** | `NIGHTGUARD_STACK_DIR` is resolved + pinned (must contain `nightguard_ctl.py`) before import/sudo — the existing CR-02 control; `status` emits JSON via `json.dumps` (no string interpolation into the bar) |
| V6 Cryptography | no | No crypto added — the status path computes no HMAC, reads no key |

### Known Threat Patterns for {ngtui status + uv tool install on Linux}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Poisoned `NIGHTGUARD_STACK_DIR` redirects the imported/sudo'd stack | Tampering / EoP | Existing `_resolve_stack_dir` pin (CR-02): resolve to realpath + require `nightguard_ctl.py` present, else `RuntimeError` (fail closed). Verified live. |
| A bar/launcher surface used to loosen the curfew | Elevation of Privilege | "Window, never a lever": `status` is read-only, never imports the commit path; no `on-click` loosen action (BAR-03 enforces in Phase 12) |
| JSON injection into the Waybar bar via crafted config text in `tooltip` | Tampering | Emit via `json.dumps` (proper escaping); the tooltip sources from controlled verdict/token values, not raw user config |
| Status exec hangs the bar (DoS-by-poll) | Denial of Service | Cache-only verdict read (Pitfall 1) so no synchronous network query; bar-layer `timeout` as defense-in-depth (Phase 12) |
| Global shim shadows another `ngtui` on PATH | Spoofing | `~/.local/bin` precedence is user-owned; `uv tool install` is the only writer; no collision found (`which ngtui` clean after install) |

## Sources

### Primary (HIGH confidence — verified live this session)
- Live box: `uv tool install --python 3.14 .` run end-to-end → shim `~/.local/bin/ngtui` → `~/.local/share/uv/tools/ngtui/bin/ngtui` (then `uv tool uninstall ngtui`). `uv 0.11.23`, `cpython 3.14.6`.
- Live box: `env -i` scrubbed-env import of `ngtui.backend` → STACK_DIR/NIGHTGUARD_DIR resolution + `live_verdict=outside_curfew`, `tokens_left=2` (SC-1, SC-5).
- Live box: `ls -la` on `/home/danitrrga/dev/Projects/LifeOS/nightguard/` → `guard.json`/`config.sanctioned.yaml` `root:root 0644`, `.guardkey` `root:root 0600`; `cat` confirms user can read the first two, is denied the key (SC-5 GREEN).
- Live box: monkeypatch `read_key`→raise across `ng`/`guard`/`ctl` → status path makes zero key reads (DESK-02 key-lessness).
- Live box: timed `live_verdict` warm (0.001s) vs cold (2.094s) cache (Pitfall 1).
- Live box: `bash -lc` AND `fish -lc` PATH both include `~/.local/bin`.
- Source read: `ngcommon.py` (paths, `load_state`, `read_key`), `guard.py` (`curfew_verdict`, `true_unix`, `_sntp`/`_http_time`), `nightguard_ctl.py:202-260` (`classify_change`, `quota_decide` purity, `WEEKLY_TOKENS=3`), `ngtui/ngtui/backend.py`, `__main__.py`, `app.py`, `SPIKE-NOTES.md`.
- Live `~/.config/waybar/config.jsonc` — `return-type: json` modules; signal slots 7/8/9/10 in use (free: 11+); `class`/`alt`/`format-icons` conventions.
- `systemctl status nightguard-watchdog` + `.timer` → `OnUnitActiveSec=60`, live ticks 18:22-18:24; `.timecache` TTL 120s.

### Secondary (MEDIUM confidence)
- Waybar wiki — Module: Custom (JSON shape `{text,alt,tooltip,class,percentage}`, single-line, `return-type: json`, `#custom-<name>.<class>` CSS). Cross-confirmed against the live config's actual usage.

### Tertiary (LOW confidence)
- None — every Phase 11 claim was verified against the live box or source.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `uv tool install` run for real; versions read from the live box.
- Architecture (clean-env resolution, key-lessness, argv routing, PTY independence): HIGH — verified live with scrubbed env, monkeypatch, and source inspection.
- Pitfalls (cold-cache NTP, import-time RuntimeError, empty-data-is-locked, TTY guard): HIGH — each reproduced live.
- SC-4 end-to-end commit from the installed shim: MEDIUM — interpreter independence verified; the live token-spending commit is deferred to a phase human-verify checkpoint (would consume a real weekly token to test).

**Research date:** 2026-06-25
**Valid until:** 2026-07-25 (stable; the only fast-moving piece is `uv`, and the install mechanics verified here are long-stable). Re-confirm `.timecache` warmth assumption if the watchdog timer cadence changes.
