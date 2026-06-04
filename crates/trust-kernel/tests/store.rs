//! Atomic-store behavior tests (RED-first, per the TDD directive).
//!
//! Proves the crash-safety contract (PITFALLS Pitfall 3 / threat T-01-02): an
//! interrupted write must leave the prior file byte-for-byte intact, no temp file
//! leaks, and `write_canonical_text` is byte-stable (KERN-04).

use std::fs;
use std::path::{Path, PathBuf};

use trust_kernel::{atomic_write, write_canonical_text};

/// Per-test scratch directory under the crate's own `target/` (avoids $TMPDIR per
/// the Windows note; lives inside the gitignored build dir). Uniquified by a counter
/// so concurrent tests never collide.
fn scratch_dir(tag: &str) -> PathBuf {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join(format!("store-{tag}-{n}"));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).expect("create scratch dir");
    dir
}

/// Count files in `dir` whose name contains ".tmp".
fn tmp_files(dir: &Path) -> Vec<PathBuf> {
    fs::read_dir(dir)
        .unwrap()
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.file_name().unwrap().to_string_lossy().contains(".tmp"))
        .collect()
}

#[test]
fn atomic_write_creates_file_with_exact_bytes() {
    let dir = scratch_dir("create");
    let target = dir.join("out.bin");
    let bytes = b"\x00\x01\x02hello\xff";
    atomic_write(&target, bytes).expect("write should succeed");
    assert_eq!(fs::read(&target).unwrap(), bytes);
}

#[test]
fn no_temp_file_remains_after_success() {
    let dir = scratch_dir("notmp");
    let target = dir.join("out.bin");
    atomic_write(&target, b"content").expect("write should succeed");
    let leftovers = tmp_files(&dir);
    assert!(
        leftovers.is_empty(),
        "leftover temp files after success: {leftovers:?}"
    );
}

#[test]
fn prior_file_intact_when_write_fails() {
    let dir = scratch_dir("intact");
    let target = dir.join("config.yaml");
    let original = b"curfew: 21:30\n# do not lose me\n";
    // Establish a pre-existing, valid target file.
    fs::write(&target, original).unwrap();

    // Inject failure: the target's PARENT must be a directory for the same-dir temp
    // write to succeed. Replace the parent dir with a regular file so creating the
    // temp file inside it fails — simulating an interrupted/failed write.
    let nested_parent = dir.join("nested");
    fs::write(&nested_parent, b"i am a file, not a dir").unwrap();
    let doomed_target = nested_parent.join("config.yaml");

    let result = atomic_write(&doomed_target, b"new content that must not land");
    assert!(result.is_err(), "write into a non-directory parent must fail");

    // The unrelated pre-existing file is untouched (no truncation, no partial write).
    assert_eq!(fs::read(&target).unwrap(), original);
    // No temp file leaked into the real scratch dir.
    assert!(tmp_files(&dir).is_empty(), "temp leaked on failure");
}

#[test]
fn overwrite_leaves_no_partial_and_replaces_bytes() {
    let dir = scratch_dir("overwrite");
    let target = dir.join("config.yaml");
    fs::write(&target, b"old\nold\nold\n").unwrap();
    atomic_write(&target, b"new\n").expect("overwrite should succeed");
    assert_eq!(fs::read(&target).unwrap(), b"new\n");
    assert!(tmp_files(&dir).is_empty());
}

#[test]
fn write_canonical_text_is_byte_stable_and_canonical() {
    let dir = scratch_dir("stable");
    let a = dir.join("a.yaml");
    let b = dir.join("b.yaml");
    // Same logical content, written twice (with CRLF + missing trailing newline to
    // prove canonicalization is applied).
    let content = "curfew:\r\n  start: 21:30\r\n  end: 06:00";
    write_canonical_text(&a, content).unwrap();
    write_canonical_text(&b, content).unwrap();

    let bytes_a = fs::read(&a).unwrap();
    let bytes_b = fs::read(&b).unwrap();

    // Byte-stable across repeated writes.
    assert_eq!(bytes_a, bytes_b, "repeated writes are not byte-identical");

    // Canonical form: no CRLF, no BOM, exactly one trailing LF.
    assert!(!bytes_a.contains(&b'\r'), "must contain no CR");
    assert!(!bytes_a.starts_with(&[0xEF, 0xBB, 0xBF]), "must have no BOM");
    assert_eq!(*bytes_a.last().unwrap(), b'\n', "must end in LF");
    assert_ne!(
        bytes_a[bytes_a.len().saturating_sub(2)],
        b'\n',
        "must have exactly one trailing newline"
    );
}

#[test]
fn round_trip_config_is_parser_friendly() {
    // A representative config.yaml with comments, written via write_canonical_text,
    // reads back as raw bytes with no CRLF and no BOM — so the line-oriented
    // PowerShell minimal parser reads it unchanged (KERN-04).
    let dir = scratch_dir("roundtrip");
    let target = dir.join("config.yaml");
    let content = "# Nightguard curfew\r\ncurfew:\r\n  enabled: true\r\n  start: 21:30\r\n  end: 06:00\r\n";
    write_canonical_text(&target, content).unwrap();

    let raw = fs::read(&target).unwrap();
    assert!(!raw.contains(&b'\r'), "round-tripped config has CRLF");
    assert!(!raw.starts_with(&[0xEF, 0xBB, 0xBF]), "round-tripped config has BOM");
    // Content survives, just LF-normalized.
    let text = String::from_utf8(raw).unwrap();
    assert!(text.contains("# Nightguard curfew\n"));
    assert!(text.contains("start: 21:30\n"));
    assert!(text.ends_with("end: 06:00\n"));
}
