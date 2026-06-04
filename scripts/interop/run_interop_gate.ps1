# run_interop_gate.ps1 -- the Phase 1 EXIT GATE.
#
# Proves the DPAPI + HMAC trust kernel is byte-identical across Rust and PowerShell,
# BOTH directions, on this real Windows CurrentUser session. Exits 0 only if every
# check PASSes; exits 1 on ANY mismatch.
#
# Run:  pwsh   -NoProfile -File scripts/interop/run_interop_gate.ps1     (PowerShell 7)
#   or  powershell -NoProfile -File scripts/interop/run_interop_gate.ps1 (Windows PowerShell 5.1)
# The .NET [ProtectedData] / [HMACSHA256] APIs are identical in both hosts.
#
# Checks:
#   1. DPAPI Rust->PS : Rust gen-key writes a blob; PS Unprotect -> assert exactly 32 bytes (FAIL on 64).
#   2. DPAPI PS->Rust : PS protects a known 32-byte key; Rust unprotect-key -> identical 32 hex bytes.
#   3. HMAC  Rust->PS : Rust sign-file; PS Get-FileHmacHex over same key+file -> identical hex tag.
#   4. HMAC  PS->Rust : PS computes a tag; Rust verify-file -> exit 0.
#   5. Tamper         : CRLF and BOM mutated copies -> PS tag DIFFERS and Rust verify-file exits 2.
#   6. KERN-04        : Rust write-config; PS raw read -> no 0x0D (CR), no leading BOM, one trailing 0x0A.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here 'nightguard_interop.ps1')

$repoRoot = Resolve-Path (Join-Path $here '..\..')
$crateDir = Join-Path $repoRoot 'crates\trust-kernel'

# --- Resolve / build the Rust interop_cli ----------------------------------------------------
# Prefer the compiled debug exe (deterministic, fast); build it if missing.
$cliExe = Join-Path $repoRoot 'target\debug\interop_cli.exe'
Write-Host "Building interop_cli (cargo build --bin interop_cli)..."
Push-Location $repoRoot
try {
    # cargo writes progress to stderr; with $ErrorActionPreference='Stop' a native command's
    # stderr is promoted to a terminating error under Windows PowerShell. Locally relax to
    # 'Continue' and gate purely on $LASTEXITCODE.
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    # Merge stderr->stdout and collect as plain strings so cargo's progress (written to
    # stderr) is not rendered as a PowerShell error record. Gate on $LASTEXITCODE only.
    $cargoLines = & cargo build --bin interop_cli 2>&1 | ForEach-Object { $_.ToString() }
    $buildCode = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP
    Write-Host (($cargoLines -join "`n").TrimEnd())
    if ($buildCode -ne 0) { throw "cargo build --bin interop_cli failed (exit $buildCode)" }
} finally {
    Pop-Location
}
if (-not (Test-Path $cliExe)) { throw "interop_cli.exe not found at $cliExe after build" }

function Invoke-Cli {
    # Run the Rust interop_cli, capturing stdout lines and the exit code. The CLI writes
    # diagnostics to stderr (e.g. verify-file mismatch) and we WANT the non-zero exit, not a
    # PowerShell terminating error -- so relax $ErrorActionPreference around the native call.
    param([Parameter(Mandatory)][string[]]$CliArgs)
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = & $cliExe @CliArgs 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP
    return [PSCustomObject]@{ Exit = $code; Out = (($out | Out-String).Trim()) }
}

# --- Temp working dir under the repo's target/ (never the global temp; same volume) ----------
$work = Join-Path $repoRoot 'target\interop_gate'
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
Write-Host "=== Nightguard cross-language exit gate ==="
Write-Host ("CLI: {0}" -f $cliExe)
Write-Host ("Work dir: {0}" -f $work)
Write-Host ("PowerShell: {0}" -f $PSVersionTable.PSVersion)
Write-Host ""

# === Check 1: DPAPI Rust -> PS (32-not-64 canary) ============================================
try {
    $rustKeyFile = Join-Path $work 'rust.guardkey'
    $r = Invoke-Cli -CliArgs @('gen-key', $rustKeyFile)
    if ($r.Exit -ne 0) { throw "gen-key exited $($r.Exit): $($r.Out)" }
    $rustKeyHex = $r.Out
    $blob = Get-FileBytes -Path $rustKeyFile
    $plain = Unprotect-GuardKey -Blob $blob
    $is32 = ($plain.Length -eq 32)
    $psKeyHex = ConvertTo-LowerHex -Bytes $plain
    $match = ($is32 -and ($psKeyHex -eq $rustKeyHex))
    if ($plain.Length -eq 64) {
        Add-Check -Name 'DPAPI Rust->PS' -Pass $false -Detail "GOT 64 BYTES -- SecureString trap! (must be 32)"
    } else {
        Add-Check -Name 'DPAPI Rust->PS' -Pass $match `
            -Detail ("decrypted={0} bytes (expect 32); key match={1}" -f $plain.Length, $match)
    }
} catch {
    Add-Check -Name 'DPAPI Rust->PS' -Pass $false -Detail "exception: $_"
}

# === Check 2: DPAPI PS -> Rust ===============================================================
try {
    $knownKey = New-Object byte[] 32
    for ($i = 0; $i -lt 32; $i++) { $knownKey[$i] = ($i * 7 + 3) -band 0xFF }
    $knownHex = ConvertTo-LowerHex -Bytes $knownKey
    $psBlobFile = Join-Path $work 'ps.guardkey'
    $psBlob = Protect-GuardKey -KeyBytes $knownKey
    Write-RawBytes -Path $psBlobFile -Bytes $psBlob
    $r = Invoke-Cli -CliArgs @('unprotect-key', $psBlobFile)
    $rustHex = $r.Out
    $match = ($r.Exit -eq 0 -and $rustHex -eq $knownHex)
    Add-Check -Name 'DPAPI PS->Rust' -Pass $match `
        -Detail ("rust exit={0}; len(hex)={1} (expect 64); identical={2}" -f $r.Exit, $rustHex.Length, ($rustHex -eq $knownHex))
} catch {
    Add-Check -Name 'DPAPI PS->Rust' -Pass $false -Detail "exception: $_"
}

# === Check 3: HMAC Rust -> PS (byte-identical tag) ===========================================
try {
    $dataFile = Join-Path $work 'config.yaml'
    $r = Invoke-Cli -CliArgs @('write-config', $dataFile)
    if ($r.Exit -ne 0) { throw "write-config exited $($r.Exit): $($r.Out)" }
    # Use the PS->Rust known key (already DPAPI-unprotectable by Rust at $psBlobFile) so both
    # sides hold the SAME 32-byte key: Rust loads it from $psBlobFile, PS holds $knownKey.
    $r = Invoke-Cli -CliArgs @('sign-file', $psBlobFile, $dataFile)
    if ($r.Exit -ne 0) { throw "sign-file exited $($r.Exit): $($r.Out)" }
    $rustTag = $r.Out
    $psTag = Get-FileHmacHex -KeyBytes $knownKey -Path $dataFile
    $match = ($rustTag -eq $psTag)
    Add-Check -Name 'HMAC Rust->PS' -Pass $match `
        -Detail ("rust={0}... ps={1}... identical={2}" -f $rustTag.Substring(0,16), $psTag.Substring(0,16), $match)
} catch {
    Add-Check -Name 'HMAC Rust->PS' -Pass $false -Detail "exception: $_"
}

# === Check 4: HMAC PS -> Rust (PS signs, Rust verifies) ======================================
try {
    $psTag2 = Get-FileHmacHex -KeyBytes $knownKey -Path $dataFile
    $r = Invoke-Cli -CliArgs @('verify-file', $psBlobFile, $dataFile, $psTag2)
    $match = ($r.Exit -eq 0)
    Add-Check -Name 'HMAC PS->Rust' -Pass $match -Detail ("rust verify-file exit={0} (expect 0)" -f $r.Exit)
} catch {
    Add-Check -Name 'HMAC PS->Rust' -Pass $false -Detail "exception: $_"
}

# === Check 5: Tamper -- CRLF and BOM mutations flagged both sides =============================
try {
    $origBytes = Get-FileBytes -Path $dataFile
    $origTag = Get-FileHmacHex -KeyBytes $knownKey -Path $dataFile

    # 5a. CRLF: replace every LF (0x0A) with CRLF (0x0D 0x0A).
    $crlf = New-Object System.Collections.Generic.List[byte]
    foreach ($b in $origBytes) {
        if ($b -eq 0x0A) { $crlf.Add([byte]0x0D) }
        $crlf.Add($b)
    }
    $crlfFile = Join-Path $work 'config.crlf.yaml'
    Write-RawBytes -Path $crlfFile -Bytes $crlf.ToArray()
    $crlfTag = Get-FileHmacHex -KeyBytes $knownKey -Path $crlfFile
    $psCrlfTampered = ($crlfTag -ne $origTag)
    $rc = Invoke-Cli -CliArgs @('verify-file', $psBlobFile, $crlfFile, $origTag)
    $rustCrlfTampered = ($rc.Exit -eq 2)

    # 5b. BOM: prepend a UTF-8 BOM (0xEF 0xBB 0xBF). Append byte-by-byte (AddRange on a
    # byte[] surfaced via PowerShell can bind as Object[] and fail the IEnumerable<byte> cast).
    $bom = New-Object System.Collections.Generic.List[byte]
    $bom.Add([byte]0xEF); $bom.Add([byte]0xBB); $bom.Add([byte]0xBF)
    foreach ($b in $origBytes) { $bom.Add([byte]$b) }
    $bomFile = Join-Path $work 'config.bom.yaml'
    Write-RawBytes -Path $bomFile -Bytes $bom.ToArray()
    $bomTag = Get-FileHmacHex -KeyBytes $knownKey -Path $bomFile
    $psBomTampered = ($bomTag -ne $origTag)
    $rb = Invoke-Cli -CliArgs @('verify-file', $psBlobFile, $bomFile, $origTag)
    $rustBomTampered = ($rb.Exit -eq 2)

    $allTampered = $psCrlfTampered -and $rustCrlfTampered -and $psBomTampered -and $rustBomTampered
    Add-Check -Name 'Tamper CRLF/BOM' -Pass $allTampered `
        -Detail ("CRLF: ps-mismatch={0} rust-exit={1}; BOM: ps-mismatch={2} rust-exit={3} (all must be true/2)" -f `
            $psCrlfTampered, $rc.Exit, $psBomTampered, $rb.Exit)
} catch {
    Add-Check -Name 'Tamper CRLF/BOM' -Pass $false -Detail "exception: $_"
}

# === Check 6: KERN-04 -- Rust-written config reads back clean =================================
try {
    $cfgBytes = Get-FileBytes -Path $dataFile
    $hasCR = $false
    foreach ($b in $cfgBytes) { if ($b -eq 0x0D) { $hasCR = $true; break } }
    $hasBom = ($cfgBytes.Length -ge 3 -and $cfgBytes[0] -eq 0xEF -and $cfgBytes[1] -eq 0xBB -and $cfgBytes[2] -eq 0xBF)
    $oneTrailingLf = ($cfgBytes.Length -ge 2 -and $cfgBytes[$cfgBytes.Length - 1] -eq 0x0A -and $cfgBytes[$cfgBytes.Length - 2] -ne 0x0A)
    $clean = (-not $hasCR) -and (-not $hasBom) -and $oneTrailingLf
    Add-Check -Name 'KERN-04 config readback' -Pass $clean `
        -Detail ("hasCR={0} hasBOM={1} exactlyOneTrailingLF={2}" -f $hasCR, $hasBom, $oneTrailingLf)
} catch {
    Add-Check -Name 'KERN-04 config readback' -Pass $false -Detail "exception: $_"
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
    Write-Host "ALL CHECKS PASSED -- Phase 1 exit gate is GREEN. DPAPI key round-trips to 32 bytes both directions; HMAC tags byte-identical; tamper detected both sides." -ForegroundColor Green
    exit 0
} else {
    Write-Host ("EXIT GATE FAILED -- {0} check(s) failed:" -f $failed.Count) -ForegroundColor Red
    foreach ($f in $failed) { Write-Host ("  FAIL {0}: {1}" -f $f.Name, $f.Detail) -ForegroundColor Red }
    exit 1
}
