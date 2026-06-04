---
phase: 01-trust-kernel
verified: 2026-06-04T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 1: Trust Kernel Verification Report

**Phase Goal:** The cryptographic foundation works identically across Rust and PowerShell — both languages produce the same HMAC over the same input using the same DPAPI-stored key, and every write is atomic.
**Verified:** 2026-06-04
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | A 32-byte key DPAPI-protected by one side decrypts to the identical 32 bytes on the other; DPAPI+HMAC round-trip passes both directions | VERIFIED | Interop gate run independently: `[PASS] DPAPI Rust->PS` (decrypted=32 bytes, key match=True) and `[PASS] DPAPI PS->Rust` (rust exit=0, identical=True). Exit code 0. |
| SC-2 | Same `config.yaml` bytes yield identical HMAC-SHA256 tags in both Rust and PowerShell (no CRLF/BOM/trailing-newline divergence) | VERIFIED | Interop gate: `[PASS] HMAC Rust->PS` (tags identical, confirmed with identical hex prefix) and `[PASS] HMAC PS->Rust` (Rust verify-file exit=0). Tamper check confirms CRLF/BOM mutations ARE detected both sides. |
| SC-3 | An interrupted config/state write never leaves a partial or corrupt file; prior valid file remains intact | VERIFIED | `store.rs` implements temp-then-rename in the same parent dir, `sync_all` before rename, handle dropped before rename. `prior_file_intact_when_write_fails` test passes. `cargo test` exit 0, 6 store tests green. |
| SC-4 | Config writer round-trips `config.yaml` so the existing PowerShell minimal YAML parser still reads it correctly | VERIFIED | Interop gate: `[PASS] KERN-04 config readback` (hasCR=False, hasBOM=False, exactlyOneTrailingLF=True). `write_canonical_text` encodes UTF-8/no-BOM/LF/one-trailing-newline by construction. |

**Score:** 4/4 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `crates/trust-kernel/src/lib.rs` | Module declarations + public re-exports | VERIFIED | Exports `canon`, `store`, `hmac`, `key`, `dpapi` (cfg windows). Real module declarations, not stubs. |
| `crates/trust-kernel/src/canon.rs` | `canonicalize_bytes` — BOM strip, CRLF→LF, one trailing newline | VERIFIED | Substantive 57-line implementation. 13 canon tests pass. |
| `crates/trust-kernel/src/store.rs` | `atomic_write`, `write_canonical_text`, `StoreError` | VERIFIED | Substantive implementation: same-dir temp, flush+sync_all, drop-before-rename. 6 store tests pass. |
| `crates/trust-kernel/src/hmac.rs` | `sign_bytes`, `verify_bytes` (constant-time), `tag_to_hex` | VERIFIED | Uses `hmac::Mac::verify_slice` (subtle, constant-time), never `==` on tags. 8 hmac tests pass. |
| `crates/trust-kernel/src/dpapi.rs` | `dpapi_protect`/`dpapi_unprotect` — raw CryptProtectData blob, CurrentUser, no entropy | VERIFIED | `windows_dpapi::encrypt_data/decrypt_data(_, Scope::User, None)`. `#[cfg(windows)]`. No SecureString framing. |
| `crates/trust-kernel/src/key.rs` | `load_or_create_key`, `KernelError`, 32-not-64 guard | VERIFIED | Generate-once/load-thereafter with CSPRNG (`OsRng`), DPAPI-protect, atomic_write blob. Rejects non-32 results (`BadKeyLength`). 5 key tests pass. |
| `crates/trust-kernel/src/bin/interop_cli.rs` | 6-subcommand Rust CLI for the exit gate | VERIFIED | All 6 subcommands implemented (`gen-key`, `unprotect-key`, `protect-key`, `sign-file`, `verify-file`, `write-config`). Distinct exit codes (0/1/2). |
| `scripts/interop/nightguard_interop.ps1` | PowerShell DPAPI+HMAC parity functions | VERIFIED | `Protect-GuardKey`/`Unprotect-GuardKey` via `[ProtectedData]::Protect/Unprotect($bytes, $null, CurrentUser)`. `Get-FileBytes` via `[IO.File]::ReadAllBytes`. `Get-FileHmacHex` via `[HMACSHA256]`. No SecureString, no `Get-Content`. |
| `scripts/interop/run_interop_gate.ps1` | 6-check both-direction exit gate script | VERIFIED | Implements all 6 checks; exits 1 on any mismatch. Ran independently: exit 0, all 6 PASS. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `interop_cli.rs` | `hmac.rs` | `trust_kernel::hmac::{sign_bytes, tag_to_hex, verify_bytes}` | WIRED | Import confirmed at line 30 of `interop_cli.rs`; `sign_bytes` called in `cmd_sign_file`, `verify_bytes` in `cmd_verify_file`. |
| `interop_cli.rs` | `key.rs` | `trust_kernel::key::load_or_create_key` | WIRED | Import line 31; called in `cmd_gen_key`, `load_key` helper used by `cmd_sign_file`/`cmd_verify_file`. |
| `interop_cli.rs` | `dpapi.rs` | `trust_kernel::dpapi::{dpapi_protect, dpapi_unprotect}` | WIRED | Import line 34 (`#[cfg(windows)]`); called in `cmd_protect_key` and `cmd_unprotect_key`. |
| `interop_cli.rs` | `store.rs` | `trust_kernel::atomic_write`, `trust_kernel::write_canonical_text` | WIRED | Called in `cmd_protect_key` (atomic_write) and `cmd_write_config` (write_canonical_text). |
| `run_interop_gate.ps1` | `nightguard_interop.ps1` | `. (Join-Path $here 'nightguard_interop.ps1')` (dot-source) | WIRED | Line 23 of gate script; all PS-side functions (`Protect-GuardKey`, `Unprotect-GuardKey`, `Get-FileBytes`, `Get-FileHmacHex`) confirmed used in checks 1–6. |
| `run_interop_gate.ps1` | `interop_cli.exe` | `Invoke-Cli` helper, `$LASTEXITCODE` gating | WIRED | `Invoke-Cli` drives all 6 checks; exit codes 0/2 asserted precisely. |
| `store.rs` | `canon.rs` | `use crate::canon::canonicalize_bytes` | WIRED | `write_canonical_text` calls `canonicalize_bytes` directly. |
| `key.rs` | `dpapi.rs` | `use crate::dpapi::{dpapi_protect, dpapi_unprotect}` | WIRED | `load_or_create_key` uses both functions. |

---

## Data-Flow Trace (Level 4)

Not applicable — this phase produces a library crate and CLI tool, not a UI component. Data flows were verified via the interop gate execution (real DPAPI + real HMAC, not mocked).

---

## Behavioral Spot-Checks (Step 7b)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `cargo test` exit 0, all tests green | `cargo test` from workspace root | exit 0; 32 tests (13 canon + 8 hmac + 5 key + 6 store); 0 failures | PASS |
| Interop gate exit 0, all 6 checks PASS | `powershell -NoProfile -File scripts/interop/run_interop_gate.ps1` | exit 0; DPAPI Rust->PS PASS, DPAPI PS->Rust PASS, HMAC Rust->PS PASS, HMAC PS->Rust PASS, Tamper CRLF/BOM PASS, KERN-04 config readback PASS | PASS |

---

## Probe Execution (Step 7c)

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| `scripts/interop/run_interop_gate.ps1` | `powershell -NoProfile -File scripts/interop/run_interop_gate.ps1` | exit 0; all 6 checks PASS | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| KERN-01 | 01-02, 01-03 | HMAC-SHA256 byte-identical across Rust and PowerShell | SATISFIED | Interop gate HMAC Rust->PS and PS->Rust both PASS. `sign_bytes`/`verify_bytes` in `hmac.rs` verified against same key+file bytes as PS `[HMACSHA256]`. |
| KERN-02 | 01-02, 01-03 | 32-byte key via DPAPI raw CryptProtectData blob, no SecureString | SATISFIED | `dpapi.rs`: `Scope::User`, `None` entropy, no SecureString. `key.rs`: `BadKeyLength` rejects non-32 results. Gate checks 1+2 pass with decrypted=32 bytes both directions. `hmac 0.12.1` and `sha2 0.10.9` confirmed in Cargo.lock. |
| KERN-03 | 01-01 | Atomic temp→rename writes, never partial | SATISFIED | `store.rs`: temp in same parent dir, `sync_all`, drop handle, then rename. `prior_file_intact_when_write_fails` test confirms prior file survives a failed write. |
| KERN-04 | 01-01, 01-03 | Config writer round-trips; PowerShell minimal YAML parser reads correctly | SATISFIED | `write_canonical_text` enforces UTF-8/no-BOM/LF/one-trailing-newline. Gate check 6 (KERN-04 config readback): hasCR=False, hasBOM=False, exactlyOneTrailingLF=True. |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | No TBD/FIXME/XXX markers, no stub returns, no placeholder implementations found in any phase-1 file. |

Checked all 9 created files and 3 modified files for: `TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, `PLACEHOLDER`, `return null`, `return {}`, `return []`, hardcoded empty values. None found outside of test scaffolding or documentation references.

No Tauri dependency in `Cargo.toml` or `Cargo.lock` — confirmed library-only as required.

---

## Human Verification Required

None. All phase success criteria are verifiable programmatically and have been verified:
- Cargo test: run independently, exit 0, 32 tests green.
- Interop gate: run independently, exit 0, all 6 checks PASS.
- No UI behavior, no external service integration, no real-time behavior in scope for this phase.

---

## Gaps Summary

No gaps. All 4 success criteria are met. All 4 requirements (KERN-01..04) are satisfied. The codebase delivers the phase goal: both languages produce the same HMAC over the same input using the same DPAPI-stored key (proven live), and every write is atomic (proven by test and design).

---

_Verified: 2026-06-04_
_Verifier: Claude (gsd-verifier)_
