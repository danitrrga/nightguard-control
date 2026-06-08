# verify_hook_integrity.ps1 -- in-repo SHA256 integrity baseline for the guard scripts (D-10 / GARD-06).
#
# Closes the highest-leverage attack on a self-binding tool: silently replacing, editing, or
# deleting the enforcement guard itself. This script records the SHA256 of each protected guard
# script in a committed baseline manifest (scripts/guard/guard.baseline.sha256) and, on a plain
# run, recomputes those hashes and raises a non-zero alert on ANY drift.
#
# The REGISTERED SET self-includes this script (verify_hook_integrity.ps1), so neutering the
# integrity check by editing it also trips the baseline (threat T-03-17). The guard itself
# (nightguard_guard.ps1) is registered so replacing/disabling it trips the baseline (T-03-16).
#
# USAGE:
#   verify_hook_integrity.ps1            # VERIFY: recompute + compare vs baseline; exit 0 clean, 1 on drift.
#   verify_hook_integrity.ps1 -Update    # WRITE:  (re)generate the baseline manifest, exit 0.
#
# INVARIANTS:
#   - Hashing uses [Get-FileHash -Algorithm SHA256], which reads RAW bytes (no EOL/encoding
#     normalization) -> a stable baseline that is not perturbed by checkout line-ending policy.
#     NEVER hash via Get-Content (it normalizes and would produce false drift).
#   - Manifest form: "<sha256-lowercase-hex><two spaces><forward-slash-relative-path>" per line,
#     ASCII, written LF-only.

[CmdletBinding()]
param([switch]$Update)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --- Locate this script and the repo root (scripts/guard/.. /.. = repo root) -----------------
$here     = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $here '..\..')).Path
$manifest = Join-Path $here 'guard.baseline.sha256'

# --- The protected set: relative (forward-slash) paths of the guard scripts to baseline -------
# Self-registers verify_hook_integrity.ps1 so editing EITHER script trips the check.
$registered = @(
    'scripts/guard/nightguard_guard.ps1',
    'scripts/guard/verify_hook_integrity.ps1'
)

function Get-GuardFileHash {
    param([Parameter(Mandatory)][string]$RelPath)
    $abs = Join-Path $repoRoot $RelPath
    if (-not (Test-Path -LiteralPath $abs -PathType Leaf)) { return $null }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $abs).Hash.ToLowerInvariant()
}

# =============================================================================================
# -Update mode: (re)write the baseline manifest against the CURRENT bytes of the guard scripts.
# =============================================================================================
if ($Update) {
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($rel in $registered) {
        $hash = Get-GuardFileHash -RelPath $rel
        if ($null -eq $hash) {
            throw "verify_hook_integrity -Update: registered script is missing on disk: $rel"
        }
        $lines.Add(("{0}  {1}" -f $hash, $rel))
    }
    # ASCII, LF-only, no trailing BOM. Join with LF and append a single trailing LF.
    $text = ($lines -join "`n") + "`n"
    [System.IO.File]::WriteAllText($manifest, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "=== verify_hook_integrity -Update ==="
    Write-Host ("Wrote baseline: {0}" -f $manifest)
    foreach ($l in $lines) { Write-Host ("  {0}" -f $l) }
    exit 0
}

# =============================================================================================
# Default (verify) mode: recompute each registered hash and compare against the baseline.
# =============================================================================================
$results = New-Object System.Collections.Generic.List[object]
function Add-Check {
    param([string]$Name, [bool]$Pass, [string]$Detail)
    $status = if ($Pass) { 'PASS' } else { 'FAIL' }
    Write-Host ("[{0}] {1} -- {2}" -f $status, $Name, $Detail)
    $results.Add([PSCustomObject]@{ Name = $Name; Pass = $Pass; Detail = $Detail })
}

Write-Host ""
Write-Host "=== Nightguard guard-script integrity check (D-10 / GARD-06) ==="
Write-Host ("Repo root: {0}" -f $repoRoot)
Write-Host ("Manifest:  {0}" -f $manifest)
Write-Host ("PowerShell: {0}" -f $PSVersionTable.PSVersion)
Write-Host ""

# The baseline manifest must exist; absence is itself a drift/tamper condition -> fail closed.
if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
    Add-Check -Name 'baseline present' -Pass $false -Detail "missing manifest: $manifest (run with -Update to create)"
    Write-Host ""
    Write-Host "=== Summary: FAIL (no baseline) ==="
    exit 1
}

# Parse the manifest into an ordered map of relpath -> expected-hash.
$baseline = @{}
$baselineOrder = New-Object System.Collections.Generic.List[string]
foreach ($raw in [System.IO.File]::ReadAllLines($manifest)) {
    $line = $raw.Trim()
    if ($line.Length -eq 0) { continue }
    # Split on the first run of two+ spaces: "<hash>  <relpath>".
    $idx = $line.IndexOf('  ')
    if ($idx -lt 0) {
        Add-Check -Name 'manifest line' -Pass $false -Detail "malformed manifest line: '$line'"
        continue
    }
    $h   = $line.Substring(0, $idx).Trim().ToLowerInvariant()
    $rel = $line.Substring($idx).Trim()
    $baseline[$rel] = $h
    $baselineOrder.Add($rel)
}

# Check 1..N: every manifest entry recomputes to its baseline hash, and the file still exists.
foreach ($rel in $baselineOrder) {
    $expected = $baseline[$rel]
    $actual   = Get-GuardFileHash -RelPath $rel
    if ($null -eq $actual) {
        Add-Check -Name "integrity: $rel" -Pass $false -Detail "ALERT: registered script MISSING on disk (removed/renamed)"
    }
    elseif ($actual -ne $expected) {
        Add-Check -Name "integrity: $rel" -Pass $false -Detail "ALERT: SHA256 drift -- expected $expected got $actual"
    }
    else {
        Add-Check -Name "integrity: $rel" -Pass $true -Detail "sha256 matches baseline ($expected)"
    }
}

# Cross-check: every script in the REGISTERED set must appear in the manifest. A registered
# script that is absent from the baseline (added-but-unbaselined) is unprotected -> fail.
foreach ($rel in $registered) {
    if (-not $baseline.ContainsKey($rel)) {
        Add-Check -Name "registered: $rel" -Pass $false -Detail "ALERT: registered script NOT in baseline (run -Update)"
    }
}

Write-Host ""
$failed = @($results | Where-Object { -not $_.Pass })
if ($failed.Count -eq 0) {
    Write-Host ("=== Summary: PASS ({0} registered scripts match baseline) ===" -f $baselineOrder.Count)
    exit 0
}
else {
    Write-Host ("=== Summary: FAIL ({0} drift/alert) ===" -f $failed.Count)
    exit 1
}
