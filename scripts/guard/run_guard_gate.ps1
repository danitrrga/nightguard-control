# run_guard_gate.ps1 -- the Phase 3 GUARD end-to-end EXIT GATE (GARD-01/02/03/04/05).
#
# Drives scripts/guard/nightguard_guard.ps1 against real DPAPI + HMAC fixtures, a deterministic
# NTP seam (-NtpOverrideUnixSecs), and a LIVE Rust fd-lock holder, asserting the guard's exit code
# + verdict JSON for every GARD behavior. Exits 0 only if every check PASSes; exits 1 on ANY
# failure. Mirrors scripts/interop/run_state_interop_gate.ps1 (the Phase 2 state gate skeleton).
#
# Run:  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/guard/run_guard_gate.ps1   (Windows PowerShell 5.1)
#   or  pwsh -NoProfile -File scripts/guard/run_guard_gate.ps1                                   (PowerShell 7)
# [HMACSHA256] / [ProtectedData] are identical .NET types in both hosts.
#
# Checks:
#   GARD-01 tamper->revert     : hand-edit config.yaml -> guard restores sanctioned bytes, reverted=true.
#   GARD-02 both-invalid       : corrupt config.yaml AND config.sanctioned.yaml -> maximal-lockout written, fail_closed=true.
#   GARD-03 state tamper       : flip a guard.json byte (state_hmac no longer re-derives) -> deny (worst-case, no allow).
#   GARD-04 grace/expired/offline: override < window_end -> allow + remaining>0; override > window_end -> deny;
#                                   unreachable SNTP server -> deny + fail_closed (D-07).
#   GARD-05 lock-held->skip    : a live Rust with_commit_lock holder holds .nightguard.lock; tamper while held ->
#                                reverted=false (revert skipped); release -> fire again -> reverted=true.
#   GARD-06 override-ignored   : CR-01 production-safety -- without NIGHTGUARD_TEST_NTP_OVERRIDE=1 a passed
#                                -NtpOverrideUnixSecs is IGNORED; the real SNTP+clock-tamper path runs (no allow).
#   GARD-07 audit-chain-tamper : WR-01 / T-03-13 -- fire once (writes a record), flip one byte of
#                                guard-audit.log, fire again -> verdict reports audit_chain_broken=true,
#                                a chain-broken record is appended, and the curfew verdict is UNCHANGED.
#
# Fixture strategy (DEVIATION from the plan's "emit-state-hmac builds guard.json" text -- see the
# SUMMARY): state_interop_cli emit-state-hmac writes a FIXED, arbitrary config_hmac that is NOT the
# HMAC of any real file, so it cannot drive a GARD-01 byte-exact revert. Instead the gate BUILDS
# guard.json in PowerShell -- config_hmac = the REAL Get-FileHmacHex of the gate's config.yaml, and
# state_hmac via the LOCKED A3 recipe (proven byte-identical to Rust in plan 01/02). The gate then
# cross-checks every PS-built guard.json with Rust `verify-state-hmac` (exit 0) so the PS recipe
# stays provably equal to compute_state_hmac. The live Rust lock holder for GARD-05 is the CLI's
# `hold-commit-lock` subcommand (real with_commit_lock).
#
# STRICT Windows PowerShell 5.1 compatibility: ASCII only (no em-dash / smart quotes), byte arrays
# built explicitly, $ErrorActionPreference relaxed to 'Continue' around native cargo/CLI calls and
# gated purely on $LASTEXITCODE.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here '..\interop\nightguard_interop.ps1')

$repoRoot = Resolve-Path (Join-Path $here '..\..')
$guard    = Join-Path $here 'nightguard_guard.ps1'

# --- Resolve / build the Rust state_interop_cli (for the state_hmac cross-check + lock holder) ---
$cliExe = Join-Path $repoRoot 'target\debug\state_interop_cli.exe'
Write-Host "Building state_interop_cli (cargo build -p mutation-engine --bin state_interop_cli)..."
Push-Location $repoRoot
try {
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
    # Run the Rust CLI, capturing the exit code. Relax $ErrorActionPreference around the native
    # call (cargo/CLI write diagnostics to stderr) and gate on $LASTEXITCODE.
    param([Parameter(Mandatory)][string[]]$CliArgs)
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = & $cliExe @CliArgs 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP
    return [PSCustomObject]@{ Exit = $code; Out = (($out | Out-String).Trim()) }
}

function Invoke-Guard {
    # Fire the guard under test against a fixture data dir, optionally injecting NTP true-now via
    # the -NtpOverrideUnixSecs seam. Returns the exit code + parsed verdict JSON. Relax EAP and
    # gate on $LASTEXITCODE (the guard exits 1 on deny, which is a normal non-error result here).
    # -AllowOverride controls the CR-01 test-only env gate (NIGHTGUARD_TEST_NTP_OVERRIDE). It
    # defaults TRUE so the existing GARD checks keep injecting deterministic true-time; the
    # production-safety check below passes -AllowOverride:$false to prove a passed override is
    # IGNORED when the env flag is absent.
    param(
        [Parameter(Mandatory)][string]$DataDir,
        [Int64]$NtpOverrideUnixSecs = -1,
        [string]$NtpServer,
        [bool]$AllowOverride = $true
    )
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $guardArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $guard, '-DataDir', $DataDir)
    if ($NtpOverrideUnixSecs -ge 0) { $guardArgs += @('-NtpOverrideUnixSecs', $NtpOverrideUnixSecs) }
    if ($PSBoundParameters.ContainsKey('NtpServer')) { $env:NIGHTGUARD_NTP_SERVER = $NtpServer }
    # CR-01: the override only takes effect when this test-only signal is present. Production never
    # sets it, so a host-supplied -NtpOverrideUnixSecs cannot inject true-time / skip clock-tamper.
    if ($AllowOverride) { $env:NIGHTGUARD_TEST_NTP_OVERRIDE = '1' }
    $out  = & powershell @guardArgs 2>&1
    $code = $LASTEXITCODE
    if ($AllowOverride) { Remove-Item Env:\NIGHTGUARD_TEST_NTP_OVERRIDE -ErrorAction SilentlyContinue }
    if ($PSBoundParameters.ContainsKey('NtpServer')) { Remove-Item Env:\NIGHTGUARD_NTP_SERVER -ErrorAction SilentlyContinue }
    $ErrorActionPreference = $savedEAP
    $jsonText = ($out | Out-String).Trim()
    $verdict = $null
    try { $verdict = $jsonText | ConvertFrom-Json } catch { $verdict = $null }
    return [PSCustomObject]@{ Exit = $code; Json = $verdict; Raw = $jsonText }
}

# --- Temp working dir under the repo's target/ (never the global temp; same volume) -------------
$work = Join-Path $repoRoot 'target\guard_gate'
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
Write-Host "=== Nightguard GUARD end-to-end exit gate (GARD-01/02/03/04/05/06/07) ==="
Write-Host ("Guard: {0}" -f $guard)
Write-Host ("CLI:   {0}" -f $cliExe)
Write-Host ("Work:  {0}" -f $work)
Write-Host ("PowerShell: {0}" -f $PSVersionTable.PSVersion)
Write-Host ""

# --- Shared key: a known 32-byte key DPAPI-protected per fixture (Rust + guard both consume it) --
$knownKey = New-Object byte[] 32
for ($i = 0; $i -lt 32; $i++) { $knownKey[$i] = ($i * 11 + 5) -band 0xFF }

# Canonical config bytes (UTF-8, no BOM, LF-only, exactly one trailing LF) -- the byte form the
# Rust writer guarantees and config_hmac is signed over. Keep it minimal but schema-shaped.
$canonicalConfigText = @(
    'curfew:'
    '  enabled: true'
    '  start: "23:00"'
    '  end: "07:00"'
    'timezone: "Europe/Amsterdam"'
) -join "`n"
$canonicalConfigText = $canonicalConfigText + "`n"
$canonicalConfigBytes = [System.Text.Encoding]::UTF8.GetBytes($canonicalConfigText)

# --- Build-Fixture: assemble a complete, internally-consistent fixture data dir -----------------
# Writes .guardkey (DPAPI), config.yaml = config.sanctioned.yaml = canonical bytes, and a
# guard.json whose config_hmac is the REAL HMAC of those bytes and whose state_hmac is signed via
# the LOCKED A3 recipe. $WindowEnd controls the grace window (set $null for no grace). Returns the
# fixture dir + the config_hmac for assertions. Cross-checks the PS-built state_hmac with Rust.
function Build-Fixture {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Nullable[Int64]]$WindowEnd = $null,
        [int]$WeeklySpent = 1
    )
    $dir = Join-Path $work $Name
    if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
    New-Item -ItemType Directory -Path $dir -Force | Out-Null

    # DPAPI key blob the guard's Unprotect-GuardKey will read.
    $keyBlob = Protect-GuardKey -KeyBytes $knownKey
    Write-RawBytes -Path (Join-Path $dir '.guardkey') -Bytes $keyBlob

    # config.yaml == config.sanctioned.yaml == the canonical bytes config_hmac is signed over.
    Write-RawBytes -Path (Join-Path $dir 'config.yaml') -Bytes $canonicalConfigBytes
    Write-RawBytes -Path (Join-Path $dir 'config.sanctioned.yaml') -Bytes $canonicalConfigBytes
    $cfgHmac = Get-FileHmacHex -KeyBytes $knownKey -Path (Join-Path $dir 'config.yaml')

    # Build the GuardState object in the LOCKED field order (config_hmac, state_hmac, weekly_spent,
    # week_anchor, ledger, grace) so the compact re-serialization matches serde's struct order.
    $state = [PSCustomObject]([ordered]@{
        config_hmac  = $cfgHmac
        state_hmac   = ''
        weekly_spent = $WeeklySpent
        week_anchor  = '2026-06-01'
        ledger       = @(
            [PSCustomObject]([ordered]@{
                ntp_timestamp = 1750000000
                fields        = @('curfew.start')
            })
        )
        grace        = $null
    })
    if ($null -ne $WindowEnd) {
        $state.grace = [PSCustomObject]([ordered]@{
            date         = '2026-06-08'
            window_start = ([Int64]$WindowEnd - 480)
            window_end   = [Int64]$WindowEnd
        })
    }

    # A3 recipe: blank state_hmac, compact (-Depth 10) re-serialize, append one 0x0A, HMAC.
    $state.state_hmac = ''
    $compact = $state | ConvertTo-Json -Compress -Depth 10
    $bytes   = [System.Text.Encoding]::UTF8.GetBytes($compact)
    $canon   = New-Object byte[] ($bytes.Length + 1)
    [Array]::Copy($bytes, $canon, $bytes.Length)
    $canon[$bytes.Length] = 0x0A
    $hmac = [System.Security.Cryptography.HMACSHA256]::new($knownKey)
    try { $stateTag = ConvertTo-LowerHex -Bytes $hmac.ComputeHash($canon) } finally { $hmac.Dispose() }
    $state.state_hmac = $stateTag

    # Write guard.json compact (the guard parses it via ConvertFrom-Json; the tag re-derives from
    # the compact re-serialization regardless of on-disk pretty/compact form).
    $guardBytes = [System.Text.Encoding]::UTF8.GetBytes(($state | ConvertTo-Json -Compress -Depth 10))
    Write-RawBytes -Path (Join-Path $dir 'guard.json') -Bytes $guardBytes

    return [PSCustomObject]@{ Dir = $dir; ConfigHmac = $cfgHmac; StateTag = $stateTag }
}

# === GARD-01: tamper live config.yaml -> guard reverts to sanctioned bytes ======================
try {
    $f = Build-Fixture -Name 'gard01' -WindowEnd $null
    $cfgPath = Join-Path $f.Dir 'config.yaml'
    # Hand-edit: flip one byte of config.yaml so HMAC(live) != config_hmac.
    $b = Get-FileBytes -Path $cfgPath
    $b[10] = $b[10] -bxor 0xFF
    Write-RawBytes -Path $cfgPath -Bytes $b
    # Fire with a valid override so the run completes the verdict half too (curfew, no grace).
    $r = Invoke-Guard -DataDir $f.Dir -NtpOverrideUnixSecs 1750002000
    # After the fire, config.yaml must be byte-restored to the sanctioned snapshot (HMAC matches).
    $restoredHmac = Get-FileHmacHex -KeyBytes $knownKey -Path $cfgPath
    $restored = ($restoredHmac -eq $f.ConfigHmac)
    $revertedTrue = ($null -ne $r.Json) -and ($r.Json.reverted -eq $true)
    Add-Check -Name 'GARD-01 tamper->revert' -Pass ($restored -and $revertedTrue) `
        -Detail ("restored={0} reverted={1} exit={2}" -f $restored, ($(if($null -ne $r.Json){$r.Json.reverted}else{'?'})), $r.Exit)
} catch {
    Add-Check -Name 'GARD-01 tamper->revert' -Pass $false -Detail "exception: $_"
}

# === GARD-02: corrupt BOTH config.yaml and config.sanctioned.yaml -> maximal-lockout ============
try {
    $f = Build-Fixture -Name 'gard02' -WindowEnd $null
    $cfgPath  = Join-Path $f.Dir 'config.yaml'
    $sanctPath = Join-Path $f.Dir 'config.sanctioned.yaml'
    # Corrupt both: neither can satisfy config_hmac -> guard must write the maximal-lockout default.
    $cb = Get-FileBytes -Path $cfgPath;  $cb[5]  = $cb[5]  -bxor 0xFF; Write-RawBytes -Path $cfgPath  -Bytes $cb
    $sb = Get-FileBytes -Path $sanctPath; $sb[5] = $sb[5] -bxor 0xFF; Write-RawBytes -Path $sanctPath -Bytes $sb
    $r = Invoke-Guard -DataDir $f.Dir -NtpOverrideUnixSecs 1750002000
    # The written config.yaml must now be the maximal-lockout default (24/7 curfew literal).
    $newCfg = [System.Text.Encoding]::UTF8.GetString((Get-FileBytes -Path $cfgPath))
    $isLockout = ($newCfg -match 'MAXIMAL LOCKOUT DEFAULT') -and ($newCfg -match '00:00-23:59')
    $failClosed = ($null -ne $r.Json) -and ($r.Json.fail_closed -eq $true) -and ($r.Json.reverted -eq $true)
    Add-Check -Name 'GARD-02 both-invalid->lockout' -Pass ($isLockout -and $failClosed) `
        -Detail ("lockout-written={0} fail_closed={1} reverted={2}" -f $isLockout, ($(if($null -ne $r.Json){$r.Json.fail_closed}else{'?'})), ($(if($null -ne $r.Json){$r.Json.reverted}else{'?'})))
} catch {
    Add-Check -Name 'GARD-02 both-invalid->lockout' -Pass $false -Detail "exception: $_"
}

# === GARD-03: flip a guard.json byte so state_hmac no longer re-derives -> deny (worst-case) =====
try {
    # Window is active and covers the override; an UNTAMPERED state would ALLOW. Tampering the
    # state must force deny regardless (worst-case grace-used, T-03-15 / GARD-03).
    $we = 1750001480
    $f = Build-Fixture -Name 'gard03' -WindowEnd $we
    $gjPath = Join-Path $f.Dir 'guard.json'
    # Flip a byte inside the weekly_spent/anchor region (keeps JSON parseable, breaks state_hmac).
    $gb = Get-FileBytes -Path $gjPath
    $flipAt = [Math]::Floor($gb.Length / 2)
    # Nudge a digit if we landed on one (keeps JSON valid); else xor (parse may still hold).
    if ($gb[$flipAt] -ge 0x31 -and $gb[$flipAt] -le 0x38) { $gb[$flipAt] = $gb[$flipAt] + 1 } else { $gb[$flipAt] = $gb[$flipAt] -bxor 0x01 }
    Write-RawBytes -Path $gjPath -Bytes $gb
    # Fire INSIDE the window: a trusted state would allow, but the tampered state must deny.
    $r = Invoke-Guard -DataDir $f.Dir -NtpOverrideUnixSecs ($we - 100)
    $denied = ($r.Exit -ne 0) -and ($null -ne $r.Json) -and ($r.Json.decision -eq 'deny')
    Add-Check -Name 'GARD-03 state-tamper->deny' -Pass $denied `
        -Detail ("decision={0} exit={1} (inside-window, untampered would allow)" -f ($(if($null -ne $r.Json){$r.Json.decision}else{'?'})), $r.Exit)
} catch {
    Add-Check -Name 'GARD-03 state-tamper->deny' -Pass $false -Detail "exception: $_"
}

# === GARD-04: grace honored vs expired vs offline (deterministic via -NtpOverrideUnixSecs) ======
try {
    $we = 1750001480
    $f = Build-Fixture -Name 'gard04' -WindowEnd $we
    # Cross-check: the PS-built guard.json state_hmac is accepted by Rust verify-state-hmac.
    $xc = Invoke-Cli -CliArgs @('verify-state-hmac', (Join-Path $f.Dir '.guardkey'), (Join-Path $f.Dir 'guard.json'), $f.StateTag)
    $crossOk = ($xc.Exit -eq 0)

    # Honored: true-now < window_end -> allow + grace_remaining_secs > 0 + exit 0.
    $rh = Invoke-Guard -DataDir $f.Dir -NtpOverrideUnixSecs ($we - 100)
    $honored = ($rh.Exit -eq 0) -and ($null -ne $rh.Json) -and ($rh.Json.decision -eq 'allow') -and ([int]$rh.Json.grace_remaining_secs -gt 0)

    # Expired: true-now > window_end -> deny + exit 1.
    $re = Invoke-Guard -DataDir $f.Dir -NtpOverrideUnixSecs ($we + 100)
    $expired = ($re.Exit -ne 0) -and ($null -ne $re.Json) -and ($re.Json.decision -eq 'deny')

    # Offline: real SNTP path against an unroutable server (TEST-NET-1, RFC 5737) -> the 2s
    # timeout fires -> $trueNow=$null -> deny + fail_closed (D-07). No override (real SNTP path).
    $ro = Invoke-Guard -DataDir $f.Dir -NtpServer '192.0.2.1'
    $offline = ($ro.Exit -ne 0) -and ($null -ne $ro.Json) -and ($ro.Json.decision -eq 'deny') -and ($ro.Json.fail_closed -eq $true)

    $all = $crossOk -and $honored -and $expired -and $offline
    Add-Check -Name 'GARD-04 grace/expired/offline' -Pass $all `
        -Detail ("xcheck={0} honored={1}(rem={2}) expired={3} offline={4}" -f $crossOk, $honored, ($(if($null -ne $rh.Json){$rh.Json.grace_remaining_secs}else{'?'})), $expired, $offline)
} catch {
    Add-Check -Name 'GARD-04 grace/expired/offline' -Pass $false -Detail "exception: $_"
}

# === GARD-05: lock held -> guard skips the revert; released -> revert resumes ====================
try {
    $f = Build-Fixture -Name 'gard05' -WindowEnd $null
    $cfgPath = Join-Path $f.Dir 'config.yaml'
    $readySentinel   = Join-Path $f.Dir '.lock-ready'
    $releaseSentinel = Join-Path $f.Dir '.lock-release'

    # Start the LIVE Rust lock holder in the background: it takes with_commit_lock on the fixture
    # dir, creates .lock-ready once held, then blocks until we create .lock-release.
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $holder = Start-Process -FilePath $cliExe `
        -ArgumentList @('hold-commit-lock', $f.Dir, $readySentinel, $releaseSentinel) `
        -PassThru -WindowStyle Hidden
    $ErrorActionPreference = $savedEAP

    # Wait for the holder to confirm the lock is genuinely held (bounded).
    $deadline = (Get-Date).AddSeconds(15)
    while (-not (Test-Path $readySentinel) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 50 }
    $lockReady = Test-Path $readySentinel

    # Tamper config.yaml WHILE the lock is held; the guard's circuit-breaker must SKIP the revert.
    $b = Get-FileBytes -Path $cfgPath; $b[10] = $b[10] -bxor 0xFF; Write-RawBytes -Path $cfgPath -Bytes $b
    $tamperedHmac = Get-FileHmacHex -KeyBytes $knownKey -Path $cfgPath
    $rHeld = Invoke-Guard -DataDir $f.Dir -NtpOverrideUnixSecs 1750002000
    $stillTampered = ((Get-FileHmacHex -KeyBytes $knownKey -Path $cfgPath) -eq $tamperedHmac)
    $heldSkipped = ($null -ne $rHeld.Json) -and ($rHeld.Json.reverted -eq $false) -and $stillTampered

    # Release the lock and wait for the holder to exit.
    Write-RawBytes -Path $releaseSentinel -Bytes ([byte[]](1))
    if (-not $holder.WaitForExit(15000)) { try { $holder.Kill() } catch { } }

    # Fire again with the lock free: the revert must now run -> config.yaml restored, reverted=true.
    $rFree = Invoke-Guard -DataDir $f.Dir -NtpOverrideUnixSecs 1750002000
    $restored = ((Get-FileHmacHex -KeyBytes $knownKey -Path $cfgPath) -eq $f.ConfigHmac)
    $freeReverted = ($null -ne $rFree.Json) -and ($rFree.Json.reverted -eq $true) -and $restored

    $pass = $lockReady -and $heldSkipped -and $freeReverted
    Add-Check -Name 'GARD-05 lock-held->skip' -Pass $pass `
        -Detail ("lockReady={0} held:reverted={1}(stillTampered={2}) free:reverted={3}(restored={4})" -f $lockReady, ($(if($null -ne $rHeld.Json){$rHeld.Json.reverted}else{'?'})), $stillTampered, ($(if($null -ne $rFree.Json){$rFree.Json.reverted}else{'?'})), $restored)
} catch {
    Add-Check -Name 'GARD-05 lock-held->skip' -Pass $false -Detail "exception: $_"
}

# === GARD-06: CR-01 production-safety -- without the test env flag, a passed override is IGNORED ==
try {
    # Active window covering the override: WITH the test flag this allows (proven by GARD-04).
    # WITHOUT the flag (-AllowOverride:$false) the override must be ignored and the REAL SNTP path
    # run instead. We point SNTP at an unroutable TEST-NET address so the real path deterministically
    # denies (D-07 fail_closed). If the override were still honored we'd see allow -> this check
    # catches any regression that re-exposes the bypass to a production-shaped invocation.
    $we = 1750001480
    $f = Build-Fixture -Name 'gard06' -WindowEnd $we
    # Override would allow (inside window) BUT the env flag is absent -> override ignored, real SNTP
    # path runs against an unroutable server -> deny + fail_closed (never allow).
    $r = Invoke-Guard -DataDir $f.Dir -NtpOverrideUnixSecs ($we - 100) -NtpServer '192.0.2.1' -AllowOverride:$false
    $ignored = ($r.Exit -ne 0) -and ($null -ne $r.Json) -and ($r.Json.decision -ne 'allow') -and ($r.Json.fail_closed -eq $true)
    Add-Check -Name 'GARD-06 override-ignored-in-prod' -Pass $ignored `
        -Detail ("decision={0} fail_closed={1} exit={2} (override passed, env flag absent -> real SNTP)" -f ($(if($null -ne $r.Json){$r.Json.decision}else{'?'})), ($(if($null -ne $r.Json){$r.Json.fail_closed}else{'?'})), $r.Exit)
} catch {
    Add-Check -Name 'GARD-06 override-ignored-in-prod' -Pass $false -Detail "exception: $_"
}

# === GARD-07: tamper guard-audit.log -> the chain verifier detects it next fire (WR-01/T-03-13) ==
try {
    # Fire 1 writes the FIRST audit record (chains off genesis). With a clean log the verifier must
    # report audit_chain_broken=false. Then flip ONE byte inside that record (not the trailing LF)
    # so its stored tag no longer re-derives; fire 2 must detect the break (audit_chain_broken=true)
    # AND append a 'chain-broken' record, while the curfew verdict (deny here) is UNCHANGED.
    $f = Build-Fixture -Name 'gard07' -WindowEnd $null
    $auditLog = Join-Path $f.Dir 'guard-audit.log'

    # Fire 1: clean run -> writes record 1. Curfew (no grace window), so decision=deny.
    $r1 = Invoke-Guard -DataDir $f.Dir -NtpOverrideUnixSecs 1750002000
    $cleanOk = ($null -ne $r1.Json) -and ($r1.Json.audit_chain_broken -eq $false) -and (Test-Path $auditLog)

    # Capture the pre-tamper record count so we can assert a 'chain-broken' record was appended.
    $beforeText  = [System.Text.Encoding]::UTF8.GetString((Get-FileBytes -Path $auditLog))
    $beforeLines = @($beforeText -split "`n" | Where-Object { $_ -ne '' })
    $beforeCount = $beforeLines.Count

    # Tamper: flip one byte in the middle of the (single) record. Avoid the final byte (the LF) and
    # stay inside the payload region so the line keeps its '|' tag separator -> a pure tag mismatch.
    $ab = Get-FileBytes -Path $auditLog
    $flipAt = [Math]::Floor($ab.Length / 2)
    if ($flipAt -ge ($ab.Length - 1)) { $flipAt = 0 }
    $ab[$flipAt] = $ab[$flipAt] -bxor 0x01
    Write-RawBytes -Path $auditLog -Bytes $ab

    # Fire 2: the verifier must catch the break BEFORE appending this fire's record.
    $r2 = Invoke-Guard -DataDir $f.Dir -NtpOverrideUnixSecs 1750002000
    $brokenReported = ($null -ne $r2.Json) -and ($r2.Json.audit_chain_broken -eq $true) -and ([int]$r2.Json.audit_chain_break_index -ge 0)
    # Verdict must be UNCHANGED by the repudiation detection: still a curfew deny (never loosened).
    $verdictUnchanged = ($null -ne $r2.Json) -and ($r2.Json.decision -eq 'deny') -and ($r2.Exit -ne 0)

    # A 'chain-broken' record must have been appended (logged forward from the current last tag).
    $afterText  = [System.Text.Encoding]::UTF8.GetString((Get-FileBytes -Path $auditLog))
    $afterLines = @($afterText -split "`n" | Where-Object { $_ -ne '' })
    $chainBrokenMatches = @($afterLines | Where-Object { $_ -match '\|chain-broken\|' })
    $chainBrokenRecord = ($chainBrokenMatches.Count -ge 1)
    $appendedForward = ($afterLines.Count -gt $beforeCount)

    $pass = $cleanOk -and $brokenReported -and $verdictUnchanged -and $chainBrokenRecord -and $appendedForward
    Add-Check -Name 'GARD-07 audit-chain-tamper-detected' -Pass $pass `
        -Detail ("clean={0} broken={1}(idx={2}) verdictUnchanged={3} chainBrokenRecord={4} appendedForward={5}" -f $cleanOk, $brokenReported, ($(if($null -ne $r2.Json){$r2.Json.audit_chain_break_index}else{'?'})), $verdictUnchanged, $chainBrokenRecord, $appendedForward)
} catch {
    Add-Check -Name 'GARD-07 audit-chain-tamper-detected' -Pass $false -Detail "exception: $_"
}

# === Verdict ====================================================================================
Write-Host ""
Write-Host "=== Summary ==="
$failed = @($results | Where-Object { -not $_.Pass })
foreach ($c in $results) {
    Write-Host ("  {0,-30} {1}" -f $c.Name, ($(if ($c.Pass) { 'PASS' } else { 'FAIL' })))
}
Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host "ALL CHECKS PASSED -- GUARD gate is GREEN. GARD-01/02/03/04/05/06/07 hold end-to-end against real DPAPI/HMAC fixtures, a deterministic NTP seam, a live Rust fd-lock holder, the CR-01 production-safety property (override ignored without the test env flag), and the WR-01/T-03-13 audit-chain tamper detector (a one-byte edit of guard-audit.log is caught next fire, surfaced as audit_chain_broken, and logged forward as a chain-broken record without changing the verdict)." -ForegroundColor Green
    exit 0
} else {
    Write-Host ("GUARD GATE FAILED -- {0} check(s) failed:" -f $failed.Count) -ForegroundColor Red
    foreach ($f in $failed) { Write-Host ("  FAIL {0}: {1}" -f $f.Name, $f.Detail) -ForegroundColor Red }
    exit 1
}
