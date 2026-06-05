//! RULE-02/04: the commit-rule weekly token quota state machine.
//!
//! Locked rule (design-spec.md "Commit rule"): **one edit session = at most one token.**
//!
//! 1. All-`Noop` diff -> nothing is written (`is_noop`, free, allowed).
//! 2. No field loosens (all tighten/neutral) -> free, allowed, no token.
//! 3. Any field loosens AND effective `weekly_spent < 3` -> allowed, costs 1 token.
//! 4. Any field loosens AND effective `weekly_spent >= 3` -> blocked; the `reason` contains
//!    the locked substring `available again Monday` (RULE-04) and `next_reset` is the
//!    upcoming Monday 00:00 in the configured tz (DST-aware, via [`crate::week`]).
//!
//! The **effective** `weekly_spent` applies a lazy reset first: if the stored `week_anchor`
//! predates the current Monday, the spent count is treated as 0 (a fresh week), so a stale
//! `spent=3` never blocks a legitimate loosen in a new week.
//!
//! This module is 100% pure — no file I/O, no lock — so the whole quota matrix runs offline
//! (mirroring trust-kernel's `tests/hmac.rs`). The budget reset is computed deterministically
//! from the supplied instant + configured tz; per threat T-02-04 the AUTHORITATIVE clock for
//! the binding value (grace) is NTP (plan 02-04) — callers must source `now_utc` responsibly.

use chrono::{DateTime, Utc};

use crate::classify::{is_loosening_commit, Direction};
use crate::state::GuardState;
use crate::week::{next_monday_midnight, reset_decision};

/// The maximum loosening commits allowed per week.
const WEEKLY_TOKENS: u8 = 3;

/// The locked block-reason substring the UI surfaces (RULE-04). Must be present verbatim.
const RESET_HINT: &str = "available again Monday";

/// The decision for a proposed commit under the weekly quota.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct QuotaDecision {
    /// Whether the commit may proceed.
    pub allowed: bool,
    /// A human reason when blocked (contains `available again Monday`); `None` when allowed.
    pub reason: Option<String>,
    /// Whether the commit spends one weekly token (true only for an allowed loosening commit).
    pub costs_token: bool,
    /// Whether the diff is a no-op (nothing to write).
    pub is_noop: bool,
    /// The post-lazy-reset spent count this decision is based on (0 when the stored anchor
    /// predates the current week, else the stored `weekly_spent`). `build_new_state` MUST
    /// persist this (not the stale clone) so a reset is durably written (CR-01).
    pub effective_spent: u8,
    /// The CURRENT week's Monday ISO date "YYYY-MM-DD" (configured tz, DST-aware) to persist
    /// as `week_anchor`, so a stale anchor advances and the reset is not recomputed forever.
    pub week_anchor: String,
    /// The upcoming Monday 00:00 (configured tz, DST-aware) — always populated for the UI.
    pub next_reset: DateTime<Utc>,
}

/// Decide the quota outcome for a classified diff against the current state.
///
/// Pure: derives the effective `weekly_spent` via the lazy week reset, then applies the
/// commit rule. `now_utc`/`tz_name` feed the DST-aware Monday math (RULE-03).
pub fn decide(
    dirs: &[(String, Direction)],
    state: &GuardState,
    now_utc: DateTime<Utc>,
    tz_name: &str,
) -> QuotaDecision {
    // next_reset is the upcoming Monday regardless of outcome (for the UI).
    let next_reset = next_monday_midnight(now_utc, tz_name);

    // (1) Lazy reset: if the stored anchor predates the current Monday, the week is fresh.
    // `reset.new_anchor` is the CURRENT week's Monday ISO date — the value to persist so the
    // anchor advances and the reset is not recomputed on every subsequent commit (CR-01).
    let reset = reset_decision(&state.week_anchor, now_utc, tz_name);
    let effective_spent = if reset.should_reset { 0 } else { state.weekly_spent };
    let week_anchor = reset.new_anchor;

    // (2) All-noop -> nothing to write.
    let all_noop = dirs.iter().all(|(_, d)| *d == Direction::Noop);
    if all_noop {
        return QuotaDecision {
            allowed: true,
            reason: None,
            costs_token: false,
            is_noop: true,
            effective_spent,
            week_anchor,
            next_reset,
        };
    }

    // (3) No loosen -> free commit.
    if !is_loosening_commit(dirs) {
        return QuotaDecision {
            allowed: true,
            reason: None,
            costs_token: false,
            is_noop: false,
            effective_spent,
            week_anchor,
            next_reset,
        };
    }

    // (4) Loosening commit -> requires a remaining token.
    if effective_spent < WEEKLY_TOKENS {
        QuotaDecision {
            allowed: true,
            reason: None,
            costs_token: true,
            is_noop: false,
            effective_spent,
            week_anchor,
            next_reset,
        }
    } else {
        QuotaDecision {
            allowed: false,
            reason: Some(format!(
                "weekly loosen quota exhausted ({WEEKLY_TOKENS}/{WEEKLY_TOKENS} used); \
                 {RESET_HINT} when the budget resets"
            )),
            costs_token: false,
            is_noop: false,
            effective_spent,
            week_anchor,
            next_reset,
        }
    }
}
