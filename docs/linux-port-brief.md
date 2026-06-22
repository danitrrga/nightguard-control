# Nightguard v2.0 — Linux Port Brief

> Brainstorm capture (2026-06-22) to seed a GSD milestone discussion. The v1.0
> product is Windows-only (DPAPI + PowerShell guard + Windows Scheduled Task).
> Daniel has moved to Linux (CachyOS + Hyprland/omarchy); this milestone ports
> the system and replaces the StayFree dependency.

## TL;DR

- **StayFree has no native Linux desktop client** — Android/iOS/Windows/Chrome-extension only. The Chrome/Chromium **extension does run on Linux**, so the browser slice of StayFree survives. What's gone is native-desktop app-blocking + screen-time tracking.
- A Linux port is **already partially landed** (today, 2026-06-22) in `LifeOS/nightguard/`: file-based key, Python watchdog, a systemd user timer (active), browser managed-policies force-installing the StayFree extension, HMAC config + sanctioned snapshot.
- The Tauri app's Rust engine is **platform-agnostic** and ports almost as-is; only the DPAPI key-store module needs swapping.

## Decisions made in brainstorm

| Question | Decision |
|----------|----------|
| Browser blocking | Use the **StayFree browser extension** (already force-installed via root-owned managed policy). Keep it locked + alive; don't rebuild URL-blocklist machinery. |
| Native-app blocking | **In scope** — block apps (Steam, Discord, games) during curfew. |
| DNS/hosts sinkhole | Out of scope for now. |
| Usage tracking | **In scope** — replace StayFree analytics with **ActivityWatch** (Linux-native, open-source, scriptable). |
| Integrity wall strength | **Root-backed** — guard runs as a root systemd service; key + sanctioned config root-owned. `sudo` becomes the past-the-impulse threshold. |

## What v1.0 maps to on Linux

| Windows piece | Linux replacement | Status (2026-06-22) |
|---|---|---|
| DPAPI key store | file-based `.guardkey` (0600, 32 bytes) → move to **root-owned** | ✅ file key exists; ⏳ not yet root |
| PowerShell guard + watchdog | Python `nightguard_watchdog.py` | ✅ exists |
| Windows Scheduled Task | **systemd timer** (currently `--user`, every 60s) → move to **system** unit | ✅ active; ⏳ not yet system/root |
| App watchdog (kill→relaunch) | browser managed policy + native-app blocker | ⚠️ browser done; native not built |
| HMAC config signing / auto-revert | carried over (`config.sanctioned.yaml`) | ✅ |
| Tauri app (Rust engine) | recompile for Linux; swap key-store module only | ⏳ not started |

## Target architecture

```
┌─ ROOT (the "anti-me" wall) ──────────────────────────────┐
│  nightguard-watchdog.service  [systemd SYSTEM timer]      │
│   • verify true time (NTP/HTTPS)  → clock-tamper detect   │
│   • verify config HMAC → revert to config.sanctioned.yaml │
│   • verify /etc/*/policies (StayFree ext still forced)    │
│   • holds .guardkey  (root:root 0600)                     │
└───────────────────────────────────────────────────────────┘
┌─ USER SESSION (enforcement + tracking) ──────────────────┐
│  nightguard-blocker.service  [systemd --user]             │
│   • listens Hyprland socket2 `openwindow` events          │
│   • during curfew: closewindow/kill blacklisted classes   │
│  activitywatch  [user]  • aw-watcher-window + afk → :5600  │
│  Chromium + StayFree extension  (forced by root policy)   │
└───────────────────────────────────────────────────────────┘
┌─ Tauri app (sole sanctioned editor) ─────────────────────┐
│  Rust engine ports as-is; only key-store module swaps    │
└───────────────────────────────────────────────────────────┘
```

**Root vs user split rationale:** native-app blocking needs the Hyprland session
(`HYPRLAND_INSTANCE_SIGNATURE`), so it *must* run as the user — but it need not be
tamper-proof, because the **root** watchdog is what prevents disabling it. Prefer
hooking Hyprland's **socket2 `openwindow` event** (instant kill on open) over a poll
loop (up to 60s of leakage).

## The core design tension (must resolve before P2/P5)

Root-owning the key makes hand-edit HMAC forgery impossible — but then the **Tauri app
(runs as the user) can't sign its own sanctioned edits.** Options:

1. **Root "commit helper"** (recommended): app sends the proposed change over a Unix
   socket to a root service that enforces the token quota, signs, and writes. App is
   freely usable; forgery needs the key (root-only); quota can't be bypassed; `sudo`
   is the only break. Linux analog of "DPAPI app is sole signer," with a real
   privilege boundary.
2. **`pkexec`/polkit per commit** — simpler, but a password prompt on every legit edit.
3. **Keep key user-readable** — simplest, but HMAC becomes friction-by-obscurity, not a
   real wall. Contradicts the root decision.

## Proposed phases

- **P1 · Config cleanup** — `config.yaml` still lists StayFree as a Windows `uwp`
  watchdog app with a `package_id`; that entry is dead on Linux. Redefine blocking
  targets: `browser_extension` (StayFree, policy-managed) + `native_apps` (Hyprland
  window-class blacklist).
- **P2 · Root integrity wall** *(highest value)* — move `.guardkey` + sanctioned config
  to root ownership; convert watchdog to a **system** systemd unit; build the root
  commit helper (Unix socket + quota + sign).
- **P3 · Native blocker** — Hyprland socket2 listener as a `--user` service;
  curfew-gated kill-by-window-class.
- **P4 · ActivityWatch** — install + a sync script feeding screen-time into LifeOS.
- **P5 · Tauri port** *(biggest lift)* — swap the DPAPI key module for the
  socket-to-root-helper client; recompile for Linux; confirm the engine's existing
  Rust tests pass unchanged.

## Open questions / to verify

- [x] **Extension ID verified** `elfaihghhjjoknimpccccmkioofjjfkf` =
  **StayFree — Website Blocker, Web Usage Stats, Shorts Blocker** (publisher: Sensor
  Tower, 4.7★). Canonical Web Store URL:
  `https://chromewebstore.google.com/detail/stayfree-website-blocker/elfaihghhjjoknimpccccmkioofjjfkf`.
  Confirmed correct — safe to lock in. *(verified 2026-06-22)*
- [ ] Decide the commit-path mechanism (recommend option 1, root commit helper).
- [ ] Native-blocker policy: kill the process (SIGKILL) vs `hyprctl dispatch
  closewindow` (gentler, app stays resident) — pick per-app or global.
- [ ] How aggressively to lock the StayFree extension (prevent disable/uninstall via
  policy) and whether to add `URLBlocklist` as belt-and-suspenders.
- [ ] Out-of-scope confirm: DNS/hosts sinkhole deferred, not dropped.

## Out of scope (this milestone)

- DNS/hosts-level blocking.
- Making the system literally unbreakable (Daniel is admin; goal is friction past the
  impulse threshold, per v1.0 design spec).
- macOS port.

---
*See `docs/design-spec.md` for the v1.0 approved design and `.planning/PROJECT.md` for
the Windows-era requirements this milestone supersedes/extends.*
