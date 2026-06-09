//! The IPC contract: `AppCtx`, the serde DTOs, [`IpcError`], and the four
//! `#[tauri::command]` stubs.
//!
//! This module fixes the SHAPE every Phase 4 plan builds on: the DTO fields, the error
//! surface, the data-dir/key resolution, and the four final command signatures. Command
//! bodies are minimal stubs here — later plans fill the real read/verify/classify/
//! commit/grace logic against these fixed signatures (D-01); the signatures do NOT change.
//!
//! Error/DTO voice mirrors `mutation_engine::state` (thiserror + prefixed messages +
//! `From` folding); the IPC layer adds a `Serialize`-as-string impl so the JS `catch()`
//! receives the message (RESEARCH Pattern 2).

use std::path::PathBuf;

use serde::Serialize;

use mutation_engine::commit::CommitPaths;
use trust_kernel::key::load_or_create_key;

/// IPC error surfaced across the `invoke` boundary.
///
/// Same `#[derive(Debug, thiserror::Error)]` + per-variant `#[error("…")]` voice as
/// `mutation_engine::MutationError`, plus a `Serialize` impl that emits `.to_string()`
/// (so JS `catch(e)` receives the human message) and `From<MutationError>` folding.
#[derive(Debug, thiserror::Error)]
pub enum IpcError {
    /// Any engine-side failure, folded to its message string.
    #[error("{0}")]
    Engine(String),
    /// An HMAC re-verification failed (fail-closed read path).
    #[error("verify failed")]
    VerifyFailed,
    /// The app context could not be established (e.g. no data dir / no key).
    #[error("not initialized")]
    NotInitialized,
}

impl serde::Serialize for IpcError {
    fn serialize<S: serde::Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        // Surface the message to JS so `invoke(...).catch(e)` gets a readable string.
        s.serialize_str(&self.to_string())
    }
}

impl From<mutation_engine::MutationError> for IpcError {
    fn from(e: mutation_engine::MutationError) -> Self {
        IpcError::Engine(e.to_string())
    }
}

/// Managed application context: the loaded signing key, the resolved data dir, the fixed
/// commit paths, and the configured timezone.
///
/// Built ONCE at startup by [`AppCtx::load`] and `.manage()`d into the Tauri runtime — it
/// is never returned to JS. The 32-byte key stays in host memory only (T-04-01): no DTO
/// ever carries it.
pub struct AppCtx {
    /// The 32-byte DPAPI-unwrapped signing key (host-memory only; never serialized).
    pub key: [u8; 32],
    /// The single base data dir (mirrors the guard's `NIGHTGUARD_DIR` resolution).
    pub data_dir: PathBuf,
    /// The four fixed paths a commit touches (config / sanctioned / guard.json / lock dir).
    pub paths: CommitPaths,
    /// Configured timezone name (filled from config in plan 03; advisory default for now).
    pub tz: String,
}

impl AppCtx {
    /// Resolve the data dir from `NIGHTGUARD_DIR`, build the five fixed paths, and load
    /// the `.guardkey` ONCE.
    ///
    /// Mirrors the guard's data-dir resolution (`nightguard_guard.ps1` lines 42-56):
    /// `NIGHTGUARD_DIR` env -> fixed filenames `config.yaml` / `config.sanctioned.yaml` /
    /// `guard.json` / `.nightguard.lock` / `.guardkey`. An unset/empty env var is
    /// [`IpcError::NotInitialized`] (fail-closed, never guess). The key is loaded via the
    /// single existing key path (`Scope::User`, `None` entropy) — no second path is added
    /// (T-04-02 / Pitfall 4).
    pub fn load() -> Result<AppCtx, IpcError> {
        let data_dir = match std::env::var("NIGHTGUARD_DIR") {
            Ok(d) if !d.trim().is_empty() => PathBuf::from(d),
            _ => return Err(IpcError::NotInitialized),
        };

        let paths = CommitPaths {
            config: data_dir.join("config.yaml"),
            sanctioned: data_dir.join("config.sanctioned.yaml"),
            guard_json: data_dir.join("guard.json"),
            lock_dir: data_dir.clone(),
        };

        // The ONE key path — Scope::User, None entropy (T-04-02). Never a second path.
        let key = load_or_create_key(&data_dir.join(".guardkey"))
            .map_err(|e| IpcError::Engine(e.to_string()))?;

        Ok(AppCtx {
            key,
            data_dir,
            paths,
            // Advisory default; plan 03 reads `config.timezone` and fills this.
            tz: "Europe/Amsterdam".to_string(),
        })
    }
}

/// The verified-state snapshot the Status view renders.
///
/// Timestamps are unix seconds (`i64`) — the engine/guard already speak unix seconds
/// (`GraceWindow.window_end`, `LedgerEntry.ntp_timestamp`), so the TS side formats them.
/// Field set is the locked contract (RESEARCH Pattern 3); the TS `interface StateDto` in
/// `src/main.ts` mirrors it field-for-field.
#[derive(Debug, Serialize, Clone)]
pub struct StateDto {
    // ── verification / fail-closed (D-03) ──
    pub config_verified: bool,
    pub state_verified: bool,
    pub maximal_lockout: bool,
    // ── lock status + countdown (UI-01 / D-06) — from lock_status (plan 02) ──
    pub locked: bool,
    pub grace_active: bool,
    pub boundary_unix: i64,
    pub boundary_kind: String,
    pub time_unverified: bool,
    // ── token meter (UI-02) — from quota::decide ──
    pub tokens_remaining: u8,
    pub weekly_spent: u8,
    pub next_reset_unix: i64,
    // ── grace availability (UI-02 / UI-03 / D-10) ──
    pub grace_available_today: bool,
    pub grace_remaining_secs: i64,
}

/// One per-field direction in a proposed edit.
#[derive(Debug, Serialize, Clone)]
pub struct FieldDirection {
    /// Dotted field path that changed (e.g. `curfew.start`).
    pub field: String,
    /// `"tighten"` | `"loosen"` | `"noop"`.
    pub direction: String,
}

/// Live classify + quota-preview result for the edit panel (UI-04).
#[derive(Debug, Serialize, Clone)]
pub struct ClassifyDto {
    /// Per-field tighten/loosen/noop verdicts.
    pub fields: Vec<FieldDirection>,
    /// Whether the proposed commit would be allowed (false at 0 tokens on a loosen).
    pub allowed: bool,
    /// Inline reason when `allowed == false` (the disabled-commit copy).
    pub reason: Option<String>,
    /// Whether committing this edit would spend a weekly token.
    pub costs_token: bool,
}

/// Read + re-verify the signed artifacts and derive the display state.
///
/// STUB (this plan): returns a fail-closed placeholder. Plan 03 fills the real
/// read/verify/derive path (T-04-03 — placeholder ships ONLY in this scaffold plan).
#[tauri::command]
pub fn get_state(state: tauri::State<'_, AppCtx>) -> Result<StateDto, IpcError> {
    // Touch the managed ctx so the wiring is exercised (key stays in-host, never returned).
    let _ = state.key.len();
    Ok(StateDto {
        config_verified: false,
        state_verified: false,
        // Placeholder is fail-closed: never look LESS locked than the guard (Pitfall 2).
        maximal_lockout: true,
        locked: true,
        grace_active: false,
        boundary_unix: 0,
        boundary_kind: "next_lock".to_string(),
        time_unverified: true,
        tokens_remaining: 0,
        weekly_spent: 3,
        next_reset_unix: 0,
        grace_available_today: false,
        grace_remaining_secs: 0,
    })
}

/// Classify a proposed edit + preview the quota verdict (no write).
///
/// STUB (this plan): returns an empty, allowed-noop preview. Plan 04 wraps
/// `classify::classify_change` + `quota::decide`.
#[tauri::command]
pub fn classify_change(old_yaml: String, new_yaml: String) -> Result<ClassifyDto, IpcError> {
    let _ = (old_yaml, new_yaml);
    Ok(ClassifyDto {
        fields: Vec::new(),
        allowed: true,
        reason: None,
        costs_token: false,
    })
}

/// Gate + atomically commit a sanctioned edit, then re-read the freshly-signed state.
///
/// STUB (this plan): not yet wired. Plan 05 wraps `commit::commit_change` (D-09 re-read).
#[tauri::command]
pub fn commit_change(
    new_yaml: String,
    state: tauri::State<'_, AppCtx>,
) -> Result<StateDto, IpcError> {
    let _ = (new_yaml, state.data_dir.as_path());
    Err(IpcError::NotInitialized)
}

/// Grant the once-daily timed grace window, then re-read the freshly-signed state.
///
/// STUB (this plan): not yet wired. Plan 05 wraps `grace::use_grace` (D-09 re-read).
#[tauri::command]
pub fn use_grace(state: tauri::State<'_, AppCtx>) -> Result<StateDto, IpcError> {
    let _ = state.tz.as_str();
    Err(IpcError::NotInitialized)
}
