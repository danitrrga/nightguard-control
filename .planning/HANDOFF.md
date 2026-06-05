# Nightguard Control — Resume Handoff

**Updated:** 2026-06-05
**Status:** Phase 1 of 5 COMPLETE & verified. Resume at Phase 2.

## One-line resume

After `/clear`, open this repo (`dev/Projects/nightguard-control`) and run:

```
/gsd:plan-phase 2
```

(YOLO mode is on — it will plan, plan-check, then `/gsd:execute-phase 2` continues the build.)

## What this project is

The **publishable** product repo for Nightguard Control — a Windows self-binding ("anti-me")
curfew/config manager (Tauri v2 + Rust + PowerShell hooks). Daniel's **personal instance**
(his config, state, hook wiring) lives separately in `LifeOS/nightguard/`. Full approved
design: `docs/design-spec.md`. Wiki entity: `LifeOS/vault/9 - Wiki/entities/nightguard-control.md`.

## Done — Phase 1: Trust Kernel ✅

`crates/trust-kernel/` (plain Rust lib, NO Tauri yet — that's Phase 4). 32 tests green.
- `canonicalize_bytes` (BOM strip / CRLF→LF / one trailing newline, raw-bytes, idempotent)
- `atomic_write` / `write_canonical_text` (temp→fsync→rename; prior file survives failure)
- HMAC-SHA256 sign/verify over **raw file bytes** (hmac 0.12 / sha2 0.10, constant-time, RFC 4231 KAT)
- DPAPI key store (raw `CryptProtectData`, `Scope::User`, no entropy, 32-not-64 SecureString-trap canary)
- `interop_cli` + `scripts/interop/run_interop_gate.ps1`
- **Exit gate proven green 6/6:** Rust↔PowerShell DPAPI key + HMAC byte-identical both directions; CRLF/BOM tamper detected both sides; clean config readback. The project's single biggest risk is closed.

## Locked decisions carried forward

- **HMAC = raw file bytes** (not canonical-JSON). Writer emits one byte form: UTF-8, no BOM, LF, exactly one trailing newline. PowerShell reads via `[IO.File]::ReadAllBytes`. Key = 32 raw bytes.
- **DPAPI = raw blob, CurrentUser, no entropy.** Never PowerShell `ConvertFrom-SecureString`.
- Direction classifier = **Rust-only**; the guard is **direction-agnostic** (reverts anything whose signature doesn't match).
- `.gitattributes` marks `config*.yaml` / `*.guardkey` as `-text` so git never alters their bytes.

## Environment gotcha (important)

This machine has **Windows PowerShell 5.1, not pwsh 7**. All PowerShell scripts/harnesses must
stay 5.1-compatible: ASCII only (no em-dash literals in `-File` scripts), build byte lists with
`foreach` (no `List[byte].AddRange` casts), relax `$ErrorActionPreference` around cargo stderr and
gate on `$LASTEXITCODE`. `[ProtectedData]` / `[HMACSHA256]` are identical .NET types in 5.1 and 7.

## Next phases (roadmap)

- **Phase 2 — Mutation Engine:** direction classifier, 3/week token quota (DST-aware Monday reset),
  NTP grace (sntpc 0.10 — verify `sync::get_time` sig), atomic ordered commit (sanctioned + state
  before live config) under a single-writer lock. Reqs RULE-01..06.
- **Phase 3 — Enforcement Guard:** PowerShell verify→auto-revert, fail-closed, grace re-check.
  ⚠ Verify hook-path resolution under Claude Code junctions first (`$PSScriptRoot\..` may resolve to
  the drifted `~/.claude/nightguard`). Reqs GARD-01..06.
- **Phase 4 — UI (Moonlit Indigo):** Tauri app. Palette `--bg #0c0e14 --surface #161a24 --border
  #242a38 --text #e8eaf0 --dim #8b91a3 --accent #7aa2ff`, Roboto, left icon rail, flat cards, locked
  = bright text + 🌙 badge. Reqs UI-01..05.
- **Phase 5 — Instance Wiring:** point Daniel's live hook at the LifeOS canonical config (fix the
  `~/.claude` drift); init his instance. Reqs WIRE-01..02.
