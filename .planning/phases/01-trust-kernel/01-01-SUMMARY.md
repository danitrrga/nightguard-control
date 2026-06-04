---
phase: 01-trust-kernel
plan: 01
subsystem: infra
tags: [rust, cargo-workspace, canonicalization, atomic-write, thiserror, hmac-foundation]

# Dependency graph
requires: []
provides:
  - "trust-kernel Rust library crate (plain lib, NOT Tauri) as a workspace member"
  - "canonicalize_bytes: deterministic UTF-8/no-BOM/LF/one-trailing-newline byte form"
  - "atomic_write: crash-safe temp-then-rename in same dir; prior file intact on failure"
  - "write_canonical_text: canonicalize then atomic_write (byte-stable YAML writer)"
  - "StoreError (thiserror) for the file-store error surface"
affects: [hmac-signing, dpapi-key, powershell-guard-interop, tauri-app, config-writer]

# Tech tracking
tech-stack:
  added: [thiserror 1]
  patterns:
    - "Cargo workspace (resolver 2) with crates/ member layout"
    - "TDD RED->GREEN per behavior-adding task (separate test/feat commits)"
    - "Hand-rolled atomic write (temp+rename same dir) — NOT tempfile, to guarantee same-volume atomic rename"
    - "Canonicalize on raw bytes, never String, so non-UTF-8 input cannot panic the signer"

key-files:
  created:
    - Cargo.toml
    - .gitignore
    - .gitattributes
    - crates/trust-kernel/Cargo.toml
    - crates/trust-kernel/src/lib.rs
    - crates/trust-kernel/src/canon.rs
    - crates/trust-kernel/src/store.rs
    - crates/trust-kernel/tests/canon.rs
    - crates/trust-kernel/tests/store.rs
  modified: []

key-decisions:
  - "HMAC input form locked to RAW FILE BYTES; writer emits exactly one byte form (UTF-8/no-BOM/LF/one-trailing-newline)"
  - "Empty-input canonicalization rule locked: empty (or BOM-only) input -> single LF"
  - "Atomic write hand-rolled (temp+rename in same parent dir), no tempfile crate, to guarantee atomic same-volume rename"
  - "No tauri/serde_yaml/hmac/sha2/windows-dpapi/tempfile deps this plan — only thiserror"

patterns-established:
  - "Deterministic byte canonicalization is the single signed form for the whole project"
  - "All config/key/state files write through atomic_write so an interrupted write never corrupts the prior file"
  - "store calls canonicalize_bytes before writing text artifacts (write_canonical_text)"

requirements-completed: [KERN-03, KERN-04]

# Metrics
duration: 3min
completed: 2026-06-04
---

# Phase 1 Plan 01: Trust Kernel Scaffold + Canonicalization + Atomic Store Summary

**A plain Rust `trust-kernel` library crate that turns any input into the project's single signed byte form (UTF-8/no-BOM/LF/one-trailing-newline) and writes it crash-safely via temp-then-rename, fully unit-tested.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-04T18:17:02Z (first task commit)
- **Completed:** 2026-06-04T18:19:54Z (last task commit)
- **Tasks:** 3
- **Files modified:** 9 created

## Accomplishments
- Cargo workspace (resolver 2) with a plain `trust-kernel` library crate — no Tauri, only `thiserror`.
- `canonicalize_bytes`: strips a leading UTF-8 BOM, normalizes CRLF and lone CR to LF, collapses trailing newlines to exactly one, preserves interior blanks, operates on raw bytes (non-UTF-8 safe), idempotent. 13 tests.
- `atomic_write`: unique temp file in the same parent dir → write → flush → `sync_all` → rename; on any failure removes the temp and leaves the prior target byte-for-byte intact. 6 store tests including a deliberate failed-write that proves the prior file survives.
- `write_canonical_text`: canonicalizes then atomically writes, byte-stable across repeated writes of the same logical content (KERN-04) and parser-friendly for the PowerShell minimal YAML reader.
- `cargo build` and `cargo test` both pass from the workspace root; 19 tests green, zero warnings.

## Task Commits

Each task was committed atomically (TDD tasks split test → feat):

1. **Task 1: Scaffold workspace + trust-kernel lib crate** — `ece3159` (chore)
2. **Task 2: Canonicalization** — `29d0973` (test/RED) → `e339ea1` (feat/GREEN)
3. **Task 3: Atomic store + KERN-04 stability** — `a55e753` (test/RED) → `83e177c` (feat/GREEN)

## Files Created/Modified
- `Cargo.toml` — workspace manifest (resolver 2, member `crates/trust-kernel`)
- `.gitignore` — excludes `/target` and runtime secrets (`*.guardkey`, `guard.json`, `config*.yaml`, `tamper.log`)
- `.gitattributes` — forces `config*.yaml` and `*.guardkey` to `-text` (defeats Git autocrlf rewriting the signed bytes)
- `crates/trust-kernel/Cargo.toml` — lib crate, edition 2021, `thiserror = "1"` only
- `crates/trust-kernel/src/lib.rs` — `pub mod canon; pub mod store;` + public re-exports
- `crates/trust-kernel/src/canon.rs` — `canonicalize_bytes`
- `crates/trust-kernel/src/store.rs` — `atomic_write`, `write_canonical_text`, `StoreError`
- `crates/trust-kernel/tests/canon.rs` — 13 canonicalization tests
- `crates/trust-kernel/tests/store.rs` — 6 atomic-store / byte-stability tests

## Decisions Made
- **Empty-input rule locked:** empty (and BOM-only) input canonicalizes to a single `\n`. This was the plan's "pick one and lock it" choice; documented in code and asserted by two tests.
- **Hand-rolled atomic write (no `tempfile` crate):** the temp file is created in the SAME parent directory as the target so the final `rename` is a same-volume atomic operation. `tempfile` could place the temp on a different volume, making the rename non-atomic on Windows.
- **`sync_all` before rename:** flush + fsync the temp file before renaming so a crash after rename cannot expose un-synced bytes.
- **Drop the file handle before rename:** Windows can refuse to rename an open file; the handle is explicitly dropped first.

## Deviations from Plan
None — plan executed exactly as written. The plan offered a choice between stub modules with `// implemented in Task N` versus minimal compiling stubs; I used minimal compiling stubs in Task 1 (passthrough `canonicalize_bytes`, no-op store) so the crate built green, then replaced them with the real RED-first implementations in Tasks 2 and 3. This is within the plan's stated latitude, not a deviation.

## Issues Encountered
- Git emitted `LF will be replaced by CRLF` warnings when staging the `.rs`/`.toml`/`.gitignore` source files. These are source files, not the signed artifacts — autocrlf on them is harmless, and the actual signed files (`config*.yaml`, `*.guardkey`) are protected by the new `.gitattributes -text` rules and are git-ignored anyway. No action needed.

## TDD Gate Compliance
Both behavior-adding tasks followed RED → GREEN with separate commits:
- Canon: `29d0973` (test, 11 failing) → `e339ea1` (feat, 13 passing).
- Store: `a55e753` (test, 5 failing) → `83e177c` (feat, 6 passing).
Task 1 was config/scaffolding only (no `<behavior>` block) and is correctly exempt from the gate.

## Threat Model Coverage
- **T-01-01 (Tampering, config byte form):** mitigated — `canonicalize_bytes` enforces one byte form; `.gitattributes -text` stops autocrlf.
- **T-01-02 (DoS, interrupted write):** mitigated — temp-then-rename, prior file proven intact by `prior_file_intact_when_write_fails`.
- **T-01-03 (Tampering, supply chain):** mitigated — only `thiserror` added; no crypto/DPAPI deps; verified against STACK.md "What NOT to use".
- **T-01-04 (Info disclosure, secrets in git):** mitigated — `.gitignore` excludes all runtime secret/state files.

## Known Stubs
None — the Task 1 placeholder stubs were fully replaced by real implementations in Tasks 2 and 3. No hardcoded empty values, placeholders, or TODOs remain.

## Next Phase Readiness
- The deterministic writer and crash-safe store are in place; Plan 02 (HMAC-SHA256 + DPAPI key) can import `canonicalize_bytes` and `atomic_write`/`write_canonical_text` directly — the public API in `lib.rs` matches the plan's `<interfaces>` block exactly, so no exploration is needed.
- No Rust crypto/DPAPI deps yet by design — `hmac 0.12.1`, `sha2 0.10.9`, `windows-dpapi 0.2.0` land in Plan 02.
- Carry-forward concern (from STATE): the DPAPI + HMAC Rust↔PowerShell byte-identical round-trip remains the phase exit gate and is addressed in Plans 02/03, not here.

## Self-Check: PASSED

All 9 created files exist on disk; all 5 task commits (`ece3159`, `29d0973`, `e339ea1`, `a55e753`, `83e177c`) are present in git history. `cargo build` and `cargo test` both exit 0 (19 tests, zero warnings), no prohibited dependencies in `Cargo.lock`.

---
*Phase: 01-trust-kernel*
*Completed: 2026-06-04*
