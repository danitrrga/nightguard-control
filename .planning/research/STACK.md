# Stack Research

**Domain:** Windows-only self-binding desktop app (Tauri v2) — sole sanctioned editor for an HMAC-signed, DPAPI-keyed curfew config, with a PowerShell integrity guard
**Researched:** 2026-06-04
**Confidence:** HIGH (all critical claims verified via crates.io API, official Microsoft/Tauri docs, and crate source)

---

## TL;DR — the load-bearing answers

1. **DPAPI Rust↔PowerShell interop: VERIFIED, low risk.** .NET `ProtectedData.Protect/Unprotect` is a thin wrapper over the Win32 `CryptProtectData`/`CryptUnprotectData` functions, and the `windows-dpapi` crate returns the **raw** `CryptProtectData` output blob with **no extra framing**. A blob protected by either side is unprotectable by the other, *provided both use the same scope (`CurrentUser`) and the same `optionalEntropy` (use `None`/`null` on both)*. This is documented, intended Windows behavior — not a hack. Still: do a **30-minute spike** before committing the architecture (write key with PowerShell `[ProtectedData]::Protect(bytes,$null,'CurrentUser')`, read it with Rust `decrypt_data(&blob, Scope::User, None)`, and vice-versa). See Pitfalls.
2. **HMAC-SHA256 byte-compatibility: GUARANTEED by the algorithm.** HMAC-SHA256 is fully specified (RFC 2104 / FIPS 198-1). RustCrypto `hmac`+`sha2` and .NET `HMACSHA256` produce **byte-identical** output for the same key + same message bytes. The only risk is *input canonicalization* (whitespace, encoding, line endings), not the crypto. Pin the canonical byte form and you're done.
3. **Tauri current stable: 2.11.2** (2.x line; v2 is the supported major).
4. **Comment-preserving YAML: use `yamlpatch` + `yamlpath`** (edit-in-place, format-preserving). `serde_yaml` is archived; `yaml-rust2`/`saphyr` do not preserve comments yet.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Tauri** | `2.11.2` (`tauri` crate + `@tauri-apps/cli`) | Desktop shell; Rust backend = sole writer/signer, webview frontend = UI | Current stable v2; tiny binaries, Rust backend holds the signing key off the JS surface, mature Windows bundler/signer. v2 is the only supported major. |
| **Rust** | latest stable via `rustup`, **MSVC toolchain** (`x86_64-pc-windows-msvc`) | Backend: HMAC, DPAPI, NTP, atomic writes, classifier | Required by Tauri; MSVC host triple is mandatory on Windows (not GNU). |
| **Vite** | `^7` (whatever `create-tauri-app` scaffolds for the vanilla-TS template) | Frontend bundler/dev server | Tauri's recommended frontend tooling; the `vanilla-ts` template is exactly the "no-React vanilla TS" the project mandates. |
| **TypeScript** | `^5` | Frontend language | Type safety over the `invoke()` boundary; matches the lean-deps constraint. |
| **WebView2 Runtime** | Evergreen (system) | Renders the UI on Windows | Pre-installed on Win10 1803+/Win11 (your target). No bundling needed for personal use. |

### Supporting Libraries (Rust / `Cargo.toml`)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **`windows-dpapi`** | `0.2.0` | DPAPI encrypt/decrypt of the 32-byte `.guardkey`, `Scope::User` | Wrap key at rest. Returns raw `CryptProtectData` blob → interoperable with PowerShell `[ProtectedData]`. **Verify scope/entropy match the guard.** |
| **`hmac`** | `0.12.1` | HMAC construction | Pair with `sha2 0.10`. Use the proven pairing, not bleeding-edge 0.13 (see "What NOT to use"). |
| **`sha2`** | `0.10.9` | SHA-256 backing the HMAC | Battle-tested; the version 99% of the ecosystem (and `hmac 0.12`) depends on. |
| **`subtle`** | `2.x` | Constant-time tag comparison | Use `hmac`'s `verify_slice()` (built on `subtle`) instead of `==` on tags. |
| **`hex`** | `0.4.3` | Encode HMAC tag as hex for `guard.json` | If storing tags as hex strings (recommended for readability + PowerShell parity). |
| **`sntpc`** | `0.10.1` | SNTP/NTP true-time query | NTP-true-time for grace window + clock-tamper detection. Use `sync` module + `sntpc-net-std` adapter over `UdpSocket` (set a short timeout; offline → flag in UI). |
| **`yamlpath`** | `1.25.2` | Format-preserving YAML feature extraction | Read individual fields for the direction classifier without losing layout. |
| **`yamlpatch`** | `1.25.2` | Comment- and format-preserving YAML patch ops | **The writer.** Apply per-field edits to `config.yaml` while preserving comments/whitespace so the hand-rolled PowerShell parser still reads it. |
| **`serde` / `serde_json`** | `1.x` | `guard.json` (de)serialization + Tauri command payloads | `guard.json` is machine state — plain JSON, comment preservation irrelevant. Tauri commands require `serde`. |
| **`tempfile`** *(or hand-rolled)* | `3.x` | Atomic writes (write temp → `rename`) | Required by the "atomic writes / fail-closed" constraint. On Windows use write-temp-then-`ReplaceFile`/rename in same dir. |
| **`chrono`** *(or `time`)* | `chrono 0.4` | Monday-00:00 week anchor, grace window math, tz handling | Week-reset / ISO-week / Europe-Amsterdam logic. `chrono-tz` if you need named-tz resolution in Rust. |
| **`thiserror`** | `1.x` | Backend error types surfaced to commands | Clean `Result` returns across the `invoke` boundary. |

### Frontend (npm)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **`@tauri-apps/api`** | `^2` | `invoke()` IPC, event listeners | Call Rust commands (`get_state`, `classify_change`, `commit_change`, `use_grace`). |
| **`@tauri-apps/cli`** | `^2.11` | dev/build/bundle CLI | `tauri dev`, `tauri build`. |
| *(none for UI)* | — | Hand CSS with palette tokens | Spec mandates hand CSS / Moonlit Indigo tokens. No UI framework — honors lean-deps. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `create-tauri-app` | Scaffold | `npm create tauri-app@latest` → choose **TypeScript / JavaScript → Vanilla → TypeScript**. Produces `src/` (frontend) + `src-tauri/` (Rust). |
| Microsoft C++ Build Tools | Native linking | Installer → check **"Desktop development with C++"**. Required before any Tauri build. |
| `rustup` | Rust install | Ensure default host triple is `x86_64-pc-windows-msvc`. |

---

## IPC pattern (Tauri v2, verified)

Backend command:
```rust
#[tauri::command]
fn classify_change(proposed: ProposedConfig) -> Result<Classification, String> { ... }
```
Register in the builder:
```rust
tauri::Builder::default()
    .invoke_handler(tauri::generate_handler![
        get_state, classify_change, commit_change, use_grace
    ])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
```
Frontend call:
```ts
import { invoke } from "@tauri-apps/api/core"; // v2 path is /core, NOT /tauri (that was v1)
const cls = await invoke<Classification>("classify_change", { proposed });
```
Command args/returns must be `serde::Serialize`/`Deserialize`. Args are camelCase on the JS side by default (`weekly_spent` ↔ `weeklySpent`) — or annotate with `#[tauri::command(rename_all = "snake_case")]`.

---

## Installation

```bash
# 0. Prerequisites (one-time): MS C++ Build Tools, rustup (msvc), WebView2 (preinstalled Win11)

# 1. Scaffold
npm create tauri-app@latest nightguard-control
#    → Vanilla → TypeScript

cd nightguard-control
npm install

# 2. Frontend dep
npm install @tauri-apps/api@^2

# 3. Backend deps (src-tauri/Cargo.toml)
#    cd src-tauri
cargo add windows-dpapi@0.2.0
cargo add hmac@0.12.1
cargo add sha2@0.10.9
cargo add subtle@2
cargo add hex@0.4.3
cargo add sntpc@0.10.1
cargo add yamlpath@1.25.2 yamlpatch@1.25.2
cargo add serde@1 --features derive
cargo add serde_json@1
cargo add chrono@0.4
cargo add tempfile@3
cargo add thiserror@1

# 4. Run / build
npm run tauri dev
npm run tauri build   # produces .exe + (optional) MSI/NSIS installer in src-tauri/target/release/bundle/
```

---

## Bundling / signing (Windows)

- `tauri build` produces a standalone `.exe` and, by default, **MSI (WiX)** and/or **NSIS** installers (configurable in `tauri.conf.json` → `bundle.targets`).
- **For a personal LifeOS instance, code-signing is optional** — unsigned runs fine for yourself; SmartScreen will warn on first launch. For a *publishable* repo, sign with an Authenticode cert (`bundle.windows.certificateThumbprint` / `signCommand`); Tauri's updater also supports its own signature scheme if you ever ship updates.
- Recommendation: ship the plain `.exe` (or NSIS) for v1; defer Authenticode until the repo is actually published. Don't block the milestone on a cert.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `windows-dpapi 0.2.0` | Raw `windows`/`windows-sys` crate calling `CryptProtectData` yourself | If you want zero third-party deps for the security path, or need flags (`CRYPTPROTECT_UI_FORBIDDEN`) the wrapper doesn't expose. The wrapper is ~thin; rolling your own is ~40 lines and removes a dependency you're trusting with the key. **Reasonable to do for this project given its security focus.** |
| `windows-dpapi 0.2.0` | `winapi 0.3` `dpapi` module | Older, unmaintained-style binding; `windows`/`windows-sys` is the current Microsoft-blessed path. Prefer `windows-sys` if rolling your own. |
| `hmac 0.12 + sha2 0.10` | `hmac 0.13 + sha2 0.11` | Once the RustCrypto 0.13/0.11 line is widely adopted (it shipped Mar 2026). For a project that wants stability and maximum ecosystem compatibility *today*, stay on 0.12/0.10. |
| `hmac 0.12 + sha2 0.10` | `ring` | If you already use `ring` elsewhere. Heavier (vendored BoringSSL/asm), overkill for one HMAC; RustCrypto is pure-Rust and lighter for a single tag. |
| `yamlpatch + yamlpath` | `serde_yaml` + accept comment loss | Only if you decide `config.yaml` does **not** need comments preserved. The spec explicitly says it's human-readable with comments → don't. |
| `yamlpatch` | Hand-rolled line-oriented patcher mirroring the PowerShell parser | If `yamlpatch` proves too heavy or its patch model doesn't fit. Since the *guard* already uses a hand-rolled minimal YAML parser, a matching minimal Rust writer is viable and keeps both sides in lockstep — but it's more code to maintain. |
| `sntpc` | Reuse the existing PowerShell NTP logic via shelling out | The PS hooks already have NTP/clock-tamper logic. The app could call it — but a native Rust SNTP query is cleaner for the UI's live drift display. Guard re-checks timing with *its own* NTP regardless (per spec), so app-side NTP is advisory only. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `serde_yaml` (as the config writer) | **Archived/unmaintained** (last release 0.9.34+deprecated, Mar 2024) and **destroys comments + formatting** on round-trip — would corrupt the human-readable `config.yaml` and could break the PowerShell minimal parser. | `yamlpatch` + `yamlpath` for `config.yaml`. `serde_json` is fine for `guard.json`. |
| `yaml-rust2` / `saphyr` for round-trip edits | YAML 1.2 compliant *parsers* but **do not preserve comments** on emit (comment support deferred to future `saphyr`). | `yamlpatch` (purpose-built for comment/format-preserving patches). |
| Tauri **v1** APIs / `@tauri-apps/api/tauri` import | v1 is legacy; import path and plugin model changed. | Tauri **v2** (`2.11.2`), `invoke` from `@tauri-apps/api/core`. |
| `CRYPTPROTECT_LOCAL_MACHINE` / `Scope::Machine` for the key | Spec requires **CurrentUser** binding — machine scope lets *any* user on the box decrypt, weakening the "only this user can forge a signature" property. | `Scope::User` (DPAPI CurrentUser) on **both** Rust and PowerShell. |
| DPAPI `optionalEntropy` mismatch | If Rust passes entropy and PowerShell passes `$null` (or different bytes), `Unprotect` **fails** — silently breaking the guard. | Use `None` / `$null` on **both** sides (or the identical entropy bytes on both). Document it as a hard invariant. |
| GNU Rust toolchain on Windows | Tauri requires the **MSVC** host triple; GNU builds fail/misbehave. | `x86_64-pc-windows-msvc`. |
| `==` to compare HMAC tags | Timing side-channel (minor here, but free to avoid). | `Hmac::verify_slice()` (constant-time via `subtle`). |

---

## Stack Patterns by Variant

**If you want to minimize trusted third-party crypto deps (recommended for this security-critical tool):**
- Replace `windows-dpapi` with a ~40-line direct `windows-sys` call to `CryptProtectData`/`CryptUnprotectData`.
- Because: you're trusting this dep with the signing key; the wrapper is thin enough that owning the code is cheap and auditable. The interop guarantee is identical (raw blob, same API).

**If the PowerShell minimal YAML parser turns out to be fragile:**
- Use `yamlpatch` for writes but **add a round-trip test**: after every Rust write, re-read with a Rust port of the PS parser's rules (or shell out to the actual PS parser) and assert it parses to the expected values. Lock the canonical form.

**If NTP is frequently unreachable on the target machine:**
- `sntpc` with a 2–3s timeout; on failure, surface "offline — time unverified" in the UI and rely on the guard's `block_when_offline`. Never let app-side NTP failure *widen* a grace window (guard re-validates with its own NTP per spec).

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `tauri 2.11.2` | `@tauri-apps/api ^2`, `@tauri-apps/cli ^2.11` | Keep JS API/CLI major-matched to the Rust crate. |
| `hmac 0.12.1` | `sha2 0.10.9`, `digest 0.10` | The canonical, widely-deployed pairing. Do **not** mix `hmac 0.12` with `sha2 0.11` (incompatible `digest` majors). |
| `hmac 0.13` | `sha2 0.11`, `digest 0.11` | Newer line (Mar 2026); only adopt if you move the whole crypto set together. |
| `windows-dpapi 0.2.0` | `winapi 0.3` (its internal dep) | Pure-Windows; `x86_64-pc-windows-msvc` only — fine, project is Windows-only. |
| RustCrypto `hmac`/`sha2` | .NET `HMACSHA256` | **Byte-identical output** — HMAC-SHA256 is algorithm-defined. Compatibility risk is *input canonicalization*, not the libraries. |

---

## Cross-language interop invariants (must hold, else the guard breaks silently)

1. **DPAPI:** scope = CurrentUser on both; entropy = none on both. Blob is raw `CryptProtectData` output (no base64/framing unless *you* add it consistently — PS often base64s for storage; if so, base64 on read in Rust too).
2. **HMAC input canonicalization:** define ONE canonical byte sequence both sides hash. Pin: encoding (UTF-8, no BOM), line endings (decide LF vs CRLF and normalize), trailing newline, and whether you HMAC the *raw file bytes* or a *normalized/serialized* form. Easiest robust choice: **HMAC the exact on-disk file bytes of `config.yaml`** (both Rust and PS read the same bytes) → zero canonicalization ambiguity. Same for `guard.json`.
3. **Tag encoding in `guard.json`:** store as lowercase hex (both `hex` crate and PS `[BitConverter]`/`-join` agree on lowercase hex) — pick one case and enforce.

---

## Sources

- crates.io API (version + last-published + downloads, fetched 2026-06-04) — `tauri 2.11.2`, `windows-dpapi 0.2.0`, `hmac 0.13.0`/`0.12.1`, `sha2 0.11.0`/`0.10.9`, `sntpc 0.10.1`, `yamlpath`/`yamlpatch 1.25.2`, `saphyr 0.0.6`, `serde_yaml 0.9.34+deprecated`. **HIGH**
- Microsoft Learn — `CryptProtectData` (dpapi.h), parameters incl. `pOptionalEntropy` ("must also be used in the decryption phase"), CurrentUser vs LOCAL_MACHINE scope. **HIGH**
- Microsoft Learn — `System.Security.Cryptography.ProtectedData` / `ProtectedData.Protect` — confirmed thin wrapper over DPAPI; `optionalEntropy` + `DataProtectionScope.CurrentUser=0`. **HIGH**
- `windows-dpapi` source (`src/lib.rs`, sheridans/windows-dpapi) — `encrypt_data(data, Scope, Option<entropy>)` returns **raw** `CryptProtectData` blob, no framing; `Scope::User` supported. **HIGH**
- v2.tauri.app — prerequisites (MS C++ Build Tools, WebView2, MSVC Rust toolchain), v2 invoke pattern. **HIGH**
- RustCrypto MACs/hashes (GitHub) — `hmac`+`sha2` digest-version pairing; HMAC-SHA256 RFC-defined output. **HIGH** (interop byte-equality is algorithmic, not library-specific)
- docs.rs `sntpc` — async-first with `sync` module + `sntpc-net-std` adapter. **MEDIUM** (verify exact `sync::get_time` signature at integration time)
- "Respectful YAML patching in Rust" (verrchu.github.io) + serde-yaml issue #145 — comment-preservation landscape, `yamlpatch`/`yamlpath` as the format-preserving option. **MEDIUM**

---
*Stack research for: Windows self-binding curfew-editor desktop app (Tauri v2 + Rust + DPAPI + HMAC + PowerShell guard interop)*
*Researched: 2026-06-04*
