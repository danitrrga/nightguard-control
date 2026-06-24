# Architecture Research — v2.1 Desktop Integration

**Domain:** omarchy/Hyprland desktop integration for an existing Python Textual TUI (`ngtui`) layered over a separate, root-owned LifeOS trust stack
**Researched:** 2026-06-24
**Confidence:** HIGH (verified against the live box: omarchy launch helpers, Waybar config, Hyprland windowrules, `backend.py` seam, `uv 0.11.23`)

> This is a **subsequent-milestone** architecture doc: it describes how the NEW desktop
> pieces bolt onto the system that v2.0 shipped. It does not re-derive the trust-stack
> or TUI architecture (see the phase-10 TUI research and `docs/design-spec.md`). The
> single load-bearing seam it builds on is `ngtui/ngtui/backend.py` and its
> `_resolve_stack_dir()` / `NIGHTGUARD_DIR` env bootstrap.

---

## 1. System Overview — where the new pieces sit

```
┌──────────────────────────────────────────────────────────────────────────┐
│  DESKTOP SURFACE  (user session, key-less, NEW in v2.1)                    │
│                                                                            │
│   Waybar bar           App launcher (wofi/walker)        Hyprland          │
│   ┌────────────┐       ┌──────────────────────┐         ┌──────────────┐  │
│   │custom/     │       │ nightguard.desktop    │         │ windowrule:  │  │
│   │ nightguard │       │  Exec=omarchy-launch- │         │ float org.   │  │
│   │ (icon+     │       │   tui ngtui           │         │ omarchy.ngtui│  │
│   │  status)   │       └──────────┬───────────┘         └──────┬───────┘  │
│   └─────┬──────┘                  │ left-click /                │          │
│         │ exec (poll/signal)      │ .desktop launch             │ tags the │
│         │   ngtui status --json   │                             │ window   │
│         │ on-click → omarchy-     ▼                             ▼          │
│         │   launch-or-focus-tui ngtui  ──►  floating terminal ── runs ──┐  │
│         │ on-click-right → ngtui menu / wofi                            │  │
│         └────────────────────────────────────────────┐                 │  │
└──────────────────────────────────────────────────────┼─────────────────┼──┘
                                                        │ both import     │
                                                        ▼ ngtui.backend   │
┌──────────────────────────────────────────────────────────────────────────┐
│  ngtui PACKAGE  (this repo — installed by `uv tool install`)              │
│  isolated venv at ~/.local/share/uv/tools/ngtui/  ; shim on PATH          │
│                                                                            │
│   console_scripts:                                                         │
│     ngtui            → ngtui.__main__:main         (the TUI — existing)    │
│     ngtui status     → ngtui.status_cli:main       (Waybar JSON — NEW)     │
│       (a subcommand on the same shim — see §3)                            │
│                                                                            │
│   backend.py  ── _resolve_stack_dir() reads NIGHTGUARD_STACK_DIR or the    │
│                  baked-in author default, sys.path.insert, imports ───────┐│
└──────────────────────────────────────────────────────────────────────────┼┘
                                                                            │ import
                                                                            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  LifeOS TRUST STACK  (SEPARATE repo — NOT shipped by this milestone)      │
│   /home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/                  │
│     ngcommon.py · guard.py · nightguard_ctl.py · nightguard.sudoers        │
│     systemd/ (root system watchdog)                                        │
│   key-less reads (load_state / curfew_verdict) ← Waybar + TUI read path    │
│   sign path: TUI shells `sudo /usr/bin/python3 nightguard_ctl.py commit`   │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | New/Modified | Responsibility | Runs as | Key access |
|-----------|--------------|----------------|---------|------------|
| `ngtui` console script | existing | Launch the Textual TUI (the editor) | user | none (sign via sudo) |
| `ngtui status --json` | **NEW** | Emit one Waybar JSON line from the read-only verdict/token surface | user | **none — key-less reads only** |
| `nightguard.desktop` | **NEW (shipped)** | Launcher entry; `Exec=` opens the TUI in a floating terminal | — | — |
| brand icon (`hicolor/.../nightguard.png` + scalable) | **NEW (shipped)** | Icon for `.desktop` + Waybar | — | — |
| Hyprland windowrule | **NEW (split)** | `float`/`center`/`size` the `org.omarchy.ngtui` window | — | — |
| Waybar module snippet | **NEW (split)** | Wire `custom/nightguard` into the user's bar | — | — |
| autostart unit / `exec-once` | **NEW (instance)** | Optional login pin | user | none |
| `PKGBUILD` | **NEW (shipped)** | AUR packaging; declares the trust-stack dependency | — | — |

---

## 2. The launcher-environment problem (THE core integration risk)

**Verified facts about `uv tool install` (uv 0.11.23):**
- It builds an **isolated venv** at `~/.local/share/uv/tools/ngtui/` and drops thin
  shims for every `[project.scripts]` entry into `~/.local/bin` (on PATH via
  `uv tool update-shell`).
- The shim execs the venv interpreter directly. It does **NOT** source the dev shell,
  the project `.venv`, or any `env NIGHTGUARD_STACK_DIR=… NIGHTGUARD_DIR=…` prefix the
  author currently uses to run from the repo (PROJECT.md line 152).
- `.desktop` `Exec=` and a Waybar `exec` run in an even more minimal environment than an
  interactive shell (login env only; no `.bashrc`/`.zshrc` interactive block).

**Consequence:** when `ngtui` is launched from the bar / app menu, the **only** thing
that resolves the external LifeOS stack is `backend.py`'s baked-in defaults:
`_DEFAULT_STACK_DIR = ".../LifeOS/scripts/nightguard"` and the `os.environ.setdefault`
of `NIGHTGUARD_DIR`. Those defaults already point at the author's paths and
`_resolve_stack_dir()` fails closed if `nightguard_ctl.py` is absent. **So for the
author's own box, the globally-installed launcher works with zero env injection** — the
defaults ARE the launcher's environment.

**Design decision — do NOT make the launcher inject env (for the author).** The repo
defaults are the contract. Injecting `NIGHTGUARD_STACK_DIR` into the `.desktop`/Waybar
exec would (a) duplicate the path in a third place that can drift, and (b) push
author-specific paths into shipped, publishable artifacts — violating the two-layer
split. Instead:

| Audience | How the launcher resolves the stack |
|----------|-------------------------------------|
| **Author (this box)** | `backend.py` defaults already point at LifeOS → launcher needs no env. The `.desktop`/Waybar exec stay path-free and shippable. |
| **Other installers (AUR/README)** | Set `NIGHTGUARD_STACK_DIR`/`NIGHTGUARD_DIR` **once, globally** — `~/.config/environment.d/nightguard.conf` (systemd user env, picked up by uwsm/Hyprland and thus by Waybar `exec` and `.desktop` `Exec`). This is the single sanctioned env hook; the launcher artifacts stay generic. |

> **environment.d is the right injection point**, not the `.desktop` file: omarchy runs
> the session under uwsm (`uwsm-app` wraps every launch — confirmed in
> `omarchy-launch-tui`), so `~/.config/environment.d/*.conf` variables are exported into
> the whole graphical session, reaching both Waybar's `exec` child and the terminal the
> `.desktop` spawns. One file, session-wide, instance-owned.

**Open item for the build phase:** the baked-in `_DEFAULT_STACK_DIR` is fine for the
author but is an author-specific literal in a "publishable" package. Recommend the
packaging phase change the default to fail with a clear "set NIGHTGUARD_STACK_DIR"
message when the path is absent **and** the env is unset, rather than hard-coding one
user's home. (Today it already RuntimeErrors if the dir lacks `nightguard_ctl.py`, so
the failure is already loud — this is a message-quality refinement, LOW urgency.)

---

## 3. Waybar module ↔ app data flow

### The status reader is a NEW key-less entry point in THIS package

The read surface already exists as pure helpers in `ngtui/ngtui/widgets/status.py`
(`verdict_display`, `token_meter`) sourcing everything from `backend` (`read_state`,
`live_verdict`, `tokens_left`, `sanctioned_config`). A Waybar reader is a thin
**non-Textual** main that calls the same `backend` functions and prints one JSON line.

**Decision: ship it as a second entry point in `pyproject.toml`/`__main__`, NOT a
standalone script.** Rationale:
- It must import `ngtui.backend` to reuse the verdict/token logic and the
  stack-resolution bootstrap — a standalone script outside the package would have to
  re-implement `sys.path` surgery and re-derive verdict mapping (drift risk, DRY
  violation, and it would need the same env story solved twice).
- A console entry rides the same isolated venv + PATH shim that `uv tool install`
  already produces, so `omarchy`/Waybar can call it by bare name.
- It keeps the desktop surface inside the published product (the Waybar reader is
  generic; only the *wiring* into the user's bar is instance-specific).

**Two viable shapes — recommend the subcommand:**

| Option | Shape | Verdict |
|--------|-------|---------|
| **A. Subcommand (recommended)** | `ngtui status --json` — `__main__:main` parses argv; bare `ngtui` runs the TUI, `ngtui status --json` prints Waybar JSON and exits | One shim, one name on PATH, discoverable (`ngtui --help`), matches the question's "new `ngtui status --json`". Importing `ngtui.app`/Textual is deferred so `status` stays light. |
| **B. Separate entry** | `ngtui-status` → `ngtui.status_cli:main` | Cleaner separation, but adds a second PATH name and a second thing to remember. Use only if argv routing in `__main__` feels heavy. |

> If you pick A, refactor `__main__.main()` to dispatch: `status` → a `status_cli`
> module that imports only `backend` (NOT `ngtui.app`, so no Textual/TTY import on the
> hot Waybar poll path); anything else → `NightguardApp().run()`.

### Waybar JSON contract (verified field set)

`return-type: "json"` accepts: `text`, `alt`, `tooltip`, `class`, `percentage`. Map the
existing verdict/token model onto them:

```json
{
  "text": "",                         // brand glyph or short status mark
  "alt": "locked",                     // drives format-icons if you want per-state glyphs
  "tooltip": "LOCKED · curfew until 06:00\n2 of 3 tokens · resets Mon 2026-06-29",
  "class": "locked",                   // CSS hook: locked|open|grace|tamper|offline|unavailable
  "percentage": 66                     // optional: tokens_left/WEEKLY_TOKENS*100, or grace remaining
}
```

- `class` ← the verdict role (reuse `verdict_display`'s colour-role string).
- `tooltip` ← verdict caption + `token_meter` text.
- **Fail-closed in the reader too:** unknown/exception → emit
  `{"text":"","class":"unavailable"}` (exactly the omarchy `weather.sh` precedent) and
  exit 0, so a transient stack error never breaks the bar.

### Refresh strategy

| Mechanism | Use it for |
|-----------|-----------|
| `interval` (e.g. 30–60s) | Baseline poll — cheap; the reader is a sub-100ms key-less read of `guard.json` + config. |
| `signal` (`SIGRTMIN+N`) | **Push refresh after a commit.** When the TUI commits an edit, have it `kill -SIGRTMIN+N $(pidof waybar)` so the bar updates immediately instead of waiting for the next interval. This is the clean coupling between the editor and the bar — no shared state, just a signal. |

### Key-less / no-root property — CONFIRMED

The Waybar reader calls only `read_state()` (`ng.load_state()`), `live_verdict()`
(`guard.curfew_verdict()`), `sanctioned_config()`/`sanctioned_text()`
(`ng.file_bytes(ng.SANCTIONED)`), and `tokens_left()` (`ctl.quota_decide`). **None of
these read the key or compute an HMAC** — `backend.py`'s docstring states the key reader
returns `None` for a non-root caller and is never invoked. The only privileged path in
`backend` is `commit()`, which the status reader never touches. Therefore the Waybar
module **runs as the user, needs no sudo, and never prompts** — exactly the constraint.
The one prerequisite: the sanctioned config + `guard.json` must be **user-readable** for
a user-level read. (v2.0 set `.guardkey` + sanctioned config root:root 0600 — verify the
config/state files the reader needs are readable by the user; if the sanctioned config is
0600 root-only, the reader can't see it and the bar shows `unavailable`. This is a
**phase-A verification item**, flagged in PITFALLS.)

---

## 4. Click actions

The omarchy bar already demonstrates every pattern this milestone needs (verified in
`~/.config/waybar/config.jsonc` and `~/.local/share/omarchy/bin/`):

```jsonc
"custom/nightguard": {
  "exec": "ngtui status --json",
  "return-type": "json",
  "interval": 60,
  "signal": 8,                                  // pick a free SIGRTMIN+N
  "on-click":       "omarchy-launch-or-focus-tui ngtui",
  "on-click-right": "ngtui menu",               // or a wofi menu — see below
  "tooltip": true
}
```

- **Left-click → open/focus the TUI.** Use `omarchy-launch-or-focus-tui ngtui`
  (verified helper): it focuses an existing `org.omarchy.ngtui` window if one is open,
  else launches `omarchy-launch-tui ngtui` →
  `xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui`. This single helper gives the
  stable window class AND the focus-don't-duplicate behavior for free.
- **Right-click → status/actions menu.** Two options:
  - **`wofi`/`walker` menu (recommend for v1):** a tiny instance script lists actions
    (Open editor · Use +8 grace · Show ledger) and dispatches. Lower coupling; the menu
    items just shell `ngtui`/launch helpers. omarchy already ships `omarchy-launch-walker`.
  - **`ngtui menu` subcommand:** a third argv route that prints/handles actions. More
    self-contained but pulls menu UX into the package. Defer unless you want the menu
    shippable. Recommendation: **wofi menu lives in the instance; keep the package to
    `ngtui` + `ngtui status`.**

**Floating-terminal requirement** is satisfied by the Hyprland windowrule keying on the
`org.omarchy.ngtui` app-id (next section), NOT by the launch command — so left-click,
the `.desktop`, and autostart all produce the same floating window with one rule.

---

## 5. Repo-vs-instance placement (the two-layer split)

| Artifact | Lives in | Shipped/Installed? | Why |
|----------|----------|--------------------|-----|
| `ngtui` TUI entry | **repo** (`pyproject.toml`) | installed by `uv tool install` | the product |
| `ngtui status --json` reader | **repo** (`pyproject.toml`, new `status_cli` module) | installed | generic, key-less, reusable |
| Brand icon (PNG sizes + scalable SVG) | **repo** (`packaging/icons/` or `ngtui/assets/`) | installed into `hicolor` by PKGBUILD/`make install` | own-brand, part of the product identity (PROJECT: "no borrowed logos") |
| `nightguard.desktop` (generic, path-free `Exec`) | **repo** (`packaging/`) | installed to `/usr/share/applications` (AUR) or `~/.local/share/applications` (README) | generic launcher; `Exec=omarchy-launch-tui ngtui` carries no author paths |
| Hyprland windowrule snippet | **repo provides the snippet** (`packaging/hypr/nightguard.conf` as a documented include) | **instance applies it** (author's `~/.config/hypr/`) | the *rule text* is generic and shippable as a doc/snippet; *installing it into a user's live Hyprland config* is instance wiring |
| Waybar module snippet | **repo provides the snippet** (`packaging/waybar/nightguard.jsonc`) | **instance merges it** into `~/.config/waybar/config.jsonc` | same: generic snippet, instance applies |
| `~/.config/environment.d/nightguard.conf` (`NIGHTGUARD_STACK_DIR`/`NIGHTGUARD_DIR`) | **instance / dotfiles** | not shipped | author-specific paths; the ONE place that injects them session-wide |
| Autostart (`exec-once` in Hyprland autostart.conf, or a user systemd unit) | **instance / dotfiles** | not shipped | personal "pin on login" preference |
| `PKGBUILD` | **repo** (`packaging/aur/`) | the AUR artifact | the publish surface |
| LifeOS trust stack (`ngcommon`/`guard`/`nightguard_ctl`/sudoers/watchdog) | **LifeOS (separate repo)** | NOT this milestone | declared as a *dependency*, never vendored |

**Guiding rule:** *snippet text is generic → repo; applying a snippet into a live user
config, and any literal author path → instance/dotfiles.* The `.desktop` and icon are
the only desktop artifacts that get *installed* by the package; the windowrule and Waybar
entry are *documented snippets the user (or an install script) merges*, because Hyprland
and Waybar configs are user-owned single files, not drop-in directories you can safely
overwrite.

---

## 6. Hyprland windowrule — the float contract

The existing `TodQuickAdd` rule is the exact template (verified in `hyprland.conf`):

```conf
# packaging/hypr/nightguard.conf  (generic snippet; user includes or copies)
windowrule = float on,   match:class ^(org\.omarchy\.ngtui)$
windowrule = center on,  match:class ^(org\.omarchy\.ngtui)$
windowrule = size 900 640, match:class ^(org\.omarchy\.ngtui)$
```

- The `app-id`/class `org.omarchy.ngtui` comes for free from
  `omarchy-launch-tui ngtui` (`--app-id=org.omarchy.$(basename …)`). This is why the
  `.desktop` `Exec` should be `omarchy-launch-tui ngtui` (or `omarchy-launch-or-focus-tui`)
  rather than a raw `alacritty -e ngtui` — it guarantees the class the rule matches.
- One rule set covers every entry point (launcher, left-click, autostart) since they all
  produce the same app-id. **HIGH confidence** — this is the established omarchy idiom.

---

## 7. AUR package — what it installs and the dependency story

**Installs (into system paths):**
- the `ngtui` package (as a Python app — see packaging shape below),
- `/usr/share/applications/nightguard.desktop`,
- `/usr/share/icons/hicolor/{48x48,128x128,256x256,scalable}/apps/nightguard.{png,svg}`,
- docs: the Waybar + Hyprland snippets to `/usr/share/doc/ngtui/` (NOT auto-merged into
  user configs — Arch packaging rule: never write into `~`/user config from a package).

**Packaging shape — two routes:**

| Route | How | Trade-off |
|-------|-----|-----------|
| **`python-ngtui` (recommend for AUR)** | Standard PyPA build → `python -m build` → install the wheel into `/usr/lib/python3.x/site-packages` with `depends=(python python-textual)`. `console_scripts` land in `/usr/bin/ngtui`. | Idiomatic Arch Python packaging; system Python resolves `textual`. No uv at runtime. |
| **uv-tool style** | PKGBUILD wraps `uv tool install` into `$pkgdir`. | Non-idiomatic for AUR; uv as a makedep. Use only if you must pin the isolated-venv model. |

> For the **author**, `uv tool install` from the repo is the real install path (README
> documents it). The AUR `PKGBUILD` is the *publish* surface for others and should use the
> idiomatic `python-ngtui` wheel route.

**Declaring the trust-stack dependency (the hard part):** the LifeOS trust stack is NOT
on the AUR and is the author's private repo — so the package **cannot** list it as a
`depends=()`. Handle it as a **documented runtime prerequisite**, not a package dep:
- `optdepends=('nightguard-trust-stack: signing/guard backend (set NIGHTGUARD_STACK_DIR)')`
  as a signpost,
- a `post_install()` message in the `.install` file telling the user to point
  `NIGHTGUARD_STACK_DIR`/`NIGHTGUARD_DIR` at their stack (and that the app fails closed
  without it — which `_resolve_stack_dir()` already enforces),
- README documents the contract: ngtui is the *editor*; it requires a compatible
  `nightguard_ctl.py`/`ngcommon.py`/`guard.py` + the root watchdog + the sudoers entry.

This is honest: the product is genuinely a thin client over a backend it doesn't bundle.
The dependency is a *protocol/path contract* (`backend.py`'s expected module API + the
sudoers `Cmnd_Alias` shape), surfaced via env + docs, not an installable package.

---

## 8. Suggested build order (dependency-ordered)

```
Phase A — Global install + stack resolution from a bare env   [foundation; unblocks all]
  • Add `ngtui status --json` argv route (status_cli module, backend-only import).
  • `uv tool install` the package; verify the bare `ngtui` shim launches the TUI
    AND resolves the LifeOS stack with NO dev-shell env (the launcher-env test).
  • Decide the env-injection point for non-author installs (environment.d) — document.
  • Verify config/state file perms allow a key-less user read (else bar = unavailable).
  Gate: `ngtui` and `ngtui status --json` both run from a login shell with no
        NIGHTGUARD_* prefix; status emits valid Waybar JSON and never prompts/needs root.

Phase B — Launcher + window behavior                          [needs A: a global ngtui]
  • Brand icon into hicolor (own-brand, shipped).
  • `nightguard.desktop` (Exec=omarchy-launch-tui ngtui) → appears in wofi/walker.
  • Hyprland windowrule snippet (float/center/size on org.omarchy.ngtui).
  Gate: launching from wofi opens a floating, correctly-sized ngtui terminal.

Phase C — Waybar module                                       [needs A: status JSON]
  • custom/nightguard snippet: exec ngtui status --json, interval+signal, on-click
    (omarchy-launch-or-focus-tui ngtui), on-click-right (wofi menu or ngtui menu).
  • Fail-closed to {"unavailable"} on error.
  • Wire commit→Waybar push refresh (TUI sends SIGRTMIN+N after a successful commit).
  Gate: bar shows live lock/token state; left-click opens/focuses; right-click menus;
        state updates within the interval AND immediately after a commit.

Phase D — Autostart / login pin                               [optional; needs B]
  • Instance exec-once / user systemd unit (dotfiles, not shipped).

Phase E — Publish packaging                                   [last: needs B+C artifacts]
  • PKGBUILD (python-ngtui wheel route) installing package + .desktop + icons + doc
    snippets; optdepends + .install message for the trust-stack contract.
  • README install path (uv tool install for the author; PKGBUILD for others;
    environment.d for the stack path).
  Gate: clean-machine dry-run install produces a launchable (or clearly-fails-closed)
        app with documented dependency wiring.
```

**Why this order:** A is the keystone — the global command + the bare-env stack
resolution + the status subcommand are the substrate B and C both stand on. B and C are
independent of each other (both depend only on A) and could run in parallel, but B is the
smaller/safer "make it appear in the launcher" win and de-risks the window-class contract
that C's `on-click` reuses. D is a cosmetic pin. E is deliberately last because the
PKGBUILD packages the artifacts A–C produce and must encode the dependency story those
phases finalize.

---

## Component Boundaries — explicit new vs modified

| Element | Status | File(s) |
|---------|--------|---------|
| `ngtui status --json` subcommand router | **NEW** | `ngtui/ngtui/__main__.py` (dispatch), `ngtui/ngtui/status_cli.py` (NEW) |
| Reuse of verdict/token helpers | **reuse** | `ngtui/ngtui/widgets/status.py` (`verdict_display`, `token_meter`), `ngtui/ngtui/backend.py` |
| `pyproject.toml` scripts | **MODIFIED** (only if separate `ngtui-status` entry); unchanged for the subcommand route | `ngtui/pyproject.toml` |
| Brand icon | **NEW (shipped)** | `packaging/icons/nightguard.{svg,png…}` |
| `.desktop` | **NEW (shipped)** | `packaging/nightguard.desktop` |
| Hyprland windowrule snippet | **NEW (repo snippet, instance-applied)** | `packaging/hypr/nightguard.conf` |
| Waybar module snippet | **NEW (repo snippet, instance-applied)** | `packaging/waybar/nightguard.jsonc` |
| environment.d stack-path file | **NEW (instance/dotfiles)** | `~/.config/environment.d/nightguard.conf` |
| Autostart | **NEW (instance/dotfiles)** | `~/.config/hypr/autostart.conf` exec-once |
| Commit→Waybar signal refresh | **MODIFIED** | `ngtui/ngtui/backend.py` `commit()` (emit `SIGRTMIN+N` to waybar on success) |
| PKGBUILD | **NEW (shipped)** | `packaging/aur/PKGBUILD` (+ `.install`) |

---

## Sources

- Live box inspection (2026-06-24) — `~/.config/waybar/config.jsonc` (custom-module +
  on-click/on-click-right + json + signal/interval patterns), `~/.config/hypr/*.conf`
  (`windowrule = float … match:class` template via `TodQuickAdd`),
  `~/.local/share/omarchy/bin/omarchy-launch-{tui,or-focus-tui,floating-terminal-…}`
  (app-id `org.omarchy.<basename>`, focus-or-launch, uwsm wrapping),
  `~/.local/share/omarchy/default/waybar/weather.sh` (fail-closed json precedent),
  `ngtui/ngtui/backend.py` + `widgets/status.py` (the key-less read seam + verdict/token
  helpers), `uv 0.11.23`. **HIGH**
- Waybar wiki — Custom module `return-type: json` fields (`text/alt/tooltip/class/percentage`),
  `interval`/`signal` (SIGRTMIN+N)/`on-click`/`on-click-right`. **HIGH**
  https://github.com/Alexays/Waybar/wiki/Module:-Custom
- uv docs — `uv tool install` isolated venv at `~/.local/share/uv/tools`, PATH shims +
  `uv tool update-shell`, editable/local-path install (`-e .`). **HIGH**
  https://docs.astral.sh/uv/concepts/tools/ ·
  https://docs.astral.sh/uv/reference/installer/
- Arch packaging convention (no writes into `$HOME`; `optdepends`/`.install` for
  non-AUR runtime prerequisites). **MEDIUM** (standard practice; not re-verified against a
  specific guideline URL this session)
