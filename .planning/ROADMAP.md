# Roadmap: Nightguard Control

## Milestones

- ✅ **v1.0 · Windows** — Phases 1–5 (Tauri/Rust/PowerShell trust stack) — *superseded by the Linux port*
- ✅ **v2.0 · Linux Port** — Phases 6–10 (single Python trust stack + omarchy TUI) — **shipped 2026-06-24**
- 🚧 **v2.1 · Desktop App** — Phases 11–13 (global install + launcher + Waybar + AUR packaging) — **in progress**
- 📋 **v3.0 · (next)** — to be defined via `/gsd:new-milestone`

## Phases

<details>
<summary>✅ v1.0 · Windows (Phases 1–5) — superseded by the Linux port</summary>

- [x] Phase 1: Trust Kernel (3 plans) — HMAC + DPAPI + atomic writes, Rust↔PowerShell parity
- [x] Phase 2: Mutation Engine (5 plans) — direction classifier, weekly token quota, DST-aware reset, NTP grace
- [x] Phase 3: Enforcement Guard (4 plans) — always-firing PowerShell guard, auto-revert, fail-closed
- [x] Phase 4: UI Moonlit Indigo (5 plans) — Tauri display + edit-intent layer *(retired; replaced by the Phase-10 TUI)*
- [x] Phase 5: Instance Wiring (3 plans) — point the live hook at the canonical config

*The Windows/DPAPI/PowerShell stack and the Moonlit Indigo Tauri UI are retired; the trust-model invariants carry forward into the Linux port.*

</details>

<details>
<summary>✅ v2.0 · Linux Port (Phases 6–10) — SHIPPED 2026-06-24</summary>

- [x] Phase 6: Config Cleanup (2 plans) — Linux `blocking:` schema (`browser_extension` + `native_apps`) — LXCF-01/02
- [x] Phase 7: Root Integrity Wall (2 plans) — root-owned key + sanctioned config; watchdog as systemd system service; sole signer = control-CLI via `sudo` — ROOT-01..04
- [x] Phase 7.1: Curfew Hook (3 plans) — `guard.py` wired as the Claude Code curfew hook — CURF-01
- [~] Phase 8: Native Blocker (2 plans) — **DESCOPED**: native-app kill built then reverted; curfew hook deemed sufficient. `curfew_verdict()` refactor survives — NBLK-01/02/03 descoped
- [~] Phase 9: StayFree Desktop (2/3 plans) — **PARKED**: StayFree records 0 sessions on Wayland (spike failed); offline config-import is a future-phase candidate — TRAK-01/02 parked
- [x] Phase 10: Linux App — omarchy TUI (3 plans) — Textual thin client over the Python trust stack; anti-impulse editing — PORT-01/02/03

**Full detail:** [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md) · **Audit:** [`milestones/v2.0-MILESTONE-AUDIT.md`](milestones/v2.0-MILESTONE-AUDIT.md) · **Requirements:** [`milestones/v2.0-REQUIREMENTS.md`](milestones/v2.0-REQUIREMENTS.md)

</details>

### 🚧 v2.1 · Desktop App (Phases 11–13)

Package the existing `ngtui` Textual TUI as a first-class omarchy desktop app — a global `ngtui` command + key-less status subcommand, a floating-terminal launcher with a brand icon, a Waybar `custom/nightguard` module, optional autostart, and an AUR-ready PKGBUILD. Packaging/integration only — no new editing features. Every surface honors the two load-bearing invariants: the inline-`sudo` commit needs a real PTY, and the bar/launcher is *a window, never a lever*.

- [x] Phase 11: Global Install + Status Subcommand (3 plans) — `uv tool install` exposes a global `ngtui`; key-less `ngtui status --json` emits Waybar JSON — DESK-01, DESK-02
- [x] Phase 12: Launcher + Waybar Presence — floating-terminal `.desktop` + brand icon + Hyprland windowrule; `custom/nightguard` bar module (left-click open, right-click read-only menu, signal refresh) — DESK-03, DESK-04, BAR-01..04 (completed 2026-07-04)
- [ ] Phase 12.1: Native dashboard — the TUI restyled from the live theme's structural tokens and driven by one cursor shared between pointer and keyboard — UIX-02..06 complete, **UIX-01 still Pending**; all 9 plans executed 2026-09-13, phase gate (the live walkthrough) OPEN
- [ ] Phase 12.2: Blocking becomes editable — the four keys the signer classifies but the editor never exposed, at one token per list — BLK-01..05
- [ ] Phase 13: Autostart + AUR Packaging — optional login autostart (module, not window) + publish-ready PKGBUILD/README that declares (never vendors) the trust stack — DESK-05, DESK-06

### 📋 v3.0 — (next milestone)

Run `/gsd:new-milestone` to scope the next milestone. Carried-forward candidates (from the v2.0 audit tech debt): offline StayFree blocklist import (TRAK), Nyquist backfill for phases 6/7/7.1, browser-policy root-lock, ROOT-02 watchdog wording, grace-as-action (`sudo`-gated) once grace-commit lands in the TUI (D-11).

## Phase Details

### Phase 11: Global Install + Status Subcommand

**Goal**: `ngtui` becomes a globally-installed command that resolves the LifeOS trust stack from a bare login shell, and exposes a new key-less `ngtui status --json` subcommand that emits Waybar-shaped JSON — the keystone substrate every later phase stands on.
**Depends on**: Phase 10 (the shipped `ngtui` TUI + `backend.py` read seam)
**Requirements**: DESK-01, DESK-02
**Success Criteria** (what must be TRUE):

  1. `uv tool install --python 3.14 .` puts a real `ngtui` on `PATH`; the installed shim (not `python -m ngtui`) launches the TUI from a clean login shell with NO `NIGHTGUARD_*` dev-shell env, resolving the LifeOS stack via `backend.py` defaults.
  2. `ngtui status --json` prints a single-line, `jq`-valid Waybar object (`text`/`tooltip`/`class`) sourced key-lessly from `backend.live_verdict`/`tokens_left` — it never reads the `.guardkey`, never computes an HMAC, never calls `sudo`, and never prompts.
  3. The status reader fails closed: any stack/read error emits `{"text":"○ —","class":"unavailable"}` and exits 0 (never blocks or crashes the eventual bar).
  4. A real loosen-with-token commit still succeeds end-to-end from the installed `ngtui` (the inline-`sudo` PTY path survives the global-install interpreter/env change); a `sys.stdin.isatty()` startup check fails loudly when run without a TTY.
  5. Flag resolved: `guard.json` + the sanctioned config are confirmed **user-readable** from the isolated-venv process (not 0600 root-only), and `_DEFAULT_STACK_DIR` resolves from a clean login shell — else the whole Waybar/status path is blocked.

**Plans**: 3 plans

- [x] 11-01-PLAN.md — pure key-less status builder (`status.py`) + cache-only verdict seam + Wave-0 headless tests
- [x] 11-02-PLAN.md — `__main__.py` argv router: `status --json` emitter (fail-closed, exit 0) + TTY guard
- [x] 11-03-PLAN.md — manual checkpoints: `uv tool install` clean-env resolution (SC-1/SC-5) + live token commit (SC-4) — human-verified GREEN

### Phase 12: Launcher + Waybar Presence

**Goal**: Nightguard appears as a first-class omarchy surface — a brand-iconed `.desktop` entry that opens the TUI in a floating terminal, and a `custom/nightguard` Waybar module showing live curfew status with left-click-open / right-click-read-only-menu and instant post-commit refresh.
**Depends on**: Phase 11 (global `ngtui` + `ngtui status --json`)
**Requirements**: DESK-03, DESK-04, BAR-01, BAR-02, BAR-03, BAR-04
**Success Criteria** (what must be TRUE):

  1. A `nightguard.desktop` (`Exec=xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui`, `Terminal=false`) appears in wofi/walker and, when launched, opens `ngtui` as a **floating, centered** window (Hyprland windowrule matching the stable `org.omarchy.ngtui` app-id/`initialClass`, not title); other terminals still tile.
  2. The custom own-brand icon (no borrowed logos), installed into the hicolor theme, shows on the launcher entry (and the bar mechanism is decided/working) — appearing immediately after install, not only after relogin.
  3. The `custom/nightguard` Waybar module shows live lock-glyph + tokens colored by state, sourced key-lessly from `ngtui status --json`, non-blocking (no `sudo`/NTP in the exec) and fail-closed to `unavailable` on error.
  4. Left-click opens/focuses the floating TUI; right-click shows a **read-only** status/actions menu (verdict, tokens left, grace remaining, "open status"/"open editor") with **no curfew-loosening action** — and a real loosen-with-token commit still succeeds end-to-end after launching from the bar (PTY path intact).
  5. The bar refreshes **instantly** after a commit via a signal push (a free `SIGRTMIN+N` slot confirmed in the live Waybar config and wired into `backend.commit()`), not just on the poll interval.

**Plans**: 6 plans
Plans:
**Wave 1**

- [x] 12-01-PLAN.md — [BLOCKING] (re)install `ngtui` on PATH + green baseline (prereq)
- [x] 12-02-PLAN.md — BAR-04: success-only `SIGRTMIN+11` bar refresh in `backend.commit()` (TDD)
- [x] 12-03-PLAN.md — DESK-04: hand-authored crescent-on-tile brand SVG
- [x] 12-04-PLAN.md — DESK-03/BAR-01/02/03: `.desktop` + windowrule + module + style + `ngtui-menu` artifacts

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 12-05-PLAN.md — D-07: idempotent backup-first installer + fixture idempotency test

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 12-06-PLAN.md — live install + phase-gate human-verify (float/icon/bar/menu/commit-refresh)

**UI hint**: yes

### Phase 12.1: Native dashboard — pointer-first Omarchy TUI (INSERTED)

**Goal**: The TUI reads and behaves as a native Omarchy 4 app rather than a terminal form — restyled from the live theme's *structural* tokens (not just its colours), driven by **one cursor shared between pointer and keyboard**, with the day shown as a full-width instrument instead of a number. Same product as the finished bar panel, without copying its patterns.
**Depends on**: Phase 12 (the launcher + windowrule that give the TUI its 135 × 46 window)
**Requirements**: UIX-01, UIX-02, UIX-03, UIX-04, UIX-05, UIX-06
**Design contract**: `.planning/sketches/00{1,2,3,4}-*/` — direction chosen (tile grid), aesthetic accepted (device frame, greyscale ASCII ramp hero, outline chips, one accent dot), interaction model read out of `/usr/share/omarchy/shell/`.
**Success Criteria** (what must be TRUE):

  1. `app.tcss` and the widgets are restyled from `shell.toml`'s `[controls]` state fills/borders, `[spacing]` and `[font]`, plus Hyprland's live `decoration:rounding` — and switching the desktop theme restyles the **running** TUI, borders and fills included, not only its colours. A negative-control test fails when the style tokens are ignored, and its failure message is recorded.
  2. Hovering a row and then pressing `j`/`k` continues the highlight **from where the pointer left it** — one cursor, moved by either input, with paint priority pressed > focus > hover/cursor > selected > idle from the theme's own alphas. Every control is reachable and activatable by keyboard alone (`Enter`/`Space`), and by pointer alone.
  3. Every changeable value on the home surface is a clickable control whose whole row is the click target; no action requires a memorised bracket hint. Hovering never reflows a neighbour (border widths constant across states).
  4. The day renders as a full-width ASCII density ramp (density = hours-until-curfew) with a separate channel for the hours a loosening is accepted and a marker for now; hovering a column reads out that hour and whether a loosening would be accepted there.
  5. No fixed hex in `app.tcss` or any widget, and the composed screen fits 135 × 46 cells — asserted by a test that fails on overflow, so the layout cannot quietly outgrow the sanctioned window.
  6. The trust path is untouched: `backend.commit()`, the inline `sudo` under `App.suspend()` with a real PTY, the direction classifier, and the refusal to accept a weakening keystroke outside the edit window all behave exactly as before, proven by the existing suite staying green.

**Plans**: 9 plans in 7 waves

Plans:

**Wave 1**

- [x] 12.1-01-PLAN.md — [BLOCKING] async test idiom + UI fixture group + the literal-hex scan (control 1)
- [x] 12.1-02-PLAN.md — colour-role pick chains in theme.py + the 28-theme Textual-role sweep (control 4)

**Wave 2**

- [x] 12.1-03-PLAN.md — omarchy_style injection seam + full [controls] ladder + hypr_rounding + style_variables (controls 3b/4b/4c)

**Wave 3**

- [x] 12.1-04-PLAN.md — get_css_variables + the real repaint sequence + app.tcss rewritten with the paint ladder (controls 2/3)

**Wave 4** *(parallel)*

- [x] 12.1-05-PLAN.md — ControlRow + the 16-stop registry + the shared cursor and no-reflow controls (5/6/6b/6c/7/8)
- [x] 12.1-06-PLAN.md — DayRamp + the pure density/column helpers + the hero controls (11/11b/11c)

**Wave 5**

- [x] 12.1-07-PLAN.md — StatusScreen recomposed across the 46-row budget; Header gone, chips in

**Wave 6**

- [x] 12.1-08-PLAN.md — edit.py chrome removal + on_resize degradation + the window and accent budgets (controls 9/10)

**Wave 7**

- [x] 12.1-09-PLAN.md — control-ledger close-out + trust-path diff audit + live walkthrough checkpoint
      - Task 1 closed: 20 control rows, each with its verbatim failure message, zero blank. Found and fixed a control that could not fail — the no-crypto scan (PORT-03) resolved its root one `parent.parent` too deep and had been scanning **zero** files.
      - Task 2 OPEN: the live walkthrough is a human gate and was not auto-approved. The `ngtui` shim is reinstalled from this tree, so it will test this phase's UI.

### Phase 12.2: Blocking becomes editable — the four frozen keys (INSERTED)

**Goal**: The half of the product that actually ends applications stops being unchangeable. The four blocking keys the signer already classifies but the only sanctioned editor never exposed become editable, at one token per list touched, inside the same clock window that gates a curfew loosening — with the cost stated before any authentication.
**Depends on**: Phase 12.1 (the control rows and staging surface these keys are edited through)
**Requirements**: BLK-01, BLK-02, BLK-03, BLK-04, BLK-05
**Success Criteria** (what must be TRUE):

  1. The site list, the app blocklist/allowlist mode, game blocking and the allowlist are all editable from the TUI and commit through the signer — and a real end-to-end commit of each is proven against the running stack, not just unit-tested. Blocking a site becomes possible for the first time.
  2. A commit touching N lists costs **N tokens**, decided inside the signer's own quota decision (the one function both the pre-auth preview and the commit call), so the cost and any refusal are visible **before** the fingerprint prompt and never after. A negative control proves the charge can fail.
  3. Outside the clock edit window, a list edit is refused by the signer with its own reason, and the TUI shows that reason on the control before it is touched — never a prompt the user cannot pass.
  4. The surface shows what the config cannot: which blocklist entries match a running process and which match nothing (`discord` matches nothing — it is a chromium webapp), the titles the game catalogue detected, the floor the allowlist cannot shrink, and whether enforcement is the strong cgroup jail or the weak `SIGTERM` fallback.
  5. The TUI still holds no key and computes no HMAC; the signer stays the sole writer; the watchdog still reverts a hand edit to any of the four keys.
  6. **Decision resolved before the signer is touched** (it blocks one task, not the phase — the surface work is identical either way): whether the per-list token applies in both directions or only when the edit loosens. Applied uniformly, *adding* a site to the blocklist is a tightening that still costs a token and is still refused outside the window — so the pact cannot be made stricter at midnight, which contradicts the rule the guard already applies to every other tightening. Both rules are live behind a switch in `.planning/sketches/004-native-dashboard/`.

**Plans**: TBD

### Phase 13: Autostart + AUR Packaging

**Goal**: Make the desktop app publish-ready — an optional, off-by-default login autostart for the status surface, plus an AUR `PKGBUILD` and documented README install path that declares (never vendors) the Python trust stack and fails loud when it is absent.
**Depends on**: Phase 12 (the `.desktop` + icon + Waybar artifacts the package installs)
**Requirements**: DESK-05, DESK-06
**Success Criteria** (what must be TRUE):

  1. Optional login autostart (off by default) autostarts the Waybar **module**, not the TUI window; any opt-in TUI-window autostart still uses the full `-e ngtui` terminal+env wrapper (no revived no-TTY break, no unprompted editor on every login).
  2. An AUR `PKGBUILD` installs the client (TUI + `ngtui status` subcommand + `.desktop` + brand icon + doc snippets) via the idiomatic python-wheel route — installing **no** root-owned/0600 files and **never vendoring** the trust stack (PORT-02); the stack is declared `optdepends` + an `.install` message, and the sudoers entry stays a manual reviewed step.
  3. On a machine without the LifeOS trust stack the packaged app fails **loudly and actionably** at startup (clear "set `NIGHTGUARD_STACK_DIR`" guidance), not cryptically at commit time; the README documents the full install path (`uv tool install` for the author, PKGBUILD for others, `environment.d` for the stack path).
  4. The packaged status reader is still key-less/unprivileged and no packaged launcher/autostart surface can loosen the curfew without the `sudo` prompt; install hooks refresh the icon/desktop caches (`gtk-update-icon-cache` + `update-desktop-database`).
  5. Flag resolved: `python-textual 8.2.7` availability in Arch repos/AUR confirmed at publish time (else documented as a bundled/AUR-dep contingency).

**Plans**: TBD

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Trust Kernel | v1.0 | 3/3 | Complete (superseded) | — |
| 2. Mutation Engine | v1.0 | 5/5 | Complete (superseded) | — |
| 3. Enforcement Guard | v1.0 | 4/4 | Complete (superseded) | — |
| 4. UI Moonlit Indigo | v1.0 | 5/5 | Complete (retired) | — |
| 5. Instance Wiring | v1.0 | 3/3 | Complete (superseded) | — |
| 6. Config Cleanup | v2.0 | 2/2 | Complete | 2026-06-22 |
| 7. Root Integrity Wall | v2.0 | 2/2 | Complete | 2026-06-22 |
| 7.1 Curfew Hook | v2.0 | 3/3 | Complete | 2026-06-23 |
| 8. Native Blocker | v2.0 | 2/2 | Descoped (reverted) | 2026-06-24 |
| 9. StayFree Desktop | v2.0 | 2/3 | Parked (spike failed) | — |
| 10. Linux App (omarchy TUI) | v2.0 | 3/3 | Complete | 2026-06-24 |
| 11. Global Install + Status Subcommand | v2.1 | 3/3 | Complete    | 2026-06-25 |
| 12. Launcher + Waybar Presence | v2.1 | 6/6 | Complete    | 2026-07-04 |
| 12.1 Native dashboard | v2.1 | 9/9 | Complete   | 2026-09-13 |
| 12.2 Blocking editable | v2.1 | 0/? | Not started | — |
| 13. Autostart + AUR Packaging | v2.1 | 0/? | Not started | — |
