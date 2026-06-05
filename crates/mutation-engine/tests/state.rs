//! guard.json serde model + state_hmac recipe + sign-the-canonical-bytes tests
//! (RED-first, per the TDD directive).
//!
//! Proves four contracts that downstream plans and the Phase 3 PowerShell guard depend on:
//!   1. The `GuardState` serde model round-trips (the Phase 3 interop contract; RULE-06).
//!   2. The locked `state_hmac` recipe (Assumption A3) is byte-reproducible: computing the
//!      tag twice over the same logical state yields the identical hex, and recomputing
//!      after blanking + refilling `state_hmac` matches (threat T-02-01).
//!   3. `config_hmac` (sign over `canonicalize_bytes` of a config string) equals the HMAC
//!      of the exact bytes `write_canonical_text` lands on disk — the sign-the-canonical-
//!      bytes invariant (Pitfall 3 / threat T-02-02; mirrors trust-kernel's cosmetic-EOL
//!      hmac test).
//!   4. A raw-CRLF config string and its LF equivalent produce the SAME `config_hmac`
//!      after canonicalization (cosmetic EOL absorbed), proving parity with the writer.

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

use mutation_engine::sign::sign_config;
use mutation_engine::state::GuardState;
use mutation_engine::{GraceWindow, LedgerEntry};

use trust_kernel::canon::canonicalize_bytes;
use trust_kernel::hmac::{sign_bytes, tag_to_hex};
use trust_kernel::store::write_canonical_text;

/// A fixed 32-byte test key (32 x 0x2a). Arbitrary; the contracts are about byte parity,
/// not a specific published vector.
const TEST_KEY: [u8; 32] = [0x2a; 32];

/// Collision-free scratch dir inside the crate's target/ (same-volume atomic rename),
/// following trust-kernel/tests/store.rs (NOT std::env::temp_dir()).
fn scratch_dir(tag: &str) -> PathBuf {
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join(format!("me-state-{tag}-{n}"));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).expect("create scratch dir");
    dir
}

/// A representative populated GuardState for round-trip + state_hmac tests.
fn sample_state() -> GuardState {
    GuardState {
        config_hmac: "aa".repeat(32),
        state_hmac: String::new(),
        weekly_spent: 2,
        week_anchor: "2026-06-01".to_string(),
        ledger: vec![LedgerEntry {
            ntp_timestamp: 1_749_000_000,
            fields: vec!["curfew.start".to_string(), "curfew.enabled".to_string()],
        }],
        grace: Some(GraceWindow {
            date: "2026-06-05".to_string(),
            window_start: 1_749_100_000,
            window_end: 1_749_100_480,
        }),
    }
}

#[test]
fn guard_state_json_round_trip() {
    let state = sample_state();
    let json = serde_json::to_string(&state).expect("serialize GuardState");
    let back: GuardState = serde_json::from_str(&json).expect("deserialize GuardState");
    assert_eq!(state, back, "deserialize(serialize(s)) must equal s");
}

#[test]
fn state_hmac_recipe_is_reproducible() {
    let mut state = sample_state();
    // The recipe ignores any prior value in state_hmac (it blanks it first), so a populated
    // field must not change the result.
    state.state_hmac = "deadbeef".to_string();

    let tag_a = state.compute_state_hmac(&TEST_KEY);
    let tag_b = state.compute_state_hmac(&TEST_KEY);
    assert_eq!(tag_a, tag_b, "two computations over the same logical state must match");

    // Fill the field with the computed tag, then recompute (the recipe blanks state_hmac
    // again) — must still match (blank + refill parity, threat T-02-01).
    state.state_hmac = tag_a.clone();
    let tag_c = state.compute_state_hmac(&TEST_KEY);
    assert_eq!(tag_a, tag_c, "recompute after refilling state_hmac must match");
}

#[test]
fn config_hmac_equals_hmac_of_on_disk_bytes() {
    let yaml = "curfew:\n  enabled: true\n  start: \"23:00\"\n";

    // sign.rs computes the tag over canonicalize_bytes(yaml) and returns the SAME bytes.
    let (tag_hex, canon) = sign_config(&TEST_KEY, yaml);

    // Write through the same canonical writer the engine uses on disk.
    let dir = scratch_dir("config-hmac");
    let path = dir.join("config.yaml");
    write_canonical_text(&path, yaml).expect("write canonical config");
    let on_disk = fs::read(&path).expect("read back config");

    // The returned canonical bytes must equal what landed on disk...
    assert_eq!(canon, on_disk, "sign.rs canonical bytes must equal on-disk bytes");
    // ...and the tag must equal the HMAC of those on-disk bytes (sign-the-canonical-bytes).
    let expected = tag_to_hex(&sign_bytes(&TEST_KEY, &on_disk));
    assert_eq!(tag_hex, expected, "config_hmac must equal HMAC(on-disk bytes)");
}

#[test]
fn crlf_and_lf_config_yield_identical_config_hmac() {
    let lf = "curfew:\n  enabled: true\n  start: \"23:00\"\n";
    let crlf = "curfew:\r\n  enabled: true\r\n  start: \"23:00\"\r\n";

    let (tag_lf, canon_lf) = sign_config(&TEST_KEY, lf);
    let (tag_crlf, canon_crlf) = sign_config(&TEST_KEY, crlf);

    // Cosmetic EOL drift is absorbed by canonicalization before signing.
    assert_eq!(canon_lf, canon_crlf, "canonical bytes must be EOL-agnostic");
    assert_eq!(tag_lf, tag_crlf, "config_hmac must be identical for CRLF vs LF input");
    // And both must equal a direct HMAC over canonicalize_bytes (no hidden normalization).
    let direct = tag_to_hex(&sign_bytes(&TEST_KEY, &canonicalize_bytes(lf.as_bytes())));
    assert_eq!(tag_lf, direct, "config_hmac must be HMAC(canonicalize_bytes(yaml))");
}
