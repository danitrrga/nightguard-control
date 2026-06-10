# run_cutover_gate.ps1 -- the D-11 prove-then-switch verify gate (run BEFORE retiring the old gate).
#
# Exercises the REAL LifeOS/nightguard instance (NIGHTGUARD_DIR) + the repo guard/adapter, asserting
# the five D-11 properties in order. Exits 0 only if EVERY check PASSes; exits 1 on ANY failure.
# Leaves the instance armed + verifying (restores config.yaml from the sanctioned snapshot at the
# end of the auto-revert test). Run BEFORE the settings.json swap; the old gate stays active until
# this is green (no unprotected window).
#
# Windows PowerShell 5.1 compatible: ASCII only; $ErrorActionPreference relaxed around native calls.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$here     = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $here '..\..')).Path
. (Join-Path $repoRoot 'scripts\interop\nightguard_interop.ps1')

$guard    = Join-Path $repoRoot 'scripts\guard\nightguard_guard.ps1'
$adapter  = Join-Path $repoRoot 'scripts\guard\nightguard_adapter.ps1'
$cliExe   = Join-Path $repoRoot 'target\debug\state_interop_cli.exe'

$DataDir = $env:NIGHTGUARD_DIR
if ([string]::IsNullOrWhiteSpace($DataDir)) { $DataDir = 'C:\Users\20252128\dev\Projects\LifeOS\nightguard' }
# Ensure the var is present in THIS process env so child guard/adapter invocations inherit it
# (mirrors production: Claude Code / the watchdog task launch the hook with the user-scope var in
# their env). Without this the adapter -- which fail-closes on unset NIGHTGUARD_DIR by design --
# would block even /shutdown, masking the real allow-path behaviour.
$env:NIGHTGUARD_DIR = $DataDir
$cfgPath   = Join-Path $DataDir 'config.yaml'
$sanctPath = Join-Path $DataDir 'config.sanctioned.yaml'
$keyPath   = Join-Path $DataDir '.guardkey'
$guardJson = Join-Path $DataDir 'guard.json'

if (-not (Test-Path $cliExe)) { throw "run_cutover_gate: state_interop_cli.exe not found at $cliExe (cargo build first)" }

$results = New-Object System.Collections.Generic.List[object]
function Add-Check { param([string]$Name, [bool]$Pass, [string]$Detail)
    Write-Host ("[{0}] {1} -- {2}" -f ($(if ($Pass) { 'PASS' } else { 'FAIL' })), $Name, $Detail)
    $results.Add([PSCustomObject]@{ Name = $Name; Pass = $Pass })
}
function To-Unix { param([int]$H, [int]$M)
    $tz = [System.TimeZoneInfo]::FindSystemTimeZoneById('W. Europe Standard Time')
    $loc = [datetime]::new(2026, 6, 10, $H, $M, 0, [DateTimeKind]::Unspecified)
    [int64]([DateTimeOffset][System.TimeZoneInfo]::ConvertTimeToUtc($loc, $tz)).ToUnixTimeSeconds()
}
function Invoke-Guard { param([Int64]$NtpOverrideUnixSecs)
    $saved = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $env:NIGHTGUARD_TEST_NTP_OVERRIDE = '1'
    $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $guard -DataDir $DataDir -NtpOverrideUnixSecs $NtpOverrideUnixSecs 2>&1
    $code = $LASTEXITCODE
    Remove-Item Env:\NIGHTGUARD_TEST_NTP_OVERRIDE -ErrorAction SilentlyContinue
    $ErrorActionPreference = $saved
    $json = $null; try { $json = (($out | Out-String).Trim() | ConvertFrom-Json) } catch { $json = $null }
    return [PSCustomObject]@{ Exit = $code; Json = $json }
}

Write-Host ""
Write-Host "=== Nightguard CUTOVER prove-then-switch gate (D-11) ==="
Write-Host ("DataDir: {0}" -f $DataDir)
Write-Host ("Guard:   {0}" -f $guard)
Write-Host ("PowerShell: {0}" -f $PSVersionTable.PSVersion)
Write-Host ""

# --- Step 1: DPAPI key round-trips to exactly 32 bytes ------------------------------------------
try {
    $key = Unprotect-GuardKey -Blob (Get-FileBytes -Path $keyPath)
    Add-Check -Name 'D11-1 key round-trip (32 bytes)' -Pass ($key.Length -eq 32) -Detail ("len={0}" -f $key.Length)
} catch { Add-Check -Name 'D11-1 key round-trip (32 bytes)' -Pass $false -Detail "exception: $_"; $key = $null }

# --- Step 2: guard.json verifies in BOTH PowerShell (A3 re-derive) and Rust ---------------------
try {
    $jsonText = [System.Text.Encoding]::UTF8.GetString((Get-FileBytes -Path $guardJson))
    $obj = $jsonText | ConvertFrom-Json
    $onDisk = [string]$obj.state_hmac
    $obj.state_hmac = ''
    $compact = $obj | ConvertTo-Json -Compress -Depth 10
    $cb = [System.Text.Encoding]::UTF8.GetBytes($compact); $cn = New-Object byte[] ($cb.Length + 1); [Array]::Copy($cb, $cn, $cb.Length); $cn[$cb.Length] = 0x0A
    $hm = [System.Security.Cryptography.HMACSHA256]::new($key); try { $psTag = ConvertTo-LowerHex -Bytes $hm.ComputeHash($cn) } finally { $hm.Dispose() }
    $psOk = ($psTag -eq $onDisk)
    $saved = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & $cliExe verify-state-hmac $keyPath $guardJson $onDisk 2>&1 | Out-Null
    $rustOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $saved
    Add-Check -Name 'D11-2 state_hmac verifies (PS + Rust)' -Pass ($psOk -and $rustOk) -Detail ("ps={0} rust={1}" -f $psOk, $rustOk)
} catch { Add-Check -Name 'D11-2 state_hmac verifies (PS + Rust)' -Pass $false -Detail "exception: $_" }

# --- Step 3: curfew verdict honors the schedule (out-of-curfew allow / in-curfew deny) ----------
try {
    $rOut = Invoke-Guard -NtpOverrideUnixSecs (To-Unix 12 0)    # 12:00 -> outside 20:45-05:30
    $rIn  = Invoke-Guard -NtpOverrideUnixSecs (To-Unix 21 30)   # 21:30 -> inside curfew
    $outAllow = ($rOut.Exit -eq 0) -and ($rOut.Json.decision -eq 'allow') -and ($rOut.Json.reason -eq 'outside curfew')
    $inDeny   = ($rIn.Exit -eq 1) -and ($rIn.Json.decision -eq 'deny') -and ($rIn.Json.reason -eq 'curfew')
    Add-Check -Name 'D11-3 curfew schedule verdict' -Pass ($outAllow -and $inDeny) -Detail ("noon:allow/outside={0} 2130:deny/curfew={1}" -f $outAllow, $inDeny)
} catch { Add-Check -Name 'D11-3 curfew schedule verdict' -Pass $false -Detail "exception: $_" }

# --- Step 4: auto-revert -- hand-edit config.yaml -> guard restores sanctioned bytes ------------
try {
    $cfgHmacBefore = Get-FileHmacHex -KeyBytes $key -Path $cfgPath
    $bytes = Get-FileBytes -Path $cfgPath
    $tampered = New-Object byte[] ($bytes.Length + 1); [Array]::Copy($bytes, $tampered, $bytes.Length); $tampered[$bytes.Length] = 0x20  # append a space
    Write-RawBytes -Path $cfgPath -Bytes $tampered
    $r = Invoke-Guard -NtpOverrideUnixSecs (To-Unix 21 30)
    $cfgHmacAfter = Get-FileHmacHex -KeyBytes $key -Path $cfgPath
    $restored = ($cfgHmacAfter -eq $cfgHmacBefore)
    $revertedTrue = ($null -ne $r.Json) -and ($r.Json.reverted -eq $true)
    # Sanctioned identity: HMAC(sanctioned) == guard.json config_hmac.
    $sanctHmac = Get-FileHmacHex -KeyBytes $key -Path $sanctPath
    $sanctOk = ($sanctHmac -eq [string]$obj.config_hmac)
    Add-Check -Name 'D11-4 auto-revert + sanctioned identity' -Pass ($restored -and $revertedTrue -and $sanctOk) `
        -Detail ("reverted={0} restored={1} sanctioned_id={2}" -f ($(if ($null -ne $r.Json) { $r.Json.reverted } else { '?' })), $restored, $sanctOk)
} catch { Add-Check -Name 'D11-4 auto-revert + sanctioned identity' -Pass $false -Detail "exception: $_" }

# --- Step 5: adapter contract -- /shutdown allows (exit 0); fail-closed blocks (exit 2) ---------
try {
    # Allow-command pass: /shutdown exits 0 BEFORE the guard is invoked (deterministic, no network).
    $saved = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    '{"prompt":"/shutdown now"}' | & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $adapter 2>$null | Out-Null
    $shutdownExit = $LASTEXITCODE
    # Fail-closed: point NIGHTGUARD_DIR at a dir with no config.yaml -> adapter throws -> block (exit 2).
    $emptyDir = Join-Path $repoRoot 'target\cutover_gate_empty'
    if (-not (Test-Path $emptyDir)) { New-Item -ItemType Directory -Path $emptyDir -Force | Out-Null }
    $savedDir = $env:NIGHTGUARD_DIR; $env:NIGHTGUARD_DIR = $emptyDir
    $blockOut = '{"prompt":"hello"}' | & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $adapter 2>&1
    $blockExit = $LASTEXITCODE
    $env:NIGHTGUARD_DIR = $savedDir
    $ErrorActionPreference = $saved
    $allowOk = ($shutdownExit -eq 0)
    $blockOk = ($blockExit -eq 2)
    Add-Check -Name 'D11-5 adapter allow(/shutdown)=0 + fail-closed=2' -Pass ($allowOk -and $blockOk) -Detail ("shutdownExit={0} failClosedExit={1}" -f $shutdownExit, $blockExit)
} catch { Add-Check -Name 'D11-5 adapter contract' -Pass $false -Detail "exception: $_" }

# --- Verdict ------------------------------------------------------------------------------------
Write-Host ""
Write-Host "=== Summary ==="
foreach ($c in $results) { Write-Host ("  {0,-46} {1}" -f $c.Name, ($(if ($c.Pass) { 'PASS' } else { 'FAIL' }))) }
Write-Host ""
$failed = @($results | Where-Object { -not $_.Pass })
if ($failed.Count -eq 0) {
    Write-Host "CUTOVER GATE GREEN -- key/state/curfew-schedule/auto-revert/adapter all proven against the real instance. Safe to retire the old gate." -ForegroundColor Green
    exit 0
} else {
    Write-Host ("CUTOVER GATE RED -- {0} check(s) failed. DO NOT retire the old gate." -f $failed.Count) -ForegroundColor Red
    exit 1
}
