//! NTP true-time tests (RED-first, per the TDD directive).
//!
//! Proves the RULE-05 true-time half: callers depend on the [`TrueTime`] trait so the
//! live UDP path is fully abstracted away (offline-testable with an injected fake), and
//! any failure to obtain true time surfaces as a typed [`NtpUnreachable`] refusal — the
//! app/system clock is NEVER used as a fallback (threat T-02-08, fail-closed).
//!
//! The two fake-based tests always run (no network). The single live test against a real
//! public NTP host is `#[ignore]` so CI/offline runs skip it (threat T-02-08: unreachable
//! is itself a tested refusal path, so the live path needs no always-on coverage).

use mutation_engine::ntp::{FakeTrueTime, NtpTrueTime, NtpUnreachable, SntpTrueTime, TrueTime};

/// A caller that depends only on the `TrueTime` trait. Stands in for plan 02-04's grace
/// logic: it must be drivable entirely offline by an injected fake (no real UDP).
fn true_day_unix<T: TrueTime>(clock: &T) -> Result<i64, NtpUnreachable> {
    clock.now().map(|t| t.unix_secs)
}

#[test]
fn fake_true_time_is_consumed_without_network() {
    // A fake returning a fixed instant proves the trait abstracts UDP entirely.
    let fixed = NtpTrueTime { unix_secs: 1_777_000_000, frac: 0, offset: 0 };
    let clock = FakeTrueTime::ok(fixed);

    let got = true_day_unix(&clock).expect("fake clock yields a fixed instant offline");
    assert_eq!(got, 1_777_000_000);
}

#[test]
fn fake_unreachable_propagates_as_refusal() {
    // The error path grace will use: NtpUnreachable propagates, never a clock fallback.
    let clock = FakeTrueTime::unreachable();

    let result = true_day_unix(&clock);
    assert!(
        matches!(result, Err(NtpUnreachable)),
        "an unreachable true-time source must refuse, never return a fallback time"
    );
}

/// Live integration test against a real public NTP host. `#[ignore]` so offline/CI runs
/// skip it; run explicitly with `cargo test -p mutation-engine --test ntp -- --ignored`.
#[test]
#[ignore = "requires outbound UDP 123 to a public NTP host"]
fn live_sntp_returns_plausible_unix_time() {
    let clock = SntpTrueTime::default();
    let t = clock.now().expect("a public NTP host should answer when online");
    // Lower bound: 2025-01-01T00:00:00Z = 1_735_689_600. True time must be after it.
    assert!(
        t.unix_secs > 1_735_689_600,
        "true unix time {} should be after the 2025 epoch lower bound",
        t.unix_secs
    );
}
