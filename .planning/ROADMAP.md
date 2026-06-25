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

- [ ] Phase 11: Global Install + Status Subcommand (3 plans) — `uv tool install` exposes a global `ngtui`; key-less `ngtui status --json` emits Waybar JSON — DESK-01, DESK-02
- [ ] Phase 12: Launcher + Waybar Presence — floating-terminal `.desktop` + brand icon + Hyprland windowrule; `custom/nightguard` bar module (left-click open, right-click read-only menu, signal refresh) — DESK-03, DESK-04, BAR-01..04
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
- [ ] 11-03-PLAN.md — manual checkpoints: `uv tool install` clean-env resolution (SC-1/SC-5) + live token commit (SC-4)

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
**Plans**: TBD
**UI hint**: yes

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
| 11. Global Install + Status Subcommand | v2.1 | 2/3 | In Progress|  |
| 12. Launcher + Waybar Presence | v2.1 | 0/? | Not started | — |
| 13. Autostart + AUR Packaging | v2.1 | 0/? | Not started | — |
