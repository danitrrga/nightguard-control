# Phase 5: Instance Wiring - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase upgrades the author's **live, currently-running personal nightguard** so it runs on
the published product. It is an **in-place upgrade of "the normal nightguard," not a parallel
install.** It delivers WIRE-01 (every consumer reads the canonical `LifeOS/nightguard/config.yaml`,
eliminating the `~/.claude` drift) and WIRE-02 (the instance is configured with `NIGHTGUARD_DIR`,
a DPAPI signing key, and a signed initial state that verifies).

**Discovered during scout — the starting reality:**
- The "live hook" today is an **older Hermes-era system** (`~/.claude/hooks/nightguard_curfew_guard.ps1`
  + `curfew_guard.ps1`) with its own minimal YAML parser, per-day schedules, a StayFree-killing
  watchdog, and butler block-messages. It has **no token quota, no grace, no HMAC/signing, no
  sanctioned snapshot** — none of the published product's model.
- There are **two divergent config copies**: canonical `LifeOS/nightguard/config.yaml` (newer, Jun 4,
  `watchdog.enabled: true`, curfew 20:45→05:30) and the stale `~/.claude/nightguard/config.yaml`
  (Jun 2, `watchdog.enabled: false`). **Every live consumer reads the stale copy** — this IS the
  WIRE-01 drift, observed live.
- The published guard (`scripts/guard/nightguard_guard.ps1`) is a **host-agnostic verdict oracle**:
  it emits `{decision,reason,...}` JSON + exit 0/1 and deliberately does NOT emit the Claude-Code
  `{continue,decision,reason}` hook schema (lines 569–583). A thin **adapter hook** must translate
  exit-1 into a `{continue:false}` block carrying the butler message.

**In scope:** the curfew-gate cutover, the adapter hook, the watchdog rewrite, config normalization,
canonical-path wiring, and instance initialization (key + sanctioned snapshot + signed state).

**Out of scope (deferred):** any new product capability beyond making the live instance run on the
published engine.

</domain>

<decisions>
## Implementation Decisions

### Cutover (old → new)
- **D-01:** **Full replace.** Retire the old Hermes curfew hook (`nightguard_curfew_guard.ps1` /
  `curfew_guard.ps1`). The published product guard, fronted by a thin adapter hook, becomes the
  **sole curfew gate AND auto-revert** — no side-by-side, no double-evaluation.
- **D-02:** The **adapter hook preserves the existing butler messages** (curfew / tamper / offline).
  The product guard returns only verdict JSON + exit code; the adapter maps exit-1 → Claude-Code
  `{continue:false}` with the appropriate message (curfew vs clock-tamper vs offline reason).
- **D-03:** **Per-day `schedule` is carried over.** The live config uses per-day overrides; the
  product's `lock_status` evaluator already supports `schedule.<day>` (Phase 4, 04-02) — wire it through.

### Watchdog (StayFree)
- **D-04:** The watchdog is **rewritten for the new design** (this SUPERSEDES an earlier in-session
  decision to keep it verbatim). It must read the **same single canonical config** as everything else.
- **D-05:** **Root-cause confirmed live and folded into this phase** (user chose "Fold into Phase 5
  only" — no stopgap, no live-env edits during discussion): the watchdog scheduled task
  (`NightguardWatchdog`) is *Running*, but reads the stale `~/.claude/nightguard/config.yaml` where
  `watchdog.enabled: false`, so `Invoke-Pass` returns early every cycle and never relaunches StayFree
  (watchdog.log: loop started 2026-06-07 12:27, zero "restarting" lines after). Repointing the
  rewritten watchdog at canonical `LifeOS/nightguard/config.yaml` (`enabled: true`) restores StayFree.
  **This is the acceptance proof-case for WIRE-01.**
- **D-06:** The watchdog stays invoked by its Windows **Scheduled Task** (always-on), unchanged as a
  delivery mechanism; only the script + config source change.
- **D-07 (research item):** Verify StayFree's **actual UWP process name** matches `process_name: StayFree`
  used by `Get-Process` — a UWP process name mismatch is a plausible secondary failure mode to confirm.

### Canonical path & schema
- **D-08:** **`NIGHTGUARD_DIR = C:\Users\20252128\dev\Projects\LifeOS\nightguard`** — the single source
  of truth. Co-locate the five product files there: `config.yaml`, `config.sanctioned.yaml`,
  `guard.json`, `.nightguard.lock`, `.guardkey`. Curfew adapter, watchdog, and Rust app all resolve
  to this one home (matches existing `AppCtx::load` + guard `NIGHTGUARD_DIR` resolution).
- **D-09:** **Normalize the config to the product schema.** Migrate the existing curfew window + per-day
  schedule + the fields the watchdog/adapter consume (messages, clock_protection, watchdog block) into
  the product-canonical layout. Researcher/planner must reconcile exactly which keys the product writer
  (`yamlpatch`/`yamlpath`) touches vs. leaves for the watchdog/adapter, and keep the PowerShell minimal
  parser able to read the result (KERN-04 invariant).

### Go-live & safety
- **D-10:** **Live immediately, fully armed.** Enforcement starts the moment it's installed (tonight
  included): begin the week with **all 3 weekly tokens available**, **no grace used today**, current
  curfew **20:45→05:30**, watchdog back on, StayFree restored. No gap in protection.
- **D-11:** **Prove-then-switch cutover.** Verify the new instance actually signs, locks, and unlocks
  correctly on the author's machine (key generates + DPAPI round-trips, guard.json verifies, curfew
  gate returns correct allow/deny, a hand-edit auto-reverts) **before** retiring the old hook — so
  there is never a night unprotected or wrongly locked out.

### Claude's Discretion
- **Path resolution mechanism:** persist a user-level `NIGHTGUARD_DIR` env var pointing at the absolute
  LifeOS path; scripts NEVER resolve config relative to their own location (defeats the
  `$PSScriptRoot\..`-under-junction drift). User explicitly delegated this ("I don't know about
  technology, explain yourself better") — researcher to confirm the junction-safe approach on the
  actual machine (the standing STATE.md blocker).
- **Script deployment:** an **install/update step** copies the built scripts (guard, adapter, interop,
  watchdog) into `~/.claude/hooks` (where Claude Code invokes hooks and the watchdog task points) and
  **re-registers the hook-integrity SHA256 baseline** (`verify_hook_integrity.ps1`) after each deploy.
  "Updating the nightguard" = re-run install. User delegated this decision.
- **Instance init internals:** generate a fresh DPAPI `.guardkey` (Scope::User); seed
  `config.sanctioned.yaml` from the normalized canonical config; sign the initial `guard.json`
  (weekly_spent=0, grace unused) per the Phase 2 A3 recipe. Bootstrap order and the verify gate are
  the planner's to detail under D-11.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition
- `.planning/ROADMAP.md` §"Phase 5: Instance Wiring" — goal + 2 success criteria.
- `.planning/REQUIREMENTS.md` — WIRE-01 (hook reads canonical config, drift fixed), WIRE-02
  (instance configured: target path + key + state initialized).
- `.planning/STATE.md` §Blockers/Concerns [Phase 3] — the standing pre-wiring blocker: verify
  hook-path resolution under Claude Code junctions (`$PSScriptRoot\..` may resolve to the drifted
  `~/.claude/nightguard`).

### Published product (the new engine to wire in)
- `scripts/guard/nightguard_guard.ps1` — the verdict-oracle guard: config verify/auto-revert,
  circuit-breaker, curfew + grace verdict, JSON output + exit 0/1 (see lines 569–583 for the
  deliberately host-agnostic output the adapter must translate).
- `scripts/guard/verify_hook_integrity.ps1` + `scripts/guard/guard.baseline.sha256` — the SHA256
  integrity baseline the install/deploy step must re-register after copying scripts.
- `scripts/interop/nightguard_interop.ps1`, `scripts/interop/state_interop.ps1` — crypto primitives
  the guard dot-sources (`$here\..\interop`) — relevant to the junction-resolution decision.
- `src-tauri/src/commands.rs` §`AppCtx::load` (lines ~86–115) — how the Rust app resolves
  `NIGHTGUARD_DIR` and the five fixed paths; the app side of "single home."
- `src-tauri/src/lib.rs` (lines ~17–47) — startup `AppCtx::load` + runtime `fs:scope` extension
  for a non-conventional `NIGHTGUARD_DIR` (WR-02) — directly affects pointing the app at LifeOS.

### Live system being replaced (read to migrate, then retire)
- `~/.claude/hooks/nightguard_curfew_guard.ps1` + `~/.claude/hooks/curfew_guard.ps1` — old curfew
  gate + its minimal YAML parser + butler messages to preserve in the adapter.
- `~/.claude/hooks/nightguard_app_watchdog.ps1` — old watchdog (`-Loop` mode, reads
  `$USERPROFILE\.claude\nightguard\config.yaml`, early-returns on `enabled:false`) — the rewrite source.
- `~/.claude/hooks/nightguard_install_watchdog.ps1` — registers the `NightguardWatchdog` Scheduled Task.
- `~/.claude/hooks/config.yaml` — Hermes hook-wiring manifest (session_start/before_prompt/...);
  where the curfew adapter hook gets registered.
- `LifeOS/nightguard/config.yaml` — the **canonical** config (curfew 20:45→05:30, watchdog enabled,
  messages, clock_protection); the migration source-of-truth.

### Cross-language invariants (must not break)
- `.planning/phases/01-trust-kernel/01-CONTEXT.md` and Phase 2 STATE notes (02-04, 02-05, A3) —
  canonical-bytes / state_hmac recipe the instance init must reuse so guard.json verifies in both
  Rust and PowerShell.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `lock_status` evaluator (mutation-engine, 04-02): pure `(config_yaml, now) -> LockStatus` with
  `schedule.<day>` support and fail-safe-LOCKED precedence — the curfew verdict the adapter relies on.
- `AppCtx::load` (`src-tauri/src/commands.rs`): already resolves `NIGHTGUARD_DIR` → five fixed paths
  and loads `.guardkey` once. Pointing the instance at LifeOS is a config/env change, not new resolution code.
- Phase 1–2 interop + state-sign machinery (`nightguard_interop.ps1`, `state_interop.ps1`,
  `compute_state_hmac`): the instance-init signing path already exists and is parity-proven.
- `verify_hook_integrity.ps1` + `guard.baseline.sha256`: the deploy step's integrity re-stamp is built;
  it already self-registers the guard and itself.

### Established Patterns
- **Guard is a host-agnostic oracle** (JSON verdict + exit code), never the Claude-Code hook schema —
  so an adapter layer is the established seam for host-specific blocking/messages.
- **Single `NIGHTGUARD_DIR` home** is the existing convention across guard + app; the watchdog must
  join it rather than keep its own `$USERPROFILE\.claude\nightguard` path.
- **Fail-closed / atomic-ordered commit** and the KERN-04 PS-parser-readability invariant constrain
  how config normalization may rewrite `config.yaml`.

### Integration Points
- Claude Code `settings.json` / `~/.claude/hooks/config.yaml` `before_prompt` chain — where the new
  curfew adapter registers (replacing `discipline/curfew_guard.ps1`).
- `NightguardWatchdog` Scheduled Task — repointed to the rewritten watchdog reading canonical config.
- DPAPI `.guardkey` under LifeOS — shared by Rust app, guard, and adapter (CurrentUser scope invariant).

</code_context>

<specifics>
## Specific Ideas

- "This is just an update of the normal nightguard" — the published product replaces the author's
  existing personal system in place; the whole nightguard (curfew + watchdog) is the deliverable.
- Keep the existing curfew window exactly: closes **20:45**, opens **05:30**, Europe/Amsterdam.
- Preserve the existing Spanish-butler voice in the curfew/tamper/offline block messages.
- StayFree must be running again after cutover (the visible signal that wiring worked).

</specifics>

<deferred>
## Deferred Ideas

- **Watchdog as a first-class product feature** — currently folded in as a personal-instance rewrite
  reusing the Scheduled-Task delivery. Generalizing app-watchdog enforcement into the published
  product (config schema, UI, cross-app) is a future roadmap candidate, not this phase.
- **Browser/zen lock hooks** (`browser_lock.log`, `zen_lock.log` seen under `~/.claude/nightguard`) —
  other Hermes-era enforcement surfaces; out of scope, noted for a future "consolidate all discipline
  hooks" phase.

None of these block planning.

</deferred>

---

*Phase: 5-Instance Wiring*
*Context gathered: 2026-06-09*
