//! Daily-grace tests (RED-first, per the TDD directive).
//!
//! Proves the RULE-05 grant half (threats T-02-11/12/14): "+8" grants a once-per-true-day
//! 8-minute window recorded in signed state, computed from NTP true time in the configured
//! tz (Pitfall 4 — NOT the system clock), refused if already used today OR if NTP is
//! unreachable, costing no weekly token. All five behaviors run offline with a `FakeTrueTime`.

use std::fs;
use std::path::{Path, PathBuf};

use mutation_engine::commit::CommitPaths;
use mutation_engine::grace::use_grace;
use mutation_engine::ntp::{FakeTrueTime, NtpTrueTime};
use mutation_engine::state::{GuardState, GraceWindow, MutationError};

const KEY: [u8; 32] = [9u8; 32];
const TZ: &str = "Europe/Amsterdam";

/// Per-test scratch dir under the crate's `target/` (mirrors trust-kernel store tests).
fn scratch_dir(tag: &str) -> PathBuf {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join(format!("grace-{tag}-{n}"));
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

fn fake(unix_secs: i64) -> FakeTrueTime {
    FakeTrueTime::ok(NtpTrueTime {
        unix_secs,
        frac: 0,
        offset: 0,
    })
}

/// Seed guard.json with the given state (re-signed), return it.
fn seed_state(p: &CommitPaths, mut state: GuardState) -> GuardState {
    state.state_hmac = state.compute_state_hmac(&KEY);
    fs::write(&p.guard_json, serde_json::to_vec_pretty(&state).unwrap()).unwrap();
    state
}

fn base_state() -> GuardState {
    GuardState {
        config_hmac: "deadbeef".to_string(),
        state_hmac: String::new(),
        weekly_spent: 2,
        week_anchor: "2026-06-01".to_string(),
        ledger: vec![],
        grace: None,
    }
}

fn read_state(p: &CommitPaths) -> GuardState {
    serde_json::from_slice(&fs::read(&p.guard_json).unwrap()).unwrap()
}

// 2026-06-05T10:00:00Z -> Europe/Amsterdam (summer, UTC+2) = 2026-06-05 12:00 local => "2026-06-05".
const NOON_JUN5_UTC: i64 = 1_780_653_600; // 2026-06-05T10:00:00Z

#[test]
fn grant_writes_window_and_costs_no_token() {
    let dir = scratch_dir("grant");
    let p = paths_in(&dir);
    let seeded = seed_state(&p, base_state());

    let window = use_grace(&p, &seeded, &fake(NOON_JUN5_UTC), TZ, &KEY).expect("grace granted");

    assert_eq!(window.date, "2026-06-05", "true-day in the configured tz");
    assert_eq!(window.window_start, NOON_JUN5_UTC);
    assert_eq!(window.window_end, NOON_JUN5_UTC + 8 * 60, "8-minute window");

    let after = read_state(&p);
    assert_eq!(after.grace, Some(window), "grace written into guard.json");
    assert_eq!(after.weekly_spent, 2, "grace spends NO weekly token");
    // Re-signed: state_hmac matches a fresh re-derivation.
    assert_eq!(after.state_hmac, after.compute_state_hmac(&KEY));
}

#[test]
fn second_grant_same_true_day_is_refused_and_leaves_file_unchanged() {
    let dir = scratch_dir("reuse");
    let p = paths_in(&dir);
    // State already has a grace granted earlier the SAME true-day.
    let mut state = base_state();
    state.grace = Some(GraceWindow {
        date: "2026-06-05".to_string(),
        window_start: NOON_JUN5_UTC - 3600,
        window_end: NOON_JUN5_UTC - 3600 + 8 * 60,
    });
    let seeded = seed_state(&p, state);
    let before_bytes = fs::read(&p.guard_json).unwrap();

    let result = use_grace(&p, &seeded, &fake(NOON_JUN5_UTC), TZ, &KEY);
    assert!(
        matches!(result, Err(MutationError::GraceAlreadyUsedToday)),
        "a second grant on the same true-day must be refused"
    );
    assert_eq!(
        fs::read(&p.guard_json).unwrap(),
        before_bytes,
        "guard.json must be byte-unchanged on a refused reuse"
    );
}

#[test]
fn grant_on_a_new_true_day_succeeds_again() {
    let dir = scratch_dir("newday");
    let p = paths_in(&dir);
    let mut state = base_state();
    // Yesterday's grace.
    state.grace = Some(GraceWindow {
        date: "2026-06-04".to_string(),
        window_start: NOON_JUN5_UTC - 86_400,
        window_end: NOON_JUN5_UTC - 86_400 + 8 * 60,
    });
    let seeded = seed_state(&p, state);

    // Now is the NEXT true-day.
    let window = use_grace(&p, &seeded, &fake(NOON_JUN5_UTC), TZ, &KEY)
        .expect("a new true-day allows a fresh grant");
    assert_eq!(window.date, "2026-06-05");
    assert_eq!(read_state(&p).grace, Some(window));
}

#[test]
fn ntp_unreachable_refuses_and_leaves_file_unchanged() {
    let dir = scratch_dir("offline");
    let p = paths_in(&dir);
    let seeded = seed_state(&p, base_state());
    let before_bytes = fs::read(&p.guard_json).unwrap();

    let result = use_grace(&p, &seeded, &FakeTrueTime::unreachable(), TZ, &KEY);
    assert!(
        matches!(result, Err(MutationError::NtpUnreachable)),
        "grace must be refused when true time cannot be verified — never the app clock"
    );
    assert_eq!(
        fs::read(&p.guard_json).unwrap(),
        before_bytes,
        "guard.json must be byte-unchanged when NTP is unreachable"
    );
}

#[test]
fn true_day_is_derived_in_configured_tz_not_utc() {
    let dir = scratch_dir("tzboundary");
    let p = paths_in(&dir);
    let seeded = seed_state(&p, base_state());

    // 2026-06-05T22:30:00Z. In Europe/Amsterdam (summer, UTC+2) that is 2026-06-06 00:30
    // LOCAL — so the true-day is 2026-06-06, NOT the UTC date 2026-06-05.
    let near_boundary: i64 = 1_780_698_600; // 2026-06-05T22:30:00Z
    let window =
        use_grace(&p, &seeded, &fake(near_boundary), TZ, &KEY).expect("grant near tz boundary");
    assert_eq!(
        window.date, "2026-06-06",
        "true-day must be the LOCAL (configured tz) date, not the UTC date"
    );
}
