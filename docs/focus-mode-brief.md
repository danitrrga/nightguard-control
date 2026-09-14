# Nightguard — Focus Mode Brief (Voluntary Daytime Curfew)

> **Never built — historical.** A brainstorm for a voluntary daytime focus
> mode. No `focus:` config block, no CLI, no code of any kind exists for it,
> and it assumed two things that did not happen: window-class blocking and a
> waybar bar. Kept as a record of an idea, not as a plan.

> Brainstorm capture (2026-06-22) to seed a GSD milestone discussion. Focus Mode
> extends nightguard from a single **involuntary bedtime curfew** into a system that
> also offers **voluntary, timer-bound daytime focus sessions** — triggered by Daniel,
> on demand, with a one-keystroke bail. It reuses the Linux-port enforcement engine
> (`linux-port-brief.md`) but intentionally sits *outside* the root integrity wall.

## TL;DR

- **Focus Mode = a short, self-imposed curfew you can cancel.** `focus 25` blocks
  distracting apps + sites, enables Do-Not-Disturb, and drops the desktop into a
  "concentration" layout (fullscreen, no waybar) for 25 minutes, then restores
  everything. `focus stop` ends it early, anytime.
- **It reuses the bedtime-curfew enforcement primitives** — the P3 Hyprland
  window-class kill, the StayFree browser block, ActivityWatch tracking — but is driven
  by a **voluntary timer**, not the curfew schedule, and is **never gated by the root
  watchdog**. The whole point is friction *removal* on exit.
- **This is the design tension, stated up front:** bedtime curfew's value is that it's
  *hard to cheat* (root-owned key, HMAC sanctioned config, anti-tamper). Focus Mode's
  value is that it's *easy to leave* (`focus stop`). The two modes share mechanism but
  must NOT share the integrity model. Focus Mode config is user-owned and never signed.
- **Depends on the Linux port's P3 (native blocker).** Focus app-blocking is the same
  Hyprland socket2 / window-class-kill engine; F-phases below should land after P3 or
  build it in a way P3 can adopt.

## Focus Mode vs. Bedtime Curfew

| Dimension | Bedtime Curfew (v2.0) | Focus Mode (this brief) |
|---|---|---|
| Initiator | Automatic, by schedule (`20:45–05:30`) | Manual — Daniel runs `focus` / presses a keybind |
| Duration | Until `end` (hours) | A timer (default ~25 min), repeatable |
| Anti-tamper | **Root wall** — HMAC config, clock check, sanctioned revert | **None** — voluntary by design |
| Bail | `sudo` past the impulse threshold | `focus stop` — instant, no friction |
| Privilege | Root watchdog + user blocker | **User session only** |
| Blocks Claude Code | Yes (curfew hook) | No — focus is *for* working, often in Claude Code |
| Adds DND + concentration UI | No | **Yes** (fullscreen, hide waybar) |

## Decisions made in brainstorm

| Question | Decision |
|----------|----------|
| What does a session block? | **Apps + websites + notifications (DND) + concentration mode** (fullscreen, hide waybar / chrome). |
| Strictness | **Easy to bail** — `focus stop` cancels instantly. No root, no anti-tamper. Commitment-device variant deferred. |
| Trigger | A dedicated **Hyprland keybind** + a `focus` CLI. `SUPER+Space` is **already the walker launcher** — Focus Mode takes a *different* free combo (TBD, see open questions). |
| Relationship to nightguard | A new **mode** that reuses curfew's enforcement engine, NOT a second copy of it. Shares the P3 native blocker + StayFree + ActivityWatch. |
| Integrity | Focus config is **user-owned, not HMAC-sanctioned**. Focus never calls the root commit helper and cannot alter or extend the bedtime curfew. |

## What Focus Mode reuses (and what's new)

| Focus need | Existing primitive to reuse | New work |
|---|---|---|
| Block native apps (Steam, Discord, Spotify, Signal…) | **P3 native blocker** — Hyprland socket2 `openwindow` → kill blacklisted window-class | Feed it a *focus* blocklist for the session window; tear down on stop |
| Block websites | **StayFree extension** (root-forced, Chromium) | A *temporary, focus-scoped* site block — see open questions (StayFree focus feature vs. per-session policy) |
| Silence notifications (DND) | **mako** — `makoctl mode -a do-not-disturb` (the omarchy mako config already whitelists `notify-send`, so Focus's own start/end toasts still show) | Toggle on start, `-r` on stop |
| Concentration layout | **omarchy / Hyprland** — fullscreen active window (`hyprctl dispatch fullscreen 0`), hide bar (`pkill -x waybar`; restore with `omarchy restart waybar`), no-gaps (`omarchy hyprland window gaps toggle`) | Sequence + reliable restore on stop/expiry |
| The timer itself | **systemd** — `systemd-run --user --on-active=<min>` transient timer fires the auto-stop | `focus` CLI to start/stop/status + a `focus _expire` cleanup entrypoint |
| Session tracking | **ActivityWatch** (Linux-port P4) | Tag focus sessions so screen-time/LifeOS can report "X min focused today" |

## Target architecture

Focus Mode lives entirely in the **user session** layer — the same box as the P3
blocker — and never touches the root wall.

```
┌─ ROOT (bedtime-curfew wall) ─────────────────────────────┐
│  nightguard-watchdog.service   [systemd SYSTEM]          │
│   • NOT involved in Focus Mode. Focus cannot read the    │
│     .guardkey, cannot sign config, cannot extend curfew. │
└───────────────────────────────────────────────────────────┘
┌─ USER SESSION ───────────────────────────────────────────┐
│  focus  (CLI + keybind)                                   │
│   1. start: DND on · fullscreen · hide waybar · no-gaps   │
│   2. push focus blocklist → native blocker + browser      │
│   3. systemd-run --user --on-active=<min>  → auto-stop    │
│   4. stop/expire: reverse every step, restore desktop     │
│                                                           │
│  nightguard-blocker.service  [systemd --user]  ◄── shared │
│   • bedtime curfew uses curfew blacklist                  │
│   • focus mode pushes a focus blacklist for the session   │
│  mako (DND) · waybar · Hyprland · StayFree · ActivityWatch │
└───────────────────────────────────────────────────────────┘
```

## Proposed config (user-owned — NOT in `config.sanctioned.yaml`)

A new top-level `focus:` block in `~/.claude/nightguard/config.yaml`. It is deliberately
**outside** the HMAC-sanctioned snapshot: hand-editing it is *allowed*, because Focus
Mode is voluntary.

```yaml
focus:
  enabled: true
  default_minutes: 25
  keybind: "SUPER, <TBD>"        # SUPER+Space is taken by walker — see open questions
  bail: easy                     # focus stop ends instantly; no sudo
  block:
    native_apps: [steam, discord, spotify, signal]   # may reuse curfew's blacklist
    websites: true               # mechanism TBD (StayFree focus vs per-session)
    dnd: true
  concentration:
    fullscreen: true
    hide_waybar: true
    no_gaps: true
  notify: true                   # start/end toasts (survive DND via notify-send rule)
```

## Proposed phases (GSD)

- **F1 · Session core** — `focus [min]` / `focus stop` / `focus status`; `systemd-run
  --user` transient timer + `_expire` cleanup; session state file; start/end toasts.
  *(No blocking yet — proves the timer + lifecycle.)*
- **F2 · Concentration mode** — fullscreen + hide waybar + no-gaps + DND, with a
  bullet-proof restore path (must survive crash/logout — restore on next `focus` run).
- **F3 · App blocking via the shared engine** — drive the P3 native blocker with the
  focus blocklist for the session window only; clean teardown on stop. *(Hard dep: P3.)*
- **F4 · Browser blocking** — temporary focus site-block; resolve StayFree-focus vs.
  per-session policy (open question). Must auto-clear on stop.
- **F5 · Omarchy keybind + menu** — Hyprland keybind (chosen combo) bound to a
  toggle (`focus` if idle, `focus stop` if active); optional `omarchy menu` entry.
- **F6 · Tracking** — tag focus sessions in ActivityWatch; surface "focused minutes" to
  LifeOS/Jimmy.

## Open questions / to verify

- [ ] **Which keybind?** `SUPER+Space` = walker (app launcher) — not available. Daniel
  chose "a different key entirely" but hasn't named it. Candidates: a free `SUPER`
  combo, or repurpose `SUPER+F` (fullscreen) / a `SUPER SHIFT` pair. **Needs a pick.**
- [ ] **Website-block mechanism.** Options: (a) StayFree's own focus/schedule feature
  (already installed, no new infra, but configured inside the extension); (b) a
  focus-scoped `/etc/hosts` sinkhole (needs root → contradicts easy-bail unless via a
  passwordless helper; also nightguard marked DNS/hosts out of scope); (c) skip web,
  apps+DND only. Recommend (a) if StayFree exposes a togglable focus list.
- [ ] **Reuse curfew's `native_apps.blacklist` or a separate focus list?** Likely a
  separate, longer focus list (curfew blocks games at night; focus may also block
  Spotify/Signal during work).
- [ ] **Toggle semantics on the keybind** — single key does `focus` when idle and
  `focus stop` when active? (Recommended.) Default duration if pressed bare = 25 min.
- [ ] **Collision with bedtime curfew** — if a focus session is running when `20:45`
  hits, bedtime curfew supersedes (it's the stronger wall); focus teardown must not
  un-block curfew targets. Define precedence.
- [ ] **Repeats / breaks** — Pomodoro cadence (25/5) or single ad-hoc sessions only?
- [ ] **Restore robustness** — if the box sleeps/crashes mid-session, waybar/DND/gaps
  must not be left hidden. Need a "heal on next launch" check.

## Out of scope (this brief)

- **Anti-tamper / making Focus Mode unbreakable** — it is voluntary by design; the
  commitment-device ("hard to bail") variant is a separate future discussion.
- **Any root involvement** — no `.guardkey`, no HMAC, no sanctioned config, no systemd
  *system* unit. Focus Mode is user-session only.
- **macOS / Windows** — Linux (CachyOS + Hyprland/omarchy) only.

---
*See `docs/linux-port-brief.md` for the v2.0 enforcement engine this reuses (esp. P3
native blocker) and `docs/design-spec.md` for the v1.0 approved curfew design.*
