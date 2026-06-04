//! HMAC-SHA256 sign/verify tests over RAW bytes (KERN-01).
//!
//! Locked invariant (PITFALLS Pitfall 2 / threat T-01-05, T-01-06): the key is the
//! 32 RAW key bytes (never its hex/base64 string) and the HMAC is computed over the
//! exact bytes handed in. Tamper detection must fire on a one-byte change AND on
//! cosmetic-EOL/BOM/trailing-newline drift of the RAW bytes — proving we sign exactly
//! what is on disk.
//!
//! Known-answer vector provenance (auditable):
//! - The HMAC-SHA256 algorithm is fully specified by RFC 2104 / FIPS 198-1 and is
//!   byte-identical across RustCrypto, .NET `HMACSHA256`, and OpenSSL (STACK.md
//!   "Version Compatibility"). The oracle used to derive the vector below is Python's
//!   `hmac`/`hashlib`, which reproduces the published RFC 4231 Test Case 1 tag
//!   (key = 20 x 0x0b, msg = "Hi There") =
//!   b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7 exactly,
//!   confirming it is a faithful HMAC-SHA256 oracle.
//! - Because `sign_bytes` takes a fixed `[u8;32]` key, the asserted vector here uses a
//!   32-byte key of 0x0b over the same "Hi There" message:
//!     key = 32 x 0x0b, msg = "Hi There"
//!     tag = 198a607eb44bfbc69903a0f1cf2bbdc5ba0aa3f3d9ae3c1c7a3b1696a0b68cf7
//!   (derived via the same RFC-faithful oracle; reproducible with
//!    `python -c "import hmac,hashlib;print(hmac.new(bytes([0x0b]*32),b'Hi There',hashlib.sha256).hexdigest())"`).

use trust_kernel::canon::canonicalize_bytes;
use trust_kernel::hmac::{sign_bytes, tag_to_hex, verify_bytes};

/// The fixed 32-byte known-answer key (32 x 0x0b).
const KAT_KEY: [u8; 32] = [0x0b; 32];
const KAT_MSG: &[u8] = b"Hi There";
const KAT_TAG_HEX: &str = "198a607eb44bfbc69903a0f1cf2bbdc5ba0aa3f3d9ae3c1c7a3b1696a0b68cf7";

#[test]
fn known_answer_vector_matches_external_oracle() {
    let tag = sign_bytes(&KAT_KEY, KAT_MSG);
    assert_eq!(
        tag_to_hex(&tag),
        KAT_TAG_HEX,
        "HMAC-SHA256(32x0x0b, \"Hi There\") must match the RFC-faithful oracle vector"
    );
}

#[test]
fn tag_to_hex_is_64_lowercase_hex_chars() {
    let tag = sign_bytes(&KAT_KEY, KAT_MSG);
    let hex = tag_to_hex(&tag);
    assert_eq!(hex.len(), 64, "a SHA-256 tag is 32 bytes => 64 hex chars");
    assert!(
        hex.chars().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit()),
        "tag hex must be lowercase: {hex}"
    );
}

#[test]
fn round_trip_verifies_true() {
    let key = [7u8; 32];
    let msg = b"the quick brown fox";
    let tag = sign_bytes(&key, msg);
    assert!(verify_bytes(&key, msg, &tag), "self-signed tag must verify");
}

#[test]
fn one_byte_mutation_fails_verification() {
    let key = [7u8; 32];
    let msg = b"the quick brown fox".to_vec();
    let tag = sign_bytes(&key, &msg);

    let mut mutated = msg.clone();
    mutated[4] ^= 0x01; // flip a single bit of one byte
    assert!(
        !verify_bytes(&key, &mutated, &tag),
        "a one-byte mutation must fail verification"
    );
}

#[test]
fn wrong_key_fails_verification() {
    let key = [7u8; 32];
    let other_key = [8u8; 32];
    let msg = b"the quick brown fox";
    let tag = sign_bytes(&key, msg);
    assert!(
        !verify_bytes(&other_key, msg, &tag),
        "a different key must fail verification"
    );
}

#[test]
fn canonicalization_absorbs_cosmetic_eol_but_raw_crlf_is_tamper() {
    // We sign the CANONICAL form of "a\nb\n".
    let key = [42u8; 32];
    let lf_canon = canonicalize_bytes(b"a\nb\n");
    let tag = sign_bytes(&key, &lf_canon);

    // A CRLF version, once canonicalized, is byte-identical => verifies (cosmetic EOL
    // is absorbed by canonicalization, NOT by HMAC).
    let crlf_canon = canonicalize_bytes(b"a\r\nb\r\n");
    assert!(
        verify_bytes(&key, &crlf_canon, &tag),
        "canonicalized CRLF must equal canonicalized LF and verify"
    );

    // But verifying the RAW (un-canonicalized) CRLF bytes FAILS — proving HMAC signs
    // exactly the bytes handed in, with no normalization of its own.
    assert!(
        !verify_bytes(&key, b"a\r\nb\r\n", &tag),
        "raw CRLF bytes must NOT verify against a tag over canonical LF bytes"
    );
}

#[test]
fn raw_bom_prefix_is_tamper() {
    // Tag is signed over the NON-BOM raw bytes.
    let key = [42u8; 32];
    let clean = b"hello\n";
    let tag = sign_bytes(&key, clean);

    // A BOM-prefixed RAW byte string is a different message => must fail.
    let mut with_bom = vec![0xEF, 0xBB, 0xBF];
    with_bom.extend_from_slice(clean);
    assert!(
        !verify_bytes(&key, &with_bom, &tag),
        "a BOM-prefixed raw byte string must NOT verify"
    );
}

#[test]
fn trailing_newline_change_is_tamper() {
    // Tag signed over the single-trailing-newline form.
    let key = [42u8; 32];
    let one_nl = b"hello\n";
    let tag = sign_bytes(&key, one_nl);

    // A DOUBLE trailing newline is a different RAW message => must fail.
    assert!(
        !verify_bytes(&key, b"hello\n\n", &tag),
        "an extra trailing newline must NOT verify"
    );
    // No trailing newline likewise fails.
    assert!(
        !verify_bytes(&key, b"hello", &tag),
        "a removed trailing newline must NOT verify"
    );
}
