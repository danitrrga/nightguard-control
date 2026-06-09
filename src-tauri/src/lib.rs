//! Nightguard Control — Tauri v2 host library (scaffold placeholder).
//!
//! Task 2 replaces this with the real `run()` Builder, `.manage(AppCtx)`, and the
//! `generate_handler!` registration of the four IPC commands.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
