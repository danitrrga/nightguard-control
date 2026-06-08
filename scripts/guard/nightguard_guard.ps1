# nightguard_guard.ps1 -- the always-firing reader/enforcer (Phase 3 guard).
#
# This is the single, clock-free integrity half of the nightguard guard. It runs UNCONDITIONALLY
# every fire (no NTP needed) and enforces the anti-me guarantees the Rust mutation-engine signs:
#   - config-verify: HMAC(config.yaml) must equal guard.json.config_hmac, else revert.
#   - circuit-breaker: while the app holds .nightguard.lock, skip the revert this cycle (GARD-05).
#   - revert: copy the sanctioned snapshot over a hand-edited config.yaml (GARD-01).
#   - maximal-lockout: if BOTH live and sanctioned are invalid, write a hardcoded 24/7-curfew,
#     no-grace, zero-token default (GARD-02 / D-03) -- corruption buys the impulsive user nothing.
#   - state-verify: on a guard.json state_hmac mismatch, runtime-substitute weekly_spent=3 and
#     grace-as-used (GARD-03 / D-04); the guard NEVER re-signs guard.json (D-05).
#
# The grace/curfew VERDICT, SNTP true-time, audit log, and JSON stdout (GARD-04 / D-02) are plan 03;
# this plan leaves the script computing $reverted / $failClosed / $weeklySpent / $graceUsed only.
#
# LOCKED INVARIANTS (inherited from Phase 1/2):
#   - The guard NEVER signs. Revert is a byte copy; lockout is a hardcoded literal; a state
#     mismatch substitutes runtime values only. Re-blessing is the Rust DPAPI repair's job.
#   - DPAPI: CurrentUser, $null entropy, raw blob (the 32-not-64 length canary catches SecureString framing).
#   - All HMAC inputs are RAW file bytes; config writes use Write-RawBytes (no Get-Content/Set-Content).
#
# Windows PowerShell 5.1 compatible: ASCII only (the -File launcher chokes on em-dashes / smart
# quotes), [HMACSHA256]/[IO.File]/[ProtectedData] are identical .NET types in 5.1 and 7.

[CmdletBinding()]
param(
    # D-09: the single base directory holding all fixed-name guard files. -DataDir overrides
    # $env:NIGHTGUARD_DIR; if neither is set the guard throws (fail-closed, never guesses).
    [string]$DataDir,
    # Plan-03 test seam (mirrors Rust FakeTrueTime): inject NTP true-time for the verdict gate.
    # Ignored in this plan; -1 means "use real SNTP" once plan 03 wires the verdict.
    [int64]$NtpOverrideUnixSecs = -1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here '..\interop\nightguard_interop.ps1')
. (Join-Path $here '..\interop\state_interop.ps1')

# --- D-09: resolve the single base data dir, then the fixed filenames within it ----------------
if ([string]::IsNullOrWhiteSpace($DataDir)) {
    $DataDir = $env:NIGHTGUARD_DIR
}
if ([string]::IsNullOrWhiteSpace($DataDir)) {
    throw "nightguard: no data dir (pass -DataDir or set NIGHTGUARD_DIR)"
}

# Fixed filenames (planner-locked per CONTEXT D-09); every path is rooted at the one base dir.
$cfgLive       = Join-Path $DataDir 'config.yaml'
$cfgSanctioned = Join-Path $DataDir 'config.sanctioned.yaml'
$guardJson     = Join-Path $DataDir 'guard.json'
$lockPath      = Join-Path $DataDir '.nightguard.lock'
$keyBlobPath   = Join-Path $DataDir '.guardkey'
$auditLog      = Join-Path $DataDir 'guard-audit.log'   # written by plan 03; declared here for completeness

# --- DPAPI key load + 32-not-64 canary ---------------------------------------------------------
# Unprotect-GuardKey is dot-sourced (DPAPI CurrentUser, $null entropy). A SecureString/UTF-16
# framing bug would return 64 bytes instead of 32 -- assert the raw length is the canary.
$blob = Get-FileBytes -Path $keyBlobPath
$key  = Unprotect-GuardKey -Blob $blob
if ($key.Length -ne 32) {
    throw "guardkey canary: expected 32 raw bytes, got $($key.Length)"
}

# --- Test-LockHeld: the plan-01-PROVEN circuit-breaker probe (D-06) -----------------------------
# The lock file persists once the app first commits, so its mere EXISTENCE is NOT the held-signal.
# Probe by attempting an exclusive (deny-share) open: an IOException means the app holds it now.
function Test-LockHeld {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$LockPath)
    if (-not (Test-Path $LockPath)) {
        return $false   # never created -> no commit ever ran -> not held
    }
    try {
        $fs = [System.IO.File]::Open($LockPath, 'Open', 'ReadWrite', 'None')
        $fs.Close()
        return $false   # opened exclusively -> the app does NOT hold it
    } catch [System.IO.IOException] {
        return $true    # exclusive open refused -> the app holds it -> skip revert this cycle
    }
}

# --- Get-RuntimeStateHmac: the plan-01-PROVEN runtime state_hmac re-derivation (A3 recipe) ------
# Reads the PRETTY on-disk guard.json, blanks state_hmac, re-serializes COMPACT (-Depth 10
# MANDATORY), appends exactly one trailing 0x0A, then HMACs with the 32 raw key bytes. Returns
# both the lowercase-hex tag AND the parsed object so the caller reads config_hmac / weekly_spent /
# week_anchor / grace. Defensive (V5 / Phase 2 A2): a missing or unparseable guard.json, or any
# missing field, sets Valid=$false (state-invalid -> worst-case), never a permissive loosen.
function Get-RuntimeStateHmac {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][byte[]]$Key,
        [Parameter(Mandatory)][string]$GuardJson
    )
    $result = [PSCustomObject]@{
        Valid     = $false
        Tag       = ''
        Expected  = ''
        Obj       = $null
    }
    try {
        if (-not (Test-Path $GuardJson)) { return $result }
        $jsonText = [System.Text.Encoding]::UTF8.GetString((Get-FileBytes -Path $GuardJson))
        $obj = $jsonText | ConvertFrom-Json
        # Required fields must all be present; a forged/truncated state is state-invalid, not a loosen.
        foreach ($field in @('config_hmac', 'state_hmac', 'weekly_spent', 'week_anchor')) {
            if (-not ($obj.PSObject.Properties.Name -contains $field)) { return $result }
        }
        $result.Obj      = $obj
        $result.Expected = [string]$obj.state_hmac

        # A3 recipe: blank state_hmac, compact re-serialize, append one 0x0A, HMAC.
        $obj.state_hmac = ''
        $compact = $obj | ConvertTo-Json -Compress -Depth 10
        $bytes   = [System.Text.Encoding]::UTF8.GetBytes($compact)
        $canon   = New-Object byte[] ($bytes.Length + 1)
        [Array]::Copy($bytes, $canon, $bytes.Length)
        $canon[$bytes.Length] = 0x0A   # canon.rs: exactly one trailing LF, UTF-8, no BOM
        $hmac = [System.Security.Cryptography.HMACSHA256]::new($Key)
        try {
            $result.Tag = ConvertTo-LowerHex -Bytes $hmac.ComputeHash($canon)
        } finally {
            $hmac.Dispose()
        }
        $result.Valid = $true
        return $result
    } catch {
        # Any parse/HMAC failure -> state-invalid (worst-case). Never throw into a permissive state.
        return $result
    }
}

# --- Verdict-input variables (Task 2 sets the config/state branches; plan 03 reads these) -------
$reverted    = $false
$failClosed  = $false
$weeklySpent = 3       # default to worst-case until state-verify proves otherwise (fail-closed)
$graceUsed   = $true   # default to grace-as-used until state-verify proves otherwise

# Task 2 fills the config-verify -> circuit-breaker -> revert/lockout path and the state-verify
# substitution here, all BEFORE any clock-dependent logic.

# Plan 03 replaces this tail with the SNTP verdict + audit log + JSON stdout (GARD-04 / D-02).
exit 0
