//! lock_status curfew-window evaluator truth table (Open Q1 / Pitfall 1, the highest-risk
//! net-new logic of Phase 4). Mirrors `quota.rs`'s offline diff-table discipline: a `utc()`
//! helper, a fixed `now()` per case, a small config builder, and one `#[test]` per behavior
//! case from the plan. Every case asserts `{locked, grace_active, boundary_unix,
//! boundary_kind}` against `lock_status(config_yaml, now)` — a pure function, no I/O.
//!
//! The cases enumerate the written precedence spec (documented in lock_status.rs):
//!   1 inside-window simple      2 outside-window simple   3 overnight-wrap correctness
//!   4 non-overnight window      5 enabled=false           6 schedule.<day> precedence
//!   7 defensive absent/malformed (fail-safe-LOCKED)       8 bad-tz default (no panic)

use chrono::{DateTime, TimeZone, Utc};

use mutation_engine::lock_status::{lock_status, NO_UPCOMING_LOCK};

const TZ: &str = "Europe/Amsterdam";

/// Build a `DateTime<Utc>` from Y-M-D H:M (seconds = 0), like quota.rs.
fn utc(y: i32, mo: u32, d: u32, h: u32, mi: u32) -> DateTime<Utc> {
    Utc.with_ymd_and_hms(y, mo, d, h, mi, 0).single().unwrap()
}

/// The local minute-of-day `min` on the local date of `local_day` (Y-M-D), in `Europe/Amsterdam`,
/// returned as a unix-secs `i64` — what `boundary_unix` should equal. Built by converting the
/// expected LOCAL instant to UTC, so the test asserts the wall-clock boundary the UI shows.
fn local_unix(y: i32, mo: u32, d: u32, h: u32, mi: u32) -> i64 {
    use chrono_tz::Europe::Amsterdam;
    Amsterdam
        .with_ymd_and_hms(y, mo, d, h, mi, 0)
        .single()
        .unwrap()
        .timestamp()
}

/// A simple non-schedule config: curfew enabled with a single start/end window + tz.
fn cfg_window(start: &str, end: &str) -> String {
    format!(
        "timezone: \"{TZ}\"\ncurfew:\n  enabled: true\n  start: \"{start}\"\n  end: \"{end}\"\n"
    )
}

// ---- Test 1: inside window, simple (overnight 23:00-07:00, now 00:30 local) ----------------
#[test]
fn inside_window_simple_is_locked_boundary_is_curfew_end() {
    let cfg = cfg_window("23:00", "07:00");
    // 2026-06-09 00:30 CEST == 2026-06-08 22:30 UTC.
    let now = utc(2026, 6, 8, 22, 30);
    let s = lock_status(&cfg, now);
    assert!(s.locked, "00:30 is inside the 23:00-07:00 overnight window");
    assert_eq!(s.boundary_kind, "curfew_end");
    // The window end is TODAY's (local) 07:00.
    assert_eq!(s.boundary_unix, local_unix(2026, 6, 9, 7, 0));
}

// ---- Test 2: outside window, simple (now 12:00 local) --------------------------------------
#[test]
fn outside_window_simple_is_open_boundary_is_next_lock() {
    let cfg = cfg_window("23:00", "07:00");
    // 2026-06-09 12:00 CEST == 10:00 UTC.
    let now = utc(2026, 6, 9, 10, 0);
    let s = lock_status(&cfg, now);
    assert!(!s.locked, "12:00 is outside the 23:00-07:00 window");
    assert_eq!(s.boundary_kind, "next_lock");
    // Next lock is TODAY's (local) 23:00.
    assert_eq!(s.boundary_unix, local_unix(2026, 6, 9, 23, 0));
}

// ---- Test 3: overnight wrap correctness (now 23:30, boundary is NEXT day 07:00) ------------
#[test]
fn overnight_wrap_boundary_lands_on_next_calendar_day() {
    let cfg = cfg_window("23:00", "07:00");
    // 2026-06-09 23:30 CEST == 21:30 UTC.
    let now = utc(2026, 6, 9, 21, 30);
    let s = lock_status(&cfg, now);
    assert!(s.locked, "23:30 is inside the 23:00-07:00 overnight window");
    assert_eq!(s.boundary_kind, "curfew_end");
    // The window crosses midnight: the end is the NEXT calendar day's 07:00, never naive +24h.
    assert_eq!(s.boundary_unix, local_unix(2026, 6, 10, 7, 0));
}

// ---- Test 4: non-overnight window (09:00-17:00) — both sides of the window -----------------
#[test]
fn non_overnight_window_before_open_boundary_today_start() {
    let cfg = cfg_window("09:00", "17:00");
    // 2026-06-09 08:00 CEST == 06:00 UTC.
    let now = utc(2026, 6, 9, 6, 0);
    let s = lock_status(&cfg, now);
    assert!(!s.locked, "08:00 is before the 09:00-17:00 window");
    assert_eq!(s.boundary_kind, "next_lock");
    assert_eq!(s.boundary_unix, local_unix(2026, 6, 9, 9, 0));
}

#[test]
fn non_overnight_window_inside_locked_boundary_today_end() {
    let cfg = cfg_window("09:00", "17:00");
    // 2026-06-09 10:00 CEST == 08:00 UTC.
    let now = utc(2026, 6, 9, 8, 0);
    let s = lock_status(&cfg, now);
    assert!(s.locked, "10:00 is inside the 09:00-17:00 window");
    assert_eq!(s.boundary_kind, "curfew_end");
    assert_eq!(s.boundary_unix, local_unix(2026, 6, 9, 17, 0));
}

// ---- Test 5: enabled=false is NEVER locked ------------------------------------------------
#[test]
fn enabled_false_is_never_locked() {
    let cfg =
        format!("timezone: \"{TZ}\"\ncurfew:\n  enabled: false\n  start: \"23:00\"\n  end: \"07:00\"\n");
    // An instant that WOULD be inside the window if enabled.
    let now = utc(2026, 6, 8, 22, 30); // 00:30 local
    let s = lock_status(&cfg, now);
    assert!(!s.locked, "enabled=false must never be locked");
    assert!(!s.grace_active);
    // CR-02: a DISABLED curfew has no upcoming lock — the boundary must be the "no upcoming lock"
    // sentinel, NEVER a `curfew.start`-derived today/tomorrow instant and NEVER `now` (which would
    // render a stuck 00:00:00 countdown under an OPEN word).
    assert_eq!(s.boundary_kind, "none");
    assert_eq!(s.boundary_unix, NO_UPCOMING_LOCK);
    assert!(
        s.boundary_unix > now.timestamp(),
        "an OPEN status must never advertise a boundary at or behind now"
    );
}

// ---- Test 6: schedule.<day> precedence over start/end -------------------------------------
#[test]
fn schedule_off_day_overrides_startend_and_is_unlocked() {
    // 2026-06-08 is a Monday. schedule.monday = "off" -> Monday is unlocked even at 00:30.
    let cfg = format!(
        "timezone: \"{TZ}\"\ncurfew:\n  enabled: true\n  start: \"23:00\"\n  end: \"07:00\"\n  schedule:\n    monday: \"off\"\n"
    );
    // 2026-06-08 00:30 CEST == 2026-06-07 22:30 UTC (a Monday, local).
    let now = utc(2026, 6, 7, 22, 30);
    let s = lock_status(&cfg, now);
    assert!(!s.locked, "schedule.monday=off overrides start/end -> unlocked Monday");
    // CR-02: an `off` day does not scan future days for the advisory display, and today's
    // `curfew.start` would resolve to a lock instant the guard never enforces on an off day.
    // The boundary must be the "no upcoming lock" sentinel, never a false today/tomorrow start
    // and never `now`.
    assert_eq!(s.boundary_kind, "none");
    assert_eq!(s.boundary_unix, NO_UPCOMING_LOCK);
    assert!(
        s.boundary_unix > now.timestamp(),
        "an OPEN status must never advertise a boundary at or behind now"
    );
}

#[test]
fn schedule_day_window_overrides_startend() {
    // 2026-06-09 is a Tuesday. schedule.tuesday = "20:00-06:00" should be used, not start/end.
    let cfg = format!(
        "timezone: \"{TZ}\"\ncurfew:\n  enabled: true\n  start: \"23:00\"\n  end: \"07:00\"\n  schedule:\n    tuesday: \"20:00-06:00\"\n"
    );
    // 2026-06-09 21:00 CEST == 19:00 UTC. Inside tuesday's 20:00-06:00, NOT inside start/end yet.
    let now = utc(2026, 6, 9, 19, 0);
    let s = lock_status(&cfg, now);
    assert!(s.locked, "tuesday window 20:00-06:00 must apply (locked at 21:00)");
    assert_eq!(s.boundary_kind, "curfew_end");
    // End is NEXT day (Wednesday) 06:00 (overnight wrap of the schedule window).
    assert_eq!(s.boundary_unix, local_unix(2026, 6, 10, 6, 0));
}

// ---- Test 7: defensive absent/malformed -> fail-safe LOCKED (never silent unlock) ---------
#[test]
fn missing_curfew_block_fails_safe_locked() {
    let cfg = format!("timezone: \"{TZ}\"\n"); // no curfew block at all
    let now = utc(2026, 6, 9, 10, 0);
    let s = lock_status(&cfg, now);
    assert!(s.locked, "a missing curfew block must fail-safe LOCKED, never silently unlock");
}

#[test]
fn malformed_window_fails_safe_locked() {
    // enabled=true but a garbage start time -> cannot evaluate -> fail-safe LOCKED.
    let cfg = format!(
        "timezone: \"{TZ}\"\ncurfew:\n  enabled: true\n  start: \"99:99\"\n  end: \"07:00\"\n"
    );
    let now = utc(2026, 6, 9, 10, 0);
    let s = lock_status(&cfg, now);
    assert!(s.locked, "a malformed window must fail-safe LOCKED, never silently unlock");
}

// ---- Test 8: bad timezone defaults to UTC, never panics -----------------------------------
#[test]
fn bad_timezone_defaults_to_utc_no_panic() {
    let cfg =
        "timezone: \"Not/AZone\"\ncurfew:\n  enabled: true\n  start: \"09:00\"\n  end: \"17:00\"\n"
            .to_string();
    // 12:00 UTC. With tz defaulting to UTC, 12:00 is inside 09:00-17:00 -> locked.
    let now = utc(2026, 6, 9, 12, 0);
    let s = lock_status(&cfg, now);
    assert!(s.locked, "bad tz falls back to UTC; 12:00 UTC is inside 09:00-17:00");
    assert_eq!(s.boundary_kind, "curfew_end");
    // End is today's 17:00 in UTC.
    assert_eq!(s.boundary_unix, utc(2026, 6, 9, 17, 0).timestamp());
}
