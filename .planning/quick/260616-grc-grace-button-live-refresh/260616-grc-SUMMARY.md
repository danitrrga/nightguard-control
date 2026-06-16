---
phase: quick-260616-grc
status: complete
date: 2026-06-16
commits:
  - 2257c04
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
