# Phase 12: Launcher + Waybar Presence - Context

**Gathered:** 2026-07-03
**Status:** Ready for planning

> ⚠️ **Discussion note:** The user selected "discuss all areas" but stepped away
> before answering. Per the discuss-phase timeout protocol, the decisions below are
> **Claude's best-judgment defaults**, each grounded in the locked roadmap criteria
> and the live-system scout. **D-01/D-02 (icon concept + build) are the most
> user-owned and are flagged UNCONFIRMED** — the user should confirm or override
> before/at planning. The rest are defensible technical defaults but remain open to
> override.

<domain>
## Phase Boundary

Make Nightguard a **first-class omarchy desktop surface** — packaging/integration only,
**no new editing features**. Two deliverables:

1. **Launcher:** a brand-iconed `nightguard.desktop` that opens `ngtui` in a **floating,
   centered terminal window** (`xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui`,
   `Terminal=false`), enforced by a Hyprland windowrule matching the stable
   `org.omarchy.ngtui` app-id/class (**not title**). Appears in wofi/walker.
2. **Waybar presence:** a `custom/nightguard` module showing live curfew status
   (lock glyph + tokens, colored by state), sourced key-lessly from `ngtui status --json`;
   **left-click** opens/focuses the floating TUI; **right-click** shows a **read-only**
   status/actions menu; the bar **refreshes instantly** after a commit via a `SIGRTMIN+N`
   signal push wired into `backend.commit()`.

**Load-bearing invariants (from prior phases — NOT re-decided):**
- **A window, never a lever.** No launcher/bar surface may loosen the curfew. The
  right-click menu is strictly read-only (verdict / tokens / grace / open-actions).
- **The inline-`sudo` commit needs a real PTY** → the launcher must open a real terminal
  (`-e ngtui`), never a headless exec.
- **`ngtui status --json` is key-less, non-blocking, fail-closed** (Phase 11, DESK-02) —
  it is the ONLY data source the bar exec touches (no `sudo`, no NTP, no key).

**Out of scope:** autostart / login pin (DESK-05 → Phase 13); AUR PKGBUILD + README
install path (DESK-06 → Phase 13); any new curfew-editing capability; granting grace.
</domain>

<decisions>
## Implementation Decisions

### Brand icon (DESK-04) — ✅ CONFIRMED by user 2026-07-03
- **D-01 (CONFIRMED):** Concept = **a crescent moon on a rounded-square app tile.**
  - **Background:** a rounded-corner square app-icon tile (the standard app-icon shape).
  - **Foreground (moon, on top):** a **crescent** formed by a full circle with a **smaller
    circular cut removed from its bottom part** (big circle minus an offset smaller circle
    → crescent). The moon sits on top of the rounded tile.
  - Must still read at 16px monochrome first; the rounded tile + crescent silhouette is the
    at-a-glance mark. **Own-brand only — no borrowed logos.** Exact geometry (tile radius,
    circle radii, cut offset, Moonlit-Indigo fills) is iterable — nail concrete coordinates
    in the icon-authoring task; user can tweak after.
- **D-02 (CONFIRMED):** Claude **authors a real hand-coded SVG source now** (per D-01) and
  rasterizes the hicolor PNG sizes (16→512) this phase — a real final icon, iterable later,
  no external tool/asset dependency.
- **D-03:** Icon installs into the user hicolor theme
  (`~/.local/share/icons/hicolor/<size>/apps/org.omarchy.ngtui.png` + a scalable SVG),
  `.desktop` `Icon=org.omarchy.ngtui`; install refreshes caches
  (`gtk-update-icon-cache`) so it **appears immediately, not only after relogin** (SC-2).

### Right-click read-only menu (BAR-03)
- **D-04:** Mechanism = a small **wofi/walker `dmenu`-style popup script** (omarchy-idiomatic
  — wofi/walker already back the launcher). The script reads `ngtui status --json`
  (key-less) and renders **non-selectable header lines** (verdict, tokens left, grace
  remaining) plus **selectable actions**: "Open editor" and "Open status". Selecting an
  action runs the same open-or-focus command as left-click. **No loosening action exists in
  the menu** ("a window, never a lever"). Exact tool (wofi vs walker `--dmenu`) is
  researcher-confirmable; the *read-only + open-actions* shape is fixed.
- **D-05:** The bar's **hover tooltip** stays the `ngtui status` `tooltip` field (already
  emitted). The right-click menu is the richer, actionable surface.

### Install target (immediate-now vs publish-later split)
- **D-06:** The repo ships **canonical artifacts**: `nightguard.desktop`, icon
  sources/PNGs, a `custom/nightguard` Waybar module JSON snippet, a Hyprland windowrule
  snippet, the right-click menu script, and the signal-refresh wiring.
- **D-07:** This phase provides an **idempotent author-facing installer** that, for
  immediate effect on the author's live box (SC-1/SC-2/SC-3 "appears immediately"):
  installs the `.desktop` + icon into `~/.local/share/{applications,icons/hicolor}` (with
  cache refresh), and **merges** the Waybar module + Hyprland windowrule into the live
  `~/.config/waybar/config.jsonc` and `~/.config/hypr/*.conf`. Because these live configs
  are **outside the repo** and hand-editable (scouted: `config.jsonc` is a plain file, not
  omarchy-symlinked), the merge MUST be **idempotent and back up first** (re-running never
  duplicates the module; a marker/guard comment delimits the injected block). This is an
  outward, hard-to-reverse edit to the author's system — executor treats it as such.
- **D-08:** The **publish path (drop-in snippets + README paste instructions)** is
  **deferred to Phase 13** (DESK-06 / PKGBUILD) — a Phase-12 scope fence, not a deliverable.
  Phase 12's job is the artifacts + the author-immediate install; Phase 13 packages the same
  artifacts without clobbering arbitrary users' configs. (Scope fence recorded in Plan 05.)

### Bar appearance (BAR-01)
- **D-09:** **State color = fixed semantic classes, not live theme.** `status.py` already
  emits a stable `class` per verdict (`locked` / `grace_active` / `outside_curfew` /
  `clock_tamper` / `offline_blocked` / `unavailable`) precisely so a Waybar stylesheet can
  target `#custom-nightguard.locked` etc. A curfew status is a **danger signal** — a fixed
  red/amber/green semantic mapping stays legible and reinforces "at-a-glance" state, where
  live-theming the alert color would fight that. Ship a `style.css` snippet keyed on the
  emitted classes (tweakable). *(Unlike the TUI, which live-themes per Phase-10 D-04/05 —
  intentional divergence: the TUI is an editor surface, the bar is a status light.)*
- **D-10:** **Text verbosity = keep `status.py` as-built** (`text = "{glyph} {left}"` —
  verdict glyph + remaining-token count, always). Tokens-always reinforces the "tokens are
  precious" core value. **Grace remaining stays in the tooltip/menu, NOT the bar text** — a
  poll-interval bar cannot show a smooth live countdown without jitter, and the signal push
  (D-11) is commit-triggered, not per-second. Minimal/zero change to `status.py`.

### Signal-refresh (BAR-04)
- **D-11:** Wire an instant post-commit bar refresh: `backend.commit()`, on a **successful**
  commit, sends `SIGRTMIN+N` to Waybar (e.g. `pkill --signal SIGRTMIN+N waybar` /
  `pkill -RTMIN+N waybar`), and the `custom/nightguard` module declares the matching
  `"signal": N`. **Scouted free slot:** signals 7/8/9/10 are already taken in the live
  Waybar config — researcher/planner **confirms a free slot** (e.g. 11) against the live
  config at plan time before hardcoding. Fire only on success; never let a failed/refused
  commit or the signal itself affect the sudo/commit result.

### Claude's Discretion
- Exact windowrule syntax + size/centering values (match the scouted
  `windowrule = float on, match:class ^(...)$` idiom; app-id/class `org.omarchy.ngtui`).
- Whether `xdg-terminal-exec --app-id=` reliably maps to Alacritty's app-id/class on
  Wayland (default terminal is **Alacritty**) — **researcher must verify** the app-id
  actually lands on the window so the windowrule matches; fall back to Alacritty's
  `--class` if `--app-id` doesn't propagate.
- Exact free `SIGRTMIN` slot number (D-11), the menu tool (wofi vs walker), and the
  open-or-focus command (reuse `omarchy-launch-or-focus-tui`-style helper vs custom).
- Icon glyph/geometry details within the chosen concept (D-01).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### This phase's contract
- `.planning/ROADMAP.md` §"Phase 12: Launcher + Waybar Presence" — goal + 5 success
  criteria (app-id/windowrule, icon, module, click behavior, signal refresh).
- `.planning/REQUIREMENTS.md` — DESK-03, DESK-04, BAR-01, BAR-02, BAR-03, BAR-04.

### The substrate this phase consumes (Phase 11 output — in this repo)
- `ngtui/ngtui/status.py` — the key-less Waybar status builder; emits stable
  `class`/`text`/`tooltip`. The bar's data source + CSS class contract (D-09/D-10).
- `ngtui/ngtui/__main__.py` — `ngtui status [--json]` router (fail-closed, exit 0) + the
  bare-`ngtui` TTY guard (why the launcher must be a real terminal).
- `ngtui/ngtui/backend.py` — `commit()` (D-11 signal hook goes here, on success only);
  `STACK_DIR`/`CTL_SCRIPT` bootstrap; the sudo-PTY commit path that must survive launch.
- `ngtui/pyproject.toml` — `[project.scripts] ngtui = ngtui.__main__:main` (the global
  command the `.desktop`/module/menu invoke).

### Prior decisions this phase inherits
- `.planning/phases/10-linux-app-omarchy-tui-was-tauri-port/10-CONTEXT.md` — thin-client /
  no-key / sudo-commit model; live theming (D-04/05) that the bar intentionally diverges from.
- `.planning/PROJECT.md` §"Active (v2.1)" + §"Key Decisions" — DESK-01/02 (Phase 11),
  "a window, never a lever" invariant, key-less non-blocking status path.

### Live-system artifacts the executor touches (outside the repo — author's box)
- `~/.config/waybar/config.jsonc` — plain hand-editable file; signals 7/8/9/10 taken;
  existing `custom/*` modules show the `format`/`on-click`/`on-click-right`/`signal`/
  `interval` idiom to mirror.
- `~/.config/waybar/style.css` — where the semantic state classes (D-09) are styled.
- `~/.config/hypr/hyprland.conf` — existing float pattern
  `windowrule = float on, match:class ^(TodQuickAdd)$` (+ `center on`, `size ...`) to mirror.
- `~/.local/share/icons/hicolor/<size>/apps/` and `~/.local/share/applications/` — icon +
  `.desktop` install targets (hicolor size dirs already exist).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ngtui status --json` (Phase 11): drop-in, key-less, non-blocking, fail-closed data
  source for both the bar `exec` and the right-click menu script — no new backend needed.
- `status.py` stable `class` names: the CSS contract for the bar stylesheet already exists
  — the phase writes a `style.css` keyed on them, no `status.py` change (D-09).
- `backend.commit()`: the single, already-central commit seam — the ONLY place to add the
  post-commit signal push (D-11), fired on success.

### Established Patterns
- **Omarchy Waybar module idiom:** `custom/*` with `format` + `on-click` + `on-click-right`
  + `signal` + `interval`; existing modules (`custom/omarchy`, `custom/update`) are the
  template (e.g. `on-click: omarchy-launch-floating-terminal-with-presentation ...`).
- **Hyprland float rule idiom:** `windowrule = float on, match:class ^(...)$` on a stable
  class (never title) — exactly what SC-1 mandates for `org.omarchy.ngtui`.
- **`xdg-terminal-exec`** is the omarchy terminal launcher (default → Alacritty); already
  used in keybindings — the `.desktop` `Exec` reuses it.

### Integration Points
- `.desktop` `Exec` → `xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui`.
- Waybar `custom/nightguard.exec` → `ngtui status --json`; `on-click` → open/focus TUI;
  `on-click-right` → the read-only menu script; `signal` → matches `backend.commit()`'s slot.
- `backend.commit()` success → `pkill -RTMIN+N waybar` (D-11).
</code_context>

<specifics>
## Specific Ideas

- The bar is a **status light**, not a control: glyph encodes verdict, count encodes the
  precious weekly-token budget, semantic color encodes danger — and the ONLY write action
  reachable is "open the (friction-gated) editor."
- The right-click menu deliberately mirrors the read-only surface (verdict / tokens / grace)
  and offers only *open* actions — the anti-impulse guarantee holds even from the bar.
- Icon must read at 16px monochrome first; color/detail second.
</specifics>

<deferred>
## Deferred Ideas

- **Autostart / login pin (DESK-05)** — Phase 13 (autostarts the *module*, not the TUI window).
- **AUR PKGBUILD + README install path (DESK-06)** — Phase 13; the publish-safe drop-in
  snippet path (never clobbering arbitrary user configs) lives there, consuming Phase 12's
  artifacts.
- **Grace-as-action (`sudo`-gated "+8")** — still display-only; restoring the Windows "+8"
  needs a `nightguard_ctl.py grace` command first (Phase 10 D-11 deferral). Not this phase,
  and never a bar action.
- **Live-themed bar colors** — considered and rejected for the status module (D-09); could
  revisit if a future theme-aware semantic palette is wanted.

### Reviewed Todos (not folded)
None — no pending todos matched this phase.
</deferred>

---

*Phase: 12-launcher-waybar-presence*
*Context gathered: 2026-07-03*
