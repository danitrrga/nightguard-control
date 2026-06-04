# Nightguard Control

## What This Is

A Windows desktop app (Tauri v2) that is the **single sanctioned editor** for a
"nightguard" curfew configuration — a self-binding ("anti-me") discipline tool. It
rate-limits how often you can *weaken* your own curfew, grants a small once-daily timed
bypass, and pairs with a guard hook that **auto-reverts any out-of-band hand edits** to
the config. The repo is the clean, publishable product; the author runs a personal
instance wired into his LifeOS (see Context).

## Core Value

A late-night, impulsive version of the user **cannot quietly loosen their own curfew** —
loosening costs a limited weekly token, and editing the raw config by hand silently
reverts. Everything else is secondary to that guarantee holding.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] App is the only sanctioned path to edit the curfew config; raw config is HMAC-signed.
- [ ] An integrity guard hook detects hand-edits (HMAC mismatch) on session/prompt and auto-reverts to the last sanctioned snapshot.
- [ ] Loosening the curfew costs 1 of 3 weekly tokens; tightening/neutral edits are always free and unlimited (direction classifier).
- [ ] Weekly token budget resets Monday 00:00 in the configured timezone.
- [ ] A once-per-day "+8 minutes" button grants a time-boxed bypass of an active lock, NTP-true-time boxed, then re-locks. Does not cost a weekly token.
- [ ] Signing key is stored via Windows DPAPI (CurrentUser); both the app (Rust) and the guard (PowerShell) can verify the same HMAC.
- [ ] State (`guard.json`) is signed too; tampering fails closed (no loosening, grace treated as used).
- [ ] UI: "Moonlit Indigo" — left icon rail, flat Material KPI cards, single periwinkle accent, locked = bright text + moon badge, status + countdown, 3-dot token meter, grace indicator, live per-field loosen/tighten feedback in the editor.

### Out of Scope

- Cross-platform (macOS/Linux) — Windows-only; DPAPI + the PowerShell guard are Windows-bound.
- Multi-user / accounts — single-operator tool.
- Antigravity-side integrity guard — the curfew gate stays cross-agent, but auto-revert is PowerShell/Windows for now.
- Editing anything beyond the nightguard curfew config — not a general settings editor.
- Making the system literally unbreakable — the user is admin; goal is friction past the impulse threshold, explicitly not an absolute lock.

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

## Constraints

- **Tech stack**: Tauri v2, Rust backend (sole writer/signer), vanilla TS + Vite frontend — keep deps lean.
- **Platform**: Windows-only (DPAPI, PowerShell guard).
- **Security**: HMAC-SHA256 over config + state; key at rest via DPAPI (CurrentUser); atomic writes; fail-closed on tamper.
- **Interop**: Rust app and PowerShell guard must verify the *same* HMAC key (shared DPAPI blob).
- **Design**: Moonlit Indigo palette (`--bg #0c0e14 --surface #161a24 --border #242a38 --text #e8eaf0 --dim #8b91a3 --accent #7aa2ff`), Roboto, YouTube-Studio aesthetic, own brand (no borrowed logos).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Auto-revert guard (vs ACL lock / speed-bump) | Strong friction without admin/ACL fights; user can't delete hooks anyway | — Pending |
| Only loosening costs a token | Asymmetry is what makes a self-binding pact actually bind | — Pending |
| 3 tokens/week, reset Monday 00:00 | Predictable calendar-week budget | — Pending |
| +8 = once-daily 8-min timed bypass (not a schedule shift) | Matches user's intent: brief access to plan, then re-lock | — Pending |
| DPAPI-stored HMAC key shared by Rust + PowerShell | Both layers verify same signature; hand-edits can't forge it | — Pending |
| Publishable generic repo + personal LifeOS instance | App is a product; personal config/wiring stays in LifeOS | — Pending |

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
*Last updated: 2026-06-04 after initialization*
