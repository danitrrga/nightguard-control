# Phase 3: Enforcement Guard - Research

**Researched:** 2026-06-08
**Domain:** Windows PowerShell 5.1 cross-language security guard (HMAC verify, DPAPI, atomic revert, SNTP, integrity baseline)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Curfew-gate enforcement boundary (GARD-04)**
- **D-01:** The guard is a **pure verified-state oracle**, not the enforcer. On each fire it (a) unconditionally performs the config integrity-check + auto-revert, then (b) emits a curfew/grace **verdict**. The host decides what to do with a deny. Keeps this publishable repo host-agnostic; the teeth are a thin host adapter (Phase 5 / personal LifeOS instance maps `deny → block`).
- **D-02:** **Output contract:** exit code + JSON on stdout. `exit 0 = allow`, non-zero = deny. JSON object shape: `{decision, reason, grace_remaining_secs, reverted, fail_closed}`. A host can rely on the exit code alone OR parse the JSON. Deliberately NOT the Claude-Code-native `{continue,decision,reason}` schema.

**Fail-closed strict default (GARD-02)**
- **D-03:** When BOTH live and sanctioned config are invalid, write a hardcoded **maximal-lockout** default: curfew always-on (24/7), no grace available, zero tokens. Worst case is maximally restrictive, never permissive. Forces an in-app repair. Logged.

**State-tamper repair semantics (GARD-03)**
- **D-04:** When signed state is invalid/tampered, the guard runtime-treats it as `weekly_spent=3` + grace-used (fail-closed) until re-sync.
- **D-05:** The DPAPI-gated in-app repair **blesses the worst-case for the current week**: re-signs `weekly_spent=3` + grace-used for the current `week_anchor`, making state valid again but forfeiting the rest of the week (natural Monday reset restores tokens). **Tampering state is pure loss, never a gain.** The DPAPI gate only proves the actor holds the key — NOT a loosening lever. Explicitly rejected: clean slate (`weekly_spent=0`) and "re-sign current on-disk values".

**Revert circuit-breaker (GARD-05)**
- **D-06:** On a config HMAC mismatch, before reverting the guard checks the existing **fd-lock presence** at `<data_dir>/.nightguard.lock`. If the app holds it (commit in progress), the guard **skips the revert this cycle** — Phase 2's live-written-LAST ordering guarantees consistency moments later, and the next hook fire re-checks. Reuses the Phase 2 lock primitive; no new schema. (No fixed-delay retry as primary — the lock is the real signal.)

**NTP-offline gate behavior (GARD-04 edge)**
- **D-07:** If NTP is unreachable when the gate fires, **fail closed: deny grace, treat as curfew** (`decision=deny`, `fail_closed=true`). Config auto-revert still runs (needs no clock). Explicitly rejected: honoring last-known `window_end` from guard.json without re-checking.

**Audit log (GARD-01/02/03)**
- **D-08:** **Append-only, HMAC-chained** log at `<data_dir>/guard-audit.log`. One record per event (ISO-8601 true-time where available + event type + detail), each record chained with HMAC so any deletion/edit/truncation is detectable on the next run. (Plain log and Windows Event Log rejected.)

**Path configuration (Phase 5 wires the real values)**
- **D-09:** The guard takes a **single base directory** — `--data-dir` arg (or `NIGHTGUARD_DIR` env) — and uses **fixed filenames within it** for every artifact (`config.yaml`, sanctioned snapshot, `guard.json`, `.nightguard.lock`, DPAPI key blob, `guard-audit.log`). (Per-file args rejected.)

**Integrity baseline (GARD-06)**
- **D-10:** **Ship the integrity mechanism in-repo.** Phase 3 creates/extends `verify_hook_integrity.ps1`: records the SHA256 of the guard script(s) in a baseline file and alerts on drift; the guard self-registers in that baseline.

### Claude's Discretion
- Exact JSON field encodings/casing for the verdict object, log record delimiter/escaping, HMAC-chain construction details (e.g., prev-tag-in-next-record), and the precise fixed filenames — provided they honor the decisions above and the locked interop invariants.
- Whether the integrity baseline file is JSON or a flat `sha256  path` manifest.

### Deferred Ideas (OUT OF SCOPE)
- Repair-flow UI copy / UX surface — Phase 4 (UI). Phase 3 only ships the guard runtime posture + the re-sign contract the repair invokes.
- Real host hook wiring (pointing SessionStart/UserPromptSubmit at the canonical config) — Phase 5 (Instance Wiring).
- Log rotation / size management for `guard-audit.log` — not in scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GARD-01 | On SessionStart + UserPromptSubmit, verify config HMAC and auto-revert to sanctioned on mismatch (direction-agnostic). | §Config-Verify-Revert Pattern; reuse `Get-FileHmacHex` over canonical `config.yaml`; revert = `[IO.File]::Copy(sanctioned, live)` after circuit-breaker check. |
| GARD-02 | If sanctioned snapshot also invalid, write hardcoded strict default + log (fail-closed). | §Fail-Closed Strict Default; sanctioned has no standalone HMAC — validate by re-signing sanctioned-as-config and writing it only if it parses; on both-invalid write maximal-lockout YAML literal. |
| GARD-03 | If signed state invalid/tampered, treat `weekly_spent=3` + grace-used until re-sync; DPAPI-gated in-app repair path. | §State-Verify Path (the central parity finding); runtime worst-case substitution; repair is a Rust command (Phase 4 invokes) — Phase 3 ships the re-sign contract. |
| GARD-04 | Curfew gate honors active grace window — guard's own NTP, tamper-checked first — re-locks after expiry. | §Guard-Side SNTP; §Clock-Tamper Detection; verdict computation against `grace.window_end`. |
| GARD-05 | Never revert a legitimate in-app write (ordering + lock + circuit-breaker). | §Revert Circuit-Breaker; the `commit_order.rs` revert rule is the reference; probe `.nightguard.lock` before reverting. |
| GARD-06 | Guard registered in `verify_hook_integrity.ps1` SHA256 baseline. | §Integrity Baseline; new in-repo script + baseline manifest. |
</phase_requirements>

## Summary

Phase 3 is a **pure-PowerShell-5.1 reader/enforcer** that mirrors, in PowerShell, the exact byte-level contracts the Phase 1–2 Rust code established. There is essentially **no new technology to discover** — the stack (`[HMACSHA256]`, `[ProtectedData]`, `[IO.File]`, raw UDP for SNTP) is all .NET-framework built-ins already proven in `scripts/interop/nightguard_interop.ps1`. The entire risk surface is **input-canonicalization parity**, not library choice: every guard decision is "re-derive the exact bytes Rust signed, HMAC them, compare." The guard dot-sources the existing `nightguard_interop.ps1` + `state_interop.ps1` helpers for all DPAPI/HMAC/byte primitives and must **not** reimplement hashing or key unwrapping.

The single highest-value finding, **empirically verified this session**: the runtime `guard.json` on disk is `serde_json::to_vec_pretty` (indented), but the `state_hmac` is signed over a **freshly re-serialized compact `serde_json::to_string` form** (fields in struct-declaration order) with `state_hmac` blanked, then `canonicalize_bytes` (append exactly one trailing LF, no BOM, LF-only). I proved that PowerShell 5.1 `ConvertFrom-Json | ... | ConvertTo-Json -Compress -Depth 10` reproduces that compact form **byte-for-byte** for the real fixed state, blanked state, `grace:null`, empty `ledger:[]`, and large i64 timestamps (no float coercion, field order preserved). So the state-verify path is HIGH-confidence and does NOT require the `.signbytes` harness artifact at runtime — that file is a gate-only convenience.

**Primary recommendation:** Build one `nightguard_guard.ps1` that dot-sources the two interop libs, runs config-verify→circuit-breaker→revert unconditionally, then computes a grace/curfew verdict gated on a guard-side SNTP query (fail-closed on unreachable), emitting `{decision,reason,grace_remaining_secs,reverted,fail_closed}` on stdout with exit 0=allow / non-zero=deny. Re-derive `state_hmac` via `ConvertFrom-Json → blank → ConvertTo-Json -Compress -Depth 10 → UTF-8 no-BOM → append 0x0A → Get-FileHmacHex`. Add `verify_hook_integrity.ps1` + a SHA256 baseline manifest that self-registers the guard.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Config HMAC verify + auto-revert | Guard (PowerShell reader) | — | Rust is sole *writer*; the guard is the always-firing *reader/enforcer* (D-01). Reverting is a byte copy, no signing. |
| State HMAC verify | Guard (PowerShell reader) | — | Read-only re-derivation; the guard never writes a new valid state. |
| State **repair** (re-sign worst-case) | Rust app (Phase 4 command) | DPAPI gate | Only the writer/signer re-signs; the guard consumes the re-signed result (D-05). Phase 3 ships the *contract*, not the writer. |
| Grace/curfew verdict | Guard (PowerShell reader) | Host adapter (Phase 5) | Guard emits the verdict (D-01/D-02); host maps `deny→block`. |
| Guard-side NTP true-time | Guard (PowerShell, raw UDP) | — | "Guard's OWN NTP" (GARD-04) — app-side `sntpc` is advisory only; guard re-validates independently. |
| Single-writer lock | Rust (owner) | Guard (read-only probe) | Lock is created/held by Rust `commit`/`grace`; the guard only *probes* presence for the circuit-breaker (D-06). |
| Integrity baseline | Guard tooling (PowerShell) | — | In-repo `verify_hook_integrity.ps1` (D-10); pure SHA256 over scripts. |

## Standard Stack

### Core
| Library / Primitive | Version | Purpose | Why Standard |
|---------------------|---------|---------|--------------|
| Windows PowerShell | **5.1.26100.8115** (verified on this machine) | Guard runtime host | This machine runs WinPS 5.1, NOT pwsh 7. ASCII-only scripts, gate on `$LASTEXITCODE`. [VERIFIED: `$PSVersionTable.PSVersion` this session] |
| `System.Security.Cryptography.HMACSHA256` | .NET Framework built-in | HMAC verify of config + state | Identical type in 5.1 and 7; already the proven Phase 1 primitive (`Get-FileHmacHex`). [VERIFIED: scripts/interop/nightguard_interop.ps1] |
| `System.Security.Cryptography.ProtectedData` | .NET Framework built-in | DPAPI unprotect of `.guardkey` (CurrentUser, `$null` entropy) | The proven Phase 1 `Unprotect-GuardKey`. [VERIFIED: nightguard_interop.ps1] |
| `System.IO.File` (`ReadAllBytes`/`WriteAllBytes`/`Copy`) | .NET Framework built-in | Raw byte reads (NEVER `Get-Content`), raw revert copy | `Get-Content` normalizes EOL/encoding → false tamper. [VERIFIED: nightguard_interop.ps1 FORBIDDEN list] |
| `System.Net.Sockets.Socket`/`UdpClient` | .NET Framework built-in | Guard-side SNTP (hand-built 48-byte packet) | No .NET built-in SNTP client; the 48-byte-packet pattern is the documented standard. [CITED: chrisjwarwick.wordpress.com] |
| `System.Security.Cryptography.SHA256` | .NET Framework built-in | Integrity baseline (`verify_hook_integrity.ps1`) | `Get-FileHash -Algorithm SHA256` is the WinPS-native form. [ASSUMED] |

### Supporting (reused — do NOT reimplement)
| Helper | Source | Purpose |
|--------|--------|---------|
| `Protect/Unprotect-GuardKey` | `scripts/interop/nightguard_interop.ps1` | DPAPI raw-blob round-trip, CurrentUser, `$null` entropy, 32-not-64 canary. |
| `Get-FileBytes` / `Write-RawBytes` | `nightguard_interop.ps1` | `[IO.File]::ReadAllBytes/WriteAllBytes` — the only sanctioned byte I/O. |
| `Get-FileHmacHex` | `nightguard_interop.ps1` | HMAC-SHA256 over raw file bytes → lowercase hex. Used for BOTH config and (via temp/in-mem bytes) state. |
| `ConvertTo/From-LowerHex` | `nightguard_interop.ps1` | Hex parse/emit matching Rust `hex::encode`. |
| `Get-StateHmacHex` | `scripts/interop/state_interop.ps1` | HMAC over the pre-sign canonical state bytes. The guard's state-verify builds on this. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ConvertTo-Json -Compress` for state re-serialization | Hand-built JSON string concatenation in field order | Hand-building removes ALL dependence on PS JSON quirks but is more code and more error-prone. `-Compress` is **empirically byte-identical** to serde for the constrained field set (see §State-Verify Path) — prefer it, but the planner should add a parity test that proves equality against a Rust-emitted compact form, and fall back to hand-building only if a future field introduces escaping divergence. |
| Raw UDP SNTP in PowerShell | Shell out to the Rust `sntpc` path | Spec requires the guard's **OWN** NTP (GARD-04). Shelling to Rust couples the guard to a built binary and defeats the "independent re-validation" property. Hand-built UDP is ~40 lines, self-contained. |
| `Get-FileHash` (file-based) for integrity | `[SHA256]::Create().ComputeHash([IO.File]::ReadAllBytes())` | `Get-FileHash` is simpler and WinPS-native; either is fine. `Get-FileHash` reads bytes raw, so no EOL-normalization risk for the baseline. |

**No new external packages.** All primitives are .NET Framework built-ins shipped with WinPS 5.1. The lean-deps constraint is honored by construction.

## Package Legitimacy Audit

> Not applicable — Phase 3 installs **zero** external packages (PowerShell guard uses only .NET Framework built-in types; no PSGallery modules, no npm, no crates). slopcheck/registry verification skipped: nothing to verify.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
  Host fires guard          ┌─────────────────────────────────────────────┐
  (SessionStart /           │      nightguard_guard.ps1  (the guard)       │
   UserPromptSubmit) ──────▶│  resolve <data_dir> (--data-dir | env)       │
                            │  dot-source nightguard_interop + state_interop│
                            └───────────────────┬─────────────────────────┘
                                                │
                  ┌─────────────────────────────┼──────────────────────────────┐
                  ▼ (ALWAYS, no clock needed)    ▼                                │
        ┌──────────────────┐          ┌─────────────────────┐                    │
        │ load .guardkey   │          │ probe .nightguard.lock│ (circuit-breaker) │
        │ via DPAPI        │          │ app holds it?         │                    │
        │ Unprotect (32B)  │          └──────────┬───────────┘                    │
        └────────┬─────────┘           held → skip│ free → continue               │
                 │                                ▼                                │
                 ▼                    ┌────────────────────────────┐               │
   ┌───────────────────────────┐     │ HMAC(canon config.yaml)     │               │
   │ A. CONFIG VERIFY + REVERT │────▶│   == guard.json.config_hmac?│               │
   │  (GARD-01/02/05)          │     └──────┬──────────────┬───────┘               │
   └───────────────────────────┘        match│        mismatch│ (& lock free)      │
                 │                           │               ▼                      │
                 │                           │   revert: copy sanctioned→live;      │
                 │                           │   if sanctioned ALSO invalid →        │
                 │                           │   write maximal-lockout default(D-03) │
                 │                           ▼               │                      │
                 ▼                    reverted=false   reverted=true / fail_closed   │
   ┌───────────────────────────┐                                                    │
   │ B. STATE VERIFY (GARD-03) │  re-derive state_hmac (compact serde form) ────────┘
   │  match → use on-disk vals │  mismatch → runtime worst-case (spent=3, grace-used)
   └────────────┬──────────────┘
                ▼
   ┌───────────────────────────┐    NTP unreachable / clock-tamper → fail_closed=true,
   │ C. GRACE/CURFEW VERDICT   │◀── guard-side SNTP (48-byte UDP) + clock-skew check
   │  (GARD-04)                │    grace.window_end > true_now? → allow w/ remaining
   └────────────┬──────────────┘    else → deny (curfew)
                ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ append HMAC-chained audit record (D-08) → guard-audit.log          │
   │ emit JSON {decision,reason,grace_remaining_secs,reverted,fail_closed}│
   │ exit 0 (allow) | non-zero (deny)                                    │
   └───────────────────────────────────────────────────────────────────┘
```

### Recommended File Structure
```
scripts/
├── interop/
│   ├── nightguard_interop.ps1     # EXISTING — dot-sourced (DPAPI/HMAC/byte primitives)
│   └── state_interop.ps1          # EXISTING — dot-sourced (state_hmac re-derivation base)
├── guard/
│   ├── nightguard_guard.ps1       # NEW — the always-firing reader/enforcer (D-01..D-09)
│   ├── verify_hook_integrity.ps1  # NEW — SHA256 baseline + drift check (D-10/GARD-06)
│   └── guard.baseline.sha256      # NEW — baseline manifest (sha256<2sp>path per line, or JSON)
└── tests/                         # NEW (or under existing test harness) — PS Pester / gate scripts
    ├── run_guard_gate.ps1         # mirrors run_state_interop_gate.ps1 structure
    └── ...
```

### Pattern 1: Config-Verify-Revert (GARD-01, the revert rule mirror)
**What:** Re-derive the same config HMAC Rust signs; on mismatch (after circuit-breaker), copy sanctioned over live. Direction-agnostic — ANY mismatch reverts.
**When:** Every guard fire, unconditionally, before any clock-dependent logic.
**Reference behavior:** `crates/mutation-engine/tests/commit_order.rs` encodes the exact rule the guard must mirror: `HMAC(config.yaml) != guard.json.config_hmac ⇒ copy config.sanctioned.yaml over config.yaml`.
```powershell
# Source pattern: nightguard_interop.ps1 Get-FileHmacHex + commit.rs revert rule
$liveHmac  = Get-FileHmacHex -KeyBytes $key -Path $cfgLive   # raw bytes, canonicalized by writer
$guard     = (Get-FileBytes -Path $guardJson) ... ConvertFrom-Json
if ($liveHmac -ne $guard.config_hmac) {
    if (Test-LockHeld $lockPath) { $reverted = $false }       # D-06 circuit-breaker: skip
    elseif (Test-SanctionedValid $cfgSanctioned $key) {
        [System.IO.File]::Copy($cfgSanctioned, $cfgLive, $true); $reverted = $true
    } else {
        Write-MaximalLockoutDefault $cfgLive; $reverted = $true; $failClosed = $true   # D-03
    }
}
```
> NOTE: `Get-FileHmacHex` hashes raw on-disk bytes. The live `config.yaml` written by Rust is already canonical (no BOM/CR, one trailing LF — KERN-04). A hand-edit that changes ANY byte (including cosmetic CRLF/BOM) flips the tag → revert. This is the intended direction-agnostic behavior.

### Pattern 2: State-Verify (GARD-03 — the central parity finding)
**What:** Re-derive `state_hmac` exactly as Rust's `GuardState::compute_state_hmac` does, then compare. On mismatch, substitute runtime worst-case values (`weekly_spent=3`, grace-used) — do NOT write anything.
**The recipe (LOCKED, A3):** parse guard.json → blank `state_hmac` → serialize **compact** in field order → `canonicalize_bytes` → HMAC → compare.
```powershell
# Source pattern: state.rs compute_state_hmac + canon.rs canonicalize_bytes (VERIFIED this session)
$obj = (Get-FileBytes $guardJson | ...) | ConvertFrom-Json      # field order preserved in PSObject
$expectedTag = $obj.state_hmac
$obj.state_hmac = ''                                            # blank (recipe step 1)
$compact = $obj | ConvertTo-Json -Compress -Depth 10           # serde to_string parity (VERIFIED)
$bytes   = [System.Text.Encoding]::UTF8.GetBytes($compact)      # UTF-8, NO BOM
$canon   = $bytes + [byte]0x0A                                  # canonicalize: append exactly one LF
$hmac    = [System.Security.Cryptography.HMACSHA256]::new($key)
$tag     = (ConvertTo-LowerHex $hmac.ComputeHash($canon))
$stateValid = ($tag -eq $expectedTag)
if (-not $stateValid) { $weeklySpent = 3; $graceUsed = $true }  # D-04 runtime worst-case
```
> **VERIFIED byte-for-byte this session** for: fully-populated state, blanked state, `grace:null`, `ledger:[]`, i64 timestamp `9223372036854775807` (stays Int64, no float). Field order from `ConvertFrom-Json` PSObject = struct declaration order (`config_hmac,state_hmac,weekly_spent,week_anchor,ledger,grace`). The `.signbytes` gate artifact ends `7d 7d 0a` (`}}\n`) and has no BOM — the in-memory `$bytes + 0x0A` reproduces it. See §Code Examples for the proof harness.

### Pattern 3: Guard-Side SNTP (GARD-04)
**What:** Hand-build a 48-byte client NTP packet, send over UDP, parse the transmit timestamp, convert NTP-epoch(1900) → unix-epoch(1970) by subtracting 2208988800. Fail closed (`NtpUnreachable`-equivalent) on timeout/error — NEVER fall back to the local clock.
**When:** Only the grace/curfew verdict (Pattern C). Config + state verify need no clock.
**Match to Rust:** result must be `unix_secs` (i64) comparable to `guard.json.grace.window_end` and the Rust `NtpTrueTime.unix_secs`. Use the same fail-closed posture as `grace.rs`/`ntp.rs` (any error ⇒ deny). [CITED: chrisjwarwick.wordpress.com — 0x1B header, 48-byte packet, transmit-timestamp bytes 40-47, UInt32 conversion]

### Anti-Patterns to Avoid
- **Live-first revert / signing in the guard:** the guard NEVER writes a valid signed state or signs config. It only *copies* sanctioned→live (a byte copy) or writes the *hardcoded* maximal-lockout default. Re-signing is exclusively the Rust writer's job (D-05). [Source: commit.rs forbidden anti-pattern // GARD-05]
- **`Get-Content` for any HMAC input:** normalizes EOL/encoding → false tamper. Use `[IO.File]::ReadAllBytes`. [Source: nightguard_interop.ps1 FORBIDDEN list]
- **Honoring `grace.window_end` without re-checking NTP:** a network-isolation trick could hold a window open. Always re-query true time; offline ⇒ deny (D-07).
- **`Local::now()` / `Get-Date` as a clock fallback:** mirrors the Rust invariant — no verified true time ⇒ refuse grace (fail-closed).
- **Reverting while the lock is held:** the sign-vs-write race. Probe `.nightguard.lock` first (D-06).
- **Em-dashes / smart quotes / non-ASCII in `.ps1` files:** WinPS 5.1 `-File` execution chokes. Keep guard scripts ASCII-only. [Source: STATE.md env note + run_state_interop_gate.ps1 header]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HMAC-SHA256 over file bytes | A custom hashing loop | `Get-FileHmacHex` (existing) | Proven byte-identical to Rust in Phase 1; one code path, no drift. |
| DPAPI key unwrap | Raw `CryptUnprotectData` P/Invoke | `Unprotect-GuardKey` (existing) | Already handles CurrentUser + `$null` entropy + 32-not-64 canary. |
| state_hmac canonical bytes | A bespoke serializer | `ConvertFrom-Json`→`ConvertTo-Json -Compress`→`+0x0A` | Empirically matches serde; far less surface than hand-emitting JSON. |
| Atomic revert | temp+rename dance | `[IO.File]::Copy($sanctioned,$live,$true)` | Sanctioned is already the canonical bytes; a single overwrite copy is the revert. (Phase 2 owns atomic *writes*; the guard's revert is an idempotent copy that the next fire re-checks.) |
| Lock acquisition | A new lock scheme | Probe the EXISTING `.nightguard.lock` | D-06 reuses the Phase 2 fd-lock; the guard only needs *presence detection*, not acquisition. |

**Key insight:** Phase 3 is almost entirely *re-derivation of existing contracts in PowerShell*. The only genuinely new code is (a) the SNTP UDP packet, (b) the verdict computation, (c) the HMAC-chained audit log, and (d) the integrity baseline. Everything cryptographic is a dot-sourced reuse.

## Runtime State Inventory

> Phase 3 creates a new guard script and reads existing artifacts; it is not a rename/refactor. The relevant "state" risk is **format/contract drift** between what Rust writes and what the guard reads.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data (contract the guard reads) | `guard.json` (pretty serde JSON on disk; state_hmac signed over COMPACT re-serialization), `config.yaml` (canonical bytes), `config.sanctioned.yaml` (the revert target = canonical bytes), `.guardkey` DPAPI blob | Guard must parse + re-derive — covered by Patterns 1–2. No migration; read-only. |
| Live service config | None — no external service. The guard is invoked synchronously by a host hook. | None. |
| OS-registered state | The host hook registration (SessionStart/UserPromptSubmit) — **Phase 5 scope**, explicitly out of Phase 3. | None in Phase 3 (verified: D-09 + Deferred Ideas). |
| Secrets/env vars | `NIGHTGUARD_DIR` env var (alt to `--data-dir`, D-09); the DPAPI key blob filename within `<data_dir>` | Define the fixed filename; the key is loaded, never renamed. |
| Build artifacts | `.signbytes` is a **gate-harness-only** artifact (NOT produced at runtime). The guard must NOT depend on it. | Verified: state_interop_cli emits it only in the gate; runtime guard.json re-derives bytes itself. |

**Critical contract note:** The on-disk `guard.json` format (`to_vec_pretty`, indented) differs from the state_hmac pre-sign form (`to_string`, compact). The guard MUST re-serialize compact — it cannot HMAC the on-disk pretty bytes. **Verified this session** by inspecting both forms.

## Common Pitfalls

### Pitfall 1: HMAC the on-disk pretty guard.json instead of the compact re-serialization
**What goes wrong:** Guard treats every legitimate state as tampered → constant fail-closed worst-case.
**Why:** `commit.rs` writes `to_vec_pretty` (indented); `compute_state_hmac` signs `to_string` (compact) with state_hmac blanked + canonicalized.
**How to avoid:** Always `ConvertFrom-Json` then `ConvertTo-Json -Compress -Depth 10`; never hash the raw file. (Pattern 2.)
**Warning signs:** state_hmac mismatch on a freshly app-written, untampered guard.json.

### Pitfall 2: PowerShell JSON serialization divergence from serde
**What goes wrong:** A subtle whitespace/escaping/number-format difference flips the state_hmac.
**Why:** `ConvertTo-Json` is a different serializer than serde.
**How to avoid:** I **verified** parity for the current field set (hex strings, ISO dates, integers, dotted field-paths — no `/`, no unicode, no floats). The planner MUST ship a parity test: Rust emits the compact pre-sign bytes (the existing `emit-state-hmac` `.signbytes`), PS re-derives from the parsed guard.json, assert equality. If a future field adds a `/` or non-ASCII, switch that field to hand-built emission (serde escapes `/` as `\/`? — no, serde does NOT escape `/`; PS `ConvertTo-Json` does NOT either in 5.1 for these values — but PS `ConvertTo-Json` escapes non-ASCII as `\uXXXX`; serde escapes only control chars + `"`/`\`). **Constrain the test to the locked field set.**
**Warning signs:** parity test red on any new field.
**Confidence:** HIGH for current fields (empirically verified), MEDIUM as a general guarantee (flag any schema change).

### Pitfall 3: `-Depth` truncation
**What goes wrong:** `ConvertTo-Json` defaults to `-Depth 2`; the nested `ledger[].fields[]` is depth 3 → silently truncated to `"System.Object[]"`.
**Why:** WinPS 5.1 default depth is 2.
**How to avoid:** Always pass `-Depth 10` (verified working). [VERIFIED this session]
**Warning signs:** ledger entries serialize as type strings.

### Pitfall 4: Reverting during an in-progress commit (sign-vs-write race / GARD-05)
**What goes wrong:** Guard fires between Rust's guard.json write and live write, sees a transient mismatch, reverts a legitimate new config back to old.
**Why:** Rust writes live LAST; there is a window where guard.json=NEW but live=OLD.
**How to avoid:** Per `commit_order.rs`, that exact window converges to NEW *via the revert rule itself* (guard.json=NEW so sanctioned=NEW, reverting live→sanctioned yields NEW — not a regression). The circuit-breaker (D-06) additionally skips reverting while `.nightguard.lock` is held, avoiding even a transient touch. **Both** mechanisms must be present.
**Warning signs:** a committed loosen mysteriously reverts; lock not probed.

### Pitfall 5: Clock-tamper widening the grace window
**What goes wrong:** User sets the system clock back to keep `grace.window_end > now`.
**Why:** Verdict compares against a clock.
**How to avoid:** Compare against the guard's OWN SNTP true-time (Pattern 3), and detect tamper by checking |NTP - localClock| skew (large skew ⇒ treat as tamper / fail-closed). Offline ⇒ deny (D-07).
**Warning signs:** grace honored while offline or with skewed clock.

### Pitfall 6: WinPS 5.1 native-command stderr promotion + non-ASCII
**What goes wrong:** `$ErrorActionPreference='Stop'` turns cargo/native stderr into terminating errors; em-dashes in `-File` scripts fail to parse.
**Why:** WinPS 5.1 quirks (documented in STATE.md env note).
**How to avoid:** ASCII-only scripts; relax `$ErrorActionPreference` to `Continue` around native calls and gate on `$LASTEXITCODE`. [Source: run_state_interop_gate.ps1]

## Code Examples

Verified parity harness pattern (run this session, all PASS):
```powershell
# Source: state.rs compute_state_hmac + canon.rs + this-session verification
# Reproduce serde_json::to_string of a parsed guard.json, state_hmac blanked, compact.
$obj = $prettyGuardJson | ConvertFrom-Json
$obj.state_hmac = ''
$compact = $obj | ConvertTo-Json -Compress -Depth 10
# -> byte-identical to serde to_string for the locked field set; matched grace:null, ledger:[]
$bytes = [System.Text.Encoding]::UTF8.GetBytes($compact)
$canon = New-Object byte[] ($bytes.Length + 1)
[Array]::Copy($bytes, $canon, $bytes.Length); $canon[$bytes.Length] = 0x0A   # one trailing LF
# HMAC $canon with the 32 raw key bytes -> compare lowercase-hex to $obj.state_hmac
```

Guard-side SNTP skeleton (the only genuinely new crypto-adjacent code):
```powershell
# Source: chrisjwarwick.wordpress.com (48-byte SNTP), adapted to fail-closed
function Get-GuardNtpUnixSecs {
    param([string]$Server = 'time.cloudflare.com', [int]$TimeoutMs = 2000)
    try {
        $packet = New-Object byte[] 48; $packet[0] = 0x1B    # LI=0,VN=3,Mode=3 (client)
        $sock = New-Object System.Net.Sockets.Socket('InterNetwork','Dgram','Udp')
        $sock.ReceiveTimeout = $TimeoutMs; $sock.SendTimeout = $TimeoutMs
        $sock.Connect($Server, 123); [void]$sock.Send($packet); [void]$sock.Receive($packet)
        $sock.Close()
        # Transmit Timestamp seconds = bytes 40..43, big-endian
        $secs = ([uint32]$packet[40] -shl 24) -bor ([uint32]$packet[41] -shl 16) `
              -bor ([uint32]$packet[42] -shl 8) -bor [uint32]$packet[43]
        return [int64]$secs - 2208988800L     # NTP epoch (1900) -> unix epoch (1970)
    } catch { return $null }                  # fail-closed: caller treats $null as NtpUnreachable
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `.signbytes` file as the state-HMAC input | Re-derive compact bytes in-PowerShell from parsed guard.json | Phase 3 (this research) | Guard is runtime-self-contained; no dependence on a Rust-emitted helper file. |
| (none — greenfield guard) | — | — | — |

**Deprecated/outdated:** none relevant — all primitives are stable .NET Framework types.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `Get-FileHash -Algorithm SHA256` (or `[SHA256]`) is the integrity-baseline hasher | Standard Stack | Low — both are built-in; pick either. |
| A2 | `ConvertTo-Json -Compress` will remain byte-identical to serde for ALL future guard.json fields | Pitfall 2 | MEDIUM — verified for CURRENT fields only. A new field with `/`, non-ASCII, or a float could diverge. Mitigation: ship the Rust↔PS state-parity gate as the phase exit gate; constrain schema. |
| A3 | The DPAPI key blob filename within `<data_dir>` (e.g. `.guardkey`) is the guard's discretion | D-09 / paths | Low — Claude's-discretion per CONTEXT; must match the Phase 5 wiring + Rust `load_or_create_key` path. |
| A4 | Clock-tamper detection = compare NTP true-time vs local clock skew threshold | Pitfall 5 | MEDIUM — exact threshold is a design choice; too-tight false-positives offline, too-loose lets small drift through. Recommend a generous threshold (e.g. >5 min) since the grace window is only 8 min. |
| A5 | The guard's circuit-breaker only needs lock *presence* detection, not acquisition | D-06 | LOW — D-06 explicitly says "checks fd-lock presence"; on Windows, attempting a non-blocking `LockFileEx`/open-with-share-deny probe reveals if the app holds it. Verify the exact probe mechanism at integration (a `.lock` file that merely *exists* is NOT the signal — the app holds an OS lock on it via `fd_lock`; presence of the file alone is insufficient). |

## Open Questions

1. **fd-lock presence probe mechanism (D-06).**
   - What we know: Phase 2's `with_commit_lock` opens `.nightguard.lock` and takes `fd_lock::RwLock::write()` = Windows `LockFileEx` + `LOCKFILE_EXCLUSIVE_LOCK`. The file always *exists* once created; existence is NOT the signal.
   - What's unclear: how PowerShell detects the OS-held exclusive lock. Likely: attempt to open the file with an exclusive share mode (`[IO.File]::Open($path,'Open','ReadWrite','None')`) — if it throws `IOException`, the app holds the lock → skip revert; if it opens, the lock is free.
   - Recommendation: planner spikes this probe against a live `cargo test` holding the lock (or a small Rust harness). This is the one runtime mechanism not yet proven cross-language. Add to the phase exit gate.

2. **Sanctioned-snapshot validity test (GARD-02).**
   - What we know: `config.sanctioned.yaml` is the canonical config bytes; there is NO separate sanctioned HMAC stored. The Phase 2 commit writes sanctioned = the same bytes config_hmac was signed over.
   - What's unclear: how the guard decides the sanctioned snapshot is "also invalid" (D-03 trigger). Candidate: `HMAC(sanctioned) == guard.json.config_hmac`? No — after a hand-edit, live≠sanctioned but sanctioned should still match guard.json.config_hmac (sanctioned is the revert target = NEW bytes). So "sanctioned invalid" = `HMAC(sanctioned) != guard.json.config_hmac` (sanctioned itself was tampered) OR sanctioned is missing/unparseable.
   - Recommendation: define "sanctioned valid" = `HMAC(canon(sanctioned)) == guard.json.config_hmac AND it parses as the minimal YAML`. If guard.json itself is also unverifiable, fall straight to maximal-lockout. Planner locks this predicate.

3. **HMAC-chain construction for the audit log (D-08).**
   - What we know: append-only, each record chained with HMAC so deletion/edit/truncation is detectable.
   - What's unclear: exact chain recipe (prev-tag-in-next-record is suggested in CONTEXT as discretion).
   - Recommendation: `record_tag = HMAC(key, prev_tag || record_payload)`; store `prev_tag` implicitly (last line's tag). First record chains over a fixed genesis constant. Planner picks the delimiter/escaping.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Windows PowerShell | Guard runtime | ✓ | 5.1.26100.8115 | — (target host) |
| `[HMACSHA256]` / `[ProtectedData]` / `[IO.File]` | All crypto/IO | ✓ | .NET Framework built-in | — |
| `System.Net.Sockets` UDP | Guard SNTP | ✓ | .NET Framework built-in | — |
| Network egress UDP/123 | Live grace verdict | ✗ (test env may block) | — | Fail-closed deny (D-07) IS the fallback by design |
| `cargo` (build the parity-gate Rust CLI) | Phase exit gate only | ✓ (Phase 1/2 used it) | — | — |
| Rust `.guardkey` + `guard.json` fixtures | Guard tests | produced by Phase 1/2 CLIs | — | regenerate via `state_interop_cli emit-state-hmac` |

**Missing dependencies with no fallback:** none (network-offline is a designed fail-closed path, not a blocker).
**Missing dependencies with fallback:** UDP/123 egress → deny-on-offline (D-07).

## Validation Architecture

> `.planning/config.json` not inspected for `nyquist_validation`; included by default (key absent = enabled). The project's established pattern is **exit-gate `.ps1` harnesses** (`run_interop_gate.ps1`, `run_state_interop_gate.ps1`) plus Rust `cargo test`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | PowerShell exit-gate scripts (`run_*_gate.ps1` pattern) + Rust `cargo test` for the reference revert rule. Pester optional but NOT yet used in-repo. |
| Config file | none — gate scripts are self-contained, gate on `$LASTEXITCODE`/`exit 0/1`. |
| Quick run command | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/guard/<gate>.ps1` |
| Full suite command | run all `run_*_gate.ps1` + `cargo test -p mutation-engine` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GARD-01 | hand-edit → revert; valid → no revert | integration | `run_guard_gate.ps1` (tamper live config, assert reverted) | ❌ Wave 0 |
| GARD-02 | both invalid → maximal-lockout default | integration | gate: corrupt live+sanctioned, assert lockout YAML + log | ❌ Wave 0 |
| GARD-03 | state tamper → worst-case substitution | integration | gate: flip guard.json byte, assert spent=3/grace-used verdict | ❌ Wave 0 |
| GARD-03 | state_hmac re-derivation parity | integration | Rust↔PS state-parity gate (extend run_state_interop_gate.ps1) | ⚠️ extend existing |
| GARD-04 | grace honored vs expired; offline→deny; clock-tamper→deny | integration | gate with injected/faked NTP + grace window fixtures | ❌ Wave 0 |
| GARD-05 | lock held → skip revert; ordering converges to NEW | integration + unit | `run_guard_gate.ps1` (hold lock) + existing `commit_order.rs` | ⚠️ unit exists; PS gate ❌ |
| GARD-06 | baseline drift raises alert; guard self-registered | integration | `verify_hook_integrity.ps1` self-test | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the relevant single `run_guard_*.ps1` gate (sub-30s).
- **Per wave merge:** all guard gates + `cargo test -p mutation-engine`.
- **Phase gate:** full guard gate suite green + the Rust↔PS state-parity gate green before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `scripts/guard/run_guard_gate.ps1` — drives config-verify/revert + circuit-breaker + verdict (GARD-01/02/04/05).
- [ ] Extend `scripts/interop/run_state_interop_gate.ps1` (or a sibling) to assert the **runtime** state-verify path (parse pretty guard.json → compact re-derive → HMAC), not just the `.signbytes` path.
- [ ] `scripts/guard/verify_hook_integrity.ps1` self-test fixture (GARD-06).
- [ ] A live/faked NTP seam for the verdict gate (mirror the Rust `FakeTrueTime` idea — e.g. a `-NtpOverrideUnixSecs` param on the guard so tests inject true-time deterministically; production path uses real SNTP).
- [ ] An fd-lock-presence probe spike (Open Question 1) with a Rust harness holding the lock.

## Security Domain

> `security_enforcement` assumed enabled (absent = enabled). This is a security-critical phase.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | partial | The DPAPI key *is* the authentication: holding the CurrentUser-decryptable key proves identity (D-05 repair gate). |
| V3 Session Management | no | No sessions. |
| V4 Access Control | yes | Self-binding "anti-me": the guard enforces that even the admin user cannot quietly loosen — fail-closed worst-case on tamper (D-03/D-04). |
| V5 Input Validation | yes | guard.json/config.yaml parsing must be defensive (missing/malformed → fail-closed, never permissive). Mirror Phase 2's defensive-A2 (absent field → safe default). |
| V6 Cryptography | yes | HMAC-SHA256 (reused `Get-FileHmacHex`, constant-time-intent), DPAPI (CurrentUser, `$null` entropy). **Never hand-roll** — dot-source the proven helpers. |

### Known Threat Patterns for the PowerShell guard

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Hand-edit config.yaml to loosen | Tampering | HMAC verify + direction-agnostic auto-revert (GARD-01). |
| Corrupt both live + sanctioned to brick/escape | Tampering / DoS | Maximal-lockout default — corruption buys nothing (D-03/GARD-02). |
| Forge/replay signed state to fake tokens/grace | Spoofing | state_hmac re-derive over canonical bytes (GARD-03); tamper → worst-case. |
| Set system clock back to extend grace | Tampering | Guard's OWN SNTP + clock-skew detection; offline → deny (GARD-04/D-07). |
| Race a guard fire against a legit commit to revert it | Tampering (TOCTOU) | live-last ordering + `.nightguard.lock` circuit-breaker (GARD-05/D-06). |
| Delete/edit/truncate the audit log to hide events | Repudiation | HMAC-chained append-only log (D-08). |
| Replace/disable the guard script itself | Tampering | SHA256 integrity baseline + drift alert (GARD-06/D-10). |
| `Get-Content` EOL normalization → false tamper or missed tamper | Tampering | Raw `[IO.File]::ReadAllBytes` only (locked invariant). |
| SecureString/UTF-16 framing of the key → 64-byte key | Spoofing | 32-not-64 canary in `Unprotect-GuardKey` (locked). |

## Sources

### Primary (HIGH confidence)
- `scripts/interop/nightguard_interop.ps1`, `state_interop.ps1`, `run_state_interop_gate.ps1` — the proven DPAPI/HMAC/byte/state-hmac PowerShell primitives the guard reuses.
- `crates/mutation-engine/src/{state,commit,grace,ntp,sign}.rs` + `bin/state_interop_cli.rs` — the LOCKED contracts (A1/A3 recipe, commit ordering, fail-closed posture) the guard mirrors.
- `crates/trust-kernel/src/{canon,key}.rs` — canonicalize_bytes rules + DPAPI key lifecycle.
- `target/state_interop_gate/guard.json` + `.signbytes` + `target/tmp/commit-*/guard.json` — the actual on-disk compact-vs-pretty forms (inspected this session).
- This-session PowerShell 5.1 empirical runs — `ConvertTo-Json -Compress -Depth 10` byte-parity with serde for the locked field set (full state, blanked, grace:null, empty ledger, i64); `$PSVersionTable.PSVersion = 5.1.26100.8115`.
- `.planning/phases/03-enforcement-guard/03-CONTEXT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `./CLAUDE.md`.

### Secondary (MEDIUM confidence)
- chrisjwarwick.wordpress.com "Getting NTP/SNTP Network Time with PowerShell" — 48-byte packet, 0x1B header, transmit-timestamp parse, NTP→unix epoch offset 2208988800. (Pattern verified against multiple corroborating sources in the search.)

### Tertiary (LOW confidence)
- General WinPS 5.1 behavior claims about `ConvertTo-Json` non-ASCII escaping (`\uXXXX`) — not exercised by the current locked field set; flagged in Pitfall 2 / Assumption A2 for any future schema change.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all primitives are .NET built-ins already proven cross-language in Phase 1/2.
- State-verify parity (the central risk): HIGH for current fields (empirically verified byte-for-byte this session); MEDIUM as a forward guarantee (Assumption A2 — ship the parity gate).
- Config verify/revert: HIGH — reuses `Get-FileHmacHex`; revert rule is encoded in `commit_order.rs`.
- SNTP: MEDIUM — well-documented standard pattern, but not yet run against a live server in this repo; fail-closed posture makes errors safe.
- Circuit-breaker fd-lock probe: MEDIUM — mechanism identified (exclusive-open IOException) but not yet spiked cross-language (Open Question 1).
- Pitfalls/security: HIGH — derived directly from the locked Phase 2 contracts and CONTEXT decisions.

**Research date:** 2026-06-08
**Valid until:** ~2026-07-08 (stable; the contracts are LOCKED in-repo, not external — only re-validate if guard.json schema changes).
