---
phase: 02-mutation-engine
plan: 05
subsystem: interop
tags: [rust, powershell, interop, state-hmac, hmac, dpapi, exit-gate, a3, powershell-5.1]

# Dependency graph
requires:
  - phase: 02-mutation-engine
    plan: 01
    provides: GuardState/LedgerEntry/GraceWindow model, GuardState::compute_state_hmac (locked A3 recipe)
  - phase: 01-trust-kernel
    provides: load_or_create_key, canonicalize_bytes, hmac::{sign_bytes, tag_to_hex}, DPAPI interop helpers + run_interop_gate.ps1 template
provides:
  - state_interop_cli Rust bin (emit-state-hmac / verify-state-hmac) — Rust side of the state_hmac gate
  - scripts/interop/state_interop.ps1 (Get-StateHmacHex) — PS re-derivation of the A3 recipe
  - scripts/interop/run_state_interop_gate.ps1 — green PS 5.1 exit gate proving state_hmac byte-parity both directions
  - Assumption A3 CLOSED in-phase (state_hmac byte-reproducible Rust<->PowerShell)
affects: [03-enforcement-guard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "state_hmac cross-language gate mirrors the Phase 1 config-HMAC gate exactly: Rust bin emits the EXACT pre-sign canonical bytes (.signbytes) so PS HMACs the identical bytes with NO sign-time re-canonicalization"
    - "shared 32-byte key via DPAPI blob — PS protects a known key, Rust load_or_create_key unprotects the same blob — so both hold identical raw key bytes"

key-files:
  created:
    - crates/mutation-engine/src/bin/state_interop_cli.rs
    - scripts/interop/state_interop.ps1
    - scripts/interop/run_state_interop_gate.ps1
  modified:
    - crates/mutation-engine/Cargo.toml

key-decisions:
  - "state_interop_cli reuses GuardState::compute_state_hmac (the single locked A3 recipe) — there is NO second state_hmac computation; the .signbytes file is derived from the same blank-then-canonicalize step the recipe signs"
  - "the PS side signs the Rust-emitted .signbytes verbatim (raw-bytes HMAC, reusing the Phase 1 Get-FileHmacHex), so any cosmetic byte drift would be a tamper, not a parity break — identical to the Phase 1 sign-raw-bytes invariant"
  - "tamper check splits the proof: a guard.json byte-flip makes Rust verify-state-hmac exit 2, a .signbytes byte-flip makes the PS tag differ — proving both sides reject a single-byte change"

requirements-completed: [RULE-06]

# Metrics
duration: 11min
completed: 2026-06-05
---

# Phase 2 Plan 05: Rust<->PowerShell state_hmac Parity Gate Summary

**A Rust bin emits/verifies the locked A3 `state_hmac` over a fixed `GuardState`, and a Windows-PowerShell-5.1-clean harness re-derives the identical tag over the exact pre-sign canonical bytes — proving byte-parity both directions and closing Assumption A3 inside Phase 2 (not deferred to Phase 3).**

## Performance

- **Duration:** ~11 min
- **Completed:** 2026-06-05
- **Tasks:** 2
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments
- Added a `[[bin]] state_interop_cli` stanza to `crates/mutation-engine/Cargo.toml` and built `state_interop_cli` — `cargo build -p mutation-engine --bin state_interop_cli` exits 0.
- `emit-state-hmac` builds a FIXED deterministic `GuardState` (known `config_hmac`, `weekly_spent=2`, a representative ledger entry, an active grace window), computes `state_hmac` via the SINGLE locked recipe `GuardState::compute_state_hmac`, writes the filled-in `guard.json` plus the exact pre-sign canonical bytes to `<guard.json>.signbytes`, and prints the 64-hex tag.
- `verify-state-hmac` recomputes the tag via the recipe and exits 0 on match, 2 on mismatch (distinct code, mirroring the Phase 1 `interop_cli`).
- `scripts/interop/state_interop.ps1` provides `Get-StateHmacHex`, which HMAC-SHA256s the Rust-emitted `.signbytes` verbatim with the 32 raw key bytes — reusing the Phase 1 `Get-FileHmacHex` so there is one raw-bytes HMAC path across both gates.
- `scripts/interop/run_state_interop_gate.ps1` builds the bin and runs three checks — Rust->PS byte-identical tag, PS->Rust Rust-verify exit 0, single-byte tamper rejected on both sides — exiting 0 only if all PASS. It ran GREEN under Windows PowerShell **5.1.26100.8115**.

## Gate Output (Windows PowerShell 5.1)

```
Building state_interop_cli (cargo build -p mutation-engine --bin state_interop_cli)...
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.12s

=== Nightguard state_hmac cross-language exit gate (A3) ===
CLI: C:\Users\20252128\dev\Projects\nightguard-control\target\debug\state_interop_cli.exe
Work dir: C:\Users\20252128\dev\Projects\nightguard-control\target\state_interop_gate
PowerShell: 5.1.26100.8115

[PASS] state_hmac Rust->PS -- rust=08814b3ed500df35... ps=08814b3ed500df35... len=64 identical=True
[PASS] state_hmac PS->Rust -- rust verify-state-hmac exit=0 (expect 0)
[PASS] state_hmac Tamper -- rust verify exit=2 (expect 2); ps tag differs=True

=== Summary ===
  state_hmac Rust->PS      PASS
  state_hmac PS->Rust      PASS
  state_hmac Tamper        PASS

ALL CHECKS PASSED -- A3 state_hmac gate is GREEN. The recipe is byte-identical Rust<->PowerShell both directions; a single-byte tamper fails verification on both sides.
exit=0
```

## Task Commits

Each task was committed atomically:

1. **Task 1: state_interop_cli.rs — Rust side of the state_hmac gate** — `ef9da24` (feat)
2. **Task 2: PS 5.1 state_hmac parity gate** — `026440e` (feat)

## Files Created/Modified
- `crates/mutation-engine/Cargo.toml` — added the `[[bin]] state_interop_cli` stanza (mirrors trust-kernel's `interop_cli` stanza shape; surgical, stanza only).
- `crates/mutation-engine/src/bin/state_interop_cli.rs` — argv-matched CLI (no clap, exit 0/1/2) with a `//!` doc citing A3 + the locked recipe; `emit-state-hmac` and `verify-state-hmac` subcommands; reuses `GuardState::compute_state_hmac` (no duplicate recipe).
- `scripts/interop/state_interop.ps1` — dot-sources the Phase 1 helpers and adds `Get-StateHmacHex` over the `.signbytes` file.
- `scripts/interop/run_state_interop_gate.ps1` — the PS 5.1 gate driver: builds the bin, `Invoke-Cli` with relaxed `$ErrorActionPreference` around cargo/CLI stderr gated on `$LASTEXITCODE`, `Add-Check` tally, three parity/tamper checks, exit 0/1.

## Decisions Made
- **Single recipe, exposed bytes:** the bin computes the tag exclusively through `GuardState::compute_state_hmac` (the locked A3 path from plan 02-01). The `.signbytes` file is produced by replaying the recipe's blank-then-`canonicalize_bytes` step on the same state, so the bytes PS signs are exactly the bytes Rust signed — there is no second/duplicate state_hmac computation.
- **Sign raw bytes, no sign-time canonicalization (PS side):** `Get-StateHmacHex` reuses the Phase 1 `Get-FileHmacHex`, HMACing the `.signbytes` verbatim. This is the same invariant the Phase 1 gate enforces — both sides sign identical on-disk bytes, so cosmetic drift is tamper, parity is exact.
- **Shared key via DPAPI blob:** PS protects a known 32-byte key to a blob; Rust `load_or_create_key` unprotects that same blob. Both sides then hold identical raw key bytes (the Phase 1 PS->Rust key pattern), avoiding any key-transport divergence.
- **Two-pronged tamper proof:** Rust-side tamper flips a byte of `guard.json` (verify exits 2); PS-side tamper flips a byte of `.signbytes` (re-derived tag differs). A guarded retry handles the rare case where a random `guard.json` byte-flip breaks JSON parsing (CLI exit 1) by instead flipping an in-string ASCII digit that keeps JSON valid so the recipe — not the parser — detects the change.

## Deviations from Plan

None — plan executed exactly as written. Both tasks delivered the specified artifacts and all acceptance criteria pass.

## Known Stubs

None — both scripts and the bin are fully wired and exercised by the green gate.

## Issues Encountered
- None. The gate passed on the first 5.1 run; the JSON-parse-break retry path in the tamper check was added defensively (middle-byte flip happened to stay valid, so the primary path sufficed).

## Threat Surface
The plan's threat register (T-02-15 byte-divergence, T-02-16 forged guard.json, T-02-17 PS 5.1 vs pwsh host divergence) is fully mitigated by the green gate: byte-parity both directions over identical canonical signbytes, single-byte tamper rejected on both sides, and a clean run under Windows PowerShell 5.1 with ASCII-only / foreach-byte-list / `$LASTEXITCODE`-gated scripts. No new security surface beyond the threat model.

## Next Phase Readiness
- Assumption A3 is CLOSED in-phase: the Phase 3 PowerShell guard can re-derive `state_hmac` byte-for-byte and trust `guard.json` as the interop contract without false-tamper reverts. The `state_interop.ps1` `Get-StateHmacHex` helper and the `.signbytes` emission pattern are the template the Phase 3 guard's state-verification path will follow.
- Carry-forward blocker (unchanged): Phase 3 must verify hook-path resolution under Claude Code junctions before wiring.

## Self-Check: PASSED

All three created files exist on disk; `Cargo.toml` carries the new stanza. Both task commits (`ef9da24`, `026440e`) are present in git history on `plan/phase-02-mutation-engine`. `cargo build -p mutation-engine --bin state_interop_cli` exits 0 and the PS 5.1 gate exits 0 with all checks PASS.

---
*Phase: 02-mutation-engine*
*Completed: 2026-06-05*
