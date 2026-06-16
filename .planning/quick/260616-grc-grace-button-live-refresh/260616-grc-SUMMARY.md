---
phase: quick-260616-grc
status: complete
date: 2026-06-16
commits:
  - 2257c04
  - dc7420a
  - 5a39aad
---

# Quick Task 260616-grc: Grace "+8" button live across the curfew boundary

## What was done

One change to the 1-second tick in `src/main.ts` (`init()`): the tick now re-invokes
`get_state` (via `refresh()`) when the advisory boundary has passed
(`nowUnix() >= last.boundary_unix`, boundary_kind ≠ "none"), guarded by an in-flight flag
so slow fetches don't stack. Otherwise it keeps doing only the cheap countdown redraw.

## Root cause

`render()` — the only place `graceBtn.disabled = !(s.locked && s.grace_available_today)`
is set — ran only at startup and on a data-dir file-watch event. The 1s tick redrew
countdown digits but never recomputed the lock/grace gate. For a tray-resident app, the
clock crossing 20:30 wrote nothing to the data dir (the guard only writes when a prompt
fires), so the gate never refreshed and the +8 button stayed disabled until a file changed
or the app restarted. Confirmed against the live instance: `grace=null`, both HMACs verify,
`guard-audit.log` shows `deny reason=curfew` at 20:59 Amsterdam with no grace active — i.e.
`get_state` would have enabled the button, but the UI never re-fetched it.

## Outcome

- The lock pill and the +8 grace button now go live the moment the curfew opens/closes,
  even with the app sitting in the tray (no restart, no file change required).
- State still flows solely through `get_state` (re-verified truth, D-05); the tick only
  decides *when* to re-fetch.
- Backend untouched; `tsc --noEmit` clean.

## Verify (user, tonight)

Leave the app in the tray before 20:30 and watch at 20:30: the pill should flip to
**Locked** and **+8 minutes** should become clickable on its own. If it becomes clickable
but clicking shows an amber "NTP unreachable" message, that's a separate (network/NTP)
issue, not the gate — surface it and we'll handle that next.

## Addendum — rebuild + single-instance lock (same session)

- **Single-instance** (`dc7420a`): added `tauri-plugin-single-instance` v2.4.2 (registered
  first in `lib.rs`). A second launch — Raycast opening it while the autostart `--hidden`
  tray copy is resident, or any double-open — no longer spawns a twin; the plugin fires the
  callback in the running instance, which show + unminimize + set_focus on the main window.
  Verified live: `--hidden` launch then a second no-arg launch → exactly **1** process.
- **Rebuild**: built the frontend (tsc + vite) then `cargo build --release` (the npm/tauri
  CLI path failed in this shell — npm spawns bash, which the stripped env lacks; drove the
  binaries directly instead). New exe stamped 2026-06-16 11:49, embeds the grace fix +
  single-instance. `--no-bundle` (NSIS skipped — the shortcut/autostart use the exe directly).
- **Raycast shortcut**: `…\Start Menu\Programs\Nightguard Control.lnk` already targets the
  stable `target\release\nightguard-control.exe` (no args), so it now runs the newest build
  with no change needed. Left one hidden resident instance of the new build running.

## Addendum 2 — release build was booting in DEV mode (`5a39aad`)

The first manual rebuild produced an exe that showed `ERR_CONNECTION_REFUSED` for
`localhost:1420`. Root cause: the crate had **no `[features]` block**, so the
`custom-protocol` feature was never on — and `tauri-macros` gates dev mode on it
(`dev: cfg!(not(feature = "custom-protocol"))`). `tauri build` (the CLI) enables it
automatically, but the manual `cargo build --release` (used because npm spawns bash, which
this shell lacks) did not → the app loaded the dead dev server.

Fix: declared the standard `custom-protocol = ["tauri/custom-protocol"]` feature and rebuilt
with `cargo build --release --features custom-protocol`. Verified at the binary level (the
hashed JS asset is now embedded — it was absent before) and visually (window renders the real
UI: "UNTIL LOCK 08:05:08 · Next lock at 20:30", tokens, grace card — not the error page).
Single-instance re-confirmed on the production build (2nd launch → still 1 process).

**Note for future manual builds:** always pass `--features custom-protocol`, or just use the
normal `npm run tauri build` in a real terminal (the CLI handles it).
