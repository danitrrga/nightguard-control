// Nightguard Control — frontend entry (scaffold).
//
// This plan wires only the load-time invoke of `get_state` and logs the result; the real
// Status view render lands in plan 03. Import path is v2 `@tauri-apps/api/core` (NOT v1
// `/tauri`).
import { invoke } from "@tauri-apps/api/core";

/**
 * The shared IPC contract — mirrors `StateDto` in src-tauri/src/commands.rs field-for-field.
 * Timestamps are unix seconds (the TS side does its own formatting).
 */
export interface StateDto {
  // verification / fail-closed (D-03)
  config_verified: boolean;
  state_verified: boolean;
  maximal_lockout: boolean;
  // lock status + countdown (UI-01 / D-06)
  locked: boolean;
  grace_active: boolean;
  boundary_unix: number;
  boundary_kind: string;
  time_unverified: boolean;
  // token meter (UI-02)
  tokens_remaining: number;
  weekly_spent: number;
  next_reset_unix: number;
  // grace availability (UI-02 / UI-03 / D-10)
  grace_available_today: boolean;
  grace_remaining_secs: number;
}

async function init(): Promise<void> {
  try {
    const state = await invoke<StateDto>("get_state");
    // Placeholder: plan 03 renders this; for now prove the IPC boundary works.
    console.log("get_state ->", state);
  } catch (err) {
    console.error("get_state failed:", err);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  void init();
});
