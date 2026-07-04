---
phase: 12-launcher-waybar-presence
plan: 03
subsystem: ui
tags: [svg, icon, hicolor, freedesktop, rsvg-convert, moonlit-indigo, branding]

# Dependency graph
requires:
  - phase: 12-launcher-waybar-presence
    provides: "Phase 12 desktop-integration context (icon-name org.omarchy.ngtui bound by nightguard.desktop)"
provides:
  - "Canonical own-brand icon source packaging/omarchy/icons/nightguard.svg (crescent-on-tile, Moonlit-Indigo)"
  - "The single source of truth the installer (Plan 05) rasterizes into hicolor PNG sizes 16..512 + scalable SVG"
affects: [12-05-installer, 12-06-waybar-verify, waybar, launcher, hicolor-theme]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Own-brand SVG as single source of truth: no committed PNGs; installer rasterizes hicolor sizes from the SVG at install time (no stale rasters)"
    - "Crescent via SVG <mask> (white moon circle minus black offset cut circle) for a clean anti-aliased sliver at any size"

key-files:
  created:
    - "packaging/omarchy/icons/nightguard.svg"
  modified: []

key-decisions:
  - "Crescent geometry tuned off the research seed: moon cx240 cy256 r156, cut cx326 cy216 r132 (~85% of moon r, offset up-right) for a thick waxing sliver that survives 16px"
  - "Double rect for the tile border (inset stroke rect) so the 8px border sits inside the tile edge and does not clip at the rounded corners"

patterns-established:
  - "SVG-source-of-truth: brand raster sizes are derived, never committed (installer-rasterized)"

requirements-completed: [DESK-04]

# Metrics
duration: 4min
completed: 2026-07-04
---

# Phase 12 Plan 03: Own-Brand Crescent Icon Summary

**Hand-authored own-brand crescent-moon-on-rounded-tile SVG (Moonlit-Indigo, mask-cut crescent) that rasterizes cleanly 16→512 via rsvg-convert and is the single source of truth the installer rasterizes into the hicolor theme.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-07-04T09:34Z
- **Completed:** 2026-07-04T09:38Z
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments
- Authored `packaging/omarchy/icons/nightguard.svg` — a `viewBox="0 0 512 512"` own-brand mark: a rounded-square app tile (`#161a24` surface fill + `#242a38` inset border) with a crescent moon in `#7aa2ff` accent, formed via an SVG `<mask>` (white moon circle minus an offset black cut circle).
- Verified it rasterizes cleanly: `rsvg-convert -w 16 -h 16` and `-w 512 -h 512` both exit 0 and produce valid non-empty PNGs (`PNG image data, 16 x 16` / `512 x 512`).
- Confirmed the 16px raster is not blank/invisible: 244/256 opaque tile pixels (rounded transparent corners) and a legible 27-pixel accent crescent sliver (ASCII-silhouette introspected via PIL — reads as a crescent-on-tile at 16px monochrome-first).
- Discharged decisions D-01 (crescent-on-rounded-tile concept), D-02 (Claude hand-authors the SVG this phase), D-06 (canonical brand artifact shipped in-repo).

## Task Commits

Each task was committed atomically:

1. **Task 1: Hand-author the crescent-on-tile brand SVG** - `eb6c69e` (feat)

**Plan metadata:** (this SUMMARY + STATE/ROADMAP) — see final docs commit.

## Files Created/Modified
- `packaging/omarchy/icons/nightguard.svg` - Canonical own-brand icon source (crescent moon on a rounded-square tile; Moonlit-Indigo fills; mask-cut crescent). Source of truth; installer rasterizes hicolor PNGs from it.

## Decisions Made
- Tuned the crescent off the research seed geometry for a bolder sliver: moon `cx=240 cy=256 r=156`, cut `cx=326 cy=216 r=132` (~85% of moon radius, offset toward upper-right) — a thick waxing crescent that keeps a visible sliver at 16px.
- Used an inset second `<rect>` (x=20 y=20, 472×472, rx=104) for the border stroke so the 8px `#242a38` border sits inside the tile edge rather than straddling the outer rounded corner.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed double-hyphens from XML comments**
- **Found during:** Task 1 (SVG authoring)
- **Issue:** The first-authored SVG embedded the palette notes as `--surface`/`--border` and used a `→` arrow in comments; XML forbids `--` inside comments, so `rsvg-convert` failed with `XML parse error: Comment must not contain '--'` and produced an empty PNG.
- **Fix:** Reworded the comments to drop all double-hyphens (e.g. "surface #161a24" instead of "--surface #161a24") and removed the arrow glyph.
- **Files modified:** packaging/omarchy/icons/nightguard.svg
- **Verification:** `rsvg-convert` now exits 0 at both 16px and 512px, valid PNGs; source greps for `viewBox`, `<mask`, `#7aa2ff` all pass.
- **Committed in:** `eb6c69e` (Task 1 commit — fixed before the commit)

---

**Total deviations:** 1 auto-fixed (1 bug, caught pre-commit)
**Impact on plan:** The fix was required for the SVG to rasterize at all. No scope creep — the mark, geometry, and palette are exactly as planned.

## Issues Encountered
- Piping `rsvg-convert ... -o -` into a PIL stdin reader did not yield a readable stream in this shell; switched the pixel-introspection check to rasterize to a temp file first. No effect on the artifact.

## User Setup Required
None - the SVG is a static build-time asset; live install (rasterize into `~/.local/share/icons/hicolor` + cache refresh) is Plan 05's installer.

## Next Phase Readiness
- The canonical brand icon source is in-repo. Plan 05's installer can rasterize it into hicolor PNG sizes 16..512 + a scalable copy (`org.omarchy.ngtui.png`/`.svg`) and refresh the caches.
- Subjective "looks good" is deferred to the Plan 06 human-verify (the 16px silhouette is confirmed legible here; final visual read is at the live launcher/Waybar checkpoint).

## Self-Check: PASSED

- FOUND: packaging/omarchy/icons/nightguard.svg
- FOUND: commit eb6c69e

---
*Phase: 12-launcher-waybar-presence*
*Completed: 2026-07-04*
