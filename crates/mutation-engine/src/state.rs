//! guard.json signed-state model + MutationError (filled in Task 2).
//!
//! Placeholder symbols so the crate compiles after Task 1; Task 2 implements the full
//! serde model, MutationError surface, and the locked state_hmac recipe (A3).

use serde::{Deserialize, Serialize};

/// guard.json signed-state model (interop contract — filled in Task 2).
#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
pub struct GuardState {
    pub config_hmac: String,
    pub state_hmac: String,
    pub weekly_spent: u8,
    pub week_anchor: String,
    pub ledger: Vec<LedgerEntry>,
    pub grace: Option<GraceWindow>,
}

/// A loosening event recorded in the ledger.
#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
pub struct LedgerEntry {
    pub ntp_timestamp: i64,
    pub fields: Vec<String>,
}

/// An active once-per-true-day grace window.
#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
pub struct GraceWindow {
    pub date: String,
    pub window_start: i64,
    pub window_end: i64,
}

/// Engine error surface (filled in Task 2).
#[derive(Debug, thiserror::Error)]
pub enum MutationError {
    #[error("mutation io error: {0}")]
    Io(String),
}
