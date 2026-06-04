//! Byte canonicalization.
//!
//! The whole project signs over ONE canonical byte form so that any hand-edit is
//! detectable (PITFALLS Pitfall 2). [`canonicalize_bytes`] produces exactly that form:
//! UTF-8 (the caller's responsibility — we never assume valid UTF-8), no leading BOM,
//! LF-only line endings, and exactly one trailing newline.

/// UTF-8 byte-order-mark.
const UTF8_BOM: [u8; 3] = [0xEF, 0xBB, 0xBF];

/// Normalize arbitrary input into the canonical byte form the project signs over:
/// UTF-8, no BOM, LF-only line endings, exactly one trailing newline.
///
/// Rules, applied in order:
/// 1. Strip a single leading UTF-8 BOM if present.
/// 2. Replace every `\r\n` and lone `\r` with `\n`.
/// 3. Trim all trailing `\n` and append exactly one.
///
/// Interior blank lines are preserved — only *trailing* newlines collapse. Empty
/// content (after BOM strip) canonicalizes to `"\n"`.
///
/// Operates on the byte slice, not a `String`: the guard hashes raw bytes, so this
/// must tolerate non-UTF-8 input without panicking. Idempotent:
/// `canonicalize_bytes(canonicalize_bytes(x)) == canonicalize_bytes(x)`.
pub fn canonicalize_bytes(input: &[u8]) -> Vec<u8> {
    // 1. Strip a single leading UTF-8 BOM.
    let body = if input.starts_with(&UTF8_BOM) {
        &input[UTF8_BOM.len()..]
    } else {
        input
    };

    // 2. Normalize CRLF and lone CR to LF.
    let mut out: Vec<u8> = Vec::with_capacity(body.len() + 1);
    let mut i = 0;
    while i < body.len() {
        match body[i] {
            b'\r' => {
                // Collapse \r\n or a lone \r into a single \n.
                if i + 1 < body.len() && body[i + 1] == b'\n' {
                    i += 1; // consume the \n too
                }
                out.push(b'\n');
            }
            byte => out.push(byte),
        }
        i += 1;
    }

    // 3. Trim all trailing \n, then append exactly one.
    while out.last() == Some(&b'\n') {
        out.pop();
    }
    out.push(b'\n');

    out
}
