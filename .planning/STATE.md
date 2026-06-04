# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-04)

**Core value:** A late-night, impulsive version of the user cannot quietly loosen their own curfew — loosening costs a limited weekly token, and hand-editing the raw config silently reverts.
**Current focus:** Phase 1 — Trust Kernel

## Current Position

Phase: 1 of 5 (Trust Kernel)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-06-04 — Roadmap created (5-phase layered build)

Progress: [░░░░░░░░░░] 0%

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

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 1]: DPAPI-stored HMAC key shared by Rust + PowerShell (raw `CryptProtectData` blob, never SecureString framing).
- [Phase 1]: HMAC input form (raw-bytes vs canonical-JSON) UNRESOLVED — decide in P1 planning; research recommends raw-bytes for v1.
- [Phase 2]: Direction classifier is Rust-only; the guard is direction-agnostic (reverts anything not matching the signature).
- [Phase 5]: Propagation fix is instance-level config, not product surface — point the hook at the LifeOS canonical config (zero-copy).

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

Last session: 2026-06-04
Stopped at: Roadmap and STATE initialized; requirements traceability mapped to 5 phases.
Resume file: None
