//! DPAPI key-store tests (KERN-02).
//!
//! Locked invariant (PITFALLS Pitfall 1 / threats T-01-07, T-01-08): the 32-byte key
//! is protected as a RAW `CryptProtectData` blob, CurrentUser scope, NO optional
//! entropy. NEVER PowerShell SecureString / UTF-16 / hex framing. The dead giveaway of
//! getting this wrong is a "decrypted key" that is 64 bytes (UTF-16 of a 32-char hex
//! string) instead of 32 RAW bytes — the `unprotect_yields_exactly_32_not_64` test is
//! the explicit canary against that.
//!
//! These tests exercise REAL DPAPI and must run as the interactive CurrentUser (that is
//! the intended scope). If DPAPI is unavailable in this context they would error rather
//! than silently pass.

#![cfg(windows)]

use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

use trust_kernel::dpapi::{dpapi_protect, dpapi_unprotect};
use trust_kernel::key::load_or_create_key;

static UNIQ: AtomicU64 = AtomicU64::new(0);

/// A unique temp path for a key file (not created — `load_or_create_key` creates it).
fn temp_key_path() -> PathBuf {
    let n = UNIQ.fetch_add(1, Ordering::Relaxed);
    let mut p = std::env::temp_dir();
    p.push(format!(
        "nightguard-test-{}-{}.guardkey",
        std::process::id(),
        n
    ));
    // Ensure a clean slate.
    let _ = std::fs::remove_file(&p);
    p
}

#[test]
fn dpapi_round_trip_recovers_original_bytes() {
    let plaintext = b"a-32-byte-key-exactly-32-bytes!!"; // 32 bytes
    assert_eq!(plaintext.len(), 32);
    let blob = dpapi_protect(plaintext).expect("protect");
    let recovered = dpapi_unprotect(&blob).expect("unprotect");
    assert_eq!(&recovered, plaintext, "DPAPI round-trip must recover bytes");
}

#[test]
fn unprotect_yields_exactly_32_not_64() {
    // THE canary against SecureString/UTF-16/hex framing: a 32-byte key must come back
    // as exactly 32 raw bytes, never 64 (UTF-16 of a 32-char hex string).
    let key = [0xABu8; 32];
    let blob = dpapi_protect(&key).expect("protect");
    let recovered = dpapi_unprotect(&blob).expect("unprotect");
    assert_eq!(recovered.len(), 32, "unprotected key MUST be 32 bytes");
    assert_ne!(
        recovered.len(),
        64,
        "64 bytes is the SecureString/UTF-16 framing giveaway"
    );
    assert_eq!(&recovered[..], &key[..], "bytes must be identical");
}

#[test]
fn blob_is_opaque_and_longer_than_plaintext() {
    let key = [0x11u8; 32];
    let blob = dpapi_protect(&key).expect("protect");
    assert!(
        blob.len() > 32,
        "a real DPAPI blob carries header/MAC overhead and is longer than 32 bytes"
    );
    assert_ne!(&blob[..], &key[..], "the blob must be encrypted, not plaintext");
}

#[test]
fn load_or_create_generates_then_loads_same_key() {
    let path = temp_key_path();

    // First call: no file exists -> generate, persist, return 32 bytes.
    let k1 = load_or_create_key(&path).expect("create");
    assert_eq!(k1.len(), 32);
    assert!(path.exists(), "key file must be persisted");

    // Second call: same path -> load the SAME bytes (not regenerated).
    let k2 = load_or_create_key(&path).expect("load");
    assert_eq!(k1, k2, "load_or_create_key must be generate-once / load-thereafter");

    let _ = std::fs::remove_file(&path);
}

#[test]
fn persisted_file_is_the_raw_dpapi_blob() {
    let path = temp_key_path();
    let key = load_or_create_key(&path).expect("create");

    // The on-disk bytes must be the RAW protected blob (no base64/text framing):
    // unprotecting the file's exact bytes recovers the key.
    let on_disk = std::fs::read(&path).expect("read key file");
    let recovered = dpapi_unprotect(&on_disk).expect("unprotect on-disk blob");
    assert_eq!(&recovered[..], &key[..], "on-disk bytes are the raw blob of the key");

    // Sanity: the file is not the plaintext key and not obvious base64 of 32 bytes.
    assert_ne!(&on_disk[..], &key[..], "file must not be the plaintext key");

    let _ = std::fs::remove_file(&path);
}
