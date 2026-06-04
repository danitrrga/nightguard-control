//! DPAPI raw-blob protect/unprotect (KERN-02, Windows-only).
//!
//! Locked invariant (PITFALLS Pitfall 1 / threats T-01-07, T-01-08):
//! - Raw `CryptProtectData`/`CryptUnprotectData` blob — NO SecureString / UTF-16 / hex
//!   framing. We delegate to `windows-dpapi` 0.2.0, whose `encrypt_data`/`decrypt_data`
//!   return the bare `CryptProtectData` output (no extra framing), so the blob is
//!   byte-compatible with PowerShell `[ProtectedData]::Protect/Unprotect` (proven in
//!   Plan 03).
//! - Scope = CurrentUser (`Scope::User`), NEVER LocalMachine.
//! - Optional entropy = `None` on BOTH protect and unprotect (must match the guard).
//!
//! The whole module is `#[cfg(windows)]`; the project is Windows-only.
#![cfg(windows)]

use windows_dpapi::{decrypt_data, encrypt_data, Scope};

use crate::key::KernelError;

/// DPAPI-protect `plaintext` as a RAW blob: CurrentUser scope, no optional entropy.
pub fn dpapi_protect(plaintext: &[u8]) -> Result<Vec<u8>, KernelError> {
    encrypt_data(plaintext, Scope::User, None).map_err(|e| KernelError::Dpapi(e.to_string()))
}

/// DPAPI-unprotect a RAW blob produced by [`dpapi_protect`] (or the PowerShell side):
/// CurrentUser scope, no optional entropy.
pub fn dpapi_unprotect(blob: &[u8]) -> Result<Vec<u8>, KernelError> {
    decrypt_data(blob, Scope::User, None).map_err(|e| KernelError::Dpapi(e.to_string()))
}
