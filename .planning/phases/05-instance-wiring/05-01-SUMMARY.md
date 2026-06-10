---
phase: 05-instance-wiring
plan: 01
subsystem: infra
tags: [dpapi, hmac, sha256, yaml-canonicalization, ntp, instance-init, interop]

# Dependency graph
requires:
  - phase: 02-mutation-engine
    provides: GuardState serde model + locked compute_state_hmac A3 recipe + most_recent_monday_midnight DST-aware week anchor + state_interop_cli harness
  - phase: 01-trust-kernel
    provides: load_or_create_key (DPAPI Scope::User), canonicalize_bytes, sign_bytes/tag_to_hex
provides:
  - Reusable Rust `init-instance <data_dir>` subcommand in state_interop_cli (writes a real armed, A3-signed instance — never fixed test state)
  - Initialized LifeOS/nightguard data dir (config.yaml, config.sanctioned.yaml, guard.json, .guardkey) that verifies byte-identically in Rust AND PowerShell
  - NIGHTGUARD_DIR (User scope) set to the canonical LifeOS path, readable from a fresh process
affects: [05-02-PLAN, 05-03-PLAN, instance-wiring, cutover]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Instance-init seam: compose existing analogs (canonicalize_bytes + load_or_create_key + compute_state_hmac A3 + most_recent_monday_midnight) into one init-instance subcommand — no fixed/test state on the init path"

key-files:
  created:
    - "C:/Users/20252128/dev/Projects/LifeOS/nightguard/config.sanctioned.yaml (byte-exact revert target)"
    - "C:/Users/20252128/dev/Projects/LifeOS/nightguard/guard.json (A3-signed armed initial state)"
    - "C:/Users/20252128/dev/Projects/LifeOS/nightguard/.guardkey (DPAPI CurrentUser 32-byte key)"
  modified:
    - "crates/mutation-engine/src/bin/state_interop_cli.rs (added init-instance subcommand)"
    - "C:/Users/20252128/dev/Projects/LifeOS/nightguard/config.yaml (normalized to canonical bytes; content no-op — already canonical)"

key-decisions:
  - "init-instance reuses the single locked compute_state_hmac A3 recipe, load_or_create_key (DPAPI Scope::User, None entropy), and most_recent_monday_midnight (DST-aware) — no duplicate canonicalize+HMAC, no naive +7*24h week math, no fixed test state on the init path."
  - "config.sanctioned.yaml is seeded as a byte-identical copy of the canonicalized config.yaml so Test-SanctionedValid identity (HMAC(sanctioned) == guard.json config_hmac) holds by construction."
  - "Plan 01 sets NIGHTGUARD_DIR (User scope) and writes the signed instance WITHOUT touching settings.json or the watchdog task — the legacy curfew gate keeps protecting until Plan 03's gated cutover (T-05-05 accepted)."

patterns-established:
  - "Instance-init seam: a real armed signed instance is produced by composing the already-proven primitives rather than re-deriving any signature recipe."

requirements-completed: [WIRE-02, WIRE-01]

# Metrics
duration: ~15min
completed: 2026-06-10
---

# Phase 5 Plan 01: Instance Init — LifeOS instance initialized and verifying Summary

**Author's LifeOS nightguard instance initialized: NIGHTGUARD_DIR (User scope) set, config canonicalized + sanctioned copy seeded, DPAPI key generated, and a fully-armed A3-signed guard.json that verifies byte-identically in both Rust and PowerShell — via a reusable `init-instance` Rust subcommand, without touching the live curfew gate.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-06-10
- **Tasks:** 2 (1 auto + 1 human-verify checkpoint)
- **Files modified:** 1 source + 4 instance data files

## Accomplishments
- Added `init-instance <data_dir>` subcommand to `state_interop_cli` that writes a real armed, A3-signed instance (not fixed test state), reusing `compute_state_hmac`, `load_or_create_key`, and `most_recent_monday_midnight`.
- Set NIGHTGUARD_DIR (User scope) = `C:\Users\20252128\dev\Projects\LifeOS\nightguard`; a freshly-spawned process reads it back (D-08).
- Initialized the LifeOS/nightguard data dir: canonicalized config.yaml, byte-identical config.sanctioned.yaml, DPAPI `.guardkey`, and a fully-armed guard.json (D-09, D-10).
- Proved cross-language parity on a real Windows CurrentUser session: state_hmac and config_hmac re-derive identically in Rust and PowerShell; `verify-state-hmac` exits 0; DPAPI key unprotects to exactly 32 bytes.

## Task Commits

1. **Task 1: Add init-instance subcommand to state_interop_cli** - `f888d41` (feat)
2. **Task 2: Set NIGHTGUARD_DIR + run init-instance (human-verify checkpoint)** - no source commit (live instance-file operation, user-approved; instance files live outside the repo under LifeOS/nightguard)

**Plan metadata:** this commit (docs: complete plan)

## Files Created/Modified
- `crates/mutation-engine/src/bin/state_interop_cli.rs` - Added the `init-instance <data_dir>` subcommand to the argv match dispatch; resolves the fixed paths under data_dir, canonicalizes config.yaml, seeds the byte-identical sanctioned copy, generates+DPAPI-protects the key, computes config_hmac over the canonical bytes, and writes the A3-signed armed guard.json.
- `C:/Users/20252128/dev/Projects/LifeOS/nightguard/config.yaml` - Normalized to canonical bytes (UTF-8, no BOM, LF, one trailing LF). Content unchanged — the file was already canonical, so the rewrite was a byte/content no-op. Curfew start "20:45" / end "05:30", watchdog.enabled true (+ StayFree package), clock_protection, and the Spanish-butler curfew/tamper/offline messages are all intact (858 B).
- `C:/Users/20252128/dev/Projects/LifeOS/nightguard/config.sanctioned.yaml` - Byte-identical copy of the canonicalized config.yaml (858 B) — the revert target. HMAC(config.sanctioned.yaml) == guard.json config_hmac (Test-SanctionedValid identity holds).
- `C:/Users/20252128/dev/Projects/LifeOS/nightguard/guard.json` - A3-signed armed initial state (231 B): config_hmac=7618454633260f47c31f3ec4387b75138e83392d47d59b54f2709e14e0af0da5, state_hmac=94d82214d3ae6cf19d89b99f7db238953923853cf9fc153ca0c88d6dd7967739, weekly_spent=0 (3 tokens available), week_anchor="2026-06-08", ledger=[], grace=null.
- `C:/Users/20252128/dev/Projects/LifeOS/nightguard/.guardkey` - DPAPI CurrentUser raw blob (262 B) wrapping a 32-byte signing key (Scope::User, None entropy).

## Verification Evidence (Task 2 — all PASS)
- NIGHTGUARD_DIR (User scope) reads back in a fresh process = `C:\Users\20252128\dev\Projects\LifeOS\nightguard`.
- All four data files present with the armed values above; the live curfew gate was NOT touched.
- Rust `verify-state-hmac .guardkey guard.json 94d8...` → exit 0.
- PowerShell (guard's Get-RuntimeStateHmac A3 recipe) state_hmac re-derive = 94d8... (== Rust).
- PowerShell Get-FileHmacHex over config.yaml = 7618... (== guard.json config_hmac).
- PowerShell Get-FileHmacHex over config.sanctioned.yaml = 7618... (sanctioned identity holds).
- DPAPI .guardkey unprotects to exactly 32 bytes.

## Decisions Made
- See key-decisions in frontmatter: reuse-the-locked-primitives (no duplicate recipe / no naive week math / no fixed state), sanctioned-is-a-byte-identical-copy, and set-the-var-without-touching-the-live-gate.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None. NIGHTGUARD_DIR was unset in all scopes at the start (anticipated Pitfall 1); setting it was the expected Task 2 step and did not disturb the legacy gate.

## User Setup Required
None - the human-verify checkpoint and env-var set were performed and verified during execution.

## Carry-forward for Plans 02 / 03
- **NIGHTGUARD_DIR is already set (User scope)** — Plans 02/03 should NOT re-set it; treat it as the single resolution input.
- **The live curfew gate is still the old hook (untouched).** The instance now exists and verifies, but the legacy gate keeps protecting until Plan 03's prove-then-switch cutover (settings.json swap + watchdog restart happen LAST). WIRE-01 is only partially advanced — drift is not eliminated until the Plan 03 cutover.
- The reusable `init-instance` subcommand is available for re-initialization if ever needed.

## Next Phase Readiness
- Instance initialized, armed, and verifying in both languages — the prove-then-switch precondition (D-11) for the cutover is satisfied.
- Plan 02 (build deployable hooks) can proceed; Plan 03 (cutover) remains the last step before the phase is complete.

## Self-Check: PASSED
- FOUND: crates/mutation-engine/src/bin/state_interop_cli.rs (commit f888d41)
- FOUND: C:/Users/20252128/dev/Projects/LifeOS/nightguard/{config.yaml, config.sanctioned.yaml, guard.json, .guardkey}
- FOUND: commit f888d41 (Task 1)
- Note: instance data files live outside the repo (LifeOS/nightguard) by design and are not tracked here.

---
*Phase: 05-instance-wiring*
*Completed: 2026-06-10*
