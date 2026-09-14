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

### Omarchy Native Panel (PANEL)

> **Scope amended 2026-09-13, by explicit decision.** Phase 12.1's live walkthrough rejected the restyled Textual TUI: it read as a terminal form, not a native Omarchy dashboard — no amount of theme-token following closes that gap while it stays a terminal app. Decision: retire the terminal app and rebuild the dashboard/editor as a Quickshell panel plugin, conforming to the shell's own `Ui/` component library and first-party panel patterns (monitor/audio/network/tailscale). This absorbs BLK-01..05 (delivered in the panel instead of the TUI) and supersedes UIX-01 (a Quickshell panel consumes the shell's structural tokens natively — there is no separate "follow the theme" task once the surface itself is native). Phase 12.1 stays on the record as rejected evidence and is not reopened.

- [ ] **PANEL-01**: Privileged writes move from `sudo` on a PTY to `pkexec`/polkit against the same signer CLI, with every existing guarantee held: the signing key never enters the UI process, the backend stays the sole writer/signer, the pinned-path validation (`backend.py:27-53`) survives, and the authorisation is real (a live human-approved dialog) rather than cached-away. *(keystone — proven live before the phase opened: see 12.2.1-CONTEXT.md)*
- [ ] **PANEL-02**: The panel conforms to the shell's own component library (`PanelHero`, `PanelSectionHeader`, `PanelSlider`, `Toggle`, `ConfirmDialog`, etc.) and first-party panel patterns — no hand-rolled component the library already has, no writes done in-process (always `Process` invoking a CLI, per the monitor/audio/network/tailscale precedent).
- [x] **PANEL-03**: The `ngtui` Textual terminal app is retired in one deliberate step, once the panel can do everything it did — not incrementally, and not until parity is reached.
  **Done 2026-09-13.** Parity was measured rather than asserted: the terminal editor's `EDITABLE_FIELDS` table against the panel's `proposal.EDITABLE`, in `ngtui/tests/test_parity.py`, with the gate armed and seen to fail. One field was deliberately NOT taken over — `blocking.browser_extension.extension_id` has no entry in the signer's `FIELD_TABLE`, so a change to it classified as nothing, priced as free and was written anyway. Building a control for a write the trust boundary cannot judge is the opposite of the point; giving it a direction changes what costs a token and is the owner's call.
  Removed in the same step: `app.py`, `app.tcss`, `widgets/`, the `textual` dependency, the `.desktop` launcher, the Hyprland float rule for `org.omarchy.ngtui`, `ngtui-menu`, and the Waybar module and style (already inert — Omarchy 4 replaced Waybar with Quickshell). A bare `ngtui` now says where the editor went and exits 2.

### Blocking becomes editable (BLK) — delivered via Phase 12.2.1 (PANEL), not the TUI

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
| UIX-01 | Phase 12.1 | Superseded by 12.2.1 — a native panel consumes the shell's structural tokens natively |
| UIX-02 | Phase 12.1 | Complete |
| UIX-03 | Phase 12.1 | Complete |
| UIX-04 | Phase 12.1 | Complete |
| UIX-05 | Phase 12.1 | Complete |
| UIX-06 | Phase 12.1 | Complete |
| BLK-01 | Phase 12.2.1 (supersedes 12.2) | Complete |
| BLK-02 | Phase 12.2.1 (supersedes 12.2) | Complete |
| BLK-03 | Phase 12.2.1 (supersedes 12.2) | Complete |
| BLK-04 | Phase 12.2.1 (supersedes 12.2) | Complete |
| BLK-05 | Phase 12.2.1 (supersedes 12.2) | Complete |
| PANEL-01 | Phase 12.2.1 | Complete |
| PANEL-02 | Phase 12.2.1 | Complete |
| PANEL-03 | Phase 12.2.1 | Complete |
| PUB-00 | Phase 12.3 | Complete |
| PUB-01 | Phase 14 | Deferred — owner detection under `sudo -i` and on a multi-user machine |
| PUB-02 | Phase 14 | Deferred — a missing `uv` must not produce a panel that looks installed and can change nothing |
| PUB-03 | Phase 14 | Deferred — a first install must not name a legacy directory that never existed |
| LOCK-01 | Phase 15 | Deferred — enumerate installed Gecko browsers instead of a two-entry hard-coded map |
| LOCK-02 | Phase 15 | Deferred — the verifier reports its own coverage; no bare `LOCKED: yes` |
| CFG-01 | Phase 16 | Deferred — keys with no reader in this repo get one or go (`curfew.*_message`, `allow_commands`) |
| CFG-02 | Phase 16 | Deferred — `watchdog.enabled` / `check_interval_seconds` stop being priced as if they govern |
| CFG-03 | Phase 16 | Deferred — document `curfew.schedule.<day>` and the three browser keys the code reads |
| CFG-04 | Phase 16 | Deferred — `extension_id` gains a direction, or the refusal is recorded in the field table |
| TEST-01 | Phase 17 | Deferred — no fixture that no test uses (~250 of 579 lines) |
| TEST-02 | Phase 17 | Deferred — the three live-stack tests run against a built instance or go |
| TEST-03 | Phase 17 | Deferred — the two retired-palette modules resolved |

*(Phase column filled by the roadmapper.)*
