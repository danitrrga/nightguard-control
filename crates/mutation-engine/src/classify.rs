//! RULE-01: per-field tighten / loosen / noop direction classifier.
//!
//! Compares a proposed config (`new`) against the current one (`old`) **per field** and
//! labels each diff `Tighten`, `Loosen`, or `Noop` exactly per the authoritative spec
//! field table (design-spec.md "Direction classifier"):
//!
//! | Field | Loosen = | Tighten = |
//! |---|---|---|
//! | `curfew.enabled` | true→false | false→true |
//! | `curfew.start` | later | earlier |
//! | `curfew.end` | earlier | later |
//! | `curfew.allow_commands` | add entry | remove entry |
//! | `curfew.block_when_offline` | true→false | false→true |
//! | `curfew.schedule.<day>` | set `off`, later start, earlier end | stricter / removed |
//! | `clock_protection.enabled` | true→false | false→true |
//! | `clock_protection.max_offset_minutes` | increase | decrease |
//! | `watchdog.enabled` | true→false | false→true |
//! | `watchdog.check_interval_seconds` | increase | decrease |
//! | `watchdog.apps` | remove app | add app |
//! | `timezone` | any change (potential bypass) | — |
//!
//! **Commit rule:** one edit session = at most one token. If ANY field loosens the commit
//! is a loosening commit (costs 1 token, requires `weekly_spent < 3`). All tighten/neutral
//! is free; an all-`Noop` diff writes nothing.
//!
//! This module is 100% pure — no file I/O, no lock — mirroring trust-kernel's `canon.rs`
//! so the whole table runs as offline unit tests. Reads use `yamlpath` (format-preserving,
//! RESEARCH Pattern 5). A field missing on either side is `Noop` (defensive A2, threat
//! T-02-05: never a silent loosen), and `is_loosening_commit` is fail-safe — true iff any
//! field loosens, so an unclassifiable edit errs toward charging a token.

use yamlpath::{Document, QueryError, Route};

use crate::state::MutationError;

/// The classification of a single field diff between old and new config.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Direction {
    /// The change makes the guard stricter (or neutral toward strict).
    Tighten,
    /// The change relaxes the guard — costs a weekly token.
    Loosen,
    /// No change, or a field absent on either side (defensive A2).
    Noop,
}

/// How a given spec-table field's value maps to a direction.
enum FieldKind {
    /// Boolean where `true -> false` loosens (e.g. `enabled`).
    BoolTrueIsStrict,
    /// `HH:MM` time where a *later* value loosens (e.g. `curfew.start`).
    TimeLaterLoosens,
    /// `HH:MM` time where an *earlier* value loosens (e.g. `curfew.end`).
    TimeEarlierLoosens,
    /// Integer where an *increase* loosens (e.g. `max_offset_minutes`).
    NumberIncreaseLoosens,
    /// List where *adding* an entry loosens (e.g. `allow_commands`).
    ListAddLoosens,
    /// List where *removing* an entry loosens (e.g. `watchdog.apps`).
    ListRemoveLoosens,
    /// A `schedule.<day>` window string (`off` or `HH:MM-HH:MM`).
    Schedule,
    /// Any change loosens (e.g. `timezone`).
    AnyChangeLoosens,
}

/// One spec-table row: a label, the YAML key path into the document, and its kind.
struct FieldSpec {
    /// Stable label returned in the result (e.g. `"curfew.start"`).
    label: &'static str,
    /// The yamlpath key components into the config document.
    keys: &'static [&'static str],
    kind: FieldKind,
}

/// The seven schedule weekdays, classified individually as `curfew.schedule.<day>`.
const WEEKDAYS: [&str; 7] = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
];

/// The non-schedule spec-table rows (schedule days are appended dynamically).
const FIELD_TABLE: &[FieldSpec] = &[
    FieldSpec {
        label: "curfew.enabled",
        keys: &["curfew", "enabled"],
        kind: FieldKind::BoolTrueIsStrict,
    },
    FieldSpec {
        label: "curfew.start",
        keys: &["curfew", "start"],
        kind: FieldKind::TimeLaterLoosens,
    },
    FieldSpec {
        label: "curfew.end",
        keys: &["curfew", "end"],
        kind: FieldKind::TimeEarlierLoosens,
    },
    FieldSpec {
        label: "curfew.allow_commands",
        keys: &["curfew", "allow_commands"],
        kind: FieldKind::ListAddLoosens,
    },
    FieldSpec {
        label: "curfew.block_when_offline",
        keys: &["curfew", "block_when_offline"],
        kind: FieldKind::BoolTrueIsStrict,
    },
    FieldSpec {
        label: "clock_protection.enabled",
        keys: &["clock_protection", "enabled"],
        kind: FieldKind::BoolTrueIsStrict,
    },
    FieldSpec {
        label: "clock_protection.max_offset_minutes",
        keys: &["clock_protection", "max_offset_minutes"],
        kind: FieldKind::NumberIncreaseLoosens,
    },
    FieldSpec {
        label: "watchdog.enabled",
        keys: &["watchdog", "enabled"],
        kind: FieldKind::BoolTrueIsStrict,
    },
    FieldSpec {
        label: "watchdog.check_interval_seconds",
        keys: &["watchdog", "check_interval_seconds"],
        kind: FieldKind::NumberIncreaseLoosens,
    },
    FieldSpec {
        label: "watchdog.apps",
        keys: &["watchdog", "apps"],
        kind: FieldKind::ListRemoveLoosens,
    },
    FieldSpec {
        label: "timezone",
        keys: &["timezone"],
        kind: FieldKind::AnyChangeLoosens,
    },
];

/// Classify every spec-table field's diff between `old_yaml` and `new_yaml`.
///
/// Returns one `(label, Direction)` per spec-table row (the seven `curfew.schedule.<day>`
/// rows are included). A field present in neither / either document is `Noop` (defensive
/// A2, never a hidden loosen). Pure — no I/O.
pub fn classify_change(
    old_yaml: &str,
    new_yaml: &str,
) -> Result<Vec<(String, Direction)>, MutationError> {
    let old = Document::new(old_yaml.to_string()).map_err(yaml_err)?;
    let new = Document::new(new_yaml.to_string()).map_err(yaml_err)?;

    let mut out = Vec::with_capacity(FIELD_TABLE.len() + WEEKDAYS.len());

    for spec in FIELD_TABLE {
        let old_val = read_field(&old, spec.keys)?;
        let new_val = read_field(&new, spec.keys)?;
        out.push((spec.label.to_string(), classify_field(&spec.kind, old_val, new_val)));
    }

    for day in WEEKDAYS {
        let keys = ["curfew", "schedule", day];
        let old_val = read_field(&old, &keys)?;
        let new_val = read_field(&new, &keys)?;
        out.push((
            format!("curfew.schedule.{day}"),
            classify_field(&FieldKind::Schedule, old_val, new_val),
        ));
    }

    Ok(out)
}

/// True iff ANY entry is `Loosen` — the commit-level rule (RULE-01 commit rule).
///
/// Fail-safe: a loosening commit costs a token, so erring toward `true` is the safe
/// direction. All-tighten / all-noop returns `false` (free / no-op).
pub fn is_loosening_commit(dirs: &[(String, Direction)]) -> bool {
    dirs.iter().any(|(_, d)| *d == Direction::Loosen)
}

/// Read one field's normalized scalar text, or `None` if absent on this side.
///
/// A missing final key (`query_exact` -> `Ok(None)`) and any *structural absence* on the
/// path — a missing intermediate key (`ExhaustedMapping`) or a parent that isn't a mapping
/// /list (`ExpectedMapping`/`ExpectedList`/`ExhaustedList`) — are all treated as the field
/// being absent (defensive A2, threat T-02-05: an absent field is `Noop`, never a silent
/// loosen, and never a panic). Only genuinely malformed YAML folds into `Serde`.
fn read_field(doc: &Document, keys: &[&str]) -> Result<Option<String>, MutationError> {
    let route = Route::default().with_keys(keys.iter().map(|k| (*k).into()));
    match doc.query_exact(&route) {
        Ok(Some(feat)) => Ok(Some(normalize(doc.extract(&feat)))),
        Ok(None) => Ok(None),
        // The path simply doesn't exist in this document -> field absent (A2).
        Err(
            QueryError::ExhaustedMapping(_)
            | QueryError::ExpectedMapping(_)
            | QueryError::ExhaustedList(_, _)
            | QueryError::ExpectedList(_),
        ) => Ok(None),
        // Anything else (malformed YAML / grammar failure) is a real error.
        Err(e) => Err(yaml_err(e)),
    }
}

/// Normalize a raw extracted scalar: trim whitespace and surrounding quotes.
fn normalize(raw: &str) -> String {
    let t = raw.trim();
    let t = t
        .strip_prefix('"')
        .and_then(|s| s.strip_suffix('"'))
        .or_else(|| t.strip_prefix('\'').and_then(|s| s.strip_suffix('\'')))
        .unwrap_or(t);
    t.trim().to_string()
}

/// Classify a single field given its kind and old/new values.
///
/// A `None` on either side (field absent) is `Noop` per A2. Identical values are `Noop`.
fn classify_field(kind: &FieldKind, old: Option<String>, new: Option<String>) -> Direction {
    let (old, new) = match (old, new) {
        (Some(o), Some(n)) => (o, n),
        // Missing on either side -> defensively Noop, never a silent loosen.
        _ => return Direction::Noop,
    };
    if old == new {
        return Direction::Noop;
    }

    match kind {
        FieldKind::BoolTrueIsStrict => match (parse_bool(&old), parse_bool(&new)) {
            (Some(true), Some(false)) => Direction::Loosen,
            (Some(false), Some(true)) => Direction::Tighten,
            _ => Direction::Noop,
        },
        FieldKind::TimeLaterLoosens => compare_times(&old, &new, true),
        FieldKind::TimeEarlierLoosens => compare_times(&old, &new, false),
        FieldKind::NumberIncreaseLoosens => match (parse_int(&old), parse_int(&new)) {
            (Some(o), Some(n)) if n > o => Direction::Loosen,
            (Some(o), Some(n)) if n < o => Direction::Tighten,
            _ => Direction::Noop,
        },
        FieldKind::ListAddLoosens => compare_lists(&old, &new, true),
        FieldKind::ListRemoveLoosens => compare_lists(&old, &new, false),
        FieldKind::Schedule => classify_schedule(&old, &new),
        FieldKind::AnyChangeLoosens => Direction::Loosen, // values already differ
    }
}

/// Parse a YAML boolean literal.
fn parse_bool(s: &str) -> Option<bool> {
    match s {
        "true" | "True" | "TRUE" => Some(true),
        "false" | "False" | "FALSE" => Some(false),
        _ => None,
    }
}

/// Parse a plain integer.
fn parse_int(s: &str) -> Option<i64> {
    s.parse::<i64>().ok()
}

/// Parse `HH:MM` into minutes-since-midnight.
///
/// `pub(crate)` so [`crate::lock_status`] reuses the EXACT same bounds-checked parser —
/// there is intentionally ONE `HH:MM` parser in the engine, never a divergent second copy.
pub(crate) fn parse_hhmm(s: &str) -> Option<i64> {
    let (h, m) = s.split_once(':')?;
    let h: i64 = h.trim().parse().ok()?;
    let m: i64 = m.trim().parse().ok()?;
    if (0..24).contains(&h) && (0..60).contains(&m) {
        Some(h * 60 + m)
    } else {
        None
    }
}

/// Compare two `HH:MM` times. `later_loosens` selects the direction polarity.
fn compare_times(old: &str, new: &str, later_loosens: bool) -> Direction {
    match (parse_hhmm(old), parse_hhmm(new)) {
        (Some(o), Some(n)) => {
            let later = n > o;
            if (later && later_loosens) || (!later && !later_loosens) {
                Direction::Loosen
            } else {
                Direction::Tighten
            }
        }
        _ => Direction::Noop,
    }
}

/// Parse a flow/inline YAML list (`[a, b]`) into its entries.
fn parse_list(s: &str) -> Vec<String> {
    let inner = s.trim().trim_start_matches('[').trim_end_matches(']');
    inner
        .split(',')
        .map(|e| normalize(e))
        .filter(|e| !e.is_empty())
        .collect()
}

/// Compare two lists. `add_loosens` selects polarity: an added entry loosens (commands)
/// or a removed entry loosens (watchdog apps).
fn compare_lists(old: &str, new: &str, add_loosens: bool) -> Direction {
    let old_set: Vec<String> = parse_list(old);
    let new_set: Vec<String> = parse_list(new);
    let added = new_set.iter().any(|e| !old_set.contains(e));
    let removed = old_set.iter().any(|e| !new_set.contains(e));

    if add_loosens {
        if added {
            Direction::Loosen
        } else if removed {
            Direction::Tighten
        } else {
            Direction::Noop
        }
    } else if removed {
        Direction::Loosen
    } else if added {
        Direction::Tighten
    } else {
        Direction::Noop
    }
}

/// Classify a `schedule.<day>` window: `off` / later start / earlier end loosens;
/// a stricter (later start removal / narrower) window tightens.
fn classify_schedule(old: &str, new: &str) -> Direction {
    let old_off = old.eq_ignore_ascii_case("off");
    let new_off = new.eq_ignore_ascii_case("off");
    match (old_off, new_off) {
        (false, true) => return Direction::Loosen, // turning a guarded day off loosens
        (true, false) => return Direction::Tighten, // guarding a previously-off day tightens
        (true, true) => return Direction::Noop,
        (false, false) => {}
    }

    // Both are "HH:MM-HH:MM" windows. Later start OR earlier end loosens.
    let (os, oe) = match parse_window(old) {
        Some(w) => w,
        None => return Direction::Noop,
    };
    let (ns, ne) = match parse_window(new) {
        Some(w) => w,
        None => return Direction::Noop,
    };
    if ns > os || ne < oe {
        Direction::Loosen
    } else if ns < os || ne > oe {
        Direction::Tighten
    } else {
        Direction::Noop
    }
}

/// Parse a `HH:MM-HH:MM` window into (start_minutes, end_minutes).
///
/// `pub(crate)` so [`crate::lock_status`] shares this exact window parser (single source).
pub(crate) fn parse_window(s: &str) -> Option<(i64, i64)> {
    let (start, end) = s.split_once('-')?;
    Some((parse_hhmm(start.trim())?, parse_hhmm(end.trim())?))
}

/// Fold a yamlpath query error into the crate error surface.
fn yaml_err(e: impl std::fmt::Display) -> MutationError {
    MutationError::Serde(format!("yaml classify error: {e}"))
}
