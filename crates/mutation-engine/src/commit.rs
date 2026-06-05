//! RULE-06: fd-lock single-writer + ordered atomic re-signed commit.
//!
//! Every sanctioned commit writes three files under ONE cross-process exclusive lock
//! (`fd-lock`, Windows `LockFileEx` + `LOCKFILE_EXCLUSIVE_LOCK`), in this EXACT order:
//!
//!   1. `config.sanctioned.yaml`  (the revert target)        -- FIRST
//!   2. `guard.json`              (re-signed: config_hmac=HMAC(NEW), spent++, ledger)
//!   3. `config.yaml`             (the LIVE file)             -- LAST
//!
//! Convergence contract (threats T-02-10/13): the Phase 3 guard's rule is
//! "if HMAC(config.yaml) != guard.json.config_hmac -> copy config.sanctioned.yaml over
//! config.yaml". Walk every crash point:
//!   - before step 1: nothing written -> live=OLD, guard=OLD -> match -> OLD.
//!   - after step 1 only: live=OLD, guard.json still=OLD -> match -> OLD (new sanctioned
//!     dormant, harmless).
//!   - after step 2: guard.json=NEW but live=OLD -> mismatch -> guard reverts live to
//!     sanctioned (already NEW) -> converges NEW.
//!   - after step 3: fully committed, all three consistent -> NEW.
//!
//! So any crash converges to OLD or NEW, never a forged/partial middle.
//!
//! Forbidden anti-pattern (GARD-05 / T-02-13): writing the live `config.yaml` BEFORE
//! re-signing/sanctioned opens a sign-vs-write race where a guard fire between the live
//! write and the re-sign reverts a legitimate write. Live is ALWAYS last.
//!
//! This module ORCHESTRATES [`trust_kernel::atomic_write`] / [`write_canonical_text`];
//! it does NOT reimplement temp+rename.

use std::fs::OpenOptions;
use std::path::{Path, PathBuf};

use fd_lock::RwLock;
use trust_kernel::{atomic_write, write_canonical_text};

use crate::classify::Direction;
use crate::quota::QuotaDecision;
use crate::sign::sign_config;
use crate::state::{GuardState, LedgerEntry, MutationError};

/// The four paths a commit touches. `lock_dir` holds the `.nightguard.lock` file that
/// guards the whole critical section (also reused by [`crate::grace`]).
#[derive(Debug, Clone)]
pub struct CommitPaths {
    /// The live, human-readable curfew config the guard reads.
    pub config: PathBuf,
    /// The last app-approved snapshot — the guard's auto-revert target (written FIRST).
    pub sanctioned: PathBuf,
    /// The signed state file (`config_hmac`, `state_hmac`, ledger, quota, grace).
    pub guard_json: PathBuf,
    /// The directory in which the single-writer `.nightguard.lock` lives.
    pub lock_dir: PathBuf,
}

/// Acquire the cross-process exclusive single-writer lock and run `body` inside it.
///
/// Opens/creates `lock_dir/.nightguard.lock` and takes `fd_lock::RwLock::write()` — on
/// Windows this is `LockFileEx` with `LOCKFILE_EXCLUSIVE_LOCK`, an OS-enforced advisory
/// lock for cooperating writers. The guard is RAII: released on drop (and on crash, when
/// the handle closes), so there is no stale-lock cleanup. `commit_change` and
/// `use_grace` share this one critical section.
pub fn with_commit_lock<R>(
    lock_dir: &Path,
    body: impl FnOnce() -> Result<R, MutationError>,
) -> Result<R, MutationError> {
    let lock_path = lock_dir.join(".nightguard.lock");
    let file = OpenOptions::new()
        .create(true)
        // Never truncate: this file is only a lock sentinel; its contents are irrelevant
        // and truncating on every open would be pointless churn on a shared handle.
        .truncate(false)
        .read(true)
        .write(true)
        .open(&lock_path)
        .map_err(|e| MutationError::Io(format!("open commit lock: {e}")))?;
    let mut lock = RwLock::new(file);
    let _guard = lock
        .write()
        .map_err(|e| MutationError::Io(format!("acquire commit lock: {e}")))?;
    body()
    // _guard dropped here -> UnlockFile.
}

/// Build the NEW signed state from the current state + the proposed commit.
///
/// Sets `config_hmac = HMAC(canonical NEW bytes)`, increments `weekly_spent` iff the
/// decision costs a token (a loosening commit), appends one ledger entry naming the
/// loosened fields at `true_now`, applies the lazy week reset carried in the decision's
/// effective accounting, and finally fills `state_hmac` via the locked A3 recipe.
fn build_new_state(
    current: &GuardState,
    new_config_hmac: String,
    dirs: &[(String, Direction)],
    decision: &QuotaDecision,
    key: &[u8; 32],
    true_now: i64,
) -> GuardState {
    let mut next = current.clone();
    next.config_hmac = new_config_hmac;

    if decision.costs_token {
        // A loosening commit: spend one token and record the loosened fields in the ledger.
        next.weekly_spent = next.weekly_spent.saturating_add(1);
        let fields: Vec<String> = dirs
            .iter()
            .filter(|(_, d)| *d == Direction::Loosen)
            .map(|(f, _)| f.clone())
            .collect();
        next.ledger.push(LedgerEntry {
            ntp_timestamp: true_now,
            fields,
        });
    }

    // Re-sign over the canonical bytes with state_hmac blanked (A3 recipe).
    next.state_hmac = String::new();
    next.state_hmac = next.compute_state_hmac(key);
    next
}

/// Perform a sanctioned commit, executing only the first `max_steps` of the three ordered
/// writes. This is the test seam for crash-convergence (`commit_order.rs` stops after N);
/// production code calls [`commit_change`] (which runs all three).
///
/// The NEW state is computed up front and returned regardless of `max_steps`, so callers
/// always learn what the commit WOULD produce. Steps:
///   1. atomic_write(sanctioned, NEW canonical bytes)
///   2. atomic_write(guard.json, re-signed NEW state)
///   3. write_canonical_text(config.yaml, new_yaml)   [LAST]
#[doc(hidden)]
pub fn commit_with_limit(
    paths: &CommitPaths,
    new_yaml: &str,
    dirs: &[(String, Direction)],
    decision: &QuotaDecision,
    key: &[u8; 32],
    true_now: i64,
    max_steps: usize,
) -> Result<GuardState, MutationError> {
    // Defense in depth: a disallowed decision must never write (caller should gate too).
    if !decision.allowed {
        return Err(MutationError::QuotaExhausted);
    }

    let (new_config_hmac, new_canon) = sign_config(key, new_yaml);
    let current = read_state(&paths.guard_json)?;
    let new_state = build_new_state(&current, new_config_hmac, dirs, decision, key, true_now);

    with_commit_lock(&paths.lock_dir, || {
        // Step 1: revert target FIRST.
        if max_steps >= 1 {
            atomic_write(&paths.sanctioned, &new_canon)?;
        }
        // Step 2: re-signed state (points at NEW) SECOND.
        if max_steps >= 2 {
            let serialized = serde_json::to_vec_pretty(&new_state)?;
            atomic_write(&paths.guard_json, &serialized)?;
        }
        // Step 3: LIVE config LAST — the SAME canonical bytes config_hmac was computed over.
        if max_steps >= 3 {
            write_canonical_text(&paths.config, new_yaml)?;
        }
        Ok(new_state.clone())
    })
}

/// Atomically commit `new_yaml` as the sanctioned config under the single-writer lock,
/// writing sanctioned -> re-signed guard.json -> live config in that exact order (RULE-06).
///
/// Returns the new [`GuardState`] (with the incremented quota / appended ledger / refreshed
/// `state_hmac`). A crash at any point converges to OLD or NEW per the module contract.
pub fn commit_change(
    paths: &CommitPaths,
    new_yaml: &str,
    dirs: &[(String, Direction)],
    decision: &QuotaDecision,
    key: &[u8; 32],
    true_now: i64,
) -> Result<GuardState, MutationError> {
    commit_with_limit(paths, new_yaml, dirs, decision, key, true_now, 3)
}

/// Read the current [`GuardState`] from `guard.json` (the commit's starting point).
fn read_state(guard_json: &Path) -> Result<GuardState, MutationError> {
    let bytes = std::fs::read(guard_json)
        .map_err(|e| MutationError::Io(format!("read guard.json: {e}")))?;
    let state = serde_json::from_slice(&bytes)?;
    Ok(state)
}
