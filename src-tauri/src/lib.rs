//! Nightguard Control — Tauri v2 host library.
//!
//! `run()` resolves the [`AppCtx`] (data dir + key + commit paths), `.manage()`s it into
//! the runtime, registers the plugin-fs watcher plugin, and wires the four IPC commands.
//! The Rust host is the sole writer/signer (D-02): the key lives in `AppCtx` in-host and
//! never crosses the `invoke` boundary.

mod commands;

use commands::{
    classify_change, commit_change, data_dir, get_state, read_config, use_grace, AppCtx,
};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Fail-closed: if the data dir / key can't be resolved we refuse to start rather than
    // run a window against an unknown state (NIGHTGUARD_DIR unset -> NotInitialized).
    let ctx = AppCtx::load().expect("failed to initialize AppCtx (is NIGHTGUARD_DIR set?)");

    // WR-02: the data dir is resolved at runtime from NIGHTGUARD_DIR (an arbitrary absolute path),
    // but the static `fs:scope` allow-list can only name fixed locations ($HOME/.nightguard,
    // $APPDATA/nightguard). When the operator points NIGHTGUARD_DIR elsewhere (the documented
    // LifeOS-wired case), the frontend `watch()` would be denied and the liveness watcher (D-05)
    // would silently never arm. Extend the fs scope to the ACTUAL resolved dir at setup so the
    // watch is authorized wherever the dir lives — the watcher then reflects guard reverts /
    // hand-edits as designed, instead of degrading to "no changes seen".
    let watch_dir = ctx.data_dir.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .setup(move |app| {
            use tauri_plugin_fs::FsExt;
            // Best-effort: a scope-extension failure must not crash startup. If it fails the
            // frontend still surfaces a loud watch-setup error (main.ts) rather than silently
            // pretending liveness is armed.
            if let Err(e) = app.fs_scope().allow_directory(&watch_dir, true) {
                eprintln!(
                    "warning: could not extend fs scope to {}: {e}",
                    watch_dir.display()
                );
            }
            Ok(())
        })
        .manage(ctx)
        .invoke_handler(tauri::generate_handler![
            get_state,
            data_dir,
            read_config,
            classify_change,
            commit_change,
            use_grace
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
