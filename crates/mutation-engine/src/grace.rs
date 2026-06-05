//! RULE-05: once-per-true-day 8-minute NTP-boxed grace grant.
//!
//! `use_grace` grants a single 8-minute bypass window per *true* day, recorded in the
//! signed `guard.json.grace`. The whole grant runs inside the SAME single-writer lock as
//! `commit_change` ([`crate::commit::with_commit_lock`]) so it cannot race a commit.
//!
//! Two refusals, both fail-closed:
//!   - **NTP unreachable** -> [`MutationError::NtpUnreachable`]. True time is sourced ONLY
//!     from the injected [`TrueTime`]; the system/local clock is NEVER a fallback.
//!   - **Already used today** -> [`MutationError::GraceAlreadyUsedToday`], leaving
//!     `guard.json` byte-unchanged.
//!
//! Pitfall 4 (threat T-02-12): the "today" used for the once-per-day check is derived from
//! the NTP true-now instant converted into the configured IANA timezone — NOT `Local::now()`
//! — so a clock change cannot smuggle a second grant into one true day. Grace costs no
//! weekly token (design-spec): `weekly_spent` is untouched.

use chrono::{DateTime, Utc};
use chrono_tz::Tz;

use trust_kernel::atomic_write;

use crate::commit::{with_commit_lock, CommitPaths};
use crate::ntp::TrueTime;
use crate::state::{GraceWindow, MutationError};

/// The grace window length in seconds (8 minutes — design-spec "+8").
const GRACE_SECS: i64 = 8 * 60;

/// Grant a once-per-true-day 8-minute grace window, under the commit lock.
///
/// The authoritative [`GuardState`](crate::state::GuardState) is re-read from `guard.json`
/// INSIDE the lock (CR-02): a
/// caller-supplied snapshot could be stale relative to a concurrent grant, so the
/// already-used-today check must run against the fresh on-disk state the OS lock protects.
///
/// Steps (all inside [`with_commit_lock`]):
///   1. Re-read the authoritative `guard.json` state (fresh; guaranteed by the lock).
///   2. `true_time.now()`; any [`crate::ntp::NtpUnreachable`] -> refuse (never the app clock).
///   3. Derive `true_today` = the true-now instant's date in the configured `tz_name` tz.
///   4. If `state.grace.date == true_today` -> refuse `GraceAlreadyUsedToday` (file unchanged).
///   5. Else write `grace{date, window_start=now, window_end=now+8min}` onto a clone of the
///      state WITHOUT touching `weekly_spent`, re-sign `state_hmac` (A3), atomic_write
///      `guard.json`, and return the window.
pub fn use_grace(
    paths: &CommitPaths,
    true_time: &dyn TrueTime,
    tz_name: &str,
    key: &[u8; 32],
) -> Result<GraceWindow, MutationError> {
    with_commit_lock(&paths.lock_dir, || {
        // (1) Authoritative state, re-read inside the lock — never a stale caller snapshot.
        let state = crate::commit::read_state(&paths.guard_json)?;

        // (2) True time only — refuse on any NTP failure (fail-closed, no clock fallback).
        let now = true_time.now()?; // NtpUnreachable -> MutationError::NtpUnreachable via From
        let now_secs = now.unix_secs;

        // (3) "today" in the configured tz, derived from the NTP instant (Pitfall 4).
        let true_today = true_day(now_secs, tz_name);

        // (4) Already used this true-day? Refuse, leaving guard.json untouched.
        if let Some(existing) = &state.grace {
            if existing.date == true_today {
                return Err(MutationError::GraceAlreadyUsedToday);
            }
        }

        // (5) Build the window, set it WITHOUT changing weekly_spent, re-sign, write.
        let window = GraceWindow {
            date: true_today,
            window_start: now_secs,
            window_end: now_secs + GRACE_SECS,
        };
        let mut next = state.clone();
        next.grace = Some(window.clone());
        next.state_hmac = String::new();
        next.state_hmac = next.compute_state_hmac(key);

        let serialized = serde_json::to_vec_pretty(&next)?;
        atomic_write(&paths.guard_json, &serialized)?;

        Ok(window)
    })
}

/// Derive the local "YYYY-MM-DD" date of `unix_secs` in the configured tz.
///
/// Falls back to UTC if `tz_name` is not a valid IANA name (defensive — never panics on
/// bad config; mirrors `week::parse_tz`).
fn true_day(unix_secs: i64, tz_name: &str) -> String {
    let tz: Tz = tz_name.parse().unwrap_or(chrono_tz::UTC);
    let instant: DateTime<Utc> = DateTime::<Utc>::from_timestamp(unix_secs, 0)
        .unwrap_or_else(|| DateTime::<Utc>::from_timestamp(0, 0).expect("epoch is valid"));
    instant.with_timezone(&tz).date_naive().format("%Y-%m-%d").to_string()
}
