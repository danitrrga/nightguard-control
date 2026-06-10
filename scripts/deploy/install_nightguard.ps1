# install_nightguard.ps1 -- byte-exact deploy of the nightguard hook scripts (D-09 deploy).
#
# "Updating the nightguard" = re-run this script. It byte-copies the five+ trust-surface scripts
# from the repo into LifeOS/hooks (the ~/.claude/hooks junction target), and the interop scripts
# into ~/.claude/interop (where the guard's runtime ..\interop lexically resolves), then re-stamps the SHA256
# integrity baseline at REPO-SOURCE scope and STAGES (but does NOT fire) the NightguardWatchdog
# task re-register.
#
# ===================================================================================================
# WHAT THIS SCRIPT DELIBERATELY DOES NOT DO (deferred to Plan 03, behind the D-11 verify gate):
#   - It does NOT edit ~/.claude/settings.json (the UserPromptSubmit swap curfew_guard.ps1 ->
#     nightguard_adapter.ps1).
#   - It does NOT Register-ScheduledTask / Start-ScheduledTask the watchdog (the re-register block
#     below is a function that is defined but NEVER invoked here -- Plan 03 calls it post-gate).
#   - It does NOT touch the live curfew_guard.ps1 or the LifeOS/nightguard instance data files.
# The cutover is prove-then-switch (D-11): build + deploy the artifacts here; flip the live gate
# and start the task LAST, only after the dry-run gate is all-green.
# ===================================================================================================
#
# Windows PowerShell 5.1 compatible: ASCII source only.

[CmdletBinding()]
param(
    # The deploy target dir (the ~/.claude/hooks junction => LifeOS/hooks). Override for testing.
    [string]$HooksDir = 'C:\Users\20252128\dev\Projects\LifeOS\hooks',
    # The interop deploy dir. MUST be where the guard's $here\..\interop resolves AT RUNTIME.
    # Claude Code invokes the hook via the ~/.claude/hooks junction path, so the guard's $here is
    # C:\Users\...\.claude\hooks and its '..\interop' resolves LEXICALLY to C:\Users\...\.claude\interop
    # (verified empirically). That is NOT $HooksDir\interop and NOT the junction TARGET's parent
    # (LifeOS\interop) -- only ~/.claude/hooks is junctioned, ~/.claude/interop is its own real dir.
    [string]$InteropDir = 'C:\Users\20252128\.claude\interop'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --- Repo root: scripts/deploy/.. /.. = repo root (mirrors verify_hook_integrity.ps1's derivation) ---
$here     = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $here '..\..')).Path

Write-Host "=== install_nightguard.ps1 (byte-exact deploy) ==="
Write-Host ("Repo root:  {0}" -f $repoRoot)
Write-Host ("Hooks dir:  {0}" -f $HooksDir)
Write-Host ""

# --- Byte-exact copy helper -- [IO.File]::Copy ONLY (NEVER Get-Content|Set-Content) ---------------
# Pitfall 3 / T-05-08: Get-Content|Set-Content (or any CRLF-normalizing tool) changes bytes and
# breaks the SHA256 integrity baseline AND the config/state HMAC. [IO.File]::Copy is a raw byte
# copy; the .gitattributes -text pins (scripts/guard/*.ps1, scripts/interop/*.ps1) keep the repo
# working-tree bytes LF-stable so the deployed copy is byte-identical to the re-stamped repo bytes.
function Copy-ByteExact {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Dest
    )
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "install_nightguard: source missing: $Source"
    }
    $destDir = Split-Path $Dest
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
    [System.IO.File]::Copy($Source, $Dest, $true)   # byte-exact overwrite; NEVER Set-Content
    Write-Host ("  copied: {0} -> {1}" -f $Source, $Dest)
}

# --- 1/2: deploy the guard, verifier, baseline, adapter, watchdog into LifeOS/hooks ---------------
if (-not (Test-Path $HooksDir)) { New-Item -ItemType Directory -Path $HooksDir -Force | Out-Null }

$guardDir = Join-Path $repoRoot 'scripts\guard'
Copy-ByteExact -Source (Join-Path $guardDir 'nightguard_guard.ps1')      -Dest (Join-Path $HooksDir 'nightguard_guard.ps1')
Copy-ByteExact -Source (Join-Path $guardDir 'nightguard_adapter.ps1')    -Dest (Join-Path $HooksDir 'nightguard_adapter.ps1')
Copy-ByteExact -Source (Join-Path $guardDir 'nightguard_watchdog.ps1')   -Dest (Join-Path $HooksDir 'nightguard_watchdog.ps1')
# NOTE (A5 / live-safety): we deliberately do NOT deploy verify_hook_integrity.ps1 or
# guard.baseline.sha256 into $HooksDir. $HooksDir == ~/.claude/hooks (junction), and the
# SessionStart hook already runs the EXISTING ~/.claude/hooks/verify_hook_integrity.ps1. The repo
# verifier computes $repoRoot=$here\..\.. + checks scripts/guard/* relative to it, which from
# ~/.claude/hooks resolves to a non-existent C:\Users\<u>\scripts\guard and would FAIL the live
# SessionStart integrity check. Integrity is instead enforced at REPO-SOURCE scope (re-stamp below);
# extending a deployed-layout-aware verifier + repointing the SessionStart hook is deferred (A5).

# --- 3: deploy interop where the guard's $here\..\interop dot-source resolves AT RUNTIME -----------
# Pitfall 4 / T-05-09: nightguard_guard.ps1 dot-sources ..\interop\{nightguard_interop,state_interop}.ps1.
# Claude Code invokes the hook via the ~/.claude/hooks junction, so the guard's $here is
# C:\Users\...\.claude\hooks and '..\interop' resolves LEXICALLY to C:\Users\...\.claude\interop
# (verified empirically -- a junction does not rewrite a lexical '..'). Therefore interop MUST land
# in $InteropDir (~/.claude/interop), NOT $HooksDir\interop and NOT LifeOS\interop. Putting it
# anywhere else makes the deployed guard throw on load -> the adapter fail-closes -> total lockout.
$interopSrc = Join-Path $repoRoot 'scripts\interop'
Copy-ByteExact -Source (Join-Path $interopSrc 'nightguard_interop.ps1') -Dest (Join-Path $InteropDir 'nightguard_interop.ps1')
Copy-ByteExact -Source (Join-Path $interopSrc 'state_interop.ps1')      -Dest (Join-Path $InteropDir 'state_interop.ps1')

Write-Host ""

# --- 4: re-stamp the SHA256 integrity baseline (A5 / Pitfall 5 disposition: REPO-SOURCE scope) ----
# ===================================================================================================
# A5 / Pitfall 5 DECISION (explicit, not silent): verify_hook_integrity.ps1's $registered uses
# repo-relative paths (scripts/guard/..., scripts/interop/...) and computes $repoRoot = $here\..\..,
# which resolve correctly ONLY from the REPO, not from the deployed LifeOS/hooks layout. The chosen
# disposition is SOURCE-INTEGRITY SCOPE: re-stamp the baseline by running the REPO copy of
# verify_hook_integrity.ps1 -Update against the REPO copies (scripts/guard + scripts/interop), where
# $repoRoot resolves correctly. This is SOUND because the deployed copies are byte-identical to the
# re-stamped repo bytes -- guaranteed by [IO.File]::Copy (raw byte copy) + the .gitattributes -text
# pins (scripts/guard/*.ps1, scripts/interop/*.ps1) keeping the working tree LF-stable. So the
# baseline that protects the repo source ALSO certifies the exact bytes deployed here (T-05-10).
# (The alternative -- parameterizing $registered/$repoRoot for the deployed layout -- is deferred;
# source-integrity scope is sufficient because deploy is a verified byte-identical copy.)
# Note: verify_hook_integrity.ps1's $registered does NOT yet include nightguard_adapter.ps1 /
# nightguard_watchdog.ps1; extending the trust surface to the new scripts is a verify_hook_integrity
# change tracked separately. The baseline still re-stamps the four existing trust-surface scripts.
# ===================================================================================================
$verifier = Join-Path $guardDir 'verify_hook_integrity.ps1'
Write-Host "Re-stamping integrity baseline (repo-source scope):"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verifier -Update
if ($LASTEXITCODE -ne 0) {
    throw "install_nightguard: baseline re-stamp failed (verify_hook_integrity -Update exit $LASTEXITCODE)"
}
# (No deployed baseline copy: the SessionStart verifier + baseline are repo-scope only -- see the
# A5 note above. The re-stamp protects the repo source bytes, which equal the deployed bytes.)

Write-Host ""

# --- 5: STAGED (NOT fired) NightguardWatchdog re-register -- Plan 03 invokes this post-gate --------
# ===================================================================================================
# D-06: the watchdog stays delivered by the NightguardWatchdog Scheduled Task; only the script path
# moves (from the legacy nightguard_app_watchdog.ps1 to the new nightguard_watchdog.ps1). The task
# hardcodes the script path in its action Arguments, so the file deploy above is NOT enough -- the
# task must be RE-REGISTERED to repoint it. That re-register (and the Start that lets a fresh
# powershell.exe inherit NIGHTGUARD_DIR -- Pitfall 2) is a LIVE OS-state change and is DEFERRED to
# Plan 03 behind the D-11 verify gate. This function is defined but DELIBERATELY NOT CALLED here.
# ===================================================================================================
function Register-NightguardWatchdog {
    param([string]$WatchdogScript = (Join-Path $HooksDir 'nightguard_watchdog.ps1'))

    $taskName = 'NightguardWatchdog'
    if (-not (Test-Path $WatchdogScript)) {
        throw "Watchdog script not found at $WatchdogScript"
    }

    # Remove any prior task of same name (and older one-shot variants).
    foreach ($name in @($taskName, 'StayFreeWatchdog', 'NightguardAppWatchdog', 'StayFree Watchdog', 'Nightguard App Watchdog')) {
        $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($existing) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            Write-Host "Removed prior task: $name"
        }
    }

    $action = New-ScheduledTaskAction `
        -Execute 'powershell.exe' `
        -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$WatchdogScript`" -Loop"

    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -MultipleInstances IgnoreNew

    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description 'Nightguard StayFree watchdog (loop mode, reads NIGHTGUARD_DIR config).' | Out-Null

    Write-Host "Registered scheduled task: $taskName -> $WatchdogScript"
    # Start so a fresh powershell.exe inherits the new user-scope NIGHTGUARD_DIR (Pitfall 2).
    Start-ScheduledTask -TaskName $taskName
    Write-Host "Watchdog started."
}

Write-Host "=== Deploy complete ==="
Write-Host "STAGED (NOT fired): NightguardWatchdog re-register (Register-NightguardWatchdog) -- Plan 03."
Write-Host "DEFERRED to Plan 03 (D-11 gate): settings.json UserPromptSubmit swap, watchdog task Start."
