---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: "Completed 01-02 (HMAC-SHA256 + DPAPI key store); KERN-01/KERN-02 done. Next: Plan 01-03 (Rust<->PowerShell byte-identical round-trip exit gate)."
last_updated: "2026-06-04T18:44:59.107Z"
last_activity: 2026-06-04
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 20
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-04)

**Core value:** A late-night, impulsive version of the user cannot quietly loosen their own curfew — loosening costs a limited weekly token, and hand-editing the raw config silently reverts.
**Current focus:** Phase 1 — Trust Kernel

## Current Position

Phase: 1 of 5 (Trust Kernel)
Plan: 3 of 3 in current phase complete
Status: Ready to execute
Last activity: 2026-06-04

Progress: [██████████] 100%

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
- [Phase ?]: [Phase 1]: Cross-language exit gate PROVEN GREEN — Rust<->PowerShell DPAPI key round-trips to identical 32 bytes both directions, HMAC-SHA256 tags byte-identical both signing directions over raw file bytes, CRLF/BOM tampers flagged both sides; the project's single genuine technical risk is closed.
- [Phase ?]: [Phase 1]: interop harness is host-agnostic ([ProtectedData]/[HMACSHA256] are .NET framework types identical in pwsh 7 and Windows PowerShell 5.1); signs raw bytes on disk with no re-canonicalization at sign time so cosmetic CRLF/BOM/trailing-newline drift is tamper.

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

Last session: 2026-06-04T18:44:21.323Z
Stopped at: Completed 01-02 (HMAC-SHA256 + DPAPI key store); KERN-01/KERN-02 done. Next: Plan 01-03 (Rust<->PowerShell byte-identical round-trip exit gate).
Resume file: None
