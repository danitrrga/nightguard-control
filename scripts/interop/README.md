# Cross-language interop exit gate (Phase 1)

This directory holds the **Phase 1 exit gate**: a proof that the DPAPI + HMAC trust kernel
behaves **byte-identically across Rust and PowerShell, in both directions**. It is the single
genuine technical risk of the project — if the two languages disagree on the signing key or the
HMAC tag, the auto-revert guard either does nothing or destroys legitimate edits.

## Run it

From the repo root:

```powershell
pwsh -NoProfile -File scripts/interop/run_interop_gate.ps1
```

If PowerShell 7 (`pwsh`) is not installed, Windows PowerShell works identically — the gate uses
only the .NET framework crypto types (`[ProtectedData]`, `[HMACSHA256]`), which are the same in
both hosts:

```powershell
powershell -NoProfile -File scripts/interop/run_interop_gate.ps1
```

The script builds `interop_cli` (the Rust side), runs all six checks against a temp dir under
`target/interop_gate/`, prints a `PASS`/`FAIL` line per check, and **exits 0 only if every check
passes** (exit 1 on any mismatch). `echo $LASTEXITCODE` afterward to confirm.

## Files

- `nightguard_interop.ps1` — PowerShell parity functions: `Protect-GuardKey` / `Unprotect-GuardKey`
  (`[ProtectedData]`, CurrentUser, `$null` entropy), `Get-FileBytes` (`[IO.File]::ReadAllBytes`),
  `Get-FileHmacHex` (`[HMACSHA256]` over raw bytes -> lowercase hex), `Write-RawBytes`.
- `run_interop_gate.ps1` — the harness that drives both directions and the tamper assertions.

## Locked invariants (must hold on BOTH sides, forever)

| Invariant | Rust | PowerShell |
|-----------|------|------------|
| DPAPI blob format | raw `CryptProtectData` (`windows-dpapi` `Scope::User`, `None`) | `[ProtectedData]::Protect/Unprotect`, `CurrentUser`, `$null` entropy |
| DPAPI scope | `Scope::User` (CurrentUser) | `DataProtectionScope::CurrentUser` |
| DPAPI entropy | `None` | `$null` |
| Key form | 32 **raw** bytes | 32 **raw** bytes (never hex/base64 string) |
| HMAC input | raw file bytes (`std::fs::read`) | raw file bytes (`[IO.File]::ReadAllBytes`) — **never `Get-Content`** |
| Tag form | lowercase hex (`hex::encode`) | lowercase hex (`BitConverter ... ToLowerInvariant`) |
| 32-not-64 canary | `BadKeyLength` rejects non-32 | gate asserts decrypted length == 32, fails loud on 64 |

**Forbidden** on these paths (each silently breaks parity): `ConvertTo-SecureString` /
`ConvertFrom-SecureString` (SecureString + UTF-16 framing — the tell-tale is 64 bytes back),
and `Get-Content` (normalizes EOL/encoding — false tamper).

## The honest ceiling (PITFALLS Pitfall 5)

This gate proves **interop**, not **invulnerability**. DPAPI CurrentUser protects the key against
*other* users and offline disk theft — it does **not** protect against the user scripting DPAPI as
themselves. An admin running as this user can extract or forge the HMAC key. That is by design and
within scope: the goal is friction past the impulse threshold, not an absolute lock. **No obfuscation,
decoys, or anti-debugging are added** — they would only frustrate, never protect (see PROJECT.md
"Out of Scope" and PITFALLS Pitfall 5).
