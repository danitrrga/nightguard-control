# nightguard_watchdog.ps1 -- StayFree liveness watchdog (D-04 rewrite of the legacy app watchdog).
#
# Ensures the configured apps (StayFree UWP) stay running. Delivered by the always-on
# NightguardWatchdog Scheduled Task in -Loop mode (D-06 -- only the script + config source change;
# the Scheduled-Task delivery mechanism is unchanged).
#
# WIRE-01 / D-05 FIX (the acceptance proof-case): the legacy watchdog hardcoded the STALE
# ~/.claude\nightguard\config.yaml (where watchdog.enabled:false), so the enabled-gate early-returned
# every cycle and StayFree was never relaunched. This rewrite reads the SINGLE canonical config via
# NIGHTGUARD_DIR (where watchdog.enabled:true), so the gate passes and StayFree is restored.
#
# Usage:
#   .\nightguard_watchdog.ps1            # one-shot check
#   .\nightguard_watchdog.ps1 -Loop      # long-running loop (Scheduled Task mode), sleeps
#                                          check_interval_seconds between checks
#
# Windows PowerShell 5.1 compatible: ASCII source only.

param(
    [switch]$Loop
)

$ErrorActionPreference = 'SilentlyContinue'

# --- D-09: resolve the single base data dir, fail-closed (verbatim guard stanza, never $PSScriptRoot) ---
# The stale `Join-Path $env:USERPROFILE '.claude\nightguard\config.yaml'` is GONE (the D-05 root cause).
$DataDir = $env:NIGHTGUARD_DIR
if ([string]::IsNullOrWhiteSpace($DataDir)) {
    throw "nightguard: no data dir (set NIGHTGUARD_DIR)"   # fail-closed, never guess
}
$configPath = Join-Path $DataDir 'config.yaml'
if (-not (Test-Path -LiteralPath $configPath)) {
    throw "nightguard: config.yaml not found under NIGHTGUARD_DIR ($configPath)"
}

# Log path moves under the canonical data dir too (legacy hardcoded ~/.claude\nightguard\watchdog.log).
$logFile = Join-Path $DataDir 'watchdog.log'
$logDir = Split-Path $logFile
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# --- Minimal YAML parser (KERN-04-readable form; same apps[] layout as the canonical config) -----
function Read-SimpleYaml {
    param([string]$Path)
    $config = @{}
    $section = ''
    $subsection = ''
    $currentApp = $null
    $apps = @()

    foreach ($line in (Get-Content -LiteralPath $Path -Encoding UTF8)) {
        if ($line -match '^\s*#' -or $line -match '^\s*$') { continue }

        # Top-level key
        if ($line -match '^(\w+):(.*)$') {
            $section = $Matches[1]
            $val = $Matches[2].Trim()
            if ($val -and $val -ne '') {
                $config[$section] = $val.Trim('"', "'", ' ')
            } else {
                $config[$section] = @{}
            }
            $subsection = ''
            continue
        }

        # Second-level key
        if ($line -match '^\s{2}(\w[\w_]*):(.*)$') {
            $key = $Matches[1]
            $val = $Matches[2].Trim().Trim('"', "'", ' ')
            if ($section -eq 'watchdog' -and $key -eq 'apps') {
                $subsection = 'apps'
                continue
            }
            if ($config[$section] -is [hashtable]) {
                $config[$section][$key] = $val
            }
            continue
        }

        # App list entry (starts new app)
        if ($subsection -eq 'apps' -and $line -match '^\s{4}-\s*(\w+):\s*(.+)$') {
            if ($currentApp) { $apps += $currentApp }
            $currentApp = @{ $Matches[1] = $Matches[2].Trim('"', "'", ' ') }
            continue
        }

        # App property continuation
        if ($subsection -eq 'apps' -and $currentApp -and $line -match '^\s{6}(\w[\w_]*):\s*(.+)$') {
            $currentApp[$Matches[1]] = $Matches[2].Trim('"', "'", ' ')
            continue
        }
    }
    if ($currentApp) { $apps += $currentApp }
    $config['_apps'] = $apps
    return $config
}

function Invoke-Pass {
    $config = Read-SimpleYaml -Path $configPath
    # The WIRE-01 gate: against the canonical config (watchdog.enabled:true) this PROCEEDS and
    # relaunches StayFree (vs the legacy stale enabled:false which early-returned every cycle).
    if ($config['watchdog']['enabled'] -eq 'false') { return $config }

    foreach ($app in $config['_apps']) {
        $processName = $app['process_name']
        if (-not $processName) { continue }

        # Get-Process -Name StayFree (no .exe) -- StayFree UWP surfaces as process 'StayFree' (D-07 VERIFIED).
        $running = Get-Process -Name $processName -ErrorAction SilentlyContinue
        if ($running) { continue }

        $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        $appName = $app['name']
        Add-Content -Path $logFile -Value "$timestamp - $appName not running, restarting..."

        switch ($app['type']) {
            'uwp' {
                # Relaunch the UWP via explorer.exe shell:AppsFolder\<PFN>!<AppId>
                # (StayFree PFN: 37081StayFreeApps.StayFree3_fqhk48m1tsma0!stayfree).
                $packageId = $app['package_id']
                if ($packageId) {
                    Start-Process explorer.exe -ArgumentList "shell:AppsFolder\$packageId"
                }
            }
            'exe' {
                $exePath = $app['path']
                if ($exePath -and (Test-Path $exePath)) {
                    Start-Process $exePath
                }
            }
        }

        Add-Content -Path $logFile -Value "$timestamp - Restart command issued for $appName."
    }

    return $config
}

if ($Loop) {
    $startTs = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $logFile -Value "$startTs - Watchdog loop started (PID $PID), config=$configPath."
    while ($true) {
        $cfg = Invoke-Pass
        $intervalSec = 20
        if ($cfg) {
            $rawSec = $cfg['watchdog']['check_interval_seconds']
            $rawMin = $cfg['watchdog']['check_interval_minutes']
            if ($rawSec) { $intervalSec = [int]$rawSec }
            elseif ($rawMin) { $intervalSec = [int]$rawMin * 60 }
        }
        if ($intervalSec -lt 5) { $intervalSec = 5 }
        Start-Sleep -Seconds $intervalSec
    }
} else {
    Invoke-Pass | Out-Null
}
