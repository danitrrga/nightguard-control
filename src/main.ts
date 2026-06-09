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

/**
 * Live classify + quota-preview result for the edit panel (UI-04). Mirrors `ClassifyDto` in
 * src-tauri/src/commands.rs field-for-field. `fields` carries one verdict per classified field.
 */
export interface ClassifyDto {
  fields: { field: string; direction: string }[]; // direction: "tighten" | "loosen" | "noop"
  allowed: boolean;
  reason: string | null;
  costs_token: boolean;
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
const graceBtnEl = () => el<HTMLButtonElement>("grace-btn");

// Edit view handles.
const editView = () => el<HTMLElement>("edit-view");
const railStatusEl = () => el<HTMLButtonElement>("rail-status");
const railEditEl = () => el<HTMLButtonElement>("rail-edit");
const fieldEnabledEl = () => el<HTMLInputElement>("field-enabled");
const fieldStartEl = () => el<HTMLInputElement>("field-start");
const fieldEndEl = () => el<HTMLInputElement>("field-end");
const commitBtnEl = () => el<HTMLButtonElement>("commit-btn");
const editReasonEl = () => el<HTMLElement>("edit-reason");
const fbEl = (field: string) => el<HTMLElement>(`fb-${field}`);

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
  } else if (s.boundary_kind === "none") {
    // CR-02: curfew disabled, or today is `off` and we do not scan future days — there is no
    // resolvable upcoming lock. Show "no upcoming lock" rather than a `00:00:00` countdown.
    word = "OPEN";
    caption = "no upcoming lock";
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

  // "+8 minutes" button: enabled IFF locked && grace_available_today (D-10). The `disabled`
  // attribute makes the gate real (not styling-only); `.enabled` fills it accent only when on.
  const graceEnabled = s.locked && s.grace_available_today;
  const graceBtn = graceBtnEl();
  graceBtn.disabled = !graceEnabled;
  graceBtn.classList.toggle("enabled", graceEnabled);

  dividerEl().style.display = "";
}

/**
 * Re-render ONLY the countdown digits from a DTO's boundary (D-05). NEVER recomputes lock
 * state or touches the status word — a passed boundary shows 00:00:00 and waits for the next
 * watch-driven `refresh()` (T-04-14). This is the only thing the 1s tick calls.
 */
function renderCountdownOnly(s: StateDto): void {
  // CR-02: "none" is the no-upcoming-lock sentinel (curfew disabled / today off) — render a
  // neutral dash instead of a frozen 00:00:00 countdown derived from a sentinel boundary.
  if (s.boundary_kind === "none") {
    countdownEl().textContent = "--:--:--";
    return;
  }
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
  graceBtnEl().disabled = true;
  graceBtnEl().classList.remove("enabled");
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
    // WR-02: a watch-setup failure is a real liveness degradation (D-05 never arms — guard
    // reverts / hand-edits won't reflect until a manual refresh), NOT "no changes yet". Make it
    // LOUD rather than a silent console.warn so a mis-scoped data dir is distinguishable. The 1s
    // tick + load-time refresh still keep the display advisory-live, but the user is told liveness
    // is off. (The Rust host also extends the fs scope to the resolved dir at setup; this caption
    // covers any remaining failure path.)
    console.warn("data-dir watch unavailable; relying on tick + load fetch:", err);
    const caption = captionEl();
    const warn = "Live updates unavailable — changes may not appear until you reopen the app.";
    caption.textContent = caption.textContent ? `${caption.textContent} · ${warn}` : warn;
    caption.classList.add("warn");
  }
}

// ── "+8 minutes" grace grant (UI-03 / D-10) ──
//
// Enabled ONLY during an active lock when grace is available (the enable rule lives in render()).
// On press it grants the once-daily window via use_grace, then re-renders the countdown to the
// grace-window end from the returned re-verified StateDto (D-09 — grace_active=true,
// boundary_kind="grace_end"). NTP-unreachable / already-used errors surface non-punitively and
// leave the displayed state unchanged. No optimistic grace_active flip before the command returns.
async function onGrace(): Promise<void> {
  try {
    const s = await invoke<StateDto>("use_grace");
    last = s;
    render(s); // re-render from re-verified truth (D-09) — never an optimistic flip
    captionEl().classList.remove("warn");
  } catch (err) {
    // NtpUnreachable / GraceAlreadyUsedToday — amber, non-punitive; displayed state unchanged.
    captionEl().textContent = String(err);
    captionEl().classList.add("warn");
  }
}

// ── Edit view (D-07/D-08/D-09) ──
//
// The Edit view is the ONLY sanctioned editor for config.yaml. It loads the live config text
// once, lets the user edit the visible curfew.* fields, runs classify_change DEBOUNCED on every
// input (live tighten/loosen/noop feedback), disables Commit with the locked reason when a
// loosen is pending at 0 tokens (UI-04), and confirms ONCE on a loosening commit (D-08). After a
// successful commit it re-renders the Status view from the returned re-verified StateDto (D-09) —
// never an optimistic local mutation.

/** The live config.yaml text loaded from disk — the classifier's `old` side and the edit base. */
let baseConfig = "";
/** The most recent ClassifyDto, used by the commit handler to decide confirm + gating. */
let lastClassify: ClassifyDto | null = null;

/** Replace (or note absence of) a top-level-ish `curfew.<key>: value` line in the YAML text.
 *  The classifier reads fields via yamlpath, so a per-field line edit on the visible curfew
 *  fields is a faithful, format-preserving way to compose the proposed `new_yaml`. */
function setYamlField(yaml: string, key: string, value: string): string {
  // Match an indented `key:` line (e.g. `  start: 23:00`) and replace its value, preserving
  // the original indentation and key. Anchored per-line; only the first match is rewritten.
  const re = new RegExp(`^(\\s*${key}\\s*:).*$`, "m");
  if (re.test(yaml)) {
    return yaml.replace(re, `$1 ${value}`);
  }
  return yaml; // field absent in the source — leave untouched (absent != loosen, server decides)
}

/** Compose the proposed new YAML from `baseConfig` + the current input values. */
function composeNewYaml(): string {
  let y = baseConfig;
  y = setYamlField(y, "enabled", fieldEnabledEl().checked ? "true" : "false");
  // HH:MM values; <input type=time> yields "HH:MM" (empty string if cleared — keep as-is).
  const start = fieldStartEl().value;
  const end = fieldEndEl().value;
  if (start) y = setYamlField(y, "start", start);
  if (end) y = setYamlField(y, "end", end);
  return y;
}

/** Seed the inputs from the loaded config text (best-effort line reads of the visible fields). */
function seedInputsFromConfig(): void {
  const read = (key: string): string | null => {
    const m = baseConfig.match(new RegExp(`^\\s*${key}\\s*:\\s*(.+?)\\s*$`, "m"));
    return m ? m[1].trim() : null;
  };
  const enabled = read("enabled");
  fieldEnabledEl().checked = enabled === null ? true : enabled.toLowerCase() !== "false";
  const start = read("start");
  if (start) fieldStartEl().value = start.replace(/^["']|["']$/g, "");
  const end = read("end");
  if (end) fieldEndEl().value = end.replace(/^["']|["']$/g, "");
}

/** Clear all per-field feedback badges. */
function clearFieldFeedback(): void {
  for (const field of ["curfew.enabled", "curfew.start", "curfew.end"]) {
    const node = fbEl(field);
    node.textContent = "";
    node.classList.remove("tighten", "loosen");
  }
}

/** Render per-field feedback + gate the Commit button from a ClassifyDto (D-07). */
function applyClassify(c: ClassifyDto): void {
  lastClassify = c;
  clearFieldFeedback();

  let hasLoosen = false;
  for (const f of c.fields) {
    if (f.direction === "noop") continue; // noop is silent (UI-SPEC line 150)
    const node = document.getElementById(`fb-${f.field}`);
    if (!node) continue;
    if (f.direction === "tighten") {
      node.textContent = "Tightens curfew · free";
      node.classList.add("tighten");
    } else if (f.direction === "loosen") {
      node.textContent = "Loosens curfew · costs 1 token";
      node.classList.add("loosen");
      hasLoosen = true;
    }
  }

  // Commit label: "Commit (spends 1 token)" when the pending diff loosens (UI-SPEC line 138).
  const commit = commitBtnEl();
  commit.textContent = hasLoosen ? "Commit (spends 1 token)" : "Commit changes";
  commit.classList.toggle("loosen", hasLoosen);

  // Gating: a loosen at 0 tokens (allowed===false) disables Commit with the locked reason.
  if (hasLoosen && !c.allowed) {
    commit.disabled = true;
    editReasonEl().textContent =
      c.reason ?? "Out of weekly tokens — available again Monday.";
  } else {
    commit.disabled = false;
    editReasonEl().textContent = "";
  }
}

let classifyTimer: number | undefined;

/** Debounced (~250ms) per-input classify — invokes classify_change with the composed new YAML. */
function scheduleClassify(): void {
  window.clearTimeout(classifyTimer);
  classifyTimer = window.setTimeout(() => void runClassify(), 250);
}

async function runClassify(): Promise<void> {
  if (!baseConfig) return;
  const newYaml = composeNewYaml();
  try {
    const c = await invoke<ClassifyDto>("classify_change", {
      oldYaml: baseConfig,
      newYaml,
    });
    applyClassify(c);
  } catch (err) {
    // A classify failure (e.g. malformed YAML) surfaces inline; leave the edit intact.
    editReasonEl().textContent = `Could not classify: ${String(err)}`;
  }
}

/** Commit handler: confirm ONCE on a loosening diff (D-08), then commit + re-render truth (D-09). */
async function onCommit(): Promise<void> {
  const c = lastClassify;
  if (!c) return;
  const loosens = c.fields.some((f) => f.direction === "loosen");

  // One-step confirm on loosening commits (D-08). Tighten-only/neutral commits skip this.
  if (loosens) {
    const ok = window.confirm(
      "Spend a weekly token?\n\nThis loosens your curfew and uses 1 of your 3 weekly tokens.",
    );
    if (!ok) return; // "Keep current"
  }

  const newYaml = composeNewYaml();
  try {
    const s = await invoke<StateDto>("commit_change", { newYaml });
    // D-09: re-render the Status view from the returned re-verified StateDto — no local mutation.
    last = s;
    render(s);
    // Reflect the freshly-committed config as the new base, switch back to Status.
    baseConfig = newYaml;
    lastClassify = null;
    clearFieldFeedback();
    editReasonEl().textContent = "";
    commitBtnEl().textContent = "Commit changes";
    commitBtnEl().classList.remove("loosen");
    showView("status");
  } catch (err) {
    // A server-side refusal (0-token loosen re-check, ntp unreachable) surfaces inline; the edit
    // stays intact so the user can adjust. The displayed Status state is unchanged.
    editReasonEl().textContent = String(err);
  }
}

/** Switch the main container between the Status and Edit views (toggle visibility + aria). */
function showView(view: "status" | "edit"): void {
  const isEdit = view === "edit";
  statusView().hidden = isEdit;
  editView().hidden = !isEdit;
  railStatusEl().setAttribute("aria-current", isEdit ? "false" : "page");
  railEditEl().setAttribute("aria-current", isEdit ? "page" : "false");
}

async function initEdit(): Promise<void> {
  // Load the live config text once (the classifier's `old` side + the input seed).
  try {
    baseConfig = await invoke<string>("read_config");
    seedInputsFromConfig();
  } catch {
    // No config yet (NotInitialized) — the Edit view stays inert until a config exists.
    baseConfig = "";
  }

  // Debounced live classify on any field input.
  fieldEnabledEl().addEventListener("change", scheduleClassify);
  fieldStartEl().addEventListener("input", scheduleClassify);
  fieldEndEl().addEventListener("input", scheduleClassify);

  commitBtnEl().addEventListener("click", () => void onCommit());

  // Left-rail view switching (Status is the default).
  railStatusEl().addEventListener("click", () => showView("status"));
  railEditEl().addEventListener("click", () => showView("edit"));

  // "+8 minutes" grace grant (the handler only fires when the button is enabled — D-10).
  graceBtnEl().addEventListener("click", () => void onGrace());
}

async function init(): Promise<void> {
  await refresh();
  await initEdit();
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
