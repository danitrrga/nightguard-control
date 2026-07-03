# Phase 12: Launcher + Waybar Presence — Research

**Researched:** 2026-07-03
**Domain:** omarchy desktop integration (Hyprland windowrules, Waybar custom modules, freedesktop `.desktop`/hicolor icons, walker dmenu, SVG icon authoring)
**Confidence:** HIGH (every load-bearing answer verified live against the author's box; two items flagged as execution-time checks)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 (CONFIRMED):** Icon concept = a **crescent moon on a rounded-square app tile**. Background = rounded-corner square app-icon tile. Foreground = a crescent (full circle minus a smaller offset circle removed from its bottom part), sitting on top. Must read at 16px monochrome first. Own-brand only, no borrowed logos. Exact geometry iterable.
- **D-02 (CONFIRMED):** Claude **hand-authors a real SVG source now** (per D-01) and rasterizes hicolor PNG sizes 16→512 this phase. No external tool/asset dependency.
- **D-03:** Icon installs into the user hicolor theme (`~/.local/share/icons/hicolor/<size>/apps/org.omarchy.ngtui.png` + a scalable SVG); `.desktop` `Icon=org.omarchy.ngtui`; install refreshes caches so it appears immediately, not only after relogin (SC-2).
- **D-04:** Right-click menu = a small **wofi/walker `dmenu`-style popup script** reading `ngtui status --json` (key-less); renders non-selectable header lines (verdict, tokens left, grace remaining) + selectable actions "Open editor" / "Open status". Selecting an action runs the same open-or-focus command as left-click. **No loosening action exists.**
- **D-05:** Bar hover tooltip stays the `ngtui status` `tooltip` field. The right-click menu is the richer, actionable surface.
- **D-06:** Repo ships canonical artifacts: `nightguard.desktop`, icon sources/PNGs, a `custom/nightguard` Waybar module snippet, a Hyprland windowrule snippet, the right-click menu script, the signal-refresh wiring.
- **D-07:** This phase provides an **idempotent author-facing installer** that installs `.desktop` + icon into `~/.local/share/{applications,icons/hicolor}` (with cache refresh) and **merges** the Waybar module + Hyprland windowrule into the live `~/.config/waybar/config.jsonc` and `~/.config/hypr/*.conf`. Merge MUST be idempotent + back up first (marker/guard comment delimits the injected block; re-running never duplicates).
- **D-08:** Publish path (drop-in snippets + README) is deferred to Phase 13 (DESK-06).
- **D-09:** State color = fixed semantic classes, not live theme. Ship a `style.css` snippet keyed on `status.py`'s emitted classes (`locked` / `grace_active` / `outside_curfew` / `clock_tamper` / `offline_blocked` / `unavailable`). Bar = status light, not editor surface (intentional divergence from the TUI's live theming).
- **D-10:** Text verbosity = keep `status.py` as-built (`text = "{glyph} {left}"`). Grace stays in tooltip/menu, NOT bar text. Minimal/zero change to `status.py`.
- **D-11:** Wire an instant post-commit bar refresh: `backend.commit()`, on a **successful** commit only, sends `SIGRTMIN+N` to Waybar; the module declares matching `"signal": N`. Fire only on success; never let the signal affect the commit result. Free slot to be confirmed live (context noted 7/8/9/10 taken).

### Claude's Discretion
- Exact windowrule syntax + size/centering values (match the scouted idiom; app-id/class `org.omarchy.ngtui`).
- Whether `xdg-terminal-exec --app-id=` reliably maps to Alacritty's app-id on Wayland — **researcher must verify** (done below); fall back to `--class` if not.
- Exact free `SIGRTMIN` slot number (D-11), the menu tool (wofi vs walker), and the open-or-focus command (reuse an `omarchy-launch-or-focus-*` helper vs custom).
- Icon glyph/geometry details within the chosen concept (D-01).

### Deferred Ideas (OUT OF SCOPE)
- Autostart / login pin (DESK-05) → Phase 13.
- AUR PKGBUILD + README install path (DESK-06) → Phase 13.
- Grace-as-action (`sudo`-gated "+8") — display-only; never a bar action.
- Live-themed bar colors — considered and rejected for the status module (D-09).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DESK-03 | `.desktop` opens `ngtui` in a floating terminal (`xdg-terminal-exec … -e ngtui`, `Terminal=false`), appears in walker, floating enforced by a Hyprland windowrule on a stable app-id/class; inline-`sudo` still works (real terminal) | app-id propagation VERIFIED (§Pitfall 1 / Pattern 1); windowrule idiom scouted (Pattern 2); PTY preserved because `-e ngtui` opens a real Alacritty |
| DESK-04 | Custom own-brand icon installed into the hicolor theme, shown by launcher + Waybar | SVG crescent technique + rasterize + install/cache commands (Pattern 5, Code Examples §Icon) |
| BAR-01 | `custom/nightguard` module: lock glyph + tokens, colored by state, key-less from `ngtui status --json`, non-blocking, fail-closed | module JSON idiom scouted (Pattern 3); `status.py` contract unchanged (D-09/D-10); style.css keyed on emitted classes |
| BAR-02 | Left-click opens/focuses the TUI (floating terminal) | **reuse `omarchy-launch-or-focus-tui ngtui`** — VERIFIED it sets app_id `org.omarchy.ngtui` and focuses an existing window (Pattern 4) |
| BAR-03 | Right-click read-only menu (verdict, tokens, grace, "open" actions) — **no loosening action** | **walker `--dmenu`** (wofi absent); read-only header + open-actions script (Pattern 6, Code Examples §Menu) |
| BAR-04 | Bar refreshes instantly after a commit (`SIGRTMIN+N`), not just polling | **free slot = SIGRTMIN+11** (7/8/9/10 confirmed taken live); `pkill -RTMIN+11 waybar` wired into `backend.commit()` on success only (Pattern 7) |
</phase_requirements>

## Summary

This is a **packaging/integration phase with a heavy live-runtime-state footprint** — almost no new logic, but a set of freedesktop/omarchy artifacts plus an idempotent installer that mutates the author's live Hyprland + Waybar configs. Every hard question the plan needs has been answered against the live box, and the omarchy ecosystem already supplies most of the machinery: the app-id→windowrule dance, the open-or-focus helper, the custom-module idiom, and the signal-refresh mechanism are all established patterns to mirror rather than invent.

The single most important verified fact: **`xdg-terminal-exec --app-id=org.omarchy.ngtui` DOES propagate to Alacritty's Wayland `app_id`.** The author's `~/.local/share/applications/Alacritty.desktop` carries `X-TerminalArgAppId=--class=`, which xdg-terminal-exec reads and translates into `alacritty --class=org.omarchy.ngtui`; `alacritty --class <general>` sets the Wayland app_id. So the Hyprland `match:class ^(org\.omarchy\.ngtui)$` rule will match — no `--class` fallback needed (but keep it documented as the contingency).

**Primary recommendation:** Reuse omarchy's own primitives verbatim — `omarchy-launch-or-focus-tui ngtui` for open-or-focus (left-click + menu actions), `xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui` for the `.desktop` `Exec`, `walker --dmenu` for the read-only menu, `rsvg-convert` for rasterizing the hand-coded SVG, and `SIGRTMIN+11` for the commit-refresh signal. The only genuinely delicate engineering is the **idempotent, comment-preserving text merge into `config.jsonc`** (JSONC ≠ JSON) and the **backup-first mutation of live configs** — handle both as marker-guarded text injection, never a JSON round-trip. **Execution prerequisite flagged: `ngtui` is NOT currently on PATH** (Phase 11 installed `~/.local/bin/ngtui` via `uv tool install`, but it is absent now) — the plan must (re)install it before the live install/verify steps.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Launcher entry (`.desktop`) | Desktop / freedesktop (XDG) | — | App discovery + icon binding is an XDG concern; walker reads `~/.local/share/applications` |
| Floating-window enforcement | Compositor (Hyprland) | — | Only Hyprland can float/center/size a window; keyed on the stable app_id, never title |
| Terminal + PTY host | Terminal emulator (Alacritty) via `xdg-terminal-exec` | — | The inline-`sudo` commit needs a real PTY; only a real terminal provides it |
| Bar status display | Waybar `custom/*` module | `ngtui status --json` (data) | Waybar owns the bar pixel; the module's `exec` sources key-less JSON from the ngtui reader |
| Status data / verdict | ngtui reader (Phase 11) | Python trust stack | Already built, key-less, fail-closed; this phase adds NO new data path |
| Open-or-focus action | omarchy helper (`omarchy-launch-or-focus-tui`) → Hyprland dispatch | — | Reuse existing hyprctl-based focus/launch; no custom script |
| Read-only menu | walker (`--dmenu`) | `ngtui status --json` | walker is the installed launcher/dmenu; menu is a thin presentation of key-less status |
| Commit→bar refresh | ngtui `backend.commit()` (signal emit) → Waybar (`signal`) | — | The commit seam is the single place that knows a commit succeeded; `pkill -RTMIN+N` is the push |
| Brand icon | hicolor icon theme (raster + scalable) | rsvg-convert (build) | Icons live in the XDG icon theme; rsvg rasterizes the hand-coded SVG at build time |
| Live-config install | author-facing installer script | backups + markers | Outward, hard-to-reverse edits to `~/.config/{waybar,hypr}` — idempotent, backup-first |

## Standard Stack

This phase installs **no new packages**. Every tool it depends on is a system binary already present on the target box (verified live). The "stack" here is the omarchy/freedesktop tool inventory.

### Core (verified present on the live box)
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `xdg-terminal-exec` | freedesktop reference impl (`/usr/bin`) | Resolves the default terminal (Alacritty) + forwards `--app-id`/`-e` | omarchy's canonical TUI launcher; already used by `omarchy-launch-tui` [VERIFIED: live box] |
| `alacritty` | `0.17.0` | Terminal host; `--class` sets Wayland app_id | omarchy default terminal (`xdg-terminals.list` → `Alacritty.desktop`) [VERIFIED: live box] |
| Hyprland (`hyprctl`) | running session | `windowrule` float/center/size; `dispatch focuswindow` | The compositor; float rules keyed on app_id [VERIFIED: live box] |
| Waybar | running (pid live) | `custom/nightguard` module host | omarchy bar; supports `custom/*` with `exec`/`signal`/`interval`/`on-click*` [VERIFIED: live config] |
| `walker` | `2.16.2` | `--dmenu` read-only menu | omarchy launcher (wofi/rofi/fuzzel all ABSENT) [VERIFIED: live box] |
| `rsvg-convert` | `2.62.3` | SVG → hicolor PNG rasterizer | Crisp cairo rasterization; present. `magick`/`convert` (ImageMagick) also present as fallback [VERIFIED: live box] |
| `gtk-update-icon-cache` | present | Refresh icon cache so entry/icon appear without relogin | Supports `-t/--ignore-theme-index` (user hicolor dir has NO `index.theme`) [VERIFIED: live box] |
| `update-desktop-database` | present | Refresh the `.desktop` MIME/app cache | Standard XDG cache refresh for `~/.local/share/applications` [VERIFIED: live box] |
| omarchy helper bin (`~/.local/share/omarchy/bin`) | on Waybar PATH | `omarchy-launch-or-focus-tui`, `omarchy-launch-tui`, `omarchy-launch-or-focus` | Reuse the exact open-or-focus machinery [VERIFIED: live box] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `walker --dmenu` | wofi / rofi / fuzzel | **None installed** — walker is the only dmenu on this box. Do not introduce a new dep. |
| `rsvg-convert` | `magick`/`convert` (ImageMagick, present) | rsvg gives cleaner small-size AA for SVG; ImageMagick is the fallback if a specific effect fails |
| explicit `float/center/size` windowrule | omarchy `tag +floating-window` | The tag reuses omarchy's `float+center+size 875 600` for all `org.omarchy.*` TUIs (visual consistency) but depends on tag-rule evaluation ordering — flag as execution-time check |
| bare `ngtui status --json` in module `exec` | absolute `~/.local/bin/ngtui …` | Waybar's PATH includes `~/.local/bin` + `~/.local/share/omarchy/bin` (verified) → bare `ngtui` resolves once installed. Bare is idiomatic (all omarchy modules use bare commands). |

**Installation:** No package installs. **Execution prerequisite:** `ngtui` must be on PATH — currently MISSING (see Environment Availability). (Re)install with `uv tool install --python 3.14 .` from `ngtui/` per Phase 11.

## Package Legitimacy Audit

**Not applicable — this phase installs zero external packages.** All tools are pre-existing system binaries verified present on the target box (see Standard Stack). The only "install" is the project's own `ngtui` (first-party, already built in Phase 11) via `uv tool install`, and the phase's own hand-authored artifacts (`.desktop`, SVG, module snippet, menu/installer scripts). slopcheck / registry verification is moot — no npm/PyPI/crates dependency is introduced.

## Architecture Patterns

### System Architecture Diagram

```
                       ┌─────────────────────────────────────────────┐
   walker (app list) ──►  nightguard.desktop                          │
                       │   Exec=xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui
                       │   Icon=org.omarchy.ngtui   Terminal=false    │
                       └───────────────┬─────────────────────────────┘
                                       ▼
              xdg-terminal-exec (reads Alacritty.desktop:X-TerminalArgAppId=--class=)
                                       ▼
              alacritty --class=org.omarchy.ngtui -e ngtui   ── Wayland app_id set ──►
                                       ▼
   Hyprland windowrule match:class ^(org\.omarchy\.ngtui)$  → float + center + size
                                       ▼
              ngtui TUI (real PTY → inline sudo commit works)


   Waybar bar
   ┌───────────────────────────────────────────────────────────────────┐
   │ custom/nightguard                                                   │
   │   exec:    ngtui status --json   (key-less, non-blocking, exit 0)   │
   │   format:  {}  (glyph + tokens)   tooltip: {tooltip}   class: <verdict>
   │   interval: 30      signal: 11                                       │
   │   on-click:        omarchy-launch-or-focus-tui ngtui   ── open/focus ┼─► (same app_id path above)
   │   on-click-right:  ngtui-menu  ── walker --dmenu (read-only) ────────┤
   └───────────────────────────────▲───────────────────────────────────┘
                                    │ SIGRTMIN+11 (pkill -RTMIN+11 waybar)
                                    │  ── refresh on SUCCESSFUL commit only
              ngtui backend.commit() ── sudo commit returncode==0 ──┘

   style.css:  #custom-nightguard.locked / .grace_active / .outside_curfew /
               .clock_tamper / .offline_blocked / .unavailable   (fixed semantic colors)
```

### Recommended Artifact Structure (in-repo canonical artifacts, D-06)
```
packaging/omarchy/                 # new dir (repo has no packaging/ yet)
├── nightguard.desktop             # Exec/Icon/Terminal=false
├── icons/
│   ├── nightguard.svg             # hand-coded crescent-on-tile source (viewBox 0 0 512 512)
│   └── (generated PNGs are built by the installer, not committed — or commit a set)
├── waybar/
│   ├── custom-nightguard.jsonc    # the module object snippet (with markers)
│   └── style-nightguard.css       # semantic-class rules snippet (with markers)
├── hypr/
│   └── nightguard.windowrule.conf # the 3-line float/center/size snippet (with markers)
├── bin/
│   └── ngtui-menu                 # walker --dmenu read-only right-click menu
└── install.sh                     # idempotent, backup-first author-facing installer (D-07)
```

### Pattern 1: app-id propagation through xdg-terminal-exec → Alacritty (DESK-03, SC-1)
**What:** `xdg-terminal-exec --app-id=X` reads the resolved terminal's `.desktop` `X-TerminalArgAppId` key and prepends the corresponding flag to the terminal argv. The author's `Alacritty.desktop` has `X-TerminalArgAppId=--class=` → xdg-terminal-exec emits `alacritty --class=X …`; alacritty sets the Wayland `app_id` to `X`. **Verified live.** [VERIFIED: live box — `~/.local/share/applications/Alacritty.desktop` line 15 + xdg-terminal-exec §1415-1425]
**When to use:** Always for the `.desktop` `Exec`.
**Fallback (if the desktop entry ever lacks the key, e.g. a fresh omarchy or different terminal):** `Exec=alacritty --class=org.omarchy.ngtui -e ngtui` (direct, terminal-specific). Keep documented but not needed on this box.

### Pattern 2: Hyprland float rule keyed on app_id (never title)
**What:** Mirror the scouted `TodQuickAdd` idiom in the author's **personal** `~/.config/hypr/hyprland.conf` (the "Add any other personal Hyprland configuration below" section):
```
windowrule = float on,   match:class ^(org\.omarchy\.ngtui)$
windowrule = center on,  match:class ^(org\.omarchy\.ngtui)$
windowrule = size 875 600, match:class ^(org\.omarchy\.ngtui)$
```
**Omarchy-native alternative (one line):** omarchy's `default/hypr/apps/system.conf` already floats/centers/sizes (875×600) every window tagged `floating-window`, and its match list is exactly `org.omarchy.btop|…|org.omarchy.terminal|…` — but **`org.omarchy.ngtui` is NOT in that list.** You can inherit that behavior with:
```
windowrule = tag +floating-window, match:class ^(org\.omarchy\.ngtui)$
```
Tradeoff: the tag approach is DRY and matches every other omarchy TUI, but depends on Hyprland applying the `float/center/size` tag-rules (defined earlier, in the sourced default) to a window tagged by a rule defined later in the personal file. **Flag as an execution-time check** — if the tag doesn't take, use the explicit 3-line form. Recommend shipping the **explicit 3-line form** as the canonical snippet (self-contained, order-independent), size `875 600` to match omarchy TUIs.
[VERIFIED: live box — hyprland.conf TodQuickAdd rules + omarchy system.conf floating-window tag list]

### Pattern 3: Waybar `custom/*` module idiom
**What:** Mirror `custom/update` (the closest analog — has `exec`+`signal`+`interval`+`on-click`+`tooltip`). Return-type is a JSON object (`ngtui status --json` emits `{text,tooltip,class}` on one line), so use `"return-type": "json"` and `"format": "{}"` (or `"{text}"`). The `class` field auto-applies as the CSS class `#custom-nightguard.<class>`.
[VERIFIED: live config — `custom/update`, `custom/weather` (return-type json), `custom/voxtype`]

### Pattern 4: open-or-focus via the existing omarchy helper (BAR-02)
**What:** `omarchy-launch-or-focus-tui ngtui` — REUSE, do not roll a custom script. It sets `APP_ID="org.omarchy.ngtui"`, greps `hyprctl clients -j` for a window whose class matches `\bngtui\b`, and either `hyprctl dispatch focuswindow address:…` (focus existing) or `omarchy-launch-tui ngtui` (which runs `xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui` under `setsid uwsm-app`). Same app_id path as the `.desktop`. Use this for the module `on-click` AND for the menu's "Open editor"/"Open status" actions.
[VERIFIED: live box — `omarchy-launch-or-focus-tui`, `omarchy-launch-or-focus`, `omarchy-launch-tui` script bodies]

### Pattern 5: hand-coded crescent SVG + hicolor rasterize + immediate cache refresh (DESK-04, D-01/02/03)
**Crescent technique (renders crisp at 16px):** a full circle with a smaller, offset circle **subtracted** — cleanest via an SVG `<mask>` (white keeps, black cuts). Author in a 512-viewBox and rasterize down; anti-aliasing is handled by rsvg. Keep the crescent thick (cut-circle radius ≈ 82% of the moon radius, offset ≈ 34% of the moon radius toward bottom-right) so the sliver survives at 16px. Rounded-square tile behind (rx ≈ 22% of side). See Code Examples §Icon for concrete coordinates.
**Rasterize (rsvg-convert):** loop sizes 16 32 48 64 128 256 512 → `~/.local/share/icons/hicolor/<S>x<S>/apps/org.omarchy.ngtui.png`; also copy the SVG to `hicolor/scalable/apps/org.omarchy.ngtui.svg` (**note: the `scalable/apps` dir does NOT exist yet — `mkdir -p` it**; the pixel dirs 16..512 all exist).
**Immediate visibility (SC-2):** `gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor` (`-t` skips the missing `index.theme`) + `update-desktop-database ~/.local/share/applications`. No relogin needed. Walker re-reads on next open.
[VERIFIED: live box — rsvg-convert 2.62.3, gtk-update-icon-cache `-t`, all hicolor pixel dirs present, NO scalable dir, NO user index.theme]

### Pattern 6: walker `--dmenu` read-only menu (BAR-03, D-04)
**What:** walker (2.16.2) is the only dmenu on the box. It reads newline-separated entries from stdin and prints the selected line to stdout; `-p/--placeholder` sets the prompt. Feed **header lines** (verdict / tokens / grace, parsed from `ngtui status --json` with a divider) followed by **action lines** ("Open editor", "Open status"). Because dmenu has no true "non-selectable" concept, the script simply **ignores any selection that isn't a known action** — the header lines are inert. No loosening action is ever emitted.
[VERIFIED: live box — `walker --help` shows `-d/--dmenu`, `-p/--placeholder`; wofi/rofi/fuzzel absent]

### Pattern 7: commit → instant bar refresh (BAR-04, D-11)
**What:** In `ngtui/ngtui/backend.py` `commit()`, after `subprocess.run([...])` returns, if `proc.returncode == 0` fire `pkill -RTMIN+11 waybar` (best-effort, never raises into the commit result). The module declares `"signal": 11`. **SIGRTMIN+11 is FREE** (live config uses 7=custom/update, 8=screenrecording, 9=idle, 10=notification-silencing; nothing uses 11). Waybar re-runs the module `exec` on that signal.
[VERIFIED: live config — signals 7/8/9/10 in use, 11 free; waybar running]

### Anti-Patterns to Avoid
- **Matching a windowrule on `title`** — titles are user/content-dependent; SC-1 mandates the stable app_id/class. Always `match:class ^(org\.omarchy\.ngtui)$`.
- **Parsing/round-tripping `config.jsonc` with `jq`/`json.load`** — both strip comments and reformat, corrupting the author's hand-maintained JSONC. Use marker-guarded **text** injection (Don't Hand-Roll / Pitfall 2).
- **A headless/detached launch** (`Exec` without `-e`, or `setsid … &` without a terminal) — kills the PTY the inline `sudo` needs. Always `-e ngtui` in a real terminal.
- **Firing the refresh signal on any commit** — only `returncode == 0`. A refused/failed commit must not flip the bar, and the signal must never change the commit's exit result.
- **Adding a loosening action to the right-click menu** — violates "a window, never a lever." Menu is read-only header + open actions only.
- **`gtk-update-icon-cache` without `-t`** — the user hicolor dir has no `index.theme`; the plain command errors. Use `-f -t`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Open-or-focus the TUI window | A custom hyprctl grep/focus script | `omarchy-launch-or-focus-tui ngtui` | Already exists, sets the right app_id, handles focus-vs-launch + uwsm scope [VERIFIED] |
| Set the Wayland app_id | A bespoke alacritty wrapper | `xdg-terminal-exec --app-id=org.omarchy.ngtui` (propagates via `X-TerminalArgAppId`) | The omarchy Alacritty.desktop already wires `--class=`; the reference impl forwards it [VERIFIED] |
| SVG → PNG at 7 sizes | Manual pixel art / a Node canvas script | `rsvg-convert -w S -h S in.svg -o out.png` in a size loop | cairo AA, one binary, deterministic [VERIFIED present] |
| Read-only status popup | A custom GTK/Qt window | `walker --dmenu` fed pre-rendered lines | The installed launcher; zero new deps [VERIFIED] |
| Float/center/size the window | Manual `hyprctl` dispatch after launch | Declarative `windowrule` on the app_id | Compositor applies it at map time, race-free [VERIFIED idiom] |
| Instant bar refresh | Polling at 1s (jitter, wakeups) | `pkill -RTMIN+11 waybar` on commit + `interval` as a slow safety net | Waybar's native signal mechanism; commit-triggered = zero idle cost [VERIFIED slot free] |
| Icon cache refresh | Relogin / restart the session | `gtk-update-icon-cache -f -t` + `update-desktop-database` | Immediate (SC-2), no session bounce [VERIFIED] |

**Key insight:** omarchy has already solved every desktop-integration sub-problem for its own TUIs (btop, bluetui, impala, wiremix all float via `org.omarchy.*` app_ids and launch via the same helpers). Phase 12 is "make ngtui look like a native omarchy TUI," which is 90% mirroring existing idioms and 10% the one thing omarchy does NOT do for you: idempotently merging your snippet into the author's live, comment-bearing configs.

## Runtime State Inventory

This phase mutates live, out-of-repo runtime state (D-07). A file-only view is insufficient — enumerate what the installer touches and what must be refreshed.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Live service config (Waybar) | `~/.config/waybar/config.jsonc` — plain hand-editable JSONC (NOT omarchy-symlinked); needs the `custom/nightguard` **object** added AND the module **name** added to a `modules-*` array. `~/.config/waybar/style.css` — needs the semantic-class rules appended. | Marker-guarded text merge, backup-first (D-07). After merge, reload Waybar so the new module loads: `pkill -SIGUSR2 waybar` (SIGUSR2 = config reload) or omarchy's restart helper. **Verify reload works (execution-time).** |
| Live service config (Hyprland) | `~/.config/hypr/hyprland.conf` — personal section (where `TodQuickAdd` rules live) needs the 3-line float/center/size block. Line-based, trivial to append with markers. | Marker-guarded append, backup-first. Hyprland auto-reloads config on file change (or `hyprctl reload`). |
| OS-registered state (XDG) | `~/.local/share/applications/nightguard.desktop` (new); `~/.local/share/icons/hicolor/<16..512>/apps/org.omarchy.ngtui.png` (new) + `scalable/apps/org.omarchy.ngtui.svg` (**scalable dir absent → mkdir -p**). | Install files + `gtk-update-icon-cache -f -t` + `update-desktop-database`. Idempotent (overwrite). |
| Installed package (PATH) | `ngtui` command — **currently MISSING from `~/.local/bin`** (Phase 11 installed it via `uv tool install`; absent now). Both the module `exec`, the `.desktop` `Exec`, and the menu depend on it resolving on the session PATH. | (Re)install `ngtui` (`uv tool install --python 3.14 .` from `ngtui/`) as a **prerequisite task** before any live-install/verify step. Waybar PATH already includes `~/.local/bin` (verified). |
| Secrets / env vars | None — this phase reads no key, adds no secret, changes no env var. `ngtui status --json` is key-less; `backend.commit()`'s signal push is a plain `pkill`. | None — verified by the key-less status path (Phase 11) and read-only surfaces. |
| Build artifacts | The committed hicolor PNGs (if the repo vendors them) become stale if the SVG source changes → regenerate on SVG edit. | Installer rasterizes from the SVG at install time (source of truth = SVG), so live install is never stale. |

**Canonical question — after every repo file is written, what runtime state still holds an old value?** (1) Waybar won't show the module until reloaded (SIGUSR2); (2) walker won't show the icon until `gtk-update-icon-cache`/`update-desktop-database` run; (3) the whole chain is dead until `ngtui` is back on PATH. All three are installer/prereq steps, not repo edits.

## Common Pitfalls

### Pitfall 1: `--app-id` silently dropped if the terminal desktop entry lacks `X-TerminalArgAppId`
**What goes wrong:** xdg-terminal-exec only forwards `--app-id` if the resolved terminal's `.desktop` defines `X-TerminalArgAppId` (or `TerminalArgAppId`). If it's absent, the value is silently discarded (script logs `debug "terminal entry has no TerminalArgAppId="` and prepends nothing) → the window keeps app_id `Alacritty` → the windowrule never matches → the TUI opens tiled, not floated.
**Why it happens:** The forwarding is data-driven from the terminal's desktop entry, not hardcoded.
**How to avoid:** VERIFIED the author's `~/.local/share/applications/Alacritty.desktop` HAS `X-TerminalArgAppId=--class=` → works. If the plan ever runs on a box where only `/usr/share/applications/Alacritty.desktop` exists (no `X-TerminalArg*` keys), fall back to `Exec=alacritty --class=org.omarchy.ngtui -e ngtui`.
**Warning signs:** `hyprctl clients -j | jq '.[].class'` shows `Alacritty` instead of `org.omarchy.ngtui` for the ngtui window.

### Pitfall 2: JSONC is not JSON — a JSON parser corrupts `config.jsonc`
**What goes wrong:** Feeding `config.jsonc` through `jq`/`python -m json.tool`/`json.load` strips every `//` comment and reformats the file, destroying the author's hand-maintained config on write.
**Why it happens:** Waybar uses JSONC (comments allowed); stdlib/`jq` are strict JSON.
**How to avoid:** Treat the file as **text**. Idempotent marker-guarded injection: (a) `grep` for a guard marker → if present, skip (idempotent); (b) `cp` to `config.jsonc.bak.<epoch>`; (c) inject the module **object** just before the final `}` inside a `// >>> nightguard (managed) >>>` … `// <<< nightguard <<<` block; (d) insert `"custom/nightguard",` into a chosen `modules-*` array via an anchored text edit (e.g. right after `"modules-right": [`), guarded by the same "already present?" check. Never round-trip.
**Warning signs:** comments vanish; diff shows the whole file reformatted.

### Pitfall 3: adding the module object but forgetting the `modules-*` membership
**What goes wrong:** The `custom/nightguard` definition is present but the module never renders — Waybar only shows modules listed in `modules-left/center/right`.
**Why it happens:** Two independent edits are required (definition + array membership).
**How to avoid:** The installer must do BOTH, each idempotently. Recommend placing `"custom/nightguard"` in `modules-center` (near `clock`/`custom/update`) or at the head of `modules-right`. Verify with a rendered bar after `pkill -SIGUSR2 waybar`.

### Pitfall 4: `ngtui` not on PATH at exec time
**What goes wrong:** The module `exec: ngtui status --json` yields "command not found" → Waybar shows an empty/errored module; the `.desktop` `Exec` fails. **Live-verified: `ngtui` is currently absent from `~/.local/bin`.**
**Why it happens:** `ngtui` is a `uv tool` install, not a repo binary; it can be uninstalled/absent independent of the repo.
**How to avoid:** Make `uv tool install` a prerequisite task; verify `command -v ngtui` before wiring the bar. Waybar's PATH does include `~/.local/bin` (verified), so once installed, bare `ngtui` resolves.
**Warning signs:** `command -v ngtui` empty; bar module blank.

### Pitfall 5: firing the refresh signal on a failed/refused commit (or letting it perturb the result)
**What goes wrong:** Flipping the bar after a refused loosen, or an exception from `pkill` propagating into `commit()`'s return, corrupting the anti-impulse guarantee's user feedback.
**How to avoid:** Gate strictly on `proc.returncode == 0`; wrap the `pkill` in its own try/except that swallows all errors; emit AFTER computing the return dict, never before. Add a unit test asserting: success → signal sent once; non-zero returncode → signal NOT sent; `pkill` raising → `commit()` still returns the real result.

### Pitfall 6: `gtk-update-icon-cache` fails on the user hicolor dir (no `index.theme`)
**What goes wrong:** `~/.local/share/icons/hicolor` has no `index.theme` (verified); plain `gtk-update-icon-cache <dir>` errors and the cache isn't refreshed → icon doesn't appear until relogin (breaks SC-2).
**How to avoid:** Use `gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor` (`-t/--ignore-theme-index`). `update-desktop-database` also required for the `.desktop`.

## Code Examples

### `nightguard.desktop` (DESK-03)
```ini
[Desktop Entry]
Type=Application
Name=Nightguard Control
Comment=Sanctioned editor for your curfew — a window, never a lever
Exec=xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui
Icon=org.omarchy.ngtui
Terminal=false
Categories=Utility;
Keywords=curfew;nightguard;focus;
StartupNotify=false
```
Install to `~/.local/share/applications/nightguard.desktop`. `Terminal=false` because `xdg-terminal-exec` provides the terminal itself. [VERIFIED: app-id propagation, live box]

### Hyprland windowrule snippet (`hypr/nightguard.windowrule.conf`, appended to personal `hyprland.conf`)
```
# >>> nightguard (managed) — do not edit inside markers >>>
windowrule = float on,   match:class ^(org\.omarchy\.ngtui)$
windowrule = center on,  match:class ^(org\.omarchy\.ngtui)$
windowrule = size 875 600, match:class ^(org\.omarchy\.ngtui)$
# <<< nightguard (managed) <<<
```
[VERIFIED: mirrors live TodQuickAdd idiom + omarchy floating-window size]

### Waybar module snippet (`waybar/custom-nightguard.jsonc`, injected into `config.jsonc`)
```jsonc
  // >>> nightguard (managed) >>>
  "custom/nightguard": {
    "return-type": "json",
    "exec": "ngtui status --json",
    "interval": 30,
    "signal": 11,
    "format": "{}",
    "on-click": "omarchy-launch-or-focus-tui ngtui",
    "on-click-right": "ngtui-menu"
  },
  // <<< nightguard (managed) <<<
```
Plus array membership (anchored insert), e.g. into `modules-center`:
`"clock", "custom/nightguard", "custom/weather", …`
[VERIFIED: mirrors custom/update + custom/weather (return-type json) idiom; signal 11 free]

### Waybar style snippet (`waybar/style-nightguard.css`, appended to `style.css`, D-09)
```css
/* >>> nightguard (managed) >>> */
#custom-nightguard { min-width: 12px; margin: 0 7.5px; }
#custom-nightguard.locked          { color: #a55555; }  /* danger red */
#custom-nightguard.clock_tamper    { color: #a55555; }
#custom-nightguard.offline_blocked { color: #a55555; }
#custom-nightguard.grace_active    { color: #c8a24a; }  /* amber */
#custom-nightguard.outside_curfew  { color: #6ea86e; }  /* open green */
#custom-nightguard.unavailable     { color: #8b91a3; }  /* dim */
/* <<< nightguard (managed) <<< */
```
Colors are the fixed semantic mapping (D-09); tweakable. `reload_style_on_change: true` is already set in the live config, so style edits hot-reload. [VERIFIED: live style.css uses `#custom-*.<state> { color: … }` idiom, e.g. `#custom-voxtype.recording`]

### `ngtui-menu` — walker read-only right-click menu (BAR-03, D-04)
```bash
#!/usr/bin/env bash
# Read-only status menu. A window, never a lever: no loosening action exists.
set -euo pipefail
json="$(ngtui status --json 2>/dev/null || echo '{"text":"○ —","tooltip":"unavailable","class":"unavailable"}')"
tooltip="$(printf '%s' "$json" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("tooltip",""))')"
text="$(printf '%s' "$json" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("text",""))')"

# Header lines (inert) + actions (acted on).
choice="$(printf '%s\n' \
  "  $tooltip" \
  "  status: $text" \
  "  ─────────────" \
  "Open editor" \
  "Open status" \
  | walker --dmenu -p "Nightguard")" || exit 0

case "$choice" in
  "Open editor"|"Open status") exec omarchy-launch-or-focus-tui ngtui ;;
  *) exit 0 ;;  # header lines / divider are no-ops
esac
```
Both actions open the same read surface (the TUI opens on StatusScreen; the editor is one keypress in). Install to `~/.local/share/omarchy/bin/ngtui-menu` or `~/.local/bin/ngtui-menu` (both on Waybar PATH). [VERIFIED: walker `--dmenu`/`-p`; omarchy helper reuse]

### `backend.commit()` signal hook (BAR-04, D-11) — minimal diff to `ngtui/ngtui/backend.py`
```python
# after: proc = subprocess.run([...], stdout=subprocess.PIPE, text=True)
result = {"returncode": proc.returncode, "stdout": (proc.stdout or "").strip()}
if proc.returncode == 0:
    # Best-effort instant Waybar refresh; never let this perturb the commit result.
    try:
        subprocess.run(["pkill", "-RTMIN+11", "waybar"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except Exception:
        pass
return result
```
Only on success; swallow all errors. [VERIFIED: signal 11 free; waybar responds to SIGRTMIN+N per module `signal`]

### Icon — hand-coded crescent SVG (DESK-04, D-01) — concrete geometry
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <!-- rounded-square app tile -->
  <rect x="16" y="16" width="480" height="480" rx="108" ry="108" fill="#161a24"/>
  <rect x="16" y="16" width="480" height="480" rx="108" ry="108"
        fill="none" stroke="#242a38" stroke-width="8"/>
  <!-- crescent = moon circle minus an offset smaller circle (mask) -->
  <defs>
    <mask id="crescent">
      <rect width="512" height="512" fill="black"/>
      <circle cx="256" cy="256" r="150" fill="white"/>      <!-- moon -->
      <circle cx="316" cy="212" r="126" fill="black"/>       <!-- offset cut -->
    </mask>
  </defs>
  <circle cx="256" cy="256" r="150" fill="#7aa2ff" mask="url(#crescent)"/>
</svg>
```
Moon r=150; cut r=126 (~84%) offset (+60,−44 ≈ 40%/29% of r toward upper-right) → a bold waxing crescent that keeps a thick sliver at 16px. Tile fill = `--surface #161a24`, border = `--border #242a38`, crescent = `--accent #7aa2ff` (Moonlit Indigo). **Iterate the exact offset/radii in the authoring task and eyeball the 16px raster.** For a monochrome-first read, the silhouette (tile + crescent) carries meaning even without color.

### Icon rasterize + install + cache refresh (D-03, SC-2)
```bash
SRC=packaging/omarchy/icons/nightguard.svg
ICONBASE="$HOME/.local/share/icons/hicolor"
for S in 16 32 48 64 128 256 512; do
  install -d "$ICONBASE/${S}x${S}/apps"
  rsvg-convert -w "$S" -h "$S" "$SRC" -o "$ICONBASE/${S}x${S}/apps/org.omarchy.ngtui.png"
done
install -d "$ICONBASE/scalable/apps"                      # dir absent — create it
install -m644 "$SRC" "$ICONBASE/scalable/apps/org.omarchy.ngtui.svg"
gtk-update-icon-cache -f -t "$ICONBASE"                   # -t: no index.theme in user dir
update-desktop-database "$HOME/.local/share/applications"
```
[VERIFIED: rsvg-convert 2.62.3; all pixel dirs exist; scalable absent; `-t` flag present]

### Idempotent live-config merge (D-07) — approach
```bash
inject_block() {  # $1=file  $2=marker_id  $3=block_text
  local f="$1" m="$2" blk="$3"
  grep -qF ">>> $m" "$f" && { echo "already merged: $m"; return 0; }   # idempotent
  cp -a "$f" "$f.bak.$(date +%s)"                                       # backup first
  printf '\n%s\n' "$blk" >> "$f"                                        # append (hypr: line-based)
}
```
- **Hyprland:** append the marker-guarded windowrule block to `~/.config/hypr/hyprland.conf` (line-based → trivial append). Reloads on file change.
- **Waybar `config.jsonc`:** cannot simply append (object must be inside the root `{}`). Text-insert the module object before the final `}` (guarded), AND anchor-insert `"custom/nightguard",` into a `modules-*` array — each guarded by a "not already present" grep. Never `jq`. Then `pkill -SIGUSR2 waybar` to reload.
- **`style.css`:** append the guarded CSS block (hot-reloads via `reload_style_on_change`).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `hyprctl keyword windowrulev2 …` at runtime | Declarative `windowrule = <rule>, match:<selector>` in config | Hyprland ≥ 0.45 (new `windowrule`/`match:` grammar) | The live box already uses the new `windowrule = float on, match:class ^(…)$` grammar — mirror it, not the old `windowrulev2 = float,class:^(…)$` |
| wofi as the omarchy dmenu | **walker** | omarchy default | wofi is NOT installed; use `walker --dmenu` |
| `xdg-terminal-exec` X-only `--class` | `--app-id` (Wayland) forwarded via `X-TerminalArgAppId` in the terminal's desktop entry | current freedesktop reference impl | app_id lands on Wayland; verified on this box |

**Deprecated/outdated on this box:** the old `windowrulev2 = …, class:^(…)$` syntax (use `windowrule = …, match:class ^(…)$`); wofi/rofi/fuzzel (absent — walker only).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `xdg-terminal-exec` | DESK-03 launcher | ✓ | freedesktop ref impl | — |
| Alacritty w/ `X-TerminalArgAppId=--class=` | app_id propagation | ✓ | alacritty 0.17.0 | `alacritty --class=… -e` direct |
| Hyprland / `hyprctl` | windowrule + focus | ✓ | running session | — |
| Waybar | BAR-01..04 | ✓ | running (live pid) | — |
| `walker` | BAR-03 menu | ✓ | 2.16.2 | none installed (wofi/rofi/fuzzel absent) |
| `rsvg-convert` | DESK-04 rasterize | ✓ | 2.62.3 | `magick`/`convert` (present) |
| `gtk-update-icon-cache` | DESK-04 cache | ✓ | present (`-t` supported) | — |
| `update-desktop-database` | DESK-03/04 | ✓ | present | — |
| omarchy launch helpers | BAR-02 open-or-focus | ✓ | `~/.local/share/omarchy/bin` (on Waybar PATH) | roll a hyprctl script (not needed) |
| SIGRTMIN+11 slot | BAR-04 | ✓ free | 7/8/9/10 taken, 11 free | pick another free N (12+) |
| **`ngtui` on PATH** | module exec, `.desktop`, menu | **✗ MISSING** | — (Phase 11 put it at `~/.local/bin/ngtui`; absent now) | **BLOCKING** — (re)install via `uv tool install --python 3.14 .` before live wiring |

**Missing dependencies with no fallback:**
- `ngtui` command — the entire phase's runtime depends on it. Plan a prerequisite install/verify task (`command -v ngtui`). Waybar PATH already includes `~/.local/bin` (verified), so no PATH change is needed after install.

**Missing dependencies with fallback:**
- None else — every other tool is present.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (invoked via `uv`/venv; `[tool.pytest.ini_options]` in `ngtui/pyproject.toml`, `pythonpath=["."]`, `testpaths=["tests"]`) |
| Config file | `ngtui/pyproject.toml` |
| Quick run command | `cd ngtui && uv run pytest tests/test_backend_signal.py -x -q` (new file) |
| Full suite command | `cd ngtui && uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BAR-04 | `commit()` fires `pkill -RTMIN+11 waybar` ONLY on returncode==0; NOT on non-zero; a raising `pkill` doesn't perturb the result | unit (mock `subprocess.run`) | `uv run pytest tests/test_backend_signal.py -x` | ❌ Wave 0 |
| BAR-01/D-10 | `status.py` still emits `{text,tooltip,class}` unchanged (regression: no change made) | unit | `uv run pytest tests/test_status.py tests/test_status_cli.py -x` | ✅ exists |
| BAR-03 | `ngtui-menu` emits only known actions; never a loosening action (grep the script) | static/grep | `! grep -Eiq 'loosen|token.*spend|grace|commit' packaging/omarchy/bin/ngtui-menu` (allow only open actions) | ❌ Wave 0 |
| DESK-03 | `.desktop` `Exec` uses `-e ngtui` + `--app-id=org.omarchy.ngtui`; `Terminal=false` | static | `grep -q 'app-id=org.omarchy.ngtui' … && grep -q 'Terminal=false' …` | ❌ Wave 0 |
| DESK-03 (live) | window opens with app_id `org.omarchy.ngtui` and floats | manual/human-verify | `hyprctl clients -j \| jq '.[].class'` after launch | manual |
| DESK-04 (live) | icon appears in walker without relogin | manual/human-verify | visual | manual |
| D-07 idempotency | installer run twice → no duplicate blocks; backups created | integration (temp copies) | `uv run pytest tests/test_installer_idempotent.py -x` OR a bash test over fixture configs | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the relevant quick pytest file (`test_backend_signal.py`) + static greps on the artifacts.
- **Per wave merge:** `cd ngtui && uv run pytest -q` (full ngtui suite — guards the D-10 no-change contract).
- **Phase gate:** full suite green + a human-verify checkpoint for the live desktop behaviors (window floats, icon shows, bar renders, right-click menu opens, commit refreshes the bar) — these are inherently GUI/session-bound and cannot be fully automated headless.

### Wave 0 Gaps
- [ ] `ngtui/tests/test_backend_signal.py` — covers BAR-04 (success-only signal; non-perturbing). Mock `subprocess.run` for both the `sudo` commit and the `pkill`.
- [ ] `ngtui/tests/test_installer_idempotent.py` (or a bash harness under `packaging/omarchy/`) — covers D-07 (run-twice-no-dup, backup created) against fixture copies of `config.jsonc`/`hyprland.conf`.
- [ ] Static-grep checks for the `.desktop`, windowrule snippet, and `ngtui-menu` (no-loosening) — can live in a small pytest or a `just`/shell check.
- [ ] Prerequisite (not a test): `command -v ngtui` — install gate before live steps.
- Framework install: none needed (pytest already configured; run via `uv run`).

## Security Domain

Security enforcement is enabled (no `security_enforcement:false` in config). This phase adds **no new privilege** — but it adds new outward-facing entry points and mutates live configs, so the relevant controls are integrity/least-privilege, not auth.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface; the only privileged action stays the existing inline-`sudo` commit (unchanged) |
| V3 Session Management | no | — |
| V4 Access Control | **yes** | "A window, never a lever": every new surface (bar, menu, launcher) is read-only or open-only; the ONLY mutation path remains `backend.commit()` → `sudo nightguard_ctl commit`. No new command reaches a loosen. |
| V5 Input Validation | **yes** | `ngtui status --json` output consumed by the menu — parse defensively (already fail-closed, exit 0, fixed `UNAVAILABLE` on error). Installer must not interpolate untrusted data into `config.jsonc` (only static, phase-authored snippets). |
| V6 Cryptography | no | Key-less throughout; no HMAC, no key read (inherits Phase 11 `test_port03_no_crypto` AST guard) |

### Known Threat Patterns for {omarchy desktop integration}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A bar/menu action that loosens the curfew | Elevation of Privilege (defeats self-binding) | Enforce read-only/open-only surfaces; grep-test `ngtui-menu` for any loosen/commit/grace action (BAR-03 invariant) |
| Signal push perturbs or fakes commit success | Tampering | Fire `pkill` only after `returncode==0`; swallow its errors; never let it change the return (unit-tested) |
| Installer corrupts / clobbers live configs irreversibly | Denial of Service (author locks himself out of his desktop) | Backup-first (`cp -a …bak.<epoch>`), idempotent marker guards, never a JSON round-trip; verify reload before declaring success |
| `ngtui` resolves to a rogue binary on PATH | Tampering/EoP | `ngtui` from the pinned `uv tool` install; `backend.py` already pins `NIGHTGUARD_STACK_DIR` and refuses an unverified stack (CR-02, existing) |
| Window-title spoofing to dodge the float rule | Spoofing | Match on the stable `app_id` (`class`), never `title` (SC-1 invariant) |

## Open Questions

1. **Waybar reload without a full restart**
   - What we know: `pkill -SIGUSR2 waybar` reloads Waybar's config; the live config sets `reload_style_on_change:true` (style hot-reloads). Waybar is running (pid confirmed).
   - What's unclear: whether SIGUSR2 cleanly picks up a *newly added module* (vs only re-reading existing ones) on this Waybar build, or whether a full `omarchy-restart-waybar`/respawn is needed.
   - Recommendation: schedule an execution-time check — after merge, `pkill -SIGUSR2 waybar` and confirm the module renders; if not, fall to a full restart (uwsm autostart respawns waybar). Low risk.

2. **`tag +floating-window` vs explicit float rule (Pattern 2)**
   - What we know: omarchy floats all `org.omarchy.*` TUIs via the `floating-window` tag (875×600), but `org.omarchy.ngtui` isn't in that list.
   - What's unclear: whether a personal-config `tag +floating-window` rule (defined after the sourced default rules) reliably inherits the earlier `float/center/size` tag-rules under Hyprland's evaluation order.
   - Recommendation: ship the **explicit 3-line** rule (order-independent, self-contained). Optionally test the tag one-liner as a nicety; treat as execution-time.

3. **Chosen `modules-*` position for `custom/nightguard`**
   - What we know: any of left/center/right works; center groups the info modules (clock, update, weather).
   - Recommendation: author preference — default to inserting into `modules-center` after `clock`. Not blocking; make it a one-line installer constant.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pkill -SIGUSR2 waybar` loads a newly-added module (not just re-reads existing ones) | Open Q1 | Bar won't show the module until a full waybar restart — low, cheap to fix at exec time |
| A2 | A personal-config `tag +floating-window` rule inherits omarchy's earlier float/center/size tag-rules | Pattern 2 / Open Q2 | Window opens un-floated — mitigated by shipping the explicit 3-line rule instead |
| A3 | Hyprland auto-reloads `hyprland.conf` on file change so the windowrule takes without `hyprctl reload` | Runtime State Inventory | Rule not active until next reload/login — cheap `hyprctl reload` in the installer covers it |
| A4 | Waybar's `custom/*` with `"return-type":"json"` applies the JSON `class` field as the CSS class (as `custom/weather`/`custom/voxtype` do) | Pattern 3 / style.css | style rules wouldn't key correctly — verified idiom in live config; low risk |

*(No package/version assumptions — all tools verified live. These four are behavioral/session assumptions, each with a documented cheap fallback and flagged for an execution-time check.)*

## Sources

### Primary (HIGH confidence — verified live on the target box, 2026-07-03)
- `~/.config/waybar/config.jsonc` — signals 7/8/9/10 in use (11 free); `custom/*` idiom (`exec`/`signal`/`interval`/`on-click`/`return-type:json`).
- `~/.config/waybar/style.css` — `#custom-<name>.<state> { color: … }` idiom; `reload_style_on_change:true`.
- `~/.config/hypr/hyprland.conf` — `windowrule = float on, match:class ^(TodQuickAdd)$` idiom + personal-config section + omarchy-default `source` order.
- `~/.local/share/omarchy/default/hypr/apps/system.conf` — `tag +floating-window` list (org.omarchy.* TUIs) + float/center/size 875×600.
- `~/.local/share/applications/Alacritty.desktop` — `X-TerminalArgAppId=--class=` (the app-id propagation linchpin).
- `/usr/bin/xdg-terminal-exec` (freedesktop reference impl) — `--app-id` → `X-TerminalArgAppId` forwarding logic (§895-905, §1415-1427); drops the value if the terminal entry lacks the key.
- `omarchy-launch-or-focus-tui` / `omarchy-launch-or-focus` / `omarchy-launch-tui` scripts — app_id `org.omarchy.<basename>`, hyprctl focus-or-launch.
- `alacritty --help` — `--class <general>|<general>,<instance>` sets app_id on Wayland (alacritty 0.17.0).
- Live tool inventory: `walker 2.16.2` (`-d/--dmenu`,`-p`); `rsvg-convert 2.62.3`; `gtk-update-icon-cache` (`-t`); `update-desktop-database`; wofi/rofi/fuzzel ABSENT; hicolor pixel dirs present, scalable + user index.theme ABSENT.
- Waybar PATH via `/proc/<pid>/environ` — includes `~/.local/bin` + `~/.local/share/omarchy/bin`.
- `ngtui/ngtui/{status.py,__main__.py,backend.py}`, `ngtui/pyproject.toml`, `ngtui/tests/` — the Phase 11 substrate + test layout.

### Secondary (MEDIUM confidence)
- freedesktop Default Terminal Execution spec (referenced in the xdg-terminal-exec header) — behavior corroborated by reading the actual installed script.

### Tertiary (LOW confidence)
- None relied upon — every load-bearing claim is verified against the live box.

## Metadata

**Confidence breakdown:**
- Standard stack / tool availability: HIGH — every tool probed live with versions.
- app-id propagation (SC-1): HIGH — traced through the actual Alacritty.desktop key + xdg-terminal-exec source.
- Signal slot / module idiom / style idiom: HIGH — read from the live configs.
- Open-or-focus reuse: HIGH — read the actual helper scripts.
- Waybar hot-reload of a *new* module + tag-rule ordering: MEDIUM — flagged as execution-time checks with cheap fallbacks (A1/A2).
- Icon geometry crispness at 16px: MEDIUM — technique is sound (mask-subtract); exact offset/radii to be eyeballed in the authoring task.

**Research date:** 2026-07-03
**Valid until:** 2026-08-02 (stable — omarchy/Hyprland/Waybar idioms; re-verify the free signal slot and `ngtui` PATH presence at plan/exec time as they can change with unrelated config edits).

## RESEARCH COMPLETE
