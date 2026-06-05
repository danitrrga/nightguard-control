# Requirements: Nightguard Control

**Defined:** 2026-06-04
**Core Value:** A late-night, impulsive version of the user cannot quietly loosen their own curfew — loosening costs a limited weekly token, and hand-editing the raw config silently reverts.

## v1 Requirements

### Trust Kernel

- [x] **KERN-01**: HMAC-SHA256 sign/verify produces byte-identical results across the Rust app and the PowerShell guard for the same key + input.
- [x] **KERN-02**: A 32-byte signing key is generated once and stored encrypted at rest via Windows DPAPI (CurrentUser), decryptable by both the Rust app and the PowerShell guard (raw `CryptProtectData` blob, no SecureString framing).
- [x] **KERN-03**: Config and state writes are atomic and idempotent (temp → rename), never leaving partial or corrupt files.
- [x] **KERN-04**: The config writer round-trips `config.yaml` so it stays readable by the existing PowerShell minimal YAML parser (format/comments preserved as needed).

### Rules Engine

- [x] **RULE-01**: A per-field direction classifier labels each proposed change `tighten` / `loosen` / `noop` per the spec's field table.
- [x] **RULE-02**: A commit that loosens anything costs exactly 1 of 3 weekly tokens; all-tighten/neutral commits are free; no-op commits do nothing.
- [x] **RULE-03**: The weekly token budget resets at Monday 00:00 in the configured timezone, DST-aware (never naive +7×24h).
- [x] **RULE-04**: A loosening commit is blocked with a clear reason ("available again Monday") when 0 tokens remain.
- [ ] **RULE-05**: "+8" grants a once-per-true-day 8-minute grace window recorded in signed state; refused if already used today or if NTP is unreachable.
- [ ] **RULE-06**: Every sanctioned commit atomically writes the sanctioned snapshot and signed state *before* the live config, re-signing all artifacts.

### Enforcement Guard

- [ ] **GARD-01**: On SessionStart + UserPromptSubmit, the guard verifies the config HMAC and auto-reverts to the sanctioned snapshot on mismatch (direction-agnostic).
- [ ] **GARD-02**: If the sanctioned snapshot is also invalid, the guard writes a hardcoded strict default and logs the event (fail-closed).
- [ ] **GARD-03**: If signed state is invalid/tampered, the guard treats `weekly_spent=3` and grace-as-used until the app re-syncs, with a DPAPI-gated in-app repair path (fail-closed).
- [ ] **GARD-04**: The curfew gate honors an active grace window — re-checked with the guard's own NTP and tamper-checked first — and re-locks after it expires.
- [ ] **GARD-05**: The guard never reverts a legitimate in-app write (atomic write ordering + single-writer lock + revert circuit-breaker prevent the sign-vs-write race).
- [ ] **GARD-06**: The integrity guard is registered in `verify_hook_integrity.ps1`'s SHA256 baseline so altering/removing it raises an alert.

### UI (Moonlit Indigo)

- [ ] **UI-01**: The main screen shows lock status (🌙 LOCKED / OPEN) and a live countdown reflecting hook-enforced reality (never app-local optimism).
- [ ] **UI-02**: The main screen shows the 3-dot weekly token meter with next-reset, and today's grace availability.
- [ ] **UI-03**: The "+8 minutes" button is enabled only during an active lock when grace is available, and grants the window on press.
- [ ] **UI-04**: The edit panel shows per-field inputs with live tighten/loosen feedback and disables commit with a reason when loosening at 0 tokens.
- [ ] **UI-05**: The interface implements the Moonlit Indigo palette + Roboto + left-icon-rail / flat-card layout.

### Instance Wiring (author's deployment)

- [ ] **WIRE-01**: The live curfew hook reads the canonical config directly (propagation fix), eliminating the `~/.claude` vs LifeOS drift.
- [ ] **WIRE-02**: The author's instance (`LifeOS/nightguard`) is configured as the app's target config path, with key + state initialized.

## v2 Requirements

### Grace Polish

- **GRACE-01**: A short pre-delay and/or deliberate confirm before granting grace (One Sec-style pause).
- **GRACE-02**: Beeminder-style reframing copy throughout ("available again Monday", not "denied").

## Out of Scope

| Feature | Reason |
|---------|--------|
| Cross-platform (macOS/Linux) | DPAPI + PowerShell guard are Windows-bound |
| Multi-user / accounts | Single-operator tool |
| Antigravity-side integrity guard | Curfew gate stays cross-agent; auto-revert is PowerShell/Windows for now |
| Gamification (streaks/XP/forests) | Serves retention metrics this tool lacks; creates incentives to game the budget |
| Cloud sync / social / referee / master-off / quick presets | Each is a new escape hatch or attack surface |
| General-purpose settings editor | Scope is the nightguard curfew config only |
| Absolute unbreakability | User is admin; goal is friction past the impulse threshold, explicitly not a literal lock |

## Traceability

Phase mapping finalized by the roadmapper (matches the research-converged layered structure).

| Requirement | Phase | Status |
|-------------|-------|--------|
| KERN-01 | Phase 1 | Complete |
| KERN-02 | Phase 1 | Complete |
| KERN-03 | Phase 1 | Complete |
| KERN-04 | Phase 1 | Complete |
| RULE-01 | Phase 2 | Complete |
| RULE-02 | Phase 2 | Complete |
| RULE-03 | Phase 2 | Complete |
| RULE-04 | Phase 2 | Complete |
| RULE-05 | Phase 2 | Pending |
| RULE-06 | Phase 2 | In progress (02-01 sign layer + guard.json state model; full ordered commit closes in 02-04) |
| GARD-01 | Phase 3 | Pending |
| GARD-02 | Phase 3 | Pending |
| GARD-03 | Phase 3 | Pending |
| GARD-04 | Phase 3 | Pending |
| GARD-05 | Phase 3 | Pending |
| GARD-06 | Phase 3 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| UI-04 | Phase 4 | Pending |
| UI-05 | Phase 4 | Pending |
| WIRE-01 | Phase 5 | Pending |
| WIRE-02 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-04*
*Last updated: 2026-06-04 after roadmap creation (traceability finalized)*
