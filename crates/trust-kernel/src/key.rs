//! DPAPI-backed 32-byte key store (RED stub — replaced in GREEN).

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

pub fn load_or_create_key(_key_path: &Path) -> Result<[u8; 32], KernelError> {
    Err(KernelError::Dpapi("not implemented".into()))
}
