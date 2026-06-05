//! RULE-01: the per-field direction classifier must label every spec-table row.
//!
//! Locked invariant (design-spec.md "Direction classifier" / RESEARCH lines 296-311):
//! each per-field diff is `Tighten`, `Loosen`, or `Noop` exactly per the field table; a
//! field missing from either side is `Noop` (defensive A2, never a silent loosen); and a
//! commit is a loosening commit iff ANY field loosens (fail-safe toward charging a token,
//! threat T-02-05). These tests assert the whole table offline, one #[test] per claim —
//! the same KAT/table discipline as trust-kernel's `tests/hmac.rs`.

use mutation_engine::classify::{classify_change, is_loosening_commit, Direction};

/// Direction of a single named field in a classified diff (test helper).
fn dir_of(dirs: &[(String, Direction)], field: &str) -> Direction {
    dirs.iter()
        .find(|(f, _)| f == field)
        .map(|(_, d)| *d)
        .unwrap_or_else(|| panic!("field `{field}` not in classified diff: {dirs:?}"))
}

// ---------------------------------------------------------------------------
// Booleans: true->false = Loosen, false->true = Tighten
// ---------------------------------------------------------------------------

#[test]
fn curfew_enabled_true_to_false_is_loosen() {
    let old = "curfew:\n  enabled: true\n";
    let new = "curfew:\n  enabled: false\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.enabled"), Direction::Loosen);
}

#[test]
fn curfew_enabled_false_to_true_is_tighten() {
    let old = "curfew:\n  enabled: false\n";
    let new = "curfew:\n  enabled: true\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.enabled"), Direction::Tighten);
}

#[test]
fn curfew_block_when_offline_true_to_false_is_loosen() {
    let old = "curfew:\n  block_when_offline: true\n";
    let new = "curfew:\n  block_when_offline: false\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.block_when_offline"), Direction::Loosen);
}

#[test]
fn clock_protection_enabled_true_to_false_is_loosen() {
    let old = "clock_protection:\n  enabled: true\n";
    let new = "clock_protection:\n  enabled: false\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "clock_protection.enabled"), Direction::Loosen);
}

#[test]
fn watchdog_enabled_false_to_true_is_tighten() {
    let old = "watchdog:\n  enabled: false\n";
    let new = "watchdog:\n  enabled: true\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "watchdog.enabled"), Direction::Tighten);
}

// ---------------------------------------------------------------------------
// Time fields: curfew.start later = Loosen / earlier = Tighten;
//              curfew.end earlier = Loosen / later = Tighten
// ---------------------------------------------------------------------------

#[test]
fn curfew_start_later_is_loosen() {
    let old = "curfew:\n  start: \"22:00\"\n";
    let new = "curfew:\n  start: \"23:30\"\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.start"), Direction::Loosen);
}

#[test]
fn curfew_start_earlier_is_tighten() {
    let old = "curfew:\n  start: \"23:00\"\n";
    let new = "curfew:\n  start: \"21:00\"\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.start"), Direction::Tighten);
}

#[test]
fn curfew_end_earlier_is_loosen() {
    let old = "curfew:\n  end: \"07:00\"\n";
    let new = "curfew:\n  end: \"06:00\"\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.end"), Direction::Loosen);
}

#[test]
fn curfew_end_later_is_tighten() {
    let old = "curfew:\n  end: \"06:00\"\n";
    let new = "curfew:\n  end: \"08:00\"\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.end"), Direction::Tighten);
}

// ---------------------------------------------------------------------------
// Numerics: max_offset_minutes increase = Loosen; check_interval_seconds increase = Loosen
// ---------------------------------------------------------------------------

#[test]
fn clock_protection_max_offset_increase_is_loosen() {
    let old = "clock_protection:\n  max_offset_minutes: 5\n";
    let new = "clock_protection:\n  max_offset_minutes: 30\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(
        dir_of(&dirs, "clock_protection.max_offset_minutes"),
        Direction::Loosen
    );
}

#[test]
fn clock_protection_max_offset_decrease_is_tighten() {
    let old = "clock_protection:\n  max_offset_minutes: 30\n";
    let new = "clock_protection:\n  max_offset_minutes: 5\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(
        dir_of(&dirs, "clock_protection.max_offset_minutes"),
        Direction::Tighten
    );
}

#[test]
fn watchdog_check_interval_increase_is_loosen() {
    let old = "watchdog:\n  check_interval_seconds: 30\n";
    let new = "watchdog:\n  check_interval_seconds: 120\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(
        dir_of(&dirs, "watchdog.check_interval_seconds"),
        Direction::Loosen
    );
}

// ---------------------------------------------------------------------------
// Lists: allow_commands add = Loosen / remove = Tighten;
//        watchdog.apps remove = Loosen / add = Tighten
// ---------------------------------------------------------------------------

#[test]
fn curfew_allow_commands_add_is_loosen() {
    let old = "curfew:\n  allow_commands: [git]\n";
    let new = "curfew:\n  allow_commands: [git, npm]\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.allow_commands"), Direction::Loosen);
}

#[test]
fn curfew_allow_commands_remove_is_tighten() {
    let old = "curfew:\n  allow_commands: [git, npm]\n";
    let new = "curfew:\n  allow_commands: [git]\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.allow_commands"), Direction::Tighten);
}

#[test]
fn watchdog_apps_remove_is_loosen() {
    let old = "watchdog:\n  apps: [discord.exe, steam.exe]\n";
    let new = "watchdog:\n  apps: [discord.exe]\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "watchdog.apps"), Direction::Loosen);
}

#[test]
fn watchdog_apps_add_is_tighten() {
    let old = "watchdog:\n  apps: [discord.exe]\n";
    let new = "watchdog:\n  apps: [discord.exe, steam.exe]\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "watchdog.apps"), Direction::Tighten);
}

// ---------------------------------------------------------------------------
// schedule.<day>: set off / later start / earlier end = Loosen
// ---------------------------------------------------------------------------

#[test]
fn schedule_day_set_off_is_loosen() {
    let old = "curfew:\n  schedule:\n    monday: \"22:00-07:00\"\n";
    let new = "curfew:\n  schedule:\n    monday: \"off\"\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.schedule.monday"), Direction::Loosen);
}

#[test]
fn schedule_day_later_start_is_loosen() {
    let old = "curfew:\n  schedule:\n    friday: \"22:00-07:00\"\n";
    let new = "curfew:\n  schedule:\n    friday: \"23:30-07:00\"\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.schedule.friday"), Direction::Loosen);
}

#[test]
fn schedule_day_earlier_end_is_loosen() {
    let old = "curfew:\n  schedule:\n    sunday: \"22:00-08:00\"\n";
    let new = "curfew:\n  schedule:\n    sunday: \"22:00-06:00\"\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.schedule.sunday"), Direction::Loosen);
}

#[test]
fn schedule_day_stricter_window_is_tighten() {
    let old = "curfew:\n  schedule:\n    saturday: \"23:00-06:00\"\n";
    let new = "curfew:\n  schedule:\n    saturday: \"22:00-08:00\"\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.schedule.saturday"), Direction::Tighten);
}

// ---------------------------------------------------------------------------
// timezone: ANY change = Loosen (potential bypass)
// ---------------------------------------------------------------------------

#[test]
fn timezone_any_change_is_loosen() {
    let old = "timezone: Europe/Amsterdam\n";
    let new = "timezone: America/New_York\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "timezone"), Direction::Loosen);
}

// ---------------------------------------------------------------------------
// Noop: identical field, and missing-on-either-side (defensive A2, no panic)
// ---------------------------------------------------------------------------

#[test]
fn identical_field_is_noop() {
    let old = "curfew:\n  start: \"22:00\"\n";
    let new = "curfew:\n  start: \"22:00\"\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.start"), Direction::Noop);
}

#[test]
fn field_missing_on_new_side_is_noop_no_panic() {
    let old = "curfew:\n  enabled: true\n";
    let new = "watchdog:\n  enabled: true\n";
    let dirs = classify_change(old, new).unwrap();
    // curfew.enabled present in old, absent in new -> Noop (never a silent loosen).
    assert_eq!(dir_of(&dirs, "curfew.enabled"), Direction::Noop);
}

#[test]
fn field_missing_on_both_sides_is_noop() {
    let old = "curfew:\n  enabled: true\n";
    let new = "curfew:\n  enabled: true\n";
    let dirs = classify_change(old, new).unwrap();
    // timezone absent on both sides -> Noop.
    assert_eq!(dir_of(&dirs, "timezone"), Direction::Noop);
}

// ---------------------------------------------------------------------------
// is_loosening_commit: true iff ANY field is Loosen
// ---------------------------------------------------------------------------

#[test]
fn multi_field_diff_returns_per_field_directions() {
    let old = "curfew:\n  enabled: true\n  start: \"22:00\"\n";
    let new = "curfew:\n  enabled: true\n  start: \"23:00\"\n";
    let dirs = classify_change(old, new).unwrap();
    assert_eq!(dir_of(&dirs, "curfew.enabled"), Direction::Noop);
    assert_eq!(dir_of(&dirs, "curfew.start"), Direction::Loosen);
}

#[test]
fn is_loosening_commit_true_when_any_loosen() {
    let dirs = vec![
        ("curfew.enabled".to_string(), Direction::Tighten),
        ("curfew.start".to_string(), Direction::Loosen),
        ("timezone".to_string(), Direction::Noop),
    ];
    assert!(is_loosening_commit(&dirs));
}

#[test]
fn is_loosening_commit_false_when_all_tighten_or_noop() {
    let dirs = vec![
        ("curfew.enabled".to_string(), Direction::Tighten),
        ("curfew.start".to_string(), Direction::Tighten),
        ("timezone".to_string(), Direction::Noop),
    ];
    assert!(!is_loosening_commit(&dirs));
}
