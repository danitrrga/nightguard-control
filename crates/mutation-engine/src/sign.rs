//! Canonical-bytes signing helpers over [`trust_kernel::hmac`] (KERN-01 / Pitfall 3).
//!
//! Hard rule (sign-the-canonical-bytes invariant, threat T-02-02 / Pitfall 3): NEVER sign
//! the raw config `String` (which may carry CRLF / no trailing newline). Compute the tag
//! over [`canonicalize_bytes`] output and return those SAME canonical bytes, so the caller
//! writes EXACTLY the bytes that were signed via [`trust_kernel::write_canonical_text`].
//! If the signed bytes and the on-disk bytes ever diverge, the Phase 3 guard reverts a
//! legitimate write as tamper.
//!
//! This module USES `trust_kernel::hmac`; it does not reimplement HMAC.

pub use trust_kernel::canon::canonicalize_bytes;
use trust_kernel::hmac::{sign_bytes, tag_to_hex};

/// Sign a config YAML string over its canonical byte form.
///
/// Canonicalizes `yaml` ONCE (`canonicalize_bytes`), signs those bytes with `key`, and
/// returns `(hex_tag, canonical_bytes)`. The hex tag is the value to store as
/// `guard.json.config_hmac`; the canonical bytes are EXACTLY what the caller must write to
/// disk (e.g. via `write_canonical_text`, which canonicalizes identically) so the on-disk
/// bytes equal the signed bytes.
pub fn sign_config(key: &[u8; 32], yaml: &str) -> (String, Vec<u8>) {
    let canon = canonicalize_bytes(yaml.as_bytes());
    let tag_hex = tag_to_hex(&sign_bytes(key, &canon));
    (tag_hex, canon)
}
