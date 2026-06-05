---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: "Phase 2 Plan 02 (classify/quota/week pure logic) COMPLETE. 43 new tests green (27 classify + 7 week + 9 quota), full crate 47/47; RULE-01/02/03/04 done. NEXT: 02-03-PLAN.md (NTP true-time module)."
last_updated: "2026-06-05T09:30:00.000Z"
last_activity: 2026-06-05 -- Phase 02 Plan 02 complete
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 8
  completed_plans: 5
  percent: 31
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-04)

**Core value:** A late-night, impulsive version of the user cannot quietly loosen their own curfew — loosening costs a limited weekly token, and hand-editing the raw config silently reverts.
**Current focus:** Phase 02 — mutation-engine

## Current Position

Phase: 02 (mutation-engine) — EXECUTING
Plan: 3 of 5
Next: 02-03-PLAN.md (NTP true-time module behind a TrueTime trait, RULE-05)
Status: Executing Phase 02
Last activity: 2026-06-05 -- Phase 02 Plan 02 complete

Phase progress: [██░░░░░░░░] 1/5 phases complete (Phase 02: 2/5 plans)

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 1 P01-02 | 5 | 2 tasks | 8 files |
| Phase 1 P01-03 | 10 | 3 tasks | 5 files |
| Phase 2 P02-01 | 8 | 2 tasks | 13 files |
| Phase 2 P02-02 | 14 | 3 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 1]: DPAPI-stored HMAC key shared by Rust + PowerShell (raw `CryptProtectData` blob, never SecureString framing).
- [Phase 1]: HMAC input form LOCKED to raw file bytes (resolved in 01-01); writer emits one byte form (UTF-8/no-BOM/LF/one-trailing-newline); empty/BOM-only -> single LF.
- [Phase 1]: Atomic write hand-rolled (temp+rename in same parent dir, no tempfile crate) to guarantee atomic same-volume rename on Windows.
- [Phase 2]: Direction classifier is Rust-only; the guard is direction-agnostic (reverts anything not matching the signature).
- [Phase 5]: Propagation fix is instance-level config, not product surface — point the hook at the LifeOS canonical config (zero-copy).
- [Phase 1]: HMAC-SHA256 known-answer vector = HMAC(32x0x0b, "Hi There") derived via an RFC 4231 TC1-faithful oracle (resolved in 01-02); constant-time verify via `verify_slice`, never `==`; signer hashes raw bytes (no internal normalization).
- [Phase 1]: DPAPI key store uses `windows-dpapi` 0.2.0 (`Scope::User`, `None` entropy) — raw `CryptProtectData` blob; 32-not-64 length guard (`KernelError::BadKeyLength`) is the SecureString-framing canary.
- [Phase 1]: Cross-language exit gate PROVEN GREEN — Rust<->PowerShell DPAPI key round-trips to identical 32 bytes both directions, HMAC-SHA256 tags byte-identical both signing directions over raw file bytes, CRLF/BOM tampers flagged both sides; the project's single genuine technical risk is closed.
- [Phase 1]: interop harness is host-agnostic ([ProtectedData]/[HMACSHA256] are .NET framework types identical in pwsh 7 and Windows PowerShell 5.1); signs raw bytes on disk with no re-canonicalization at sign time so cosmetic CRLF/BOM/trailing-newline drift is tamper.
- [Phase 2, 02-01]: state_hmac recipe LOCKED (A3) — serialize GuardState with state_hmac blanked to "", canonicalize_bytes, sign_bytes, tag_to_hex; the field is re-blanked on every computation so its prior value never affects the tag (Phase 3 PS guard must re-derive identically).
- [Phase 2, 02-01]: sign_config returns (hex tag, canonical bytes) so the caller writes EXACTLY the signed bytes (sign-the-canonical-bytes invariant; closes Pitfall 3 / T-02-02 by construction).
- [Phase 2, 02-01]: guard.json field names/types locked as the Phase 3 PowerShell interop contract (A1); GuardState derives PartialEq for round-trip assertions.
- [Phase 2, 02-01]: sntpc 0.10.1 + sntpc-net-std 1.2 pairing confirmed by a clean dependency-tree resolve (Pitfall 1 did not materialize).
- [Phase 2, 02-02]: Defensive A2 covers BOTH a missing leaf key (yamlpath query_exact -> Ok(None)) AND structural absence on the path (ExhaustedMapping/ExpectedMapping/Exhausted-/ExpectedList query errors) — all map to field-absent Noop; only malformed YAML folds to Serde (never a panic, never a silent loosen, T-02-05).
- [Phase 2, 02-02]: week reset is DST-aware via from_local_datetime + explicit MappedLocalTime (Ambiguous->earliest deterministic); next_monday_midnight re-derives from the local Monday DATE + 7 days (transition week = 169h), never +7*24h (T-02-06; grep gate = 0).
- [Phase 2, 02-02]: QuotaDecision.next_reset is always populated (upcoming Monday), and decide() applies the lazy week reset to an EFFECTIVE weekly_spent before charging — a stale spent=3 never blocks a fresh-week loosen; blocked reason carries the locked 'available again Monday' substring (RULE-04).

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: DPAPI + HMAC Rust↔PowerShell interop is the single genuine technical risk — must pass the byte-identical round-trip spike as the phase exit gate.
- [Phase 2]: Verify `sntpc 0.10.1` `sync::get_time` signature and `yamlpatch` round-trip against the actual PowerShell minimal YAML parser at integration.
- [Phase 3]: Verify hook-path resolution under Claude Code junctions before wiring (`$PSScriptRoot\..` may resolve to the drifted `~/.claude/nightguard`).

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-05T11:30:00.000Z
Stopped at: Phase 2 Plan 02 COMPLETE — classify.rs (RULE-01 per-field direction classifier), week.rs (RULE-03 DST-aware Monday reset), quota.rs (RULE-02/04 commit-rule token quota); all pure/I-O-free, 43 new tests green (full crate 47/47), no-naive-week grep gate = 0. NEXT: 02-03-PLAN.md (NTP true-time module).
Resume file: .planning/HANDOFF.md
Env note: this machine has Windows PowerShell 5.1 (NOT pwsh 7) — PowerShell scripts/harnesses must stay 5.1-compatible (ASCII, no em-dash literals in -File scripts, gate on $LASTEXITCODE).
