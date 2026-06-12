---
quick_id: 260612-fsc
slug: tray-number-badge
title: Tray number-badge — runtime time-remaining on the tray icon
date: 2026-06-12
status: complete
commit: 8f67492
---

# Quick Task 260612-fsc: Tray number-badge

## Goal

Make the curfew time-remaining visible on the tray icon itself, not just in the
hover-only Windows tooltip. Fulfills the original "see how much time is
remaining" tray ask. Lean-deps: pure-Rust, zero new crates.

## What changed (3 files)

### Task 1 — `src-tauri/src/tray_badge.rs` (new)
- Hand-rolled 5x7 bitmap font for `0-9`, `h`, `+`, `!` (only glyphs the badge emits).
- `render_badge(text, state) -> Option<Image<'static>>`: integer-scales (cap 4)
  + centers the text on a 32x32 transparent RGBA canvas, dark 8-neighbour outline
  for taskbar contrast, then a state-tinted fill (cobalt/sage/amber/rose).
- `None` when no drawable glyphs (caller restores the brand icon).
- verify: `cargo test tray_badge` — 5 tests (canvas size, none-on-empty, palette
  fill, unknown-state fallback, multi-glyph hours).

### Task 2 — `src-tauri/src/lib.rs`
- `TrayHandles` gains `default_icon: Image<'static>` (owned copy of the brand icon,
  built via `Image::new_owned(icon.rgba().to_vec(), w, h)` so it is `'static`).
- `set_tray_status` takes `badge` + `state`: `set_icon(render_badge(..))` when a
  count exists, else restore `default_icon`. Tooltip/menu-line behavior unchanged.
- verify: `cargo check` / `cargo clippy` clean (no new warnings).

### Task 3 — `src/main.ts`
- `fmtBadge(secs)`: `'0'..'59'` under an hour, else `'{h}h'` (clamped 99h).
- `updateTray` derives `badge` + `state` (warn=`!`, none=`''`), passes them to
  `set_tray_status`, throttles the icon swap by `state|badge`.
- verify: `npm run build` green.

## Must-haves
- Tray icon shows the remaining count, updated each minute, tinted by state.
- No count (curfew clear / disabled) restores the plain brand icon.
- Zero new dependencies; advisory display only (no state writes).
- All builds green; unit tests pass.

## Out of scope
- Sub-minute precision on the icon (menu line / tooltip carry "1h 24m").
- Per-platform icon DPI variants (32x32 RGBA, OS downscales).
