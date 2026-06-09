//! state_interop_cli — the Rust side of the Phase 2 state_hmac cross-language gate.
//!
//! A tiny argv-parsed CLI (no clap — match on args) that the PowerShell harness
//! (`scripts/interop/run_state_interop_gate.ps1`) drives to prove the `guard.json`
//! `state_hmac` recipe (Assumption A3 / threat T-02-01) is byte-identical across Rust
//! and PowerShell, both directions — exactly as Phase 1 proved the config HMAC.
//!
//! Locked `state_hmac` recipe this binary upholds (mirrored by the harness, and the SAME
//! code path as `GuardState::compute_state_hmac` in `state.rs` — no second recipe):
//!   1. Serialize the `GuardState` with `config_hmac` set and `state_hmac` BLANKED to "".
//!   2. Run those JSON string bytes through `trust_kernel::canonicalize_bytes`.
//!   3. `sign_bytes` with the 32-byte key, then `tag_to_hex` -> lowercase hex tag.
//! Key = 32 RAW bytes loaded via the kernel's DPAPI lifecycle (`load_or_create_key`).
//!
//! So the PS side can re-sign the IDENTICAL bytes, `emit-state-hmac` also writes the exact
//! pre-sign canonical byte form to `<out_json_path>.signbytes`. The PS harness HMACs that
//! file verbatim — there is no canonicalization at sign time on either side, so any cosmetic
//! drift would be a tamper, not a parity break.
//!
//! Subcommands (all paths are positional):
//!   emit-state-hmac  <key_path> <out_json_path>
//!       load the 32-byte key; build a FIXED deterministic GuardState; compute state_hmac via
//!       the locked recipe; write the filled-in guard.json to <out_json_path> AND the exact
//!       pre-sign canonical bytes to <out_json_path>.signbytes; print the 64-hex state_hmac.
//!   verify-state-hmac <key_path> <json_path> <expected_hex>
//!       read the guard.json; recompute state_hmac via the recipe; exit 0 on match, exit 2 on
//!       mismatch (distinct code so the harness can assert precisely).
//!
//! Exit codes: 0 = success, 1 = error (bad args / IO / DPAPI / serde),
//!             2 = verify-state-hmac tag mismatch (distinct from a generic error).

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use chrono::Utc;
use mutation_engine::commit::with_commit_lock;
use mutation_engine::state::{GraceWindow, GuardState, LedgerEntry, MutationError};
use mutation_engine::week::most_recent_monday_midnight;
use trust_kernel::canon::canonicalize_bytes;
use trust_kernel::hmac::{sign_bytes, tag_to_hex};
use trust_kernel::key::load_or_create_key;

/// Exit code for a state_hmac verification failure (distinct from a generic error).
const EXIT_VERIFY_FAILED: u8 = 2;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str).unwrap_or("");

    let result: Result<u8, String> = match cmd {
        "emit-state-hmac" => cmd_emit_state_hmac(args.get(2), args.get(3)),
        "verify-state-hmac" => cmd_verify_state_hmac(args.get(2), args.get(3), args.get(4)),
        "hold-commit-lock" => cmd_hold_commit_lock(args.get(2), args.get(3), args.get(4)),
        "init-instance" => cmd_init_instance(args.get(2)),
        other => Err(format!(
            "unknown or missing subcommand: '{other}'\n\
             usage: state_interop_cli <emit-state-hmac|verify-state-hmac|hold-commit-lock|init-instance> ..."
        )),
    };

    match result {
        Ok(code) => ExitCode::from(code),
        Err(msg) => {
            eprintln!("state_interop_cli error: {msg}");
            ExitCode::from(1)
        }
    }
}

/// Build the FIXED, deterministic `GuardState` both sides agree on. Literal values only —
/// a known `config_hmac` hex, a representative ledger entry, an active grace window — so the
/// parity check is over a fully-populated, stable state (not an all-default one).
fn fixed_guard_state() -> GuardState {
    GuardState {
        // A known 64-hex config_hmac (arbitrary but fixed) — the field is set, not blank.
        config_hmac: "1122334455667788990011223344556677889900112233445566778899001122"
            .to_string(),
        // Blanked here; the recipe re-blanks it anyway, but keep the literal explicit.
        state_hmac: String::new(),
        weekly_spent: 2,
        week_anchor: "2026-06-01".to_string(),
        ledger: vec![LedgerEntry {
            ntp_timestamp: 1_750_000_000,
            fields: vec!["curfew.start".to_string(), "curfew.end".to_string()],
        }],
        grace: Some(GraceWindow {
            date: "2026-06-05".to_string(),
            window_start: 1_750_001_000,
            window_end: 1_750_001_480,
        }),
    }
}

/// Produce the EXACT pre-sign canonical bytes the recipe signs: serialize with `state_hmac`
/// blanked, then `canonicalize_bytes`. This is the same byte form `GuardState::compute_state_hmac`
/// signs internally — we expose it so the PS side can HMAC the identical bytes.
fn canonical_signbytes(state: &GuardState) -> Result<Vec<u8>, String> {
    let mut blanked = state.clone();
    blanked.state_hmac = String::new();
    let json = serde_json::to_string(&blanked).map_err(|e| format!("serialize state: {e}"))?;
    Ok(canonicalize_bytes(json.as_bytes()))
}

/// `emit-state-hmac <key_path> <out_json_path>`
fn cmd_emit_state_hmac(
    key_path: Option<&String>,
    out_json_path: Option<&String>,
) -> Result<u8, String> {
    let key_path = key_path.ok_or("emit-state-hmac requires <key_path> <out_json_path>")?;
    let out_json_path =
        out_json_path.ok_or("emit-state-hmac requires <key_path> <out_json_path>")?;
    let key = load_or_create_key(Path::new(key_path)).map_err(|e| e.to_string())?;

    let mut state = fixed_guard_state();

    // Compute the tag via the SINGLE locked recipe in state.rs (no duplicate computation).
    let tag_hex = state.compute_state_hmac(&key);

    // Emit the exact pre-sign canonical bytes the PS side will re-sign. These MUST be derived
    // from the state BEFORE filling state_hmac in, so they equal what compute_state_hmac signed.
    let signbytes = canonical_signbytes(&state)?;
    let signbytes_path = format!("{out_json_path}.signbytes");
    std::fs::write(&signbytes_path, &signbytes)
        .map_err(|e| format!("write {signbytes_path}: {e}"))?;

    // Now fill the tag in and write the complete guard.json.
    state.state_hmac = tag_hex.clone();
    let filled = serde_json::to_string(&state).map_err(|e| format!("serialize guard.json: {e}"))?;
    std::fs::write(out_json_path, filled.as_bytes())
        .map_err(|e| format!("write {out_json_path}: {e}"))?;

    println!("{tag_hex}");
    Ok(0)
}

/// `verify-state-hmac <key_path> <json_path> <expected_hex>`
fn cmd_verify_state_hmac(
    key_path: Option<&String>,
    json_path: Option<&String>,
    expected_hex: Option<&String>,
) -> Result<u8, String> {
    let key_path =
        key_path.ok_or("verify-state-hmac requires <key_path> <json_path> <expected_hex>")?;
    let json_path =
        json_path.ok_or("verify-state-hmac requires <key_path> <json_path> <expected_hex>")?;
    let expected_hex =
        expected_hex.ok_or("verify-state-hmac requires <key_path> <json_path> <expected_hex>")?;
    let key = load_or_create_key(Path::new(key_path)).map_err(|e| e.to_string())?;

    let json = std::fs::read_to_string(json_path).map_err(|e| format!("read {json_path}: {e}"))?;
    let state: GuardState =
        serde_json::from_str(&json).map_err(|e| format!("parse {json_path}: {e}"))?;

    // Recompute via the locked recipe (re-blanks state_hmac internally).
    let recomputed = state.compute_state_hmac(&key);
    if recomputed.trim().eq_ignore_ascii_case(expected_hex.trim()) {
        Ok(0)
    } else {
        eprintln!(
            "verify-state-hmac: tag mismatch (recomputed != expected)\n  recomputed: {recomputed}\n  expected:   {expected_hex}"
        );
        Ok(EXIT_VERIFY_FAILED)
    }
}

/// `hold-commit-lock <lock_dir> <ready_path> <release_path>`
///
/// The GARD-05 live lock holder for `run_guard_gate.ps1`. Acquires the REAL cross-process
/// `with_commit_lock` on `<lock_dir>` (the same `fd_lock::RwLock::write()` / Windows
/// `LockFileEx` + `LOCKFILE_EXCLUSIVE_LOCK` an app commit takes), then signals readiness by
/// creating `<ready_path>` so the gate knows the lock is genuinely held before it fires the
/// guard. It then BLOCKS inside the critical section until the gate creates `<release_path>`,
/// at which point it returns (dropping the lock -> UnlockFile). This lets the gate assert the
/// guard's `Test-LockHeld` circuit-breaker observes a held lock and skips the revert (D-06),
/// then observes a free lock after release. A 30s safety timeout prevents a wedged gate from
/// hanging the holder forever.
fn cmd_hold_commit_lock(
    lock_dir: Option<&String>,
    ready_path: Option<&String>,
    release_path: Option<&String>,
) -> Result<u8, String> {
    let lock_dir =
        lock_dir.ok_or("hold-commit-lock requires <lock_dir> <ready_path> <release_path>")?;
    let ready_path =
        ready_path.ok_or("hold-commit-lock requires <lock_dir> <ready_path> <release_path>")?;
    let release_path =
        release_path.ok_or("hold-commit-lock requires <lock_dir> <ready_path> <release_path>")?;

    let release = release_path.clone();
    let ready = ready_path.clone();
    let held: Result<(), MutationError> = with_commit_lock(Path::new(lock_dir), move || {
        // Signal the gate that the lock is now genuinely held (created AFTER acquisition).
        std::fs::write(&ready, b"ready").map_err(|e| MutationError::Io(format!("write ready: {e}")))?;
        // Block inside the critical section until the gate asks us to release (or we time out).
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(30);
        while !Path::new(&release).exists() {
            if std::time::Instant::now() >= deadline {
                break; // safety valve: never hang forever if the gate wedges
            }
            std::thread::sleep(std::time::Duration::from_millis(50));
        }
        Ok(())
    });
    held.map_err(|e| e.to_string())?;
    Ok(0)
}

/// `init-instance <data_dir>`
///
/// Initialize a fresh, fully-armed signed instance under `<data_dir>` (WIRE-02 / D-10).
/// This is the LIVE-instance counterpart to `emit-state-hmac`: instead of a fixed test
/// state it writes a real armed `GuardState` whose `state_hmac` and `config_hmac` both verify
/// in Rust AND PowerShell. Ordered recipe (mirrors RESEARCH Pattern 3):
///   1. Resolve the five fixed paths under `<data_dir>` exactly like `AppCtx::load`
///      (config.yaml / config.sanctioned.yaml / guard.json / .nightguard.lock / .guardkey).
///   2. Read `config.yaml` raw bytes and run them through `canonicalize_bytes` (UTF-8 / no BOM /
///      LF / one trailing LF) so the PS minimal parser (KERN-04) and the Rust HMAC agree.
///   3. Write the canonical bytes back to `config.yaml` AND byte-copy them to
///      `config.sanctioned.yaml` so the two files are byte-identical (the guard's
///      `Test-SanctionedValid` revert-target identity).
///   4. `load_or_create_key(<data_dir>/.guardkey)` — generate-once + DPAPI-protect (Scope::User).
///   5. `config_hmac = tag_to_hex(sign_bytes(&key, &canonical_config_bytes))` (lowercase hex).
///   6. Build the armed `GuardState` (weekly_spent=0 -> 3 tokens; week_anchor from the DST-aware
///      `most_recent_monday_midnight`; ledger empty; grace none).
///   7. `compute_state_hmac(&key)` via the SINGLE locked A3 recipe; fill it in; write `guard.json`.
///
/// Prints `config_hmac=<hex>` and `state_hmac=<hex>`.
fn cmd_init_instance(data_dir: Option<&String>) -> Result<u8, String> {
    let data_dir = data_dir.ok_or("init-instance requires <data_dir>")?;
    let data_dir = PathBuf::from(data_dir);
    if !data_dir.is_dir() {
        return Err(format!("data dir does not exist: {}", data_dir.display()));
    }

    // (1) The five fixed paths under <data_dir>, exactly like AppCtx::load.
    let config_path = data_dir.join("config.yaml");
    let sanctioned_path = data_dir.join("config.sanctioned.yaml");
    let guard_path = data_dir.join("guard.json");
    let key_path = data_dir.join(".guardkey");
    // .nightguard.lock is created lazily by the commit lock; not written here.

    // (2) Read config.yaml raw bytes and canonicalize them.
    let raw_config = std::fs::read(&config_path)
        .map_err(|e| format!("read {}: {e}", config_path.display()))?;
    let canonical_config = canonicalize_bytes(&raw_config);

    // (3) Write the canonical bytes back to config.yaml, then byte-copy to sanctioned so the
    //     two files are byte-identical (HMAC(sanctioned) == HMAC(config) == config_hmac).
    std::fs::write(&config_path, &canonical_config)
        .map_err(|e| format!("write {}: {e}", config_path.display()))?;
    std::fs::write(&sanctioned_path, &canonical_config)
        .map_err(|e| format!("write {}: {e}", sanctioned_path.display()))?;

    // (4) Generate-once + DPAPI-protect the 32-byte signing key.
    let key = load_or_create_key(&key_path).map_err(|e| e.to_string())?;

    // (5) config_hmac over the IDENTICAL canonical config bytes (lowercase hex).
    let config_hmac = tag_to_hex(&sign_bytes(&key, &canonical_config));

    // (6) Build the armed initial state (D-10). week_anchor via the DST-aware Monday anchor in
    //     Europe/Amsterdam — never naive date math.
    let week_anchor = most_recent_monday_midnight(Utc::now(), "Europe/Amsterdam")
        .with_timezone(&chrono_tz::Europe::Amsterdam)
        .date_naive()
        .format("%Y-%m-%d")
        .to_string();
    let mut state = GuardState {
        config_hmac: config_hmac.clone(),
        state_hmac: String::new(),
        weekly_spent: 0,
        week_anchor,
        ledger: vec![],
        grace: None,
    };

    // (7) state_hmac via the SINGLE locked A3 recipe (no second canonicalize+HMAC); write guard.json.
    let state_hmac = state.compute_state_hmac(&key);
    state.state_hmac = state_hmac.clone();
    let filled = serde_json::to_string(&state)
        .map_err(|e| format!("serialize guard.json: {e}"))?;
    std::fs::write(&guard_path, filled.as_bytes())
        .map_err(|e| format!("write {}: {e}", guard_path.display()))?;

    println!("config_hmac={config_hmac}");
    println!("state_hmac={state_hmac}");
    Ok(0)
}
