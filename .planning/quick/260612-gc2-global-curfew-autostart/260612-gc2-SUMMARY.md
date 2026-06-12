---
quick_id: 260612-gc2
slug: global-curfew-autostart
title: Globalize curfew guard hook + app login-autostart (close-to-tray)
date: 2026-06-12
status: complete
commit: d96c76c
---

# Quick Task 260612-gc2 — Summary

Two asks: run Nightguard at startup, and enforce the curfew hook in ALL Claude
projects (not just the LifeOS vault).

## Key discovery (corrected a stale assumption)

The prior "cutover complete" notes claimed the live guard was the new Phase-5
`nightguard_adapter.ps1`. The live config said otherwise:
- Global `~/.claude/settings.json` had **no** curfew hook.
- The guard was wired **only** in `LifeOS/vault/.claude/settings.json`, calling
  the **legacy** `curfew_guard.ps1`.
- => The prompt curfew was enforced **only inside the vault project**; every
  other project (this repo, el-portal, ...) had no prompt gate. (The
  StayFree watchdog task still runs globally — that part was fine.)

## What shipped

### Curfew hook -> global (ops, outside repo; per user choice = legacy guard)
- Added `curfew_guard.ps1` to global `~/.claude/settings.json` `UserPromptSubmit`
  (now fires in every project, incl. this session).
- Removed the duplicate from `LifeOS/vault/.claude/settings.json` (`hooks: {}`)
  so it's single-source (Claude merges hook scopes -> would otherwise double-fire).
- Safety proof: guard exits **0 (allow)** before and after wiring (daytime,
  outside the 20:45 curfew); both settings files re-validated as JSON; this
  session kept working = live confirmation it doesn't lock you out today. It will
  block (exit 2) at curfew / NTP-unreachable / clock-tamper, in all projects now.

### Close-to-tray + hidden login start (repo, commit d96c76c)
- `src-tauri/src/lib.rs`: `on_window_event` CloseRequested -> `prevent_close()` +
  `hide()` (resident tray companion; quit via tray menu). Window starts hidden;
  manual launch (no `--hidden`) shows it on ready.
- `src-tauri/tauri.conf.json`: main window `"visible": false` — a late `hide()` in
  setup lost the race (window briefly visible), so we start hidden in config and
  show only on manual launch. Verified: `--hidden` launch leaves the
  'Nightguard Control' window `IsWindowVisible=false`, process resident.
- `scripts/deploy/install_autostart.ps1` (new): parameterized HKCU Run-key
  installer -> `"<exe>" --hidden`, `-Remove` to unregister. Publishable (defaults
  to repo `target/release` exe; no personal paths committed).

### Live instance wiring (ops)
- Built the release exe (`target/release/nightguard-control.exe` + NSIS bundle).
- Registered HKCU Run-key "Nightguard Control" -> `"<exe>" --hidden` (via the new
  script). Launches hidden-to-tray at next login.
- Started the instance now (running hidden, pid resident) — needs user-scope
  `NIGHTGUARD_DIR` (already set: `...\LifeOS\nightguard`; logon inherits it).

## Verification
- Guard exit 0 (allow) pre + post wiring; global + vault settings.json valid JSON.
- Release build green (cargo release compile, exit 0); NSIS bundle produced.
- `--hidden` smoke launch: app window `IsWindowVisible=false`, process resident.
- Run-key readback matches `"<exe>" --hidden`.

## Reversibility / notes
- Undo autostart: `install_autostart.ps1 -Remove` (or delete the HKCU Run value).
- Undo global hook: remove the `curfew_guard.ps1` group from
  `~/.claude/settings.json` `UserPromptSubmit`.
- Run-key points at the dev `target/release` exe (auto-fresh on each
  `npm run tauri build`); a `cargo clean` would remove it — re-run the build +
  installer if so. Alternatively install the NSIS bundle and point the key there.
- Decision was initially the **legacy** guard (parity with what was live).

## Addendum — cutover to the new guard (same day, user: "GO AHEAD")

Promoted the global hook from the legacy `curfew_guard.ps1` to the Phase-5
**`nightguard_adapter.ps1`** (thin Claude-Code seam → `nightguard_guard.ps1`,
the full HMAC config+state verify / schedule verdict / fail-closed oracle).
Prove-then-switch:
- Adapter contract confirmed: stdin prompt JSON → exit 0 allow / exit 2 block;
  ANY exception (unset NIGHTGUARD_DIR, guard throw, non-{0,1} exit) → exit 2
  (fail-closed). `/shutdown`-type `allow_commands` bypass before invoking guard.
- Proved adapter **exit 0 (allow)** with user-scope NIGHTGUARD_DIR + a fake
  prompt, mirroring the wired invocation — **before and after** the swap (daytime,
  state verified).
- Swapped `~/.claude/settings.json` UserPromptSubmit `curfew_guard.ps1` →
  `nightguard_adapter.ps1`; re-validated JSON; hook list confirmed.
- Now live in **all** projects: full fail-closed guard (HMAC-verified state, NTP
  true-time, clock-tamper, schedule). Blocks (exit 2) at curfew / offline /
  tamper / any verification failure — everywhere.
- Revert: point the UserPromptSubmit command back at `curfew_guard.ps1`.
