# Phase 3: Enforcement Guard - Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 5 new / 2 modified-or-extended
**Analogs found:** 5 / 5 (every new file has a strong in-repo analog)

This phase is almost entirely **re-derivation of existing Rust contracts in PowerShell 5.1**.
There is no greenfield architecture: each new guard file copies an established Phase 1/2 pattern
(dot-source the interop libs, sign canonical raw bytes, fail-closed on tamper/NTP, gate on
`$LASTEXITCODE`). The only genuinely new code is the SNTP UDP packet, the verdict computation,
the HMAC-chained audit log, and the SHA256 integrity baseline.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/guard/nightguard_guard.ps1` | guard / reader-enforcer | request-response (host fires -> verdict) + file-I/O | `scripts/interop/state_interop.ps1` (dot-source pattern) + `crates/mutation-engine/src/commit.rs` (revert rule) | role-match (PS) + contract-mirror (Rust) |
| `scripts/guard/verify_hook_integrity.ps1` | utility / integrity tool | file-I/O (SHA256 over scripts) | `scripts/interop/nightguard_interop.ps1` (helper-lib style) + `run_interop_gate.ps1` (Add-Check/exit pattern) | role-match |
| `scripts/guard/guard.baseline.sha256` | config / manifest | n/a (static data) | none (new artifact; flat `sha256<2sp>path` per line) | no analog (trivial) |
| `scripts/guard/run_guard_gate.ps1` | test / exit-gate | batch (drive fixtures, assert, exit 0/1) | `scripts/interop/run_state_interop_gate.ps1` | exact |
| `scripts/interop/run_state_interop_gate.ps1` (EXTEND) | test / exit-gate | batch | itself (add runtime state-verify check) | exact (self) |

**State-verify recipe source of truth:** `crates/mutation-engine/src/state.rs`
`GuardState::compute_state_hmac` (the A3 recipe the guard re-derives in PowerShell).

## Pattern Assignments

### `scripts/guard/nightguard_guard.ps1` (guard / reader-enforcer, request-response + file-I/O)

**Primary analog (PS structure):** `scripts/interop/state_interop.ps1`
**Contract analogs (Rust behavior to mirror byte-for-byte):** `commit.rs`, `state.rs`,
`grace.rs`, `ntp.rs`.

**Header + strict-mode + dot-source pattern** — copy from `state_interop.ps1` lines 18-22:
```powershell
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here '..\interop\nightguard_interop.ps1')
. (Join-Path $here '..\interop\state_interop.ps1')
```
> The guard dot-sources BOTH interop libs for ALL DPAPI/HMAC/byte primitives. Do NOT
> reimplement `Protect/Unprotect-GuardKey`, `Get-FileBytes`, `Write-RawBytes`,
> `Get-FileHmacHex`, `ConvertTo/From-LowerHex`. ASCII-only file (WinPS 5.1 `-File` chokes on
> em-dashes / smart quotes).

**DPAPI key unwrap + 32-not-64 canary** — reuse `nightguard_interop.ps1` `Unprotect-GuardKey`
(lines 36-43) then assert length, copying the canary intent documented at lines 37-38:
```powershell
$blob = Get-FileBytes -Path $keyBlobPath
$key  = Unprotect-GuardKey -Blob $blob
if ($key.Length -ne 32) { throw "guardkey canary: expected 32 raw bytes, got $($key.Length)" }
```

**A. Config-verify + revert (GARD-01/02/05)** — mirrors the revert rule documented in
`crates/mutation-engine/src/commit.rs` lines 9-18 (the convergence contract) and reuses
`Get-FileHmacHex` (`nightguard_interop.ps1` lines 82-98). The exact rule to mirror, verbatim
from `commit.rs` lines 10-12:
> `if HMAC(config.yaml) != guard.json.config_hmac -> copy config.sanctioned.yaml over config.yaml`

```powershell
# Source: nightguard_interop.ps1 Get-FileHmacHex + commit.rs revert rule (lines 9-18)
$liveHmac = Get-FileHmacHex -KeyBytes $key -Path $cfgLive   # raw on-disk bytes; Rust wrote them canonical
$guardObj = ([System.Text.Encoding]::UTF8.GetString((Get-FileBytes $guardJson))) | ConvertFrom-Json
if ($liveHmac -ne $guardObj.config_hmac) {
    if (Test-LockHeld $lockPath) { $reverted = $false }                 # D-06 circuit-breaker: skip this cycle
    elseif (Test-SanctionedValid $cfgSanctioned $guardObj.config_hmac $key) {
        [System.IO.File]::Copy($cfgSanctioned, $cfgLive, $true); $reverted = $true   # idempotent revert copy
    } else {
        Write-MaximalLockoutDefault $cfgLive; $reverted = $true; $failClosed = $true # D-03
    }
}
```
> `Get-FileHmacHex` hashes RAW on-disk bytes (`[IO.File]::ReadAllBytes`); the canonical writer
> guarantees one trailing LF, no BOM, no CR (see `trust-kernel/src/canon.rs` lines 5-6). Any
> byte change (incl. cosmetic CRLF/BOM) flips the tag -> revert. Direction-agnostic by design.

**Circuit-breaker lock probe (D-06)** — the lock is owned by Rust `with_commit_lock`
(`commit.rs` lines 61-81): `OpenOptions` + `fd_lock::RwLock::write()` = Windows `LockFileEx`
+ `LOCKFILE_EXCLUSIVE_LOCK` at `<lock_dir>/.nightguard.lock`. The guard only PROBES presence
(not acquisition). File existence is NOT the signal (the file persists once created — see
`commit.rs` "Never truncate" note line 67-68). Probe by attempting an exclusive open:
```powershell
function Test-LockHeld {
    param([string]$LockPath)
    if (-not (Test-Path $LockPath)) { return $false }   # never created -> no commit ever ran
    try {
        $fs = [System.IO.File]::Open($LockPath, 'Open', 'ReadWrite', 'None')  # deny-share
        $fs.Close(); return $false                       # opened -> app does NOT hold it
    } catch [System.IO.IOException] { return $true }     # locked -> app holds it -> skip revert
}
```
> OPEN QUESTION (RESEARCH §Open Questions 1): this cross-language probe is the one mechanism
> not yet spiked. Planner must validate against a live Rust harness holding the lock.

**B. State-verify (GARD-03) — the central A3 parity recipe.** Mirror
`crates/mutation-engine/src/state.rs` `compute_state_hmac` lines 49-56 exactly. Rust:
```rust
let mut blanked = self.clone();
blanked.state_hmac = String::new();
let json = serde_json::to_string(&blanked)            // COMPACT, struct-field order
    .expect("GuardState is always serializable to JSON");
let canon = canonicalize_bytes(json.as_bytes());      // canon.rs: no BOM, LF, +1 trailing LF
tag_to_hex(&sign_bytes(key, &canon))
```
PowerShell re-derivation (VERIFIED byte-identical this research session) — note the on-disk
`guard.json` is `to_vec_pretty` (indented) but the tag signs the COMPACT re-serialization:
```powershell
# Source: state.rs compute_state_hmac (49-56) + canon.rs (25-57)
$obj = ([System.Text.Encoding]::UTF8.GetString((Get-FileBytes $guardJson))) | ConvertFrom-Json
$expectedTag = $obj.state_hmac
$obj.state_hmac = ''                                            # blank (recipe step 1)
$compact = $obj | ConvertTo-Json -Compress -Depth 10           # serde to_string parity; -Depth 10 MANDATORY
$bytes   = [System.Text.Encoding]::UTF8.GetBytes($compact)     # UTF-8, NO BOM
$canon   = New-Object byte[] ($bytes.Length + 1)
[Array]::Copy($bytes, $canon, $bytes.Length); $canon[$bytes.Length] = 0x0A   # canon: one trailing LF
$hmac = [System.Security.Cryptography.HMACSHA256]::new($key)
try { $tag = ConvertTo-LowerHex $hmac.ComputeHash($canon) } finally { $hmac.Dispose() }
if ($tag -ne $expectedTag) { $weeklySpent = 3; $graceUsed = $true }   # D-04 runtime worst-case (no write)
```
> LOCKED field order from `state.rs` lines 26-39:
> `config_hmac, state_hmac, weekly_spent, week_anchor, ledger, grace`. `ConvertFrom-Json`
> preserves it. Pitfalls: `-Depth 10` is mandatory (default 2 truncates `ledger[].fields` to
> `"System.Object[]"`); NEVER hash the on-disk pretty bytes. The guard NEVER writes a re-signed
> state (that is the Rust repair's job, D-05) — on mismatch it only substitutes runtime values.

**C. Grace/curfew verdict (GARD-04) + guard-side SNTP.** Mirror the fail-closed posture of
`grace.rs` lines 7-16 (NtpUnreachable -> refuse, never the local clock) and `ntp.rs` lines
36-55 (`NtpUnreachable` is the only failure; no `SystemTime::now()` fallback). The verdict
compares the SNTP true-now against `guard.json.grace.window_end` (`state.rs` lines 69-77).
```powershell
# Source: ntp.rs fail-closed contract + RESEARCH §Pattern 3 (chrisjwarwick 48-byte SNTP)
function Get-GuardNtpUnixSecs {
    param([string]$Server = 'time.cloudflare.com', [int]$TimeoutMs = 2000)
    try {
        $packet = New-Object byte[] 48; $packet[0] = 0x1B          # LI=0,VN=3,Mode=3 client
        $sock = New-Object System.Net.Sockets.Socket('InterNetwork','Dgram','Udp')
        $sock.ReceiveTimeout = $TimeoutMs; $sock.SendTimeout = $TimeoutMs
        $sock.Connect($Server, 123); [void]$sock.Send($packet); [void]$sock.Receive($packet)
        $sock.Close()
        $secs = ([uint32]$packet[40] -shl 24) -bor ([uint32]$packet[41] -shl 16) `
              -bor ([uint32]$packet[42] -shl 8) -bor [uint32]$packet[43]
        return [int64]$secs - 2208988800L                          # NTP(1900) -> unix(1970)
    } catch { return $null }                                       # fail-closed: caller treats $null as NtpUnreachable
}
# Verdict: $trueNow = Get-GuardNtpUnixSecs; if $null -> decision=deny, fail_closed=true (D-07).
# else if $obj.grace -ne $null -and $obj.grace.window_end -gt $trueNow -> allow, grace_remaining = window_end - trueNow.
# else -> deny (curfew). Clock-tamper: |$trueNow - localUnix| > skewThreshold -> treat as offline/deny (A4: >5 min).
```
> Add a `-NtpOverrideUnixSecs` test seam param (mirrors Rust `FakeTrueTime`, `ntp.rs` lines
> 124-148) so the verdict gate injects true-time deterministically; production uses real SNTP.

**Output contract (D-01/D-02)** — emit JSON on stdout + exit code:
```powershell
$verdict = [PSCustomObject]@{
    decision = $decision; reason = $reason; grace_remaining_secs = $graceRemaining
    reverted = $reverted; fail_closed = $failClosed
}
$verdict | ConvertTo-Json -Compress -Depth 5
if ($decision -eq 'allow') { exit 0 } else { exit 1 }   # exit 0 = allow, non-zero = deny
```
> Deliberately NOT the Claude-Code `{continue,decision,reason}` schema (host-agnostic, D-02).

---

### `scripts/guard/verify_hook_integrity.ps1` (utility / integrity tool, file-I/O)

**Analog:** `scripts/interop/nightguard_interop.ps1` (helper-lib header/strict-mode style) +
`run_interop_gate.ps1` lines 51-73 (Add-Check / PASS-FAIL / exit pattern).
> This file does NOT exist yet — confirmed by grep (only referenced in planning docs). It is
> a NEW in-repo script (D-10), not an extension.

**Header + strict-mode** — copy `nightguard_interop.ps1` lines 1-23 style (ASCII-only banner,
`Set-StrictMode -Version Latest`, `$ErrorActionPreference = 'Stop'`).

**SHA256 baseline + drift check** — use the WinPS-native hasher (RESEARCH Standard Stack /
Alternatives: either is fine):
```powershell
# Compute baseline (self-register the guard scripts):
$hash = (Get-FileHash -Algorithm SHA256 -Path $scriptPath).Hash.ToLowerInvariant()
# Manifest line form (D-10 discretion): "<sha256><two spaces><relative-path>" per line.
# Drift check: recompute each manifest entry; any mismatch/missing -> Write-Host alert + exit 1.
```
> `Get-FileHash` reads raw bytes (no EOL normalization) -> safe for a baseline. Self-registers
> `nightguard_guard.ps1` AND `verify_hook_integrity.ps1` so altering/removing either alerts.

---

### `scripts/guard/run_guard_gate.ps1` (test / exit-gate, batch)

**Analog:** `scripts/interop/run_state_interop_gate.ps1` (EXACT — copy its whole skeleton).

**Build/Invoke-Cli/Add-Check/work-dir/summary skeleton** — copy from
`run_state_interop_gate.ps1`:
- Header + strict-mode + dot-source (lines 1-27).
- `Invoke-Cli` native-call wrapper with relaxed `$ErrorActionPreference` gated on
  `$LASTEXITCODE` (lines 49-60) — needed for the fd-lock Rust harness and any cargo build.
- Temp work dir under `target\` on the same volume (lines 62-65).
- `Add-Check` PASS/FAIL collector (lines 67-73) and the `=== Summary ===` / `exit 0|1`
  verdict block (lines 171-186).
- Shared-key setup: PS protects a known 32-byte key, Rust/guard consume it (lines 82-87).

**Checks to add** (RESEARCH §Phase Requirements -> Test Map): GARD-01 tamper-live->revert,
GARD-02 both-invalid->maximal-lockout, GARD-04 grace-honored/expired/offline-deny (via
`-NtpOverrideUnixSecs`), GARD-05 lock-held->skip-revert (drive a Rust harness holding
`.nightguard.lock`).

---

### `scripts/interop/run_state_interop_gate.ps1` (EXTEND, test / exit-gate, batch)

**Analog:** itself. Add ONE check that exercises the **runtime** state-verify path (parse
pretty `guard.json` -> compact re-derive -> HMAC), not just the `.signbytes` gate-only path.
Insert a new `Add-Check` block after Check 3 (after line 169), reusing the exact A3 recipe from
the `nightguard_guard.ps1` State-verify section above. Assert the in-PS re-derived tag equals
the on-disk `guard.json.state_hmac` for an untampered Rust-written `guard.json`.
> Closes RESEARCH Wave 0 gap: prove the runtime recipe (not `.signbytes`) before the phase gate.

## Shared Patterns

### DPAPI + HMAC + byte-I/O primitives (reused, never reimplemented)
**Source:** `scripts/interop/nightguard_interop.ps1` (lines 25-98)
**Apply to:** `nightguard_guard.ps1` (all crypto paths); `verify_hook_integrity.ps1` (byte reads).
```powershell
# Dot-source, then call — do NOT hand-roll any of these:
Protect-GuardKey / Unprotect-GuardKey   # DPAPI CurrentUser, $null entropy, raw blob (25-43)
Get-FileBytes / Write-RawBytes          # [IO.File]::ReadAllBytes/WriteAllBytes ONLY (45-60)
Get-FileHmacHex                         # HMAC-SHA256 over raw file bytes -> lowercase hex (82-98)
ConvertTo-LowerHex / ConvertFrom-LowerHex  # hex parity with Rust hex::encode (62-80)
```
> FORBIDDEN (lines 12-16): `Get-Content` for any HMAC input (normalizes EOL/encoding -> false
> tamper); `ConvertTo/From-SecureString` (UTF-16 framing -> 64-byte key, the 32-not-64 canary).

### Canonical byte form (the bytes every HMAC signs over)
**Source:** `crates/trust-kernel/src/canon.rs` (lines 25-57) — no BOM, LF-only, exactly one
trailing LF. **Apply to:** the state-verify recipe (append one `0x0A` after the compact JSON);
relied on implicitly for config (Rust already wrote `config.yaml` canonical).

### state_hmac A3 recipe (the LOCKED parity contract)
**Source:** `crates/mutation-engine/src/state.rs` `compute_state_hmac` (lines 49-56) +
field-order struct (lines 26-39). **Apply to:** `nightguard_guard.ps1` state-verify AND the
extended `run_state_interop_gate.ps1` check. Compact (`to_string`) re-serialization, NOT the
on-disk pretty bytes.

### Fail-closed posture (anti-me lodestar)
**Source:** `grace.rs` lines 7-16 + `ntp.rs` lines 36-55 (NtpUnreachable -> refuse, no clock
fallback); `state.rs` `MutationError` (lines 85-106). **Apply to:** every guard edge —
NTP-offline -> deny grace (D-07); state-tamper -> `weekly_spent=3`+grace-used (D-04);
both-config-invalid -> maximal-lockout (D-03). When in doubt, the more-restrictive branch wins.

### WinPS 5.1 exit-gate harness conventions
**Source:** `run_state_interop_gate.ps1` (lines 22-73, 171-186) + `run_interop_gate.ps1`.
**Apply to:** `run_guard_gate.ps1` and the gate extension. ASCII-only; relax
`$ErrorActionPreference` to `'Continue'` around native cargo/CLI calls and gate on
`$LASTEXITCODE`; `Add-Check` collector; `exit 0`/`exit 1` verdict.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `scripts/guard/guard.baseline.sha256` | config / manifest | static data | New artifact; a flat `sha256<2sp>path` manifest (or JSON, D-10 discretion). Trivial, no pattern to copy. |
| Guard-side SNTP packet (function inside `nightguard_guard.ps1`) | n/a | streaming/UDP | No PowerShell networking exists in-repo. `ntp.rs` is the Rust analog for the fail-closed CONTRACT (lines 36-55), but the 48-byte UDP packet itself is new (RESEARCH §Pattern 3, cited external source). Mirror only the fail-closed posture, not the Rust transport. |

## Metadata

**Analog search scope:** `scripts/interop/` (all 5 files), `crates/mutation-engine/src/`
(commit, state, grace, ntp), `crates/trust-kernel/src/canon.rs`,
`crates/mutation-engine/src/bin/state_interop_cli.rs`.
**Files scanned:** 10 read in full/targeted; `verify_hook_integrity.ps1` confirmed nonexistent via grep.
**Pattern extraction date:** 2026-06-08
