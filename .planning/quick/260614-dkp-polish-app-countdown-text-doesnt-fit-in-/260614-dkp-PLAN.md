---
quick_id: 260614-dkp
description: "Polish app — fix countdown overflowing the ring; redesign the logo/mark"
date: 2026-06-14
status: in-progress
---

# Quick Task 260614-dkp — Ring countdown fit + logo redesign

## Problem

1. **Countdown overflows the ring.** `.ring-wrap` is 256px; the inner chord at the
   vertical centerline is ≈218px. `#countdown` (`.type-display`) renders at 58px mono,
   so "11:39:40" (8 glyphs) is ≈280px wide and spills onto/over the cobalt ring border.
2. **Logo doesn't look good.** Current `logo.svg` (portal ring + offset-cut crescent) and
   the derived titlebar `mark.svg` read as muddy. Wants a cleaner, intentional mark.

## Tasks

### Task 1 — Make the countdown fit inside the ring
- **files:** `src/styles.css`
- **action:** Enlarge `.ring-wrap` to 288px and reduce `#countdown` to a ring-scoped
  size (~44px) that keeps HH:MM:SS clear of the ring at the vertical centerline. Tighten
  `.ring-center` horizontal padding so status-word/caption never crowd the arc. Keep the
  status-word eyebrow + 2-line caption inside the safe zone.
- **verify:** Run dev server, measure `#countdown` rendered width via Playwright; assert
  it is comfortably less than the available inner chord (≥16px clearance each side).
- **done:** Countdown digits sit fully inside the ring with margin; caption + word fit.

### Task 2 — Redesign the logo + titlebar mark
- **files:** `src/assets/logo.svg`, `src/assets/mark.svg`
- **action:** Design a cleaner Ceramic-Night mark: a crisp crescent guarded by a single
  cobalt arc/shield, balanced on the navy rounded-square canvas. `logo.svg` = 512 app
  icon; `mark.svg` = simplified 24px titlebar glyph in cobalt. No borrowed logos.
- **verify:** Visual check in the running app (titlebar + favicon); shapes crisp at 18px
  and 512px, no muddy overlaps.
- **done:** New mark looks intentional at both sizes.

### Task 3 — Regenerate app icons from the new logo
- **files:** `src-tauri/icons/*` (generated)
- **action:** `npm run tauri icon src/assets/logo.svg` (or a PNG export) to regenerate
  ico/png/icns so taskbar + installer match the new mark.
- **verify:** `src-tauri/icons/icon.ico` + png set regenerated; release build embeds them.
- **done:** Taskbar/installer icon matches the new logo.

## Rebuild & verify
- Kill running app, `npm run tauri build`, relaunch from the existing Start Menu shortcut.
- Confirm: countdown inside ring, new logo in titlebar + taskbar.
