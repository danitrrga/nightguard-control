---
phase: 02-mutation-engine
plan: 01
subsystem: infra
tags: [rust, cargo-workspace, serde, hmac, canonicalization, guard-json, interop-contract]

# Dependency graph
requires:
  - phase: 01-trust-kernel
    provides: canonicalize_bytes, atomic_write, write_canonical_text, hmac::{sign_bytes, verify_bytes, tag_to_hex}, StoreError
provides:
  - mutation-engine crate as a workspace member depending on trust-kernel
  - GuardState/LedgerEntry/GraceWindow serde model (the guard.json Phase 3 interop contract)
  - MutationError thiserror enum with From<StoreError> + From<serde_json::Error>
  - Locked state_hmac derivation recipe (Assumption A3), byte-reproducible
  - sign::sign_config canonical-bytes signing helper (sign-the-canonical-bytes invariant)
  - Placeholder module surface (classify/commit/grace/ntp/quota/week) for downstream plans
affects: [02-02-classify-quota-week, 02-03-ntp, 02-04-commit-grace, 02-05-state-parity, 03-enforcement-guard]

# Tech tracking
tech-stack:
  added: [chrono, chrono-tz 0.10.4, sntpc 0.10.1, sntpc-net-std 1.2.1, fd-lock 4.0.4, yamlpath 1.25.2, yamlpatch 1.25.2, serde 1, serde_json 1, thiserror, hex 0.4.3]
  patterns: [per-crate thiserror error enum + From folding, sign-the-canonical-bytes invariant, integration tests in tests/ with CARGO_TARGET_TMPDIR scratch dirs, module //! doc cites the RULE/invariant]

key-files:
  created:
    - crates/mutation-engine/Cargo.toml
    - crates/mutation-engine/src/lib.rs
    - crates/mutation-engine/src/state.rs
    - crates/mutation-engine/src/sign.rs
    - crates/mutation-engine/src/classify.rs (placeholder)
    - crates/mutation-engine/src/commit.rs (placeholder)
    - crates/mutation-engine/src/grace.rs (placeholder)
    - crates/mutation-engine/src/ntp.rs (placeholder)
    - crates/mutation-engine/src/quota.rs (placeholder)
    - crates/mutation-engine/src/week.rs (placeholder)
    - crates/mutation-engine/tests/state.rs
  modified:
    - Cargo.toml (workspace members array only)
    - Cargo.lock (new deps resolved)

key-decisions:
  - "state_hmac recipe LOCKED (A3): serialize GuardState with state_hmac blanked to \"\", canonicalize_bytes, sign_bytes, tag_to_hex — byte-reproducible regardless of the field's prior value"
  - "sign_config returns BOTH the hex tag and the canonical bytes so the caller writes exactly the bytes that were signed (Pitfall 3 / T-02-02)"
  - "guard.json field names/types locked as the Phase 3 PowerShell interop contract (A1); GuardState derives PartialEq for round-trip assertions"
  - "sntpc 0.10.1 pairs with sntpc-net-std 1.2 (adapter crates version independently) — confirmed by a clean dependency-tree resolve"

patterns-established:
  - "Per-crate thiserror MutationError enum with prefixed-message voice + From<trust_kernel::StoreError> folding (mirrors KernelError)"
  - "Sign-the-canonical-bytes: HMAC always computed over canonicalize_bytes output; on-disk bytes == signed bytes"
  - "Integration tests in tests/ (not #[cfg(test)] inline) with CARGO_TARGET_TMPDIR + AtomicU64 scratch dirs (mirrors trust-kernel store tests)"

requirements-completed: [RULE-06]

# Metrics
duration: 8min
completed: 2026-06-05
---

# Phase 2 Plan 01: Mutation Engine Scaffold + guard.json Sign Layer Summary

**New mutation-engine workspace crate with the locked guard.json serde model, byte-reproducible state_hmac recipe (A3), and a canonical-bytes config signer that guarantees on-disk bytes equal signed bytes.**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-06-05
- **Tasks:** 2 (Task 2 was TDD: RED → GREEN)
- **Files modified:** 13 (11 created, 2 modified)

## Accomplishments
- Scaffolded `crates/mutation-engine/` as a workspace member depending on trust-kernel; `cargo build -p mutation-engine` resolves the full dependency tree, confirming the sntpc 0.10.1 + sntpc-net-std 1.2 pairing.
- Locked the `guard.json` serde model (GuardState/LedgerEntry/GraceWindow) as the Phase 3 cross-language interop contract; it round-trips through serde_json.
- Implemented the A3 `state_hmac` recipe (blank state_hmac → canonicalize → sign → hex) and proved it byte-reproducible, including blank+refill parity.
- Added `sign::sign_config`, proving config_hmac equals the HMAC of the exact bytes `write_canonical_text` lands on disk, and that CRLF vs LF input yields the identical tag.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create the crate + add it to the workspace** - `bc2ed7a` (feat)
2. **Task 2: guard.json serde model + MutationError + sign helpers (TDD)**
   - RED: `f3e6a3d` (test) — four failing tests
   - GREEN: `3fdc2e6` (feat) — implementation, all four green

_No REFACTOR commit: the GREEN implementation was already minimal and clean._

## Files Created/Modified
- `Cargo.toml` - Added `crates/mutation-engine` to workspace members (surgical, members array only).
- `Cargo.lock` - New dependency tree resolved.
- `crates/mutation-engine/Cargo.toml` - Crate manifest with verified dep pins.
- `crates/mutation-engine/src/lib.rs` - 8 `pub mod` declarations + re-exports of GuardState/GraceWindow/LedgerEntry/MutationError.
- `crates/mutation-engine/src/state.rs` - guard.json serde model + MutationError + `compute_state_hmac` (A3 recipe).
- `crates/mutation-engine/src/sign.rs` - `sign_config` canonical-bytes signer (re-exports `canonicalize_bytes`).
- `crates/mutation-engine/src/{classify,commit,grace,ntp,quota,week}.rs` - `//!`-only placeholders for downstream plans.
- `crates/mutation-engine/tests/state.rs` - 4 integration tests (round-trip, state_hmac reproducibility, sign-the-canonical-bytes, CRLF/LF parity).

## Decisions Made
- **state_hmac recipe (A3):** serialize with `state_hmac=""`, canonicalize, sign, hex. The recipe blanks the field on every computation so a populated `state_hmac` never affects the result — this is what makes the Phase 3 PowerShell guard's re-derivation match.
- **sign_config returns (tag, canonical_bytes):** forces the caller to write the SAME bytes that were signed, closing Pitfall 3 / threat T-02-02 by construction.
- **Two `From` impls on MutationError:** `From<trust_kernel::StoreError>` (folds to `Io`) per the plan, plus `From<serde_json::Error>` (folds to `Serde`) since the state model is JSON-serialized — both keep downstream `?` ergonomic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created minimal state.rs/sign.rs symbols in Task 1**
- **Found during:** Task 1 (crate scaffold)
- **Issue:** The plan's Task 1 `lib.rs` re-exports `GuardState/GraceWindow/LedgerEntry/MutationError` and declares `pub mod state; pub mod sign;`, but those types are implemented in Task 2. The crate could not compile after Task 1 (acceptance criterion `cargo build -p mutation-engine` exits 0) with state.rs/sign.rs as empty `//!` placeholders.
- **Fix:** Created `state.rs` with the struct/enum skeletons (the re-exported symbols) and a one-line `sign.rs` placeholder so Task 1 compiles; Task 2's TDD GREEN step then replaced their bodies with the full implementation and the `compute_state_hmac`/`sign_config` logic.
- **Files modified:** crates/mutation-engine/src/state.rs, crates/mutation-engine/src/sign.rs
- **Verification:** `cargo build -p mutation-engine` exits 0 after Task 1; all 4 tests green after Task 2.
- **Committed in:** `bc2ed7a` (Task 1) then fully implemented in `3fdc2e6` (Task 2 GREEN)

**2. [Rule 2 - Missing Critical] Added From<serde_json::Error> for MutationError**
- **Found during:** Task 2 (state model)
- **Issue:** The plan specifies `From<trust_kernel::StoreError>` but the guard.json model is JSON-serialized; serde_json failures need a typed home for `?` ergonomics in downstream commit/grace plans.
- **Fix:** Added a `Serde(String)` variant (already named in the plan's minimum variant list) and `impl From<serde_json::Error>`.
- **Files modified:** crates/mutation-engine/src/state.rs
- **Verification:** Compiles clean; the variant is part of the plan's required `MutationError` shape.
- **Committed in:** `3fdc2e6`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** Both necessary for the crate to compile per the plan's own acceptance criteria and for downstream error ergonomics. No scope creep — the symbols and variants are exactly those the plan specifies.

## Issues Encountered
- None beyond the deviations above. The dependency tree resolved on the first `cargo build` (no sntpc/net-std version conflict — the documented Pitfall 1 did not materialize because the pins were correct).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The crate compiles, the module surface is declared, and the two foundation contracts (guard.json model + canonical-bytes sign layer) are locked and tested. Downstream plans (02-02 classify/quota/week, 02-03 ntp, 02-04 commit/grace, 02-05 state_hmac parity) can `use mutation_engine::{GuardState, MutationError, sign}` directly.
- The A3 recipe is implemented in Rust and documented in `state.rs`; plan 02-05 must mirror it byte-for-byte in PowerShell as the cross-language parity gate.

## Self-Check: PASSED

All created files exist on disk and all three task commits (`bc2ed7a`, `f3e6a3d`, `3fdc2e6`) are present in git history.

---
*Phase: 02-mutation-engine*
*Completed: 2026-06-05*
