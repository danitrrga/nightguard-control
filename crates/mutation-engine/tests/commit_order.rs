//! Ordered atomic re-signed commit tests (RED-first, per the TDD directive).
//!
//! Proves the RULE-06 contract (threats T-02-10/11/13/14): a sanctioned commit writes
//! `config.sanctioned.yaml` -> re-signed `guard.json` -> live `config.yaml` IN THAT ORDER,
//! under a single-writer `fd-lock`, so EVERY crash point converges (via the guard's
//! verify-and-revert rule) to either the OLD or the NEW state — never a forged/partial
//! middle (T-02-13: live is written LAST, after re-signing).
//!
//! The crash-convergence test exercises `commit_with_limit` (a test-only hook that performs
//! only the first N of the three ordered writes), then runs a local copy of the Phase 3
//! guard's revert rule and asserts convergence for N in {0,1,2,3}.

use std::fs;
use std::path::{Path, PathBuf};

use mutation_engine::classify::Direction;
use mutation_engine::commit::{commit_change, commit_with_limit, CommitPaths};
use mutation_engine::quota::QuotaDecision;
use mutation_engine::state::GuardState;
use mutation_engine::{sign, week};

use chrono::{TimeZone, Utc};
use trust_kernel::canon::canonicalize_bytes;
use trust_kernel::hmac::{sign_bytes, tag_to_hex};

const KEY: [u8; 32] = [7u8; 32];
const TZ: &str = "Europe/Amsterdam";

const OLD_YAML: &str = "curfew:\n  enabled: true\n  start: \"21:30\"\n  end: \"06:00\"\ntimezone: Europe/Amsterdam\n";
const NEW_YAML: &str = "curfew:\n  enabled: true\n  start: \"22:30\"\n  end: \"06:00\"\ntimezone: Europe/Amsterdam\n";

/// Per-test scratch dir under the crate's `target/` (same-volume atomic rename; mirrors
/// trust-kernel's store tests). Uniquified by a counter so concurrent tests never collide.
fn scratch_dir(tag: &str) -> PathBuf {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join(format!("commit-{tag}-{n}"));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).expect("create scratch dir");
    dir
}

fn paths_in(dir: &Path) -> CommitPaths {
    CommitPaths {
        config: dir.join("config.yaml"),
        sanctioned: dir.join("config.sanctioned.yaml"),
        guard_json: dir.join("guard.json"),
        lock_dir: dir.to_path_buf(),
    }
}

/// Hex HMAC of the on-disk bytes of `path` (what the guard recomputes for `config.yaml`).
fn config_hmac_on_disk(path: &Path) -> String {
    let bytes = fs::read(path).expect("read config on disk");
    // The guard recomputes over the canonical bytes of whatever is on disk.
    tag_to_hex(&sign_bytes(&KEY, &canonicalize_bytes(&bytes)))
}

fn read_state(path: &Path) -> GuardState {
    let bytes = fs::read(path).expect("read guard.json");
    serde_json::from_slice(&bytes).expect("guard.json parses")
}

/// A local copy of the Phase 3 guard's verify-and-revert rule, applied to the on-disk
/// state. If `HMAC(config.yaml) != guard.json.config_hmac`, copy `config.sanctioned.yaml`
/// over `config.yaml` (crash recovery). Returns the resulting live config bytes.
fn guard_verify_and_revert(p: &CommitPaths) -> Vec<u8> {
    let state = read_state(&p.guard_json);
    let live_hmac = config_hmac_on_disk(&p.config);
    if live_hmac != state.config_hmac {
        // Revert: copy sanctioned over live.
        let sanctioned = fs::read(&p.sanctioned).expect("sanctioned readable on revert");
        fs::write(&p.config, &sanctioned).expect("revert write");
    }
    fs::read(&p.config).expect("read live after revert")
}

/// Seed an OLD-consistent on-disk state (sanctioned + live = OLD, guard.json points at OLD).
fn seed_old(p: &CommitPaths) {
    let (old_hmac, old_canon) = sign::sign_config(&KEY, OLD_YAML);
    fs::write(&p.config, &old_canon).unwrap();
    fs::write(&p.sanctioned, &old_canon).unwrap();
    let mut state = GuardState {
        config_hmac: old_hmac,
        state_hmac: String::new(),
        weekly_spent: 0,
        week_anchor: "2026-06-01".to_string(),
        ledger: vec![],
        grace: None,
    };
    state.state_hmac = state.compute_state_hmac(&KEY);
    fs::write(&p.guard_json, serde_json::to_vec_pretty(&state).unwrap()).unwrap();
}

fn loosening_decision() -> QuotaDecision {
    QuotaDecision {
        allowed: true,
        reason: None,
        costs_token: true,
        is_noop: false,
        next_reset: week::next_monday_midnight(Utc.timestamp_opt(1_780_000_000, 0).unwrap(), TZ),
    }
}

fn tightening_decision() -> QuotaDecision {
    QuotaDecision {
        allowed: true,
        reason: None,
        costs_token: false,
        is_noop: false,
        next_reset: week::next_monday_midnight(Utc.timestamp_opt(1_780_000_000, 0).unwrap(), TZ),
    }
}

#[test]
fn full_commit_leaves_all_three_files_consistent() {
    let dir = scratch_dir("full");
    let p = paths_in(&dir);
    seed_old(&p);

    let dirs = vec![("curfew.start".to_string(), Direction::Loosen)];
    let new_state = commit_change(&p, NEW_YAML, &dirs, &loosening_decision(), &KEY, 1_780_000_000)
        .expect("commit succeeds");

    // (a) live config.yaml on disk hashes to guard.json.config_hmac (consistency).
    assert_eq!(
        config_hmac_on_disk(&p.config),
        new_state.config_hmac,
        "live config HMAC must equal guard.json.config_hmac after a full commit"
    );
    // (b) sanctioned == live (both NEW canonical bytes).
    assert_eq!(
        fs::read(&p.sanctioned).unwrap(),
        fs::read(&p.config).unwrap(),
        "sanctioned and live must be the same NEW bytes after a full commit"
    );
    // (c) the on-disk guard.json equals the returned state.
    assert_eq!(read_state(&p.guard_json), new_state);
}

#[test]
fn full_commit_writes_canonical_bytes_matching_config_hmac() {
    let dir = scratch_dir("canon");
    let p = paths_in(&dir);
    seed_old(&p);

    // Feed CRLF-laden input; the on-disk bytes must be canonical and equal to what
    // config_hmac was computed over (no CRLF/BOM drift) — re-using the plan-01 signer.
    let crlf_new = "curfew:\r\n  enabled: true\r\n  start: \"22:30\"\r\n  end: \"06:00\"\r\ntimezone: Europe/Amsterdam\r\n";
    let dirs = vec![("curfew.start".to_string(), Direction::Loosen)];
    let new_state =
        commit_change(&p, crlf_new, &dirs, &loosening_decision(), &KEY, 1_780_000_000).unwrap();

    let on_disk = fs::read(&p.config).unwrap();
    assert!(!on_disk.contains(&b'\r'), "config.yaml must be CRLF-free on disk");
    let (expected_hmac, expected_canon) = sign::sign_config(&KEY, crlf_new);
    assert_eq!(on_disk, expected_canon, "on-disk bytes must be the canonical bytes");
    assert_eq!(new_state.config_hmac, expected_hmac);
}

#[test]
fn loosening_commit_spends_one_token_and_appends_ledger() {
    let dir = scratch_dir("loosen");
    let p = paths_in(&dir);
    seed_old(&p);

    let dirs = vec![("curfew.start".to_string(), Direction::Loosen)];
    let new_state =
        commit_change(&p, NEW_YAML, &dirs, &loosening_decision(), &KEY, 1_780_000_042).unwrap();

    assert_eq!(new_state.weekly_spent, 1, "a loosening commit spends exactly one token");
    assert_eq!(new_state.ledger.len(), 1, "a loosening commit appends one ledger entry");
    assert_eq!(new_state.ledger[0].ntp_timestamp, 1_780_000_042);
    assert_eq!(new_state.ledger[0].fields, vec!["curfew.start".to_string()]);
}

#[test]
fn tightening_commit_changes_no_token_and_no_ledger() {
    let dir = scratch_dir("tighten");
    let p = paths_in(&dir);
    seed_old(&p);

    let dirs = vec![("curfew.start".to_string(), Direction::Tighten)];
    let new_state =
        commit_change(&p, NEW_YAML, &dirs, &tightening_decision(), &KEY, 1_780_000_042).unwrap();

    assert_eq!(new_state.weekly_spent, 0, "a tightening commit spends no token");
    assert!(new_state.ledger.is_empty(), "a tightening commit appends no ledger entry");
}

#[test]
fn crash_before_any_write_converges_to_old() {
    let dir = scratch_dir("n0");
    let p = paths_in(&dir);
    seed_old(&p);
    let old_live = fs::read(&p.config).unwrap();

    let dirs = vec![("curfew.start".to_string(), Direction::Loosen)];
    // Stop after 0 writes: nothing changes on disk.
    let _ = commit_with_limit(&p, NEW_YAML, &dirs, &loosening_decision(), &KEY, 1_780_000_000, 0);

    let converged = guard_verify_and_revert(&p);
    assert_eq!(converged, old_live, "crash before any write must converge to OLD");
}

#[test]
fn crash_after_sanctioned_converges_to_old() {
    let dir = scratch_dir("n1");
    let p = paths_in(&dir);
    seed_old(&p);
    let old_live = fs::read(&p.config).unwrap();

    let dirs = vec![("curfew.start".to_string(), Direction::Loosen)];
    // Stop after step 1 (sanctioned=NEW only): live still OLD, guard.json still OLD => match => OLD.
    let _ = commit_with_limit(&p, NEW_YAML, &dirs, &loosening_decision(), &KEY, 1_780_000_000, 1);

    let converged = guard_verify_and_revert(&p);
    assert_eq!(converged, old_live, "crash after sanctioned-only must converge to OLD");
}

#[test]
fn crash_after_guardjson_converges_to_new() {
    let dir = scratch_dir("n2");
    let p = paths_in(&dir);
    seed_old(&p);
    let (_new_hmac, new_canon) = sign::sign_config(&KEY, NEW_YAML);

    let dirs = vec![("curfew.start".to_string(), Direction::Loosen)];
    // Stop after step 2 (sanctioned=NEW, guard.json points at NEW), live still OLD:
    // guard sees mismatch => reverts live to sanctioned (=NEW) => converges NEW.
    let _ = commit_with_limit(&p, NEW_YAML, &dirs, &loosening_decision(), &KEY, 1_780_000_000, 2);

    let converged = guard_verify_and_revert(&p);
    assert_eq!(converged, new_canon, "crash after guard.json must converge to NEW");
}

#[test]
fn crash_after_live_converges_to_new() {
    let dir = scratch_dir("n3");
    let p = paths_in(&dir);
    seed_old(&p);
    let (_new_hmac, new_canon) = sign::sign_config(&KEY, NEW_YAML);

    let dirs = vec![("curfew.start".to_string(), Direction::Loosen)];
    // Stop after step 3 (all written): fully committed, consistent NEW; guard does nothing.
    let _ = commit_with_limit(&p, NEW_YAML, &dirs, &loosening_decision(), &KEY, 1_780_000_000, 3);

    let converged = guard_verify_and_revert(&p);
    assert_eq!(converged, new_canon, "full commit must be NEW-consistent");
}
