# Phase 13: Autostart + AUR Packaging - Context

**Gathered:** 2026-07-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the desktop app **publish-ready**: an optional, off-by-default login autostart
for the status surface, plus an AUR `PKGBUILD` and a documented README install path
that **declares (never vendors)** the Python trust stack and **fails loud** when it is
absent. Requirements: **DESK-05** (autostart), **DESK-06** (packaging).

This phase packages and documents the artifacts Phase 12 already shipped
(`.desktop`, hicolor icon, Waybar `custom/nightguard` module + style, Hyprland
windowrule, the `ngtui` console script + `ngtui status --json`). It adds **no** new
curfew-editing capability and **no** grace-granting.

**Out of scope:** any new TUI editing feature; grace-as-action; auto-merging config
into arbitrary users' Waybar/Hyprland configs; vendoring or scaffolding a generic
trust stack.

</domain>

<decisions>
## Implementation Decisions

### Audience / trust-stack story
- **D-01:** Target = **clean, publishable packaging of the author's own app, third-party-honest.**
  A stranger *can* technically install the client and point `NIGHTGUARD_STACK_DIR` at
  their own stack, but the README is explicit that the Python trust stack is the
  author's LifeOS-specific component — **not** a turnkey dependency and **not** vendored
  (PORT-02). No generic trust-stack scaffolding is shipped. Anyone without the stack
  gets a loud, actionable failure (see D-08).

### Autostart (DESK-05)
- **D-02:** The Waybar module already comes up with Waybar itself (Phase 12), so
  "autostart" is delivered as **documentation + drop-ins, not a forced login process.**
  Ship the module snippet so a fresh Waybar config renders it, and provide an **opt-in,
  off-by-default** autostart for the *TUI window* only.
- **D-03:** Prefer a documented Hyprland **`exec-once` snippet** (omarchy-native) over a
  `systemd --user` unit for the opt-in TUI-window autostart. Any TUI-window autostart
  MUST use the full `-e ngtui` terminal+env wrapper — **never** a bare `ngtui` (no
  revived no-TTY break, no unprompted editor on every login). Off by default; the user
  opts in by uncommenting/adding the snippet.

### Package contents & drop-ins (DESK-06)
- **D-04:** **Installed directly:** the `ngtui` console script (incl. `ngtui status`
  subcommand), the `.desktop` launcher, and the hicolor brand icon.
- **D-05:** **Paste-it-yourself drop-ins:** the Waybar `custom-nightguard.jsonc`,
  `style-nightguard.css`, and the Hyprland windowrule ship to `/usr/share/nightguard/`
  as copy-paste snippets with README instructions — **never auto-merged** into a
  stranger's configs (the installer that *does* merge stays author-facing, Phase-12 D-07/D-08).
- **D-06:** Build via the idiomatic **`python-wheel` PKGBUILD** (hatchling wheel from
  the repo). Installs **nothing** root-owned or `0600`. The trust stack is declared as
  `optdepends` + an `.install` post-install message that points at the drop-ins and the
  `NIGHTGUARD_STACK_DIR` requirement. The sudoers entry stays a **manual, reviewed** step
  (never touched by the package).
- **D-07:** Install hooks refresh caches: `gtk-update-icon-cache` + `update-desktop-database`
  (mirrors the Phase-12 installer's cache refresh).

### Fail-loud surface (SC3 / SC4)
- **D-08:** **Interactive `ngtui` startup** fails loud: if the trust stack is unreachable,
  hard-exit with an actionable **stderr** message (`set NIGHTGUARD_STACK_DIR=…`, README
  pointer) — not a cryptic failure at commit time. README documents `environment.d` for
  the persistent stack path.
- **D-09:** The key-less **`ngtui status --json`** Waybar path keeps its locked behavior:
  **silent fail-closed** to `{"text":"○ —","class":"unavailable"}` exit 0 (a bar must
  never spew errors). This split (loud TUI / quiet bar) is deliberate.
- **D-10:** No packaged launcher/autostart surface can loosen the curfew without the
  `sudo` prompt; the packaged status reader stays key-less/unprivileged.

### Claude's Discretion (recommended defaults — not locked; confirm at plan time)
- **AUR package name:** recommend **`nightguard-control`** (`provides`/console script `ngtui`).
- **Build source:** recommend building from a **git release tag** (versioned tarball) —
  idiomatic AUR — rather than an untagged checkout. Requires cutting a `v2.1`-era tag.
- **README location:** recommend a **top-level `README.md`** carrying the publish/install
  story; the drop-in paste steps can live there and/or in the `.install` message.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/ROADMAP.md` §"Phase 13: Autostart + AUR Packaging" — goal + the 5 success criteria (SC1–SC5)
- `.planning/REQUIREMENTS.md` — **DESK-05**, **DESK-06**, and the **PORT-02** anti-vendoring invariant (Non-Goals table)
- `.planning/PROJECT.md` §"Constraints" / §"Key Decisions" — the single-trust-stack + key-less-status invariants

### Phase-12 artifacts this phase packages (the substrate)
- `packaging/omarchy/nightguard.desktop` — launcher (`xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui`)
- `packaging/omarchy/icons/nightguard.svg` — canonical brand icon (Ceramic Night; = `src/assets/logo.svg`)
- `packaging/omarchy/waybar/custom-nightguard.jsonc` + `style-nightguard.css` — the module drop-ins
- `packaging/omarchy/hypr/nightguard.windowrule.conf` — the float windowrule drop-in
- `packaging/omarchy/bin/ngtui-menu` — right-click read-only menu
- `packaging/omarchy/install.sh` — the **author-facing** merge installer (Phase-12 D-07/D-08 scope fence; the publish path is this phase, and does NOT auto-merge)
- `ngtui/pyproject.toml` — hatchling wheel, `requires-python >=3.11`, `dependencies = ["textual==8.2.7"]`, `[project.scripts] ngtui = "ngtui.__main__:main"`
- `.planning/phases/12-launcher-waybar-presence/12-CONTEXT.md` §D-06/D-07/D-08 — the immediate-now vs publish-later split that this phase completes

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ngtui/pyproject.toml`: already a valid hatchling wheel with a `ngtui` entry point — the PKGBUILD builds from this; **no restructure needed**, only a build/package wrapper.
- `packaging/omarchy/*`: every artifact the package must install/ship already exists and is human-verified live — Phase 13 relocates/documents them, it does not author new UI.
- `packaging/omarchy/install.sh` cache-refresh block (`gtk-update-icon-cache -f -t`, `update-desktop-database`): the pattern to reuse in the PKGBUILD `.install` hooks (D-07).

### Established Patterns
- **Trust-stack resolution:** the backend resolves the stack via env/hardcoded defaults under a scrubbed `env -i`; the fail-loud check (D-08) belongs at interactive startup, mirroring how `ngtui status --json` already fails closed (Phase 11 DESK-02).
- **Never-clobber principle:** the Phase-12 installer is marker-guarded/backup-first for the *author*; the publish package must go further and **never touch** user configs — drop-ins only (D-05).

### Integration Points
- PKGBUILD → the `ngtui` wheel + `packaging/omarchy/` artifacts (installed vs `/usr/share/nightguard/` drop-ins).
- `.install` message → `NIGHTGUARD_STACK_DIR` / `environment.d` guidance + drop-in paste pointers.
- Interactive `ngtui` startup → new fail-loud guard (D-08); waybar status path unchanged (D-09).

</code_context>

<specifics>
## Specific Ideas

- The loud/quiet split is a hard design intent: **interactive TUI = loud stderr abort**,
  **waybar `--json` = silent `unavailable` exit 0**. Do not unify them.
- Omarchy-native flavor preferred (Hyprland `exec-once` over systemd) for the opt-in
  window autostart.

</specifics>

<deferred>
## Deferred Ideas

- **Grace-as-action** (`sudo`-gated grace from the TUI/menu) — needs a
  `nightguard_ctl.py grace` command first (Phase 10 D-11 deferral / v3.0 candidate). Not this phase.
- **Offline StayFree blocklist import** (TRAK) — parked v2.0 candidate, future milestone.
- **Nyquist backfill for phases 6/7/7.1**, **browser-policy root-lock**, **ROOT-02 watchdog wording** — carried v2.0 tech-debt, not packaging work.

</deferred>

---

*Phase: 13-autostart-aur-packaging*
*Context gathered: 2026-07-04*
