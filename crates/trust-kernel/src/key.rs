//! DPAPI-backed 32-byte key store (KERN-02).
//!
//! [`load_or_create_key`] is the project's signing-key lifecycle:
//! - First run (no key file): generate 32 cryptographically-random bytes, DPAPI-protect
//!   them as a RAW blob ([`crate::dpapi::dpapi_protect`]), and persist that blob
//!   atomically ([`crate::store::atomic_write`]) — so an interrupted write never leaves a
//!   half-written key. Returns the 32 raw bytes.
//! - Subsequent runs: read the on-disk RAW blob and DPAPI-unprotect it back to the SAME
//!   32 bytes (generate-once / load-thereafter).
//!
//! The unprotected key MUST be exactly 32 bytes; anything else (notably 64 bytes, the
//! UTF-16/hex SecureString-framing giveaway) is a hard error ([`KernelError::BadKeyLength`]).

use std::path::Path;

/// Unified error surface for the crypto kernel (DPAPI + key store).
#[derive(Debug, thiserror::Error)]
pub enum KernelError {
    /// File I/O / atomic-write failure.
    #[error("kernel io error: {0}")]
    Io(String),

    /// A DPAPI CryptProtectData / CryptUnprotectData failure.
    #[error("dpapi error: {0}")]
    Dpapi(String),

    /// The unprotected key was not exactly 32 bytes — the SecureString/UTF-16/hex
    /// framing canary (a 64-byte result is the classic giveaway).
    #[error("unprotected key length was {0}, expected 32 (SecureString-framing canary)")]
    BadKeyLength(usize),
}

impl From<crate::store::StoreError> for KernelError {
    fn from(e: crate::store::StoreError) -> Self {
        KernelError::Io(e.to_string())
    }
}

/// Generate-once / load-thereafter the 32-byte DPAPI-protected signing key at `key_path`.
#[cfg(windows)]
pub fn load_or_create_key(key_path: &Path) -> Result<[u8; 32], KernelError> {
    use crate::dpapi::{dpapi_protect, dpapi_unprotect};

    if key_path.exists() {
        // Load: read the raw blob and unprotect it back to exactly 32 bytes.
        let blob = std::fs::read(key_path).map_err(|e| KernelError::Io(e.to_string()))?;
        let plain = dpapi_unprotect(&blob)?;
        return to_key32(plain);
    }

    // Create: 32 cryptographically-random bytes -> DPAPI-protect -> atomic_write raw blob.
    use rand::RngCore;
    let mut key = [0u8; 32];
    rand::rngs::OsRng.fill_bytes(&mut key);

    let blob = dpapi_protect(&key)?;
    crate::store::atomic_write(key_path, &blob)?;

    Ok(key)
}

/// Convert an unprotected key buffer into a fixed `[u8;32]`, rejecting any other length
/// (the SecureString/UTF-16/hex-framing canary).
#[cfg(windows)]
fn to_key32(plain: Vec<u8>) -> Result<[u8; 32], KernelError> {
    if plain.len() != 32 {
        return Err(KernelError::BadKeyLength(plain.len()));
    }
    let mut out = [0u8; 32];
    out.copy_from_slice(&plain);
    Ok(out)
}
