# Roadmap: Nightguard Control

## Overview

Nightguard Control delivers a tamper-evident self-binding curfew tool from the security
core outward. The build is layered: a trust kernel (HMAC + DPAPI + atomic writes) is
de-risked first because every downstream guarantee depends on Rust and PowerShell agreeing
on the same signature. The mutation engine (direction classifier, weekly token quota, NTP
grace) sits on top of the kernel and produces the sanctioned snapshots the guard reverts
to. The PowerShell enforcement guard — the highest-risk runtime piece — comes next, since
it consumes both kernel verification and engine commit semantics. The Moonlit Indigo UI
hangs off the engine commands last because nothing trusts the display layer. Finally,
instance wiring points the author's live LifeOS hook at the canonical config, closing the
`~/.claude` drift bug. Critical path: Phase 1 → Phase 2 → Phase 3.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Trust Kernel** - HMAC + DPAPI + atomic store with a Rust↔PowerShell interop round-trip as the exit gate (completed 2026-06-04)
- [ ] **Phase 2: Mutation Engine** - Direction classifier, weekly token quota, NTP-true grace, atomic ordered commit
- [ ] **Phase 3: Enforcement Guard** - PowerShell verify→auto-revert with fail-closed paths and grace re-check
- [ ] **Phase 4: UI (Moonlit Indigo)** - Status, token meter, +8 button, and live per-field editor feedback
- [ ] **Phase 5: Instance Wiring** - Point the author's live hook at the canonical LifeOS config and initialize the instance

## Phase Details

### Phase 1: Trust Kernel
**Goal**: The cryptographic foundation works identically across Rust and PowerShell — both languages produce the same HMAC over the same input using the same DPAPI-stored key, and every write is atomic.
**Depends on**: Nothing (first phase)
**Requirements**: KERN-01, KERN-02, KERN-03, KERN-04
**Success Criteria** (what must be TRUE):
  1. A 32-byte key written and DPAPI-encrypted (CurrentUser, raw `CryptProtectData` blob) by one side is decrypted by the other to the identical 32 bytes — the DPAPI + HMAC Rust↔PowerShell interop round-trip passes: PowerShell signs an input, Rust verifies the tag, and Rust signs, PowerShell verifies, byte-identical both directions.
  2. The same `config.yaml` bytes hashed via Rust and via PowerShell `[IO.File]::ReadAllBytes` yield identical HMAC-SHA256 tags (no CRLF/BOM/trailing-newline divergence).
  3. A config or state write that is interrupted never leaves a partial or corrupt file — the prior valid file remains intact (temp → atomic rename).
  4. The config writer round-trips `config.yaml` so the existing PowerShell minimal YAML parser still reads it correctly after a write.
**Plans**: 3 plans
  - [x] 01-01-PLAN.md — Scaffold Rust workspace + canonicalization + atomic store (KERN-03, KERN-04)
  - [x] 01-02-PLAN.md — HMAC-SHA256 sign/verify + DPAPI key store, Rust side (KERN-01, KERN-02)
  - [x] 01-03-PLAN.md — Rust↔PowerShell DPAPI+HMAC interop exit gate (KERN-01, KERN-02, KERN-04)

### Phase 2: Mutation Engine
**Goal**: All edit-intent logic lives authoritatively in Rust — every proposed change is classified, loosening is rate-limited against a DST-aware weekly token budget, and grace is granted only against true time, committing atomically in the safe order.
**Depends on**: Phase 1
**Requirements**: RULE-01, RULE-02, RULE-03, RULE-04, RULE-05, RULE-06
**Success Criteria** (what must be TRUE):
  1. Each proposed per-field change is correctly labeled `tighten` / `loosen` / `noop` against the spec's field table (unit-tested against a diff table).
  2. A commit that loosens anything spends exactly 1 of 3 weekly tokens; all-tighten/neutral commits are free; no-op commits change nothing; a loosening commit at 0 tokens is blocked with an "available again Monday" reason.
  3. The weekly token budget resets at Monday 00:00 in the configured timezone, DST-aware (never naive +7×24h).
  4. "+8" grants a once-per-true-day 8-minute grace window recorded in signed state, refused if already used today or if NTP is unreachable.
  5. Every sanctioned commit atomically writes the sanctioned snapshot and signed state *before* the live config, re-signing all artifacts under a single-writer lock.
**Plans**: 5 plans
  - [x] 02-01-PLAN.md — Scaffold mutation-engine crate + guard.json serde model + canonical-bytes sign layer (RULE-06)
  - [x] 02-02-PLAN.md — Pure logic: direction classifier + token quota + DST-aware Monday reset (RULE-01, RULE-02, RULE-03, RULE-04)
  - [x] 02-03-PLAN.md — NTP true-time module behind a TrueTime trait (RULE-05)
  - [ ] 02-04-PLAN.md — fd-lock ordered atomic re-signed commit + once-per-true-day grace (RULE-05, RULE-06)
  - [ ] 02-05-PLAN.md — Rust↔PowerShell state_hmac parity gate (A3 closed in-phase) (RULE-06)

### Phase 3: Enforcement Guard
**Goal**: The always-firing PowerShell guard makes the binding real — out-of-band edits silently revert, tampered state fails closed, grace is honored against the guard's own true time, and the guard cannot revert a legitimate in-app write.
**Depends on**: Phase 2
**Requirements**: GARD-01, GARD-02, GARD-03, GARD-04, GARD-05, GARD-06
**Success Criteria** (what must be TRUE):
  1. A hand-edit to `config.yaml` is auto-reverted to the sanctioned snapshot on the next SessionStart/UserPromptSubmit (HMAC mismatch, direction-agnostic).
  2. If the sanctioned snapshot is also invalid, the guard writes a hardcoded strict default and logs the event (fail-closed, no brick).
  3. If signed state is invalid/tampered, the guard treats `weekly_spent=3` and grace-as-used until the app re-syncs, with a DPAPI-gated in-app repair path available.
  4. The curfew gate honors an active grace window — clock-tamper-checked and re-verified with the guard's own NTP first — and re-locks after it expires.
  5. A legitimate in-app commit is never reverted (atomic write ordering + single-writer lock + revert circuit-breaker prevent the sign-vs-write race), and the guard is registered in `verify_hook_integrity.ps1`'s SHA256 baseline.
**Plans**: TBD

### Phase 4: UI (Moonlit Indigo)
**Goal**: The non-authoritative display + edit-intent layer reflects hook-enforced reality and gives live per-field feedback, in the Moonlit Indigo aesthetic.
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05
**Success Criteria** (what must be TRUE):
  1. The main screen shows lock status (🌙 LOCKED / OPEN) with a live countdown that reflects hook-enforced reality, never app-local optimism.
  2. The main screen shows the 3-dot weekly token meter with next-reset and today's grace availability.
  3. The "+8 minutes" button is enabled only during an active lock when grace is available, and grants the window on press.
  4. The edit panel shows per-field inputs with live tighten/loosen feedback and disables commit with a reason when loosening at 0 tokens.
  5. The interface implements the Moonlit Indigo palette + Roboto + left-icon-rail / flat-card layout.
**Plans**: TBD
**UI hint**: yes

### Phase 5: Instance Wiring
**Goal**: The author's personal LifeOS deployment runs on the published product — the live hook reads the canonical config directly (drift fixed) and the instance is fully initialized with key + state.
**Depends on**: Phase 4
**Requirements**: WIRE-01, WIRE-02
**Success Criteria** (what must be TRUE):
  1. The live curfew hook reads the canonical `LifeOS/nightguard/config.yaml` directly, eliminating the `~/.claude` vs LifeOS drift (verified after confirming hook-path resolution under Claude Code junctions).
  2. The author's instance is configured as the app's target config path, with signing key and signed state initialized and verifying.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Trust Kernel | 3/3 | Complete   | 2026-06-04 |
| 2. Mutation Engine | 3/5 | In progress | - |
| 3. Enforcement Guard | 0/TBD | Not started | - |
| 4. UI (Moonlit Indigo) | 0/TBD | Not started | - |
| 5. Instance Wiring | 0/TBD | Not started | - |
