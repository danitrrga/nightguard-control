# Phase 13: Autostart + AUR Packaging - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-04
**Phase:** 13-autostart-aur-packaging
**Areas discussed:** Audience / trust-stack story, Autostart shape (DESK-05), Package contents & drop-ins (DESK-06), Fail-loud surface (SC3/SC4)

**Format note:** The gray-area multi-select drew no response (user away). Per workflow, Claude proposed a recommended resolution for all four areas grounded strictly in the locked roadmap success criteria + PORT-02, and the user reviewed and approved them wholesale ("looks good and works fine"). Options below reflect the proposal that was accepted.

---

## Audience / trust-stack story

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Genuinely third-party-installable | Ship generic trust-stack scaffolding so any stranger can run it turnkey | |
| (b) Clean publishable packaging of the author's app, third-party-honest | Installable + `NIGHTGUARD_STACK_DIR`-pointable, but README is explicit the stack is the author's LifeOS component; no vendoring, no generic scaffolding | ✓ |

**User's choice:** (b) — clean publishable packaging, third-party-honest.
**Notes:** Honors PORT-02 (never vendor). Anyone without the stack fails loud + actionable.

---

## Autostart shape (DESK-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Forced login process | Autostart something on every login by default | |
| Documented off-by-default drop-ins + opt-in TUI-window autostart | Module rides Waybar's own startup; opt-in Hyprland `exec-once` (preferred over `systemd --user`) for the TUI window, always via `-e ngtui` wrapper | ✓ |

**User's choice:** Documented, off-by-default; opt-in `exec-once` for the window.
**Notes:** No revived no-TTY break; no unprompted editor on login. omarchy-native flavor.

---

## Package contents & drop-ins (DESK-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-merge config into user configs | Package edits the user's Waybar/Hyprland configs | |
| Installed binary/desktop/icon + paste-it-yourself config drop-ins | `ngtui` + `.desktop` + icon installed; module/style/windowrule shipped to `/usr/share/nightguard/` as copy-paste; `python-wheel` PKGBUILD; nothing root-owned/0600; stack = `optdepends` + `.install` message | ✓ |

**User's choice:** Installed binary/desktop/icon + paste-it-yourself drop-ins.
**Notes:** Never clobber arbitrary users' configs. Sudoers stays manual/reviewed.

---

## Fail-loud surface (SC3/SC4)

| Option | Description | Selected |
|--------|-------------|----------|
| Unify failure behavior | Same behavior for TUI and status path | |
| Split: loud TUI startup / quiet fail-closed status | Interactive `ngtui` hard-aborts with actionable stderr (`set NIGHTGUARD_STACK_DIR=…`); `ngtui status --json` stays silent fail-closed to `unavailable` exit 0 | ✓ |

**User's choice:** Split — loud TUI, quiet bar.
**Notes:** A bar must never spew errors. README documents `environment.d` for the stack path.

---

## Claude's Discretion

- **AUR package name** → recommended `nightguard-control` (console script `ngtui`).
- **Build source** → recommended a git release tag (versioned tarball), idiomatic AUR.
- **README location** → recommended a top-level `README.md` for the publish/install story.

These were flagged to the user and left as recommended-not-locked defaults for plan time.

## Deferred Ideas

- Grace-as-action (`sudo`-gated grace from TUI/menu) — needs `nightguard_ctl.py grace` first; v3.0 candidate.
- Offline StayFree blocklist import (TRAK) — parked, future milestone.
- Nyquist backfill for phases 6/7/7.1, browser-policy root-lock, ROOT-02 watchdog wording — carried v2.0 tech-debt.
