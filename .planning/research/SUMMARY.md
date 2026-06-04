# Project Research Summary

**Project:** Nightguard Control
**Domain:** Windows desktop self-binding / commitment-device tool (Tauri v2 + Rust, tamper-evident local crypto)
**Researched:** 2026-06-04
**Confidence:** HIGH

## Executive Summary

Nightguard Control is a Windows-only "commitment device" — a self-binding tool people use
against their own future weakness. Research across the category (SelfControl, Cold Turkey,
Freedom, Beeminder, One Sec) strongly **validates the locked architecture**: durable tools
win trust by putting enforcement somewhere the impulsive self cannot reach in the moment.
Nightguard's "enforcement lives in always-firing PowerShell hooks, not the app" is exactly
that. Clock-tampering is a named category-wide bypass; the NTP-true-time design already
counters it.

The recommended build is a Tauri 2.11.x app with a Rust backend as the **sole writer and
signer**, a vanilla-TS + Vite frontend, and the existing PowerShell hooks as the **sole
runtime enforcer**. The single linchpin — and the one genuine technical risk — is sharing
one HMAC key between Rust and PowerShell via Windows DPAPI, and producing byte-identical
HMACs across both languages. Both are achievable with documented APIs, but only if done a
specific way (raw `CryptProtectData` blobs, never PowerShell's `SecureString`/
`ConvertFrom-SecureString` framing). This must be de-risked in an early interop spike that
gates Phase 1.

Top risks are all in the trust kernel: the DPAPI SecureString framing trap, HMAC input
canonicalization (CRLF/BOM/trailing-newline), an auto-revert sign-vs-write race that could
revert a legitimate in-app edit, and a fail-closed "brick" with no recovery. Each has a
known prevention and maps to a specific phase.

## Key Findings

### Recommended Stack

Tauri v2 (current stable **2.11.2**), scaffolded via `create-tauri-app` → Vanilla →
TypeScript. v2 IPC import is `@tauri-apps/api/core` (not the v1 `/tauri` path). Rust backend
owns all writes, signing, classification, and quota math.

**Core technologies:**
- **Tauri 2.11.x** — desktop shell + Rust↔frontend IPC (`#[tauri::command]` / `invoke`).
- **`hmac 0.12.1` + `sha2 0.10.9`** — battle-tested HMAC-SHA256 pairing (avoid the brand-new 0.13/0.11 line, not yet widely adopted).
- **`windows-dpapi 0.2.0`** (returns the raw `CryptProtectData` blob, no framing) — or a ~40-line direct `windows-sys` call to minimise trusted deps in the security path.
- **`sntpc 0.10.1`** — SNTP true-time (verify exact `sync::get_time` signature at integration).
- **`yamlpatch` / `yamlpath 1.25.2`** — comment/format-preserving YAML writes (NOT `serde_yaml`, which is archived and destroys comments; the config.yaml is human-readable and the PowerShell hooks use a hand-rolled minimal parser that must keep reading it).

### Expected Features

**Must have (table stakes — or the tool fails its purpose):**
- Enforcement that survives the app being closed (hooks, not app) — trust foundation.
- Status UI that reflects **hook-enforced reality**, never app-local optimism. If it ever shows "locked" while a hand-edit actually loosened things, trust collapses permanently.
- NTP-true-time boxing of lock, grace, and weekly reset (anti clock-tamper).
- Asymmetric control: easy to tighten, hard to loosen (Beeminder model).
- Grace that can't become an escape hatch: hard daily cap + auto-expiry + auto-re-lock (already in spec).

**Should have (competitive polish, v1.x):**
- A deliberate confirm and/or short pre-delay before grace (One Sec's ~10s pause; PNAS: 36% dismiss after pause).
- Beeminder-style reframing: present disabled loosening as "available again Monday" (a wait), not "denied" (a wall).

**Defer / anti-features (deliberately excluded):**
- Gamification (streaks/XP/forests) — serves retention metrics this tool doesn't have; creates incentives to game the budget.
- Accounts, cloud sync, social/referee, master-off switch, quick presets — each is a new escape hatch or attack surface.

### Architecture Approach

One driving principle: **Rust app = sole writer/signer; PowerShell hooks = sole runtime
enforcer.** No enforcement decision may depend on the app running, and every piece of trust
logic has exactly one authoritative home.

**Major components:**
1. **Trust kernel (Rust)** — canonicalization + HMAC-SHA256 + DPAPI key store + atomic store for `config.yaml`, `config.sanctioned.yaml`, `guard.json`, `.guardkey`.
2. **Mutation engine (Rust)** — direction classifier (tighten/loosen/noop, **Rust-only**), weekly quota (DST-aware Monday reset, computed in Rust only), grace grant.
3. **Enforcement guard (PowerShell)** — integrity verify→auto-revert on SessionStart/UserPromptSubmit (direction-agnostic: reverts anything whose signature doesn't match), plus grace-window re-check with its own NTP. Highest-risk component.
4. **Frontend (vanilla TS/Vite)** — display + edit-intent + live per-field loosen/tighten feedback. Non-authoritative.

The guard never validates edit *direction* — it reverts anything not matching the signature. A PowerShell classifier would be dead weight that can drift. `curfew_guard.ps1` stays the single curfew authority; Rust gets only a display-only mirror of schedule semantics.

### Critical Pitfalls

1. **DPAPI SecureString framing trap** — PowerShell `ConvertTo/From-SecureString` adds UTF-16LE/hex framing incompatible with a Rust raw blob (tell-tale: 64 bytes back instead of 32). Use raw `[ProtectedData]::Protect/Unprotect` on both sides, matched `CurrentUser` scope + same entropy (`None`/`$null`). Byte-for-byte round-trip test = crypto phase exit gate.
2. **HMAC canonicalization** — hash *raw file bytes* (`[IO.File]::ReadAllBytes`, never `Get-Content`); Rust writes UTF-8-no-BOM + LF + fixed trailing newline; key = 32 raw bytes (not its hex string). Never hash the lossy YAML parser's output.
3. **Auto-revert sign-vs-write race + fail-closed brick** — guard firing between config write and guard.json re-sign could revert a legit edit; a state mismatch setting `weekly_spent=3` + grace-used with no recovery bricks the user. Prevention: atomic ordered writes (sanctioned + signed guard.json *before* live config), single-writer lock with guard no-op-on-contention, a revert circuit-breaker, and a DPAPI-gated in-app repair path.
4. **Time pitfalls** — DST-aware tzdb Monday reset (never +7×24h); check clock-tamper BEFORE honoring grace (so a forwarded clock can't launder curfew through grace); refuse to *grant* grace when NTP is unreachable; NTP-true-time window validation so a clock rollback can't replay a stale grace window.
5. **Tauri v2 deny-by-default capabilities** — bite only in release builds; register single-instance first (prevents a double-writer racing guard.json); autostart likely unnecessary since enforcement is in always-on hooks.

## Implications for Roadmap

Suggested coarse phase structure (converged across architecture + pitfalls research):

### Phase 1: Trust Kernel
**Rationale:** The whole revert mechanism is either inert or self-destructive if crypto is wrong — de-risk first.
**Delivers:** canonicalization + HMAC sign/verify, DPAPI key store, atomic store. Includes the **DPAPI + HMAC Rust↔PowerShell interop spike** as the exit gate (Rust reads a blob PowerShell wrote; shared HMAC tag matches across both).
**Avoids:** DPAPI SecureString trap, CRLF/BOM HMAC bugs.

### Phase 2: Mutation Engine
**Rationale:** Editing rules depend on the kernel; classifier correctness is the highest-value correctness surface (one misclassified loosen-as-tighten = silent bypass).
**Delivers:** direction classifier (Rust, unit-tested against a diff table), weekly quota (DST-aware Monday reset), grace grant (NTP-required), atomic commit with single-writer lock.
**Uses:** trust kernel from P1.

### Phase 3: Enforcement Guard
**Rationale:** Highest-risk runtime piece; needs P1 verify + P2 commit semantics to exist first.
**Delivers:** `nightguard_integrity_guard.ps1` (verify→auto-revert, fail-closed paths, circuit-breaker, DPAPI-gated repair), grace-window re-check in `curfew_guard.ps1`, registration in `verify_hook_integrity.ps1`.
**Avoids:** sign-vs-write race, fail-closed brick, tamper-before-grace ordering.

### Phase 4: UI
**Rationale:** Display layer hangs off P2 commands; nothing trusts it.
**Delivers:** Moonlit Indigo main screen (status + countdown, 3-dot token meter, grace KPI, +8 button), edit panel with live per-field feedback.

### Phase 5: Instance Wiring & Polish (optional)
**Rationale:** Daniel-specific deployment + low-cost UX polish, not part of the published product surface.
**Delivers:** point the live hook at the LifeOS canonical config (propagation fix), grace pre-delay/confirm, Beeminder-style reframing.

### Phase Ordering Rationale
- Crypto/interop first because everything downstream trusts it; cheap to spike, catastrophic if wrong.
- Classifier + quota before the guard, because the guard reverts to sanctioned snapshots the mutation engine produces.
- UI last because it's non-authoritative.

### Research Flags
- **Phase 1:** needs the DPAPI/HMAC interop spike (already the riskiest assumption) — keep research-on.
- **Phase 3:** verify **hook-path resolution under Claude Code junctions** before wiring (`$PSScriptRoot\..` may resolve to the drifted `~/.claude/nightguard` instead of the LifeOS canonical — the exact drift bug being fixed).
- **Phase 2/4:** standard patterns — lighter research.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified via crates.io + official v2 docs |
| Features | MEDIUM-HIGH | Strong category consensus; budget-size/delay are personal-tuning, validated by use |
| Architecture | HIGH | Spec + existing hooks authoritative; canonicalization choice MEDIUM |
| Pitfalls | HIGH | DPAPI/line-ending/Tauri verified vs MS + Tauri docs + PowerShell issues |

**Overall confidence:** HIGH

### Gaps to Address
- **HMAC input form (UNRESOLVED — decide in P1 planning):** *raw file bytes* (simplest; app is the sole deterministic writer, so false reverts only ever hit hand-edits we WANT reverted) vs *canonical-JSON projection* (robust to cosmetic reformat, but requires a sanctioned duplicated canonicalizer in Rust + PowerShell with committed conformance vectors). **Recommendation: raw-bytes for v1** unless planning finds a reason cosmetic reformatting must be tolerated.
- **`sntpc 0.10.1` exact API** — verify `sync::get_time` signature + `sntpc-net-std` wiring at integration.
- **PowerShell minimal YAML parser tolerance** — round-trip test `yamlpatch` output against the actual `LifeOS/hooks` parser (flow vs block, quoting).
- **DPAPI blob encoding on the PowerShell side** — if stored base64 in a text file, Rust must base64-decode before decrypt.
- **Autostart necessity** — likely droppable (enforcement is in always-on hooks).

## Sources

### Primary (HIGH confidence)
- Microsoft Learn — CryptProtectData / ProtectedData.Protect (DPAPI raw-blob semantics)
- Tauri v2 official docs — prerequisites, capabilities, IPC, single-instance
- crates.io — tauri 2.11.2, hmac 0.12.1, sha2 0.10.9, sntpc 0.10.1, windows-dpapi 0.2.0, yamlpath 1.25.2

### Secondary (MEDIUM confidence)
- Beeminder, SelfControl (#28 clock-tamper), Cold Turkey, One Sec (PNAS pause study), AppBlock — category UX patterns
- PowerShell issue #25246, serde_yaml issue #145 — canonicalization + comment-preservation footguns

### Tertiary (LOW confidence)
- General scarcity/commitment-device UX writing — budget-size and pre-delay efficacy (population-level, not this-user-specific)

---
*Research completed: 2026-06-04*
*Ready for roadmap: yes*
