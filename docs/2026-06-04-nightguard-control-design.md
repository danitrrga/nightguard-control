# Nightguard Control — Design Spec

**Date:** 2026-06-04
**Status:** Approved for planning (brainstorming complete)
**Implementation protocol:** GSD (user-chosen, overrides default writing-plans)

## Problem

Daniel keeps weakening his own nightguard curfew by hand-editing
`LifeOS/nightguard/config.yaml` late at night, defeating the boundary he set when
rested. He wants a self-binding ("anti-me") system: limit loosening, allow a small
daily grace, route all changes through one sanctioned app, and auto-undo sneaky hand
edits.

## Honest constraint (agreed)

Daniel is admin on this machine — **nothing here is absolutely unbreakable**. The goal
is to raise friction past the threshold where impulse-self gives up, not to build a
literal vault. Daniel confirmed he does not know how to delete hooks, so the friction
tier below holds well for him.

## Locked decisions

| Decision | Choice |
|---|---|
| Enforcement tier | **Auto-revert guard** — app is the only sanctioned editor; hand-edits to the raw config are detected via HMAC mismatch and reverted on next prompt/SessionStart. No ACL/admin fights. |
| Token cost asymmetry | **Only loosening costs a token.** Tightening (or neutral) is always free and unlimited. |
| Weekly budget | **3 loosening tokens**, reset **Monday 00:00** Europe/Amsterdam. |
| +8 grace | A **once-per-day, 8-minute time-boxed bypass** of an *active* curfew lock — unlocks Claude Code for anything for exactly 8 min, then re-locks. NTP-true-time boxed. Does **not** cost a weekly token. |
| Propagation | Hook reads the **LifeOS canonical** `config.yaml` directly (zero-copy). Fixes today's drift between `LifeOS/nightguard/` and `~/.claude/nightguard/`. |
| Visual direction | "Moonlit Indigo", YouTube-Studio *aesthetic* (own brand, no borrowed logos): left icon rail, flat 12px Material cards, big-number KPIs, pill buttons. Single periwinkle accent `#7aa2ff`; locked state = bright text + 🌙 badge. |

### Palette tokens
`--bg #0c0e14` · `--surface #161a24` · `--border #242a38` · `--text #e8eaf0` ·
`--dim #8b91a3` · `--accent #7aa2ff` · `--token-empty #2a3146`. Font: Roboto.

## Architecture

Three separated parts. **Enforcement lives in always-firing hooks, not the app** — the
app being closed never weakens anything.

| Part | Role | Always-on |
|---|---|---|
| Guard hooks (PowerShell, existing system) | Enforce curfew, detect tamper, auto-revert, enforce grace window | Yes |
| Tauri app (Rust + vanilla TS/Vite) | Sole sanctioned editor: holds signing key, classifies changes, enforces 3/week + daily grace, re-signs state | No (open on demand) |
| Canonical config + signed state (`LifeOS/nightguard/`) | Single source of truth; hooks read live | — |

### Files in `LifeOS/nightguard/`

- `config.yaml` — canonical, human-readable, read by hooks.
- `config.sanctioned.yaml` — last app-approved snapshot; the auto-revert target.
- `guard.json` — signed state: `config_hmac`, `state_hmac`, `ledger[]` (loosening events
  w/ NTP timestamps + which fields), `weekly_spent`, `week_anchor` (Monday ISO date),
  `grace` (`{date, window_start, window_end}`).
- `.guardkey` — 32-byte HMAC key, **DPAPI-encrypted (CurrentUser)**. Generated on first
  app run. Both the Rust app and the PowerShell guard can `Unprotect` it; a hand-editor
  cannot forge a valid HMAC without scripting DPAPI as this user.

## Enforcement logic

### Auto-revert integrity guard (`hooks/nightguard_integrity_guard.ps1`)
Runs on **SessionStart + UserPromptSubmit**:
1. Unprotect `.guardkey` (DPAPI). Recompute HMAC of `config.yaml`; compare to
   `guard.json.config_hmac`.
2. **Mismatch → hand-edit detected:** copy `config.sanctioned.yaml` over `config.yaml`,
   log to `tamper.log`, continue. The sneaky edit silently vanishes.
3. If `config.sanctioned.yaml` is also invalid (both tampered) → write a **hardcoded
   strict default** (curfew enabled, conservative window) and log. Fail closed.
4. Verify `guard.json.state_hmac`. If invalid → fail closed: treat `weekly_spent = 3`
   (no loosening) and grace as used, until the app re-syncs.
5. Register this script in the existing `verify_hook_integrity.ps1` SHA256 baseline so
   removing/altering it trips a visible integrity alert.

### Direction classifier (in the Rust app)
Compares proposed config to current, **per field**. A field diff is `tighten`,
`loosen`, or `noop`:

| Field | Loosen = | Tighten = |
|---|---|---|
| `curfew.enabled` | true→false | false→true |
| `curfew.start` | later | earlier |
| `curfew.end` | earlier | later |
| `curfew.allow_commands` | add entry | remove entry |
| `curfew.block_when_offline` | true→false | false→true |
| `curfew.schedule.<day>` | set `off`, later start, earlier end | stricter / removed |
| `clock_protection.enabled` | true→false | false→true |
| `clock_protection.max_offset_minutes` | increase | decrease |
| `watchdog.enabled` | true→false | false→true |
| `watchdog.check_interval_seconds` | increase | decrease |
| `watchdog.apps` | remove app | add app |
| `timezone` | any change (potential bypass) | — |

**Commit rule:** one edit session = **at most one token**. If *any* field in the diff
loosens → the commit is a loosening commit (costs 1 token, requires `weekly_spent < 3`).
If all diffs tighten/neutral → free. No-op → nothing.

### Daily grace (`use_grace`)
Enabled only while curfew is **actively locked**, once per true-day. Writes
`guard.json.grace = {date, window_start=NTP-now, window_end=now+8min}` and re-signs.
`curfew_guard.ps1` gains: if NTP-true-now is inside an active grace window → `exit 0`
(let prompt through). After 8 min → blocks again. The **guard re-checks timing with its
own NTP**, so an app-side clock error can't widen the window.

## Tauri app

**Rust backend (sole writer/signer).** Commands:
- `get_state()` → status, locked?, opens_in, tokens_left, week_anchor, grace availability/active window, NTP drift.
- `classify_change(proposed)` → `{direction, loosens:[fields], allowed, reason}` (live UI feedback).
- `commit_change(proposed)` → validate → classify → quota check → atomically write
  `config.yaml` + `config.sanctioned.yaml`, append ledger, re-sign `guard.json`
  (increment `weekly_spent` iff loosening). Returns new state.
- `use_grace()` → guarded as above.
- NTP true-time via SNTP; if unreachable, flag in UI (hooks already `block_when_offline`).

**Frontend (vanilla TS + Vite, hand CSS w/ tokens).** Screens:
1. **Main** (the approved mockup): status hero (🌙 LOCKED / OPEN + countdown), 3-dot token
   meter, grace KPI, "Grant +8 minutes" (lit only during lock), "Edit curfew".
2. **Edit panel**: field inputs with **live per-field feedback** ("⬇ loosening — costs 1
   token" / "⬆ tightening — free"); commit disabled when loosening with 0 tokens, showing
   reason + refill date.
3. *(Optional, YAGNI-gated)* compact weekly ledger list.

**Location:** `LifeOS/apps/nightguard-control/`. Tauri v2, Windows-only.

## Testing

- Rust unit tests: direction classifier (diff table → expected direction), commit quota
  (loosen consumes 1, tighten free, mixed = 1), Monday week-anchor reset, grace once/day,
  HMAC sign/verify round-trip.
- Integration: tamper `config.yaml` → integrity guard reverts to sanctioned (scripted
  pwsh test); both-tampered → strict default; invalid `state_hmac` → fail-closed quota.
- TDD throughout (GSD executor enforces).

## Out of scope

Cross-platform (Windows-only), Antigravity-side integrity guard (curfew gate stays
cross-agent; integrity guard is PS/Windows for now), multi-user, editing anything beyond
the nightguard config.

## Open implementation detail to verify during GSD

How Claude Code resolves hook paths today (junctioned into `~/.claude/hooks` vs run from
`LifeOS/hooks/`) — determines whether the integrity guard resolves the canonical config
via `$PSScriptRoot\..\nightguard\config.yaml` or an absolute LifeOS path. Verify before
wiring.
