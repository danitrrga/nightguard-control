//! interop_cli — the Rust side of the Phase 1 cross-language exit gate.
//!
//! A tiny argv-parsed CLI (no clap — match on args) that the PowerShell harness
//! (`scripts/interop/run_interop_gate.ps1`) drives to prove the DPAPI + HMAC trust
//! kernel is byte-identical across Rust and PowerShell, both directions.
//!
//! Locked invariants this binary upholds (mirrored by the harness):
//! - DPAPI: raw `CryptProtectData` blob, CurrentUser scope, NO optional entropy.
//!   (via `trust_kernel::dpapi`, `Scope::User`, `None`).
//! - HMAC: over the RAW bytes of the data file (read with `std::fs::read`, NO
//!   re-canonicalization at sign time — the file on disk is already the canonical
//!   artifact). Key = 32 RAW bytes. Tags emitted as lowercase hex.
//! - The unprotected key MUST be exactly 32 bytes; 64 is the SecureString-framing
//!   canary and is a hard error.
//!
//! Subcommands (all paths are positional):
//!   gen-key       <key_path>                 generate-or-load the DPAPI key; print 64 hex chars
//!   unprotect-key <key_path>                 read raw DPAPI blob; print the 32 key bytes as hex
//!   protect-key   <hex32> <out_path>         parse 32 bytes from hex; DPAPI-protect; atomic_write blob
//!   sign-file     <key_path> <data_path>     load key; HMAC raw bytes of data_path; print hex tag
//!   verify-file   <key_path> <data_path> <hex_tag>   exit 0 if tag matches, exit 2 if not
//!   write-config  <out_path>                 write a representative config.yaml (canonical bytes)
//!
//! Exit codes: 0 = success, 1 = error (bad args / IO / DPAPI / bad length),
//!             2 = verify-file tag mismatch (distinct so the harness can assert precisely).

use std::path::Path;
use std::process::ExitCode;

use trust_kernel::hmac::{sign_bytes, tag_to_hex, verify_bytes};
use trust_kernel::key::load_or_create_key;
use trust_kernel::write_canonical_text;
#[cfg(windows)]
use trust_kernel::dpapi::{dpapi_protect, dpapi_unprotect};

/// Exit code for a tag-verification failure (distinct from a generic error).
const EXIT_VERIFY_FAILED: u8 = 2;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str).unwrap_or("");

    let result: Result<u8, String> = match cmd {
        "gen-key" => cmd_gen_key(args.get(2)),
        "unprotect-key" => cmd_unprotect_key(args.get(2)),
        "protect-key" => cmd_protect_key(args.get(2), args.get(3)),
        "sign-file" => cmd_sign_file(args.get(2), args.get(3)),
        "verify-file" => cmd_verify_file(args.get(2), args.get(3), args.get(4)),
        "write-config" => cmd_write_config(args.get(2)),
        other => Err(format!(
            "unknown or missing subcommand: '{other}'\n\
             usage: interop_cli <gen-key|unprotect-key|protect-key|sign-file|verify-file|write-config> ..."
        )),
    };

    match result {
        Ok(code) => ExitCode::from(code),
        Err(msg) => {
            eprintln!("interop_cli error: {msg}");
            ExitCode::from(1)
        }
    }
}

/// `gen-key <key_path>` — generate-once / load-thereafter the DPAPI key; print 64 hex chars.
fn cmd_gen_key(key_path: Option<&String>) -> Result<u8, String> {
    let key_path = key_path.ok_or("gen-key requires <key_path>")?;
    let key = load_or_create_key(Path::new(key_path)).map_err(|e| e.to_string())?;
    println!("{}", hex::encode(key));
    Ok(0)
}

/// `unprotect-key <key_path>` — read the raw DPAPI blob, unprotect, print 32 bytes as hex.
/// Errors (exit 1) if the unprotected result is not exactly 32 bytes (the 64-byte
/// SecureString-framing canary). On Windows this is enforced by `dpapi_unprotect` +
/// the explicit length check below.
#[cfg(windows)]
fn cmd_unprotect_key(key_path: Option<&String>) -> Result<u8, String> {
    let key_path = key_path.ok_or("unprotect-key requires <key_path>")?;
    let blob = std::fs::read(key_path).map_err(|e| format!("read {key_path}: {e}"))?;
    let plain = dpapi_unprotect(&blob).map_err(|e| e.to_string())?;
    if plain.len() != 32 {
        return Err(format!(
            "unprotected key length was {} bytes, expected 32 (SecureString-framing canary)",
            plain.len()
        ));
    }
    println!("{}", hex::encode(&plain));
    Ok(0)
}

/// `protect-key <hex32> <out_path>` — parse 32 bytes from hex, DPAPI-protect, atomic_write the blob.
#[cfg(windows)]
fn cmd_protect_key(hex32: Option<&String>, out_path: Option<&String>) -> Result<u8, String> {
    let hex32 = hex32.ok_or("protect-key requires <hex32> <out_path>")?;
    let out_path = out_path.ok_or("protect-key requires <hex32> <out_path>")?;
    let key = parse_key32_hex(hex32)?;
    let blob = dpapi_protect(&key).map_err(|e| e.to_string())?;
    trust_kernel::atomic_write(Path::new(out_path), &blob).map_err(|e| e.to_string())?;
    Ok(0)
}

/// `sign-file <key_path> <data_path>` — load key, HMAC the RAW bytes of data_path, print hex tag.
/// NO canonicalization here: the file on disk is already the canonical artifact; we sign
/// exactly what's there so any cosmetic CRLF/BOM/trailing-newline drift is detected as tamper.
fn cmd_sign_file(key_path: Option<&String>, data_path: Option<&String>) -> Result<u8, String> {
    let key_path = key_path.ok_or("sign-file requires <key_path> <data_path>")?;
    let data_path = data_path.ok_or("sign-file requires <key_path> <data_path>")?;
    let key = load_key(key_path)?;
    let data = std::fs::read(data_path).map_err(|e| format!("read {data_path}: {e}"))?;
    let tag = sign_bytes(&key, &data);
    println!("{}", tag_to_hex(&tag));
    Ok(0)
}

/// `verify-file <key_path> <data_path> <hex_tag>` — exit 0 if the tag matches, exit 2 if not.
fn cmd_verify_file(
    key_path: Option<&String>,
    data_path: Option<&String>,
    hex_tag: Option<&String>,
) -> Result<u8, String> {
    let key_path = key_path.ok_or("verify-file requires <key_path> <data_path> <hex_tag>")?;
    let data_path = data_path.ok_or("verify-file requires <key_path> <data_path> <hex_tag>")?;
    let hex_tag = hex_tag.ok_or("verify-file requires <key_path> <data_path> <hex_tag>")?;
    let key = load_key(key_path)?;
    let data = std::fs::read(data_path).map_err(|e| format!("read {data_path}: {e}"))?;
    let tag = parse_tag32_hex(hex_tag)?;
    if verify_bytes(&key, &data, &tag) {
        Ok(0)
    } else {
        eprintln!("verify-file: tag mismatch (file does not match the given tag)");
        Ok(EXIT_VERIFY_FAILED)
    }
}

/// `write-config <out_path>` — write a representative config.yaml via the canonical writer,
/// so the harness can prove PowerShell reads it back with no CRLF/BOM (KERN-04).
fn cmd_write_config(out_path: Option<&String>) -> Result<u8, String> {
    let out_path = out_path.ok_or("write-config requires <out_path>")?;
    // A representative curfew block with a comment. The canonical writer guarantees
    // UTF-8 / no BOM / LF-only / exactly one trailing newline.
    let content = "# Nightguard curfew config (representative)\n\
curfew:\n\
  enabled: true\n\
  start: \"21:30\"\n\
  end: \"06:00\"\n\
  block_when_offline: true\n\
tokens:\n\
  weekly_budget: 3\n";
    write_canonical_text(Path::new(out_path), content).map_err(|e| e.to_string())?;
    Ok(0)
}

/// Load the 32-byte signing key from a key file (DPAPI blob) via the kernel's lifecycle.
fn load_key(key_path: &str) -> Result<[u8; 32], String> {
    load_or_create_key(Path::new(key_path)).map_err(|e| e.to_string())
}

/// Parse exactly 32 bytes from a 64-char lowercase/uppercase hex string.
fn parse_key32_hex(hex32: &str) -> Result<[u8; 32], String> {
    let bytes = hex::decode(hex32.trim()).map_err(|e| format!("bad hex key: {e}"))?;
    if bytes.len() != 32 {
        return Err(format!(
            "hex key decoded to {} bytes, expected 32",
            bytes.len()
        ));
    }
    let mut out = [0u8; 32];
    out.copy_from_slice(&bytes);
    Ok(out)
}

/// Parse a 32-byte HMAC tag from a 64-char hex string.
fn parse_tag32_hex(hex_tag: &str) -> Result<[u8; 32], String> {
    let bytes = hex::decode(hex_tag.trim()).map_err(|e| format!("bad hex tag: {e}"))?;
    if bytes.len() != 32 {
        return Err(format!(
            "hex tag decoded to {} bytes, expected 32",
            bytes.len()
        ));
    }
    let mut out = [0u8; 32];
    out.copy_from_slice(&bytes);
    Ok(out)
}

// Non-Windows stubs so the crate still type-checks off-Windows (the project is Windows-only;
// these are never reached in practice but keep `cargo check` honest on other hosts).
#[cfg(not(windows))]
fn cmd_unprotect_key(_key_path: Option<&String>) -> Result<u8, String> {
    Err("DPAPI is Windows-only".into())
}
#[cfg(not(windows))]
fn cmd_protect_key(_hex32: Option<&String>, _out_path: Option<&String>) -> Result<u8, String> {
    Err("DPAPI is Windows-only".into())
}
