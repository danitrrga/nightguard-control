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

use chrono::Utc;
use serde::Serialize;

use mutation_engine::classify::{self, Direction};
use mutation_engine::commit::{self, CommitPaths};
use mutation_engine::grace;
use mutation_engine::lock_status::{config_timezone, lock_status};
use mutation_engine::ntp::{SntpTrueTime, TrueTime};
use mutation_engine::quota;
use mutation_engine::state::GuardState;
use trust_kernel::canon::canonicalize_bytes;
use trust_kernel::hmac::{verify_bytes, verify_tag_hex};
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
    /// An HMAC re-verification failed (fail-closed read path). Reserved contract surface:
    /// `get_state` surfaces verification failure IN the DTO (`config_verified`/`state_verified`
    /// false + `maximal_lockout`) rather than erroring, so the UI can still render the
    /// worst-cased state; this variant stays for callers that prefer a hard error.
    #[allow(dead_code)]
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
    /// The single base data dir (mirrors the guard's `NIGHTGUARD_DIR` resolution). Surfaced to
    /// the frontend by the `data_dir` command so the webview can target `plugin-fs` `watch()`
    /// at the exact enforced directory (D-05); also the `fs:scope` watch target.
    pub data_dir: PathBuf,
    /// The four fixed paths a commit touches (config / sanctioned / guard.json / lock dir).
    pub paths: CommitPaths,
    /// Fallback timezone name used only when the live `config.yaml` cannot be read. The real
    /// week/grace day-math reads `timezone` from the verified config per call (WR-06), so this
    /// is just the startup default for the unreadable-config edge.
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
            // Fallback default only (WR-06): the live week/grace day-math reads `timezone` from the
            // verified config per call via `config_timezone`; this is used solely when that read fails.
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

/// The maximum loosening commits allowed per week (mirrors `quota::WEEKLY_TOKENS`); used to
/// derive `tokens_remaining` from the effective spent count.
const WEEKLY_TOKENS: u8 = 3;

/// Decode a 64-char hex HMAC string into a fixed 32-byte tag, or `None` if malformed.
fn hex_to_tag32(hex_str: &str) -> Option<[u8; 32]> {
    let bytes = hex::decode(hex_str.trim()).ok()?;
    <[u8; 32]>::try_from(bytes.as_slice()).ok()
}

/// Read both signed artifacts from disk and assemble the re-verified [`StateDto`].
///
/// This is the ONE place the read → re-verify → derive → worst-case path lives, so
/// `get_state`, `commit_change`, and `use_grace` all return identically-verified truth and
/// the worst-casing parity (the guard's `nightguard_guard.ps1:217-222` substitution) is
/// applied in exactly one location (T-04-08 / T-04-09).
///
/// Fail-closed contract:
///   - missing `config.yaml` or `guard.json` -> [`IpcError::NotInitialized`].
///   - `config.yaml` tampered (config_hmac mismatch) -> `config_verified=false`,
///     `maximal_lockout=true`.
///   - `guard.json` tampered (state_hmac mismatch) -> WORST-CASE the token/grace fields
///     exactly like the guard: `weekly_spent=3, tokens_remaining=0,
///     grace_available_today=false, grace_active=false`, plus `maximal_lockout=true`.
///   - app-side time is advisory only (D-04): `time_unverified` is always `true` and NO
///     blocking SNTP call happens on this read path (the guard re-validates true time).
fn build_state_dto(ctx: &AppCtx) -> Result<StateDto, IpcError> {
    // (1) Read both signed artifacts. Either absent => not initialized (never an optimistic DTO).
    let raw_config = match std::fs::read(&ctx.paths.config) {
        Ok(bytes) => bytes,
        Err(_) => return Err(IpcError::NotInitialized),
    };
    let raw_guard = match std::fs::read_to_string(&ctx.paths.guard_json) {
        Ok(s) => s,
        Err(_) => return Err(IpcError::NotInitialized),
    };

    // (2) Deserialize guard.json into the signed-state model (serde error -> engine message).
    let gs: GuardState = serde_json::from_str(&raw_guard)
        .map_err(|e| IpcError::Engine(format!("guard.json parse: {e}")))?;

    // (3) Re-verify config_hmac: canonicalize the RAW config bytes (the exact form it was
    //     signed over) and constant-time verify against the stored tag. NEVER `==` on tags.
    let canon = canonicalize_bytes(&raw_config);
    let config_verified = match hex_to_tag32(&gs.config_hmac) {
        Some(tag) => verify_bytes(&ctx.key, &canon, &tag),
        None => false,
    };

    // (4) Re-verify state_hmac via the locked A3 recipe (recompute over the blanked clone),
    //     then CONSTANT-TIME compare the recomputed tag against the stored one. The two tags
    //     are hex strings, so compare them with the kernel's `verify_tag_hex` (decodes + `subtle`
    //     ConstantTimeEq) — NEVER `String ==`, which is a timing side-channel explicitly
    //     forbidden by the project's "What NOT to Use". A malformed stored hex fails closed.
    let state_verified = verify_tag_hex(&gs.compute_state_hmac(&ctx.key), &gs.state_hmac);

    // (5) Advisory now: app-side time is never authoritative (D-04). No SNTP on this hot path.
    let now_utc = Utc::now();
    let now_secs = now_utc.timestamp();
    let config_yaml = String::from_utf8_lossy(&raw_config).to_string();

    // WR-06: drive the week/grace day-math from the SAME tz `lock_status` reads off this config,
    // not the hardcoded `ctx.tz`. Otherwise the lock display and the quota/grace day rollover
    // disagree on the zone (the Monday reset / "grace used today" would compute in the wrong
    // local instant). `config_timezone` defaults to UTC fail-safe, matching `lock_status::parse_tz`.
    let tz = config_timezone(&config_yaml);

    // (6) Curfew lock verdict + boundary from the pure evaluator over the (advisory) now.
    let ls = lock_status(&config_yaml, now_utc);

    // (7) Pure read of effective spent / next reset (empty diff = no proposed change).
    let decision = quota::decide(&[], &gs, now_utc, &tz);

    let maximal_lockout = !config_verified || !state_verified;

    // (8) Assemble. On ANY state-verify failure, worst-case the token/grace fields to mirror
    //     the guard — the app must never look LESS locked than the guard enforces.
    if !state_verified {
        return Ok(StateDto {
            config_verified,
            state_verified,
            maximal_lockout: true,
            // Lock/boundary still come from lock_status (a tampered guard.json never relaxes
            // the curfew window), but the token/grace surface is worst-cased.
            locked: ls.locked,
            grace_active: false,
            boundary_unix: ls.boundary_unix,
            boundary_kind: ls.boundary_kind,
            time_unverified: true,
            tokens_remaining: 0,
            weekly_spent: WEEKLY_TOKENS, // 3 — the guard's worst-case substitution
            next_reset_unix: decision.next_reset.timestamp(),
            grace_available_today: false,
            grace_remaining_secs: 0,
        });
    }

    // (9) Verified state: real token meter + grace overlay.
    let weekly_spent = decision.effective_spent;
    let tokens_remaining = WEEKLY_TOKENS.saturating_sub(weekly_spent);

    // `grace_available_today` mirrors the guard (`$graceUsed = ($null -ne grace)`): grace is
    // available today iff there is no recorded window, or the recorded window is for a prior
    // day (advisory: compared against today's date in the configured tz).
    // WR-01: an unresolvable "today" must fail CLOSED — never report grace as available again
    // off the back of an empty-string date comparing unequal to a real recorded window.
    let grace_available_today = match (&gs.grace, today_in_tz(&tz, now_secs)) {
        (None, _) => true,
        (Some(_), None) => false, // cannot resolve today -> assume grace already used (fail-closed)
        (Some(g), Some(today)) => g.date != today,
    };

    // Overlay an ACTIVE grace window on top of lock_status: if a window is present and not yet
    // expired (window_end in the advisory future), the next boundary is the grace end.
    let (grace_active, boundary_unix, boundary_kind, grace_remaining_secs) = match &gs.grace {
        Some(g) if g.window_end > now_secs => (
            true,
            g.window_end,
            "grace_end".to_string(),
            g.window_end - now_secs,
        ),
        _ => (ls.grace_active, ls.boundary_unix, ls.boundary_kind, 0),
    };

    Ok(StateDto {
        config_verified,
        state_verified,
        maximal_lockout,
        locked: ls.locked,
        grace_active,
        boundary_unix,
        boundary_kind,
        time_unverified: true,
        tokens_remaining,
        weekly_spent,
        next_reset_unix: decision.next_reset.timestamp(),
        grace_available_today,
        grace_remaining_secs,
    })
}

/// The advisory "YYYY-MM-DD" date of `now_secs` in the configured tz (defensive UTC default,
/// mirroring the engine's `parse_tz`/`true_day` discipline — never panics on a bad tz name).
///
/// Returns `None` when the instant cannot be resolved to a single local date (a non-`Single`
/// `timestamp_opt` result). WR-01: callers MUST treat `None` as fail-closed — an unresolvable
/// "today" must never become an empty string that compares unequal to a recorded grace window
/// and thereby re-arms the once-daily grace.
fn today_in_tz(tz_name: &str, now_secs: i64) -> Option<String> {
    use chrono::TimeZone;
    let tz: chrono_tz::Tz = tz_name.parse().unwrap_or(chrono_tz::UTC);
    tz.timestamp_opt(now_secs, 0)
        .single()
        .map(|dt| dt.format("%Y-%m-%d").to_string())
}

/// Read the current `GuardState` from `guard.json`, mapping absence/parse failures to
/// [`IpcError`]. Used by `classify_change` (which needs the live state for the quota preview).
fn read_guard_state(ctx: &AppCtx) -> Result<GuardState, IpcError> {
    let raw = std::fs::read_to_string(&ctx.paths.guard_json)
        .map_err(|_| IpcError::NotInitialized)?;
    serde_json::from_str(&raw).map_err(|e| IpcError::Engine(format!("guard.json parse: {e}")))
}

/// Map an engine [`Direction`] to the locked DTO string (`"tighten" | "loosen" | "noop"`).
fn direction_str(d: Direction) -> &'static str {
    match d {
        Direction::Tighten => "tighten",
        Direction::Loosen => "loosen",
        Direction::Noop => "noop",
    }
}

/// Read + re-verify the signed artifacts and derive the display state (D-03).
///
/// Re-reads `config.yaml` + `guard.json` from the resolved data dir, re-verifies BOTH HMACs
/// via the kernel (`verify_bytes` for config, `compute_state_hmac` for state), and derives
/// the full [`StateDto`] through the shared [`build_state_dto`] helper — worst-casing exactly
/// like the guard on any verification failure. Uninitialized (either file absent) maps to
/// [`IpcError::NotInitialized`], which drives the empty state in the UI.
#[tauri::command]
pub fn get_state(state: tauri::State<'_, AppCtx>) -> Result<StateDto, IpcError> {
    build_state_dto(&state)
}

/// Surface the absolute resolved data dir to the frontend so it can target `plugin-fs`
/// `watch()` at the exact directory the guard enforces (D-05 liveness).
///
/// This is read-only and carries no secret (the key never leaves `AppCtx`). It exists because
/// the data dir is resolved at startup from `NIGHTGUARD_DIR` and the webview otherwise has no
/// way to know the absolute path to watch (Pitfall 5). The returned path also matches the
/// `fs:scope` allow entry in `capabilities/default.json`.
#[tauri::command]
pub fn data_dir(state: tauri::State<'_, AppCtx>) -> String {
    state.data_dir.to_string_lossy().into_owned()
}

/// Surface the current `config.yaml` text to the frontend so the Edit view can build the
/// `old`/`new` YAML pair for `classify_change` / `commit_change`.
///
/// Read-only and carries no secret — it returns the same human-readable config the guard reads
/// (re-verification of its HMAC happens server-side in `get_state` / `commit_change`). The Edit
/// view loads this once to seed the per-field inputs and to compose the edited YAML (the
/// classifier reads individual fields via yamlpath, so a per-field line edit is sufficient). On
/// an uninitialized data dir (no `config.yaml`) it maps to [`IpcError::NotInitialized`].
#[tauri::command]
pub fn read_config(state: tauri::State<'_, AppCtx>) -> Result<String, IpcError> {
    std::fs::read_to_string(&state.paths.config).map_err(|_| IpcError::NotInitialized)
}

/// Classify a proposed edit + preview the quota verdict (no write).
///
/// Wraps `classify::classify_change` for the per-field tighten/loosen/noop directions and
/// `quota::decide` for the allow/reason/cost preview so the edit panel can disable-with-reason
/// at 0 tokens (UI-04). Read-only: no file is written here.
///
/// The managed `state: tauri::State<AppCtx>` is injected by the Tauri runtime (it does NOT
/// change the JS `invoke('classify_change', { oldYaml, newYaml })` call shape); `decide` needs
/// the live `GuardState` + configured tz, so the body reads them — a sanctioned body-fill.
#[tauri::command]
pub fn classify_change(
    old_yaml: String,
    new_yaml: String,
    state: tauri::State<'_, AppCtx>,
) -> Result<ClassifyDto, IpcError> {
    // Per-field directions (engine error -> IpcError::Engine via From).
    let dirs = classify::classify_change(&old_yaml, &new_yaml)?;

    // Quota preview against the live signed state (advisory now for the week math). WR-06: the
    // week-math tz comes from the live config, not the hardcoded `state.tz`, so the preview's
    // Monday-reset boundary agrees with `lock_status`.
    let gs = read_guard_state(&state)?;
    let tz = config_timezone(&old_yaml);
    let decision = quota::decide(&dirs, &gs, Utc::now(), &tz);

    let fields = dirs
        .iter()
        .map(|(field, dir)| FieldDirection {
            field: field.clone(),
            direction: direction_str(*dir).to_string(),
        })
        .collect();

    Ok(ClassifyDto {
        fields,
        allowed: decision.allowed,
        reason: decision.reason,
        costs_token: decision.costs_token,
    })
}

/// Gate + atomically commit a sanctioned edit, then re-read the freshly-signed state.
///
/// Classifies `new_yaml` against the live `config.yaml`, re-checks the quota decision in-command
/// (defense in depth, mirroring `commit.rs:148` — a 0-token loosen never reaches the writer),
/// obtains TRUE NTP time fail-closed for the ledger, then commits via the engine's ONLY
/// sanctioned writer `commit::commit_change` (ordered, fd-locked — never hand-rolled). After the
/// commit it RE-READS the freshly-signed state (D-09) through the shared `build_state_dto` path,
/// so the returned DTO is verified truth, not an optimistic local mutation.
#[tauri::command]
pub fn commit_change(
    new_yaml: String,
    state: tauri::State<'_, AppCtx>,
) -> Result<StateDto, IpcError> {
    // The current live config is the classifier's `old` side — read its RAW bytes so we can
    // re-verify them against the signed tag before trusting them as the token-charging baseline.
    let raw_old = std::fs::read(&state.paths.config).map_err(|_| IpcError::NotInitialized)?;
    let gs = read_guard_state(&state)?;

    // WR-05: the `old` side MUST be verified-sanctioned, not whatever is on disk. If `config.yaml`
    // was hand-edited out of band (the exact threat this product counters), classifying the
    // proposed change against the TAMPERED file lets an actual loosen-vs-sanctioned read as
    // noop/tighten and commit for free. Re-verify the on-disk bytes against `gs.config_hmac`
    // (same canonicalize + constant-time verify path as `build_state_dto`); refuse on mismatch.
    let canon_old = canonicalize_bytes(&raw_old);
    let old_verified = match hex_to_tag32(&gs.config_hmac) {
        Some(tag) => verify_bytes(&state.key, &canon_old, &tag),
        None => false,
    };
    if !old_verified {
        return Err(IpcError::Engine(
            "config.yaml does not match the signed baseline (tampered or unverified) — \
             commit refused; re-sync before editing"
                .to_string(),
        ));
    }

    let old_yaml = String::from_utf8_lossy(&raw_old).to_string();

    // Classify + decide against the live signed state. WR-06: the week-math tz is read from the
    // live config (the same zone `lock_status` uses), not the hardcoded `state.tz`.
    let dirs = classify::classify_change(&old_yaml, &new_yaml)?;
    let tz = config_timezone(&old_yaml);
    let decision = quota::decide(&dirs, &gs, Utc::now(), &tz);

    // Defense in depth: a disallowed (0-token loosen) decision NEVER reaches the writer.
    if !decision.allowed {
        return Err(IpcError::Engine(
            decision.reason.unwrap_or_else(|| "commit blocked".to_string()),
        ));
    }

    // TRUE time for the ledger — fail-closed on NTP failure (no system-clock fallback).
    let true_now = SntpTrueTime::default()
        .now()
        .map(|t| t.unix_secs)
        .map_err(|_| IpcError::Engine("ntp unreachable: cannot verify true time".to_string()))?;

    // The ONLY write path: the engine's ordered, fd-locked, re-signing commit (RULE-06 / GARD-05).
    commit::commit_change(&state.paths, &new_yaml, &dirs, &decision, &state.key, true_now)?;

    // Re-read the freshly-signed state (D-09) — verified truth, never an optimistic echo.
    build_state_dto(&state)
}

/// Grant the once-daily timed grace window, then re-read the freshly-signed state.
///
/// Wraps the engine's `grace::use_grace`, which (inside the same commit lock) sources TRUE NTP
/// time and refuses fail-closed on `NtpUnreachable` / `GraceAlreadyUsedToday` — both fold to
/// [`IpcError`] via `From<MutationError>`. On success it RE-READS the freshly-signed state (D-09)
/// through the shared `build_state_dto` path, so the returned DTO reflects the active window as
/// verified truth (`grace_active=true`, `boundary_kind="grace_end"`), never an optimistic echo.
#[tauri::command]
pub fn use_grace(state: tauri::State<'_, AppCtx>) -> Result<StateDto, IpcError> {
    // WR-06: the grace day-math tz must match the read-path tz `build_state_dto` uses to compare
    // `grace.date` against "today", or a window granted near local midnight could be recorded under
    // a date the read path then reads as a different day. Read it from the live config (UTC
    // fail-safe), not the hardcoded `state.tz`. A missing/unreadable config falls back to `state.tz`.
    let tz = std::fs::read_to_string(&state.paths.config)
        .map(|c| config_timezone(&c))
        .unwrap_or_else(|_| state.tz.clone());

    // Grant via the engine (NtpUnreachable / GraceAlreadyUsedToday -> IpcError via From).
    grace::use_grace(&state.paths, &SntpTrueTime::default(), &tz, &state.key)?;

    // Re-read the freshly-signed state (D-09) — the overlay surfaces the active grace window.
    build_state_dto(&state)
}
