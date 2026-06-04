---
phase: 01-trust-kernel
plan: 03
subsystem: interop
tags: [rust, powershell, dpapi, hmac-sha256, interop, exit-gate, windows, cross-language]

# Dependency graph
requires:
  - "01-02: trust-kernel public API (dpapi_protect/unprotect, sign_bytes/verify_bytes/tag_to_hex, load_or_create_key, write_canonical_text)"
provides:
  - "interop_cli — Rust binary driving the cross-language gate (gen-key/unprotect-key/protect-key/sign-file/verify-file/write-config)"
  - "scripts/interop/nightguard_interop.ps1 — PowerShell DPAPI+HMAC parity functions (the guard's eventual building blocks)"
  - "scripts/interop/run_interop_gate.ps1 — the runnable Phase 1 exit gate (both-direction round-trip + tamper assertions)"
  - "PROVEN: byte-identical Rust<->PowerShell DPAPI key round-trip and HMAC tag, both directions, on real Windows DPAPI"
affects: [powershell-guard, config-signing, state-signing, phase-2-and-beyond]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "interop_cli is argv-matched (no clap) with distinct exit codes (0 ok / 1 error / 2 verify-failed) so the harness asserts precisely"
    - "PowerShell side uses ONLY .NET framework crypto ([ProtectedData], [HMACSHA256]) — no third-party modules, no SecureString, no Get-Content"
    - "Gate runs against a temp dir under target/ (same volume; never the global TEMP) and exits non-zero on ANY mismatch"
    - "Harness is pwsh-first with a documented Windows PowerShell 5.1 fallback (the .NET crypto APIs are identical across both hosts)"

key-files:
  created:
    - crates/trust-kernel/src/bin/interop_cli.rs
    - scripts/interop/nightguard_interop.ps1
    - scripts/interop/run_interop_gate.ps1
    - scripts/interop/README.md
  modified:
    - crates/trust-kernel/Cargo.toml

key-decisions:
  - "interop_cli signs the RAW bytes on disk (no re-canonicalization at sign time) — the file IS the canonical artifact, so cosmetic CRLF/BOM/trailing-newline drift is detected as tamper"
  - "Harness made host-agnostic: prefers pwsh, runs identically under Windows PowerShell 5.1 (only pwsh 5.1 was installed on this machine); [ProtectedData]/[HMACSHA256] are framework types shared by both hosts"
  - "Gate uses the same 32-byte key on both sides by having PS DPAPI-protect a known key to a blob Rust loads — guaranteeing the HMAC comparison is over identical key material"

patterns-established:
  - "The PowerShell parity functions (Protect/Unprotect-GuardKey, Get-FileBytes, Get-FileHmacHex) are the canonical building blocks the Phase 3 auto-revert guard will reuse"
  - "Native-command stderr (cargo progress, interop_cli diagnostics) is captured with a locally-relaxed $ErrorActionPreference and gated on $LASTEXITCODE, never promoted to a terminating error"

requirements-completed: [KERN-01, KERN-02, KERN-04]

# Metrics
duration: 10min
completed: 2026-06-04
---

# Phase 1 Plan 03: Cross-Language Trust-Kernel Exit Gate Summary

**The Phase 1 exit gate is GREEN on real Windows: a Rust `interop_cli` and a PowerShell harness prove the DPAPI key round-trips byte-identically Rust<->PowerShell (exactly 32 bytes, never 64), the HMAC-SHA256 tag is byte-identical in both signing directions over raw file bytes, and CRLF/BOM tampers are flagged on both sides — closing the single genuine technical risk of the project.**

## The Exit-Gate Proof (real run, this interactive CurrentUser session)

`powershell -NoProfile -File scripts/interop/run_interop_gate.ps1` → **exit 0**, verbatim:

```
=== Nightguard cross-language exit gate ===
CLI: C:\Users\20252128\dev\Projects\nightguard-control\target\debug\interop_cli.exe
Work dir: C:\Users\20252128\dev\Projects\nightguard-control\target\interop_gate
PowerShell: 5.1.26100.8115

[PASS] DPAPI Rust->PS -- decrypted=32 bytes (expect 32); key match=True
[PASS] DPAPI PS->Rust -- rust exit=0; len(hex)=64 (expect 64); identical=True
[PASS] HMAC Rust->PS -- rust=636503a1e7b7dbaa... ps=636503a1e7b7dbaa... identical=True
[PASS] HMAC PS->Rust -- rust verify-file exit=0 (expect 0)
[PASS] Tamper CRLF/BOM -- CRLF: ps-mismatch=True rust-exit=2; BOM: ps-mismatch=True rust-exit=2 (all must be true/2)
[PASS] KERN-04 config readback -- hasCR=False hasBOM=False exactlyOneTrailingLF=True

=== Summary ===
  DPAPI Rust->PS           PASS
  DPAPI PS->Rust           PASS
  HMAC Rust->PS            PASS
  HMAC PS->Rust            PASS
  Tamper CRLF/BOM          PASS
  KERN-04 config readback  PASS

ALL CHECKS PASSED -- Phase 1 exit gate is GREEN. DPAPI key round-trips to 32 bytes both directions; HMAC tags byte-identical; tamper detected both sides.
GATE_EXIT=0
```

This was **not stubbed or simulated** — it exercised real `CryptProtectData`/`CryptUnprotectData` (via `windows-dpapi` `Scope::User` in Rust and `[ProtectedData]` CurrentUser in PowerShell) and real .NET/RustCrypto HMAC-SHA256 over the same raw bytes. The crypto was not weakened to pass.

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-04T18:32Z
- **Completed:** 2026-06-04T18:42Z
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint, auto-approved under auto_advance)
- **Files modified:** 4 created, 1 modified

## Accomplishments

- **`interop_cli`** (Rust): argv-matched CLI (no clap) exposing every subcommand the harness drives — `gen-key`, `unprotect-key`, `protect-key`, `sign-file`, `verify-file`, `write-config` — with distinct exit codes (0 ok / 1 error / **2 verify-failed**). `gen-key`/`unprotect-key` round-trip the DPAPI key to identical 32 bytes (and reject any non-32 result, the 64-byte SecureString canary). `sign-file` HMACs the RAW bytes on disk; `verify-file` exits 2 on mismatch.
- **`nightguard_interop.ps1`** (PowerShell): `Protect-GuardKey`/`Unprotect-GuardKey` via `[System.Security.Cryptography.ProtectedData]::Protect/Unprotect($bytes, $null, CurrentUser)`; `Get-FileBytes` via `[System.IO.File]::ReadAllBytes`; `Get-FileHmacHex` via `[HMACSHA256]::new($keyBytes).ComputeHash($fileBytes)` → lowercase hex; `Write-RawBytes` via `WriteAllBytes`. **No SecureString, no `Get-Content`** anywhere on these paths (the only occurrences of those terms are in the explicit forbidding comment).
- **`run_interop_gate.ps1`**: orchestrates all six checks against a temp dir under `target/`, prints a PASS/FAIL line per check, and `exit 1` on any mismatch / `exit 0` only if all pass.
- **`README.md`**: how-to-run (pwsh and the 5.1 fallback), the locked-invariants table, and the honest-ceiling note (DPAPI ≠ protection against the user themselves; gate proves interop, not invulnerability; no obfuscation added).

## Task Commits

1. **Task 1: Rust interop CLI binary** — `1ca4363` (feat)
2. **Task 2: PowerShell harness functions + gate runner** — `6df89fb` (feat)
3. **Task 3: Human-verify the gate** — checkpoint; auto-approved under `auto_advance=true` (the gate had already been run to green non-interactively in this CurrentUser session; objective criteria — exit 0, 32-byte round-trip, tamper detected both sides — were satisfied by the real run above).

## Files Created/Modified

- `crates/trust-kernel/src/bin/interop_cli.rs` — the Rust side of the gate (6 subcommands, distinct exit codes)
- `crates/trust-kernel/Cargo.toml` — added explicit `[[bin]] name = "interop_cli"`
- `scripts/interop/nightguard_interop.ps1` — PowerShell DPAPI+HMAC parity functions
- `scripts/interop/run_interop_gate.ps1` — the six-check both-direction exit gate
- `scripts/interop/README.md` — run instructions, locked invariants, honest ceiling

## Decisions Made

- **Sign raw bytes, no re-canonicalization at sign time:** `interop_cli sign-file` HMACs exactly the bytes on disk. This is what makes the CRLF/BOM tamper checks meaningful — a cosmetic re-save diverges the tag on both sides.
- **Same key both sides by construction:** the gate has PowerShell DPAPI-protect a known 32-byte key to a blob that Rust then loads via `load_or_create_key`, so Checks 3/4 compare HMAC tags over provably-identical key material (not two independently-generated keys).
- **Host-agnostic harness:** written pwsh-first but runs under Windows PowerShell 5.1 (the only host installed here). The `[ProtectedData]`/`[HMACSHA256]` types are .NET framework types identical across 5.1 and 7, so the DPAPI/HMAC contract is unaffected by host choice.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `pwsh` (PowerShell 7) not installed — ran under Windows PowerShell 5.1**
- **Found during:** Task 2 (running the gate)
- **Issue:** The plan and checkpoint specify `pwsh -NoProfile -File`, but only Windows PowerShell 5.1 (`powershell.exe`) is installed on this machine; `pwsh` is not on PATH and no PowerShell 7 install exists.
- **Fix:** Made the harness host-agnostic and documented both invocations in the README. Verified the load-bearing .NET crypto APIs (`[ProtectedData]`, `[HMACSHA256]`) behave identically under 5.1 (DPAPI round-tripped to 32 bytes) before relying on it. The cross-language contract is unchanged — these are framework types, not host-specific. This was NOT a package install (no slopsquat risk); it is an environment fact, handled by making the script portable rather than substituting anything.
- **Files modified:** scripts/interop/run_interop_gate.ps1, scripts/interop/README.md
- **Commit:** `6df89fb`

**2. [Rule 1 - Bug] Em-dash literals broke under Windows PowerShell 5.1 `-File` parsing**
- **Found during:** Task 2 (first gate run)
- **Issue:** The script's `—` (em-dash) characters in string literals were mis-decoded by 5.1 (no BOM; 5.1 reads `-File` scripts in the system codepage, not UTF-8), producing parser errors.
- **Fix:** Replaced all em-dashes with ASCII `--` (codepage-safe in both hosts).
- **Files modified:** scripts/interop/run_interop_gate.ps1
- **Commit:** `6df89fb`

**3. [Rule 1 - Bug] cargo stderr promoted to a terminating error; `List[byte].AddRange` cast failure**
- **Found during:** Task 2 (gate runs 2 and 3)
- **Issue:** (a) Under `$ErrorActionPreference='Stop'`, cargo's stderr progress was promoted to a `NativeCommandError`; (b) `$list.AddRange($bytesFromReadAllBytes)` failed because PowerShell surfaced the `byte[]` as `Object[]`, breaking the `IEnumerable<byte>` cast in the BOM-tamper builder.
- **Fix:** (a) Capture native-command output with a locally-relaxed `$ErrorActionPreference` and gate on `$LASTEXITCODE`; (b) append the BOM bytes with a `foreach` loop instead of `AddRange`.
- **Files modified:** scripts/interop/run_interop_gate.ps1
- **Commit:** `6df89fb`

All three are harness-portability/robustness fixes; none weakened the crypto or the assertions. The DPAPI scope (CurrentUser), entropy (null), raw-blob format, raw-bytes HMAC, lowercase hex, and the 32-not-64 canary all match the locked invariants exactly.

## Authentication Gates

None.

## Issues Encountered

- Git emitted `LF will be replaced by CRLF` warnings on the `.rs`/`.toml`/`.ps1`/`.md` source files. These are source files, not the signed artifacts (`config*.yaml`/`*.guardkey`, which are `-text` via `.gitattributes` and git-ignored). Harmless — same as Plans 01/02.

## Threat Model Coverage

- **T-01-10 (Tampering, cross-language key-format divergence):** mitigated — gate asserts PS `[ProtectedData]` blob ↔ Rust `dpapi` round-trips to exactly 32 bytes both directions; the 64-byte SecureString canary would fail loud (it did not — decrypted=32).
- **T-01-11 (Tampering, HMAC canonicalization drift):** mitigated — Rust and PS tags are byte-identical over `ReadAllBytes`/`std::fs::read`; CRLF and BOM mutated copies read as tampered on BOTH sides (PS tag mismatch + Rust `verify-file` exit 2).
- **T-01-12 (Spoofing, hand-edit producing a matching tag):** mitigated — the tamper checks prove cosmetic EOL/BOM edits diverge the tag; only the keyed signer reproduces it.
- **T-01-13 (Honesty):** accepted — README states the honest ceiling (DPAPI ≠ protection against the user scripting DPAPI as themselves); the gate proves interop, not invulnerability; no obfuscation added.
- **T-01-SC (Supply chain):** mitigated — PowerShell uses ONLY .NET framework crypto (`[ProtectedData]`/`[HMACSHA256]`); no third-party PS modules installed; Rust deps unchanged from Plan 02 (no new crates added).

## Known Stubs

None — the gate is fully wired and actually ran to green against real DPAPI and real HMAC. No placeholders, no `#[ignore]`, no simulated output.

## Threat Flags

None — no new security surface beyond the plan's threat_model. The interop_cli is a test/gate harness driver, not a network or privileged surface.

## Next Phase Readiness

- The single genuine technical risk for Phase 1 (and the project) is **closed**: Rust and PowerShell agree byte-for-byte on both the DPAPI key and the HMAC tag, both directions, on real Windows.
- The PowerShell parity functions in `nightguard_interop.ps1` are the canonical building blocks the Phase 3 auto-revert guard will reuse (same `[ProtectedData]`/`ReadAllBytes`/`HMACSHA256` calls).
- Phase 2 can proceed on the locked contracts: raw DPAPI blob (`Scope::User`/`CurrentUser`, no entropy), lowercase-hex HMAC tag over raw file bytes, canonical config (UTF-8/no-BOM/LF/one trailing newline).

## Self-Check: PASSED

All 4 created files exist on disk; the 1 modified file (Cargo.toml) carries the `[[bin]]` entry. Both task commits (`1ca4363`, `6df89fb`) are present in git history. `cargo build --bin interop_cli` exits 0. The gate (`run_interop_gate.ps1`) was run live and exited 0 with all six checks PASS. Forbidden-API grep on `nightguard_interop.ps1` returns 0 matches outside comments; `ProtectedData|ReadAllBytes` count = 6 (>= 2).

---
*Phase: 01-trust-kernel*
*Completed: 2026-06-04*
