# install_autostart.ps1 -- register (or remove) Nightguard Control as a per-user login app.
#
# Adds an HKCU\...\Run entry that launches the built release exe with --hidden, so the app starts
# tucked into the system tray at login (close-to-tray keeps it resident; the tray countdown/badge
# stay live). Per-user (HKCU), no admin, fully reversible with -Remove.
#
# The app needs the user-scope NIGHTGUARD_DIR env var (set during instance init); the logon shell
# inherits it automatically. ASCII-only / Windows PowerShell 5.1 compatible.

[CmdletBinding()]
param(
    # Path to the built exe. Defaults to the repo's release build (scripts/deploy/../.. = repo root).
    [string]$ExePath,
    # Remove the autostart entry instead of adding it.
    [switch]$Remove
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$runKey   = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$valueName = 'Nightguard Control'

if ($Remove) {
    if (Get-ItemProperty -Path $runKey -Name $valueName -ErrorAction SilentlyContinue) {
        Remove-ItemProperty -Path $runKey -Name $valueName
        Write-Host "Removed autostart entry '$valueName'."
    } else {
        Write-Host "No autostart entry '$valueName' to remove."
    }
    return
}

if (-not $ExePath) {
    $here     = Split-Path -Parent $MyInvocation.MyCommand.Path
    $repoRoot = (Resolve-Path (Join-Path $here '..\..')).Path
    $ExePath  = Join-Path $repoRoot 'target\release\nightguard-control.exe'
}

if (-not (Test-Path -LiteralPath $ExePath -PathType Leaf)) {
    throw "install_autostart: exe not found at '$ExePath'. Build it first: npm run tauri build"
}
$ExePath = (Resolve-Path -LiteralPath $ExePath).Path

# Quote the path (handles spaces) and pass --hidden so login starts in the tray.
$command = '"{0}" --hidden' -f $ExePath
Set-ItemProperty -Path $runKey -Name $valueName -Value $command
Write-Host "Registered autostart '$valueName' -> $command"
Write-Host "It will launch hidden-to-tray at next login. Remove with: -Remove"
