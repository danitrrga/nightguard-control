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

# --- Test-SanctionedValid: the LOCKED sanctioned-validity predicate (RESEARCH Open Q2) ----------
# "sanctioned valid" = the file exists AND HMAC(its raw bytes) == guard.json.config_hmac. The
# sanctioned snapshot is the revert target = the NEW canonical bytes config_hmac was signed over
# (Phase 2 writes sanctioned FIRST, then re-signs config_hmac over those same bytes). So after a
# hand-edit, live != sanctioned but sanctioned still matches config_hmac. A sanctioned that itself
# was tampered (or is missing/unreadable) fails this predicate -> fall to maximal-lockout.
function Test-SanctionedValid {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][byte[]]$Key,
        [Parameter(Mandatory)][string]$SanctionedPath,
        [Parameter(Mandatory)][string]$ExpectedConfigHmac
    )
    if ([string]::IsNullOrEmpty($ExpectedConfigHmac)) { return $false }  # untrustworthy target
    if (-not (Test-Path $SanctionedPath)) { return $false }
    try {
        $sanctHmac = Get-FileHmacHex -KeyBytes $Key -Path $SanctionedPath
    } catch {
        return $false   # unreadable -> treat as invalid (fail-closed), never permissive
    }
    return ($sanctHmac -eq $ExpectedConfigHmac)
}

# --- Write-MaximalLockoutDefault: the hardcoded D-03 fail-closed default ------------------------
# Written ONLY when BOTH live and sanctioned config are invalid (or config_hmac is untrustworthy).
# Maximally restrictive: curfew always-on (24/7 via every schedule day = the full day),
# block_when_offline on, clock_protection + watchdog on. Grace/tokens live in guard.json (which the
# guard NEVER writes) -- the state-verify worst-case substitution handles "no grace, zero tokens"
# at runtime. The literal is canonical bytes (UTF-8, no BOM, LF-only, exactly one trailing 0x0A)
# so the existing minimal YAML parser (KERN-04 form) reads it. Uses Write-RawBytes (no Set-Content).
function Write-MaximalLockoutDefault {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$ConfigPath)
    # ASCII, LF-joined, single trailing LF appended below. 24/7 lockout: every day fully guarded.
    $lines = @(
        '# MAXIMAL LOCKOUT DEFAULT -- written by nightguard_guard.ps1 (D-03 fail-closed).'
        '# Both live and sanctioned config were invalid; this is the most restrictive config.'
        '# Repair via the app (DPAPI-gated re-sign), then this file is replaced by a signed one.'
        'curfew:'
        '  enabled: true'
        '  start: "00:00"'
        '  end: "23:59"'
        '  allow_commands: []'
        '  block_when_offline: true'
        '  schedule:'
        '    monday: "00:00-23:59"'
        '    tuesday: "00:00-23:59"'
        '    wednesday: "00:00-23:59"'
        '    thursday: "00:00-23:59"'
        '    friday: "00:00-23:59"'
        '    saturday: "00:00-23:59"'
        '    sunday: "00:00-23:59"'
        'clock_protection:'
        '  enabled: true'
        '  max_offset_minutes: 0'
        'watchdog:'
        '  enabled: true'
        '  check_interval_seconds: 30'
        '  apps: []'
        'timezone: "Europe/Amsterdam"'
    )
    $text = ($lines -join "`n") + "`n"   # LF-only, exactly one trailing LF
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($text)   # UTF-8, no BOM
    Write-RawBytes -Path $ConfigPath -Bytes $bytes
}

# --- Verdict-input variables (this plan sets the config/state branches; plan 03 reads these) ----
$reverted    = $false
$failClosed  = $false
$weeklySpent = 3       # default to worst-case until state-verify proves otherwise (fail-closed)
$graceUsed   = $true   # default to grace-as-used until state-verify proves otherwise

# --- State-verify (D-04): re-derive state_hmac; mismatch -> runtime worst-case (no write) -------
# Done first so the config-verify branch can lean on $guardObj.config_hmac. A missing/unparseable
# guard.json or any state_hmac mismatch leaves the worst-case defaults above in place.
$stateResult = Get-RuntimeStateHmac -Key $key -GuardJson $guardJson
$guardObj    = $stateResult.Obj
$stateValid  = $stateResult.Valid -and ($stateResult.Tag -eq $stateResult.Expected)
if ($stateValid) {
    # State proven untampered: trust the on-disk values.
    $weeklySpent = [int]$guardObj.weekly_spent
    $graceUsed   = ($null -ne $guardObj.grace)   # an active grace window means grace is used today
} else {
    # D-04: tampered/unverifiable state -> worst-case (already set above). The guard NEVER re-signs
    # guard.json -- re-blessing the worst-case for the week is the Rust DPAPI repair's job (D-05).
    $weeklySpent = 3
    $graceUsed   = $true
}

# --- Config-verify -> circuit-breaker -> revert / maximal-lockout (GARD-01/02/05) ---------------
# Runs UNCONDITIONALLY every fire, BEFORE any clock-dependent logic. config_hmac is trustworthy
# only when state-verify passed; otherwise we cannot trust the revert target and must fail closed.
$configHmacTrusted = $stateValid -and -not [string]::IsNullOrEmpty([string]$guardObj.config_hmac)

$liveHmac = $null
if (Test-Path $cfgLive) {
    try { $liveHmac = Get-FileHmacHex -KeyBytes $key -Path $cfgLive } catch { $liveHmac = $null }
}

if ($configHmacTrusted -and $liveHmac -eq [string]$guardObj.config_hmac) {
    # Live config matches the signed snapshot: nothing to revert.
    $reverted = $false
} else {
    # Mismatch (hand-edit), missing/unreadable live, or an untrustworthy config_hmac.
    # D-06 circuit-breaker: if the app holds .nightguard.lock, a commit is in progress -- SKIP the
    # revert this cycle (live-written-LAST converges moments later; the next fire re-checks).
    if (Test-LockHeld -LockPath $lockPath) {
        $reverted = $false
    }
    elseif ($configHmacTrusted -and (Test-SanctionedValid -Key $key -SanctionedPath $cfgSanctioned -ExpectedConfigHmac ([string]$guardObj.config_hmac))) {
        # Sanctioned is the valid revert target (its HMAC == config_hmac). Idempotent byte copy;
        # the next fire re-verifies. The guard NEVER re-signs -- this is a plain overwrite copy.
        [System.IO.File]::Copy($cfgSanctioned, $cfgLive, $true)
        $reverted = $true
    }
    else {
        # D-03: both live and sanctioned invalid (or config_hmac untrustworthy) -> maximal-lockout.
        # Corrupting both files buys the impulsive user nothing -- worst case is 24/7 curfew.
        Write-MaximalLockoutDefault -ConfigPath $cfgLive
        $reverted   = $true
        $failClosed = $true
    }
}

# ================================================================================================
# CLOCK-DEPENDENT HALF (plan 03 / GARD-04 / D-01 / D-02 / D-07 / D-08): guard-side SNTP true-time,
# clock-tamper detection, the grace/curfew verdict against guard.json.grace.window_end, an
# HMAC-chained audit record per fire, and the host-agnostic JSON+exit-code output. Fail-closed
# everywhere: no verifiable true time, an expired window, or a skewed clock -> deny.
# ================================================================================================

# NTP epoch (1900-01-01) to unix epoch (1970-01-01) offset in seconds. Subtract it from an NTP
# transmit-timestamp seconds field to get unix seconds. (70 years incl. 17 leap days.)
$NtpToUnixOffset = 2208988800

# Genesis tag for the FIRST audit record (no predecessor). A fixed, well-known constant so the
# very first record_tag = HMAC(key, GENESIS || payload) is deterministic and the chain is
# verifiable from record 1 forward. ASCII, 64 hex zeros (one HMAC-SHA256 tag width).
$AuditGenesisTag = '0000000000000000000000000000000000000000000000000000000000000000'

# --- Get-GuardNtpUnixSecs: the guard's OWN SNTP true-time query (fail-closed, D-07) -------------
# Builds a 48-byte SNTP client packet (byte 0 = 0x1B: LI=0, VN=3, Mode=3), sends it over UDP to a
# public NTP server, reads the transmit-timestamp seconds (bytes 40..43, big-endian), and converts
# NTP(1900) -> unix(1970) by subtracting 2208988800. On ANY exception returns $null; the caller
# treats $null as NtpUnreachable and DENIES. NEVER falls back to Get-Date / the local clock --
# mirrors ntp.rs (every sntpc error -> NtpUnreachable, no SystemTime::now() path).
function Get-GuardNtpUnixSecs {
    [CmdletBinding()]
    param(
        [string]$Server = 'time.cloudflare.com',
        [int]$TimeoutMs = 2000
    )
    $sock = $null
    try {
        $packet = New-Object byte[] 48
        $packet[0] = 0x1B   # LI=0, VN=3, Mode=3 (client)
        $sock = New-Object System.Net.Sockets.Socket('InterNetwork', 'Dgram', 'Udp')
        $sock.ReceiveTimeout = $TimeoutMs
        $sock.SendTimeout = $TimeoutMs
        $sock.Connect($Server, 123)
        [void]$sock.Send($packet)
        [void]$sock.Receive($packet)
        # Transmit-timestamp seconds = bytes 40..43, big-endian.
        $secs = ([uint32]$packet[40] -shl 24) -bor ([uint32]$packet[41] -shl 16) `
              -bor ([uint32]$packet[42] -shl 8) -bor [uint32]$packet[43]
        return [int64]$secs - $NtpToUnixOffset
    } catch {
        return $null   # fail-closed: any SNTP failure -> NtpUnreachable -> caller denies
    } finally {
        if ($null -ne $sock) { try { $sock.Close() } catch { } }
    }
}

# --- Append-AuditRecord: the tamper-evident HMAC-chained audit log (D-08) ------------------------
# Each fire appends exactly ONE record. The chain is record_tag = HMAC(key, prevTagBytes ||
# payloadBytes); the first record chains off $AuditGenesisTag. Deleting/editing/truncating the log
# breaks the chain and is detectable next run (the recomputed tag will not match). The on-disk line
# form is "<payload>|<record_tag>\n"; payload fields are pipe-delimited with newlines/pipes escaped
# so the delimiter is unambiguous. Written with [IO.File]::AppendAllText (UTF-8, no BOM) so the
# append is byte-exact and never normalizes EOLs.
function Append-AuditRecord {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][byte[]]$Key,
        [Parameter(Mandatory)][string]$LogPath,
        [Parameter(Mandatory)][string]$Timestamp,
        [Parameter(Mandatory)][string]$EventType,
        [Parameter(Mandatory)][string]$Detail
    )
    # Escape the field separator and record/line separators so a payload field cannot forge a
    # record boundary: backslash first (so our own escapes are unambiguous), then | and newlines.
    $escape = {
        param([string]$s)
        $s = $s -replace '\\', '\\\\'
        $s = $s -replace '\|', '\p'
        $s = $s -replace "`r", '\r'
        $s = $s -replace "`n", '\n'
        return $s
    }
    $payload = (& $escape $Timestamp) + '|' + (& $escape $EventType) + '|' + (& $escape $Detail)

    # Previous tag = the record_tag of the LAST line (field after the final unescaped '|'), or the
    # genesis constant if the log is empty/absent. We read raw bytes (no Get-Content normalization).
    $prevTag = $AuditGenesisTag
    if (Test-Path $LogPath) {
        try {
            $existing = [System.Text.Encoding]::UTF8.GetString((Get-FileBytes -Path $LogPath))
            # @(...) forces an array: a single surviving line must NOT collapse to a scalar string,
            # else $lines[0] would index a CHARACTER instead of the whole record line.
            $lines = @($existing -split "`n" | Where-Object { $_ -ne '' })
            if ($lines.Count -gt 0) {
                $lastLine = $lines[$lines.Count - 1]
                $sep = $lastLine.LastIndexOf('|')
                if ($sep -ge 0) { $prevTag = $lastLine.Substring($sep + 1) }
            }
        } catch {
            # Unreadable log -> chain off genesis (the broken predecessor is itself the evidence).
            $prevTag = $AuditGenesisTag
        }
    }

    $prevBytes    = [System.Text.Encoding]::UTF8.GetBytes($prevTag)
    $payloadBytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    $chainInput   = New-Object byte[] ($prevBytes.Length + $payloadBytes.Length)
    [Array]::Copy($prevBytes, 0, $chainInput, 0, $prevBytes.Length)
    [Array]::Copy($payloadBytes, 0, $chainInput, $prevBytes.Length, $payloadBytes.Length)

    $hmac = [System.Security.Cryptography.HMACSHA256]::new($Key)
    try {
        $recordTag = ConvertTo-LowerHex -Bytes $hmac.ComputeHash($chainInput)
    } finally {
        $hmac.Dispose()
    }

    $line = $payload + '|' + $recordTag + "`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($LogPath, $line, $utf8NoBom)
}

# --- Verify-AuditChain: the D-08 / WR-01 / T-03-13 chain VERIFIER (the read-side detector) -------
# Append-AuditRecord builds the chain; this recomputes it from genesis forward and reports the first
# break, closing the repudiation gap (delete/edit/truncate guard-audit.log -> detected next run).
#
# For each on-disk line "<payload>|<record_tag>": split on the LAST '|' (the tag is fixed-form
# lowercase hex with no '|'), then expected_tag = HMAC(key, prevTagBytes || payloadBytes), with
# prevTag = $AuditGenesisTag for the first record and the prior record's STORED tag thereafter.
# Compare expected vs stored with the SAME ConvertTo-LowerHex + -eq ordinal path the rest of the
# guard uses (no weaker compare introduced). The first mismatch -> Ok=$false with its index + reason.
#
# Truncation-to-empty boundary (documented per the plan): an ABSENT log is genesis state -> Ok=$true
# (nothing has ever been written, nothing to verify). A PRESENT-but-shorter/garbled log is a break:
# any line missing its '|' tag separator, or whose stored tag does not re-derive, fails. We cannot
# distinguish "honestly empty" from "truncated to zero bytes" without external state, so an absent
# file is treated as Ok and a present file is verified record-by-record from genesis.
function Verify-AuditChain {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][byte[]]$Key,
        [Parameter(Mandatory)][string]$LogPath
    )
    $result = [PSCustomObject]@{
        Ok            = $true
        BrokenAtIndex = -1
        Reason        = ''
    }
    # Absent log = genesis state. Nothing was ever appended -> nothing to verify (Ok).
    if (-not (Test-Path $LogPath)) {
        return $result
    }
    try {
        $existing = [System.Text.Encoding]::UTF8.GetString((Get-FileBytes -Path $LogPath))
    } catch {
        # Present-but-unreadable log -> treat as a break (the bytes exist but cannot be parsed).
        $result.Ok = $false
        $result.BrokenAtIndex = 0
        $result.Reason = 'audit log present but unreadable'
        return $result
    }
    # @(...) forces an array so a single surviving line stays a whole record (not a char-indexable
    # string). Drop empty splits (the trailing LF after the last record yields one).
    $lines = @($existing -split "`n" | Where-Object { $_ -ne '' })
    if ($lines.Count -eq 0) {
        # Present file that holds no records (e.g. truncated to zero bytes / only newlines). We
        # cannot prove it was truncated without external state, so this matches the absent case: Ok.
        return $result
    }

    $hmac = [System.Security.Cryptography.HMACSHA256]::new($Key)
    try {
        $prevTag = $AuditGenesisTag
        for ($i = 0; $i -lt $lines.Count; $i++) {
            $rec = $lines[$i]
            # The record_tag is the field after the FINAL '|'; everything before it is the payload.
            $sep = $rec.LastIndexOf('|')
            if ($sep -lt 0) {
                $result.Ok = $false
                $result.BrokenAtIndex = $i
                $result.Reason = "record $i has no tag separator (garbled/truncated line)"
                return $result
            }
            $payload   = $rec.Substring(0, $sep)
            $storedTag = $rec.Substring($sep + 1)

            $prevBytes    = [System.Text.Encoding]::UTF8.GetBytes($prevTag)
            $payloadBytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
            $chainInput   = New-Object byte[] ($prevBytes.Length + $payloadBytes.Length)
            [Array]::Copy($prevBytes, 0, $chainInput, 0, $prevBytes.Length)
            [Array]::Copy($payloadBytes, 0, $chainInput, $prevBytes.Length, $payloadBytes.Length)
            $expectedTag = ConvertTo-LowerHex -Bytes $hmac.ComputeHash($chainInput)

            if ($expectedTag -ne $storedTag) {
                $result.Ok = $false
                $result.BrokenAtIndex = $i
                $result.Reason = "record $i tag mismatch (chain broken: delete/edit/truncate)"
                return $result
            }
            # Chain forward off the STORED tag (== expected here) so a later edit is still caught.
            $prevTag = $storedTag
        }
    } finally {
        $hmac.Dispose()
    }
    return $result
}

# --- Resolve guard-side true-time (test seam OR real SNTP) --------------------------------------
$decision      = 'deny'
$reason        = 'curfew'
$graceRemaining = 0

# CR-01: the override seam injects true-time AND skips clock-tamper detection, which would let any
# invoker force decision=allow against the anti-me model. Gate it behind a test-only env signal the
# production host never sets. Without NIGHTGUARD_TEST_NTP_OVERRIDE=1 a passed override is IGNORED and
# the real SNTP + clock-tamper path runs.
$overrideAllowed = ($env:NIGHTGUARD_TEST_NTP_OVERRIDE -eq '1')
if (($NtpOverrideUnixSecs -ge 0) -and $overrideAllowed) {
    # Test seam (mirrors Rust FakeTrueTime): inject a deterministic true-now. Skips the SNTP query
    # AND the clock-tamper check so verdict tests stay deterministic regardless of the host clock.
    $trueNow = [int64]$NtpOverrideUnixSecs
    $usedOverride = $true
} else {
    # Production uses the built-in public NTP server. $env:NIGHTGUARD_NTP_SERVER lets the exit gate
    # point the SNTP query at an unroutable address (RFC 5737 TEST-NET) to exercise the D-07
    # fail-closed offline path deterministically; it is NEVER set in normal operation.
    if (-not [string]::IsNullOrWhiteSpace($env:NIGHTGUARD_NTP_SERVER)) {
        $trueNow = Get-GuardNtpUnixSecs -Server $env:NIGHTGUARD_NTP_SERVER
    } else {
        $trueNow = Get-GuardNtpUnixSecs
    }
    $usedOverride = $false
}

if ($null -eq $trueNow) {
    # D-07: no verifiable true time -> deny + fail_closed. The config revert above already ran (it
    # needs no clock); we simply never honor a grace window we cannot time. Never trust last-known.
    $decision   = 'deny'
    $reason     = 'ntp unreachable'
    $failClosed = $true
}
elseif ((-not $usedOverride) -and ([Math]::Abs($trueNow - [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) -gt 300)) {
    # A4 clock-tamper: the local clock is >5 min off verified true-now. The grace window is only
    # 8 min, so a skew this large is treated as tamper -> deny + fail_closed (only checked against
    # real SNTP; the override seam bypasses it so tests are clock-independent).
    $decision   = 'deny'
    $reason     = 'clock tamper'
    $failClosed = $true
}
else {
    # Verified true time in hand. Honor an ACTIVE grace window only when state-verify TRUSTED the
    # state ($stateValid) AND the on-disk window covers true-now; otherwise re-lock (curfew). A
    # worst-case state (state_hmac mismatch -> $stateValid=false) can never produce an allow: the
    # guard refuses the window regardless of what the tampered guard.json claims (T-03-15, GARD-03).
    # In the trusted branch $graceUsed == ($null -ne grace), so a present window is the live grant;
    # $stateValid is the load-bearing gate, the grace presence + window_end > trueNow is the grant.
    if ($stateValid -and ($null -ne $guardObj) -and ($null -ne $guardObj.grace) `
            -and ([int64]$guardObj.grace.window_end -gt $trueNow)) {
        $decision       = 'allow'
        $reason         = 'grace active'
        $graceRemaining = [int64]$guardObj.grace.window_end - $trueNow
    } else {
        $decision       = 'deny'
        $reason         = 'curfew'
        $graceRemaining = 0
    }
}

# --- D-08 audit: append exactly one HMAC-chained record for this fire ---------------------------
# Timestamp = ISO-8601 true-time where available (else the verifiable-time-absent marker). The
# detail carries the decision + reverted/fail_closed summary so the log is a self-describing trail.
if ($null -ne $trueNow) {
    $auditTs = [System.DateTimeOffset]::FromUnixTimeSeconds([int64]$trueNow).UtcDateTime.ToString('yyyy-MM-ddTHH:mm:ssZ')
} else {
    $auditTs = 'NTP-UNREACHABLE'
}

# WR-01 / T-03-13: VERIFY the existing chain BEFORE appending this fire's record. A detected break
# (delete/edit/truncate of guard-audit.log) is surfaced to the verdict and logged forward as its own
# 'chain-broken' record. Repudiation detection NEVER changes the curfew verdict: the decision stays
# exactly as computed above -- the break is recorded + surfaced, not used to loosen anything. A
# verifier exception is itself treated as a break (fail-evident), never silently swallowed.
$auditChainBroken = $false
$auditChainBreakIndex = -1
try {
    $chainResult = Verify-AuditChain -Key $key -LogPath $auditLog
    if (-not $chainResult.Ok) {
        $auditChainBroken = $true
        $auditChainBreakIndex = [int]$chainResult.BrokenAtIndex
    }
} catch {
    $auditChainBroken = $true
    $auditChainBreakIndex = -1
}

# If the chain is broken, emit a dedicated 'chain-broken' record FIRST so the event is logged forward
# from the current last tag (the break itself becomes part of the now-continuing trail). This must
# not crash the guard into a permissive state, so it is wrapped like the guard-fire append below.
if ($auditChainBroken) {
    try {
        $breakDetail = "break_index=$auditChainBreakIndex reason=$($chainResult.Reason)"
        Append-AuditRecord -Key $key -LogPath $auditLog -Timestamp $auditTs -EventType 'chain-broken' -Detail $breakDetail
    } catch {
        # A chain-broken append failure must not crash the guard. The break is still surfaced in the
        # verdict JSON below (audit_chain_broken=true), so the signal is not lost.
    }
}

$auditDetail = "decision=$decision reason=$reason grace_remaining_secs=$graceRemaining reverted=$reverted fail_closed=$failClosed"
try {
    Append-AuditRecord -Key $key -LogPath $auditLog -Timestamp $auditTs -EventType 'guard-fire' -Detail $auditDetail
} catch {
    # An audit-append failure must not crash the guard into a permissive state. The verdict still
    # stands (deny-leaning); surface nothing to stdout beyond the verdict JSON below.
}

# --- D-01 / D-02 output: host-agnostic verdict JSON on stdout + exit code -----------------------
# Deliberately NOT the Claude-Code {continue,decision,reason} schema. The host decides what a deny
# does; the guard is a pure verified-state oracle. exit 0 = allow, non-zero = deny.
$verdict = [PSCustomObject]@{
    decision               = $decision
    reason                 = $reason
    grace_remaining_secs   = $graceRemaining
    reverted               = $reverted
    fail_closed            = $failClosed
    audit_chain_broken     = $auditChainBroken
    audit_chain_break_index = $auditChainBreakIndex
}
$verdict | ConvertTo-Json -Compress -Depth 5

if ($decision -eq 'allow') { exit 0 } else { exit 1 }
