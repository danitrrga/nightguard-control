# Research Summary — v2.1 Desktop App

**Synthesized:** 2026-06-24 · **Confidence:** HIGH (verified against the live box)
**Sources:** STACK.md · FEATURES.md · ARCHITECTURE.md · PITFALLS.md

## Executive Summary

v2.1 is a **desktop-packaging** milestone, not a feature milestone. The `ngtui` Textual TUI is already the complete sanctioned editor; this milestone wraps it as a first-class omarchy app: a global `ngtui` command, a floating-terminal `.desktop` launcher, a Waybar `custom/nightguard` module (live lock glyph + tokens, left-click=open, right-click=read-only status/actions menu), a custom brand icon, optional autostart, and an AUR-ready PKGBUILD.

## Two Load-Bearing Risks (every phase must honor)

1. **Inline-sudo needs a real PTY.** `backend.commit()` shells `sudo … nightguard_ctl.py commit` with stderr left on the TTY and relies on `App.suspend()`. Any launch that doesn't wrap `ngtui` in a real terminal (`xdg-terminal-exec … -e ngtui`, `Terminal=false`) → `sudo: no tty present` → the core editing flow silently breaks. Add a `sys.stdin.isatty()` startup check.
2. **The bar is a window, never a lever.** No Waybar/launcher surface may loosen the curfew (no "loosen/+8/unlock/use-grace" quick-action). Every mutation must route through the TUI's `sudo`-gated `backend.commit()`. The Waybar status reader stays **key-less and unprivileged** (reads only). Treat any escape hatch as a security regression.

## Keystone Build Order (maps to phases)

- **A — Global install + status subcommand (keystone):** `uv tool install --python 3.14 .` → `~/.local/bin/ngtui`. New key-less `ngtui status --json` argv route (a `status_cli` module importing only `backend`, no Textual). Verify `_DEFAULT_STACK_DIR` resolves from a clean login shell (no dev-shell env). An `ngtui doctor` check is recommended.
- **B — Launcher + floating window:** brand icon → hicolor (`scalable/apps/nightguard.svg`); `nightguard.desktop` with `Exec=xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui`, `Terminal=false`; Hyprland 0.55.4 windowrule (`float on, match:class ^(org\.omarchy\.ngtui)$` — new grammar, not `windowrulev2`; match `initialClass` not title).
- **C — Waybar module:** `custom/nightguard` → `exec: ngtui status --json`, `return-type: json`, `interval: 60`, `signal: N`, `on-click: omarchy-launch-or-focus-tui ngtui`, `on-click-right:` a wofi **read-only** menu. Wire `backend.commit()` to `pkill -SIGRTMIN+N waybar` for instant post-commit refresh. Fail closed to `{"text":"○ —","class":"unavailable"}`.
- **D — Autostart / login pin (optional, instance-only, off by default):** autostart the *Waybar module*, not the TUI window; TUI autostart opt-in. If autostarting the window, use the full terminal wrapper.
- **E — AUR packaging (last):** `python -m build --wheel --no-isolation` + `python -m installer --destdir`. Trust stack is `optdepends` + an `.install` message + README contract — **never vendored** (PORT-02), never a pip dep. No root-owned/0600 files in the manifest; sudoers stays a manual reviewed step.

## Verified Environment Specifics

- Toolchain: uv 0.11.23, Python 3.14.6, Alacritty 0.17.0 (resolved via `xdg-terminal-exec` — do NOT hardcode a terminal), Hyprland 0.55.4 (new windowrule grammar), Waybar custom module with `signal` refresh.
- omarchy ships the primitives: `omarchy-launch-or-focus-tui ngtui` (left-click open/focus + stable window class), the `TodQuickAdd`/`custom/omarchy` rules as float + on-click templates, `weather.sh` as the fail-closed JSON precedent.
- Pin `--python 3.14` so the shim interpreter matches the `/usr/bin/python3` sudo-commit interpreter.

## Repo-vs-Instance Split (two-layer model preserved)

- **Packaged/shipped (generic):** icon, `.desktop`, PKGBUILD, the `ngtui status` subcommand.
- **Repo-provided snippets the instance merges (user-owned configs, never package-overwritten):** Hyprland windowrule, Waybar module JSON.
- **Instance/dotfiles:** `~/.config/environment.d/nightguard.conf` (the single sanctioned env-injection point for non-author installs), autostart unit.

## Anti-Features (explicitly out)

No loosen/grace/unlock button on the bar; no privileged Waybar exec; no backgrounded ngtui daemon/tray; no HMAC echo in the bar; no force-open-TUI-on-login by default. Grace-as-action is blocked on grace-commit landing in the TUI (currently display-only, D-11) → deferred to a later milestone, and must arrive `sudo`-gated.

## Research Flags (resolve at phase time)

- **Phase A:** confirm `guard.json` + sanctioned config are **user-readable** from the isolated-venv process (not 0600 root-only) — gates the whole Waybar/status path. Verify `_DEFAULT_STACK_DIR` resolves from a clean login shell.
- **Phase C:** find a free `SIGRTMIN+N` slot in the live Waybar config before hardcoding the post-commit signal.
- **Phase E:** confirm `python-textual 8.2.7` availability in Arch repos/AUR at publish time.
