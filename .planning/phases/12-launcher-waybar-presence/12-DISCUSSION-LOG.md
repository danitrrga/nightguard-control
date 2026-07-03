# Phase 12: Launcher + Waybar Presence - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-03
**Phase:** 12-launcher-waybar-presence
**Areas discussed:** Brand icon, Right-click menu, Install target, Bar appearance

> **Session note:** The user selected "discuss all four areas" then stepped away
> (two AskUserQuestion timeouts). Per the discuss-phase timeout protocol, Claude
> resolved each area with best-judgment defaults grounded in the locked roadmap
> success criteria and a live-system scout (Waybar config, Hyprland windowrules,
> default terminal, hicolor theme). Icon concept + build (D-01/D-02) are flagged
> **UNCONFIRMED** in CONTEXT.md for the user to confirm/override before planning.

---

## Brand icon

| Option | Description | Selected |
|--------|-------------|----------|
| Shield + moon | Shield silhouette with a crescent-moon cut-out — legible at 16px, on-brand ("guards the night") | ✓ (default, unconfirmed) |
| Crescent + lock | Crescent fused with padlock/keyhole — leans into "self-binding / locked curfew" | |
| Abstract mark | Minimal geometric mark — cleaner, less literal, blends with omarchy flat aesthetic | |

**Build sub-decision:**

| Option | Description | Selected |
|--------|-------------|----------|
| I design a real SVG now | Claude authors SVG + rasterizes hicolor PNGs this phase; real final icon, iterable | ✓ (default, unconfirmed) |
| Placeholder now, polish later | Functional placeholder this phase, finished art later | |
| You provide the art | User supplies SVG/PNG; phase wires install only | |

**User's choice:** No response (away) — Claude default: shield + crescent, hand-authored SVG now.
**Notes:** Most user-owned decision in this phase; explicitly flagged UNCONFIRMED in CONTEXT.md (D-01/D-02). Own-brand only, no borrowed logos. Installs to `~/.local/share/icons/hicolor/*/apps/org.omarchy.ngtui.*` with cache refresh so it shows immediately (SC-2).

---

## Right-click menu

| Option | Description | Selected |
|--------|-------------|----------|
| wofi/walker dmenu popup | Script reads `ngtui status --json`, shows read-only header (verdict/tokens/grace) + selectable "Open editor"/"Open status" | ✓ |
| Floating-terminal presentation | `omarchy-launch-floating-terminal-with-presentation ngtui status` — text only, no actionable menu | |
| Waybar native tooltip | Hover tooltip only — not a right-click menu | |

**User's choice:** No response (away) — Claude default: wofi/walker dmenu popup script (D-04).
**Notes:** Most omarchy-idiomatic and the only option giving both the read-only status readout AND actionable "open" entries while honoring "a window, never a lever" (no loosening action). Exact tool (wofi vs walker `--dmenu`) left to researcher.

---

## Install target

| Option | Description | Selected |
|--------|-------------|----------|
| Idempotent live-config install (author) + defer publish snippets | Merge module/windowrule into live configs idempotently (backup first); ship artifacts; publish/README path → Phase 13 | ✓ |
| Ship snippets only, user pastes | Documented drop-in snippets, no live-config writes this phase | |
| Full live write, no idempotency guard | Simplest but risks duplicate blocks on re-run | |

**User's choice:** No response (away) — Claude default: idempotent live-config install now, publish snippets deferred to Phase 13 (D-06/D-07/D-08).
**Notes:** Waybar `config.jsonc` scouted as a plain hand-editable file (not omarchy-symlinked), so live merge is viable but must be idempotent + backup (outward, hard-to-reverse edit to the author's system). Publish-safe snippet path belongs with the Phase 13 PKGBUILD.

---

## Bar appearance

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed semantic classes (CSS) | Style `#custom-nightguard.locked` etc. red/amber/green — legible danger signal; reuses `status.py`'s existing class contract | ✓ |
| Live aether/omarchy theme colors | Track desktop theme like the TUI | |

**Text verbosity sub-decision:**

| Option | Description | Selected |
|--------|-------------|----------|
| Keep `glyph + tokens` always (as-built) | `status.py` unchanged; grace in tooltip/menu, not bar text | ✓ |
| Tokens only when locked | Hide token count outside curfew | |
| Grace countdown in bar text | Live countdown in the bar | |

**User's choice:** No response (away) — Claude default: fixed semantic CSS classes + keep `status.py` text as-built (D-09/D-10).
**Notes:** Intentional divergence from the TUI's live theming — the bar is a status light, not an editor. Poll-interval bar can't show a smooth grace countdown without jitter (signal push is commit-triggered, not per-second), so grace stays in the tooltip/menu.

---

## Claude's Discretion

- Exact Hyprland windowrule syntax + size/centering values (mirror scouted `float on, match:class ^(...)$`).
- Whether `xdg-terminal-exec --app-id=` maps to Alacritty's Wayland app-id/class (researcher must verify; fall back to `--class`).
- Exact free `SIGRTMIN` slot (7/8/9/10 taken; confirm a free one at plan time).
- Menu tool (wofi vs walker) and the open-or-focus command (reuse omarchy helper vs custom).
- Icon glyph/geometry details within the chosen concept.

## Deferred Ideas

- Autostart / login pin (DESK-05) — Phase 13.
- AUR PKGBUILD + README publish-safe snippet path (DESK-06) — Phase 13.
- Grace-as-action (`sudo`-gated "+8") — needs a `nightguard_ctl.py grace` command first; never a bar action.
- Live-themed bar colors — considered, rejected for the status module (D-09).
