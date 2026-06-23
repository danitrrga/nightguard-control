# Phase 8: Native Blocker - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-23
**Phase:** 08-native-blocker
**Areas discussed:** Kill mechanism, Match strictness, Kill notification, Verdict source, Notification style, Blacklist membership

---

## Kill mechanism (B2)

| Option | Description | Selected |
|--------|-------------|----------|
| SIGKILL by PID | `kill -KILL <pid>`. Hard kill — fully removes the app; strongest deterrent, simplest. | ✓ |
| closewindow (gentle) | `hyprctl dispatch closewindow` — window closes, app stays resident. | |
| closewindow + SIGKILL fallback | Try closewindow, escalate to SIGKILL next tick; optional per-app override. | |

**User's choice:** SIGKILL by PID
**Notes:** Aligned with the "anti-me" guarantee — the app should die, not minimize.

---

## Match strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Substring, case-insensitive | class CONTAINS a blacklist entry — "steam" catches steam, steamwebhelper, steam_app_*. | ✓ |
| Exact, case-insensitive | class EQUALS an entry — precise, misses helper/variant windows. | |
| Prefix, case-insensitive | class STARTS WITH an entry. | |

**User's choice:** Substring, case-insensitive
**Notes:** Accept small over-broad-match risk to catch helper windows. Known gap: Steam-launched games carry their own class and won't match — accepted because killing Steam removes the launch path.

---

## Kill notification

| Option | Description | Selected |
|--------|-------------|----------|
| Silent (log only) | Append to watchdog.log; no on-screen message. | |
| Hyprland notification | Spanish-butler-style notification on kill, consistent with the curfew-hook deny theme. | ✓ |

**User's choice:** Hyprland notification
**Notes:** Matches the existing Spanish-butler deny-message voice.

---

## Verdict source

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse guard's full verdict | curfew + grace + NTP + clock-tamper + block_when_offline; kills match the session-block verdict exactly. | ✓ |
| Lightweight local curfew+grace | in_curfew + grace from state only, no NTP/clock-tamper per tick. | |

**User's choice:** Reuse guard's full verdict
**Notes:** Native-app kills must be consistent with the session-block verdict. Constraint added: reuse the *decision* without re-triggering revert/audit side-effects (the watchdog already does those).

---

## Notification style (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| One summary per tick | Single butler notification listing distinct apps closed. | ✓ |
| One per app killed | A toast per killed window. | |
| One per app, deduped | One toast per distinct app class per tick. | |

**User's choice:** One summary per tick
**Notes:** Avoids toast spam when several windows die in one tick.

---

## Blacklist membership (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Keep steam + discord | Ship v1 with current config entries; expand via signed CLI later. | |
| Add common game launchers | Also blacklist lutris/heroic/etc. | |
| You decide | Claude proposes a sensible list. | ✓ |

**User's choice:** You decide → resolved to **steam + discord** (v1)
**Notes:** Installed-app check found only `steam` present (discord already in config). Decided not to pre-blacklist launchers that aren't on the box; substring matching already covers steam variants; membership is editable later via the signed control-CLI.

---

## Claude's Discretion

- v1 blacklist membership (resolved to steam + discord based on what's installed).
- Exact `runuser`/`env` invocation, pid-dedup, and notification command (`notify-send` vs `hyprctl notify`).
- Shape of the `guard.py` refactor exposing a side-effect-free verdict (constraint locked: no double-revert / no double-audit).

## Deferred Ideas

- Instant `.socket2.sock` `openwindow` event-listener (sub-60s latency) — only if ≤60s leakage proves inadequate with evidence; stays inside the root watchdog.
- Per-app kill-mechanism override + expanded blacklist (game launchers / per-game classes) — add via the signed control-CLI when those apps appear.
