# state_interop.ps1 -- PowerShell parity helper for the Phase 2 state_hmac gate.
#
# This is the PowerShell half of the guard.json state_hmac recipe (Assumption A3 /
# threat T-02-01). The Phase 3 PowerShell guard MUST re-derive state_hmac identically or it
# will treat legitimate state as tampered (fail-closed) on every run.
#
# The Rust bin (crates/mutation-engine/src/bin/state_interop_cli.rs) emits the EXACT pre-sign
# canonical bytes to a <guard.json>.signbytes file. This lib HMAC-SHA256s those raw bytes
# verbatim with the 32 raw key bytes -- NO re-canonicalization at sign time, exactly like the
# Phase 1 file HMAC. That is why the tags are byte-identical: both sides sign the same bytes.
#
# Windows PowerShell 5.1 compatible: ASCII only, [HMACSHA256]/[IO.File] are identical .NET
# types in 5.1 and 7, no SecureString framing, no Get-Content (it normalizes EOL/encoding).
#
# Reuses the Phase 1 helpers (Protect/Unprotect-GuardKey, Get-FileBytes, Write-RawBytes,
# ConvertTo-LowerHex, ConvertFrom-LowerHex, Get-FileHmacHex) by dot-sourcing them.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$stateInteropHere = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $stateInteropHere 'nightguard_interop.ps1')

function Get-StateHmacHex {
    # HMAC-SHA256 over the EXACT pre-sign canonical bytes the Rust bin emitted (the .signbytes
    # file), using the 32 raw key bytes. Returns lowercase hex. This is the PS re-derivation of
    # the locked A3 state_hmac recipe -- it signs the identical bytes Rust signed, so the tags
    # match byte-for-byte. Get-FileHmacHex (Phase 1) already does raw-bytes HMAC + lowercase
    # hex; reuse it so there is one HMAC code path across both gates.
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][byte[]]$KeyBytes,
        [Parameter(Mandatory)][string]$SignBytesPath
    )
    return Get-FileHmacHex -KeyBytes $KeyBytes -Path $SignBytesPath
}
