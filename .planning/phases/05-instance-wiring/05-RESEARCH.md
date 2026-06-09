# Phase 5: Instance Wiring - Research

**Researched:** 2026-06-09
**Domain:** Live in-place cutover of a running personal nightguard onto the published product (Windows env wiring, PowerShell hooks, DPAPI/HMAC instance init, Scheduled Task, config schema migration)
**Confidence:** HIGH (all load-bearing facts verified against the live machine and the in-repo code, not assumed)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01: Full replace.** Retire the old Hermes curfew hook. The published product guard, fronted by a thin adapter hook, becomes the sole curfew gate AND auto-revert — no side-by-side, no double-evaluation.
- **D-02:** The adapter hook preserves the existing butler messages (curfew / tamper / offline). The product guard returns only verdict JSON + exit code; the adapter maps exit-1 → Claude-Code `{continue:false}` with the appropriate message (curfew vs clock-tamper vs offline reason).
- **D-03:** Per-day `schedule` is carried over. The product's `lock_status` evaluator already supports `schedule.<day>` (Phase 4, 04-02) — wire it through.
- **D-04:** The watchdog is rewritten for the new design (SUPERSEDES an earlier decision to keep it verbatim). It must read the same single canonical config as everything else.
- **D-05:** Root-cause confirmed live and folded into this phase (no stopgap, no live-env edits during discussion): the watchdog Scheduled Task is *Running* but reads the stale `~/.claude/nightguard/config.yaml` where `watchdog.enabled: false`, so it never relaunches StayFree. Repointing at canonical LifeOS config (`enabled: true`) restores StayFree. **This is the acceptance proof-case for WIRE-01.**
- **D-06:** The watchdog stays invoked by its Windows Scheduled Task (always-on), unchanged as a delivery mechanism; only the script + config source change.
- **D-07 (research item):** Verify StayFree's actual UWP process name matches `process_name: StayFree`.
- **D-08:** `NIGHTGUARD_DIR = C:\Users\20252128\dev\Projects\LifeOS\nightguard` — the single source of truth. Co-locate the five product files there: `config.yaml`, `config.sanctioned.yaml`, `guard.json`, `.nightguard.lock`, `.guardkey`.
- **D-09:** Normalize the config to the product schema. Reconcile exactly which keys the product writer (yamlpatch/yamlpath) touches vs. leaves for the watchdog/adapter; keep the PowerShell minimal parser able to read the result (KERN-04).
- **D-10:** Live immediately, fully armed. Begin the week with all 3 weekly tokens available, no grace used today, curfew 20:45→05:30, watchdog back on, StayFree restored. No gap in protection.
- **D-11:** Prove-then-switch cutover. Verify the new instance signs, locks, unlocks, and auto-reverts correctly **before** retiring the old hook.

### Claude's Discretion
- **Path resolution mechanism:** persist a user-level `NIGHTGUARD_DIR` env var pointing at the absolute LifeOS path; scripts NEVER resolve config relative to their own location (defeats the `$PSScriptRoot\..`-under-junction drift). Confirm the junction-safe approach on the actual machine (the standing STATE.md blocker).
- **Script deployment:** an install/update step copies the built scripts (guard, adapter, interop, watchdog) into `~/.claude/hooks` and re-registers the hook-integrity SHA256 baseline after each deploy. "Updating the nightguard" = re-run install.
- **Instance init internals:** generate a fresh DPAPI `.guardkey` (Scope::User); seed `config.sanctioned.yaml` from the normalized canonical config; sign the initial `guard.json` (weekly_spent=0, grace unused) per the Phase 2 A3 recipe. Bootstrap order and the verify gate are the planner's to detail under D-11.

### Deferred Ideas (OUT OF SCOPE)
- Watchdog as a first-class product feature (config schema, UI, cross-app generalization).
- Browser/zen lock hooks (`browser_lock.log`, `zen_lock.log`) — other Hermes-era surfaces.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WIRE-01 | The live curfew hook reads the canonical config directly, eliminating the `~/.claude` vs LifeOS drift | Verified live: the active gate is `curfew_guard.ps1` (settings.json UserPromptSubmit) which ALREADY prefers LifeOS; the watchdog and the published guard/app do NOT. Single-home `NIGHTGUARD_DIR` + absolute-path resolution closes the drift for all four consumers. Acceptance proof-case = StayFree restarts (D-05). |
| WIRE-02 | The instance (`LifeOS/nightguard`) is configured as the app's target config path, with key + state initialized | `NIGHTGUARD_DIR` is currently UNSET in all scopes (verified). Init recipe = `load_or_create_key` (generates+DPAPI-protects on first run) + seed sanctioned + sign initial `guard.json` via the locked A3 recipe. Verify gate per D-11 below. |
</phase_requirements>

## Summary

This phase is a **live in-place cutover of a currently-running personal nightguard**, and the live machine differs from the CONTEXT's stated starting reality in two material ways that the planner must absorb:

1. **The active curfew gate is `curfew_guard.ps1`, NOT `nightguard_curfew_guard.ps1`.** Claude Code's `settings.json` `UserPromptSubmit` chain runs `C:/Users/20252128/.claude/hooks/curfew_guard.ps1`. `nightguard_curfew_guard.ps1` is referenced nowhere — it is an orphan. Verified live. The retirement target (D-01) is `curfew_guard.ps1`; the orphan should also be deleted to avoid confusion but is not load-bearing. `[VERIFIED: settings.json + grep]`

2. **`~/.claude/hooks` IS a Windows junction → `C:\Users\20252128\dev\Projects\LifeOS\hooks`.** `~/.claude` itself is NOT a junction, but the `hooks` subdir is. So "deploy scripts into `~/.claude/hooks`" physically writes into `LifeOS/hooks`. This is exactly why `$PSScriptRoot\..` is dangerous: a script under `~/.claude/hooks` resolves `..` to `LifeOS` (the real parent), not `~/.claude` — *the opposite* of the drift the STATE.md blocker feared, but still non-deterministic and absolutely not where the data dir lives. The data dir is `LifeOS/nightguard`, a sibling of `LifeOS/hooks`. `[VERIFIED: Get-Item LinkType=Junction]`

**Primary recommendation:** Set a **user-scope `NIGHTGUARD_DIR` env var = `C:\Users\20252128\dev\Projects\LifeOS\nightguard`** as the single resolution mechanism for ALL FOUR consumers (guard, adapter, watchdog-task, Rust app). This is junction-immune (an absolute path never touches `$PSScriptRoot`), and it is verified that fresh processes — including the Scheduled-Task-spawned `powershell.exe` at next logon — see user-scope env vars. The guard and the Rust `AppCtx::load` already resolve `NIGHTGUARD_DIR` and fail-closed when unset; the watchdog rewrite must adopt the identical resolution. Init via `load_or_create_key` + A3-signed `guard.json`. Prove-then-switch per D-11 with a scripted dry-run gate before touching `settings.json`.

**The single biggest landmine:** `NIGHTGUARD_DIR` is currently UNSET. The moment you retire `curfew_guard.ps1` (which reads config by absolute LifeOS path with no env-var dependency) and switch to the adapter+guard (which `throw` when `NIGHTGUARD_DIR` is empty), an unset or wrongly-timed env var means the guard throws on every fire. Whether a thrown PowerShell hook *blocks* or *allows* the prompt depends on the adapter's exit-code/`continue` contract — this MUST be fail-closed (block) or the author is unprotected at curfew. See Pitfall 1.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Data-dir resolution | OS env (`NIGHTGUARD_DIR`, user scope) | — | Single source of truth; junction-immune; already the guard/app convention |
| Curfew verdict | PowerShell guard (oracle, `nightguard_guard.ps1`) | mutation-engine `lock_status` (Rust, for UI only) | Guard is the always-firing enforcer; the Rust eval is advisory display |
| Host blocking + butler messages | Adapter hook (PowerShell, new) | — | Guard is host-agnostic (exit-code only); adapter is the Claude-Code seam (D-02) |
| Auto-revert of hand edits | PowerShell guard | — | Guard owns config-verify + byte-copy revert (GARD-01) |
| Signing / re-blessing | Rust app (sole writer/signer) | — | Key never leaves Rust host memory; guard NEVER signs (locked invariant) |
| StayFree liveness | Watchdog (PowerShell, Scheduled Task) | — | Always-on delivery via `NightguardWatchdog` task (D-06) |
| Instance init (key+state) | Rust `load_or_create_key` + A3 sign | PowerShell parity check | Generate-once key; A3 recipe proven byte-identical both languages |

## Standard Stack

No new external packages are installed in this phase. It is wiring + init over the existing Phase 1–4 stack. The only "tools" are Windows built-ins.

### Core (all already present / built-in)
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `setx` / `[Environment]::SetEnvironmentVariable(...,'User')` | Windows built-in | Persist user-scope `NIGHTGUARD_DIR` | The junction-safe resolution mechanism (D-08). `[Environment]` is preferred over `setx` (setx truncates at 1024 chars and the path is short, but `[Environment]` is the .NET-native, no-truncation call). `[VERIFIED: live probe]` |
| `Register-ScheduledTask` / `Start-ScheduledTask` | Windows built-in (ScheduledTasks module) | Re-register `NightguardWatchdog` pointing at the rewritten watchdog | The existing `nightguard_install_watchdog.ps1` already uses these (D-06). `[VERIFIED: in-repo script + live task State=Running]` |
| `Get-Process -Name StayFree` | Windows built-in | Watchdog liveness probe | The UWP process IS named `StayFree` (exe = `app\StayFree.exe`). `[VERIFIED: package manifest]` |
| `explorer.exe shell:AppsFolder\<PFN>!<AppId>` | Windows built-in | Relaunch the UWP StayFree | Existing watchdog mechanism, correct PFN confirmed below. `[VERIFIED: Get-AppxPackage]` |
| `load_or_create_key` (trust-kernel) | in-repo | Generate-once DPAPI `.guardkey` (Scope::User) | Already the project's key lifecycle; generates+protects on first run, loads thereafter. `[VERIFIED: key.rs]` |
| `state_interop_cli` / `GuardState::compute_state_hmac` | in-repo | Sign the initial `guard.json` (A3 recipe) | The single locked state_hmac recipe, proven byte-identical Rust↔PS (02-05). `[VERIFIED: state.rs + state_interop_cli.rs]` |
| `verify_hook_integrity.ps1 -Update` | in-repo | Re-stamp the SHA256 baseline after deploy | Already self-registers guard+verifier+both interop scripts. `[VERIFIED: verify_hook_integrity.ps1]` |

## Package Legitimacy Audit

> Not applicable — this phase installs **no** external packages (Node, PyPI, or crates). It wires the already-vetted Phase 1–4 stack and uses Windows built-ins only. No slopcheck run required.

## Architecture Patterns

### System Architecture Diagram (post-cutover)

```
                      ┌─────────────────────────────────────┐
   user-scope env →   │  NIGHTGUARD_DIR =                    │
                      │  C:\...\LifeOS\nightguard            │  (single source of truth, D-08)
                      └───────────────┬─────────────────────┘
                                      │ resolved by ALL FOUR consumers
        ┌─────────────────────────────┼──────────────────────────────┬───────────────────────┐
        ▼                             ▼                              ▼                       ▼
  ┌───────────┐   prompt        ┌───────────┐  exit 0/1 + JSON  ┌───────────┐         ┌─────────────┐
  │ Claude    │──UserPromptSub─▶│  ADAPTER  │──invokes guard──▶ │  GUARD    │         │   RUST APP   │
  │ Code      │                 │  (new PS) │◀──verdict JSON──── │ (oracle)  │         │ (AppCtx::    │
  └───────────┘                 └─────┬─────┘                   └─────┬─────┘         │  load)       │
        ▲                             │                               │               └──────┬───────┘
        │   {continue:false} +        │ maps reason→butler msg        │ reads/verifies/       │ writes/signs
        └── butler message ───────────┘ (curfew/tamper/offline)       │ reverts               │ (sole signer)
                                                                      ▼                       ▼
                                                       ┌──────────────────────────────────────────┐
                                                       │  LifeOS/nightguard/ (the one home)         │
                                                       │   config.yaml  config.sanctioned.yaml      │
                                                       │   guard.json   .nightguard.lock  .guardkey │
                                                       └──────────────────────┬─────────────────────┘
                                                                              │ reads watchdog.enabled + apps
                                                                              ▼
                              Scheduled Task ──▶ ┌───────────┐  Get-Process StayFree?  ┌─────────────┐
                              NightguardWatchdog │ WATCHDOG  │──── if absent ─────────▶ │  StayFree   │
                              (-Loop, at logon)  │ (new PS)  │  explorer shell:Apps...  │  (UWP)      │
                                                 └───────────┘                          └─────────────┘
```

Trace the primary use case: a late-night prompt enters Claude Code → the adapter invokes the guard → the guard verifies `config.yaml` against signed `guard.json`, auto-reverts a hand edit, computes the curfew/grace verdict against its own SNTP, emits `{decision,reason,...}` + exit 1 → the adapter translates exit-1 + reason into `{continue:false}` with the butler message → the prompt is blocked.

### Recommended File Layout (deploy target = `LifeOS/hooks`, via the junction)
```
LifeOS/hooks/                        (== ~/.claude/hooks junction target)
├── nightguard_guard.ps1             # copied from scripts/guard/  (the oracle)
├── nightguard_adapter.ps1           # NEW — the Claude-Code seam (D-02)
├── nightguard_watchdog.ps1          # NEW — rewritten watchdog, reads NIGHTGUARD_DIR
├── verify_hook_integrity.ps1        # copied from scripts/guard/  (re-stamps baseline)
├── guard.baseline.sha256            # re-stamped after each deploy
└── interop/
    ├── nightguard_interop.ps1       # copied — crypto primitives the guard dot-sources
    └── state_interop.ps1            # copied

LifeOS/nightguard/                   (== NIGHTGUARD_DIR — the data home)
├── config.yaml          (normalized, product schema, signed)
├── config.sanctioned.yaml
├── guard.json           (A3-signed initial state)
├── .nightguard.lock
└── .guardkey            (DPAPI CurrentUser blob)
```

**Critical deploy-layout constraint:** `nightguard_guard.ps1` dot-sources `..\interop\nightguard_interop.ps1` and `..\interop\state_interop.ps1` via `$here = Split-Path -Parent $MyInvocation.MyCommand.Path` then `Join-Path $here '..\interop\...'` (lines 38–40). This `$here\..\interop` IS script-relative — it is the ONE place the guard resolves a path relative to itself, and it is FINE because it resolves *its own dot-source tree*, not the *data dir*. But it dictates the deploy layout: when the guard lands in `LifeOS/hooks/`, the interop scripts MUST land in `LifeOS/hooks/interop/` (a sibling `interop/` dir), or the dot-source throws. The repo layout is `scripts/guard/` + `scripts/interop/` (siblings under `scripts/`), so `..\interop` works in-repo; the deploy must preserve that sibling relationship under `hooks/`. `[VERIFIED: nightguard_guard.ps1 lines 38–40]`

### Pattern 1: Junction-safe data-dir resolution (resolves the standing blocker)
**What:** Every consumer resolves the data dir from the absolute `NIGHTGUARD_DIR` env var; NONE derives it from its own location.
**Why it works on this machine:**
- The guard already does exactly this and `throw`s when `NIGHTGUARD_DIR` is empty (lines 42–48). `[VERIFIED]`
- `AppCtx::load` already does exactly this and returns `NotInitialized` when empty (commands.rs lines 96–99). `[VERIFIED]`
- The adapter (new) and watchdog (rewrite) must adopt the identical `$env:NIGHTGUARD_DIR` read with a fail-closed throw on empty.
- User-scope env vars ARE visible to freshly-spawned processes including the logon-triggered Scheduled Task. `[VERIFIED: live SetEnvironmentVariable('...','User') round-trip — a fresh powershell read it back]`
**Example (the resolution stanza every PS consumer uses, mirroring the guard):**
```powershell
# Source: scripts/guard/nightguard_guard.ps1 lines 42-48 (verified)
$DataDir = $env:NIGHTGUARD_DIR
if ([string]::IsNullOrWhiteSpace($DataDir)) {
    throw "nightguard: no data dir (set NIGHTGUARD_DIR)"   # fail-closed, never guess
}
```

### Pattern 2: The adapter hook contract (D-02)
**What:** A thin PowerShell hook that invokes the guard, captures its exit code + JSON, and translates into the Claude-Code `UserPromptSubmit` schema.
**The guard's exact output vocabulary** (verified from `nightguard_guard.ps1` lines 461–583):
- JSON object fields: `decision` ∈ {`allow`,`deny`}, `reason`, `grace_remaining_secs`, `reverted`, `fail_closed`, `audit_chain_broken`, `audit_chain_break_index`.
- `reason` literal values: `"curfew"`, `"grace active"`, `"ntp unreachable"`, `"clock tamper"`.
- Exit code: `exit 0` iff `decision == "allow"`, else `exit 1` (lines 583).
**The translation table the adapter implements:**

| Guard exit | Guard `reason` | Adapter emits (Claude-Code schema) | Butler message source (from LifeOS config) |
|------------|----------------|-------------------------------------|--------------------------------------------|
| 0 | `grace active` (or any allow) | allow (exit 0, no `continue:false`) | — (let the prompt through) |
| 1 | `curfew` | `{continue:false}` block | `curfew.message` (with `{start}`/`{end}` substituted) |
| 1 | `clock tamper` | `{continue:false}` block | `curfew.tamper_message` |
| 1 | `ntp unreachable` | `{continue:false}` block | `curfew.offline_message` |
| (guard throws / non-0 non-1 / no JSON) | — | `{continue:false}` block (fail-closed) | `curfew.offline_message` (safest default) |

**How the legacy gate did it (the contract to preserve), from `curfew_guard.ps1`:** on block it wrote `[Console]::Error.WriteLine($reason); exit 2`. Claude Code's `UserPromptSubmit` hook contract: a hook may emit a JSON object on stdout with `{"continue": false, "reason": "..."}` to block, OR use exit-code semantics. The legacy `nightguard_curfew_guard.ps1` (the orphan) used `{decision:'block', reason:...}` JSON on stdout. **The planner must confirm the EXACT current Claude-Code `UserPromptSubmit` block schema** (this changed across CC versions) — see Open Questions. The adapter must read the guard's butler-message strings from the SAME canonical `config.yaml` it points the guard at, so messages stay in one place (do not hardcode them in the adapter).

### Pattern 3: Instance init / bootstrap order (WIRE-02, D-11)
**What:** The exact ordered recipe to initialize a fresh, fully-armed instance whose `guard.json` verifies in BOTH Rust and PowerShell.
**Ordered recipe:**
1. **Ensure `NIGHTGUARD_DIR` is set** (user scope) and the dir `LifeOS/nightguard/` exists.
2. **Normalize `config.yaml`** to the product schema (see Schema Mapping below) — write canonical bytes (UTF-8, no BOM, LF, exactly one trailing LF) so KERN-04's PS parser and the Rust HMAC agree.
3. **Generate `.guardkey`:** call `load_or_create_key(data_dir/.guardkey)` — on first run it generates 32 OS-random bytes, DPAPI-protects (CurrentUser, `None` entropy) as a raw blob, atomic-writes it, returns the 32 bytes. `[VERIFIED: key.rs lines 41–60]`
4. **Seed `config.sanctioned.yaml`:** byte-copy the normalized `config.yaml` so `HMAC(sanctioned) == HMAC(config) == config_hmac` (the guard's revert-target invariant, `Test-SanctionedValid` lines 141–156).
5. **Build the initial `GuardState`** (fully armed, D-10):
   - `config_hmac` = `HMAC(canonical config.yaml bytes)` (lowercase hex)
   - `weekly_spent` = `0`
   - `week_anchor` = current Monday ISO date in `Europe/Amsterdam`, via `most_recent_monday_midnight(now_utc, "Europe/Amsterdam")` → format `YYYY-MM-DD` (DST-aware; never naive). For 2026-06-09 (Tue) the anchor is **`2026-06-08`** (the Monday). `[VERIFIED: week.rs most_recent_monday_midnight]`
   - `ledger` = `[]`
   - `grace` = `null` (no grace used today)
6. **Compute `state_hmac`** via `GuardState::compute_state_hmac(&key)` (A3: blank state_hmac → serialize → `canonicalize_bytes` → `sign_bytes` → `tag_to_hex`), then write the filled `guard.json`. `[VERIFIED: state.rs lines 49–56]`
7. **Re-stamp the integrity baseline** (`verify_hook_integrity.ps1 -Update`) AFTER the scripts are deployed (see Deploy below).

**Where this belongs:** there is no in-repo init/bootstrap binary yet — `state_interop_cli emit-state-hmac` writes a *fixed test* state, not a real armed instance, and `load_or_create_key` is only called from the Tauri app's `AppCtx::load` and the test CLI. The planner must decide: (a) add a small `init` subcommand to a Rust bin that performs steps 3–6 with real D-10 values, OR (b) drive it by launching the Tauri app pointed at the empty dir (it calls `load_or_create_key` at startup) plus a one-shot signing step. Option (a) is cleaner and testable; flagged as a planning decision. `[ASSUMED — no existing init binary found; planner chooses the seam]`

### Pattern 4: Prove-then-switch verify gate (D-11)
**What:** A scripted dry-run that proves the new instance signs/locks/unlocks/auto-reverts BEFORE editing `settings.json` to retire `curfew_guard.ps1`.
**The gate (run against `LifeOS/nightguard` with the real key, mirroring `run_guard_gate.ps1` from Phase 3):**
1. **Key round-trips:** Rust `load_or_create_key` and PS `Unprotect-GuardKey` both yield the identical 32 bytes (the Phase 1 canary). 
2. **`guard.json` verifies:** PS `Get-RuntimeStateHmac` re-derives a tag == on-disk `state_hmac` (A3 parity); Rust `verify-state-hmac` exits 0.
3. **Curfew gate correct:** run `nightguard_guard.ps1` with `NIGHTGUARD_TEST_NTP_OVERRIDE=1` + `-NtpOverrideUnixSecs` set to an in-curfew instant → `decision=deny reason=curfew exit 1`; an out-of-curfew instant → `decision=deny`/`allow` per window. (Note: the guard denies on `curfew` even out-of-window only if not allowed; verify the window math against 20:45→05:30.)
4. **Auto-revert works:** hand-edit `config.yaml`, fire the guard, assert it byte-copies `config.sanctioned.yaml` back (`reverted=true`) and `HMAC(config)` matches `config_hmac` again.
5. **Adapter translates:** feed each guard reason through the adapter, assert the correct butler message + `{continue:false}`.
6. **ONLY on all-green:** edit `settings.json` `UserPromptSubmit` to replace `curfew_guard.ps1` with `nightguard_adapter.ps1`; restart the watchdog task; confirm StayFree relaunches (the WIRE-01 acceptance signal, D-05).

### Anti-Patterns to Avoid
- **`$PSScriptRoot\..` / `$MyInvocation\..` to find the DATA dir.** This is the blocker. The guard's `$here\..\interop` is fine (it finds its own dot-source tree); deriving `NIGHTGUARD_DIR` from script location is NOT (junction-dependent). Always use the env var for the data dir.
- **Hardcoding butler messages in the adapter.** They live in `config.yaml` (`message`/`tamper_message`/`offline_message`); read them there so there is one source.
- **Setting `NIGHTGUARD_DIR` and immediately expecting the *already-running* watchdog task to see it.** The currently-running task process was spawned before the var exists; it will only pick up a user-scope var on a fresh spawn. Restart the task (`Start-ScheduledTask` after `Stop`/re-register) so a fresh `powershell.exe` inherits the new var. `[VERIFIED: env semantics]`
- **Using `serde_yaml` / any comment-destroying writer on `config.yaml`.** KERN-04 + the PS minimal parser require format preservation; use `yamlpatch`/`yamlpath` per the project stack.
- **`Get-Content` to read bytes for HMAC.** Normalizes EOL/BOM → false tamper. The interop layer already forbids this.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 32-byte key generation + DPAPI protect | Custom rand + CryptProtectData call | `load_or_create_key` (trust-kernel) | Generate-once/load-thereafter + 32-byte canary already proven cross-language |
| state_hmac computation | A second JSON-canonicalize+HMAC | `GuardState::compute_state_hmac` (the A3 recipe) | The ONE locked recipe; any divergence = guard treats state as tampered every fire |
| Monday week-anchor | `now - weekday`, `+7*24h` | `most_recent_monday_midnight` (week.rs) | DST-aware; naive math is forbidden anti-pattern T-02-06 |
| Integrity baseline re-stamp | New hashing script | `verify_hook_integrity.ps1 -Update` | Self-registers guard+verifier+interop; raw-byte SHA256, no EOL normalization |
| Curfew window verdict (UI) | New evaluator | `lock_status` (mutation-engine) | Pure, schedule-aware, fail-safe-LOCKED, 11 tests green |
| YAML field edits | Line surgery / serde_yaml | `yamlpatch`/`yamlpath` | Comment/format preserving (KERN-04) |

**Key insight:** every cryptographic and time-math primitive this phase needs is already built and *parity-proven*. The risk is entirely in *wiring and ordering*, not in new logic — do not re-implement any signing or time math.

## Runtime State Inventory

> Rename/refactor/migration phase — this is a LIVE cutover. All five categories answered explicitly.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | Two divergent `config.yaml` copies: canonical `LifeOS/nightguard/config.yaml` (20:45→05:30, enabled, watchdog.enabled:true, Jun 4) and stale `~/.claude/nightguard/config.yaml` (21:50→06:00, disabled, watchdog.enabled:false, Jun 2). No `guard.json`, no `.guardkey`, no sanctioned snapshot exist anywhere yet (instance never initialized). Logs under `~/.claude/nightguard/`: `curfew.log`, `watchdog.log`, `browser_lock.log`, `zen_lock.log`. `LifeOS/nightguard/curfew.log` is the live diag log. | Normalize `LifeOS/nightguard/config.yaml` to product schema; seed sanctioned + sign guard.json; generate .guardkey. The stale `~/.claude/nightguard/config.yaml` becomes orphaned — leave or delete (not read post-cutover). `browser_lock.log`/`zen_lock.log` are deferred (out of scope). `[VERIFIED]` |
| **Live service config** | `NightguardWatchdog` Scheduled Task: **State=Running**, action `powershell.exe -Loop -File C:\Users\20252128\.claude\hooks\nightguard_app_watchdog.ps1`. Claude Code `settings.json` `UserPromptSubmit` runs `curfew_guard.ps1` (the active gate); `SessionStart` runs the OLD `verify_hook_integrity.ps1` (a no-op stub that just prints `hook_integrity=ok` — it does NOT actually verify anything). `~/.claude/hooks/config.yaml` is a Hermes manifest listing `discipline/curfew_guard.ps1` under `before_prompt` (generator source, not directly executed by CC). | Re-register the watchdog task to point at the rewritten `nightguard_watchdog.ps1`; edit `settings.json` `UserPromptSubmit` to swap `curfew_guard.ps1` → `nightguard_adapter.ps1`; optionally wire the REAL `verify_hook_integrity.ps1` into `SessionStart` (replacing the stub). `[VERIFIED: live task + settings.json]` |
| **OS-registered state** | `NightguardWatchdog` task hardcodes the script path `~/.claude/hooks/nightguard_app_watchdog.ps1` in its action Arguments (set at registration time — editing the script file is NOT enough; the task points at the *old filename*). Task runs `-LogonType Interactive -RunLevel Limited` as the user (so it inherits user env). | Must RE-REGISTER the task (the existing `nightguard_install_watchdog.ps1` pattern) with the new script path/name; merely deploying a new file won't repoint it. `[VERIFIED: task Arguments]` |
| **Secrets/env vars** | `NIGHTGUARD_DIR` is **UNSET in User, Machine, and Process scopes** (verified live). No `.guardkey` exists yet. DPAPI invariant: CurrentUser scope + `None`/`$null` entropy on BOTH Rust and PS (locked Phase 1). | SET user-scope `NIGHTGUARD_DIR = C:\Users\20252128\dev\Projects\LifeOS\nightguard`. Generate `.guardkey` via `load_or_create_key`. `[VERIFIED]` |
| **Build artifacts / installed packages** | The published scripts live in-repo under `scripts/guard/` + `scripts/interop/`; they are NOT yet deployed to `LifeOS/hooks`. `~/.claude/hooks` is a junction → `LifeOS/hooks`, so deploy writes there. The Rust app (`src-tauri`) is built but not run against this instance. StayFree UWP installed at `37081StayFreeApps.StayFree3_3.3.2.0_x64__fqhk48m1tsma0`. | Deploy guard+adapter+watchdog+interop+verifier into `LifeOS/hooks` (preserving `hooks/interop/` sibling); re-stamp baseline; (optionally) build+run the Tauri app pointed at the instance. `[VERIFIED]` |

**Canonical question — after every repo file is updated, what runtime systems still hold the old string?** (1) The Scheduled Task's hardcoded script-path argument (re-register required). (2) `settings.json` `UserPromptSubmit` command string (edit required). (3) The currently-running watchdog process (restart required to pick up `NIGHTGUARD_DIR`). (4) `~/.claude/nightguard/config.yaml` — orphaned but physically present; nothing reads it post-cutover, so leaving it is harmless, but it is a future-confusion trap.

## Config Schema Normalization (D-09, KERN-04)

### Canonical LifeOS config (the migration source-of-truth), key by key
Verified contents of `LifeOS/nightguard/config.yaml`:
```yaml
timezone: Europe/Amsterdam
curfew:
  enabled: true
  start: "20:45"
  end: "05:30"
  allow_commands: ["/shutdown"]
  block_when_offline: true
  message: "Mi señor, it is past {start} ..."
  tamper_message: "Mi señor, the clock appears to have been tampered with. Nice try. ..."
  offline_message: "Mi señor, I cannot verify the time (no network). ..."
clock_protection:
  enabled: true
  max_offset_minutes: 5
watchdog:
  enabled: true
  check_interval_seconds: 15
  apps:
    - name: StayFree
      type: uwp
      package_id: "37081StayFreeApps.StayFree3_fqhk48m1tsma0!stayfree"
      process_name: StayFree
```

**Important finding: NEITHER live config contains a `schedule.<day>` block.** D-03 says "per-day schedule is carried over" — but there is currently no per-day override to carry; the curfew is a single 20:45→05:30 window every day. The product-canonical maximal-lockout literal (guard lines 169–195) DOES emit a full `schedule.<day>` block, and both `lock_status` (Rust) and the legacy parser support `schedule.<day>`. **Recommendation: do NOT invent a schedule block; preserve the single-window form (`curfew.start`/`curfew.end`).** Both readers fall back to `start`/`end` when `schedule` is absent. If the author later wants per-day, the schema already supports it. Flag this to the planner: D-03 is satisfied by *supporting* schedule, not by *adding* one. `[VERIFIED: both live configs + lock_status.rs precedence rule]`

### Key-by-key migration mapping (old → product)
The product-canonical schema is defined by what the guard's maximal-lockout literal writes (lines 169–195) + what `lock_status` reads + what `state.rs`/commit signs. The good news: **the LifeOS config is ALREADY in product schema** — the keys line up. The only real normalization is byte-canonicalization (UTF-8/no-BOM/LF/one-trailing-LF) so HMAC + PS parser agree.

| Key (in LifeOS config) | Product key | Owner (who WRITES) | Who READS | Notes |
|------------------------|-------------|--------------------|-----------|-------|
| `timezone` | `timezone` | Rust writer (yamlpatch) | guard (curfew window day), lock_status, week/grace day-math | Already `Europe/Amsterdam` |
| `curfew.enabled` | same | Rust writer | guard, lock_status | true |
| `curfew.start` / `curfew.end` | same | Rust writer | guard window math, lock_status | 20:45 / 05:30 — preserve exactly (D-10) |
| `curfew.allow_commands` | same | Rust writer (left as list) | adapter (allow-pass check) | `["/shutdown"]`. NOTE: the *published guard* (`nightguard_guard.ps1`) does NOT read `allow_commands` — it has no stdin/prompt parsing. The ADAPTER must implement the allow-command pass (the legacy gate did it before invoking curfew logic). Flag to planner. |
| `curfew.block_when_offline` | same | Rust writer | guard (the guard hardcodes offline→deny; this key is advisory in the new model — guard ALWAYS denies on ntp-unreachable) | true |
| `curfew.message` / `tamper_message` / `offline_message` | same | left ALONE by Rust writer | **adapter** (D-02 butler messages) | The Rust writer/classifier doesn't touch these; they are pure presentation read by the adapter |
| `clock_protection.enabled` / `max_offset_minutes` | same | left alone / advisory | guard hardcodes a 300s (5-min) tamper threshold (line 494) | The guard's tamper threshold is HARDCODED at 300s, NOT read from config. `max_offset_minutes:5` matches by luck. Flag: config value is currently ignored by the published guard. |
| `watchdog.enabled` | same | Rust writer / left alone | **watchdog** | true (the WIRE-01 fix vs stale false) |
| `watchdog.check_interval_seconds` | same | left alone | watchdog loop | 15 |
| `watchdog.apps[].{name,type,package_id,process_name}` | same | left alone | watchdog | StayFree UWP block |

**Which keys the Rust product writer (yamlpatch) OWNS vs leaves alone:** The classifier/commit path only edits the *curfew direction-classified fields* (`curfew.enabled`, `curfew.start`, `curfew.end` — the fields the Phase 4 edit panel exposes and `classify.rs` labels). Everything else — `message`/`tamper_message`/`offline_message`, `clock_protection.*`, `watchdog.*`, `allow_commands`, `block_when_offline` — is read by the adapter/watchdog/guard but **left untouched** by the writer (the Phase 4 edit panel only does per-field line edits on classified fields, leaving absent/other fields untouched — verified 04-05). The whole file is HMAC-signed, so even untouched keys are integrity-protected: hand-editing `watchdog.enabled` triggers auto-revert. `[VERIFIED: classify.rs scope + 04-05 note]`

## Deploy / Install Step

**Target:** `LifeOS/hooks/` (reached via the `~/.claude/hooks` junction). Preserve the `hooks/interop/` sibling so the guard's `..\interop` dot-source resolves.

**Steps:**
1. Copy `scripts/guard/nightguard_guard.ps1`, `scripts/guard/verify_hook_integrity.ps1`, `scripts/guard/guard.baseline.sha256` → `LifeOS/hooks/`.
2. Copy `scripts/interop/nightguard_interop.ps1`, `scripts/interop/state_interop.ps1` → `LifeOS/hooks/interop/`.
3. Deploy the NEW `nightguard_adapter.ps1` and `nightguard_watchdog.ps1` → `LifeOS/hooks/`.
4. **Re-stamp the baseline:** run `verify_hook_integrity.ps1 -Update` (it self-registers `nightguard_guard.ps1`, `verify_hook_integrity.ps1`, `interop/nightguard_interop.ps1`, `interop/state_interop.ps1`). NOTE: its `$registered` array uses repo-relative paths `scripts/guard/...` + `scripts/interop/...` and computes `$repoRoot = $here\..\..`. When deployed under `LifeOS/hooks/`, those relative paths and the repoRoot derivation will NOT match the deployed layout. **The planner must either (a) keep `verify_hook_integrity.ps1` running from the repo against the repo copies (integrity of the *source*), or (b) parameterize its `$registered`/`$repoRoot` for the deployed layout.** This is a real mismatch — flag it. `[VERIFIED: verify_hook_integrity.ps1 lines 30–45]`
5. **What must be re-stamped:** the four registered scripts' SHA256 — but ONLY after deploy, and only against whichever copy (repo vs deployed) the verifier is pointed at. The baseline must reflect the EXACT bytes that will be present at verify time (raw-byte SHA256, EOL-sensitive — `.gitattributes` already pins `scripts/guard/*.ps1 -text` and the interop config to prevent CRLF drift; the deploy copy must preserve bytes exactly, e.g. `[IO.File]::Copy`, NOT `Get-Content|Set-Content`).
6. Re-register the `NightguardWatchdog` task (new script path) and `settings.json` `UserPromptSubmit` swap — ONLY after the D-11 verify gate is green.

## Go-Live Armed State (D-10) — exact initial `guard.json`

```json
{
  "config_hmac": "<hex(HMAC(canonical config.yaml bytes))>",
  "state_hmac": "<computed via A3 over the blanked struct>",
  "weekly_spent": 0,
  "week_anchor": "2026-06-08",
  "ledger": [],
  "grace": null
}
```
- `weekly_spent: 0` → all 3 tokens available. `[from D-10]`
- `grace: null` → no grace used today (guard line 216 reads `grace == null` as "not used"). `[VERIFIED]`
- `week_anchor: "2026-06-08"` → the Monday of the current week (Europe/Amsterdam) for a 2026-06-09 go-live, from `most_recent_monday_midnight`. If go-live slips to a later date, recompute. `[VERIFIED: week.rs]`
- Curfew 20:45→05:30 + watchdog on live in `config.yaml`, not `guard.json`. `[from config + D-10]`
- StayFree restored is a *consequence* of the watchdog reading `watchdog.enabled:true` + `process_name:StayFree` and relaunching via `shell:AppsFolder\37081StayFreeApps.StayFree3_fqhk48m1tsma0!stayfree`. `[VERIFIED]`

## StayFree Process Name (D-07) — RESOLVED

`process_name: StayFree` is **CORRECT**. The UWP package `37081StayFreeApps.StayFree3` ships a single application whose executable is `app\StayFree.exe`, so the running process name is `StayFree` (no `.exe` in `Get-Process -Name`). `[VERIFIED: Get-AppxPackageManifest → Application Executable = app\StayFree.exe; InstallLocation confirmed]`

**Caveat for robustness:** at research time StayFree was **NOT running** (consistent with D-05's broken watchdog), so I could not confirm the *live* process name by observation — only by the manifest executable name. UWP apps occasionally spawn a differently-named host process, but a packaged-app exe named `StayFree.exe` reliably surfaces as `Get-Process -Name StayFree`. **Recommendation:** keep `Get-Process -Name StayFree`; as a belt-and-suspenders the rewritten watchdog could ALSO check `Get-Process | Where-Object MainModule.FileName -like '*StayFree*'` or fall back to the PFN via `Get-AppxPackage`, but the simple name match is correct. The relaunch via `shell:AppsFolder\<PFN>!stayfree` is the verified-correct mechanism. Verify live by launching StayFree once and running `Get-Process -Name StayFree` during the D-11 gate. `[VERIFIED manifest / ASSUMED live — confirm in gate]`

## Common Pitfalls

### Pitfall 1: `NIGHTGUARD_DIR` unset at cutover → guard throws → fail-OPEN
**What goes wrong:** The guard and adapter `throw` when `NIGHTGUARD_DIR` is empty. If a thrown PowerShell hook causes Claude Code to *allow* the prompt (the common default for a hook that errors), the author is UNPROTECTED the instant the legacy gate is removed.
**Why it happens:** `NIGHTGUARD_DIR` is currently unset; the legacy `curfew_guard.ps1` doesn't need it (absolute path), so the dependency is invisible until cutover.
**How to avoid:** (1) Set the env var FIRST, verify it in a fresh process. (2) Make the ADAPTER catch any guard throw/non-zero-non-1 exit and emit fail-closed `{continue:false}`. (3) Run the D-11 gate (which exercises the guard against the real dir) before the `settings.json` swap.
**Warning signs:** guard stderr "no data dir"; prompts going through during curfew.

### Pitfall 2: Stale running watchdog never sees the new env var
**What goes wrong:** You set `NIGHTGUARD_DIR`, deploy the new watchdog, but the *already-running* task process (spawned before the var existed) keeps running the OLD script with no env var → still broken.
**How to avoid:** `Stop-ScheduledTask` (or unregister) → re-register with the new path → `Start-ScheduledTask` so a FRESH `powershell.exe` inherits the user env. `[VERIFIED: env inheritance is per-process-at-spawn]`
**Warning signs:** watchdog.log shows no new "restarting" lines; StayFree stays dead.

### Pitfall 3: Deploy byte-corruption breaks the integrity baseline or HMAC
**What goes wrong:** Copying scripts with `Get-Content|Set-Content` (or a CRLF-normalizing tool) changes bytes → `verify_hook_integrity` reports false drift, or a re-stamp bakes wrong bytes.
**How to avoid:** Use byte-exact copy (`[IO.File]::Copy`/`Copy-Item`), re-stamp AFTER deploy, and rely on the `.gitattributes -text` pins already in place.

### Pitfall 4: The guard's `..\interop` dot-source fails in the deployed layout
**What goes wrong:** Guard lands in `LifeOS/hooks/` but interop scripts don't land in `LifeOS/hooks/interop/` → `Join-Path $here '..\interop\...'` throws on every fire.
**How to avoid:** Deploy preserves the sibling `interop/` dir under `hooks/`. `[VERIFIED: guard lines 38–40]`

### Pitfall 5: `verify_hook_integrity.ps1` repoRoot/relpath assumptions break post-deploy
**What goes wrong:** The verifier hardcodes `scripts/guard/...` relpaths and `$repoRoot = $here\..\..`; under `LifeOS/hooks/` those don't resolve.
**How to avoid:** Decide deployment-vs-repo integrity scope (see Deploy step 4). Flag as a planning decision. `[VERIFIED]`

## State of the Art

| Old (Hermes) Approach | New (Product) Approach | Impact |
|-----------------------|------------------------|--------|
| `curfew_guard.ps1` reads config, decides, blocks — all in one hook with its own NTP + minimal parser | Guard = host-agnostic oracle (`{decision,reason}`+exit); thin adapter translates to CC schema | Single enforcement engine shared by app+guard; messages decoupled |
| No HMAC, no signing, no sanctioned snapshot, no token/grace | DPAPI-keyed HMAC over config+state; auto-revert; 3-token/week budget; 8-min grace | The actual anti-me guarantee |
| Watchdog reads `~/.claude/nightguard/config.yaml` (stale, disabled) | Watchdog reads `NIGHTGUARD_DIR` canonical config (enabled) | WIRE-01 drift fixed; StayFree restored |
| `verify_hook_integrity.ps1` = no-op stub printing `hook_integrity=ok` | Real SHA256 baseline verifier (GARD-06) | Tampering with the guard scripts is now detected |

**Deprecated/orphaned:**
- `nightguard_curfew_guard.ps1` — referenced nowhere; dead. (The CONTEXT named it as the active gate; it is NOT.)
- `stayfree_watchdog.ps1` — a thin delegator to the old watchdog; superseded.
- The OLD `~/.claude/hooks/verify_hook_integrity.ps1` stub + `hooks.sha256` — superseded by the product verifier.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Live StayFree process name is `StayFree` (confirmed via manifest exe, not a running process) | D-07 | Watchdog never relaunches; confirm live in the D-11 gate by launching StayFree once |
| A2 | Claude Code's current `UserPromptSubmit` block schema is `{"continue": false, "reason": "..."}` on stdout (the legacy orphan used `{decision:'block',reason}`; the active gate used `exit 2` + stderr) | Adapter contract | Adapter blocks won't register → prompts go through at curfew. MUST confirm exact CC schema before writing the adapter |
| A3 | No in-repo init/bootstrap binary exists; the planner must add an `init` seam or drive init via the Tauri app | Pattern 3 | If a hidden init path exists, reuse it instead of building one |
| A4 | The published guard does NOT read `allow_commands`, `clock_protection.max_offset_minutes`, or `block_when_offline` from config (tamper threshold hardcoded 300s; offline always denies); the adapter must own the allow-command pass | Schema mapping | If the planner assumes the guard honors these, allow-commands (`/shutdown`) won't pass during curfew |
| A5 | Re-stamping the baseline against the deployed copy requires parameterizing `verify_hook_integrity.ps1`'s repoRoot/relpaths | Deploy step 4 / Pitfall 5 | A blind re-stamp from the repo verifies the wrong bytes |

## Open Questions

1. **Exact Claude Code `UserPromptSubmit` block schema (the adapter's output contract).**
   - What we know: legacy orphan emitted `{decision:'block',reason}` on stdout; the active `curfew_guard.ps1` uses `[Console]::Error.WriteLine($reason); exit 2`. CC hook schemas have changed across versions.
   - What's unclear: whether the current CC version blocks on `{"continue": false}` JSON, on a specific exit code (2?), or on `decision:block`. The author's CC is recent (Opus 4.8 era).
   - Recommendation: the planner/executor must inspect the installed CC's hook docs or test empirically (a no-op block hook) during the D-11 gate, BEFORE the settings.json swap. The adapter must be confirmed to actually block.

2. **Init seam (Rust `init` subcommand vs Tauri-app-driven).**
   - What we know: `load_or_create_key` + `compute_state_hmac` exist; `state_interop_cli` writes only a fixed test state.
   - Recommendation: add a small `init`/`bless-initial` subcommand to a Rust bin that takes the data dir + D-10 values and performs steps 3–6, with a PS parity assertion. Cleaner and testable than launching the GUI.

3. **`config.sanctioned.yaml` vs `config.yaml` byte-identity at init.**
   - The guard's `Test-SanctionedValid` requires `HMAC(sanctioned) == config_hmac`. At init, sanctioned must be a byte-exact copy of the (canonicalized) config so the first verify passes. Confirm the init writes them as identical bytes.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `~/.claude/hooks` junction → `LifeOS/hooks` | Deploy target | ✓ | Junction | — |
| `NightguardWatchdog` Scheduled Task | Watchdog delivery (D-06) | ✓ (State=Running) | — | Re-register |
| StayFree UWP | Watchdog target (D-05/D-07) | ✓ installed (not running) | 3.3.2.0 | — |
| `NIGHTGUARD_DIR` env var | All four consumers (WIRE-02) | ✗ UNSET (all scopes) | — | **None — must be set; blocking** |
| `LifeOS/nightguard/config.yaml` | Migration source | ✓ | Jun 4 | — |
| `.guardkey` / `guard.json` / sanctioned | Instance state (WIRE-02) | ✗ never initialized | — | **None — init creates them; blocking** |
| Windows PowerShell 5.1 | All hooks/scripts | ✓ | 5.1.26100 | Scripts already 5.1-safe (ASCII) |
| Rust toolchain (MSVC) + built app | Init signing | ✓ (Phase 1–4 built) | — | — |

**Missing dependencies with no fallback (BLOCKING — this phase creates them):**
- `NIGHTGUARD_DIR` env var (set in this phase).
- `.guardkey`, `guard.json`, `config.sanctioned.yaml` (initialized in this phase).

These are the *deliverables*, not external blockers — but the cutover MUST NOT remove the legacy gate until they exist and verify (D-11).

## Sources

### Primary (HIGH confidence — verified this session)
- Live machine probes: `Get-Item .claude\hooks` (LinkType=Junction → LifeOS\hooks); `[Environment]::GetEnvironmentVariable('NIGHTGUARD_DIR',*)` (all empty); user-scope env round-trip to a fresh process; `Get-ScheduledTask NightguardWatchdog` (State=Running, action args); `Get-AppxPackage *StayFree*` + `Get-AppxPackageManifest` (exe = app\StayFree.exe, PFN `37081StayFreeApps.StayFree3_fqhk48m1tsma0`); `Get-Process` (StayFree not running).
- In-repo (read in full): `scripts/guard/nightguard_guard.ps1`, `scripts/guard/verify_hook_integrity.ps1`, `scripts/guard/guard.baseline.sha256`, `scripts/interop/nightguard_interop.ps1`, `scripts/interop/state_interop.ps1`, `src-tauri/src/commands.rs` (AppCtx::load), `src-tauri/src/lib.rs`, `crates/trust-kernel/src/key.rs`, `crates/mutation-engine/src/state.rs`, `crates/mutation-engine/src/week.rs`, `crates/mutation-engine/src/lock_status.rs`, `crates/mutation-engine/src/bin/state_interop_cli.rs`.
- Live system: `~/.claude/hooks/{curfew_guard.ps1, nightguard_curfew_guard.ps1, nightguard_app_watchdog.ps1, nightguard_install_watchdog.ps1, stayfree_watchdog.ps1, config.yaml, verify_hook_integrity.ps1, hooks.sha256}`; `~/.claude/settings.json` (hooks block); `~/.claude/nightguard/{config.yaml, watchdog.log}`; `LifeOS/nightguard/config.yaml`.
- Planning: `.planning/phases/05-instance-wiring/05-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/config.json`.

### Secondary
- Phase 1–4 STATE.md decision log (A3 recipe, commit ordering, DPAPI invariants, lock_status precedence).

## Metadata

**Confidence breakdown:**
- Junction-safe resolution (Q1): HIGH — junction confirmed, env var unset confirmed, fresh-process visibility proven, guard/app resolution code read.
- StayFree process name (Q2): HIGH (manifest) / MEDIUM (live, not running at research time — confirm in gate).
- Schema normalization (Q3): HIGH — both configs + all readers inspected; finding "no schedule block exists" is verified.
- Adapter contract (Q4): MEDIUM — guard vocabulary verified exactly; the *CC-side* block schema is the one open item (A2/Open Q1).
- Init/bootstrap order (Q5): HIGH for primitives (key.rs, state.rs, week.rs all read); MEDIUM for the seam (no init binary exists yet — planning decision).
- Deploy/baseline re-stamp (Q6): HIGH — verifier + baseline read; the repoRoot/layout mismatch is a flagged real issue.
- Armed state (Q7): HIGH — all field values + week anchor derived from verified code + config.

**Research date:** 2026-06-09
**Valid until:** 7 days for the live-env facts (env vars / task state / running processes can change); 30 days for the in-repo code facts.

*Note: `workflow.nyquist_validation` is `false` in config.json — Validation Architecture section intentionally omitted. `security_enforcement` is not present as an explicit key; the security-relevant controls (DPAPI, HMAC, fail-closed, integrity baseline) are covered inline under Pitfalls + Patterns and were established/verified in Phases 1–3.*
