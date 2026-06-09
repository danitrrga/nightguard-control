//! Nightguard Control — Tauri v2 host library.
//!
//! `run()` resolves the [`AppCtx`] (data dir + key + commit paths), `.manage()`s it into
//! the runtime, registers the plugin-fs watcher plugin, and wires the four IPC commands.
//! The Rust host is the sole writer/signer (D-02): the key lives in `AppCtx` in-host and
//! never crosses the `invoke` boundary.

mod commands;

use commands::{classify_change, commit_change, get_state, use_grace, AppCtx};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Fail-closed: if the data dir / key can't be resolved we refuse to start rather than
    // run a window against an unknown state (NIGHTGUARD_DIR unset -> NotInitialized).
    let ctx = AppCtx::load().expect("failed to initialize AppCtx (is NIGHTGUARD_DIR set?)");

    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .manage(ctx)
        .invoke_handler(tauri::generate_handler![
            get_state,
            classify_change,
            commit_change,
            use_grace
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
