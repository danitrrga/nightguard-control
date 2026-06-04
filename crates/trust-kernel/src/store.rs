//! Atomic crash-safe file writes — implemented in Task 3.

use std::path::Path;

/// Errors produced by the store. Implemented fully in Task 3.
#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
}

/// Write `bytes` to `path` atomically (temp file in the same dir, then rename).
/// On any failure the prior file at `path` is left fully intact.
pub fn atomic_write(_path: &Path, _bytes: &[u8]) -> Result<(), StoreError> {
    // Stub — real implementation lands in Task 3.
    Ok(())
}

/// Canonicalize text content then [`atomic_write`] it.
pub fn write_canonical_text(_path: &Path, _content: &str) -> Result<(), StoreError> {
    // Stub — real implementation lands in Task 3.
    Ok(())
}
