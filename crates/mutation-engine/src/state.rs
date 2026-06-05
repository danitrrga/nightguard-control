//! guard.json signed-state model + [`MutationError`] (RULE-06 interop contract).
//!
//! `guard.json` is the cross-language contract the Phase 3 PowerShell guard parses, so the
//! field names and types here are LOCKED (Assumption A1): `config_hmac`, `state_hmac`,
//! `weekly_spent`, `week_anchor`, `ledger[]`, `grace`. Treat any change as a breaking
//! interop change like the HMAC byte form.
//!
//! Locked `state_hmac` recipe (Assumption A3 / threat T-02-01) — the PS guard MUST
//! re-derive identically:
//!   1. Serialize the struct with `config_hmac` set and `state_hmac` BLANKED to `""`.
//!   2. Run the JSON string bytes through [`trust_kernel::canonicalize_bytes`].
//!   3. `sign_bytes` with the 32-byte key, then `tag_to_hex`.
//! This is the same "sign canonical raw bytes" invariant trust-kernel's `hmac` enforces:
//! the bytes signed are the canonical bytes, so cosmetic drift is absorbed and any logical
//! change is detectable.

use serde::{Deserialize, Serialize};

use trust_kernel::canon::canonicalize_bytes;
use trust_kernel::hmac::{sign_bytes, tag_to_hex};

/// The `guard.json` signed-state model — the Phase 3 interop contract.
///
/// `#[derive(Debug, PartialEq)]` is present so tests can assert exact round-trip equality.
#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
pub struct GuardState {
    /// hex(HMAC(canonical `config.yaml` bytes)).
    pub config_hmac: String,
    /// hex(HMAC(canonical bytes of this struct with `state_hmac` blanked)); see A3 recipe.
    pub state_hmac: String,
    /// Tokens spent this week, 0..=3.
    pub weekly_spent: u8,
    /// Monday ISO date "YYYY-MM-DD" in the configured tz (the week anchor).
    pub week_anchor: String,
    /// Loosening events (NTP timestamp + the fields that loosened).
    pub ledger: Vec<LedgerEntry>,
    /// An active once-per-true-day grace window, if any.
    pub grace: Option<GraceWindow>,
}

impl GuardState {
    /// Compute the `state_hmac` over this state per the locked A3 recipe.
    ///
    /// Clones the state, BLANKS `state_hmac` to `""` (so the field never signs itself and
    /// any prior value is irrelevant), serializes to JSON, canonicalizes those bytes, signs
    /// with `key`, and returns the lowercase hex tag. Deterministic and byte-reproducible:
    /// the same logical state always yields the same tag, regardless of the current
    /// `state_hmac` value — which is what makes the PS guard's re-derivation match.
    pub fn compute_state_hmac(&self, key: &[u8; 32]) -> String {
        let mut blanked = self.clone();
        blanked.state_hmac = String::new();
        let json = serde_json::to_string(&blanked)
            .expect("GuardState is always serializable to JSON");
        let canon = canonicalize_bytes(json.as_bytes());
        tag_to_hex(&sign_bytes(key, &canon))
    }
}

/// A loosening event recorded in the ledger.
#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
pub struct LedgerEntry {
    /// NTP true-time unix seconds at which the loosening commit happened.
    pub ntp_timestamp: i64,
    /// The fields that loosened in this commit.
    pub fields: Vec<String>,
}

/// An active once-per-true-day grace window.
#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
pub struct GraceWindow {
    /// True-day date "YYYY-MM-DD" (configured tz) this grace was granted.
    pub date: String,
    /// Window start, NTP true-time unix seconds.
    pub window_start: i64,
    /// Window end, NTP true-time unix seconds (start + 8 minutes).
    pub window_end: i64,
}

/// Unified error surface for the mutation engine.
///
/// Mirrors trust-kernel's per-crate `thiserror` enum + prefixed-message voice
/// ("store io error", "kernel io error"); folds `trust_kernel::StoreError` into [`Io`].
///
/// [`Io`]: MutationError::Io
#[derive(Debug, thiserror::Error)]
pub enum MutationError {
    /// File I/O / atomic-write failure.
    #[error("mutation io error: {0}")]
    Io(String),

    /// NTP true time could not be obtained — refuse anything time-gated (RULE-05).
    #[error("ntp unreachable: cannot verify true time")]
    NtpUnreachable,

    /// No weekly tokens left to spend on a loosening commit (RULE-04).
    #[error("weekly loosen quota exhausted")]
    QuotaExhausted,

    /// A grace window was already granted earlier today (true-day) (RULE-05).
    #[error("grace already used today")]
    GraceAlreadyUsedToday,

    /// (De)serialization of `guard.json` failed.
    #[error("mutation serde error: {0}")]
    Serde(String),
}

impl From<trust_kernel::StoreError> for MutationError {
    fn from(e: trust_kernel::StoreError) -> Self {
        MutationError::Io(e.to_string())
    }
}

impl From<serde_json::Error> for MutationError {
    fn from(e: serde_json::Error) -> Self {
        MutationError::Serde(e.to_string())
    }
}
