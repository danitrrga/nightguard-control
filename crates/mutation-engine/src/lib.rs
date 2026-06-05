//! mutation-engine: the authoritative edit-intent + sanctioned-commit logic of
//! Nightguard Control.
//!
//! This is a plain Rust library crate (NOT a Tauri app — Tauri arrives in Phase 4).
//! It builds ON the Phase 1 [`trust_kernel`] primitives (`canonicalize_bytes`,
//! `atomic_write`, `write_canonical_text`, `hmac::{sign_bytes, verify_bytes,
//! tag_to_hex}`, `key::load_or_create_key`) and adds the edit-intent state machine:
//!
//! - [`state`]: the `guard.json` signed-state serde model — the Phase 3 interop
//!   contract — plus [`MutationError`] and the locked `state_hmac` derivation recipe.
//! - [`sign`]: thin canonical-bytes signing helpers over [`trust_kernel::hmac`], so the
//!   bytes that land on disk are exactly the bytes that get signed (sign-the-canonical-
//!   bytes invariant).
//! - [`classify`] / [`quota`] / [`week`] / [`ntp`] / [`grace`] / [`commit`]: the
//!   per-field direction classifier, weekly token quota, DST-aware Monday reset,
//!   NTP true-time grace, and ordered atomic locked commit (filled by later plans).

pub mod classify;
pub mod commit;
pub mod grace;
pub mod ntp;
pub mod quota;
pub mod sign;
pub mod state;
pub mod week;

pub use state::{GraceWindow, GuardState, LedgerEntry, MutationError};
