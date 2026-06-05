# run_state_interop_gate.ps1 -- the Phase 2 state_hmac EXIT GATE (closes Assumption A3 in-phase).
#
# Proves the guard.json state_hmac recipe is byte-identical across Rust and PowerShell, BOTH
# directions, on this real Windows CurrentUser session. Exits 0 only if every check PASSes;
# exits 1 on ANY mismatch. Mirrors scripts/interop/run_interop_gate.ps1 (the Phase 1 gate).
#
# Run:  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/interop/run_state_interop_gate.ps1  (Windows PowerShell 5.1)
#   or  pwsh -NoProfile -File scripts/interop/run_state_interop_gate.ps1                                  (PowerShell 7)
# [HMACSHA256] / [ProtectedData] are identical .NET types in both hosts.
#
# Checks:
#   1. state_hmac Rust->PS : Rust emit-state-hmac writes a tag + .signbytes; PS Get-StateHmacHex
#                            over the same key + .signbytes -> assert byte-identical hex.
#   2. state_hmac PS->Rust : PS computes the tag; Rust verify-state-hmac -> exit 0.
#   3. Tamper              : flip one byte of guard.json -> Rust verify-state-hmac exits 2;
#                            flip one byte of .signbytes -> PS re-derives a DIFFERENT tag.
#
# STRICT Windows PowerShell 5.1 compatibility: ASCII only (no em-dash / smart quotes), byte
# lists built with foreach (no List[byte].AddRange casts), $ErrorActionPreference relaxed to
# 'Continue' around native cargo/CLI calls and gated purely on $LASTEXITCODE.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'state_interop.ps1')

$repoRoot = Resolve-Path (Join-Path $here '..\..')

# --- Resolve / build the Rust state_interop_cli ----------------------------------------------
$cliExe = Join-Path $repoRoot 'target\debug\state_interop_cli.exe'
Write-Host "Building state_interop_cli (cargo build -p mutation-engine --bin state_interop_cli)..."
Push-Location $repoRoot
try {
    # cargo writes progress to stderr; with $ErrorActionPreference='Stop' that promotes to a
    # terminating error under Windows PowerShell. Relax to 'Continue' and gate on $LASTEXITCODE.
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $cargoLines = & cargo build -p mutation-engine --bin state_interop_cli 2>&1 | ForEach-Object { $_.ToString() }
    $buildCode = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP
    Write-Host (($cargoLines -join "`n").TrimEnd())
    if ($buildCode -ne 0) { throw "cargo build --bin state_interop_cli failed (exit $buildCode)" }
} finally {
    Pop-Location
}
if (-not (Test-Path $cliExe)) { throw "state_interop_cli.exe not found at $cliExe after build" }

function Invoke-Cli {
    # Run the Rust CLI, capturing stdout lines and the exit code. The CLI writes diagnostics to
    # stderr (e.g. verify mismatch) and we WANT the non-zero exit, not a terminating error --
    # so relax $ErrorActionPreference around the native call and gate on $LASTEXITCODE.
    param([Parameter(Mandatory)][string[]]$CliArgs)
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = & $cliExe @CliArgs 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP
    return [PSCustomObject]@{ Exit = $code; Out = (($out | Out-String).Trim()) }
}

# --- Temp working dir under the repo's target/ (never the global temp; same volume) ----------
$work = Join-Path $repoRoot 'target\state_interop_gate'
if (Test-Path $work) { Remove-Item $work -Recurse -Force }
New-Item -ItemType Directory -Path $work -Force | Out-Null

$results = New-Object System.Collections.Generic.List[object]
function Add-Check {
    param([string]$Name, [bool]$Pass, [string]$Detail)
    $status = if ($Pass) { 'PASS' } else { 'FAIL' }
    Write-Host ("[{0}] {1} -- {2}" -f $status, $Name, $Detail)
    $results.Add([PSCustomObject]@{ Name = $Name; Pass = $Pass; Detail = $Detail })
}

Write-Host ""
Write-Host "=== Nightguard state_hmac cross-language exit gate (A3) ==="
Write-Host ("CLI: {0}" -f $cliExe)
Write-Host ("Work dir: {0}" -f $work)
Write-Host ("PowerShell: {0}" -f $PSVersionTable.PSVersion)
Write-Host ""

# --- Shared key: PS protects a known 32-byte key to a blob Rust can unprotect (same key both) -
$knownKey = New-Object byte[] 32
for ($i = 0; $i -lt 32; $i++) { $knownKey[$i] = ($i * 11 + 5) -band 0xFF }
$keyBlobFile = Join-Path $work 'ps.guardkey'
$keyBlob = Protect-GuardKey -KeyBytes $knownKey
Write-RawBytes -Path $keyBlobFile -Bytes $keyBlob

$guardJson = Join-Path $work 'guard.json'
$signBytes = "$guardJson.signbytes"

# === Check 1: state_hmac Rust -> PS (byte-identical tag over identical signbytes) ============
try {
    $r = Invoke-Cli -CliArgs @('emit-state-hmac', $keyBlobFile, $guardJson)
    if ($r.Exit -ne 0) { throw "emit-state-hmac exited $($r.Exit): $($r.Out)" }
    $rustTag = $r.Out
    if (-not (Test-Path $signBytes)) { throw "emit-state-hmac did not write $signBytes" }
    $psTag = Get-StateHmacHex -KeyBytes $knownKey -SignBytesPath $signBytes
    $is64 = ($rustTag.Length -eq 64)
    $match = ($is64 -and ($rustTag -eq $psTag))
    Add-Check -Name 'state_hmac Rust->PS' -Pass $match `
        -Detail ("rust={0}... ps={1}... len={2} identical={3}" -f $rustTag.Substring(0, [Math]::Min(16, $rustTag.Length)), $psTag.Substring(0, [Math]::Min(16, $psTag.Length)), $rustTag.Length, ($rustTag -eq $psTag))
} catch {
    Add-Check -Name 'state_hmac Rust->PS' -Pass $false -Detail "exception: $_"
}

# === Check 2: state_hmac PS -> Rust (PS computes tag, Rust verifies) ==========================
try {
    $psTag2 = Get-StateHmacHex -KeyBytes $knownKey -SignBytesPath $signBytes
    $r = Invoke-Cli -CliArgs @('verify-state-hmac', $keyBlobFile, $guardJson, $psTag2)
    $match = ($r.Exit -eq 0)
    Add-Check -Name 'state_hmac PS->Rust' -Pass $match `
        -Detail ("rust verify-state-hmac exit={0} (expect 0)" -f $r.Exit)
} catch {
    Add-Check -Name 'state_hmac PS->Rust' -Pass $false -Detail "exception: $_"
}

# === Check 3: Tamper -- single-byte flip breaks verification on both sides ====================
try {
    # 3a. Flip one byte of guard.json -> Rust verify-state-hmac must exit 2 against the orig tag.
    $origTag = Get-StateHmacHex -KeyBytes $knownKey -SignBytesPath $signBytes
    $guardBytes = Get-FileBytes -Path $guardJson
    $tamperedGuard = New-Object byte[] $guardBytes.Length
    for ($i = 0; $i -lt $guardBytes.Length; $i++) { $tamperedGuard[$i] = $guardBytes[$i] }
    # Flip a byte in the middle (avoid the leading '{' / trailing '}' for a meaningful edit).
    $flipAt = [Math]::Floor($tamperedGuard.Length / 2)
    $tamperedGuard[$flipAt] = $tamperedGuard[$flipAt] -bxor 0xFF
    $tamperedGuardFile = Join-Path $work 'guard.tampered.json'
    Write-RawBytes -Path $tamperedGuardFile -Bytes $tamperedGuard
    $rt = Invoke-Cli -CliArgs @('verify-state-hmac', $keyBlobFile, $tamperedGuardFile, $origTag)
    # A single-byte flip in valid JSON usually still parses (e.g. a digit/letter change) and the
    # recomputed tag differs -> exit 2. If the flip breaks JSON parsing the CLI exits 1; either
    # way verification does NOT succeed (exit 0). Accept exit 2 as the tamper signal; exit 1
    # (parse failure) is also a non-acceptance, but we require the strict 2 to prove the recipe
    # detected the change rather than a parser. Retry on a different byte if we hit a parse break.
    $rustTamperDetected = ($rt.Exit -eq 2)
    if (-not $rustTamperDetected -and $rt.Exit -eq 1) {
        # Pick a clearly in-value digit byte: flip the last digit of the week_anchor day, which
        # is deep inside a quoted string and always parses. Fall back to flipping a hex char of
        # config_hmac by locating an ASCII hex byte and incrementing it within hex range.
        for ($j = 0; $j -lt $guardBytes.Length; $j++) { $tamperedGuard[$j] = $guardBytes[$j] }
        $picked = $false
        for ($j = 10; $j -lt $guardBytes.Length - 2 -and -not $picked; $j++) {
            $c = $guardBytes[$j]
            # ASCII '1'..'9' (0x31..0x39): change to a different digit, keeps JSON valid.
            if ($c -ge 0x31 -and $c -le 0x38) { $tamperedGuard[$j] = $c + 1; $picked = $true }
        }
        Write-RawBytes -Path $tamperedGuardFile -Bytes $tamperedGuard
        $rt = Invoke-Cli -CliArgs @('verify-state-hmac', $keyBlobFile, $tamperedGuardFile, $origTag)
        $rustTamperDetected = ($rt.Exit -eq 2)
    }

    # 3b. Flip one byte of the signbytes -> PS re-derives a DIFFERENT tag.
    $sbBytes = Get-FileBytes -Path $signBytes
    $tamperedSb = New-Object byte[] $sbBytes.Length
    for ($i = 0; $i -lt $sbBytes.Length; $i++) { $tamperedSb[$i] = $sbBytes[$i] }
    $sbFlipAt = [Math]::Floor($tamperedSb.Length / 2)
    $tamperedSb[$sbFlipAt] = $tamperedSb[$sbFlipAt] -bxor 0xFF
    $tamperedSbFile = Join-Path $work 'guard.tampered.signbytes'
    Write-RawBytes -Path $tamperedSbFile -Bytes $tamperedSb
    $psTamperTag = Get-StateHmacHex -KeyBytes $knownKey -SignBytesPath $tamperedSbFile
    $psTamperDetected = ($psTamperTag -ne $origTag)

    $allTamperDetected = $rustTamperDetected -and $psTamperDetected
    Add-Check -Name 'state_hmac Tamper' -Pass $allTamperDetected `
        -Detail ("rust verify exit={0} (expect 2); ps tag differs={1}" -f $rt.Exit, $psTamperDetected)
} catch {
    Add-Check -Name 'state_hmac Tamper' -Pass $false -Detail "exception: $_"
}

# === Verdict =================================================================================
Write-Host ""
Write-Host "=== Summary ==="
$failed = @($results | Where-Object { -not $_.Pass })
foreach ($c in $results) {
    Write-Host ("  {0,-24} {1}" -f $c.Name, ($(if ($c.Pass) { 'PASS' } else { 'FAIL' })))
}
Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host "ALL CHECKS PASSED -- A3 state_hmac gate is GREEN. The recipe is byte-identical Rust<->PowerShell both directions; a single-byte tamper fails verification on both sides." -ForegroundColor Green
    exit 0
} else {
    Write-Host ("STATE GATE FAILED -- {0} check(s) failed:" -f $failed.Count) -ForegroundColor Red
    foreach ($f in $failed) { Write-Host ("  FAIL {0}: {1}" -f $f.Name, $f.Detail) -ForegroundColor Red }
    exit 1
}
