---
phase: 12-launcher-waybar-presence
plan: 04
subsystem: omarchy-desktop-integration
tags: [waybar, hyprland, freedesktop, walker, launcher, packaging]
requires:
  - "ngtui status --json (Phase 11 key-less Waybar substrate)"
  - "omarchy-launch-or-focus-tui (system helper, reused)"
provides:
  - "packaging/omarchy/nightguard.desktop (DESK-03 launcher entry)"
  - "packaging/omarchy/hypr/nightguard.windowrule.conf (float/center/size on app_id)"
  - "packaging/omarchy/waybar/custom-nightguard.jsonc (BAR-01/02/03 module def)"
  - "packaging/omarchy/waybar/style-nightguard.css (D-09 fixed semantic colors)"
  - "packaging/omarchy/bin/ngtui-menu (BAR-03 read-only right-click menu)"
affects:
  - "Plan 05 installer merges these five canonical artifacts onto the live box"
tech-stack:
  added: []
  patterns:
    - "marker-guarded (>>> nightguard (managed) >>>) text snippets for idempotent injection"
    - "windowrule keyed on stable Wayland app_id (class), never title"
    - "walker --dmenu read-only surface (open-only actions, no lever)"
key-files:
  created:
    - packaging/omarchy/nightguard.desktop
    - packaging/omarchy/hypr/nightguard.windowrule.conf
    - packaging/omarchy/waybar/custom-nightguard.jsonc
    - packaging/omarchy/waybar/style-nightguard.css
    - packaging/omarchy/bin/ngtui-menu
  modified: []
decisions:
  - "D-04/D-05/D-06/D-09 discharged: read-only walker menu, tooltip stays the status tooltip, canonical in-repo artifacts, fixed semantic style classes"
  - "Shipped the explicit 3-line float rule (order-independent) rather than `tag +floating-window` (D-06 canonical form, Open Q2 resolution)"
metrics:
  duration: "~5 min"
  completed: "2026-07-04"
  tasks: 3
  files: 5
---

# Phase 12 Plan 04: Launcher + Waybar Presence Artifacts Summary

Authored the five canonical omarchy-integration artifacts (D-06) that Plan 05's
installer merges onto the live box: a `.desktop` launcher + Hyprland float rule
(DESK-03), a key-less `custom/nightguard` Waybar module + fixed-semantic style
snippet (BAR-01/BAR-02), and a `walker --dmenu` read-only right-click menu
(BAR-03). All live-config snippets carry `>>> nightguard (managed) >>>` guard
markers for idempotent injection; the float rule keys on the stable app_id
(`org.omarchy.ngtui`, never title); the module declares `"signal": 11` to match
Plan 02's `pkill -RTMIN+11` post-commit refresh; and the menu is provably
read-only/open-only ("a window, never a lever").

## What Was Built

### Task 1 — nightguard.desktop + Hyprland windowrule (DESK-03) — `c5e6e54`
- `nightguard.desktop`: `Exec=xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui`,
  `Terminal=false` (xdg-terminal-exec supplies the terminal), `Icon=org.omarchy.ngtui`,
  `Categories=Utility;`, `StartupNotify=false`. The `-e ngtui` opens a real
  Alacritty PTY so the inline-`sudo` commit still works.
- `nightguard.windowrule.conf`: explicit, order-independent 3-line block
  (`float on` / `center on` / `size 875 600`), each `match:class ^(org\.omarchy\.ngtui)$`
  — never `title` (SC-1 / T-12-07 spoofing mitigation). Marker-guarded.

### Task 2 — custom/nightguard module + style.css (BAR-01/BAR-02) — `3b7f18d`
- `custom-nightguard.jsonc`: `"return-type": "json"`, `"exec": "ngtui status --json"`
  (key-less — no sudo/NTP/key in the exec, T-12-09 mitigation), `"interval": 30`,
  `"signal": 11`, `"format": "{}"`, `"on-click": "omarchy-launch-or-focus-tui ngtui"`
  (BAR-02 reuse, no custom focus script), `"on-click-right": "ngtui-menu"` (BAR-03).
- `style-nightguard.css`: base `#custom-nightguard` rule + all six emitted classes
  keyed (`.locked`/`.clock_tamper`/`.offline_blocked` red, `.grace_active` amber,
  `.outside_curfew` green, `.unavailable` dim). D-09 fixed semantic mapping.
- Both marker-guarded.

### Task 3 — ngtui-menu read-only walker menu (BAR-03) — `de6cbbd`
- `#!/usr/bin/env bash`, `set -euo pipefail`. Runs `ngtui status --json` (falls
  back to the `unavailable` object on error), parses `tooltip`/`text` defensively
  with `python3 … .get(...)` (the fail branch has no `tooltip` key, T-12-08).
- Feeds `walker --dmenu -p "Nightguard"` inert header lines + two open-only actions
  ("Open editor" / "Open status"), both `exec omarchy-launch-or-focus-tui ngtui`;
  every other selection is a no-op. No loosen/commit/grace/token-spend action
  exists anywhere (T-12-06 / BAR-03 no-lever invariant).
- Committed with the executable bit tracked (100755).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reworded module comment to satisfy the key-less grep**
- **Found during:** Task 2 verification
- **Issue:** The acceptance grep `! grep -Eq 'sudo|--json.*key|guardkey'` matched
  descriptive words ("no sudo… no key") in the JSONC comment, not the exec itself.
- **Fix:** Reworded the comment to "the read-only ngtui status shim" — no behavior
  change; the exec is still `ngtui status --json`.
- **Files modified:** packaging/omarchy/waybar/custom-nightguard.jsonc
- **Commit:** 3b7f18d

**2. [Rule 1 - Bug] Forced the executable bit into git for ngtui-menu**
- **Found during:** Task 3 post-commit check
- **Issue:** Repo has `core.fileMode=false`; the initial commit recorded mode
  100644 despite the working-tree file being `+x`. The installer expects a
  runnable script.
- **Fix:** `git update-index --chmod=+x` then `--amend` the Task 3 commit → mode
  100755 tracked.
- **Files modified:** packaging/omarchy/bin/ngtui-menu (mode only)
- **Commit:** de6cbbd

## Verification

- All plan grep gates pass (app-id/Terminal/Icon/-e; class-not-title; float/center/size;
  signal 11 / exec / on-click / on-click-right / return-type; key-less; all six style
  classes; markers in every snippet).
- `bash -n packaging/omarchy/bin/ngtui-menu` clean; script executable (100755 tracked).
- No-loosen grep clean on non-comment lines; no `match:title`.
- No ngtui/ Python code touched → D-10 baseline (71 passing tests) unaffected by construction.

## Notes for Downstream (Plan 05 installer)

- The five artifacts are static, phase-authored text. The installer does the live
  work: `mkdir -p scalable/apps`, rasterize the icon, marker-guarded merge into
  `~/.config/waybar/config.jsonc` (module object + `modules-*` membership — never
  a JSON round-trip) and `~/.config/hypr/hyprland.conf`, `pkill -SIGUSR2 waybar`,
  and the `command -v ngtui` prerequisite (`ngtui` may be absent from PATH).
- `ngtui-menu` installs to a Waybar-PATH dir (`~/.local/bin` or
  `~/.local/share/omarchy/bin`).
