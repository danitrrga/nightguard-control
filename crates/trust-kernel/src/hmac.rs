//! HMAC-SHA256 sign/verify over RAW bytes (KERN-01).
//!
//! Locked invariant (PITFALLS Pitfall 2 / threats T-01-05, T-01-06):
//! - The key is the 32 RAW key bytes — never its hex/base64 string.
//! - The HMAC is computed over the exact bytes handed in; this module performs NO
//!   normalization of its own (callers sign [`crate::canon::canonicalize_bytes`] output).
//!   That is what makes a one-byte / CRLF / BOM / trailing-newline change to the RAW
//!   bytes detectable as tamper.
//!
//! Pins: `hmac 0.12` + `sha2 0.10` (the canonical RustCrypto pairing — NOT 0.13/0.11).
//! HMAC-SHA256 output is byte-identical to .NET `HMACSHA256` for the same key + message
//! bytes (STACK.md), which is the cross-language contract Plan 03 proves.

use hmac::{Hmac, Mac};
use sha2::Sha256;
use subtle::ConstantTimeEq;

type HmacSha256 = Hmac<Sha256>;

/// Sign `msg` with the 32 RAW key bytes, producing a 32-byte HMAC-SHA256 tag.
///
/// The 32-byte key is used directly as the HMAC key material (a fixed-size key is
/// always within HMAC's accepted length, so `new_from_slice` cannot fail here).
pub fn sign_bytes(key: &[u8; 32], msg: &[u8]) -> [u8; 32] {
    let mut mac = HmacSha256::new_from_slice(key).expect("HMAC accepts any key length");
    mac.update(msg);
    let tag = mac.finalize().into_bytes();
    let mut out = [0u8; 32];
    out.copy_from_slice(&tag);
    out
}

/// Constant-time verify of `tag` for `msg` under `key`.
///
/// Uses HMAC's `verify_slice` (constant-time via `subtle`) — NOT `==` on the tag — so
/// tag comparison does not leak via timing.
pub fn verify_bytes(key: &[u8; 32], msg: &[u8], tag: &[u8; 32]) -> bool {
    let mut mac = HmacSha256::new_from_slice(key).expect("HMAC accepts any key length");
    mac.update(msg);
    mac.verify_slice(tag).is_ok()
}

/// Lowercase hex encoding of a tag (64 chars), for `guard.json` + PowerShell parity.
pub fn tag_to_hex(tag: &[u8; 32]) -> String {
    hex::encode(tag)
}

/// Constant-time equality of two hex-encoded HMAC tags.
///
/// Decodes both hex strings to raw bytes and compares with `subtle::ConstantTimeEq` —
/// NEVER `String ==` (which short-circuits on the first differing byte and is a timing
/// side-channel; explicitly forbidden by the project's "What NOT to Use"). A malformed or
/// length-mismatched hex string fails closed (`false`): a tag we cannot decode can never
/// be treated as verified.
pub fn verify_tag_hex(a_hex: &str, b_hex: &str) -> bool {
    let (a, b) = match (hex::decode(a_hex.trim()), hex::decode(b_hex.trim())) {
        (Ok(a), Ok(b)) => (a, b),
        _ => return false,
    };
    if a.len() != b.len() {
        return false;
    }
    a.ct_eq(&b).into()
}
