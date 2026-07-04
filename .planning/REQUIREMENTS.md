# Requirements — Milestone v2.1 · Desktop App

**Defined:** 2026-06-24 · Continues from v2.0 (Linux Port, shipped). REQ-IDs continue the project convention; phase numbering continues at Phase 11.

> **Scope:** package the existing `ngtui` Textual TUI as a first-class omarchy desktop app — global install, app-launcher entry (floating terminal), Waybar presence, brand icon, optional autostart, publish-ready AUR packaging. The TUI itself (StatusScreen + anti-impulse EditScreen) already shipped in v2.0; v2.1 is packaging + desktop integration, not new editing features.
>
> **Two load-bearing invariants (every requirement honors these):**
> 1. The inline-`sudo` commit needs a real PTY — every launch path wraps `ngtui` in a real terminal (`-e ngtui`), never detached.
> 2. The bar/launcher is a *window, never a lever* — no surface may loosen the curfew without the TUI's `sudo`-gated commit; the Waybar status reader is key-less and unprivileged.

## v2.1 Requirements

### Desktop App — install, launcher, packaging (DESK)

- [x] **DESK-01**: `uv tool install` exposes a global `ngtui` command that runs outside the dev venv and resolves the LifeOS trust stack from a clean login shell (no dev-shell env). *(keystone)*
- [x] **DESK-02**: A new **key-less** `ngtui status --json` subcommand emits Waybar-shaped JSON (`text`/`tooltip`/`class`) from `backend.live_verdict`/`tokens_left` — never reads the key, never needs root.
- [x] **DESK-03**: A `.desktop` launcher opens `ngtui` in a **floating terminal window** (`xdg-terminal-exec … -e ngtui`, `Terminal=false`) and appears in wofi/walker; floating is enforced by a Hyprland windowrule on a stable app-id/class, and the inline-`sudo` commit still works because it runs in a real terminal.
- [x] **DESK-04**: A custom own-brand icon (no borrowed logos) is installed into the hicolor theme and shown by the launcher and Waybar.
- [ ] **DESK-05**: Optional login autostart / pin (off by default) — autostarts the Waybar *module*; TUI-window autostart is opt-in.
- [ ] **DESK-06**: Publish-ready packaging — an AUR `PKGBUILD` installs the client (TUI + launcher + icon + status subcommand) **without vendoring the trust stack** (declared `optdepends`), plus a documented README install path; fails loud and explains when the trust stack is absent.

### Waybar presence (BAR)

- [x] **BAR-01**: A Waybar `custom/nightguard` module shows live curfew status in the bar (lock glyph + tokens, colored by state), sourced key-lessly from `ngtui status --json`, non-blocking and fail-closed.
- [x] **BAR-02**: Left-clicking the module opens/focuses the Nightguard Control TUI (floating terminal).
- [x] **BAR-03**: Right-clicking the module shows a **read-only** status/actions menu (verdict, tokens left, grace remaining, "open status" / "open editor") — with **no curfew-loosening action**.
- [x] **BAR-04**: The bar refreshes instantly after a commit (signal-based push, e.g. `SIGRTMIN+N`), not just polling.

## Future Requirements (deferred)

- **Grace-as-action from the bar/TUI** — blocked on grace-commit landing in the TUI (currently display-only, D-11); must arrive `sudo`-gated when built.
- **Carry-forwards from v2.0** — offline StayFree blocklist import; Nyquist backfill for phases 6/7/7.1; browser-policy root-lock; ROOT-02 watchdog clock-tamper wording.

## Out of Scope

| Item | Reason |
|------|--------|
| Any bar/launcher quick-action that loosens the curfew | Direct defeat of the self-binding core value; all mutation must pass the `sudo` friction |
| A backgrounded `ngtui` daemon / system tray | New always-on surface + escape-hatch risk; the bar module is a thin key-less reader instead |
| HMAC echo in the bar | Non-secret but pointless bar noise |
| Force-open the TUI window on every login | Autostart the status module, not the window; window autostart is opt-in |
| Vendoring the Python trust stack into the package | Violates PORT-02 (single trust stack); stack is an external `optdepends` |
| New editing features in the TUI | v2.1 is packaging/integration only; the editor shipped in v2.0 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DESK-01 | Phase 11 | Complete |
| DESK-02 | Phase 11 | Complete |
| DESK-03 | Phase 12 | Complete |
| DESK-04 | Phase 12 | Complete |
| DESK-05 | Phase 13 | Pending |
| DESK-06 | Phase 13 | Pending |
| BAR-01 | Phase 12 | Complete |
| BAR-02 | Phase 12 | Complete |
| BAR-03 | Phase 12 | Complete |
| BAR-04 | Phase 12 | Complete |

*(Phase column filled by the roadmapper.)*
