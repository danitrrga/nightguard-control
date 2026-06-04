//! HMAC-SHA256 sign/verify over RAW bytes (RED stub — replaced in GREEN).

/// Sign `msg` with the 32 RAW key bytes, producing a 32-byte HMAC-SHA256 tag.
pub fn sign_bytes(_key: &[u8; 32], _msg: &[u8]) -> [u8; 32] {
    [0u8; 32]
}

/// Constant-time verify of `tag` for `msg` under `key`.
pub fn verify_bytes(_key: &[u8; 32], _msg: &[u8], _tag: &[u8; 32]) -> bool {
    false
}

/// Lowercase hex encoding of a tag (64 chars), for guard.json + PowerShell parity.
pub fn tag_to_hex(_tag: &[u8; 32]) -> String {
    String::new()
}
