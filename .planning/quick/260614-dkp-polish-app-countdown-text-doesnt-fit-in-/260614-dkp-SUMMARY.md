---
quick_id: 260614-dkp
description: "Polish app — fix countdown overflowing the ring; redesign the logo/mark"
date: 2026-06-14
status: complete
---

# Quick Task 260614-dkp — Summary

## What changed

### Task 1 — Countdown now fits inside the ring (`e2e838b`)
- **Root cause:** `.ring-wrap` was 256px (inner chord ≈218px at the vertical centerline)
  but `#countdown` rendered at 58px mono → "11:39:40" ≈280px wide, spilling over the arc.
- **Fix:** `.ring-wrap` 256→288px; `#countdown` 58→44px; `.ring-center` horizontal padding
  `var(--sp-xl)`→32px.
- **Verified (Playwright, live DOM):** at 288px ring the countdown measures 204px wide in a
  251px available chord → **23px clearance each side**. Status-word + caption fit cleanly.

### Task 2 — Logo + titlebar mark redesigned (`0ce320e`)
- Replaced the muddy portal-ring + offset-cut crescent with a cleaner Ceramic-Night mark:
  a single cobalt **guard arc** wrapping a bone **crescent moon** on the navy rounded-square.
- `logo.svg` = 512 app icon (with atmosphere wash); `mark.svg` = 24px cobalt monochrome
  titlebar glyph. Verified legible at 240/64/18px.

### Task 3 — App icons regenerated (`4edcfc8`)
- `npx tauri icon src/assets/logo.svg` regenerated the full ico/png/icns set so the
  taskbar + NSIS installer icon match the new mark. Verified 128px render is crisp.

## Build & deploy
- `npm run tauri build` succeeded; `target/release/nightguard-control.exe` rebuilt with all
  changes + new embedded icons. Existing Start Menu / Raycast shortcut points at this exe.

## Verification
- Countdown fit: measured via live DOM geometry (23px clearance each side). ✓
- Logo: visual check at multiple sizes + 128px icon render. ✓
- Release build: clean, bundle produced. ✓
