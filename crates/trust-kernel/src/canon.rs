//! Byte canonicalization — implemented in Task 2.

/// Normalize arbitrary input into the one canonical byte form the whole project
/// signs over: UTF-8, no BOM, LF-only line endings, exactly one trailing newline.
///
/// Idempotent: `canonicalize_bytes(canonicalize_bytes(x)) == canonicalize_bytes(x)`.
pub fn canonicalize_bytes(input: &[u8]) -> Vec<u8> {
    // Stub — real implementation lands in Task 2.
    input.to_vec()
}
