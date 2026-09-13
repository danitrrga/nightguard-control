# Requirements — Milestone v2.1 · Desktop App

**Defined:** 2026-06-24 · Continues from v2.0 (Linux Port, shipped). REQ-IDs continue the project convention; phase numbering continues at Phase 11.

> **Scope:** package the existing `ngtui` Textual TUI as a first-class omarchy desktop app — global install, app-launcher entry (floating terminal), Waybar presence, brand icon, optional autostart, publish-ready AUR packaging.
>
> **Scope amended 2026-09-12, by explicit decision.** The milestone originally read "v2.1 is packaging + desktop integration, not new editing features", and listed new TUI editing features as out of scope. Two things changed that:
> 1. Omarchy 4 ("Quattro") replaced Waybar with quickshell and brought a full surface/control token system (`shell.toml`). The TUI follows only `colors.toml`, so it looks a generation behind the desktop it ships on, and it is keyboard-only while every native panel beside it is pointer-first. Packaging that as the v2.1 deliverable would ship the old generation.
> 2. Four blocking config keys the signer already classifies were never exposed by the only sanctioned editor, and a hand edit to `config.yaml` is reverted by the watchdog — so they are not awkward to change, they are **impossible** to change. That is why no site is blocked and three installed games are covered by nothing.
>
> So v2.1 now also carries the native-dashboard refresh (UIX) and makes those four keys editable (BLK), both **before** packaging, so the AUR package ships the current generation.
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

### Native dashboard — look and interaction (UIX)

- [ ] **UIX-01**: The TUI restyles from the live desktop theme's **structural** tokens, not only its colours — `shell.toml`'s `[controls]` state fills/borders, `[spacing]`, `[font]`, plus Hyprland's `decoration:rounding` — and a desktop theme change restyles the *running* TUI. Today `load_omarchy_theme` maps only `colors.toml`; `omarchy_style()` already parses the rest but the bar panel is its only consumer. *(keystone)*
- [x] **UIX-02**: **One cursor shared by pointer and keyboard.** A control is highlighted when the pointer is over it *or* the keyboard cursor is on it, and mouse-enter *moves* the keyboard cursor so the two can never disagree. Paint priority pressed > focus > hover/cursor > selected > idle, using the theme's own alphas. This is the pattern Omarchy's own panels are built on (`Ui/Button.qml`, `plugins/panels/monitor/Panel.qml`).
- [x] **UIX-03**: Every changeable value on the home surface is a **clickable control** — switch row, segmented control, list row — and the whole row is the click target. Nothing requires memorising a bracket hint. The keyboard still drives everything (`j`/`k`, arrows, `Enter`/`Space`, `Escape`).
- [x] **UIX-04**: The day is an **instrument, not a number**: a full-width ASCII density ramp whose density is hours-until-curfew, a separate channel marking the hours a loosening is accepted, and a marker for now. Hovering any column reads out that hour and whether a loosening would be accepted there.
- [x] **UIX-05**: Hover never reflows — border widths are constant across states, as the shell kit guarantees by reserving the largest border. Colour transition ~120 ms, tooltip delay ~400 ms, matching the kit.
- [x] **UIX-06**: No fixed hex in `app.tcss` or the widgets, and the layout fits the sanctioned window (135 × 46 cells at the live terminal font) with a test that fails on overflow.

### Blocking becomes editable (BLK)

- [ ] **BLK-01**: The four keys the signer already classifies but the editor never exposed become editable: the **site list** (`blocking.browser_extension.blocked_urls`), the **app mode** (`blocking.native_apps.mode`), **game blocking** (`blocking.native_apps.block_games`) and the **allowlist** (`blocking.native_apps.allowlist`). *(keystone)*
- [ ] **BLK-02**: A commit that touches a list costs **one token per list touched**, and is gated by the clock edit window — enforced by the **signer**, not by the TUI. ⚠️ *Open decision:* whether that applies in both directions (as specified) or only when the edit loosens. Applied uniformly, adding a site to the blocklist is a *tightening* that still costs a token and is still refused outside the window, so the pact cannot be made stricter at midnight — which contradicts the rule the guard already applies to every other tightening. Both rules are live behind a switch in `.planning/sketches/004-native-dashboard/`.
- [ ] **BLK-03**: The blocking surface shows **what the machine knows and the config cannot**: which blocklist entries match a running process and which match nothing, the titles the game catalogue detected, the floor the allowlist cannot shrink, and whether enforcement is the strong cgroup jail or the weak `SIGTERM` fallback.
- [ ] **BLK-04**: Cost and refusal are stated **before any authentication** — a refused commit says why and never reaches a prompt it would fail.
- [ ] **BLK-05**: The trust path is unchanged in kind: the TUI holds no key, computes no HMAC, and the signer stays the sole writer. The per-list cost rule lives in the signer's own quota decision — the one function both the pre-auth preview and the commit call — so the refusal is visible before authenticating rather than after.

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
| ~~New editing features in the TUI~~ | **Superseded 2026-09-12** — the four blocking keys were unreachable from the only sanctioned editor, which made them unchangeable rather than merely unexposed. Now BLK-01. |
| Editing anything the signer does not already classify | The direction classifier is the gate; a key it does not know would commit as a free no-op, which is a silent bypass |
| Mouse-driven commit without the `sudo` prompt | Pointer support is for navigating and staging; authorisation keeps the inline-`sudo` friction |

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
| UIX-01 | Phase 12.1 | Pending |
| UIX-02 | Phase 12.1 | Complete |
| UIX-03 | Phase 12.1 | Complete |
| UIX-04 | Phase 12.1 | Complete |
| UIX-05 | Phase 12.1 | Complete |
| UIX-06 | Phase 12.1 | Complete |
| BLK-01 | Phase 12.2 | Pending |
| BLK-02 | Phase 12.2 | Pending |
| BLK-03 | Phase 12.2 | Pending |
| BLK-04 | Phase 12.2 | Pending |
| BLK-05 | Phase 12.2 | Pending |

*(Phase column filled by the roadmapper.)*
