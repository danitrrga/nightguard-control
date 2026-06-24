# Stack Research

**Domain:** Desktop packaging / launcher integration for a Python Textual TUI on omarchy (Arch + Hyprland + Waybar) — milestone v2.1 · Desktop App
**Researched:** 2026-06-24
**Confidence:** HIGH (most facts verified against the live box: omarchy `bin/`, the running Waybar/Hyprland config, `uv`, and installed terminals)

> Supersedes the prior v1.0 STACK research (Windows/Tauri/Rust), which is retired with the v2.0 Linux port. This file covers ONLY the new v2.1 packaging/launch capability.

## TL;DR — the load-bearing answers

1. **Global install →** `uv tool install` from the `ngtui/` project dir. It already ships a `[project.scripts] ngtui = "ngtui.__main__:main"` entry point (hatchling), so `uv tool install` builds the wheel into an isolated venv and drops a real `ngtui` shim into `~/.local/bin`. The `sys.path.insert(STACK_DIR)` import of the external LifeOS stack happens **at runtime inside that venv** and is unaffected by isolation — it resolves via `NIGHTGUARD_STACK_DIR` / the hardcoded default, exactly as it does today. Pin the interpreter with `--python 3.14` (system python is 3.14.6; the sudo commit call hardcodes `/usr/bin/python3` which is 3.14).
2. **Floating-terminal launcher →** omarchy is **not** a hardcoded-terminal setup. It uses freedesktop's **`xdg-terminal-exec`** with the default resolved from `~/.config/xdg-terminals.list` (currently `Alacritty.desktop`). The idiomatic invocation — copied from omarchy's own `omarchy-launch-floating-terminal-with-presentation` — is `xdg-terminal-exec --app-id=<id> --title=<t> -e ngtui`. Set `--app-id` to a class that already floats (`org.omarchy.terminal`) or a dedicated `TUI.float`, both of which are **already matched** by omarchy's default floating window rule. **No new Hyprland windowrule is required** if you reuse one of those app-ids.
3. **Waybar →** a `custom/nightguard` module. `exec` a tiny status script (`return-type: "json"` for icon+tooltip+class), `interval` poll (or `signal`-driven), `on-click` = the launcher command, `on-click-right` = a status/actions menu. This mirrors the existing `custom/update` and `custom/omarchy` modules verbatim.
4. **Icon →** drop a `nightguard.svg` into `~/.local/share/icons/hicolor/scalable/apps/` (per-user) or `/usr/share/icons/hicolor/scalable/apps/` (system / PKGBUILD), then `gtk-update-icon-cache`. Reference it by **name** (`Icon=nightguard`) in the `.desktop` file.
5. **Autostart →** prefer Hyprland `exec-once` for a Wayland-session-scoped surface; use a `systemd --user` unit only if you want restart-on-crash / ordering. For "pin the status surface", Waybar is already autostarted by omarchy — the module **is** the autostart.
6. **AUR →** a standard **wheel-only Python PKGBUILD** (`python-build` + `python-installer`, `--no-isolation`), plus `install -Dm` lines for the `.desktop` + icon, and a documented `optdepends`/README note for the external LifeOS trust stack (it is **not** a pip dependency — it is an out-of-tree runtime requirement).

## Recommended Stack

### Core Technologies (the NEW capability — packaging/launch)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **uv** (`uv tool install`) | `0.11.23` (installed) | Global install of the `ngtui` console script into an isolated, content-addressed venv | Already the project's toolchain (dev venv is `uv`). `uv tool` is pipx's analogue but reuses uv's managed-Python + cache; one tool, no extra dep. Builds the hatchling wheel and exposes `~/.local/bin/ngtui`. |
| **xdg-terminal-exec** | system (`/usr/bin/xdg-terminal-exec`) | Resolve + launch the user's default terminal running `ngtui` | omarchy's canonical terminal-launch path (used by `SUPER+RETURN`, `omarchy-launch-floating-terminal-*`). Honors `~/.config/xdg-terminals.list` so it follows whatever terminal the user picks (currently **Alacritty 0.17.0**), instead of hardcoding ghostty/alacritty. Supports `--app-id` (Wayland class) + `--title` + `-e`. |
| **Hyprland** | `0.55.4` (installed) | Window rules for the floating TUI window | Uses the **new** `windowrule = float on, match:class ^(...)$` syntax (NOT legacy `windowrulev2`). omarchy already ships a `floating-window` tag rule matching `org.omarchy.terminal` and a `TUI.float` class — reuse one as the launcher's `--app-id`. |
| **Waybar** | installed (`/usr/bin/waybar`) | Status module + click-to-launch in the bar | The `custom/<name>` module model (`exec`/`return-type`/`interval`/`signal`/`on-click`/`on-click-right`) is exactly what's needed; the live config already uses it for `custom/update`, `custom/weather`, indicators. |
| **hicolor-icon-theme** | system | Brand icon delivery | The freedesktop standard theme every launcher (wofi/walker) + Waybar icon lookup falls back to. `scalable/apps/<name>.svg` referenced by name. |

### Supporting Libraries / Tools

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| **hatchling** | already the build backend | Build the wheel `uv tool install` / PKGBUILD consume | Already in `pyproject.toml`; nothing to add. `uv` and `python -m build` both drive it. |
| **python-build** | system pkg `python-build` | PKGBUILD `build()`: `python -m build --wheel --no-isolation` | AUR packaging only. |
| **python-installer** | system pkg `python-installer` | PKGBUILD `package()`: `python -m installer --destdir="$pkgdir" dist/*.whl` | AUR packaging only. |
| **desktop-file-utils** | system (`desktop-file-validate`, `update-desktop-database`) — installed | Validate the `.desktop` file; refresh the launcher DB | Build/CI check + post-install hook. |
| **gtk-update-icon-cache** | system (installed) | Rebuild hicolor cache after dropping the SVG | After icon install (per-user manual run, or PKGBUILD `.install` hook). |
| **systemd --user** | system | Optional autostart unit with restart semantics | Only if you need crash-restart / dependency ordering beyond Hyprland `exec-once`. |

### Development / Inspection facts (verified on this box)

| Probe | Result on this machine | Notes |
|-------|------------------------|-------|
| `omarchy-default-terminal` | resolves `Alacritty.desktop` → `alacritty` | The default terminal is **Alacritty 0.17.0**, not ghostty. ghostty is NOT installed. Launcher must go through `xdg-terminal-exec`, not a hardcoded binary. |
| `uv tool dir` | `~/.local/share/uv/tools` | Where the isolated tool venv lives. |
| `python3 --version` | `Python 3.14.6` | `/usr/bin/python3` → 3.14; matches the `sudo /usr/bin/python3 …` commit call in `backend.py`. |
| `hyprctl version` | `0.55.4` | Uses new `windowrule … match:class` grammar. |

## Installation

```bash
# --- 1. Global install (run from the ngtui/ project dir) ---------------------
cd ngtui
uv tool install --python 3.14 .
#   → builds the hatchling wheel into ~/.local/share/uv/tools/ngtui
#   → exposes ~/.local/bin/ngtui  (ensure ~/.local/bin is on PATH; `uv tool update-shell`)
# Re-install after code changes:  uv tool install --reinstall --python 3.14 .
# Dev-loop alternative (live edits):  uv tool install -e --python 3.14 .

# --- 2. Brand icon into hicolor (per-user) -----------------------------------
mkdir -p ~/.local/share/icons/hicolor/scalable/apps
cp nightguard.svg ~/.local/share/icons/hicolor/scalable/apps/nightguard.svg
gtk-update-icon-cache ~/.local/share/icons/hicolor 2>/dev/null || true

# --- 3. .desktop launcher (per-user) -----------------------------------------
# ~/.local/share/applications/nightguard.desktop  (body below)
desktop-file-validate ~/.local/share/applications/nightguard.desktop
update-desktop-database ~/.local/share/applications

# --- 4. Waybar + Hyprland: edit ~/.config/waybar/config.jsonc and
#        ~/.config/hypr/... (snippets in the integration section below)
```

### `.desktop` body (mirrors omarchy's `xdg-terminal-exec` launch path)

```ini
[Desktop Entry]
Type=Application
Name=Nightguard
Comment=Sanctioned editor for the nightguard curfew
# Reuse an app-id omarchy already floats (org.omarchy.terminal) — or a dedicated one:
Exec=xdg-terminal-exec --app-id=org.nightguard.tui --title=Nightguard -e ngtui
Icon=nightguard
Terminal=false
Categories=Utility;System;
StartupNotify=true
```

> `Terminal=false` because `xdg-terminal-exec` opens the terminal itself; `Terminal=true` would double-wrap it in the launcher's own terminal.

### Waybar `custom/nightguard` module (drop into `config.jsonc`)

```jsonc
"custom/nightguard": {
  "exec": "$HOME/.local/share/omarchy-nightguard/waybar-status.sh", // emits {"text","tooltip","class"}
  "return-type": "json",
  "interval": 30,
  "on-click": "xdg-terminal-exec --app-id=org.nightguard.tui --title=Nightguard -e ngtui",
  "on-click-right": "$HOME/.local/share/omarchy-nightguard/waybar-menu.sh",
  "tooltip": true
}
// then add "custom/nightguard" to modules-left / modules-right array
```

### Hyprland windowrule (Hyprland 0.55 syntax — only if you DON'T reuse an omarchy-floated app-id)

```ini
# new-style rule grammar (this box runs 0.55.4):
windowrule = float on,    match:class ^(org\.nightguard\.tui)$
windowrule = center on,   match:class ^(org\.nightguard\.tui)$
windowrule = size 900 600, match:class ^(org\.nightguard\.tui)$
```

> Shortcut: set the launcher `--app-id=org.omarchy.terminal` (or `TUI.float`) instead — both are **already** in omarchy's default `tag +floating-window` rule (`~/.local/share/omarchy/default/hypr/apps/system.conf`), so the window floats with **zero** added rules. Trade-off: a dedicated `org.nightguard.tui` class lets you give the window its own size/center rule and target it precisely in `hyprctl clients`; the shared id is zero-config but visually identical to other floating terminals.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `uv tool install` | **pipx** | If the target machine has pipx but not uv. Functionally equivalent for a console-script app (isolated venv + PATH shim, supports local-path/git installs). **Not** recommended here: pipx isn't installed, and uv is already the project's toolchain — adding pipx is a redundant dep. Both isolate the venv identically, so the `sys.path.insert` external-stack import behaves the same under either. |
| `uv tool install .` (build wheel) | `uv tool install -e .` (editable) | Editable for the author's dev loop so code edits land without reinstall. Use the non-editable wheel build for the "real install" milestone deliverable and the AUR package. |
| `xdg-terminal-exec -e ngtui` | `alacritty --class org.nightguard.tui -e ngtui` | Only if you want to **force** Alacritty regardless of the user's `xdg-terminals.list` preference. Hardcoding breaks the omarchy contract (user can `omarchy default terminal ghostty`); prefer `xdg-terminal-exec`. omarchy's helper uses `--app-id` (works across alacritty/ghostty/kitty/foot); a raw `--class` flag is terminal-specific. |
| Reuse `org.omarchy.terminal` app-id (zero rules) | Dedicated `org.nightguard.tui` + explicit windowrule | Dedicated class when you want a specific window size/position or to distinguish it in `hyprctl clients`. |
| Hyprland `exec-once` autostart | `systemd --user` unit | systemd when you need `Restart=on-failure`, `After=` ordering, or `journalctl --user` logs. For a Waybar status surface neither is needed — Waybar is already autostarted and the module is the surface. |
| `Icon=nightguard` (theme name) | `Icon=/abs/path/nightguard.svg` (absolute) | Absolute path if you deliberately skip the hicolor theme. Theme-name is preferred: respects theming, found by wofi/walker/Waybar lookup, and is the AUR-clean install location. |
| Waybar `return-type: "json"` | `return-type: ""` (plain text) | Plain text if the module only ever shows a static glyph with no dynamic class/tooltip. Use JSON to drive live lock/token state + a CSS `class` (`.locked`/`.unlocked`) — matches existing indicator modules. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Hardcoding `ghostty -e ngtui` | **ghostty is not installed**; the default terminal here is Alacritty via `xdg-terminals.list`. Hardcoding any terminal breaks omarchy's swappable-terminal contract. | `xdg-terminal-exec --app-id=… -e ngtui` |
| Legacy `windowrulev2 = float, class:…` | Hyprland **0.55.4** uses the new unified `windowrule = float on, match:class ^…$` grammar; old `windowrulev2` / bare `class:` matchers are deprecated/removed. | `windowrule = float on, match:class ^(…)$` |
| Listing the trust stack as a PyPI dependency | The LifeOS `ngcommon`/`guard`/`nightguard_ctl` stack is an **out-of-tree, env-resolved** import (`sys.path.insert(STACK_DIR)`), not a pip package. Listing it would make `uv tool install` fail resolution. | Keep `dependencies = ["textual==8.2.7"]` only; document the stack as a runtime prerequisite / `optdepends` + README env-var setup. |
| `pip install --user .` / bare `pip` global install | Pollutes user site-packages, no isolation, can clash with system python and the sudo `/usr/bin/python3` path; not reproducible. | `uv tool install` (isolated venv) or the AUR wheel install. |
| A `systemd --user` unit that `exec`s the TUI at login | A TUI needs a TTY/terminal window; a headless `--user` service has no terminal and would fail or run invisibly. Autostart applies to the **Waybar module / status surface**, not the interactive TUI. | Hyprland `exec-once` for the bar surface; launch the TUI on demand (click / wofi / keybind). |
| `python setup.py install` in the PKGBUILD | Deprecated; ngtui has no `setup.py` (pure `pyproject.toml` + hatchling). | `python -m build --wheel --no-isolation` + `python -m installer --destdir=…`. |
| Vendoring/borrowed launcher icons | Project constraint: own-brand only, no borrowed logos. | A custom `nightguard.svg` in hicolor `scalable/apps`. |

## Stack Patterns by Variant

**If installing for the author only (personal LifeOS instance):**
- `uv tool install --python 3.14 .` (or `-e .`), per-user `.desktop` + icon in `~/.local/share/...`, Waybar/Hyprland edits in `~/.config/...`.
- The external stack resolves via the hardcoded `_DEFAULT_STACK_DIR` / `NIGHTGUARD_DIR` defaults already in `backend.py` — **no env vars needed** on the author's box. For zero floating-rule config, reuse `--app-id=org.omarchy.terminal`.

**If publishing to the AUR (non-author installs):**
- Wheel-only PKGBUILD; install `.desktop` + `nightguard.svg` system-wide; ship a `.install` scriptlet running `update-desktop-database` + `gtk-update-icon-cache`.
- The trust stack is **not** packaged (it's the author's private LifeOS). Document it as a required external dependency the installer must point at via `NIGHTGUARD_STACK_DIR` / `NIGHTGUARD_DIR`; without it `ngtui` fails closed with the clear `RuntimeError` already coded in `_resolve_stack_dir()`. Mark as `optdepends` + a prominent README "you must supply a nightguard trust stack" note.
- Dependency: `depends=(python python-textual)` if `python-textual` is in repos/AUR at the pinned `8.2.7`; otherwise let the wheel pull textual. Verify `python-textual` availability/version at integration time.

**AUR PKGBUILD skeleton (wheel-only, hatchling):**
```bash
makedepends=(python-build python-installer python-wheel python-hatchling)
depends=(python python-textual)   # confirm python-textual==8.2.7 availability; else bundle
optdepends=('nightguard trust stack (ngcommon/guard/nightguard_ctl): external, set NIGHTGUARD_STACK_DIR')

build() {
  cd "$srcdir/$pkgname-$pkgver"
  python -m build --wheel --no-isolation
}
package() {
  cd "$srcdir/$pkgname-$pkgver"
  python -m installer --destdir="$pkgdir" dist/*.whl
  install -Dm644 packaging/nightguard.desktop "$pkgdir/usr/share/applications/nightguard.desktop"
  install -Dm644 packaging/nightguard.svg     "$pkgdir/usr/share/icons/hicolor/scalable/apps/nightguard.svg"
}
```

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `uv 0.11.23` | hatchling backend, Python 3.14.6 | `uv tool install` drives the PEP 517 build via hatchling; pin `--python 3.14` to match `/usr/bin/python3` (the sudo commit interpreter). |
| `ngtui` (entry point) | `textual==8.2.7` | Single declared dep; unchanged by packaging. |
| Hyprland `0.55.4` | new `windowrule … match:class` grammar | Do NOT use `windowrulev2`. `match:class ^(…)$` regex anchoring required. |
| Waybar (live config) | `custom/<name>` with `exec`/`return-type`/`interval`/`signal`/`on-click`/`on-click-right` | All used by existing modules (`custom/update`, `custom/weather`, indicators) — proven on this box. |
| `xdg-terminal-exec` | `--app-id` / `--title` / `-e` | Confirmed flags via `--help`; `--app-id` sets Wayland app-id (X11 class). Default terminal from `~/.config/xdg-terminals.list` (= `Alacritty.desktop`). |
| `/usr/bin/python3` | 3.14.6 | Matches `backend.py` sudo argv; keep the installed shim aligned with the stack — don't let `uv tool` silently pick 3.15-beta. |

## Sources

- **Live machine inspection** (HIGH — ground truth): `~/.local/share/omarchy/bin/omarchy-default-terminal`, `omarchy-launch-floating-terminal-with-presentation` (the `xdg-terminal-exec --app-id=org.omarchy.terminal -e bash -c …` pattern); `~/.config/waybar/config.jsonc` (custom module shapes); `~/.local/share/omarchy/default/hypr/apps/system.conf` (`tag +floating-window` matching `org.omarchy.terminal`/`TUI.float`); `~/.config/hypr/` windowrule grammar; `hyprctl version` → 0.55.4; `uv --version` → 0.11.23; `alacritty --version` → 0.17.0; `python3 --version` → 3.14.6; `xdg-terminal-exec --help` (flags).
- **uv tool vs pipx** — uv docs / pipx comparison: both isolate console-script venvs + PATH shims; uv reuses managed Python + cache. https://docs.astral.sh/uv/getting-started/installation/ , https://pipx.pypa.io/stable/explanation/comparisons/ — **MEDIUM** (corroborated by installed `uv tool install --help`).
- **AUR Python wheel-only PKGBUILD** — ArchWiki Python package guidelines: `python-build` + `python-installer`, `python -m build --wheel --no-isolation`, `python -m installer --destdir`. https://wiki.archlinux.org/title/Python_package_guidelines — **MEDIUM** (wiki page behind Anubis on fetch; pattern is well-established convention and confirmed by current AUR packages, e.g. python-mistralai/python-garth).
- **ngtui internals** (HIGH): `ngtui/pyproject.toml` (entry point + hatchling), `ngtui/ngtui/__main__.py`, `ngtui/ngtui/backend.py` (`_resolve_stack_dir` env-override + fail-closed; sudo `/usr/bin/python3` commit argv).

---
*Stack research for: omarchy desktop packaging of a Python Textual TUI thin-client (v2.1)*
*Researched: 2026-06-24*
