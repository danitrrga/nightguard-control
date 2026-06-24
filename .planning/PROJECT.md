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

### Validated (v2.0 · Linux Port — shipped 2026-06-24)

- ✓ **Linux-only:** the product targets Linux (CachyOS + Hyprland); the Windows DPAPI/PowerShell paths are retired. — v2.0
- ✓ **Config blocking model** redefined for Linux: `browser_extension` + `native_apps`; dead Windows `uwp`/`package_id` removed. — v2.0 (LXCF-01/02)
- ✓ **Root integrity wall:** `.guardkey` + sanctioned config root-owned (root:root 0600); watchdog as a systemd **system** service (true-time + HMAC-revert + managed-policy check). — v2.0 (ROOT-01/02)
- ✓ **Sign via sudo (no daemon):** allowed edits signed by elevating to the control-CLI via `sudo`; root key makes it the sole signer; the prompt is the anti-impulse friction. — v2.0 (ROOT-03/04)
- ✓ **Curfew enforced on Linux:** `guard.py` wired as the Claude Code `UserPromptSubmit` hook; a `deny` verdict hard-blocks the session. — v2.0 (CURF-01)
- ✓ **Linux app = omarchy TUI** (not Tauri): terminal-native, single-key, live-themed, a **thin client over the one Python trust stack** (calls the control-CLI to sign; never holds the key) — single HMAC implementation; anti-impulse cost-before-auth editing. — v2.0 (PORT-01/02/03)

### Descoped / Parked (v2.0)

- ✗ **Native-app blocking (NBLK-01/02/03)** — *descoped*. Built then reverted; the curfew hook was deemed sufficient enforcement. The `guard.curfew_verdict()` refactor survives and backs the TUI display.
- ⏸ **Usage tracking via StayFree (TRAK-01/02)** — *parked*. StayFree records 0 sessions on Hyprland/Wayland (X11-only detection); live tracking is non-functional. Offline blocklist/config import is a future-phase candidate. (ActivityWatch was the earlier plan; also parked.)

### Active (v3.0 — next milestone, to be scoped)

- [ ] Define via `/gsd:new-milestone`. Candidates: offline StayFree blocklist import; Nyquist backfill for phases 6/7/7.1; browser-policy root-lock; ROOT-02 watchdog clock-tamper wording.

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

## Constraints (v2.0 — as shipped)

- **Tech stack**: **one Python trust stack** (`ngcommon`/`guard`/`nightguard_ctl` + systemd watchdog) is the runtime signer/enforcer; the Linux app is a **Python Textual TUI** (`ngtui/`, the only new third-party dep is `textual==8.2.7`). The Rust engine + Tauri UI are retired from the Linux runtime (kept only as historical v1.0 product hygiene). — keep deps lean.
- **Platform**: Linux-only (CachyOS + Hyprland/omarchy). The integrity wall is root-backed; the watchdog + key run as root (systemd **system** service).
- **Security**: HMAC-SHA256 over config + state; **key at rest is a root-owned file** (root:root 0600); signing happens only in the root control-CLI reached via **`sudo`** (no socket/daemon — the socket commit-helper was curated out); atomic writes; fail-closed on tamper. The TUI holds no key and computes no HMAC.
- **Interop**: a **single** HMAC implementation (the Python stack) — no second crypto stack to keep in byte-parity. The StayFree browser extension stays force-installed via a Chromium managed policy.
- **Design**: omarchy-native, single-key, minimal; colors track the live desktop theme (`colors.toml`). *(The v1.0 Moonlit Indigo Tauri palette is retired — superseded by the omarchy TUI per the v2.0 UI contract.)*

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Auto-revert guard (vs ACL lock / speed-bump) | Strong friction without admin/ACL fights; user can't delete hooks anyway | — Pending |
| Only loosening costs a token | Asymmetry is what makes a self-binding pact actually bind | — Pending |
| 3 tokens/week, reset Monday 00:00 | Predictable calendar-week budget | — Pending |
| +8 = once-daily 8-min timed bypass (not a schedule shift) | Matches user's intent: brief access to plan, then re-lock | — Pending |
| DPAPI-stored HMAC key shared by Rust + PowerShell | Both layers verify same signature; hand-edits can't forge it | ✅ v1.0 — superseded by root file key in v2.0 |
| Publishable generic repo + personal LifeOS instance | App is a product; personal config/wiring stays in LifeOS | ✅ v1.0 |
| **[v2.0] Linux-only; retire Windows DPAPI/PowerShell paths** | Author moved to CachyOS; Windows surface is dead for the personal instance | ✅ v2.0 |
| **[v2.0] Root-backed integrity wall** (key + sanctioned config + watchdog all root) | `sudo` becomes the past-the-impulse threshold; user can't read the key to forge a signature | ✅ v2.0 (ROOT-01/02) |
| **[v2.0] Sign via `sudo`/control-CLI** (curated 2026-06-22; replaced the planned Unix-socket commit-helper) | Reuses the existing signer with zero new daemon/protocol; the sudo prompt IS the anti-impulse friction and is idiomatic in a terminal app | ✅ v2.0 (ROOT-03/04, PORT-02) |
| **[v2.0] One trust stack on Linux (Python); app is a thin TUI client** (curated; was Tauri + a 2nd Rust crypto stack) | Avoids maintaining two byte-identical HMAC stacks; the omarchy TUI calls the control-CLI to sign rather than re-implementing crypto | ✅ v2.0 (PORT-01/02/03) |
| **[v2.0] Native blocking folded into the root watchdog tick** (curated; was a separate `--user` socket2 service) | One fewer service, un-stoppable from user space, ≤60s leakage accepted | ✗ v2.0 — DESCOPED (built then reverted; curfew hook deemed sufficient; NBLK-01/02/03) |
| **[v2.0] Keep StayFree as the browser layer** (force-installed Chromium extension) | No native Linux StayFree client, but the extension runs on Linux; don't rebuild URL-blocklist machinery | ⚠️ v2.0 — browser-extension layer kept, but StayFree *tracking* is dead on Wayland (TRAK parked) |
| **[v2.0] ActivityWatch for usage tracking** (later re-scoped to StayFree desktop) | Linux-native usage analytics | ⏸ v2.0 — PARKED (StayFree spike failed on Wayland; offline config-import a future-phase candidate) |
| **[v2.0] curfew_verdict() committed standalone to LifeOS** (2026-06-24, a523c43) | Phase-10 TUI's `live_verdict` depends on it; decoupled it from the reverted native-kill so a git restore can't break the TUI | ✅ v2.0 |

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

## Current State (after v2.0)

**Shipped v2.0 · Linux Port (2026-06-24).** The product is a Linux self-binding curfew tool on one Python trust stack: a root-owned HMAC key + sanctioned config, a systemd **system** watchdog that reverts hand-edits, the control-CLI as the sole signer (reached via `sudo` = the anti-impulse threshold), `guard.py` wired as the Claude Code curfew hook, and a new **omarchy Textual TUI** (`ngtui/`) as the sole sanctioned editor — a thin client that holds no key and previews/signs through the CLI's own classifier. 56 tests, ASVS-L1 secured, Nyquist-compliant.

**Known deferrals:** native-app kill descoped (curfew hook sufficient); StayFree usage tracking parked (dead on Wayland — offline config-import is a future-phase candidate); Nyquist backfill for phases 6/7/7.1; browser-policy root-lock. See `milestones/v2.0-MILESTONE-AUDIT.md`.

**To run the TUI:** `cd ngtui && env NIGHTGUARD_STACK_DIR=/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard NIGHTGUARD_DIR=/home/danitrrga/dev/Projects/LifeOS/nightguard .venv/bin/python -m ngtui`

---
*Last updated: 2026-06-24 after v2.0 · Linux Port milestone (shipped). The Windows DPAPI/PowerShell/Tauri stack is retired; v2.0 runs on a single Python trust stack + an omarchy TUI.*
*Prior: 2026-06-23 — Phase 7.1 (Curfew Hook) complete; curfew now blocks Claude Code sessions (CURF-01).*
*Prior: 2026-06-22 — opened milestone v2.0 · Linux Port (ingested from `docs/linux-port-brief.md`).*
