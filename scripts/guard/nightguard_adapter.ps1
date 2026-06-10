# nightguard_adapter.ps1 -- the Claude-Code UserPromptSubmit seam (D-02 / WIRE-01).
#
# This is the thin host adapter that fronts the host-agnostic guard (nightguard_guard.ps1).
# The guard is a pure verified-state ORACLE: it emits {decision,reason,...} JSON on stdout and
# exits 0 (allow) / 1 (deny). It deliberately does NOT speak the Claude-Code hook protocol. THIS
# adapter is the one place that knows how to block a Claude-Code prompt, and it translates the
# guard's verdict into that protocol, sourcing the butler messages from the SAME canonical
# config.yaml (NIGHTGUARD_DIR) the guard reads -- one source of truth, no hardcoded strings.
#
# CONFIRMED Claude-Code UserPromptSubmit BLOCK CONTRACT (empirically verified against the live
# curfew_guard.ps1 wired in settings.json on this install -- resolves blocker A2):
#   - BLOCK a prompt:  write the butler message to STDERR ([Console]::Error.WriteLine) then exit 2.
#                      Exit code 2 is what Claude-Code honors as a hard block; stderr is surfaced
#                      to the user and the prompt is suppressed. (This is exactly what the live
#                      curfew_guard.ps1 does today.)
#   - ALLOW a prompt:  exit 0, emit nothing. No JSON object required.
#   - REJECTED: exit 1 and/or a {continue:false} JSON object. On THIS install exit 1 is a
#               NON-blocking (fail-OPEN) error -- a prompt with exit 1 passes through. So the
#               adapter MUST translate guard-deny (guard exit 1) into adapter exit 2 + stderr, and
#               every fail-closed catch-all path MUST exit 2 (NEVER exit 1), or an unset
#               NIGHTGUARD_DIR / any throw would fail OPEN at curfew (Pitfall 1 / T-05-07).
#
# Fail-closed everywhere (T-05-07): ANY exception (unset NIGHTGUARD_DIR, guard throw, missing
# guard, unparseable JSON, non-{0,1} exit) emits a BLOCK (stderr + exit 2), never an allow.
#
# Windows PowerShell 5.1 compatible: ASCII source only (no em-dash / smart-quote / n-tilde
# literals -- the -File launcher chokes on them). The n-tilde butler strings live in config.yaml
# (UTF-8) and are read at runtime, never written as source literals here.

# UTF-8 stderr so the config's n-tilde butler messages render correctly when blocked.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8

# Default fail-closed block message; replaced by the config offline_message once config is read.
# If we cannot even read the config (e.g. NIGHTGUARD_DIR unset) we still block with this default.
$script:FailClosedMessage = 'Nightguard is unavailable. For your own good, the house remains closed.'

function Send-Block {
    # The ONE confirmed block mechanism on this install: stderr + exit 2. NEVER exit 1 / JSON.
    param([string]$Message)
    if ([string]::IsNullOrWhiteSpace($Message)) { $Message = $script:FailClosedMessage }
    [Console]::Error.WriteLine($Message)
    exit 2
}

# --- Minimal YAML reader for the adapter's needs (allow_commands + curfew butler messages) ------
# Mirrors the legacy curfew_guard.ps1 parser shape (KERN-04-readable form). Reads the curfew
# subsection's scalar keys (message / tamper_message / offline_message / start / end) and the
# allow_commands list. Quoted values keep embedded spaces; the n-tilde survives because we read
# raw lines as UTF-8 (Get-Content default on PS 5.1 reads the file's encoding).
function Read-AdapterConfig {
    param([Parameter(Mandatory)][string]$Path)
    $curfew = @{
        start          = ''
        end            = ''
        message        = ''
        tamper_message = ''
        offline_message = ''
        allow_commands = @()
    }
    $section = ''
    $subsection = ''
    foreach ($line in (Get-Content -LiteralPath $Path -Encoding UTF8)) {
        if ($line -match '^\s*#' -or $line -match '^\s*$') { continue }
        # Top-level key (column 0).
        if ($line -match '^(\w[\w_]*):\s*(.*)$') {
            $section = $Matches[1]
            $subsection = ''
            continue
        }
        # Second-level key (2-space indent).
        if ($line -match '^\s{2}(\w[\w_]*):\s*(.*)$') {
            $key = $Matches[1]
            $val = $Matches[2]
            if ($section -eq 'curfew' -and $key -eq 'allow_commands') {
                $subsection = 'allow_commands'
                # Inline list form: allow_commands: ["/shutdown"]
                $inline = $val.Trim()
                if ($inline.StartsWith('[') -and $inline.EndsWith(']')) {
                    $inner = $inline.Substring(1, $inline.Length - 2)
                    foreach ($item in ($inner -split ',')) {
                        $c = $item.Trim().Trim('"', "'")
                        if ($c -ne '') { $curfew['allow_commands'] += $c }
                    }
                    $subsection = ''
                }
                continue
            }
            if ($section -eq 'curfew' -and $curfew.ContainsKey($key)) {
                $curfew[$key] = $val.Trim().Trim('"', "'")
            }
            $subsection = ''
            continue
        }
        # allow_commands block-list entry (4-space indent, dash form).
        if ($subsection -eq 'allow_commands' -and $line -match '^\s{4}-\s*"?(.+?)"?\s*$') {
            $cmd = $Matches[1].Trim().Trim('"', "'")
            if ($cmd -ne '') { $curfew['allow_commands'] += $cmd }
            continue
        }
    }
    return $curfew
}

try {
    # --- D-09: resolve the single base data dir, fail-closed (verbatim guard stanza, never $PSScriptRoot) ---
    $DataDir = $env:NIGHTGUARD_DIR
    if ([string]::IsNullOrWhiteSpace($DataDir)) {
        throw "nightguard: no data dir (set NIGHTGUARD_DIR)"   # fail-closed, never guess
    }
    $configPath = Join-Path $DataDir 'config.yaml'

    # Read butler strings from the canonical config (single source of truth -- NEVER hardcoded).
    $cfg = Read-AdapterConfig -Path $configPath
    # Promote the config's offline_message to the fail-closed default now that we have it.
    if (-not [string]::IsNullOrWhiteSpace($cfg['offline_message'])) {
        $script:FailClosedMessage = $cfg['offline_message']
    }

    # --- Read the prompt once, parse it (A4: the published guard does NOT read allow_commands) ----
    $stdin = [Console]::In.ReadToEnd()
    $prompt = ''
    try { $payload = $stdin | ConvertFrom-Json; $prompt = [string]$payload.prompt } catch { $prompt = '' }

    # --- /shutdown allow-command pass: BEFORE invoking the guard (the adapter owns this, A4) ------
    foreach ($cmd in $cfg['allow_commands']) {
        if ($cmd -and ($prompt -match [regex]::Escape($cmd))) {
            exit 0   # allowed command (e.g. /shutdown): let the prompt through, never invoke guard
        }
    }

    # --- Invoke the guard oracle (sibling of this adapter under the hooks dir) ----------------------
    # The guard is script-relative here (its own dot-source tree); the DATA dir came from the env var.
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    $guardScript = Join-Path $here 'nightguard_guard.ps1'
    if (-not (Test-Path -LiteralPath $guardScript -PathType Leaf)) {
        throw "nightguard: guard script missing at $guardScript"   # fail-closed
    }

    # Run the guard in a child powershell so its exit code is isolated and captured cleanly.
    $guardOut = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $guardScript 2>$null
    $guardExit = $LASTEXITCODE

    # --- Translate the guard verdict into the confirmed CC contract (block = stderr + exit 2) ------
    if ($guardExit -eq 0) {
        # allow (decision == 'allow', e.g. grace active): let the prompt through.
        exit 0
    }
    elseif ($guardExit -eq 1) {
        # deny: parse the verdict JSON to pick the matching butler message. The guard emits the
        # verdict JSON on stdout (last line); a missing/unparseable verdict is itself fail-closed.
        $reason = ''
        try {
            $verdictText = ($guardOut | Select-Object -Last 1)
            $verdict = $verdictText | ConvertFrom-Json
            $reason = [string]$verdict.reason
        } catch {
            $reason = ''
        }
        switch ($reason) {
            'curfew' {
                # Substitute {start}/{end} from config into the curfew message.
                $msg = $cfg['message']
                $msg = $msg -replace '\{start\}', $cfg['start']
                $msg = $msg -replace '\{end\}',   $cfg['end']
                Send-Block -Message $msg
            }
            'clock tamper' {
                Send-Block -Message $cfg['tamper_message']
            }
            'ntp unreachable' {
                Send-Block -Message $cfg['offline_message']
            }
            default {
                # deny with an unrecognized / missing reason -> fail-closed block (offline default).
                Send-Block -Message $cfg['offline_message']
            }
        }
    }
    else {
        # Non-{0,1} guard exit (crash / unexpected) -> fail-closed block (Pitfall 1 / T-05-07).
        Send-Block -Message $cfg['offline_message']
    }
}
catch {
    # ANY exception (unset NIGHTGUARD_DIR, missing guard, config-read failure, guard throw) ->
    # fail-closed BLOCK via the confirmed contract (stderr + exit 2). NEVER exit 1, NEVER allow.
    Send-Block -Message $script:FailClosedMessage
}

# Defensive terminal fail-closed: if execution somehow reaches here without an explicit exit,
# block rather than fall through to an implicit allow.
Send-Block -Message $script:FailClosedMessage
