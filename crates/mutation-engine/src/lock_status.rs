//! The pure curfew-window evaluator (Open Q1 / Pitfall 1 — the highest-risk net-new logic
//! of Phase 4). Answers "are we locked **right now**?" and "when is the next state-change
//! boundary?" from `config.yaml`'s curfew fields against an *advisory* `now` (D-04). It is
//! the one piece no existing crate provides; `get_state` (plan 03) overlays grace on top.
//!
//! This module is 100% pure — no file I/O, no clock reads (`now` is passed in) — so the whole
//! window matrix runs offline as unit tests, mirroring `classify.rs` / `week.rs`. It reuses
//! `classify.rs`'s bounds-checked [`crate::classify::parse_hhmm`] / [`crate::classify::parse_window`]
//! (single parser, no divergent copy) and mirrors its defensive yamlpath read.
//!
//! # Precedence spec (resolves Open Q1 — the written rule the tests enforce)
//!
//! Evaluating "locked at `now`" for a given config + advisory instant:
//!
//! 1. **`curfew.enabled` gate.** If `curfew.enabled` reads `false`, the curfew is OFF: the
//!    result is `locked = false`, `boundary_kind = "next_lock"`. An *absent* or *malformed*
//!    `enabled` does NOT count as `false` — it falls through to the fail-safe rule (4).
//! 2. **Effective window per day.** Convert `now` into the configured `timezone` (defaulting
//!    to UTC on a bad/absent tz, never panicking — mirrors `week::parse_tz`), then derive the
//!    local weekday + minute-of-day. The day's effective window is resolved by precedence:
//!      - if `curfew.schedule.<weekday>` is **present**, it OVERRIDES `curfew.start`/`curfew.end`:
//!          - value `off` (case-insensitive) => no curfew that day => `locked = false`,
//!            `boundary_kind = "next_lock"`.
//!          - value `HH:MM-HH:MM` => that window applies for the day (overnight-wrap allowed).
//!      - if `schedule.<weekday>` is **absent**, fall back to `curfew.start`-`curfew.end`.
//! 3. **Inside-window verdict (overnight-wrap aware).** A window `start..end` where
//!    `end <= start` *wraps past midnight* (e.g. `23:00-07:00`): "inside" is
//!    `minute >= start OR minute < end`. A non-wrapping window is `start <= minute < end`.
//!    - **locked** => `boundary_kind = "curfew_end"`, `boundary_unix` = the window-end instant
//!      on the CORRECT calendar day (for a wrap entered late, that is the NEXT day — derived
//!      from the wrapped end, never a naive `+24h`; mirrors `week.rs`'s explicit instant math).
//!    - **open** => `boundary_kind = "next_lock"`, `boundary_unix` = the next window-start instant
//!      (today if still upcoming, else tomorrow's — computed only from the start/end fields here;
//!      a full multi-day schedule scan is out of scope for the advisory display, D-04).
//! 4. **Fail-safe rule (D-04 / T-04-05 / T-04-06 / A2).** A missing `curfew` block, a missing
//!    `start`/`end` when no `schedule.<day>` applies, or a malformed `HH:MM`/window string is
//!    NEVER a silent unlock. The result is **fail-safe LOCKED** (`locked = true`,
//!    `boundary_kind = "curfew_end"`, `boundary_unix = now`) — the UI degrades to "locked /
//!    time unverified" rather than asserting OPEN. Absent != loosen, exactly as `classify.rs`.
//!
//! `grace_active` is always `false` here; the live grace window lives in the signed
//! `guard.json` that `get_state` reads, so the command overlays it (the simpler seam — this
//! pure fn never touches state). `boundary_kind` is one of `"curfew_end" | "next_lock"`
//! (`"grace_end"` is set by `get_state` when it overlays grace).

use chrono::{DateTime, Datelike, Duration, NaiveDate, NaiveTime, TimeZone, Timelike, Utc};
use chrono_tz::Tz;
use yamlpath::{Document, QueryError, Route};

use crate::classify::{parse_hhmm, parse_window};

/// The advisory lock verdict for a single instant against a config's curfew fields.
///
/// Timestamps are unix-secs `i64` to match `GraceWindow.window_end` / `LedgerEntry` (the UI
/// formats). `grace_active` is left `false` by this pure fn; `get_state` overlays the signed
/// grace window from `guard.json`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LockStatus {
    /// True iff `now` is inside the effective curfew window (fail-safe LOCKED on any doubt).
    pub locked: bool,
    /// Always `false` here — `get_state` overlays the signed grace window from `guard.json`.
    pub grace_active: bool,
    /// The next state-change instant, unix seconds (window end if locked, next start if open).
    pub boundary_unix: i64,
    /// One of `"curfew_end" | "next_lock"` (`"grace_end"` is set later by `get_state`).
    pub boundary_kind: String,
}

impl LockStatus {
    /// Fail-safe LOCKED: a missing/malformed field is never a silent unlock (D-04 / A2).
    /// Boundary is `now` (advisory; the UI shows "locked / time unverified").
    fn fail_safe_locked(now: DateTime<Utc>) -> Self {
        LockStatus {
            locked: true,
            grace_active: false,
            boundary_unix: now.timestamp(),
            boundary_kind: "curfew_end".to_string(),
        }
    }

    /// OPEN with the next lock boundary (used for enabled=false and off-days).
    fn open(boundary_unix: i64) -> Self {
        LockStatus {
            locked: false,
            grace_active: false,
            boundary_unix,
            boundary_kind: "next_lock".to_string(),
        }
    }
}

/// Evaluate the curfew lock status for `now` against `config_yaml`. Pure — no I/O, no clock.
///
/// Follows the module's precedence spec. Any parse/absent failure degrades to
/// [`LockStatus::fail_safe_locked`] — never a silent unlock (D-04).
pub fn lock_status(config_yaml: &str, now: DateTime<Utc>) -> LockStatus {
    // Malformed YAML -> fail-safe LOCKED (never panic, never unlock).
    let doc = match Document::new(config_yaml.to_string()) {
        Ok(d) => d,
        Err(_) => return LockStatus::fail_safe_locked(now),
    };

    // tz: defensive default to UTC on bad/absent name (mirrors week::parse_tz; T-04-07).
    let tz = parse_tz(read(&doc, &["timezone"]).flatten().as_deref().unwrap_or("UTC"));
    let local = now.with_timezone(&tz);
    let minute = local.hour() as i64 * 60 + local.minute() as i64;
    let local_date = local.date_naive();
    let weekday = local.weekday();

    // (1) enabled gate: only an explicit `false` disables; absent/garbage falls through to fail-safe.
    match read(&doc, &["curfew", "enabled"]).flatten().as_deref() {
        Some("false") | Some("False") | Some("FALSE") => {
            // Curfew off: OPEN, boundary is the next start if start/end resolve, else just now.
            let start = effective_start_minute(&doc, weekday);
            let b = match start {
                Some(s) => next_start_unix(local_date, minute, s, tz),
                None => now.timestamp(),
            };
            return LockStatus::open(b);
        }
        Some("true") | Some("True") | Some("TRUE") => {}
        // Absent or malformed enabled -> fail-safe LOCKED (A2: absent != unlock).
        _ => return LockStatus::fail_safe_locked(now),
    }

    // (2) Resolve the effective window for today, with schedule.<day> precedence.
    let weekday_key = weekday_key(weekday);
    let schedule_val = read(&doc, &["curfew", "schedule", weekday_key]).flatten();

    let (start_min, end_min) = match schedule_val {
        Some(v) if v.eq_ignore_ascii_case("off") => {
            // schedule.<day> = off OVERRIDES start/end -> unlocked this day.
            let start = effective_start_minute(&doc, weekday); // only for an advisory next_lock
            let b = match start {
                Some(s) => next_start_unix(local_date, minute, s, tz),
                None => now.timestamp(),
            };
            return LockStatus::open(b);
        }
        Some(v) => match parse_window(&v) {
            Some(w) => w,
            // Malformed schedule window -> fail-safe LOCKED.
            None => return LockStatus::fail_safe_locked(now),
        },
        None => {
            // Fall back to curfew.start / curfew.end.
            let start = read(&doc, &["curfew", "start"]).flatten();
            let end = read(&doc, &["curfew", "end"]).flatten();
            match (start.as_deref().and_then(parse_hhmm), end.as_deref().and_then(parse_hhmm)) {
                (Some(s), Some(e)) => (s, e),
                // Missing/malformed start or end -> fail-safe LOCKED.
                _ => return LockStatus::fail_safe_locked(now),
            }
        }
    };

    // (3) Inside-window verdict + boundary, overnight-wrap aware.
    let wraps = end_min <= start_min;
    let inside = if wraps {
        minute >= start_min || minute < end_min
    } else {
        minute >= start_min && minute < end_min
    };

    if inside {
        // LOCKED -> boundary is the window END on the correct calendar day.
        let end_date = if wraps && minute >= start_min {
            // Entered the wrap in the late part (>= start): end is TOMORROW (never naive +24h).
            local_date + Duration::days(1)
        } else {
            // Non-wrap, or the early-morning part of a wrap (minute < end): end is TODAY.
            local_date
        };
        let boundary = local_minute_unix(end_date, end_min, tz);
        LockStatus {
            locked: true,
            grace_active: false,
            boundary_unix: boundary,
            boundary_kind: "curfew_end".to_string(),
        }
    } else {
        // OPEN -> boundary is the next window START (today if upcoming, else tomorrow).
        LockStatus::open(next_start_unix(local_date, minute, start_min, tz))
    }
}

/// The next window-START instant: today's `start_min` if still upcoming, else tomorrow's.
fn next_start_unix(local_date: NaiveDate, minute: i64, start_min: i64, tz: Tz) -> i64 {
    let date = if minute < start_min {
        local_date
    } else {
        local_date + Duration::days(1)
    };
    local_minute_unix(date, start_min, tz)
}

/// Resolve `date` + `minute_of_day` (local, in `tz`) to a unix-secs instant, DST-aware.
///
/// Mirrors `week.rs`'s explicit `MappedLocalTime` discipline: `Single` normal, `Ambiguous`
/// -> earliest (deterministic), `None` (spring-forward gap) -> step the hour forward an hour.
fn local_minute_unix(date: NaiveDate, minute_of_day: i64, tz: Tz) -> i64 {
    let h = (minute_of_day / 60) as u32;
    let m = (minute_of_day % 60) as u32;
    let naive = date.and_time(NaiveTime::from_hms_opt(h, m, 0).unwrap_or_else(|| {
        NaiveTime::from_hms_opt(0, 0, 0).expect("midnight is valid")
    }));
    let local_dt = match tz.from_local_datetime(&naive) {
        chrono::MappedLocalTime::Single(dt) => dt,
        chrono::MappedLocalTime::Ambiguous(earliest, _latest) => earliest,
        // Spring-forward gap: shift forward one hour (that local time always exists).
        chrono::MappedLocalTime::None => tz
            .from_local_datetime(&(naive + Duration::hours(1)))
            .single()
            .unwrap_or_else(|| tz.from_utc_datetime(&naive)),
    };
    local_dt.with_timezone(&Utc).timestamp()
}

/// The `curfew.start` minute-of-day for an advisory `next_lock` boundary on an off/disabled day.
/// Prefers a present `schedule.<day>` window's start, else `curfew.start`; `None` if unresolvable.
fn effective_start_minute(doc: &Document, weekday: chrono::Weekday) -> Option<i64> {
    let key = weekday_key(weekday);
    if let Some(v) = read(doc, &["curfew", "schedule", key]).flatten() {
        if !v.eq_ignore_ascii_case("off") {
            if let Some((s, _e)) = parse_window(&v) {
                return Some(s);
            }
        }
    }
    read(doc, &["curfew", "start"]).flatten().as_deref().and_then(parse_hhmm)
}

/// Map a chrono weekday to the lowercase schedule key the config uses.
fn weekday_key(weekday: chrono::Weekday) -> &'static str {
    match weekday {
        chrono::Weekday::Mon => "monday",
        chrono::Weekday::Tue => "tuesday",
        chrono::Weekday::Wed => "wednesday",
        chrono::Weekday::Thu => "thursday",
        chrono::Weekday::Fri => "friday",
        chrono::Weekday::Sat => "saturday",
        chrono::Weekday::Sun => "sunday",
    }
}

/// Parse an IANA tz name, defaulting to UTC (never panics on bad config — mirrors week::parse_tz).
fn parse_tz(tz_name: &str) -> Tz {
    tz_name.parse().unwrap_or(chrono_tz::UTC)
}

/// Defensive yamlpath read mirroring `classify::read_field` (A2): a missing leaf
/// (`query_exact` -> `Ok(None)`) or any structural absence on the path is treated as the
/// field being absent (`Ok(None)`), never a panic. Malformed YAML returns `Err` -> the caller
/// folds it into fail-safe LOCKED. Returns `Result<Option<String>>` flattened by callers.
fn read(doc: &Document, keys: &[&str]) -> Option<Option<String>> {
    let route = Route::default().with_keys(keys.iter().map(|k| (*k).into()));
    match doc.query_exact(&route) {
        Ok(Some(feat)) => Some(Some(normalize(doc.extract(&feat)))),
        Ok(None) => Some(None),
        Err(
            QueryError::ExhaustedMapping(_)
            | QueryError::ExpectedMapping(_)
            | QueryError::ExhaustedList(_, _)
            | QueryError::ExpectedList(_),
        ) => Some(None),
        // Genuinely malformed YAML on this path: signal "could not read" -> caller fail-safes.
        Err(_) => None,
    }
}

/// Trim whitespace and surrounding quotes from a raw extracted scalar (mirrors classify::normalize).
fn normalize(raw: &str) -> String {
    let t = raw.trim();
    let t = t
        .strip_prefix('"')
        .and_then(|s| s.strip_suffix('"'))
        .or_else(|| t.strip_prefix('\'').and_then(|s| s.strip_suffix('\'')))
        .unwrap_or(t);
    t.trim().to_string()
}
