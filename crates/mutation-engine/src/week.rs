//! RULE-03: DST-aware most-recent-Monday-00:00 week reset, in the configured timezone.
//!
//! The weekly loosen budget resets at **Monday 00:00 local time** in the configured IANA
//! timezone. The anchor is computed by stepping back to the local Monday date, building the
//! local `00:00` `NaiveDateTime`, and resolving it to a real UTC instant via
//! [`chrono_tz::Tz::from_local_datetime`] with **explicit** `MappedLocalTime` handling:
//! `Single` (normal), `Ambiguous` -> earliest (deterministic fall-back), `None` -> step to
//! `01:00` (spring-forward gap; defensive). The week containing a DST transition is 167 or
//! 169 hours, so naive `+ Duration::weeks(1)` / `+7*24h` is a **forbidden anti-pattern**
//! (threat T-02-06) — `next_monday_midnight` re-derives the next Monday from the DATE.
//!
//! This module is 100% pure — no file I/O — so the whole reset matrix runs offline,
//! mirroring trust-kernel's `canon.rs`.

use chrono::{DateTime, Datelike, Duration, NaiveDate, NaiveTime, TimeZone, Utc};
use chrono_tz::Tz;

/// The most-recent local Monday 00:00 (configured tz), as a UTC instant.
///
/// Steps back `weekday().num_days_from_monday()` days from the local date, builds local
/// midnight, and resolves DST gaps/overlaps explicitly. Falls back to a UTC interpretation
/// if `tz_name` is not a valid IANA name (defensive — callers source it from config).
pub fn most_recent_monday_midnight(now_utc: DateTime<Utc>, tz_name: &str) -> DateTime<Utc> {
    let tz = parse_tz(tz_name);
    let local = now_utc.with_timezone(&tz);
    let back = local.weekday().num_days_from_monday() as i64;
    let monday_date: NaiveDate = local.date_naive() - Duration::days(back);
    resolve_local_midnight(monday_date, tz)
}

/// The NEXT Monday 00:00 (configured tz) strictly after the current week's anchor, as UTC.
///
/// Re-derived from the local Monday DATE + 7 *days* (then re-resolved through the tz), NOT
/// by adding `Duration::weeks(1)` to the UTC instant — so a DST transition in the upcoming
/// week yields the correct local midnight rather than a drifted instant (RULE-03 / T-02-06).
pub fn next_monday_midnight(now_utc: DateTime<Utc>, tz_name: &str) -> DateTime<Utc> {
    let tz = parse_tz(tz_name);
    let local = now_utc.with_timezone(&tz);
    let back = local.weekday().num_days_from_monday() as i64;
    let this_monday: NaiveDate = local.date_naive() - Duration::days(back);
    // Add 7 calendar days to the DATE, then resolve local midnight again (DST-aware).
    let next_monday = this_monday + Duration::days(7);
    resolve_local_midnight(next_monday, tz)
}

/// Resolve a local-midnight `NaiveDate` to a real UTC instant, handling DST explicitly.
fn resolve_local_midnight(date: NaiveDate, tz: Tz) -> DateTime<Utc> {
    let naive_midnight = date.and_time(NaiveTime::from_hms_opt(0, 0, 0).unwrap());
    let local_dt = match tz.from_local_datetime(&naive_midnight) {
        chrono::MappedLocalTime::Single(dt) => dt,
        // Fall-back overlap: pick the earliest instant (deterministic).
        chrono::MappedLocalTime::Ambiguous(earliest, _latest) => earliest,
        // Spring-forward gap at 00:00 (rare; defensive): 01:00 always exists.
        chrono::MappedLocalTime::None => tz
            .from_local_datetime(&date.and_hms_opt(1, 0, 0).unwrap())
            .single()
            .expect("01:00 local always exists after a spring-forward gap"),
    };
    local_dt.with_timezone(&Utc)
}

/// The outcome of a lazy weekly-budget reset check.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResetDecision {
    /// True iff the stored anchor predates the current week's Monday (budget must roll).
    pub should_reset: bool,
    /// The current week's Monday ISO date "YYYY-MM-DD" (the value to store going forward).
    pub new_anchor: String,
}

/// Decide whether the weekly budget should reset, comparing the stored anchor to now.
///
/// `stored_anchor` is the persisted Monday ISO date ("YYYY-MM-DD"). The comparison is done
/// on the resolved UTC instants (not string compare) so a tz/format quirk can't mis-order
/// them. If `stored_anchor` is unparseable, the decision is to reset (fail toward a clean
/// week rather than honoring a corrupt anchor).
pub fn reset_decision(stored_anchor: &str, now_utc: DateTime<Utc>, tz_name: &str) -> ResetDecision {
    let tz = parse_tz(tz_name);
    let current_monday = most_recent_monday_midnight(now_utc, tz_name);
    let new_anchor = current_monday
        .with_timezone(&tz)
        .date_naive()
        .format("%Y-%m-%d")
        .to_string();

    let stored_instant = NaiveDate::parse_from_str(stored_anchor, "%Y-%m-%d")
        .ok()
        .map(|d| resolve_local_midnight(d, tz));

    let should_reset = match stored_instant {
        Some(stored) => stored < current_monday,
        None => true, // unparseable stored anchor -> reset to a clean current week
    };

    ResetDecision {
        should_reset,
        new_anchor,
    }
}

/// Parse an IANA tz name, defaulting to UTC (never panics on bad config).
fn parse_tz(tz_name: &str) -> Tz {
    tz_name.parse().unwrap_or(chrono_tz::UTC)
}
