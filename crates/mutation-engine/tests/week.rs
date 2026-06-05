//! RULE-03: the weekly budget resets at Monday 00:00 in the configured timezone, DST-aware.
//!
//! Locked invariant (RESEARCH Pattern 2 / anti-pattern lines 313-318, Pitfall 5): the
//! anchor is the most-recent local Monday 00:00 resolved to a real UTC instant via
//! `chrono_tz::Tz::from_local_datetime` with explicit `MappedLocalTime` handling — NEVER
//! naive `+7*24h` (a transition week is 167 or 169 hours). A fall-back DST night
//! (`Ambiguous`) resolves deterministically to the earliest instant. The reset helper
//! rolls the budget forward iff the stored anchor predates the current Monday. These tests
//! assert a normal week, a fall-back DST week, and the reset rule offline (threat T-02-06).

use chrono::{DateTime, TimeZone, Utc};
use chrono_tz::Tz;

use mutation_engine::week::{most_recent_monday_midnight, reset_decision};

/// Helper: build a UTC instant from components.
fn utc(y: i32, mo: u32, d: u32, h: u32, mi: u32) -> DateTime<Utc> {
    Utc.with_ymd_and_hms(y, mo, d, h, mi, 0).single().unwrap()
}

#[test]
fn normal_week_returns_that_weeks_monday_midnight_local_as_utc() {
    // Tuesday 2026-06-09 14:00 local Europe/Amsterdam (CEST, UTC+2) -> 12:00 UTC.
    // The week's Monday is 2026-06-08; local 00:00 CEST == 2026-06-07 22:00 UTC.
    let now = utc(2026, 6, 9, 12, 0);
    let anchor = most_recent_monday_midnight(now, "Europe/Amsterdam");

    let tz: Tz = "Europe/Amsterdam".parse().unwrap();
    let local = anchor.with_timezone(&tz);
    // The resolved instant must be Monday 00:00 local.
    assert_eq!(local.format("%Y-%m-%d %H:%M").to_string(), "2026-06-08 00:00");
    // And as UTC it is the previous day 22:00 (CEST = UTC+2).
    assert_eq!(anchor, utc(2026, 6, 7, 22, 0));
}

#[test]
fn monday_morning_resolves_to_same_day_midnight() {
    // Monday 2026-06-08 09:00 CEST -> anchor is the SAME Monday 00:00.
    let now = utc(2026, 6, 8, 7, 0); // 09:00 CEST
    let anchor = most_recent_monday_midnight(now, "Europe/Amsterdam");
    assert_eq!(anchor, utc(2026, 6, 7, 22, 0));
}

#[test]
fn fall_back_dst_week_resolves_to_earliest_no_panic() {
    // Europe/Amsterdam fall-back is 2026-10-25 (clocks go 03:00->02:00). The clock change
    // is on a Sunday, not at Monday 00:00, but a week anchored just after the transition
    // must still resolve deterministically and never panic. Use Wednesday 2026-10-28 12:00
    // local (CET, UTC+1) -> 11:00 UTC; the week's Monday is 2026-10-26 (already CET).
    let now = utc(2026, 10, 28, 11, 0);
    let anchor = most_recent_monday_midnight(now, "Europe/Amsterdam");
    let tz: Tz = "Europe/Amsterdam".parse().unwrap();
    let local = anchor.with_timezone(&tz);
    assert_eq!(local.format("%Y-%m-%d %H:%M").to_string(), "2026-10-26 00:00");
    // Monday 2026-10-26 00:00 CET (UTC+1) == 2026-10-25 23:00 UTC.
    assert_eq!(anchor, utc(2026, 10, 25, 23, 0));
}

#[test]
fn dst_transition_week_is_not_naive_168h() {
    // The week containing the fall-back (Mon 2026-10-19 .. Mon 2026-10-26) is 169 hours.
    // A naive +7*24h from the prior Monday's UTC instant would land an hour off. Assert the
    // two consecutive Monday anchors differ by 169h (one extra hour), proving non-naive math.
    let mon_a = most_recent_monday_midnight(utc(2026, 10, 21, 12, 0), "Europe/Amsterdam"); // week of Oct 19
    let mon_b = most_recent_monday_midnight(utc(2026, 10, 28, 12, 0), "Europe/Amsterdam"); // week of Oct 26
    let delta_hours = (mon_b - mon_a).num_hours();
    assert_eq!(
        delta_hours, 169,
        "the fall-back week spans 169h, not naive 168h (+7*24)"
    );
}

#[test]
fn reset_when_stored_anchor_predates_current_monday() {
    // Stored anchor is last week's Monday; now is this week -> reset.
    let now = utc(2026, 6, 9, 12, 0); // Tuesday, week of Mon 2026-06-08
    let stored = "2026-06-01"; // previous Monday
    let dec = reset_decision(stored, now, "Europe/Amsterdam");
    assert!(dec.should_reset);
    assert_eq!(dec.new_anchor, "2026-06-08");
}

#[test]
fn no_reset_when_stored_anchor_is_current_monday() {
    let now = utc(2026, 6, 9, 12, 0); // Tuesday, week of Mon 2026-06-08
    let stored = "2026-06-08"; // current Monday
    let dec = reset_decision(stored, now, "Europe/Amsterdam");
    assert!(!dec.should_reset);
    assert_eq!(dec.new_anchor, "2026-06-08");
}

#[test]
fn next_monday_midnight_is_one_dst_aware_week_ahead() {
    // Across the fall-back week, the NEXT Monday after the week-of-Oct-19 anchor is 169h on.
    let now = utc(2026, 10, 21, 12, 0); // week of Mon 2026-10-19
    let next = mutation_engine::week::next_monday_midnight(now, "Europe/Amsterdam");
    let cur = most_recent_monday_midnight(now, "Europe/Amsterdam");
    assert_eq!((next - cur).num_hours(), 169);
    let tz: Tz = "Europe/Amsterdam".parse().unwrap();
    assert_eq!(
        next.with_timezone(&tz).format("%Y-%m-%d %H:%M").to_string(),
        "2026-10-26 00:00"
    );
}
