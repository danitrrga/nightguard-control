# Phase 5: Instance Wiring - Pattern Map

**Mapped:** 2026-06-09
**Files analyzed:** 7 new/modified artifacts
**Analogs found:** 7 / 7 (every artifact has a strong in-repo or live-system analog)

> This phase is a **live in-place cutover**, not greenfield. Almost nothing is invented: every
> crypto, time, and integrity primitive already exists and is parity-proven (Phases 1-4). The work
> is **wiring + ordering**, so most "analogs" are *exact code to copy or thin-adapt*, not loose
> inspiration. Language is called out per file (PowerShell vs Rust).

## File Classification

| New/Modified File | Lang | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|------|-----------|----------------|---------------|
| `LifeOS/hooks/nightguard_adapter.ps1` (NEW) | PowerShell | middleware (hook seam) | request-response (stdin prompt -> block/allow) | `LifeOS/hooks/curfew_guard.ps1` (legacy gate) + guard output contract (`nightguard_guard.ps1` lines 569-583) | exact (composite) |
| `LifeOS/hooks/nightguard_watchdog.ps1` (NEW, rewrite) | PowerShell | service (liveness loop) | event-driven (timed poll + relaunch) | `LifeOS/hooks/nightguard_app_watchdog.ps1` (legacy watchdog) | role+flow exact (rewrite-in-place) |
| Config normalization step (init substep) | Rust | utility/migration | transform (YAML -> canonical bytes) | `Write-MaximalLockoutDefault` (`nightguard_guard.ps1` lines 165-199) for canonical-byte form; schema source = `LifeOS/nightguard/config.yaml` | role-match |
| Instance-init seam (NEW Rust `init`/`bless-initial` bin subcommand) | Rust | service/bin | batch (key gen + sign + write) | `state_interop_cli.rs` `cmd_emit_state_hmac` (lines 100-130) + `AppCtx::load` (commands.rs 95-120) | role-match (no init bin exists yet) |
| Deploy/install step (NEW PS install script) | PowerShell | config (deployment) | file-I/O (byte-copy + task register) | `nightguard_install_watchdog.ps1` (task register) + deploy layout in RESEARCH | role-match |
| Integrity-baseline re-stamp (invocation, not new code) | PowerShell | utility | transform (hash -> manifest) | `verify_hook_integrity.ps1 -Update` (lines 57-73) | exact (reuse as-is, flag repoRoot mismatch) |
| `~/.claude/settings.json` UserPromptSubmit edit + Scheduled-Task re-register (live config) | n/a | config (OS-registered state) | n/a | `nightguard_install_watchdog.ps1` Register pattern | role-match |

---

## Pattern Assignments

### `LifeOS/hooks/nightguard_adapter.ps1` (NEW — PowerShell, middleware/hook seam, request-response)

**Analogs (composite):**
- `LifeOS/hooks/curfew_guard.ps1` — the legacy gate being replaced; source of butler-message contract, allow-command pass, stdin-prompt parse, and the `Console::Error.WriteLine + exit 2` block mechanism.
- `scripts/guard/nightguard_guard.ps1` lines 569-583 — the host-agnostic verdict the adapter must translate.

**Data-dir resolution stanza to copy verbatim** (from `nightguard_guard.ps1` lines 42-48 — the fail-closed throw is mandatory, do NOT use `$PSScriptRoot`):
```powershell
$DataDir = $env:NIGHTGUARD_DIR
if ([string]::IsNullOrWhiteSpace($DataDir)) {
    throw "nightguard: no data dir (set NIGHTGUARD_DIR)"   # fail-closed, never guess
}
```

**Guard verdict vocabulary to translate** (`nightguard_guard.ps1` lines 572-583):
```powershell
$verdict = [PSCustomObject]@{
    decision               = $decision   # 'allow' | 'deny'
    reason                 = $reason      # 'curfew' | 'grace active' | 'ntp unreachable' | 'clock tamper'
    grace_remaining_secs   = $graceRemaining
    reverted               = $reverted
    fail_closed            = $failClosed
    audit_chain_broken     = $auditChainBroken
    audit_chain_break_index = $auditChainBreakIndex
}
$verdict | ConvertTo-Json -Compress -Depth 5
if ($decision -eq 'allow') { exit 0 } else { exit 1 }
```

**Translation table the adapter implements** (from RESEARCH Pattern 2):

| Guard exit | Guard `reason` | Adapter emits (CC schema) | Butler message (read from `config.yaml`) |
|-----------|----------------|----------------------------|------------------------------------------|
| 0 | allow / `grace active` | allow, let prompt through | — |
| 1 | `curfew` | block (`{continue:false}`) | `curfew.message` (substitute `{start}`/`{end}`) |
| 1 | `clock tamper` | block | `curfew.tamper_message` |
| 1 | `ntp unreachable` | block | `curfew.offline_message` |
| throw / non-0-non-1 / no JSON | — | block (fail-closed) | `curfew.offline_message` (safest) |

**Allow-command pass + stdin-prompt parse — copy from legacy `curfew_guard.ps1` lines 72-78** (the published guard does NOT read `allow_commands`; the adapter must own this, per RESEARCH A4):
```powershell
$stdin = [Console]::In.ReadToEnd()
$prompt = ''
try { $payload = $stdin | ConvertFrom-Json; $prompt = [string]$payload.prompt } catch {}
foreach ($cmd in $config['curfew']['allow_commands']) {
    if ($cmd -and $prompt -match [regex]::Escape($cmd)) { exit 0 }
}
```

**Butler messages to preserve — copy literal strings/`$n = [char]0x00F1` n-tilde handling from `curfew_guard.ps1` lines 87-126.** Read the live strings from `config.yaml` (`curfew.message` / `tamper_message` / `offline_message`), do NOT hardcode in the adapter (RESEARCH anti-pattern).

**OPEN (A2 / blocking the executor):** the EXACT current Claude-Code `UserPromptSubmit` block schema is unconfirmed — legacy orphan used `{decision:'block',reason}` on stdout; the active `curfew_guard.ps1` used `exit 2` + stderr. The adapter's output contract MUST be confirmed empirically before the `settings.json` swap (D-11 gate).

---

### `LifeOS/hooks/nightguard_watchdog.ps1` (NEW rewrite — PowerShell, service, event-driven loop)

**Analog:** `LifeOS/hooks/nightguard_app_watchdog.ps1` (the legacy watchdog, rewritten in place).

**What to KEEP unchanged from the legacy script:**
- The `-Loop` param + while-loop + `Start-Sleep` shape (lines 7-9, 113-127).
- The per-app `Get-Process -Name $processName` liveness probe and UWP relaunch via `explorer.exe shell:AppsFolder\$packageId` (lines 81-105). StayFree process name `StayFree` is VERIFIED correct (RESEARCH D-07); PFN `37081StayFreeApps.StayFree3_fqhk48m1tsma0!stayfree`.
- The minimal YAML `apps[]` parser (lines 17-71) — KERN-04-readable form; the canonical config keeps the same `watchdog.apps[]` layout.

**What MUST change (the WIRE-01 fix, D-04/D-05):**
- Config source. Legacy line 13 hardcodes the STALE path:
```powershell
# LEGACY (the bug): reads stale ~/.claude copy where watchdog.enabled:false
$configPath = Join-Path $env:USERPROFILE '.claude\nightguard\config.yaml'
```
  Replace with the SAME env-var resolution stanza every consumer uses (from `nightguard_guard.ps1` 42-48):
```powershell
$DataDir = $env:NIGHTGUARD_DIR
if ([string]::IsNullOrWhiteSpace($DataDir)) { throw "nightguard: no data dir (set NIGHTGUARD_DIR)" }
$configPath = Join-Path $DataDir 'config.yaml'
```
- Log path likewise moves under `$DataDir` (legacy hardcodes `~/.claude\nightguard\watchdog.log`, line 73).

**The early-return that was silently disarming it** (legacy lines 78-79 — this returns every cycle when reading the stale `enabled:false`; against canonical `enabled:true` it proceeds and StayFree relaunches — the WIRE-01 acceptance signal):
```powershell
$config = Read-SimpleYaml -Path $configPath
if ($config['watchdog']['enabled'] -eq 'false') { return }
```

---

### Config normalization (init substep — Rust, utility/migration, transform)

**Analog (canonical-byte form):** `Write-MaximalLockoutDefault` in `nightguard_guard.ps1` lines 165-199 — shows the EXACT canonical byte contract every config write must honor:
```powershell
$text = ($lines -join "`n") + "`n"                 # LF-only, exactly one trailing LF
$bytes = [System.Text.Encoding]::UTF8.GetBytes($text)  # UTF-8, no BOM
Write-RawBytes -Path $ConfigPath -Bytes $bytes
```

**Migration source-of-truth:** `LifeOS/nightguard/config.yaml` is ALREADY in product schema (RESEARCH Config Schema section — keys line up). The only real normalization is **byte-canonicalization** (UTF-8 / no-BOM / LF / exactly one trailing LF) so the PS minimal parser (KERN-04) and the Rust HMAC agree on the same bytes.

**Do NOT invent a `schedule.<day>` block** (RESEARCH finding): neither live config has one; both readers fall back to `curfew.start`/`curfew.end`. D-03 is satisfied by *supporting* schedule, not adding one.

**Writer ownership** (RESEARCH Schema table): the Rust writer (yamlpatch) touches only classified curfew fields (`curfew.enabled`/`start`/`end`); `message`/`tamper_message`/`offline_message`, `clock_protection.*`, `watchdog.*`, `allow_commands`, `block_when_offline` are left untouched but still HMAC-covered. Use `yamlpatch`/`yamlpath` — NEVER `serde_yaml` (KERN-04).

---

### Instance-init seam (NEW Rust `init`/`bless-initial` bin subcommand — service/bin, batch)

**No init binary exists yet** (RESEARCH A3) — the planner adds an `init` subcommand. Two analogs to compose:

**Analog 1 — `state_interop_cli.rs` `cmd_emit_state_hmac` lines 100-130** (the write-signed-guard.json pattern; the init bin mirrors this but with REAL D-10 values instead of `fixed_guard_state()`):
```rust
let key = load_or_create_key(Path::new(key_path)).map_err(|e| e.to_string())?;
let mut state = /* real armed state, NOT fixed_guard_state() */;
let tag_hex = state.compute_state_hmac(&key);   // the ONE locked A3 recipe (state.rs 49-56)
state.state_hmac = tag_hex.clone();
let filled = serde_json::to_string(&state).map_err(...)?;
std::fs::write(out_json_path, filled.as_bytes()).map_err(...)?;
```

**Analog 2 — `AppCtx::load` (commands.rs 95-120)** for the path layout + key load:
```rust
let data_dir = match std::env::var("NIGHTGUARD_DIR") { Ok(d) if !d.trim().is_empty() => PathBuf::from(d), _ => return Err(...) };
// fixed paths: config.yaml / config.sanctioned.yaml / guard.json / .nightguard.lock / .guardkey
let key = load_or_create_key(&data_dir.join(".guardkey"))?;  // generate-once / load-thereafter (key.rs 41-60)
```

**The A3 state_hmac recipe (state.rs 49-56) — reuse, never re-implement:**
```rust
pub fn compute_state_hmac(&self, key: &[u8; 32]) -> String {
    let mut blanked = self.clone();
    blanked.state_hmac = String::new();
    let json = serde_json::to_string(&blanked).expect("...");
    let canon = canonicalize_bytes(json.as_bytes());
    tag_to_hex(&sign_bytes(key, &canon))
}
```

**Armed initial `GuardState` field values (D-10, RESEARCH Go-Live section):**
```
config_hmac  = HMAC(canonical config.yaml bytes)   // lowercase hex
state_hmac   = "" then computed via A3
weekly_spent = 0                                   // all 3 tokens available
week_anchor  = "2026-06-08"                         // most_recent_monday_midnight(now, "Europe/Amsterdam") -> Monday; recompute if go-live slips
ledger       = []
grace        = null                                // guard line 216 reads null == not used
```
Week anchor via `most_recent_monday_midnight` (week.rs line 23) — DST-aware; never naive math.

**Sanctioned seed:** byte-copy the normalized `config.yaml` to `config.sanctioned.yaml` so `HMAC(sanctioned) == config_hmac` (guard's `Test-SanctionedValid` lines 141-156 requires this exact identity).

---

### Deploy / install step (NEW PowerShell install script — config, file-I/O)

**Analog — `nightguard_install_watchdog.ps1`** for the Scheduled-Task re-register (lines 24-52). The task RE-REGISTER is mandatory: it hardcodes the script path in its Arguments, so editing the file is not enough (RESEARCH OS-registered-state row):
```powershell
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`" -Loop"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'NightguardWatchdog' -Action $action -Trigger $trigger -Settings $settings -Principal $principal ...
Start-ScheduledTask -TaskName 'NightguardWatchdog'   # fresh spawn inherits the new NIGHTGUARD_DIR env var
```
Repoint `$scriptPath` from the legacy `nightguard_app_watchdog.ps1` to the new `nightguard_watchdog.ps1`.

**Deploy target = `LifeOS/hooks/` (via the `~/.claude/hooks` junction).** Preserve the `hooks/interop/` sibling dir or the guard's `..\interop` dot-source throws (`nightguard_guard.ps1` lines 38-40):
```powershell
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here '..\interop\nightguard_interop.ps1')
. (Join-Path $here '..\interop\state_interop.ps1')
```

**Byte-exact copy mandatory** — use `[IO.File]::Copy` / `Copy-Item`, NEVER `Get-Content|Set-Content` (CRLF normalization breaks both the SHA256 baseline and HMAC; RESEARCH Pitfall 3).

---

### Integrity-baseline re-stamp (PowerShell — reuse, do NOT rewrite)

**Analog — `verify_hook_integrity.ps1 -Update` lines 57-73** (run AFTER deploy). It self-registers the four trust-surface scripts:
```powershell
$registered = @(
    'scripts/guard/nightguard_guard.ps1',
    'scripts/guard/verify_hook_integrity.ps1',
    'scripts/interop/nightguard_interop.ps1',
    'scripts/interop/state_interop.ps1'
)
# -Update: SHA256 each (Get-FileHash, raw bytes), write "<hash>  <relpath>" LF-only manifest
```

**FLAG (RESEARCH A5 / Pitfall 5):** `$registered` uses repo-relative paths and `$repoRoot = $here\..\..` (line 31). Under the deployed `LifeOS/hooks/` layout these do NOT resolve. The planner must decide: (a) run the verifier from the repo against repo copies (source integrity), or (b) parameterize `$registered`/`$repoRoot` for the deployed layout. Do not blind-restamp.

---

### `settings.json` UserPromptSubmit + Scheduled-Task (live OS-registered state — edit, not new code)

**Two runtime edits, ONLY after the D-11 gate is green:**
1. `~/.claude/settings.json` `UserPromptSubmit`: swap `curfew_guard.ps1` -> `nightguard_adapter.ps1`. (Also delete the orphan `nightguard_curfew_guard.ps1`; non-load-bearing.)
2. Re-register `NightguardWatchdog` -> new `nightguard_watchdog.ps1`, then `Start-ScheduledTask` so a fresh process inherits `NIGHTGUARD_DIR` (RESEARCH Pitfall 2).

---

## Shared Patterns

### Junction-safe data-dir resolution (applies to: adapter, watchdog, AND the Rust init bin)
**Source:** `nightguard_guard.ps1` lines 42-48 (PS) / `AppCtx::load` commands.rs 95-99 (Rust).
**Rule:** every consumer resolves the data dir from absolute `$env:NIGHTGUARD_DIR` and FAILS CLOSED when empty. NEVER `$PSScriptRoot\..` for the *data* dir (the `hooks` junction makes it non-deterministic). The guard's `$here\..\interop` is the one allowed script-relative resolve — it finds its own dot-source tree, not data.
```powershell
# PS consumers (adapter, watchdog)
$DataDir = $env:NIGHTGUARD_DIR
if ([string]::IsNullOrWhiteSpace($DataDir)) { throw "nightguard: no data dir (set NIGHTGUARD_DIR)" }
```
```rust
// Rust (init bin mirrors AppCtx::load)
let data_dir = match std::env::var("NIGHTGUARD_DIR") {
    Ok(d) if !d.trim().is_empty() => PathBuf::from(d),
    _ => return Err(IpcError::NotInitialized),
};
```

### Canonical-byte file writes (applies to: config normalization, sanctioned seed, guard.json)
**Source:** `Write-MaximalLockoutDefault` (`nightguard_guard.ps1` 196-198) / `canonicalize_bytes` (trust-kernel).
**Rule:** UTF-8, no BOM, LF-only, exactly one trailing LF. PS reads raw bytes via `Get-FileBytes` / writes via `Write-RawBytes` (`nightguard_interop.ps1`) — NEVER `Get-Content`/`Set-Content` (false tamper). Crypto primitives available: `Protect-GuardKey`/`Unprotect-GuardKey`/`Get-FileBytes`/`Write-RawBytes`/`ConvertTo-LowerHex`/`Get-FileHmacHex` (interop lines 25-82).

### Signing recipe (applies to: init bin only)
**Source:** `GuardState::compute_state_hmac` (state.rs 49-56) — the SINGLE locked A3 recipe, proven byte-identical Rust<->PS (02-05). The guard NEVER signs (locked invariant); only the Rust host signs. Verify parity with the PS side via `Get-RuntimeStateHmac` (`nightguard_guard.ps1` 91-133).

### Fail-closed everywhere
**Source:** guard throughout (every error branch -> deny / worst-case). The adapter MUST emit a block on any guard throw/non-0-non-1/no-JSON (RESEARCH Pitfall 1 — unset `NIGHTGUARD_DIR` at cutover is the biggest landmine: it makes the guard throw on every fire).

---

## No Analog Found

| File | Lang | Role | Reason |
|------|------|------|--------|
| (none — full coverage) | | | Every artifact maps to a concrete in-repo or live-system analog. The init bin is the weakest: no init *binary* exists, but its two halves (`cmd_emit_state_hmac` write pattern + `AppCtx::load` resolution) are exact and just need composing with real D-10 values. |

## Metadata

**Analog search scope:** `scripts/guard/`, `scripts/interop/`, `src-tauri/src/`, `crates/trust-kernel/src/`, `crates/mutation-engine/src/`, live `LifeOS/hooks/`.
**Files scanned (read for excerpts):** `nightguard_guard.ps1`, `verify_hook_integrity.ps1`, `commands.rs`, `lib.rs`, `key.rs`, `state.rs`, `state_interop_cli.rs`, `week.rs`, `nightguard_interop.ps1`, live `curfew_guard.ps1`, `nightguard_app_watchdog.ps1`, `nightguard_install_watchdog.ps1`.
**Pattern extraction date:** 2026-06-09
