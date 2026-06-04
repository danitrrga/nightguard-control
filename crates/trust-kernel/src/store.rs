//! Atomic, crash-safe file writes.
//!
//! Every config/key/state file the project owns is written through here so that an
//! interrupted write can never corrupt the prior file (PITFALLS Pitfall 3 / threat
//! T-01-02). The strategy is the classic temp-then-rename in the SAME directory:
//! a partially-written temp file is never visible at the target path, and the rename
//! is atomic only when source and destination share a volume — which is guaranteed
//! by keeping the temp file beside the target (cross-volume rename is NOT atomic, so
//! we deliberately do not use the OS temp dir; see STACK.md Windows note).

use std::fs::{self, File};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

use crate::canon::canonicalize_bytes;

/// Errors produced by the store.
#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    /// Underlying I/O failure (temp create, write, flush, sync, or rename).
    #[error("store io error: {0}")]
    Io(#[from] std::io::Error),

    /// The target path has no parent directory (e.g. a bare filename at the root).
    #[error("target path has no parent directory: {0}")]
    NoParent(PathBuf),
}

/// Process-local counter to uniquify temp filenames so concurrent writers in the
/// same directory never collide on the temp path.
static TEMP_COUNTER: AtomicU64 = AtomicU64::new(0);

/// Write `bytes` to `path` atomically.
///
/// Writes to a uniquely-named temp file in the SAME parent directory as `path`,
/// flushes and `sync_all`s it to durable storage, then `rename`s it over the target.
/// On ANY failure before the rename, the temp file is removed and the prior file at
/// `path` is left fully intact (no truncation, no partial content).
pub fn atomic_write(path: &Path, bytes: &[u8]) -> Result<(), StoreError> {
    let parent = path
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .ok_or_else(|| StoreError::NoParent(path.to_path_buf()))?;

    // Unique temp name beside the target: "<filename>.tmp.<pid>.<counter>".
    let file_name = path
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_else(|| "atomic".to_string());
    let n = TEMP_COUNTER.fetch_add(1, Ordering::Relaxed);
    let temp_path = parent.join(format!("{file_name}.tmp.{}.{n}", std::process::id()));

    // Write + flush + fsync, then rename. If anything fails, clean up the temp file
    // and propagate the error WITHOUT touching `path`.
    let write_result = (|| -> std::io::Result<()> {
        let mut file = File::create(&temp_path)?;
        file.write_all(bytes)?;
        file.flush()?;
        file.sync_all()?;
        // Drop the handle before rename (Windows can refuse rename of an open file).
        drop(file);
        fs::rename(&temp_path, path)?;
        Ok(())
    })();

    if let Err(e) = write_result {
        // Best-effort cleanup of any temp file we may have created. The target is
        // untouched because the rename either never ran or failed atomically.
        let _ = fs::remove_file(&temp_path);
        return Err(StoreError::Io(e));
    }

    Ok(())
}

/// Canonicalize `content` to the project's signed byte form, then [`atomic_write`] it.
///
/// Used for the human-readable YAML artifacts so they always hit disk as UTF-8,
/// no BOM, LF-only, exactly one trailing newline — byte-stable across repeated writes
/// of the same logical content (KERN-04).
pub fn write_canonical_text(path: &Path, content: &str) -> Result<(), StoreError> {
    atomic_write(path, &canonicalize_bytes(content.as_bytes()))
}
