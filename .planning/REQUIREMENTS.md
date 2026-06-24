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
**Curated:** 2026-06-22 via Musk's algorithm (`.planning/phases/REVIEWS.md`) — deleted the socket commit-helper (sign via `sudo`); folded the native blocker into the watchdog tick; reshaped the app from Tauri → omarchy TUI thin-client over the one Python stack. The unifying primitive: **one root key → one root watchdog → one signer (control-CLI behind sudo) → one config schema → one HMAC (Python).**
Phases 6–10 continue the v1.0 phase numbering. Critical path: **6 → 7 → 8 → 10**.

> **P0 (highest-risk, do before any phase work):** the Linux Python trust stack
> (`ngcommon.py`/`guard.py`/control-CLI/`nightguard_watchdog.py`) is the load-bearing security
> layer and is currently **untracked + absent from disk** (only stale `.pyc`). Restore it and
> get it into version control — it's also the standing 06-02 blocker.

### Config Cleanup (Phase 6)

- [x] **LXCF-01**: The `config.yaml` blocking model is redefined for Linux — the dead Windows `uwp` StayFree `package_id` entry is removed; targets become `browser_extension` (StayFree, policy-managed) + `native_apps` (Hyprland window-class blacklist).
- [x] **LXCF-02**: The Python stack (`ngcommon.py` parser + signer) reads and signs the new schema (canonical-bytes round-trip; the minimal YAML parser handles it; HMAC unaffected). The repo's Rust classifier (06-01) agrees on the schema *shape* for product hygiene, but Linux runtime uses the **single Python crypto stack** — cross-language byte-parity is no longer a runtime requirement (it returns only if a Rust signer is ever revived). *(Narrowed 2026-06-22 per curation.)*

### Root Integrity Wall (Phase 7)

- [x] **ROOT-01**: The `.guardkey` (32 bytes) and `config.sanctioned.yaml` move to root ownership (key root:root 0600); the user cannot read the key.
- [x] **ROOT-02**: The watchdog runs as a systemd **system** service (replacing the `--user` 60s timer), verifying true time (clock-tamper), the config HMAC (revert to sanctioned on mismatch), and that the StayFree Chromium managed policy is intact.
- [x] **ROOT-03**: Allowed edits are signed by **elevating to the existing control-CLI via `sudo`/`pkexec`** — no bespoke daemon or socket. The root-owned key makes the control-CLI the sole signer; it enforces the weekly token quota in-process and writes under flock. The sudo prompt is deliberate anti-impulse friction (aligned with ROOT-04) and idiomatic in the terminal/TUI app. *(Curated 2026-06-22: the Unix-socket commit-helper was deleted — see `.planning/phases/REVIEWS.md`.)*
- [x] **ROOT-04**: Hand-forging a valid config is infeasible without the root-owned key; `sudo` is the sole bypass (friction past the impulse threshold, explicitly not an absolute lock). Satisfied by construction once ROOT-01 + ROOT-03 hold.

### Curfew Hook — Linux enforcement (Phase 7.1 — gap-closure)

- [x] **CURF-01**: `guard.py` is wired as the Claude Code curfew hook so its verdict is actually enforced on Linux — during curfew a session/prompt is blocked with the butler deny message; outside curfew (and during an active grace window) it is allowed. The hook reads the canonical LifeOS config (no `~/.claude` drift; mirrors WIRE-01) and runs the guard in user soft-mode (integrity stays the root watchdog's job). *(Discovered 2026-06-22: the verdict engine returns `deny` correctly but no hook fires it — the Linux equivalent of the retired Windows `nightguard_adapter.ps1` was never wired.)*

### Native Blocker (Phase 8 — DESCOPED 2026-06-23)

> **Descoped per user decision (2026-06-23):** native-app blocking is not needed; the curfew layer (Claude-Code hook block + config-revert + root-locked StayFree browser policy) is sufficient. Phase 8 was executed then reverted from the live trust stack (LifeOS `3e64c81`). The three requirements below are dropped, not delivered.

- [~] **NBLK-01** *(descoped)*: The **root watchdog tick** (the same systemd *system* service from ROOT-02), during an active curfew lock, enumerates Hyprland clients and kills/closes windows whose class is on the `native_apps` blacklist — **no separate service**.
- [~] **NBLK-02** *(descoped)*: Killing is curfew- and grace-aware (reuses the watchdog's lock/grace state). Cadence = the watchdog tick (**≤60s leakage accepted for v1**; an instant socket2 listener is a deferred "accelerate" step, built only if 60s proves inadequate with evidence).
- [~] **NBLK-03** *(descoped)*: Because the kill lives **inside the root watchdog**, it is un-stoppable from user space (no `systemctl --user stop` escape). *(B2 kill mechanism — SIGKILL vs `hyprctl dispatch closewindow` — settled in phase planning.)* *(Curated 2026-06-22: folded into the watchdog tick — see REVIEWS.md.)*

### Usage Tracking (Phase 9)

- [ ] **TRAK-01**: `stayfree-desktop` (AUR) is installed as the intended screen-time/analytics source on Linux; ActivityWatch is retired (parked idea, never deployed). **Spike caveat (D-09, 2026-06-24): StayFree records 0 sessions under Hyprland/Wayland** — its X11-only window detection sees neither native Wayland nor XWayland apps on this box, so live screen-time capture is effectively non-functional on Wayland. The durable value is config, not live usage (see TRAK-02).
- [ ] **TRAK-02**: StayFree's local store is clean, offline-readable SQLite (`~/.config/StayFree/config.db`, `usage.db` — knex schema), not an opaque leveldb. Acceptable v1 for *usage* analytics = "view in StayFree's own UI" — but that is moot here because tracking is dead on Wayland (`usage.db.sessions` is empty). What **is** fully recoverable offline is the **blocklist/config**: `preferences/categories` (app/domain→category memberships), `app-groups` (brand→domains/apps), and exported `genericWebsiteLimits` (schedules + target IDs) all resolve without the cloud — usable to seed Nightguard's own enforcement. A live-usage scraper is moot (no data) and out of scope.

### Linux App (Phase 10 — omarchy TUI, was "Tauri Port")

- [ ] **PORT-01**: The Linux app is a **terminal/TUI** app (not Tauri) — omarchy-native, command-driven, minimal aesthetic, themed live via **aether** for responsive colors that track the desktop theme.
- [ ] **PORT-02**: The TUI is a **thin client over the one Python trust stack** — it reads state from `guard.json`/the guard and signs allowed edits by invoking the control-CLI via `sudo`/`pkexec` (ROOT-03). It does **not** re-implement signing, so Linux runs a **single HMAC implementation** (no second crypto stack to keep in byte-parity).
- [ ] **PORT-03**: The TUI never holds the signing key; the weekly quota is enforced by the control-CLI. *(Phase-planning choices: exact TUI stack; aether theming integration; B3 StayFree lock-down depth + optional `URLBlocklist` lands here or in P7.)* *(Curated 2026-06-22: Tauri → omarchy TUI thin-client — see REVIEWS.md.)*

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
| LXCF-01 | Phase 6 | Complete |
| LXCF-02 | Phase 6 | Complete |
| ROOT-01 | Phase 7 | Complete |
| ROOT-02 | Phase 7 | Complete |
| ROOT-03 | Phase 7 | Complete |
| ROOT-04 | Phase 7 | Complete |
| CURF-01 | Phase 7.1 | Complete |
| NBLK-01 | Phase 8 | Descoped (2026-06-23) |
| NBLK-02 | Phase 8 | Descoped (2026-06-23) |
| NBLK-03 | Phase 8 | Descoped (2026-06-23) |
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
