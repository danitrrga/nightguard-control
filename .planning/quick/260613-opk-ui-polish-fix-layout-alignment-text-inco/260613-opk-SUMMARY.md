---
phase: quick-260613-opk
status: complete
date: 2026-06-13
commits:
  - 9182324
  - 84ed4d9
  - 14e3bc7
---

# Quick Task 260613-opk: UI Polish — custom titlebar + layout cleanup

## What was done

Three atomic commits:

1. **`9182324` tauri.conf.json** — `decorations: false`, `shadow: true`. Native Windows chrome removed.

2. **`84ed4d9` index.html** — Added `#titlebar` (drag-region, moon SVG, wordmark, `#status-pill`, min/max/close buttons). Removed brand-bar from both views. Removed `#meter-divider`. Moved `#edit-budget` chip into `.edit-head-top`. Removed duplicate `.brand` from rail.

3. **`14e3bc7` styles.css + main.ts** — Titlebar CSS; body flex column; shell fills remaining height; brand-bar/meter-divider CSS removed; `.edit-head-top` added; `getCurrentWindow` imported; window controls wired; `dividerEl` removed; token caption two-line; grace copy shortened.

## Outcome

- Custom 36px titlebar with drag region and working min/max/close (red hover on close)
- Brand identity appears once (titlebar only)
- Token caption no longer wraps mid-line
- Grace copy: "Unavailable while open" / "Available · once today" / "Used today"
- tsc clean; vite build green
