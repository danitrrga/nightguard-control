//! trust-kernel: the deterministic-writer foundation of Nightguard Control.
//!
//! This is a plain Rust library crate (NOT a Tauri app — Tauri arrives in Phase 4).
//! It exposes the two primitives every later crypto guarantee rests on:
//!
//! - [`canon::canonicalize_bytes`]: normalize arbitrary input into the one canonical
//!   byte form the whole project signs over (UTF-8, no BOM, LF-only, exactly one
//!   trailing newline).
//! - [`store::atomic_write`] / [`store::write_canonical_text`]: crash-safe writes
//!   (temp file in the same dir, then atomic rename) that never corrupt the prior file.

pub mod canon;
#[cfg(windows)]
pub mod dpapi;
pub mod hmac;
pub mod key;
pub mod store;

pub use canon::canonicalize_bytes;
pub use store::{atomic_write, write_canonical_text, StoreError};
