//! RULE-02/04: the commit-rule weekly token quota state machine.
//!
//! Locked invariant (design-spec.md "Commit rule" lines 93-96 / RESEARCH lines 462-464):
//! one edit session = at most one token. An all-tighten/neutral commit is free; an all-noop
//! commit writes nothing; a loosening commit (ANY field loosens) costs exactly 1 token and
//! requires the effective `weekly_spent < 3`. A loosening commit at 0 remaining tokens is
//! blocked with a reason containing "available again Monday" plus the upcoming Monday 00:00
//! (DST-aware, via week.rs) as `next_reset`. The budget lazily resets when the stored anchor
//! predates the current Monday. This whole matrix runs offline (no I/O), mirroring
//! trust-kernel's `tests/hmac.rs` table discipline.

use chrono::{DateTime, TimeZone, Utc};

use mutation_engine::classify::Direction;
use mutation_engine::quota::decide;
use mutation_engine::state::GuardState;

const TZ: &str = "Europe/Amsterdam";

fn utc(y: i32, mo: u32, d: u32, h: u32, mi: u32) -> DateTime<Utc> {
    Utc.with_ymd_and_hms(y, mo, d, h, mi, 0).single().unwrap()
}

/// A GuardState with a given weekly_spent and a CURRENT-week anchor (no lazy reset).
fn state_current_week(weekly_spent: u8) -> GuardState {
    GuardState {
        config_hmac: String::new(),
        state_hmac: String::new(),
        weekly_spent,
        week_anchor: "2026-06-08".to_string(), // Monday of the test "now" week
        ledger: Vec::new(),
        grace: None,
    }
}

/// "Now" = Tuesday 2026-06-09 12:00 UTC, week of Monday 2026-06-08.
fn now() -> DateTime<Utc> {
    utc(2026, 6, 9, 12, 0)
}

fn dirs(pairs: &[(&str, Direction)]) -> Vec<(String, Direction)> {
    pairs.iter().map(|(f, d)| (f.to_string(), *d)).collect()
}

#[test]
fn all_tighten_commit_is_free_and_allowed() {
    let d = dirs(&[
        ("curfew.start", Direction::Tighten),
        ("watchdog.apps", Direction::Tighten),
    ]);
    let dec = decide(&d, &state_current_week(0), now(), TZ);
    assert!(dec.allowed);
    assert!(!dec.costs_token);
    assert!(!dec.is_noop);
}

#[test]
fn all_noop_commit_writes_nothing() {
    let d = dirs(&[
        ("curfew.start", Direction::Noop),
        ("timezone", Direction::Noop),
    ]);
    let dec = decide(&d, &state_current_week(0), now(), TZ);
    assert!(dec.is_noop);
    assert!(dec.allowed);
    assert!(!dec.costs_token);
}

#[test]
fn mixed_loosen_commit_costs_one_token_when_under_budget() {
    let d = dirs(&[
        ("curfew.start", Direction::Loosen),
        ("watchdog.apps", Direction::Tighten),
    ]);
    let dec = decide(&d, &state_current_week(1), now(), TZ);
    assert!(dec.allowed);
    assert!(dec.costs_token);
    assert!(!dec.is_noop);
}

#[test]
fn pure_loosen_at_full_budget_is_blocked() {
    let d = dirs(&[("curfew.start", Direction::Loosen)]);
    let dec = decide(&d, &state_current_week(3), now(), TZ);
    assert!(!dec.allowed);
    assert!(!dec.costs_token);
}

#[test]
fn blocked_decision_reason_mentions_available_again_monday() {
    let d = dirs(&[("curfew.start", Direction::Loosen)]);
    let dec = decide(&d, &state_current_week(3), now(), TZ);
    let reason = dec.reason.expect("blocked decision carries a reason");
    assert!(
        reason.contains("available again Monday"),
        "reason must contain the locked substring, got: {reason:?}"
    );
}

#[test]
fn blocked_decision_next_reset_is_upcoming_monday_dst_aware() {
    let d = dirs(&[("curfew.start", Direction::Loosen)]);
    let dec = decide(&d, &state_current_week(3), now(), TZ);
    // Upcoming Monday after 2026-06-08 is 2026-06-15 00:00 CEST == 2026-06-14 22:00 UTC.
    assert_eq!(dec.next_reset, utc(2026, 6, 14, 22, 0));
}

#[test]
fn loosen_at_two_spent_is_allowed_third_token() {
    let d = dirs(&[("curfew.start", Direction::Loosen)]);
    let dec = decide(&d, &state_current_week(2), now(), TZ);
    assert!(dec.allowed);
    assert!(dec.costs_token);
}

#[test]
fn lazy_reset_allows_loosen_in_new_week_despite_stale_spent_three() {
    // Stored spent=3 but the anchor is last week -> effective spent is 0 -> loosening allowed.
    let mut s = state_current_week(3);
    s.week_anchor = "2026-06-01".to_string(); // previous Monday (stale)
    let d = dirs(&[("curfew.start", Direction::Loosen)]);
    let dec = decide(&d, &s, now(), TZ);
    assert!(dec.allowed, "a fresh week must allow loosening even if stored spent was 3");
    assert!(dec.costs_token);
}

#[test]
fn next_reset_present_even_on_allowed_decisions() {
    // next_reset is always the upcoming Monday so the UI can show it regardless of outcome.
    let d = dirs(&[("curfew.start", Direction::Loosen)]);
    let dec = decide(&d, &state_current_week(0), now(), TZ);
    assert_eq!(dec.next_reset, utc(2026, 6, 14, 22, 0));
}
