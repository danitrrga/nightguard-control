//! Canonicalization behavior tests (RED-first, per the TDD directive).
//!
//! Locked decision 1: the canonical byte form the whole project signs over is
//! UTF-8, no BOM, LF-only line endings, exactly one trailing newline.

use trust_kernel::canonicalize_bytes;

/// Helper: canonicalize a &str's bytes and return the result as a String for
/// readable assertions. Output is always valid UTF-8 for these text cases.
fn canon_str(input: &str) -> Vec<u8> {
    canonicalize_bytes(input.as_bytes())
}

const BOM: [u8; 3] = [0xEF, 0xBB, 0xBF];

#[test]
fn crlf_normalized_to_lf() {
    assert_eq!(canon_str("a\r\nb\r\n"), b"a\nb\n");
}

#[test]
fn lone_cr_normalized_to_lf() {
    assert_eq!(canon_str("a\rb\r"), b"a\nb\n");
}

#[test]
fn mixed_cr_and_crlf_normalized() {
    // A lone CR followed later by a CRLF must both collapse to LF.
    assert_eq!(canon_str("a\rb\r\nc"), b"a\nb\nc\n");
}

#[test]
fn bom_is_stripped() {
    let mut input = BOM.to_vec();
    input.extend_from_slice(b"hello\n");
    let out = canonicalize_bytes(&input);
    assert_eq!(out, b"hello\n");
    // The BOM bytes must not survive anywhere.
    assert!(!out.starts_with(&BOM));
}

#[test]
fn bom_with_crlf_stripped_and_normalized() {
    let mut input = BOM.to_vec();
    input.extend_from_slice(b"a\r\nb\r\n");
    assert_eq!(canonicalize_bytes(&input), b"a\nb\n");
}

#[test]
fn no_trailing_newline_gets_exactly_one() {
    assert_eq!(canon_str("a\nb"), b"a\nb\n");
}

#[test]
fn multiple_trailing_newlines_collapse_to_one() {
    assert_eq!(canon_str("a\nb\n\n\n"), b"a\nb\n");
}

#[test]
fn trailing_crlf_runs_collapse_to_one_lf() {
    assert_eq!(canon_str("a\r\nb\r\n\r\n"), b"a\nb\n");
}

#[test]
fn interior_blank_lines_preserved() {
    // Only TRAILING newlines collapse; interior blanks are content.
    assert_eq!(canon_str("a\n\nb\n"), b"a\n\nb\n");
}

#[test]
fn empty_input_becomes_single_newline() {
    // Locked empty-input rule: empty -> "\n".
    assert_eq!(canonicalize_bytes(b""), b"\n");
}

#[test]
fn bare_bom_becomes_single_newline() {
    // A file containing only a BOM canonicalizes to the empty-content form.
    assert_eq!(canonicalize_bytes(&BOM), b"\n");
}

#[test]
fn idempotent_over_all_cases() {
    let cases: &[&[u8]] = &[
        b"a\r\nb\r\n",
        b"a\rb\r",
        b"a\nb",
        b"a\nb\n\n\n",
        b"a\n\nb\n",
        b"",
    ];
    for case in cases {
        let once = canonicalize_bytes(case);
        let twice = canonicalize_bytes(&once);
        assert_eq!(once, twice, "not idempotent for {:?}", case);
    }
    // BOM-prefixed case separately (can't easily inline a byte literal with BOM).
    let mut bom_case = BOM.to_vec();
    bom_case.extend_from_slice(b"x\r\ny");
    let once = canonicalize_bytes(&bom_case);
    let twice = canonicalize_bytes(&once);
    assert_eq!(once, twice, "not idempotent for BOM case");
}

#[test]
fn tolerates_non_utf8_bytes_without_panicking() {
    // The guard hashes raw bytes; canonicalize must operate on the byte slice
    // and never assume valid UTF-8. 0xFF is invalid UTF-8.
    let input = [0xFFu8, b'a', b'\r', b'\n', 0xFE];
    let out = canonicalize_bytes(&input);
    // CRLF normalized to LF; trailing newline appended; invalid bytes preserved.
    assert_eq!(out, vec![0xFF, b'a', b'\n', 0xFE, b'\n']);
}
