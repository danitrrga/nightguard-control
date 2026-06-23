# Nightguard Control

**Current milestone: v2.0 · Linux Port** (active) — supersedes the shipped v1.0 (Windows).

## What This Is

A Linux desktop app (Tauri v2) that is the **single sanctioned editor** for a
"nightguard" curfew configuration — a self-binding ("anti-me") discipline tool. It
rate-limits how often you can *weaken* your own curfew, grants a small once-daily timed
bypass, and pairs with a root-owned guard that **auto-reverts any out-of-band hand edits**
to the config. The repo is the clean, publishable product; the author runs a personal
instance wired into his LifeOS (see Context).

> **v1.0 → v2.0:** v1.0 shipped Windows-only (DPAPI key, PowerShell guard, Scheduled
> Task) and is preserved as a completed/tagged milestone. v2.0 ports the system to Linux
> (CachyOS + Hyprland) and moves the integrity wall behind a **root** privilege boundary.
> See `docs/linux-port-brief.md` and `.planning/INGEST-CONFLICTS.md` for the full delta.

## Core Value

A late-night, impulsive version of the user **cannot quietly loosen their own curfew** —
loosening costs a limited weekly token, and editing the raw config by hand silently
reverts. Everything else is secondary to that guarantee holding.

## Requirements

### Validated (v1.0 — shipped on Windows)

- [x] App is the only sanctioned path to edit the curfew config; raw config is HMAC-signed.
- [x] An integrity guard detects hand-edits (HMAC mismatch) and auto-reverts to the last sanctioned snapshot.
- [x] Loosening the curfew costs 1 of 3 weekly tokens; tightening/neutral edits are always free and unlimited (direction classifier).
- [x] Weekly token budget resets Monday 00:00 in the configured timezone.
- [x] A once-per-day "+8 minutes" button grants a time-boxed bypass of an active lock, NTP-true-time boxed, then re-locks. Does not cost a weekly token.
- [x] State (`guard.json`) is signed too; tampering fails closed (no loosening, grace treated as used).
- [x] UI: "Moonlit Indigo" — left icon rail, flat KPI cards, single periwinkle accent, status + countdown, 3-dot token meter, grace indicator, live per-field loosen/tighten feedback in the editor.

> The signing key (v1.0: Windows DPAPI; both Rust app + PowerShell guard verify the same
> HMAC) is **superseded** in v2.0 by a root-owned file key + commit-helper — see Active.

### Active (v2.0 · Linux Port)

- [ ] **Linux-only:** the product targets Linux (CachyOS + Hyprland); the Windows DPAPI/PowerShell paths are retired from the product surface.
- [ ] **Config blocking model** redefined for Linux: `browser_extension` (StayFree, policy-managed) + `native_apps` (Hyprland window-class blacklist); the dead Windows `uwp`/`package_id` entry is removed.
- [ ] **Root integrity wall:** `.guardkey` + sanctioned config are root-owned (root:root 0600 key); the watchdog runs as a systemd **system** service (true-time + HMAC-revert + managed-policy check + native-app kill).
- [ ] **Sign via sudo (no daemon):** allowed edits are signed by elevating to the existing control-CLI via `sudo`/`pkexec` (the bespoke socket commit-helper was curated out). The root key makes the control-CLI the sole signer; `sudo` is the only bypass, and the prompt is deliberate anti-impulse friction.
- [ ] **Native-app blocking folded into the watchdog tick:** during a curfew lock the root watchdog kills blacklisted Hyprland window classes (≤60s leakage accepted; un-stoppable from user space — no separate service).
- [ ] **Usage tracking via ActivityWatch** (aw-watcher-window + afk → :5600) with a sync script feeding screen-time into LifeOS, replacing StayFree analytics. *(Parked — orthogonal analytics; optional this milestone.)*
- [ ] **Linux app = omarchy TUI** (not Tauri): a terminal-native, command-driven, minimal app themed via *aether*, built as a **thin client over the one Python trust stack** (it calls the control-CLI to sign; never holds the key) — so Linux runs a single HMAC implementation.

### Out of Scope

- **macOS port** — Linux + (historical) Windows only.
- **DNS/hosts-level sinkhole** — deferred (not dropped) to a later milestone.
- Multi-user / accounts — single-operator tool.
- Editing anything beyond the nightguard curfew config — not a general settings editor.
- Making the system literally unbreakable — the user is admin (root); goal is friction past the impulse threshold (`sudo` = the threshold), explicitly not an absolute lock.

## Context

- **Existing nightguard system** (the author's personal instance) lives in LifeOS:
  `LifeOS/hooks/nightguard_*.ps1` (curfew gate, NTP utils, watchdog) and
  `LifeOS/nightguard/config.yaml` + logs. This project **extends** that system.
- **Two-layer split:** this repo = the generic, publishable product. The author's
  personal config/state/wiring = `LifeOS/nightguard/` (the "instance with my settings").
  The app reads a **configurable config path**; the author's instance points at
  `LifeOS/nightguard/config.yaml`.
- **Reuse:** existing NTP / clock-tamper detection logic and the curfew-gate schedule
  semantics already exist in the PowerShell hooks — extend, don't reinvent.
- **Propagation fix (instance-level):** today the live hook reads
  `~/.claude/nightguard/config.yaml`, which has drifted from the LifeOS canonical. The
  fix is to point the hook at the canonical config directly (zero-copy). This is
  instance configuration, not part of the published product surface.
- Full approved design: `docs/design-spec.md` (copied from the brainstorming spec).

## Constraints (v2.0)

- **Tech stack**: Tauri v2, Rust backend/engine (ports as-is), vanilla TS + Vite frontend; Python watchdog; systemd units — keep deps lean.
- **Platform**: Linux-only (CachyOS + Hyprland/omarchy). The integrity wall is root-backed; native-app blocking needs the Hyprland session, so the blocker runs `--user` while the watchdog + key run as root.
- **Security**: HMAC-SHA256 over config + state; **key at rest is a root-owned file** (root:root 0600); signing happens only inside a root commit-helper reached over a Unix socket; atomic writes; fail-closed on tamper.
- **Interop**: the Rust engine and the Python watchdog verify the *same* HMAC key (root-owned file); the StayFree browser extension stays force-installed via a root-owned Chromium managed policy.
- **Design**: Moonlit Indigo palette (`--bg #0c0e14 --surface #161a24 --border #242a38 --text #e8eaf0 --dim #8b91a3 --accent #7aa2ff`), Roboto, YouTube-Studio aesthetic, own brand (no borrowed logos). *(Carried over from v1.0 unchanged.)*

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Auto-revert guard (vs ACL lock / speed-bump) | Strong friction without admin/ACL fights; user can't delete hooks anyway | — Pending |
| Only loosening costs a token | Asymmetry is what makes a self-binding pact actually bind | — Pending |
| 3 tokens/week, reset Monday 00:00 | Predictable calendar-week budget | — Pending |
| +8 = once-daily 8-min timed bypass (not a schedule shift) | Matches user's intent: brief access to plan, then re-lock | — Pending |
| DPAPI-stored HMAC key shared by Rust + PowerShell | Both layers verify same signature; hand-edits can't forge it | ✅ v1.0 — superseded by root file key in v2.0 |
| Publishable generic repo + personal LifeOS instance | App is a product; personal config/wiring stays in LifeOS | ✅ v1.0 |
| **[v2.0] Linux-only; retire Windows DPAPI/PowerShell paths** | Author moved to CachyOS; Windows surface is dead for the personal instance | — v2.0 |
| **[v2.0] Root-backed integrity wall** (key + sanctioned config + watchdog all root) | `sudo` becomes the past-the-impulse threshold; user can't read the key to forge a signature | — v2.0 |
| **[v2.0] Sign via `sudo`/control-CLI** (curated 2026-06-22; replaced the planned Unix-socket commit-helper) | Reuses the existing signer with zero new daemon/protocol; the sudo prompt IS the anti-impulse friction (aligned with the friction-not-lock goal) and is idiomatic in a terminal app | — v2.0 |
| **[v2.0] One trust stack on Linux (Python); app is a thin TUI client** (curated; was Tauri + a 2nd Rust crypto stack) | Avoids maintaining two byte-identical HMAC stacks; the omarchy TUI calls the control-CLI to sign rather than re-implementing crypto | — v2.0 |
| **[v2.0] Native blocking folded into the root watchdog tick** (curated; was a separate `--user` socket2 service) | One fewer service, un-stoppable from user space, ≤60s leakage accepted; socket2 only if 60s proves inadequate | — v2.0 |
| **[v2.0] Keep StayFree as the browser layer** (force-installed Chromium extension) | No native Linux StayFree client, but the extension runs on Linux; don't rebuild URL-blocklist machinery | — v2.0 |
| **[v2.0] ActivityWatch for usage tracking** | Linux-native, open-source, scriptable; replaces StayFree desktop analytics | — v2.0 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-23 — Phase 7.1 (Curfew Hook) complete: `nightguard_adapter.py` wired as the Claude Code `UserPromptSubmit` hook via the LifeOS generator; a `deny` verdict now actually blocks sessions on Linux (CURF-01 closed, 3/3 verified). Curfew enforcement (curfew→Claude-Code block) is now LIVE alongside config-revert + browser block. Remaining v2.0: Phase 8 (native-app blocker).*
*Prior: 2026-06-22 — opened milestone v2.0 · Linux Port (ingested from `docs/linux-port-brief.md`).*
