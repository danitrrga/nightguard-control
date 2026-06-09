// Nightguard Control — Status view controller (frontend).
//
// The app is a READER (D-02/D-03): it only `invoke()`s; it never writes files or touches
// HMAC. Every label asserting lock state, tokens, or grace is derived SOLELY from a freshly
// re-verified `get_state` DTO (D-03) — never app-local optimism. Liveness is plugin-fs
// `watch()` of the data dir (re-reads on any change, D-05) plus a 1-second tick that
// re-renders ONLY the countdown digits and NEVER invents a state transition (D-05 / T-04-14).
//
// Import paths are Tauri v2: `invoke` from `@tauri-apps/api/core` (NOT v1 `/tauri`); `watch`
// from `@tauri-apps/plugin-fs`.
import { invoke } from "@tauri-apps/api/core";
import { watch } from "@tauri-apps/plugin-fs";

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

const WEEKLY_TOKENS = 3;

// The last re-verified DTO. The 1s tick reads this to re-render countdown digits only; it is
// only ever assigned by `refresh()` (a fresh `get_state`), never by the tick (D-05).
let last: StateDto | null = null;

// ── DOM handles ──
function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`missing #${id} in the shell DOM`);
  return node as T;
}

const statusView = () => el<HTMLElement>("status-view");
const statusWordEl = () => el<HTMLElement>("status-word");
const countdownEl = () => el<HTMLElement>("countdown");
const captionEl = () => el<HTMLElement>("status-caption");
const dividerEl = () => el<HTMLElement>("meter-divider");
const tokenMeterEl = () => el<HTMLElement>("token-meter");
const tokenCaptionEl = () => el<HTMLElement>("token-caption");
const graceCaptionEl = () => el<HTMLElement>("grace-caption");

// ── formatting helpers (advisory display only — D-04) ──
function nowUnix(): number {
  return Math.floor(Date.now() / 1000);
}

/** Format remaining seconds as HH:MM:SS (clamped at 00:00:00); tabular-nums prevents jitter. */
function fmtRemaining(secs: number): string {
  const s = Math.max(0, Math.floor(secs));
  const hh = Math.floor(s / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(hh)}:${pad(mm)}:${pad(ss)}`;
}

/** Local clock-time "HH:MM" of a unix instant (for "next lock at {time}"). */
function fmtClock(unix: number): string {
  const d = new Date(unix * 1000);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Local date "Mon DD" of a unix instant (for "resets Monday {date}"). */
function fmtDate(unix: number): string {
  const d = new Date(unix * 1000);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

// ── render ──

/**
 * Full render from a freshly re-verified DTO (D-03). Derives the status word, the hero
 * countdown, the 3-dot token meter, and the grace / verify / time captions. The `!state_verified`
 * (or maximal_lockout) branch shows the fully-locked "State unverified" copy — never optimism.
 */
function render(s: StateDto): void {
  const verifyFail = !s.state_verified || s.maximal_lockout;
  statusView().classList.toggle("verify-fail", verifyFail);

  // Status word + caption.
  let word: string;
  let caption = "";
  let captionWarn = false;

  if (verifyFail) {
    // Fail-closed: the guard is treating the user as fully locked until the app re-syncs.
    word = "State unverified";
    caption =
      "The signed state failed HMAC verification. The guard is treating you as fully locked until the app re-syncs. Open the edit panel to re-sign.";
    captionWarn = true;
  } else if (s.locked && s.grace_active) {
    word = "🌙 LOCKED · grace";
  } else if (s.locked) {
    word = "🌙 LOCKED";
  } else {
    word = "OPEN";
    caption = `next lock at ${fmtClock(s.boundary_unix)}`;
  }

  statusWordEl().textContent = word;

  // Time-unverified caveat is advisory (D-04) — append only when state itself verified.
  if (!verifyFail && s.time_unverified) {
    const caveat =
      "Time unverified — the countdown is advisory; the guard re-checks with its own clock.";
    caption = caption ? `${caption} · ${caveat}` : caveat;
  }

  captionEl().textContent = caption;
  captionEl().classList.toggle("warn", captionWarn);

  // Hero countdown (digits handled by the shared tick path).
  renderCountdownOnly(s);

  // 3-dot weekly token meter: tokens_remaining filled (accent) of 3.
  const remaining = Math.max(0, Math.min(WEEKLY_TOKENS, s.tokens_remaining));
  const meter = tokenMeterEl();
  meter.replaceChildren();
  for (let i = 0; i < WEEKLY_TOKENS; i++) {
    const dot = document.createElement("span");
    dot.className = i < remaining ? "token-dot filled" : "token-dot";
    meter.appendChild(dot);
  }
  tokenCaptionEl().textContent = `${remaining} of 3 tokens · resets Monday ${fmtDate(
    s.next_reset_unix,
  )}`;

  // Grace caption (UI-SPEC line 153).
  let grace: string;
  if (!s.locked) {
    grace = "+8 unavailable (not locked)";
  } else if (s.grace_available_today) {
    grace = "+8 available today";
  } else {
    grace = "+8 used today";
  }
  graceCaptionEl().textContent = grace;

  dividerEl().style.display = "";
}

/**
 * Re-render ONLY the countdown digits from a DTO's boundary (D-05). NEVER recomputes lock
 * state or touches the status word — a passed boundary shows 00:00:00 and waits for the next
 * watch-driven `refresh()` (T-04-14). This is the only thing the 1s tick calls.
 */
function renderCountdownOnly(s: StateDto): void {
  const remaining = s.boundary_unix - nowUnix();
  countdownEl().textContent = fmtRemaining(remaining);
}

/** Render the UI-SPEC empty state when no signed config exists yet. */
function renderEmpty(): void {
  statusView().classList.remove("verify-fail");
  statusWordEl().textContent = "No signed config yet";
  countdownEl().textContent = "--:--:--";
  captionEl().classList.remove("warn");
  captionEl().textContent =
    "Nightguard hasn't been initialized on this machine. Run the app's setup to generate your signing key and first sanctioned config.";
  tokenMeterEl().replaceChildren();
  tokenCaptionEl().textContent = "";
  graceCaptionEl().textContent = "";
  dividerEl().style.display = "none";
}

// ── liveness ──

/** Re-read the re-verified state and re-render. The single place `last` is assigned (D-03/D-09). */
async function refresh(): Promise<void> {
  try {
    const s = await invoke<StateDto>("get_state");
    last = s;
    render(s);
  } catch (err) {
    // `NotInitialized` (no signed config / no data dir) surfaces as the empty state; any other
    // error keeps the last good render rather than asserting a false transition.
    const msg = String(err);
    if (msg.includes("not initialized")) {
      last = null;
      renderEmpty();
    } else {
      console.error("get_state failed:", err);
    }
  }
}

async function startWatch(): Promise<void> {
  try {
    const dir = await invoke<string>("data_dir");
    // Debounced: any change to config.yaml / guard.json (guard revert, hand-edit, fresh sign)
    // re-reads verified truth (D-05). The callback always re-invokes get_state — never an
    // optimistic local mutation.
    await watch(dir, () => void refresh(), { delayMs: 250, recursive: false });
  } catch (err) {
    // If the watcher can't be established (dir unknown / outside fs:scope), the 1s tick + the
    // load-time refresh still keep the display advisory-live; log and degrade gracefully.
    console.warn("data-dir watch unavailable; relying on tick + load fetch:", err);
  }
}

async function init(): Promise<void> {
  await refresh();
  await startWatch();
  // 1-second tick: re-render ONLY the countdown digits from the last verified DTO. It never
  // calls invoke and never recomputes `locked` (D-05 / T-04-14).
  setInterval(() => {
    if (last) renderCountdownOnly(last);
  }, 1000);
}

window.addEventListener("DOMContentLoaded", () => {
  void init();
});
