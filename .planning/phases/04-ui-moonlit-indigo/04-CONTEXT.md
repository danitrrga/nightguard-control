# Phase 4: UI (Moonlit Indigo) - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 delivers the **non-authoritative display + edit-intent layer** for the nightguard
curfew: a single-screen Tauri desktop app that shows hook-enforced lock status, a live
countdown, the weekly loosen-token meter, the once-daily "+8 minutes" grace grant, and the
**only sanctioned editor** for `config.yaml` — with live per-field tighten/loosen feedback.

Because no application shell exists yet (Phases 1–3 produced Rust library crates +
the PowerShell guard, but **no `src/`, no `package.json`, no `tauri.conf.json`, and zero
`#[tauri::command]`**), this phase is a full vertical slice: scaffold the Tauri v2 app, wrap
the existing kernel/engine functions as IPC commands, and build the UI on top.

**The app is a reader; the guard is the enforcer.** The UI never enforces and never writes
optimistically — it reflects the same signed artifacts the guard reads, re-verified.

**Explicitly NOT in this phase / NOT this product:** usage analytics, screen-time tracking,
or app-blocking (this is **not a StayFree replacement**). The app visualizes *focus discipline
at a glance*, nothing more. A general-purpose settings editor is also out (scope is the
nightguard curfew config only, per REQUIREMENTS).
</domain>

<decisions>
## Implementation Decisions

### App-shell + IPC scope
- **D-01:** Phase 4 is a **full vertical slice** — scaffold the Tauri v2 **vanilla-TS + Vite**
  app, add `src-tauri/`, and wrap the existing crate functions as the four IPC commands named
  in CLAUDE.md: `get_state`, `classify_change`, `commit_change`, `use_grace`. The IPC layer is
  thin glue over already-built `trust-kernel` / `mutation-engine` functions. Expect ~3–4 plans
  (scaffold+IPC contract → status view → edit panel → actions/wiring).
- **D-02:** The Rust backend remains the **sole writer/signer** (carried from CLAUDE.md). The
  frontend only `invoke()`s; it never touches files or HMAC directly.

### Source of hook-enforced truth
- **D-03:** `get_state` reads the **same signed `config.yaml` + `guard.json`** the guard reads,
  **re-verifies the HMAC via the Rust kernel** (`verify_bytes` / `compute_state_hmac` /
  `canonicalize_bytes`), and derives lock status, countdown, token meter, and grace
  availability from the verified state. **No shelling out to the guard** (that would trigger
  reverts/audit/SNTP side-effects on every refresh). If verification fails or the state shows
  maximal-lockout, the UI displays that as-is — never app-local optimism.
- **D-04:** Clock-tamper/offline detection is the **guard's** authority, not the app's.
  App-side time is **advisory only** (CLAUDE.md); when the app can't confirm true time it shows
  a quiet "time unverified" caveat rather than asserting a countdown as truth.

### Liveness / refresh
- **D-05:** **Watch the data dir** (`config.yaml` + `guard.json`) via Tauri fs-watch — any
  change (a guard revert, an external hand-edit, a fresh signed state) triggers an immediate
  re-read + re-verify. A **1-second client tick** animates the countdown between changes.
  Fallback to a short poll only if the watcher proves unreliable on the target host.
- **D-06:** The **countdown is the hero element** and targets the next state-change boundary:
  LOCKED → counts to curfew-window end; grace active → counts to grace-window end; OPEN →
  shows next lock time. The token meter is the **3-dot weekly** indicator with next-reset and
  today's grace availability (UI-02).

### Edit panel + actions
- **D-07:** `classify_change` runs **live, debounced, per field**. Tighten → quiet accent;
  loosen → warning + token cost. Loosening at **0 tokens disables commit with an inline
  reason** (UI-04).
- **D-08:** **One confirm step on loosening commits** (it spends a token); tightening commits
  freely.
- **D-09:** After **any** `commit_change` or `use_grace`, **re-read the freshly-signed state**
  so the display equals enforced truth (no optimistic local mutation).
- **D-10:** The **"+8 minutes" button** is enabled **only during an active lock when grace is
  available**, and grants the window on press via `use_grace` (UI-03), then re-fetches (D-09).

### Design / aesthetic — MINIMALIST (user-led)
- **D-11:** **Minimalist, typographic, whitespace-led.** Very **few containers — no card
  soup.** The "flat-card layout" hint in CLAUDE.md is **superseded** by this direction: lean on
  type hierarchy, spacing, and hairline dividers instead of boxes. The app is a *focus-legibility
  surface*, calm and quiet — the countdown dominates, everything else recedes.
- **D-12:** Keep the **Moonlit Indigo palette + Roboto** (locked, CLAUDE.md / UI-05). The
  left-icon-rail is retained but **sparse** (status + edit, not a busy nav). Detailed visual
  contract belongs in the UI-SPEC (run `/gsd-ui-phase 4` before planning).

### Claude's Discretion
- Exact IPC payload shapes for `get_state` (the state DTO: lock bool, boundary timestamps,
  weekly_spent/remaining, grace availability, fail_closed/verify status) — to be designed in
  planning against the existing engine return types and the guard's `guard.json` schema.
- File-watch debounce window, countdown formatting, and component decomposition.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` — Phase 4 goal + the 5 success criteria (UI-01..05).
- `.planning/REQUIREMENTS.md` — UI-01..05 wording + anti-scope ("curfew config only", no
  general settings editor).

### Design system & stack (locked, with one override)
- `./CLAUDE.md` — Moonlit Indigo palette tokens (`--bg #0c0e14 --surface #161a24 --border
  #242a38 --text #e8eaf0 --dim #8b91a3 --accent #7aa2ff`), Roboto, Tauri v2 + vanilla-TS + Vite
  stack, lean-deps, the verified IPC `#[tauri::command]` pattern, and the named commands
  (`get_state`, `classify_change`, `commit_change`, `use_grace`).
  **NOTE:** the "flat-card / YouTube-Studio" descriptor is superseded for this phase by the
  minimalist, low-container direction in D-11 — keep palette/type, drop the card-heavy layout.

### Backend to wrap as IPC (the slice's load-bearing reuse)
- `crates/trust-kernel/src/` — `sign_config`, `compute_state_hmac`, `verify_bytes`,
  `canonicalize_bytes`, `dpapi_protect`/`dpapi_unprotect`. The app re-verifies signed artifacts
  through these for D-03.
- `crates/mutation-engine/src/` — `classify_change`, `is_loosening_commit`, `commit_change`,
  `commit_with_limit`, `use_grace`, `decide` (grace/curfew verdict), week-reset math
  (`most_recent_monday_midnight` / `next_monday_midnight`).

### Enforced-state contract (what get_state reads)
- `scripts/guard/nightguard_guard.ps1` — the guard's `guard.json` consumption + the D-02 verdict
  JSON shape (decision/reason/grace_remaining_secs/reverted/fail_closed); the app reads the same
  signed `config.yaml` + `guard.json` and must agree with the guard's interpretation.
- `.planning/phases/03-enforcement-guard/03-CONTEXT.md` — D-01..D-10 guard decisions (single
  base-dir resolution, state worst-casing, maximal-lockout, fail-closed) that define what the
  display must faithfully reflect.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **trust-kernel** (HMAC sign/verify, DPAPI, canonicalization): the app's read-and-verify path
  for `get_state` reuses these directly — same code the guard trusts.
- **mutation-engine** (`classify_change`, `commit_*`, `use_grace`, `decide`, week math): each of
  the four IPC commands is a thin wrapper over one or two of these.
- **Signed artifacts** `config.yaml` + `guard.json` in the single data dir (Phase 3 D-09): the
  authoritative read source for display.

### Established Patterns
- Backend = sole writer/signer; frontend never writes (CLAUDE.md, Phase 3 D-05). The UI is
  strictly a reader + intent-submitter.
- Single base-dir data resolution (Phase 3 D-09) — the app resolves the same dir the guard does.

### Integration Points
- **New:** the entire Tauri shell (`src/` frontend, `src-tauri/` Rust host) and the
  `#[tauri::command]` bridge — none exist yet; scaffolded fresh in this phase.
- The bridge connects the webview `invoke()` calls to the existing crates via a new `src-tauri`
  crate that depends on `trust-kernel` + `mutation-engine`.
</code_context>

<specifics>
## Specific Ideas

- "A way of visualizing my focus **in general** — **not** trying to replace StayFree." The app
  is a calm status/control surface for the self-binding curfew, not a usage tracker.
- "Make it simple, avoid using too many box containers and cards." → minimalist, typographic,
  whitespace-led (D-11).
- The countdown is the emotional center of the screen — big, quiet, honest.
</specifics>

<deferred>
## Deferred Ideas

- **Usage analytics / screen-time tracking / app-blocking** — explicitly out; that's StayFree's
  domain, not this product.
- **General-purpose settings editor** — out of scope (curfew config only, per REQUIREMENTS).
- **Phase 5 (Instance Wiring)** — pointing the author's live LifeOS hook at the canonical config
  is its own phase; not part of the UI build.
</deferred>

---

*Phase: 4-UI (Moonlit Indigo)*
*Context gathered: 2026-06-09*
