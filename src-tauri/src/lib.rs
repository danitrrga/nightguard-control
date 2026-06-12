//! Nightguard Control — Tauri v2 host library.
//!
//! `run()` resolves the [`AppCtx`] (data dir + key + commit paths), `.manage()`s it into
//! the runtime, registers the plugin-fs watcher plugin, builds the system tray (time-remaining
//! at a glance), and wires the IPC commands. The Rust host is the sole writer/signer (D-02): the
//! key lives in `AppCtx` in-host and never crosses the `invoke` boundary.

mod commands;
mod tray_badge;

use commands::{
    classify_change, commit_change, data_dir, get_state, read_config, use_grace, AppCtx,
};

use tauri::image::Image;
use tauri::menu::{MenuBuilder, MenuItem, MenuItemBuilder};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Manager, WindowEvent};

/// Tray handles the frontend updates as the countdown ticks: the disabled "status" menu line and
/// the brand icon (restored when there is no count to badge). Stored in managed state so
/// `set_tray_status` can reach them; the tooltip is updated by tray id.
struct TrayHandles {
    status: MenuItem<tauri::Wry>,
    default_icon: Image<'static>,
}

/// Push the current "time remaining" into the tray: the menu status line, the hover tooltip, and
/// the icon badge (`badge` text tinted by `state`; empty `badge` restores the plain brand icon).
/// Called from the frontend tick so the tray reflects the live curfew countdown at a glance.
/// Advisory display only — the guard remains the source of truth; this never writes state.
#[tauri::command]
fn set_tray_status(
    app: tauri::AppHandle,
    tray: tauri::State<'_, TrayHandles>,
    menu_line: String,
    tooltip: String,
    badge: String,
    state: String,
) -> Result<(), String> {
    tray.status.set_text(&menu_line).map_err(|e| e.to_string())?;
    if let Some(t) = app.tray_by_id("main") {
        let _ = t.set_tooltip(Some(&tooltip));
        // Badge the icon with the count when there is one; otherwise show the plain brand mark.
        let icon = if badge.is_empty() {
            Some(tray.default_icon.clone())
        } else {
            tray_badge::render_badge(&badge, &state).or_else(|| Some(tray.default_icon.clone()))
        };
        if let Some(img) = icon {
            let _ = t.set_icon(Some(img));
        }
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Fail-closed: if the data dir / key can't be resolved we refuse to start rather than
    // run a window against an unknown state (NIGHTGUARD_DIR unset -> NotInitialized).
    let ctx = AppCtx::load().expect("failed to initialize AppCtx (is NIGHTGUARD_DIR set?)");

    // WR-02: the data dir is resolved at runtime from NIGHTGUARD_DIR (an arbitrary absolute path),
    // but the static `fs:scope` allow-list can only name fixed locations. Extend the fs scope to
    // the ACTUAL resolved dir at setup so the frontend `watch()` is authorized wherever it lives.
    let watch_dir = ctx.data_dir.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .setup(move |app| {
            use tauri_plugin_fs::FsExt;
            if let Err(e) = app.fs_scope().allow_directory(&watch_dir, true) {
                eprintln!(
                    "warning: could not extend fs scope to {}: {e}",
                    watch_dir.display()
                );
            }

            // ── System tray: time-remaining at a glance (uses the bundled brand icon) ──
            // The status line starts neutral; the frontend pushes the live countdown via
            // set_tray_status as the curfew clock ticks (tooltip on hover + menu status line).
            let status = MenuItemBuilder::with_id("status", "Nightguard — starting…")
                .enabled(false)
                .build(app)?;
            let show = MenuItemBuilder::with_id("show", "Show Nightguard").build(app)?;
            let quit = MenuItemBuilder::with_id("quit", "Quit Nightguard").build(app)?;
            let menu = MenuBuilder::new(app).items(&[&status, &show, &quit]).build()?;

            let icon = app
                .default_window_icon()
                .cloned()
                .expect("bundled default window icon");
            // Owned 'static copy so the badge path can restore the plain brand icon at runtime.
            let default_icon =
                Image::new_owned(icon.rgba().to_vec(), icon.width(), icon.height());

            let _tray = TrayIconBuilder::with_id("main")
                .icon(icon)
                .tooltip("Nightguard")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                })
                .build(app)?;

            app.manage(TrayHandles {
                status,
                default_icon,
            });

            // The window is created hidden (tauri.conf `visible: false`) so the Run-key login
            // launch (`--hidden`) stays tucked in the tray with no flash. A manual launch (no flag)
            // shows it once ready; the tray's Show / left-click reveal it thereafter.
            if !std::env::args().any(|a| a == "--hidden") {
                if let Some(w) = app.get_webview_window("main") {
                    let _ = w.show();
                    let _ = w.set_focus();
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            // Close-to-tray: this is a background curfew companion. Closing the window hides it
            // (the tray countdown/badge stays live) instead of quitting — quit is via the tray menu.
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .manage(ctx)
        .invoke_handler(tauri::generate_handler![
            get_state,
            data_dir,
            read_config,
            classify_change,
            commit_change,
            use_grace,
            set_tray_status
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
