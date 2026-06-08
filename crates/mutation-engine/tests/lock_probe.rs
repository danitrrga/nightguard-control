//! fd-lock presence-probe spike (RESEARCH Open Question 1 / threat T-03-02).
//!
//! The Phase 3 PowerShell guard's circuit-breaker (`Test-LockHeld`, D-06) must distinguish a
//! HELD vs FREE `.nightguard.lock` so it skips an auto-revert only while a real in-progress
//! sanctioned commit holds the lock. The lock is owned by Rust [`with_commit_lock`]
//! (`commit.rs`): `OpenOptions` + `fd_lock::RwLock::write()` == Windows `LockFileEx` +
//! `LOCKFILE_EXCLUSIVE_LOCK`. Crucially the lock FILE persists once created, so file existence
//! is NOT the held-signal — the guard must probe with an EXCLUSIVE (share-mode `None`) open and
//! treat the resulting `IOException` as "held".
//!
//! This test proves that exact probe shape against a live Rust lock holder:
//!   - INSIDE `with_commit_lock` (lock held): the PowerShell probe prints "HELD".
//!   - AFTER `with_commit_lock` returns (lock released, file still on disk): it prints "FREE".
//!
//! This is the spike ONLY — plan 02 lifts the proven `[IO.File]::Open(...,'None')` shape into
//! the guard's `Test-LockHeld`. We do not touch the guard script here.

use std::path::{Path, PathBuf};
use std::process::Command;

use mutation_engine::commit::with_commit_lock;
use mutation_engine::state::MutationError;

/// Per-test scratch dir under the crate's `target/` (mirrors commit_order.rs conventions).
fn scratch_dir(tag: &str) -> PathBuf {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join(format!("lockprobe-{tag}-{n}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).expect("create scratch dir");
    dir
}

/// The exact circuit-breaker probe the guard will use (D-06): attempt an exclusive open
/// (`FileShare.None`); an `IOException` means another handle holds the lock (HELD), a
/// successful open (then Close) means it is FREE. Returns the probe's trimmed stdout.
///
/// The lock path is embedded into a single-quoted PowerShell literal (backslash is not an
/// escape char in PS single-quoted strings; any literal `'` is doubled) — `powershell -Command`
/// does not populate `$args` from trailing tokens the way `-File` does, so embedding is the
/// robust way to feed a Windows path with backslashes.
fn run_lock_probe(lock_path: &Path) -> String {
    let path_literal = lock_path.to_string_lossy().replace('\'', "''");
    let script = format!(
        "$p = '{path_literal}'; \
         try {{ \
             $fs = [System.IO.File]::Open($p, 'Open', 'ReadWrite', 'None'); \
             $fs.Close(); \
             Write-Output 'FREE' \
         }} catch [System.IO.IOException] {{ \
             Write-Output 'HELD' \
         }}"
    );
    let output = Command::new("powershell")
        .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", &script])
        .output()
        .expect("spawn powershell lock probe");
    assert!(
        output.status.success(),
        "lock probe powershell exited non-zero: stdout={:?} stderr={:?}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr),
    );
    String::from_utf8_lossy(&output.stdout).trim().to_string()
}

/// The fd-lock presence probe reports HELD while a live Rust holder owns `.nightguard.lock`,
/// and FREE once released — proving existence != held (the file persists across both checks).
#[test]
fn powershell_probe_distinguishes_held_vs_free_lock() {
    let dir = scratch_dir("held-free");
    let lock_path = dir.join(".nightguard.lock");

    // --- INSIDE the lock: the probe must see HELD. ---
    let held: Result<String, MutationError> = with_commit_lock(&dir, || {
        // The lock file is created + exclusively locked by with_commit_lock before `body` runs.
        assert!(
            lock_path.exists(),
            "with_commit_lock must have created .nightguard.lock before the body runs"
        );
        Ok(run_lock_probe(&lock_path))
    });
    let held = held.expect("with_commit_lock body ran");
    assert_eq!(
        held, "HELD",
        "the exclusive-open probe must report HELD while the Rust fd-lock is held"
    );

    // --- AFTER the lock released: the file still exists, but the probe must see FREE. ---
    assert!(
        lock_path.exists(),
        "the .nightguard.lock file must persist after the lock is released (existence != held)"
    );
    let free = run_lock_probe(&lock_path);
    assert_eq!(
        free, "FREE",
        "the exclusive-open probe must report FREE once the lock is released, even though the file persists"
    );
}
