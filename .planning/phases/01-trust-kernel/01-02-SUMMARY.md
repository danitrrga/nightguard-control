---
phase: 01-trust-kernel
plan: 02
subsystem: crypto
tags: [rust, hmac-sha256, dpapi, key-store, constant-time, tdd, windows]

# Dependency graph
requires:
  - "01-01: canonicalize_bytes + atomic_write (trust-kernel crate public API)"
provides:
  - "hmac::sign_bytes/verify_bytes/tag_to_hex — HMAC-SHA256 over RAW bytes, constant-time verify"
  - "dpapi::dpapi_protect/dpapi_unprotect — raw CryptProtectData blob, CurrentUser, no entropy"
  - "key::load_or_create_key — generate-once / load-thereafter 32-byte DPAPI-protected signing key"
  - "key::KernelError (thiserror) over IO / DPAPI / BadKeyLength (the 32-not-64 canary)"
affects: [powershell-guard-interop, config-signing, state-signing, tauri-app]

# Tech tracking
tech-stack:
  added: [hmac 0.12.1, sha2 0.10.9, subtle 2, hex 0.4.3, windows-dpapi 0.2.0, rand 0.8]
  patterns:
    - "HMAC computed over RAW bytes handed in — no normalization in the signer (callers sign canonicalize_bytes output)"
    - "Constant-time tag verify via hmac verify_slice (subtle), never == on tags"
    - "Key persisted as the RAW DPAPI blob via atomic_write (no base64/text framing)"
    - "Explicit 32-not-64 length guard as the SecureString-framing canary"
    - "TDD RED->GREEN per behavior-adding task (separate test/feat commits)"

key-files:
  created:
    - crates/trust-kernel/src/hmac.rs
    - crates/trust-kernel/src/dpapi.rs
    - crates/trust-kernel/src/key.rs
    - crates/trust-kernel/tests/hmac.rs
    - crates/trust-kernel/tests/key.rs
  modified:
    - crates/trust-kernel/Cargo.toml
    - crates/trust-kernel/src/lib.rs
    - Cargo.lock

key-decisions:
  - "Known-answer vector = HMAC-SHA256(32 x 0x0b, \"Hi There\") = 198a607e...0b68cf7, derived via a Python hmac oracle that reproduces published RFC 4231 TC1 exactly (auditable)"
  - "DPAPI via windows-dpapi 0.2.0 (Scope::User, None entropy) — returns the bare CryptProtectData blob, byte-compatible with PowerShell [ProtectedData]; the ~40-line windows-sys alternative was not needed"
  - "32 key bytes via rand::rngs::OsRng (CSPRNG), DPAPI-protected then atomic_write of the raw blob"
  - "KernelError::BadKeyLength rejects any non-32 unprotect result — the 64-byte UTF-16/hex SecureString giveaway"

patterns-established:
  - "The signer hashes exactly the bytes on disk; cosmetic EOL/BOM/trailing-newline drift is detected as tamper (canonicalization, if any, happens at the call site)"
  - "All key material is generated, protected, and persisted by Rust as a raw DPAPI blob — Plan 03's PowerShell side reads these exact bytes"

requirements-completed: [KERN-01, KERN-02]

# Metrics
duration: 5min
completed: 2026-06-04
---

# Phase 1 Plan 02: HMAC-SHA256 + DPAPI Key Store Summary

**The Rust half of the trust kernel: HMAC-SHA256 sign/verify over raw file bytes (constant-time, matched to an external RFC-faithful vector) plus a DPAPI-backed 32-byte key store that protects/persists the signing key as a raw CurrentUser CryptProtectData blob — both fully unit-tested on Windows.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-04 (RED commit `c170083`)
- **Completed:** 2026-06-04 (GREEN commit `0c70fd8`)
- **Tasks:** 2 (both TDD)
- **Files modified:** 5 created, 3 modified

## Accomplishments
- `hmac.rs`: `sign_bytes`/`verify_bytes`/`tag_to_hex` on `hmac 0.12` + `sha2 0.10`. Verify uses `verify_slice` (constant-time via `subtle`), never `==`. Signs exactly the bytes handed in — no internal normalization — so a one-byte, raw-CRLF, raw-BOM, or trailing-newline change is detected as tamper. Known-answer vector asserted against an RFC 4231-faithful oracle. 8 tests.
- `dpapi.rs` (`#[cfg(windows)]`): `dpapi_protect`/`dpapi_unprotect` via `windows-dpapi` `Scope::User`, `None` entropy — the raw `CryptProtectData` blob, byte-compatible with PowerShell `[ProtectedData]` (Plan 03's parity target).
- `key.rs`: `load_or_create_key` generates 32 `OsRng` bytes on first run, DPAPI-protects them, and `atomic_write`s the raw blob; on reload it unprotects back to the identical 32 bytes. Rejects any non-32 unprotect result (`KernelError::BadKeyLength`) — the explicit 32-not-64 SecureString-framing canary. 5 tests.
- `KernelError` (thiserror) unifies IO / DPAPI / BadKeyLength, with `From<StoreError>`.
- Whole crate: `cargo build` and `cargo test` both exit 0 — 32 tests green (13 canon + 8 hmac + 5 key + 6 store), zero warnings. The DPAPI round-trip tests ran for real in this interactive CurrentUser session; none had to be `#[ignore]`'d.

## Task Commits

Each task TDD-split (test/RED -> feat/GREEN):

1. **Task 1: HMAC-SHA256 sign/verify over raw bytes** — `c170083` (test/RED) -> `d8f8d0e` (feat/GREEN)
2. **Task 2: DPAPI key store (raw CryptProtectData blob)** — `88d827f` (test/RED) -> `0c70fd8` (feat/GREEN)

## Files Created/Modified
- `crates/trust-kernel/src/hmac.rs` — `sign_bytes`, `verify_bytes` (constant-time), `tag_to_hex`
- `crates/trust-kernel/src/dpapi.rs` — `dpapi_protect`/`dpapi_unprotect` (`Scope::User`, `None`), `#[cfg(windows)]`
- `crates/trust-kernel/src/key.rs` — `load_or_create_key`, `KernelError`, 32-not-64 guard
- `crates/trust-kernel/tests/hmac.rs` — 8 HMAC tests (KAT, round-trip, mutation, wrong key, CRLF/BOM/trailing-newline tamper)
- `crates/trust-kernel/tests/key.rs` — 5 DPAPI tests (round-trip, 32-not-64 canary, opaque blob, generate-once, raw-blob-on-disk)
- `crates/trust-kernel/Cargo.toml` — added `hmac 0.12.1`, `sha2 0.10.9`, `subtle 2`, `hex 0.4.3`, `windows-dpapi 0.2.0`, `rand 0.8`
- `crates/trust-kernel/src/lib.rs` — `pub mod hmac; pub mod key; #[cfg(windows)] pub mod dpapi;`
- `Cargo.lock` — locked the new dependency tree

## Decisions Made
- **Known-answer vector provenance (auditable):** the asserted tag is `HMAC-SHA256(32 x 0x0b, "Hi There") = 198a607eb44bfbc69903a0f1cf2bbdc5ba0aa3f3d9ae3c1c7a3b1696a0b68cf7`. Because `sign_bytes` takes a fixed `[u8;32]` key, a 32-byte key is used rather than RFC 4231 TC1's 20-byte key; the vector was derived via Python's `hmac`/`hashlib`, which reproduces the *published* RFC 4231 TC1 tag (`b0344c61...`) exactly — proving the oracle is a faithful HMAC-SHA256 implementation. The reproduction command is documented in the test file header.
- **`windows-dpapi 0.2.0` over the windows-sys hand-roll:** the wrapper's `encrypt_data`/`decrypt_data(_, Scope::User, None)` returns the bare `CryptProtectData` output with no framing — exactly the raw-blob contract. STACK.md sanctioned both; the wrapper was sufficient and the ~40-line `windows-sys` alternative was unnecessary.
- **CSPRNG for key material:** `rand::rngs::OsRng.fill_bytes` (OS entropy), not a seeded PRNG.

## Deviations from Plan
None — plan executed exactly as written. Both tasks followed RED -> GREEN with separate commits; pins, scope, entropy, and the 32-not-64 canary all match the locked invariants.

## Issues Encountered
- Git emitted `LF will be replaced by CRLF` warnings on the `.rs`/`.toml`/`Cargo.lock` source files. These are source files, not the signed artifacts (`config*.yaml`/`*.guardkey`, which are `-text` via `.gitattributes` and git-ignored). Harmless, no action needed — same as Plan 01.

## TDD Gate Compliance
Both behavior-adding tasks have a `test(...)` RED commit followed by a `feat(...)` GREEN commit:
- HMAC: `c170083` (RED, positive cases failing) -> `d8f8d0e` (GREEN, 8 passing).
- DPAPI key: `88d827f` (RED, 5 failing) -> `0c70fd8` (GREEN, 5 passing).
No RED test passed unexpectedly. Gate sequence intact.

## Threat Model Coverage
- **T-01-05 (Spoofing, forged HMAC):** mitigated — HMAC-SHA256 over raw bytes with a DPAPI-protected key; a hand-editor lacks the key to forge a valid tag.
- **T-01-06 (Tampering, EOL/BOM-laundered edit):** mitigated — signer hashes exactly the bytes handed in; raw-CRLF / raw-BOM / trailing-newline tests prove these fail verification.
- **T-01-07 (Info disclosure, key at rest):** mitigated — DPAPI `Scope::User` (CurrentUser, NOT LocalMachine); key never written in plaintext.
- **T-01-08 (Tampering, SecureString framing):** mitigated — raw `CryptProtectData` blob, no entropy; explicit `BadKeyLength` 32-not-64 assertion is the canary.
- **T-01-09 (Honesty):** accepted per PITFALLS Pitfall 5 — no obfuscation added; DPAPI does not protect against the user scripting DPAPI as themselves (documented, not theatered).
- **T-01-SC (Supply chain):** mitigated — all pins (`hmac 0.12.1`, `sha2 0.10.9`, `subtle 2`, `hex 0.4.3`, `windows-dpapi 0.2.0`, `rand 0.8`) match STACK.md; mainstream RustCrypto/Microsoft-blessed crates, no flags.

## Windows / DPAPI Note for the Wave 3 Human Exit-Gate
The 5 DPAPI tests exercised **real** `CryptProtectData`/`CryptUnprotectData` in this interactive CurrentUser session and all passed — **none were `#[ignore]`'d**. The crypto was not weakened and no pass was faked. The cross-language byte-identical round-trip (Rust-protected blob unprotected by PowerShell `[ProtectedData]` and vice-versa) remains the **Plan 03** exit gate; this plan proves only the Rust side.

## Known Stubs
None — the Task RED stubs (`hmac`/`dpapi`/`key`) were fully replaced by real implementations in their GREEN commits. No hardcoded empties, placeholders, or TODOs remain.

## Threat Flags
None — no new security surface beyond the plan's threat_model was introduced.

## Next Phase Readiness
- `sign_bytes`/`verify_bytes`/`tag_to_hex` and `load_or_create_key` match the plan's `<interfaces>` block exactly — Plan 03's Rust test-CLI can call them directly.
- Plan 03 must prove the byte-identical Rust<->PowerShell round-trip for BOTH the DPAPI blob and the HMAC tag (the phase exit gate). The Rust contracts are now fixed: raw DPAPI blob (`Scope::User`, no entropy) and lowercase-hex HMAC tag.

## Self-Check: PASSED

All 5 created files exist on disk; all 4 task commits (`c170083`, `d8f8d0e`, `88d827f`, `0c70fd8`) are present in git history. `cargo build` and `cargo test` both exit 0 (32 tests, zero warnings); pins verified `hmac 0.12.1` / `sha2 0.10.9` (not 0.13/0.11); `verify_slice` present, no `== tag`; `Scope::User` present, no SecureString framing (only canary doc/error references).

---
*Phase: 01-trust-kernel*
*Completed: 2026-06-04*
