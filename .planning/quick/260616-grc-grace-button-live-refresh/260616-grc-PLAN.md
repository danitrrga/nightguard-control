---
phase: quick-260616-grc
status: planned
date: 2026-06-16
---

# Quick Task 260616-grc: Grace "+8" button stays disabled across the curfew boundary

## Problem

The "+8 minutes" grace button cannot be clicked even when the curfew is active.
Reported repeatedly; prior fixes were all backend/state (classify, midnight wrap,
re-arm) and did not address it.

## Root cause (confirmed)

Verified against the live instance (`NIGHTGUARD_DIR=…/LifeOS/nightguard`):
- `guard.json`: `grace: null` → `grace_available_today=true`; `state_hmac` verifies
  (state_interop_cli exit 0); `config_hmac` verifies for `config.yaml` and
  `config.sanctioned.yaml` (interop_cli exit 0) → `maximal_lockout=false`.
- Curfew `20:30–05:30`; `guard-audit.log` shows `deny reason=curfew` at
  `2026-06-15T18:59:31Z` (20:59 Amsterdam) → `locked=true`, no grace ever active that night.
- So a fresh `get_state` at 22:00 returns `locked && grace_available_today` → the button
  *should* be enabled.

The bug is frontend liveness in `src/main.ts`: the 1-second tick calls only
`renderCountdownOnly` (countdown digits), which never recomputes `locked` or the grace
gate. The full `render()` that sets `graceBtn.disabled` runs only at startup and on a
data-dir **file-watch** event. With the app resident in the tray, nothing writes to the
data dir when the clock simply crosses 20:30 (the guard only writes when a prompt fires),
so the gate is never recomputed and the +8 button stays stuck in its pre-lock (disabled)
state until a file changes or the app restarts.

## Fix

In the existing 1-second tick, when the advisory boundary has passed
(`nowUnix() >= last.boundary_unix`, boundary_kind ≠ "none"), re-invoke `get_state` via
`refresh()` (guarded against concurrent in-flight fetches) so the lock verdict + grace
gate go live the moment the curfew opens/closes — independent of the fs-watch. State still
comes solely from `get_state` (re-verified truth, D-05); the tick only decides *when* to
re-fetch, never *what* the state is.

- files: `src/main.ts` (the `setInterval` tick in `init()`)
- verify: `tsc --noEmit` clean; with the app open across 20:30 the pill flips Locked and
  the +8 button becomes clickable without a restart.
- done: button enables on curfew start while the app is left running.
