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
- [x] **RULE-05**: "+8" grants a once-per-true-day 8-minute grace window recorded in signed state; refused if already used today or if NTP is unreachable.
- [x] **RULE-06**: Every sanctioned commit atomically writes the sanctioned snapshot and signed state *before* the live config, re-signing all artifacts.

### Enforcement Guard

- [x] **GARD-01**: On SessionStart + UserPromptSubmit, the guard verifies the config HMAC and auto-reverts to the sanctioned snapshot on mismatch (direction-agnostic).
- [x] **GARD-02**: If the sanctioned snapshot is also invalid, the guard writes a hardcoded strict default and logs the event (fail-closed).
- [x] **GARD-03**: If signed state is invalid/tampered, the guard treats `weekly_spent=3` and grace-as-used until the app re-syncs, with a DPAPI-gated in-app repair path (fail-closed).
- [x] **GARD-04**: The curfew gate honors an active grace window — re-checked with the guard's own NTP and tamper-checked first — and re-locks after it expires.
- [x] **GARD-05**: The guard never reverts a legitimate in-app write (atomic write ordering + single-writer lock + revert circuit-breaker prevent the sign-vs-write race).
- [x] **GARD-06**: The integrity guard is registered in `verify_hook_integrity.ps1`'s SHA256 baseline so altering/removing it raises an alert.

### UI (Moonlit Indigo)

- [x] **UI-01**: The main screen shows lock status (🌙 LOCKED / OPEN) and a live countdown reflecting hook-enforced reality (never app-local optimism).
- [x] **UI-02**: The main screen shows the 3-dot weekly token meter with next-reset, and today's grace availability.
- [x] **UI-03**: The "+8 minutes" button is enabled only during an active lock when grace is available, and grants the window on press.
- [x] **UI-04**: The edit panel shows per-field inputs with live tighten/loosen feedback and disables commit with a reason when loosening at 0 tokens.
- [x] **UI-05**: The interface implements the Moonlit Indigo palette + Roboto + left-icon-rail / flat-card layout.

### Instance Wiring (author's deployment)

- [ ] **WIRE-01**: The live curfew hook reads the canonical config directly (propagation fix), eliminating the `~/.claude` vs LifeOS drift.
- [ ] **WIRE-02**: The author's instance (`LifeOS/nightguard`) is configured as the app's target config path, with key + state initialized.

## v2.0 Requirements · Linux Port

**Defined:** 2026-06-22 (ingested from `docs/linux-port-brief.md`; supersession delta in `.planning/INGEST-CONFLICTS.md`)
Phases 6–10 continue the v1.0 phase numbering. Critical path: **6 → 7 → 10**.

### Config Cleanup (Phase 6)

- [ ] **LXCF-01**: The `config.yaml` blocking model is redefined for Linux — the dead Windows `uwp` StayFree `package_id` entry is removed; targets become `browser_extension` (StayFree, policy-managed) + `native_apps` (Hyprland window-class blacklist).
- [ ] **LXCF-02**: The Rust config writer and the Python watchdog agree on the new schema (round-trips through canonical bytes; the watchdog's minimal YAML parser still reads it); HMAC sign/verify is unaffected.

### Root Integrity Wall (Phase 7)

- [ ] **ROOT-01**: The `.guardkey` (32 bytes) and `config.sanctioned.yaml` move to root ownership (key root:root 0600); the user cannot read the key.
- [ ] **ROOT-02**: The watchdog runs as a systemd **system** service (replacing the `--user` 60s timer), verifying true time (clock-tamper), the config HMAC (revert to sanctioned on mismatch), and that the StayFree Chromium managed policy is intact.
- [ ] **ROOT-03**: A root **commit-helper** service exposes a Unix socket that enforces the weekly token quota, signs, and writes the sanctioned artifacts — the only path that can produce a valid signature. The user-run app connects as a client.
- [ ] **ROOT-04**: Hand-forging a valid config is infeasible without the root-owned key; `sudo` is the sole bypass (friction past the impulse threshold, explicitly not an absolute lock).

### Native Blocker (Phase 8)

- [ ] **NBLK-01**: A `--user` systemd service listens on the Hyprland socket2 `openwindow` event and, during an active curfew lock, kills/closes windows whose class is on the `native_apps` blacklist.
- [ ] **NBLK-02**: Blocking is curfew- and grace-aware (honors lock status + active grace from the engine) and event-driven — instant on window open, not a poll loop (no up-to-60s leakage).
- [ ] **NBLK-03**: The native blocker need not be tamper-proof itself; the root watchdog is what prevents disabling it. *(Deferred to phase planning: B2 — SIGKILL vs `hyprctl dispatch closewindow`, per-app or global.)*

### Usage Tracking (Phase 9)

- [ ] **TRAK-01**: ActivityWatch is installed with `aw-watcher-window` + afk feeding `localhost:5600`.
- [ ] **TRAK-02**: A sync script exports screen-time data into LifeOS, replacing StayFree desktop analytics.

### Tauri Port (Phase 10)

- [ ] **PORT-01**: The DPAPI key-store module is replaced by a commit-helper Unix-socket client; the rest of the Rust engine ports unchanged.
- [ ] **PORT-02**: The app recompiles and runs on Linux (CachyOS); the existing `trust-kernel` + `mutation-engine` Rust tests pass unchanged.
- [ ] **PORT-03**: Sanctioned edits from the app go through the root commit-helper (quota enforced server-side); the app never holds the signing key. *(Deferred to phase planning: B3 — StayFree extension lock-down depth + optional `URLBlocklist`.)*

## Backlog (future polish — not scheduled)

- **GRACE-01**: A short pre-delay and/or deliberate confirm before granting grace (One Sec-style pause).
- **GRACE-02**: Beeminder-style reframing copy throughout ("available again Monday", not "denied").

## Out of Scope

| Feature | Reason |
|---------|--------|
| macOS port | Linux + (historical) Windows only |
| DNS/hosts-level sinkhole | Deferred (not dropped) to a later milestone |
| Multi-user / accounts | Single-operator tool |
| Gamification (streaks/XP/forests) | Serves retention metrics this tool lacks; creates incentives to game the budget |
| Cloud sync / social / referee / master-off / quick presets | Each is a new escape hatch or attack surface |
| General-purpose settings editor | Scope is the nightguard curfew config only |
| Absolute unbreakability | User is admin (root); goal is friction past the impulse threshold (`sudo` = the threshold), not a literal lock |

> **Superseded from v1.0 Out of Scope:** "Cross-platform (macOS/Linux) — Windows-bound" — Linux is now the *primary* target (the Windows-bound DPAPI + PowerShell guard are retired). The "Antigravity-side integrity guard" item is moot now that auto-revert is the root systemd watchdog rather than a Windows hook.

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
| RULE-05 | Phase 2 | Complete |
| RULE-06 | Phase 2 | In progress (02-01 sign layer + guard.json state model; full ordered commit closes in 02-04) |
| GARD-01 | Phase 3 | Complete |
| GARD-02 | Phase 3 | Complete |
| GARD-03 | Phase 3 | Complete |
| GARD-04 | Phase 3 | Complete |
| GARD-05 | Phase 3 | Complete |
| GARD-06 | Phase 3 | Complete |
| UI-01 | Phase 4 | Complete |
| UI-02 | Phase 4 | Complete |
| UI-03 | Phase 4 | Complete |
| UI-04 | Phase 4 | Complete |
| UI-05 | Phase 4 | Complete |
| WIRE-01 | Phase 5 | Complete |
| WIRE-02 | Phase 5 | Complete |
| LXCF-01 | Phase 6 | Pending |
| LXCF-02 | Phase 6 | Pending |
| ROOT-01 | Phase 7 | Pending |
| ROOT-02 | Phase 7 | Pending |
| ROOT-03 | Phase 7 | Pending |
| ROOT-04 | Phase 7 | Pending |
| NBLK-01 | Phase 8 | Pending |
| NBLK-02 | Phase 8 | Pending |
| NBLK-03 | Phase 8 | Pending |
| TRAK-01 | Phase 9 | Pending |
| TRAK-02 | Phase 9 | Pending |
| PORT-01 | Phase 10 | Pending |
| PORT-02 | Phase 10 | Pending |
| PORT-03 | Phase 10 | Pending |

**Coverage:**
- v1.0 requirements: 23 total — all mapped, shipped.
- v2.0 requirements: 13 total (LXCF×2, ROOT×4, NBLK×3, TRAK×2, PORT×3) — mapped to phases 6–10.
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-04 (v1.0); 2026-06-22 (v2.0 · Linux Port)*
*Last updated: 2026-06-22 after opening the v2.0 milestone (traceability extended to phases 6–10)*
