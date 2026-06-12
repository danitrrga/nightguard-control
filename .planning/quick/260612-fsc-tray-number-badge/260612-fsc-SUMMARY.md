---
quick_id: 260612-fsc
slug: tray-number-badge
title: Tray number-badge — runtime time-remaining on the tray icon
date: 2026-06-12
status: complete
commit: 8f67492
---

# Quick Task 260612-fsc — Summary

The Windows tray tooltip is hover-only, so the curfew countdown wasn't visible at
a glance. The tray icon now renders the time-remaining count directly, tinted by
lock state. Pure-Rust, zero new dependencies.

## What shipped

- **`src-tauri/src/tray_badge.rs` (new)** — a hand-rolled 5x7 bitmap font
  (digits + `h`/`+`/`!`) integer-scaled (cap 4×) and centered on a 32×32
  transparent RGBA canvas. Dark 8-neighbour outline for contrast on light/dark
  taskbars, then a state-tinted fill: cobalt (locked), sage (open), amber
  (grace), rose (unverified). `render_badge()` returns `None` for empty/
  undrawable text so the caller restores the plain brand icon.
- **`src-tauri/src/lib.rs`** — `TrayHandles` now holds a `'static` owned copy of
  the brand icon (`Image::new_owned(icon.rgba().to_vec(), w, h)`). `set_tray_status`
  gained `badge` + `state` params: `set_icon(Some(render_badge(..)))` when there's
  a count, else restore the default icon. Tooltip + menu line unchanged.
- **`src/main.ts`** — `fmtBadge(secs)` ("0".."59" under an hour, else "{h}h",
  clamped 99h); `updateTray` derives `badge`/`state` (warn=`!`, none=`""`) and
  passes them through, throttling the icon swap by `state|badge` so the icon
  only re-renders on a real minute/state change.

## Verification

- `cargo test tray_badge` — **5/5 pass** (canvas size, none-on-empty, palette
  fill per state, unknown-state→cobalt fallback, multi-glyph "12h").
- `cargo check` + `cargo clippy` — clean; no new warnings in `tray_badge.rs`/
  `lib.rs` (pre-existing doc-lints in `mutation-engine/state.rs` left untouched).
- `npm run build` — green (JS 12.37 kB).

## Not verified (visual)

Live tray appearance not screenshotted (no `tauri dev` launch this session). The
renderer is unit-tested for structure/color; on-screen legibility at the OS tray
size is best confirmed by running the app and watching the icon tick.

## Follow-ups (optional)

- If digits look cramped on a 16px tray, bump the canvas to 48/64 or thicken the
  outline; trivial constants in `tray_badge.rs`.
- Could badge the taskbar/window icon too (same renderer) if ever wanted.
