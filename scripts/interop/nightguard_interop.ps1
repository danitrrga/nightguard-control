# nightguard_interop.ps1 — PowerShell parity functions for the Phase 1 cross-language exit gate.
#
# These functions are the PowerShell half of the DPAPI + HMAC trust kernel. They MUST be
# byte-identical to the Rust side (crates/trust-kernel: dpapi.rs + hmac.rs).
#
# LOCKED INVARIANTS (PITFALLS Pitfall 1 + 2 / threats T-01-10..12):
#   - DPAPI: raw [System.Security.Cryptography.ProtectedData]::Protect/Unprotect,
#     CurrentUser scope, $null optional entropy on BOTH protect and unprotect.
#   - HMAC: over the RAW FILE BYTES read with [System.IO.File]::ReadAllBytes(...).
#     Key = 32 RAW bytes (never its hex/base64 string). Tags compared as lowercase hex.
#
# FORBIDDEN on these paths (each silently breaks cross-language parity):
#   - ConvertTo-SecureString / ConvertFrom-SecureString  -> SecureString + UTF-16 framing;
#     the tell-tale is a 64-byte "key" coming back instead of 32. NEVER use these here.
#   - Get-Content                                        -> normalizes line endings / encoding;
#     would produce a false tamper. NEVER use it to read bytes for hashing.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# System.Security carries [ProtectedData] on Windows PowerShell; on PowerShell 7 the type
# is in the loaded framework. Add-Type is a no-op/safe if already present.
try { Add-Type -AssemblyName System.Security -ErrorAction SilentlyContinue } catch { }

function Protect-GuardKey {
    # DPAPI-protect 32 raw key bytes as a RAW blob (CurrentUser, no entropy).
    [CmdletBinding()]
    param([Parameter(Mandatory)][byte[]]$KeyBytes)
    if ($KeyBytes.Length -ne 32) {
        throw "Protect-GuardKey expects exactly 32 raw key bytes, got $($KeyBytes.Length)"
    }
    return [System.Security.Cryptography.ProtectedData]::Protect(
        $KeyBytes, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
}

function Unprotect-GuardKey {
    # DPAPI-unprotect a RAW blob produced by Rust dpapi_protect or PowerShell Protect-GuardKey.
    # Returns the raw plaintext bytes; the caller asserts length == 32 (the 32-not-64 canary).
    [CmdletBinding()]
    param([Parameter(Mandatory)][byte[]]$Blob)
    return [System.Security.Cryptography.ProtectedData]::Unprotect(
        $Blob, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
}

function Get-FileBytes {
    # Read the RAW bytes of a file. NEVER Get-Content (it normalizes EOL/encoding).
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Path)
    return [System.IO.File]::ReadAllBytes($Path)
}

function Write-RawBytes {
    # Write raw bytes verbatim (no encoding transform, no BOM, no EOL rewrite).
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][byte[]]$Bytes
    )
    [System.IO.File]::WriteAllBytes($Path, $Bytes)
}

function ConvertTo-LowerHex {
    # Lowercase hex of a byte array, matching Rust hex::encode / tag_to_hex.
    [CmdletBinding()]
    param([Parameter(Mandatory)][byte[]]$Bytes)
    return [System.BitConverter]::ToString($Bytes).Replace('-', '').ToLowerInvariant()
}

function ConvertFrom-LowerHex {
    # Parse a lowercase/uppercase hex string into a byte array.
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Hex)
    $h = $Hex.Trim()
    if ($h.Length % 2 -ne 0) { throw "hex string has odd length: $($h.Length)" }
    $out = New-Object byte[] ($h.Length / 2)
    for ($i = 0; $i -lt $out.Length; $i++) {
        $out[$i] = [System.Convert]::ToByte($h.Substring($i * 2, 2), 16)
    }
    return $out
}

function Get-FileHmacHex {
    # HMAC-SHA256 over the RAW file bytes with the 32 RAW key bytes; return lowercase hex.
    # Mirrors Rust sign_bytes + tag_to_hex exactly.
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][byte[]]$KeyBytes,
        [Parameter(Mandatory)][string]$Path
    )
    $fileBytes = Get-FileBytes -Path $Path
    $hmac = [System.Security.Cryptography.HMACSHA256]::new($KeyBytes)
    try {
        $tag = $hmac.ComputeHash($fileBytes)
    } finally {
        $hmac.Dispose()
    }
    return ConvertTo-LowerHex -Bytes $tag
}
