---
phase: 12-launcher-waybar-presence
plan: 06
subsystem: infra
tags: [omarchy, hyprland, waybar, walker, xdg-desktop, hicolor, installer, live-gate]

# Dependency graph
requires:
  - phase: 12-01
    provides: globally-installed key-less `ngtui` + `ngtui status --json` Waybar substrate
  - phase: 12-02
    provides: backend.commit() SIGRTMIN+11 instant-refresh signal (BAR-04)
  - phase: 12-04
    provides: canonical omarchy artifacts (.desktop, icon SVG, module/style snippets, float rule, ngtui-menu)
  - phase: 12-05
    provides: idempotent, backup-first author-facing install.sh
provides:
  - Live omarchy integration on the author's box (launcher + Waybar module + icon + read-only menu + commit-refresh)
  - Installer hardened to merge into a single-line (inline) modules-center array
  - All five Phase 12 success criteria proven TRUE on the live desktop (human-verified)
affects: [phase-13-packaging, DESK-06, PKGBUILD, aur-publish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Marker-guarded, backup-first text merge into live JSONC/conf (never a jq/JSON round-trip)"
    - "Live phase-gate: headless auto-verify of post-conditions + human-verify of the session-bound GUI behaviors"

key-files:
  created:
    - .planning/phases/12-launcher-waybar-presence/12-06-SUMMARY.md
  modified:
    - packaging/omarchy/install.sh
    - ngtui/tests/test_installer_idempotent.py

key-decisions:
  - "Explicit 3-line app-id float rule (order-independent) over tag +floating-window — verified floats live"
  - "modules-center membership probes the array element ([],] class), never the :-terminated module-object key, so re-runs stay idempotent"
  - "gtk-update-icon-cache 'invalid cache' warning is non-fatal — icon-by-path lookup resolves; the corrected brand icon (8edba91) rendered in walker without relogin"

patterns-established:
  - "Installer anchor greps use `|| true` so a legitimate no-match falls through the -z guard instead of aborting under set -euo pipefail"
  - "Insert fails loud if membership does not land — never a silent Pitfall-3 partial (object defined but unrendered)"

requirements-completed: [DESK-03, DESK-04, BAR-01, BAR-02, BAR-03, BAR-04]

# Metrics
duration: 40min
completed: 2026-07-04
---

# Phase 12 Plan 06: Live omarchy Integration + Phase Gate Summary

**Ran the idempotent installer against the author's live Hyprland/Waybar box and human-verified all five session-bound behaviors — floating app-id launcher, brand icon without relogin, class-colored `custom/nightguard` module, read-only right-click menu, and instant SIGRTMIN+11 post-commit refresh with the sudo PTY intact.**

## Performance

- **Duration:** ~40 min (incl. human-verify walkthrough)
- **Started:** 2026-07-04T11:46:00Z
- **Completed:** 2026-07-04T12:20:00Z
- **Tasks:** 2 (Task 1 auto + auto-verify; Task 2 human-verify — approved)
- **Files modified:** 2 repo files (+ live desktop configs out of repo)

## Accomplishments

- **Live install (Task 1):** `install.sh` ran with default paths on the real box — backed up `config.jsonc`/`style.css`/`hyprland.conf` (`*.bak.1783158947`), injected the `custom/nightguard` module object + inserted it into `modules-center` after `clock`, appended the app-id float rule + semantic style, installed the `.desktop` + hicolor icons (16→512 + scalable) + `ngtui-menu`, refreshed caches, and reloaded Waybar (SIGUSR2) + Hyprland (`hyprctl reload`).
- **12/12 auto-verify checks PASS:** markers present in all three configs, backup created, membership in modules-center, icons + validated `.desktop` + `ngtui-menu` on PATH, and the `ngtui status --json` regression (`{"text":"○ 3","tooltip":"OPEN · 3 tokens left","class":"outside_curfew"}`, exit 0, jq-valid). Merged JSONC still parses as strict JSON with the author's `//` comments preserved.
- **Phase gate (Task 2) — human-verified APPROVED:** launch+float (window `class==org.omarchy.ngtui`, `floating:true`; other terminals tile), brand icon in walker without relogin, bar renders class-colored (green/OPEN/3 tokens), left-click open/focus, right-click read-only menu (no lever), and a real loosen-with-token commit refreshed the bar instantly via SIGRTMIN+11 with the inline `sudo` PTY intact and no guard revert.
- **D-10 baseline held:** ngtui suite 74 passing (73 baseline + 1 new inline-array test), no regression.

## Task Commits

1. **Task 1: Run install.sh + auto-verify (deviation fix)** — `1db34ff` (fix) — installer inline-array merge + no-match-grep hardening + inline test. The live install run itself mutates out-of-repo desktop configs (no repo commit).
2. **Task 2: Phase-gate human-verify** — no repo files (approval only).

**Related (outside this plan, by coordinator):** `8edba91` (fix 12-03) corrected the omarchy brand icon to the canonical mark and re-rasterized the live PNGs; the launch/icon behavior was human-verified with that corrected icon.

## Files Created/Modified

- `packaging/omarchy/install.sh` — `merge_waybar_config` now handles the author's single-line `modules-center` array; anchor greps guarded with `|| true`; membership insert fails loud if it doesn't land.
- `ngtui/tests/test_installer_idempotent.py` — added `test_installer_handles_inline_modules_center_array` (run-twice-no-dup + JSON-valid against an inline array).
- Live (out of repo): `~/.config/waybar/{config.jsonc,style.css}`, `~/.config/hypr/hyprland.conf`, `~/.local/share/applications/nightguard.desktop`, `~/.local/share/icons/hicolor/*/apps/org.omarchy.ngtui.*`, `~/.local/bin/ngtui-menu`.

## Decisions Made

- Kept the explicit 3-line app-id float rule (proven `floating:true` live) rather than the `tag +floating-window` one-liner.
- Membership idempotency keys on the array element, not the object key, so `(a)` injecting the object never fools `(b)` into skipping the array insert.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug / Rule 3 - Blocking] Installer failed on the live single-line modules-center array**
- **Found during:** Task 1 (pre-run inspection of the live `config.jsonc`)
- **Issue:** The shipped installer only matched a multi-line bare `"clock",` anchor (the fixture form). The author's live config keeps `modules-center` as one inline array, so (b) found no anchor. Worse, under `set -euo pipefail` the anchor-grep pipeline (grep|head|cut) returned non-zero on a legitimate no-match and **aborted the script (exit 1, empty stderr)** before the `-z` guard could fall through — after (a) had already backed up and injected the module object, leaving a defined-but-unrendered module (Pitfall 3).
- **Fix:** Added an inline-array insertion branch (sed after `"clock",` on the modules-center line); added `|| true` to the three anchor greps so a no-match falls through instead of aborting; switched the membership idempotency probe to the array-element `[],]` class; added a fail-loud check if the insert doesn't land. Added inline-form test coverage.
- **Files modified:** `packaging/omarchy/install.sh`, `ngtui/tests/test_installer_idempotent.py`
- **Verification:** `uv run pytest -q` → 74 passed; live install then merged into the inline array ("inserted custom/nightguard into modules-center (inline)"), JSONC still parses.
- **Committed in:** `1db34ff`

---

**Total deviations:** 1 auto-fixed (Rule 1 bug + Rule 3 blocking, same fix).
**Impact on plan:** Necessary to run Task 1 against the real target format without a partial/corrupt merge. No scope creep — localized to the installer's text-merge logic + a test.

## Issues Encountered

- **`gtk-update-icon-cache` "generated cache was invalid" (non-fatal):** a known GTK quirk when the user hicolor dir has no `index.theme` (even with `-t`). The PNG/SVG files are correctly placed and icon-by-path lookup resolves; the human confirmed the corrected brand icon renders in walker without relogin. Not a blocker.

## User Setup Required

None — no external service configuration. The live desktop configs were installed and reloaded; Task 1 backups (`*.bak.1783158947`) remain available for rollback.

## Next Phase Readiness

- All five Phase 12 success criteria TRUE on the live box; DESK-03/04 + BAR-01..04 satisfied. **Phase 12 complete (6/6 plans).**
- Ready for Phase 13 (publish path: drop-in snippets + README + AUR PKGBUILD, DESK-06) — deliberately deferred out of this author-facing installer (D-08).

---
*Phase: 12-launcher-waybar-presence*
*Completed: 2026-07-04*
