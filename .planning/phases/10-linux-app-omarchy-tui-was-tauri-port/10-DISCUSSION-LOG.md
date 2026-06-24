# Phase 10: Linux App — omarchy TUI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-24
**Phase:** 10-linux-app-omarchy-tui-was-tauri-port
**Areas discussed:** TUI stack & feel, Interaction model, Live theming via aether, Edit + sudo commit flow

---

## TUI stack & feel

| Option | Description | Selected |
|--------|-------------|----------|
| Textual | Modern async, CSS-like styling maps onto aether colors, rich widgets; heaviest dep | ✓ |
| Rich only | Lighter render + keypress loop, no widget framework | |
| curses / blessed | Most minimal, near-stdlib, most manual | |

**User's choice:** Textual
**Notes:** Accepted the heavier dep for best look/feel + easiest live theming.

---

## Interaction model

| Option | Description | Selected |
|--------|-------------|----------|
| Single-key commands | Keyboard-only, one keystroke per action; matches PORT-01 "command-driven, minimal" | ✓ |
| Hybrid: keys + palette | Single-key actions + ':' command palette for edits | |
| Menu / arrow navigation | Arrow-key menus/forms; most discoverable, least minimal | |

**User's choice:** Single-key commands

---

## Live theming via aether

| Option | Description | Selected |
|--------|-------------|----------|
| aether file, re-read at launch | Read ~/.config/aether/theme on startup; simplest | |
| aether + live watch | Watch theme output, repaint running TUI on change | ✓ |
| omarchy current theme | Read ~/.config/omarchy/current/theme directly | |

**User's choice:** aether + live watch
**Notes:** Researcher to confirm aether-output vs omarchy `current/theme` as canonical color source on this box.

---

## Edit + sudo commit flow

| Option | Description | Selected |
|--------|-------------|----------|
| Preview direction + cost, then sudo | Show tighten/loosen + token cost before commit; sudo prompt inline; show REFUSED | ✓ |
| Sudo-first, ctl reports | Skip preview; run sudo commit, ctl reports direction/refusal after prompt | |

**User's choice:** Preview direction + cost, then sudo

### Follow-up — preview mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Import the Python classifier | TUI imports guard.py/ngcommon.py direction logic locally; no key, no crypto, no ctl change | ✓ |
| Add ctl 'commit --dry-run' | Add --dry-run to nightguard_ctl.py that prints direction + cost | |

**User's choice:** Import the Python classifier

### Follow-up — grace (+8)

| Option | Description | Selected |
|--------|-------------|----------|
| Wire granting now | Add `ctl grace` command + TUI key to grant the window | |
| Display-only this phase | Show grace status/remaining; granting deferred | ✓ |
| Defer grace entirely | Don't show or grant grace | |

**User's choice:** Display-only this phase
**Notes:** Control-CLI currently has no grace-grant command (guard.py only reads the window); granting is a deferred follow-up.

### Follow-up — editable scope (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| Curfew window (start/end) | Edit curfew.start / curfew.end | ✓ |
| allow_commands list | Edit curfew.allow_commands | ✓ |
| enabled toggles | Toggle curfew/clock_protection/watchdog/blocking.*.enabled | ✓ |
| blocking blacklists | Edit blocking.native_apps.blacklist + browser_extension | ✓ |

**User's choice:** All four (curfew window, allow_commands, enabled toggles, blocking blacklists)
**Notes:** Read-only: messages, timezone, hmacs, ledger.

---

## Claude's Discretion

- Exact Textual screen/layout composition, widgets, and keybinding letters (single-key model).
- aether vs omarchy as canonical live-color source (verify in research).
- Per-field edit entry mechanics within the single-key model.

## Deferred Ideas

- Grace granting (`ctl grace` command + TUI key) — restores Windows "+8" on Linux; follow-up.
- StayFree blocklist import (Phase 9 finding: lists offline-recoverable from config.db) — candidate new phase.
- `ctl --dry-run` — rejected in favor of importing the classifier; noted for future server-side preview needs.
