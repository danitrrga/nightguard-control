# Phase 4: UI (Moonlit Indigo) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-09
**Phase:** 4-UI (Moonlit Indigo)
**Areas discussed:** App-shell + IPC scope, Source of enforced truth, Liveness/refresh, Edit panel + actions, Design aesthetic

---

## App-shell + IPC scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full scaffold + IPC + UI | Scaffold Tauri v2 vanilla-TS app, add src-tauri, wrap crates as 4 IPC commands, build all UI. One vertical slice, ~3-4 plans. | ✓ |
| Insert a scaffold phase first | Add Phase 3.5 for shell+IPC, keep Phase 4 pure UI. | |
| Scaffold exists, wire only | Treat shell as present (task 0), focus on IPC+UI. | |

**User's choice:** Full scaffold + IPC + UI.
**Notes:** No Tauri shell / package.json / tauri.conf.json / #[tauri::command] exists yet — confirmed by scout. The IPC layer is thin glue over already-built trust-kernel/mutation-engine functions.

---

## Source of enforced truth

| Option | Description | Selected |
|--------|-------------|----------|
| Read + re-verify signed artifacts via kernel | get_state reads same signed config.yaml + guard.json, re-verifies HMAC via kernel, derives state. No side effects. | ✓ |
| Display the guard's last-written verdict | UI reads latest guard verdict JSON; staleness tied to guard cadence. | |
| Shell out to run the guard live | get_state runs the guard; authoritative but side-effects (revert/audit/SNTP) on every refresh. | |

**User's choice:** Read + re-verify signed artifacts via kernel.
**Notes:** Keeps "app is a reader, guard is the enforcer." No shelling out (avoids reverts/audit on refresh). Clock-tamper stays the guard's authority; app-side time advisory only.

---

## Liveness / refresh

| Option | Description | Selected |
|--------|-------------|----------|
| Watch the data dir, tick 1s | Tauri fs-watch on config.yaml + guard.json → instant re-verify; 1s client tick animates countdown. | ✓ |
| Poll every few seconds | Fixed ~5s re-verify + 1s tick. Simpler, slightly stale. | |
| Refresh on focus / manual | Re-verify on focus/click. Lowest overhead, can lie between focuses. | |

**User's choice:** Watch the data dir, tick 1s.
**Notes:** Reflects the guard the moment it reverts; fallback poll only if watcher unreliable.

---

## Edit panel + actions

| Option | Description | Selected |
|--------|-------------|----------|
| Live feedback, confirm only on loosen, re-verify after write | classify_change live debounced; tighten=accent, loosen=warning+cost; 0 tokens disables commit w/ reason; confirm on loosen; re-read after commit/+8. | ✓ |
| Feedback on blur, no confirm step | Classify on blur; commit loosening immediately (still blocked at 0). | |
| Let me steer this one | User wants follow-ups first. | |

**User's choice:** Live feedback, confirm only on loosen, re-verify after write.
**Notes:** Tightening commits freely; +8 grace grant re-fetches signed state afterward.

---

## Design aesthetic (user-led, mid-discussion steer)

**User's direction (free-text):** "Make sure that its a minimalist app, with not too much going
on — a way of visualizing my focus in general, not trying to replace StayFree. Make it simple and
avoid using too many box containers and cards."

**Captured as:** D-11/D-12 — minimalist, typographic, whitespace-led, few containers (no card
soup). "flat-card" hint in CLAUDE.md superseded for this phase; Moonlit Indigo palette + Roboto
retained; countdown is the hero; left-icon-rail kept sparse. App is a focus-legibility surface,
NOT a usage tracker.

---

## Claude's Discretion

- Exact `get_state` DTO shape (lock bool, boundary timestamps, weekly_spent/remaining, grace
  availability, fail_closed/verify status) — designed in planning against engine return types +
  guard.json schema.
- File-watch debounce window, countdown formatting, component decomposition.

## Deferred Ideas

- Usage analytics / screen-time tracking / app-blocking (StayFree domain — not this product).
- General-purpose settings editor (out of scope — curfew config only).
- Phase 5 instance wiring (its own phase).
