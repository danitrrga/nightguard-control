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

**Milestone v1.0 (Windows) — shipped:**
- [x] **Phase 1: Trust Kernel** - HMAC + DPAPI + atomic store with a Rust↔PowerShell interop round-trip as the exit gate (completed 2026-06-04)
- [x] **Phase 2: Mutation Engine** - Direction classifier, weekly token quota, NTP-true grace, atomic ordered commit (completed 2026-06-05)
- [x] **Phase 3: Enforcement Guard** - PowerShell verify→auto-revert with fail-closed paths and grace re-check (completed 2026-06-08)
- [x] **Phase 4: UI (Moonlit Indigo)** - Status, token meter, +8 button, and live per-field editor feedback (completed 2026-06-09)
- [x] **Phase 5: Instance Wiring** - Point the author's live hook at the canonical LifeOS config and initialize the instance (completed 2026-06-10)

**Milestone v2.0 · Linux Port — active** (supersedes v1.0; see `.planning/INGEST-CONFLICTS.md`):
- [x] **Phase 6: Config Cleanup** - Retire the dead Windows `uwp`/`package_id` entry; redefine targets as `browser_extension` + `native_apps` (completed 2026-06-22)
- [ ] **Phase 7: Root Integrity Wall** *(highest value)* - Root-own key + sanctioned config; watchdog → systemd system service; sign via `sudo`→control-CLI (socket helper deleted)
- [ ] **Phase 8: Native Blocker** *(folded into the watchdog)* - Root watchdog tick kills blacklisted Hyprland window classes during curfew (≤60s; no separate service)
- [ ] **Phase 9: ActivityWatch** *(parked — optional)* - Install aw-watcher-window + afk; sync screen-time into LifeOS (replaces StayFree analytics)
- [ ] **Phase 10: Linux App (omarchy TUI)** - Terminal/TUI (not Tauri), aether-themed, thin client over the Python control-CLI

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
  - [x] 02-04-PLAN.md — fd-lock ordered atomic re-signed commit + once-per-true-day grace (RULE-05, RULE-06)
  - [x] 02-05-PLAN.md — Rust↔PowerShell state_hmac parity gate (A3 closed in-phase) (RULE-06)

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
**Plans**: 4 plans
  - [x] 03-01-PLAN.md — Parity & probe gate: runtime state-verify check + fd-lock presence probe spike (GARD-03, GARD-05)
  - [x] 03-02-PLAN.md — Guard core: config verify/circuit-breaker/revert/maximal-lockout + state worst-case (GARD-01, GARD-02, GARD-03, GARD-05)
  - [x] 03-03-PLAN.md — Grace/curfew verdict + guard-side SNTP + audit log + JSON output + end-to-end gate (GARD-01, GARD-02, GARD-03, GARD-04, GARD-05)
  - [x] 03-04-PLAN.md — Integrity baseline: verify_hook_integrity.ps1 + self-registered SHA256 manifest (GARD-06)

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
**Plans**: 5 plans
  - [x] 04-01-PLAN.md — Scaffold Tauri v2 (vanilla-TS + Vite) shell as 3rd workspace member + fixed IPC contract (4 commands + DTOs + IpcError + AppCtx) (UI-01, UI-02, UI-03, UI-04)
  - [x] 04-02-PLAN.md — TDD: pure lock_status curfew-window evaluator in mutation-engine (highest-risk net-new logic) (UI-01)
  - [x] 04-03-PLAN.md — Real IPC command bodies: get_state read/re-verify/worst-case + classify/commit/grace wrappers (UI-01, UI-02, UI-03, UI-04)
  - [x] 04-04-PLAN.md — Status view: hero countdown + 🌙 LOCKED/OPEN + 3-dot token meter + plugin-fs watch + 1s tick, Moonlit Indigo styling (UI-01, UI-02, UI-05)
  - [x] 04-05-PLAN.md — Edit panel (live per-field classify + gated/confirmed commit) + "+8 minutes" grace button (UI-03, UI-04, UI-05)
**UI hint**: yes

### Phase 5: Instance Wiring
**Goal**: The author's personal LifeOS deployment runs on the published product — the live hook reads the canonical config directly (drift fixed) and the instance is fully initialized with key + state.
**Depends on**: Phase 4
**Requirements**: WIRE-01, WIRE-02
**Success Criteria** (what must be TRUE):
  1. The live curfew hook reads the canonical `LifeOS/nightguard/config.yaml` directly, eliminating the `~/.claude` vs LifeOS drift (verified after confirming hook-path resolution under Claude Code junctions).
  2. The author's instance is configured as the app's target config path, with signing key and signed state initialized and verifying.
**Plans**: 3 plans
  - [x] 05-01-PLAN.md — Instance init: set NIGHTGUARD_DIR, normalize config to canonical bytes, Rust init-instance bin, generate key + sanctioned + A3-signed armed guard.json (WIRE-02, WIRE-01)
  - [x] 05-02-PLAN.md — Build deployable hooks: adapter (verdict→CC block + allow-pass + butler msgs), watchdog rewrite (canonical config + StayFree), byte-exact install/deploy + integrity re-stamp; confirm CC block schema (WIRE-01)
  - [x] 05-03-PLAN.md — Prove-then-switch cutover: deploy + D-11 verify gate, then retire legacy gate / swap settings.json / restart watchdog LAST (WIRE-01, WIRE-02)

---

## Milestone v2.0 · Linux Port

**Overview**: v2.0 ports the system from Windows to Linux (CachyOS + Hyprland) and moves
the integrity wall behind a **root** privilege boundary. **Curated 2026-06-22 (Musk's
algorithm — see `.planning/phases/REVIEWS.md`)** around one unifying primitive: **one
root-owned key → one root systemd watchdog (verify-revert + true-time + browser-policy +
native-app kill) → one signer (the existing Python control-CLI, reached via `sudo`) → one
config schema → one HMAC implementation (Python).** The Linux runtime is the Python trust
stack; the app is a thin client over it. Sequence: config schema first (P6) so every layer
shares one `blocking:` contract; then the root integrity wall (P7) — root-own the key +
watchdog→systemd-system + sign-via-sudo (the highest-value piece); the native-app kill (P8)
folds into the P7 watchdog tick; ActivityWatch (P9) is parked (orthogonal analytics); the
Linux app (P10) becomes an omarchy **TUI** (not Tauri) that calls the control-CLI to sign.
Critical path: **Phase 6 → Phase 7 → Phase 8 → Phase 10**.

**Curation deltas vs the ingested brief:** ROOT-03 Unix-socket commit-helper → **deleted**
(sign via `sudo`/pkexec to the control-CLI); NBLK separate `--user` socket2 service →
**folded** into the root watchdog tick (≤60s leakage accepted); Phase 10 Tauri + a 2nd Rust
crypto stack → **omarchy TUI thin-client** over the single Python stack.

### Phase 6: Config Cleanup
**Goal**: `config.yaml` describes a Linux blocking model — the dead Windows `uwp`/`package_id` StayFree entry is gone, replaced by `browser_extension` (StayFree, policy-managed) + `native_apps` (Hyprland window-class blacklist) — and both the Rust writer and the Python watchdog read it identically with HMAC sign/verify unaffected.
**Depends on**: Phase 5 (v1.0 engine)
**Requirements**: LXCF-01, LXCF-02
**Success Criteria** (what must be TRUE):
  1. The Windows `uwp` StayFree `package_id` watchdog entry is removed; `config.yaml` defines `browser_extension` + `native_apps` target groups.
  2. The Rust config writer round-trips the new schema through canonical bytes; the Python watchdog's minimal YAML parser reads the same fields.
  3. HMAC sign/verify over the new config is byte-stable across the Rust engine and the Python watchdog (no schema-change drift).
**Plans**: 2 plans
  - [x] 06-01-PLAN.md — Product: re-point the direction-classifier FIELD_TABLE from `watchdog.apps` (uwp) to `blocking.browser_extension` + `blocking.native_apps` + tests (LXCF-01 product half) — **executable now**
  - [x] 06-02-PLAN.md — Instance: re-baseline LifeOS config.yaml/sanctioned to the `blocking:` schema (curfew 20:45), re-sign guard.json via the Python control CLI, prove Rust↔Python HMAC/parse parity + revert (LXCF-01 instance half, LXCF-02) — **⛔ blocked**: Linux Python tooling (ngcommon/guard/control-CLI/watchdog) currently absent from disk; restore before executing

### Phase 7: Root Integrity Wall *(highest value)*
**Goal**: The integrity wall becomes root-backed and unforgeable from user space — the key + sanctioned config are root-owned, the watchdog is a systemd *system* service, and the existing Python control-CLI (reached via `sudo`/`pkexec`) is the sole signer, enforcing the weekly quota in-process. **No bespoke daemon/socket.**
**Depends on**: Phase 6
**Requirements**: ROOT-01, ROOT-02, ROOT-03, ROOT-04
**Curation note (2026-06-22)**: B1 re-decided — the Unix-socket commit-helper is **deleted** in favour of `sudo`-to-the-control-CLI (the sudo prompt IS the anti-impulse friction; zero new infrastructure).
**Success Criteria** (what must be TRUE):
  1. `.guardkey` and `config.sanctioned.yaml` are root-owned (key root:root 0600); a non-root user cannot read the key.
  2. The watchdog runs as a systemd **system** service (not `--user`), verifying true time, the config HMAC (revert to sanctioned on mismatch), and the StayFree managed policy.
  3. Allowed edits are signed by elevating to the control-CLI via `sudo`/`pkexec`; the root key makes it the only producer of a valid signature, and it enforces the weekly token quota + ordered commit under flock.
  4. A hand-edit to `config.yaml` cannot be made to verify without the root-owned key; `sudo` is the only bypass.
**Prereq**: the Python trust stack is restored + version-controlled (P0 / the 06-02 blocker).
**Plans**: 2 plans
  - [ ] 07-01-PLAN.md — Root-own key+sanctioned+state AND watchdog→systemd **system** service, as one prove-then-switch cutover (ROOT-01, ROOT-02) — **⛔ blocked on P0**
  - [ ] 07-02-PLAN.md — Control-CLI signs as root via `sudo` + in-CLI quota + sudoers rule + chown-back (ROOT-03, ROOT-04) — **⛔ blocked on P0 + 07-01**

### Phase 8: Native Blocker *(folded into the root watchdog)*
**Goal**: During an active curfew lock, blacklisted native apps (Steam, Discord, games) are killed/closed by the **root watchdog tick itself** — no separate service. Curated to live inside P7's watchdog so it is un-stoppable from user space.
**Depends on**: Phase 6 (`native_apps` blacklist) + Phase 7 (the root watchdog this extends)
**Requirements**: NBLK-01, NBLK-02, NBLK-03
**Curation note (2026-06-22)**: B2-context — built as a tick extension, not a socket2 listener. ≤60s leakage accepted for v1; an instant socket2 listener is a deferred "accelerate" step only if 60s proves inadequate. Kill mechanism (SIGKILL vs `hyprctl dispatch closewindow`) settled in planning.
**Risk de-risked (2026-06-22)**: the root→user-Hyprland bridge (root watchdog reaching the user-owned `/run/user/1000/hypr` socket) is **verified feasible** — see `08-NOTES-hyprland-from-root.md` for the proven `runuser`-based approach + edge cases. No need to revert the fold-into-root curation.
**Success Criteria** (what must be TRUE):
  1. On each tick during an active curfew lock, the root watchdog enumerates Hyprland clients and kills/closes windows whose class is on the `native_apps` blacklist.
  2. Killing honors lock + active-grace state (no kills outside curfew / during grace); cadence = the watchdog tick (≤60s).
  3. The kill lives inside the **root** watchdog, so it cannot be stopped from user space (`systemctl --user stop` does not apply).
**Plans**: TBD (run `/gsd-plan-phase 8`)

### Phase 9: ActivityWatch
**Goal**: Screen-time tracking is restored on Linux via ActivityWatch and flows into LifeOS, replacing the StayFree desktop analytics that have no Linux client.
**Depends on**: None (independent; can run anytime after Phase 6)
**Requirements**: TRAK-01, TRAK-02
**Success Criteria** (what must be TRUE):
  1. ActivityWatch runs with `aw-watcher-window` + afk feeding `localhost:5600`.
  2. A sync script exports screen-time data into LifeOS on a schedule.
**Plans**: TBD (run `/gsd-plan-phase 9`)

### Phase 10: Linux App — omarchy TUI *(was "Tauri Port")*
**Goal**: The Linux app is the sole sanctioned editor as a **terminal/TUI** — omarchy-native, command-driven, minimal, themed live via *aether* — built as a **thin client over the one Python trust stack** (it calls the control-CLI to sign via `sudo`; never holds the key).
**Depends on**: Phase 7 (root key + sign-via-sudo control-CLI) + Phase 6 (`blocking:` schema)
**Requirements**: PORT-01, PORT-02, PORT-03
**Curation note (2026-06-22)**: dropped Tauri + a 2nd Rust crypto stack → an omarchy TUI thin-client over the single Python stack (one HMAC implementation). Kept in v2.0.
**Open questions for planning**: exact TUI stack/language; *aether* theming integration (live desktop colors); B3 StayFree lock-down depth + optional `URLBlocklist`.
**Success Criteria** (what must be TRUE):
  1. The app is a terminal/TUI with an omarchy-native minimal aesthetic and reads current theme colors via *aether*.
  2. It shows lock status / countdown / token meter / grace and lets the user make edits, reading state from the Python guard/`guard.json` (never app-local optimism).
  3. Allowed edits are signed by invoking the control-CLI via `sudo`/`pkexec`; the app holds no key and re-implements no crypto.
**Plans**: TBD (run `/gsd-plan-phase 10`)
**UI hint**: yes (TUI design + aether theme)

## Progress

**Execution Order:**
Phases execute in numeric order. v1.0: 1 → 2 → 3 → 4 → 5 (shipped).
v2.0 critical path: 6 → 7 → 8 → 10 (8 folds into the P7 watchdog; 10 is the TUI thin-client). Phase 9 (ActivityWatch) is parked/optional.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Trust Kernel | 3/3 | Complete   | 2026-06-04 |
| 2. Mutation Engine | 5/5 | Complete   | 2026-06-05 |
| 3. Enforcement Guard | 4/4 | Complete   | 2026-06-08 |
| 4. UI (Moonlit Indigo) | 5/5 | Complete   | 2026-06-09 |
| 5. Instance Wiring | 3/3 | Complete   | 2026-06-10 |
| 6. Config Cleanup | 2/2 | Complete   | 2026-06-22 |
| 7. Root Integrity Wall | 0/2 | Planned (blocked on P0: restore Python stack) | |
| 8. Native Blocker | 0/— | Not started (folded into P7 watchdog tick) | |
| 9. ActivityWatch | 0/— | Parked (optional) | |
| 10. Linux App (omarchy TUI) | 0/— | Not started (TUI, not Tauri) | |
