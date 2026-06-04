# Pitfalls Research

**Domain:** Self-binding ("anti-me") Windows desktop tool — Tauri v2 + Rust, DPAPI-stored HMAC, NTP-boxed time enforcement, PowerShell auto-revert guard
**Researched:** 2026-06-04
**Confidence:** HIGH for DPAPI interop / line-ending / Tauri specifics (verified against Microsoft docs, Tauri v2 docs, PowerShell issue tracker); MEDIUM for time/DST sequencing (reasoned from existing hook + .NET TZ semantics); HIGH for self-adversary realism (matches the spec's own honest-constraint section).

> Phase names below are *topics* (the roadmap does not exist yet). Map them to whatever phase covers that topic.

## Critical Pitfalls

### Pitfall 1: Rust↔PowerShell DPAPI interop — SecureString framing vs raw DPAPI blob (TOP RISK)

**What goes wrong:**
The two layers can't decrypt each other's `.guardkey`. The most common failure: PowerShell stores the key with `ConvertFrom-SecureString` / reads with `ConvertTo-SecureString -Key`, while Rust uses a raw `CryptProtectData`/`CryptUnprotectData` (windows-dpapi crate) blob. These are **not the same format**. `ConvertFrom-SecureString` produces a SecureString-framed, UTF-16LE-encoded, DPAPI-wrapped hex string — it is *not* a bare DPAPI blob of your 32 raw key bytes. Rust's `CryptUnprotectData` on that data returns the UTF-16LE bytes of a hex string, not your key. Result: HMACs computed by the two layers diverge, and **every config looks tampered** → the guard reverts constantly (or, if Rust is the one that's wrong, the guard silently trusts nothing).

Secondary failure modes, each producing "key not valid for use in specified state" or a verify mismatch:
- **Scope mismatch:** Rust protects with `CRYPTPROTECT_LOCAL_MACHINE` (or the crate's `Scope::Machine`) while PowerShell unprotects with `DataProtectionScope::CurrentUser` (or vice-versa). DPAPI scope must match exactly.
- **Entropy mismatch:** one side passes `optionalEntropy`, the other passes `$null`. If entropy is used it must be the **identical byte array** on both sides; a string-vs-bytes or different-encoding entropy silently fails to decrypt.
- **User-profile context:** if the integrity guard ever runs as a service / SYSTEM / scheduled task instead of as Daniel's interactive user, CurrentUser DPAPI cannot unprotect → guard fails. Claude Code hooks run as the user, so this is fine *for the hook*, but watch any watchdog/scheduled-task path.

**Why it happens:**
Everyone reaches for PowerShell's `ConvertTo-SecureString`/`ConvertFrom-SecureString` because they're the "obvious" DPAPI cmdlets, not realizing they add SecureString + UTF-16 framing on top of DPAPI. Rust crates expose the raw Win32 `CryptProtectData` which has none of that framing. The two were never byte-compatible.

**How to avoid:**
- **Define one canonical blob format and make BOTH sides use the raw DPAPI API.** On the PowerShell side use `[System.Security.Cryptography.ProtectedData]::Protect(<32 raw key bytes>, <entropy or $null>, [DataProtectionScope]::CurrentUser)` and `::Unprotect(...)` — NOT `ConvertTo/From-SecureString`. This calls the same `CryptProtectData`/`CryptUnprotectData` Rust uses.
- **Pin scope = CurrentUser on both sides, in writing.** The Rust crate must use user scope (`windows-dpapi` `Scope::User`).
- **Pin entropy explicitly.** Either both `null`/empty, or both a hardcoded constant byte array embedded in both layers. Document it. Don't let one side default to entropy.
- **Store the file as the raw DPAPI blob bytes** (the output of Protect over the 32 key bytes). Decide endianness/length: it's an opaque blob, just write/read the exact bytes — no base64 unless both sides agree base64 + which alphabet.
- **The app (Rust) generates and writes `.guardkey`** (spec already says this). Then write a **round-trip interop test as the very first thing built**: app writes key → a pwsh script unprotects it and prints the 32 bytes hex → Rust re-reads and confirms identical. Make this a CI/manual gate before any HMAC code.

**Warning signs:**
- "Tamper detected" on a config the app just wrote, immediately, with no hand-edit.
- PowerShell error "Key not valid for use in specified state" or "The parameter is incorrect" (HRESULT 0x80070057) on Unprotect.
- The decrypted "key" from one side is 64 bytes (UTF-16 of a 32-char hex string) instead of 32 raw bytes — a dead giveaway of SecureString/hex framing.

**Phase to address:**
Earliest crypto/interop phase, *before* HMAC and before the guard. Treat the round-trip test as the phase's exit gate. This is the project's single highest-risk integration — if it's wrong, the whole revert mechanism is either inert or self-destructive.

---

### Pitfall 2: HMAC canonicalization drift — CRLF/LF, BOM, trailing newline, key/encoding

**What goes wrong:**
Rust writes `config.yaml` with `\n` line endings, no BOM. The user (or an editor, or Git's `autocrlf`) re-saves it as `\r\n` with a UTF-8 BOM. The PowerShell guard reads bytes and recomputes HMAC. The bytes differ → HMAC differs → **false-positive "tamper"** → guard reverts a file the user only *opened*. The inverse is worse: if the guard normalizes line endings before hashing but the signer does **not** (or normalizes differently), a real malicious edit that only changes whitespace-adjacent content can produce a **false negative** (tamper missed). This is a documented, real cross-language signing footgun (PowerShell issue #25246: LF-vs-CRLF breaks signatures; Microsoft KB: signed-script hash mismatch from line endings).

Additional canonicalization landmines:
- **What you sign:** signing the *parsed/serialized* YAML vs the *raw file bytes*. If Rust signs raw bytes but PowerShell re-serializes through its minimal YAML parser and hashes that, they'll never match. The minimal parser in `nightguard_curfew_guard.ps1` is lossy (drops comments, reorders, trims quotes) — it must NOT be the thing that gets hashed.
- **Trailing newline:** Rust's writer adding/omitting a final `\n` flips the hash.
- **Key encoding into HMAC:** if the "key" used for HMAC is the 32 raw bytes on one side but the hex *string* of those bytes on the other, HMAC diverges even with identical message bytes.
- **Hex/base64 of the digest:** uppercase vs lowercase hex, or hex vs base64, when comparing `config_hmac` strings.

**Why it happens:**
Rust and Windows tooling have opposite line-ending defaults; editors and Git silently rewrite files; "sign the config" is ambiguous between bytes and structure; teams forget the HMAC key is bytes, not a string.

**How to avoid:**
- **Define one canonical byte form, documented, and sign exactly those bytes on both sides.** Recommended: HMAC over the **raw file bytes** read with no transformation, after the writer guarantees a fixed normalization: UTF-8 **no BOM**, **LF only**, exactly one trailing `\n` (or none — pick one and write it down).
- **Rust is the sole writer (spec already mandates this).** Have Rust write the canonical bytes deterministically. The guard must hash the file **as-is, raw bytes, no Get-Content line-splitting** — use `[System.IO.File]::ReadAllBytes($path)`, never `Get-Content` (which strips/normalizes newlines and can apply encoding heuristics).
- **Never `git add` the live `config.yaml`/`config.sanctioned.yaml`** without `.gitattributes` forcing `-text` (binary, no autocrlf). Or keep them out of Git entirely (they live in `LifeOS/nightguard/`, not the published repo).
- **HMAC key = the 32 raw bytes**, both sides. Digest comparison = constant-time, lowercase-hex (or raw byte compare), agreed once.
- **Round-trip test alongside Pitfall 1's:** Rust signs → pwsh verifies → pass; then mutate one byte → pwsh detects → revert. Add a CRLF-injection test: take a valid file, convert LF→CRLF, confirm it's correctly flagged as tampered (proving the guard reads raw bytes and didn't accidentally normalize).

**Warning signs:**
- Tamper fires after merely opening the file in an editor that auto-converts EOL or adds BOM.
- Tamper fires only on machines/checkouts where Git `core.autocrlf=true`.
- A whitespace-only or EOL-only change is *not* detected (false negative).

**Phase to address:**
Same crypto phase as Pitfall 1 (sign/verify round-trip). The CRLF + BOM + trailing-newline tests are mandatory exit criteria.

---

### Pitfall 3: Auto-revert footguns — revert loops, racing the app's own write, fail-open lockout

**What goes wrong:**
This is where the tool can hurt the user or hurt itself:
1. **Reverting a legitimate app write (sign-vs-write race).** The app writes `config.yaml` then signs `guard.json`. If the guard fires *between* those two operations (or the writes aren't atomic), it sees a config whose HMAC doesn't match the not-yet-updated `guard.json` → reverts the app's own legitimate change, destroying the edit Daniel just made through the sanctioned path. Inverse race: guard writes `config.sanctioned.yaml` over `config.yaml` while the app is mid-read.
2. **Revert loop / thrash.** If revert copies `config.sanctioned.yaml` → `config.yaml` but doesn't (can't) update `config_hmac` to match, the *next* hook fire sees mismatch again and reverts again — every prompt, forever, logging a tamper each time. Or two processes (UserPromptSubmit + SessionStart + a watchdog) fire concurrently and stomp each other.
3. **Both-tampered → hardcoded strict default destroys real config.** Correct fail-closed behavior, but if it triggers spuriously (e.g., because of a Pitfall 1/2 false positive) it silently overwrites Daniel's real curfew with a hardcoded one — data loss disguised as security.
4. **Brick / lockout.** Fail-closed sets `weekly_spent=3` and grace-used on any `state_hmac` mismatch. If a benign bug makes `guard.json` fail verification, Daniel is locked out of all loosening AND grace with no in-app recovery, and the app itself can't fix it without re-signing — but the app needs a valid key to re-sign. Combined with "curfew enabled by default," he could be hard-blocked from Claude Code with no escape that isn't "edit a file the guard immediately reverts."

**Why it happens:**
Two writers (app + guard) and two-to-three trigger points (SessionStart, UserPromptSubmit, watchdog) over three coupled files (`config.yaml`, `config.sanctioned.yaml`, `guard.json`) with no transaction. Naive revert treats "HMAC mismatch" as a single atomic truth when it's actually a multi-file consistency problem.

**How to avoid:**
- **Atomic, ordered writes from the app, single transaction semantics:** write to temp files, `fsync`/flush, then rename into place. **Order: write new `config.sanctioned.yaml` first, then sign `guard.json` (with the new config_hmac) committed atomically, then last replace `config.yaml`.** Then at no instant does a fired guard see a `config.yaml` whose hash isn't already represented in a committed `guard.json` + sanctioned snapshot. (Equivalently: guard's revert target and the signature must be updated before the live file the guard reads.)
- **Single-writer lock.** Use a lockfile / named mutex so the guard and the app never write concurrently; the guard takes a shared read lock, the app an exclusive write lock. The guard must **never** revert while the app holds the write lock — if it can't acquire the read lock within a short timeout, it should **no-op and let the prompt through** rather than revert (favor not destroying work).
- **Revert must rewrite consistency, not just copy.** Reverting means: copy sanctioned → live AND ensure `config_hmac` already equals the sanctioned file's hash (it should, by construction). If after revert the hashes still mismatch, that's a *guard bug* — log loudly and **stop reverting** (circuit-breaker after N reverts in M minutes) rather than loop forever.
- **Trust the app's own writes by construction, not by detection.** Don't try to "recognize" app writes; instead make the app the only thing that updates the signature, so a correctly-signed config is *definitionally* trusted. There is no heuristic — the HMAC IS the trust token.
- **Provide a recovery path that doesn't require defeating the guard.** A first-run / repair mode in the app that regenerates `guard.json` from the current `config.yaml` (re-sign), gated behind the DPAPI key (which a hand-editor lacks). Document a manual "delete `.guardkey` + sanctioned, relaunch app to re-init" escape so a bug never permanently bricks Daniel.
- **Back up before overwrite.** Before the both-tampered strict-default write, copy the existing files to a timestamped `.bak` so "data loss" is recoverable.

**Warning signs:**
- `tamper.log` shows a revert immediately after a successful in-app commit.
- Repeated identical tamper entries every prompt (loop).
- Daniel reports "I committed in the app but my change is gone."
- Locked out with `weekly_spent=3` he never spent.

**Phase to address:**
The guard / auto-revert phase — but the **atomic-write + ordering + single-writer lock** belongs to the Rust commit phase and must land *before* the guard is allowed to revert. The circuit-breaker and repair-mode are guard-phase exit criteria. Integration test the sign-vs-write race explicitly (fire guard mid-commit).

---

### Pitfall 4: Time/DST/timezone and the +8 grace window

**What goes wrong:**
- **DST transition + Monday-00:00 reset.** Europe/Amsterdam shifts CET↔CEST in late March / late October. If the week-anchor and reset are computed in local wall-clock naively, the DST-shift week is 23h or 25h long; a reset computed as "last anchor + 7*24h" drifts off Monday 00:00, and the spring-forward Sunday→Monday boundary can skip or double-count an hour. Token refill can land at the wrong instant or be skipped.
- **Overnight curfew across DST.** The existing hook computes `inCurfew` from local minutes-of-day; on the spring-forward night, 02:00–03:00 doesn't exist, on fall-back it happens twice — an overnight 21:30→06:00 window can be 1h short/long. Minor, but the grace math layered on top inherits it.
- **NTP unreachable interaction.** Existing hook already blocks when offline (`block_when_offline`). But the +8 grace is "NTP-true-time boxed." If NTP is unreachable when Daniel hits +8, the app can't get true time to set `window_start/window_end`; if it falls back to local clock, a clock-tampered local time could pre-expire or over-extend the window. And the guard re-checks with its *own* NTP — if the guard is offline it blocks (correct) but then the grace Daniel "spent" is wasted with no access.
- **Clock-tamper detection vs grace.** The existing `Test-ClockTampered` blocks if local clock drifts >max_offset from NTP. During an active grace window the guard is told to `exit 0`. If the grace check runs *before* the tamper check, a user could set the local clock forward, trigger grace, and the tamper guard never fires → grace becomes a clock-tamper laundering path. If tamper runs first, a tiny benign drift kills a legitimately-granted grace.
- **Stale-grace replay.** `guard.json.grace = {date, window_start, window_end}`. If the guard only checks "is now inside [start,end]" using a tamperable clock, the user can roll the local clock back into a past window and replay it. Or a `date` field checked against local date lets a clock change re-arm "once per day."

**Why it happens:**
Local wall-clock math is intuitive but wrong across DST; "true time" is only true when NTP is reachable; ordering of tamper-check vs grace-check is an easy oversight; windows stored as absolute timestamps are replayable if validated against an attacker-controlled clock.

**How to avoid:**
- **Store and compute time anchors in UTC; convert to Europe/Amsterdam only for display and for the wall-clock curfew boundary.** Compute "next Monday 00:00 Amsterdam" using a real TZ library (Rust `chrono-tz` / `time` with tzdb; PowerShell `[TimeZoneInfo]::FindSystemTimeZoneById('W. Europe Standard Time')`) that knows DST — never `+7*24h`. The week_anchor is a date (Monday) per spec; resolve reset instant via the TZ database each time, don't precompute a UTC instant that DST invalidates.
- **Validate grace against NTP true-time on BOTH set and check.** Set `window_start/window_end` from NTP; the guard validates `NTP_now ∈ [start,end]`. If NTP is unreachable at grant time, **refuse to grant grace** (don't fall back to local clock) and tell the user. If unreachable at check time, fall to the existing offline-block behavior.
- **Order: tamper-check BEFORE grace-check, but exempt grace from the tamper block correctly.** Run NTP, compute offset. If clock tampered → block regardless of grace (tampering must not be launderable through grace). Then, only with a trusted clock, honor an active grace window. This means grace requires a *non-tampered* clock to be usable — which is the intended security property.
- **Make grace non-replayable: validate against NTP true-time, store the window in UTC, and record consumption by an immutable counter, not a re-derivable date.** "Once per true-day" should be enforced by `grace.date == today(NTP)` where today is the NTP-true Amsterdam date, and the window bounds are UTC instants compared to NTP now — local clock rollback can't re-enter a past UTC window because NTP now keeps advancing. Since `guard.json` is HMAC-signed, the user can't hand-edit the window; the only attack is clock manipulation, which the tamper check already closes.
- **Reuse the existing `ntp_utils.ps1` / `Get-TrueTime` / `Test-ClockTampered`** (spec says extend, don't reinvent) — but confirm the app's Rust SNTP and the PowerShell NTP use a consistent definition of "offset" and "Amsterdam now."

**Warning signs:**
- Tokens refill at 01:00 or 23:00 instead of 00:00 on a DST week.
- Grace appears to last 7 or 9 minutes around a DST boundary.
- Daniel can roll the clock back and re-trigger +8.
- Grace silently consumed but no access granted (NTP was down).

**Phase to address:**
Time/NTP/scheduling phase (week-anchor reset, grace window). The tamper-vs-grace ordering and NTP-required-to-grant rule are exit criteria. Add tests around the two annual DST instants and a clock-rollback replay test.

---

### Pitfall 5: Self-adversary realism — honest ceiling vs security theater

**What goes wrong:**
Effort spent on defenses that an admin trivially bypasses (so they only frustrate, not protect), while the actually-effective friction is under-built. The spec is admirably honest ("nothing here is absolutely unbreakable; the user is admin"), but it's easy to drift into theater: obfuscating the key location, encrypting strings, adding tamper-traps that a determined late-night self just deletes — none of which raise the *impulse-threshold* friction, which is the only thing that matters.

The honest ceiling, stated plainly:
- An admin can **delete or rename the hook scripts** (or the `verify_hook_integrity.ps1` baseline) and the whole guard stops. The spec's mitigation (register the integrity guard in the SHA256 baseline so removal "trips a visible alert") only works if *something Daniel won't disable* checks that baseline — and Daniel can disable that too. It raises friction (he'd have to know to do it), it does not prevent.
- An admin running as Daniel can **script DPAPI as this user and extract/forge the HMAC key** — DPAPI CurrentUser protects against *other* users and offline disk theft, NOT against the user themselves. So "a hand-editor cannot forge a valid HMAC" is true only for a *naive* hand-editor; it is false for Daniel-with-a-script.
- An admin can **uninstall the app, kill the process, disable autostart, or edit `guard.json` after extracting the key.**

**Why it happens:**
Self-binding tools tempt you to imagine the future-impulse-self as dumber/weaker than present-self, and to build a "vault." But the threat model is explicitly "impulse past a friction threshold," not "motivated attacker."

**How to avoid (raise real friction, skip theater):**
- **Build exactly what the spec scopes and no DRM-style obfuscation on top.** The HMAC + DPAPI + auto-revert chain is the right amount: it defeats casual hand-editing (the actual observed failure mode: Daniel editing YAML at night), which is the documented problem. Stop there.
- **Lean on friction that exploits the impulse window's impatience:** the auto-revert "your edit silently vanished" is highly effective because it denies the *reward* of the edit without a fight. Keep reverts fast and silent (per spec) — that's friction that works.
- **The +8 grace IS the pressure valve that prevents bypass-by-frustration.** A self-binding tool with no escape hatch gets ripped out entirely. The once-daily 8-min grace is the anti-theater move: it gives impulse-self a legitimate, bounded outlet, lowering the incentive to learn how to delete hooks.
- **Document the ceiling in the product (and to Daniel), don't hide it.** Honesty prevents the false sense of security that leads to over-trusting the tool. The README should say "this raises friction; an admin who scripts DPAPI can bypass it."
- **Don't add:** code obfuscation, hidden key locations, fake decoy files, anti-debugging, process-protection hacks, registry-hiding. All defeated by the same admin, all pure frustration.
- **Effective, cheap friction worth considering (optional, YAGNI-gate):** make the recovery/disable path require a step that present-rested-self sets up but impulse-self finds annoying (e.g., disabling requires the app + a deliberate confirmation), and make tamper attempts *visible* (log + a startup notice) so the behavior is at least surfaced to rested-self.

**Warning signs:**
- Time being spent on "make the key harder to find" instead of "make revert reliable."
- Claims in code comments / UI that the system is "secure" or "can't be bypassed."
- Feature requests to "really lock it down" that would require admin/ACL fights the spec explicitly ruled out.

**Phase to address:**
Threat-model / README phase (write the honest ceiling down early so it constrains scope) and the guard phase (keep it to HMAC+revert, no obfuscation). This is a *scope discipline* pitfall as much as a technical one.

---

### Pitfall 6: Tauri v2 Windows specifics — capabilities, single-instance, autostart, packaging

**What goes wrong:**
- **Deny-by-default capabilities.** Tauri v2 (unlike v1) exposes *no* command/plugin permission unless granted in `src-tauri/capabilities/*.json`. Forgetting to grant the autostart/single-instance/fs permissions → commands silently fail or the plugin no-ops, often only at runtime in a release build, not in `tauri dev`.
- **Single-instance ordering.** The single-instance plugin **must be registered first** in the Tauri builder (before other plugins) or the second-launch handoff misbehaves. (The snap/flatpak DBus caveat is Linux-only — irrelevant here since Windows-only, but the registration-order rule still applies on Windows.) Without single-instance, launching the app twice gives two writers racing on `guard.json` — directly worsening Pitfall 3.
- **Autostart needs the plugin + explicit permission set** (`autostart:allow-enable`, `allow-disable`, `allow-is-enabled`) AND it writes a `Run` registry key / startup entry that an admin (Daniel) can disable — consistent with the honest ceiling, but don't assume autostart guarantees the app is running. (The *guard* is what's always-on via hooks; the app is open-on-demand per spec, so autostart may even be unnecessary — confirm it's actually needed before adding the plugin/permission surface.)
- **Packaging gotchas:** code-signing (unsigned Windows installers trip SmartScreen — friction for distribution, fine for personal use); WebView2 runtime dependency (present on modern Win11, but the installer should use the evergreen bootstrapper); bundle identifier in `tauri.conf.json` must be set (single-instance derives its IPC name from it, dots/dashes→underscores); and `tauri dev` vs bundled-release path resolution differs — file paths to `LifeOS/nightguard/` must not be relative to the dev cwd.
- **Hook path resolution (flagged in spec's open question).** Whether the guard resolves config via `$PSScriptRoot\..\nightguard\config.yaml` or an absolute path depends on how Claude Code junctions hooks. If junctioned, `$PSScriptRoot` may resolve to `~/.claude/hooks` (the junction target) and `..\nightguard` won't be the LifeOS canonical → guard reads/reverts the wrong file. This is the same drift bug the project is trying to fix.

**Why it happens:**
v2's security model is opt-in and bites in release builds; plugin registration order is under-documented; Windows path/signing behavior differs dev vs prod; junctioned hook paths make `$PSScriptRoot` ambiguous.

**How to avoid:**
- **Define capabilities explicitly and test in a `--release` bundle, not just `tauri dev`.** Grant only the permissions actually used (fs scope limited to `LifeOS/nightguard/`, autostart/single-instance only if used).
- **Register single-instance plugin first.** Set a stable bundle identifier early.
- **Resolve config path absolutely / via a configured path** (spec already wants a "configurable config path"). For the PowerShell guard, resolve the canonical config by an **absolute LifeOS path or an env var**, not `$PSScriptRoot\..` — and verify the actual junction behavior first (the spec's listed open question). Add a startup self-check that logs the resolved config path so drift is visible.
- **Reconsider autostart** — if the always-on enforcement is the hooks (it is), the app may not need autostart at all; dropping it removes a permission + a registry footprint.
- For personal use, skip code-signing initially; note SmartScreen friction if ever published.

**Warning signs:**
- Works in `tauri dev`, plugin/command fails or path is wrong in the installed build.
- Two app windows / two writers after a double-click.
- Guard reverts using a config from `~/.claude/nightguard` instead of `LifeOS/nightguard`.

**Phase to address:**
App scaffolding / Tauri-setup phase (capabilities, single-instance order, bundle id, path resolution). The hook-path resolution must be verified in the guard phase before wiring (spec's open question).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use `ConvertTo/From-SecureString` for the key (the "obvious" cmdlets) | Less code, familiar | Incompatible blob format with Rust DPAPI → silent verify failures (Pitfall 1) | **Never** — use raw `[ProtectedData]` |
| Hash via PowerShell's parsed/re-serialized YAML | Reuse existing minimal parser | Lossy parser → never matches Rust's bytes (Pitfall 2) | **Never** — hash raw file bytes |
| `Get-Content` to read config for hashing | Idiomatic PowerShell | Normalizes line endings / encoding → false tamper | **Never** — use `ReadAllBytes` |
| Skip the single-writer lock (rely on hooks being "fast") | Less plumbing | Sign-vs-write race destroys legit edits (Pitfall 3) | Never for the live system; OK in an isolated unit test |
| Local wall-clock arithmetic for week reset | Simpler than tzdb | DST drift, wrong reset instant (Pitfall 4) | Never — use a TZ library |
| Add obfuscation/decoys "for safety" | Feels more secure | Pure frustration, zero protection vs admin-self (Pitfall 5) | Never |
| Relative `$PSScriptRoot\..` config path | Works on dev machine | Breaks under junctioned hooks → wrong file reverted (Pitfall 6) | Never — resolve absolutely / configured |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| DPAPI (Rust ↔ PowerShell) | SecureString cmdlets on one side, raw `CryptProtectData` on the other | Raw `[ProtectedData]::Protect/Unprotect` both sides; same scope (CurrentUser) + same entropy; round-trip test first |
| File HMAC (Rust signer ↔ PS verifier) | Sign structure vs verify bytes; CRLF/BOM drift | Sign raw bytes; writer fixes UTF-8-no-BOM + LF + fixed trailing newline; verifier uses `ReadAllBytes` |
| NTP/SNTP (Rust app ↔ PS guard) | Different "offset"/timezone definitions; trusting local clock on fallback | Shared true-time definition; refuse grace if NTP unreachable at grant; guard re-checks with own NTP |
| Claude Code hooks | `$PSScriptRoot`-relative paths under junctioned hook dir | Absolute/configured canonical path; log resolved path; verify junction behavior |
| Tauri plugins | Missing capability grant; wrong plugin registration order | Explicit capabilities, tested in release bundle; register single-instance first |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| NTP call on every UserPromptSubmit | Noticeable lag before each prompt during curfew hours | Cache true-time offset briefly (seconds), reuse existing `Get-TrueTime` caching if present | Every prompt, immediately — UX, not scale |
| Re-reading/re-hashing config on every hook fire | Minor per-prompt latency | Files are tiny; fine. Don't over-optimize | N/A at this scale (single user, KB files) |

(Scale is irrelevant here — single user, kilobyte files. The only "performance" concern is per-prompt latency from NTP, not throughput.)

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| DPAPI LocalMachine scope "so the guard can read it" | Any user/process on the box can decrypt the key | CurrentUser scope; the guard runs as Daniel anyway |
| Non-constant-time HMAC comparison | Theoretically leaks via timing (negligible here, but free to do right) | Constant-time compare both sides |
| Validating grace window against local (tamperable) clock | Clock-rollback replays grace; clock-forward launders curfew | Validate against NTP true-time; run tamper-check before honoring grace (Pitfall 4) |
| Treating DPAPI as protection against the user | False security; user-self can script DPAPI | Document the honest ceiling; rely on friction not vault (Pitfall 5) |
| `guard.json` writable + unsigned state trusted | Hand-edit tokens/grace to cheat | State is HMAC-signed; fail closed on mismatch (spec already does this — keep it) |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent revert with no trace | Daniel thinks app is broken ("my edit vanished, no idea why") | Silent to the *impulse* (no reward) but visible to rested-self via tamper.log + a non-blocking startup notice |
| No recovery path on fail-closed brick | Locked out of loosening + grace + curfew with no escape (Pitfall 3) | In-app repair/re-init gated by the DPAPI key; documented manual reset |
| Loosening disabled with no reason shown | Confusion ("why is commit greyed out?") | Spec already shows reason + refill date — keep it |
| +8 grace consumed but blocked anyway (NTP down) | Wasted daily grace, frustration → motivates ripping out the tool | Refuse to *grant* grace when NTP unreachable; surface why |

## "Looks Done But Isn't" Checklist

- [ ] **DPAPI key:** Round-trips byte-for-byte Rust→PS AND PS→Rust — verify decrypted key is exactly 32 raw bytes, not 64 (UTF-16/hex framing).
- [ ] **HMAC verify:** Survives a CRLF conversion test (flagged as tamper) AND a BOM-added test AND a trailing-newline test; whitespace-only edit is *detected* (no false negative).
- [ ] **Commit atomicity:** Firing the guard *during* an in-app commit does NOT revert the legit change (race test).
- [ ] **Revert loop:** Circuit-breaker stops after N reverts/M minutes; no infinite per-prompt revert.
- [ ] **Both-tampered:** Strict-default write backs up the originals first (recoverable).
- [ ] **Fail-closed recovery:** There is an in-app path to re-sign `guard.json` without hand-editing (which would be reverted).
- [ ] **DST:** Week reset lands on Monday 00:00 Amsterdam on both the March and October DST weeks (test both instants).
- [ ] **Grace replay:** Rolling the local clock back does NOT re-enter a past grace window or re-arm "once/day."
- [ ] **NTP down:** Grace grant is *refused* (not local-clock fallback); curfew blocks per existing `block_when_offline`.
- [ ] **Tamper vs grace ordering:** Clock-tamper blocks even during an active grace window (grace can't launder a forwarded clock).
- [ ] **Tauri release build:** Capabilities work in the bundled `--release` build, not just `tauri dev`.
- [ ] **Single instance:** Double-launch yields one window/one writer.
- [ ] **Hook path:** Guard resolves the LifeOS *canonical* config, not `~/.claude/nightguard` — logged and verified under actual junction behavior.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| DPAPI interop broken (Pitfall 1) | HIGH if found late | Fix to raw `[ProtectedData]` both sides; regenerate key; re-sign config+state. Caught by round-trip test → LOW if found early |
| Canonicalization false-positive revert (Pitfall 2) | MEDIUM | Switch guard to `ReadAllBytes`; fix writer normalization; re-sign. Restore lost edit from `.bak`/sanctioned |
| Legit edit reverted by race (Pitfall 3) | MEDIUM | Add lock + reorder writes; restore edit from tamper.log context / `.bak` if backed up |
| Fail-closed brick | MEDIUM | In-app repair re-init (DPAPI-gated); or manual: delete `.guardkey` + sanctioned, relaunch app to regenerate |
| Both-tampered strict-default overwrote real config | HIGH if no backup, LOW if `.bak` exists | Restore from timestamped `.bak` (must be implemented — see checklist) |
| DST/reset drift | LOW | Recompute anchor via tzdb; tokens self-correct next reset |
| Grace replay exploited | LOW (it's self-harm) | Tighten to NTP-true-time validation; it's the user cheating themselves anyway |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. DPAPI interop (TOP) | Crypto/key phase (first) | Byte-for-byte Rust↔PS key round-trip test passes; decrypted key = 32 raw bytes |
| 2. HMAC canonicalization | Crypto/sign-verify phase (first) | CRLF/BOM/trailing-newline tamper tests pass; whitespace edit detected |
| 3. Auto-revert footguns | Rust commit phase (atomic writes/lock) + guard phase (circuit-breaker, repair) | Race test (guard during commit) doesn't revert; no revert loop; repair path works |
| 4. Time/DST/grace | Time/NTP/scheduling phase | March + October DST reset tests; clock-rollback replay test; tamper-before-grace ordering; NTP-down refuses grant |
| 5. Self-adversary realism | Threat-model/README (early) + guard phase scope discipline | README states honest ceiling; no obfuscation added; +8 grace present as pressure valve |
| 6. Tauri v2 specifics | App scaffolding phase + guard wiring | Capabilities work in release bundle; single instance; canonical config path resolved + logged |

## Sources

- Microsoft Learn — `ProtectedData.Unprotect` / `CryptProtectData` / `CryptUnprotectData` (scope, optionalEntropy, "Key not valid for use in specified state" under impersonation): https://learn.microsoft.com/en-us/dotnet/api/system.security.cryptography.protecteddata.unprotect , https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata — HIGH
- `windows-dpapi` crate (Rust raw DPAPI, `Scope::User`/`Scope::Machine`): https://crates.io/crates/windows-dpapi , https://github.com/sheridans/windows-dpapi — HIGH
- PowerShell community on DPAPI / ProtectedData vs SecureString framing: https://devblogs.microsoft.com/powershell-community/encrypting-secrets-locally/ , https://github.com/dlwyatt/ProtectedData/wiki — MEDIUM
- PowerShell issue #25246 "LF instead of CRLF can break signatures" + MS KB "signed PowerShell script fails hash mismatch": https://github.com/PowerShell/PowerShell/issues/25246 , https://learn.microsoft.com/en-us/troubleshoot/windows-client/system-management-components/signed-powershell-script-fails-hash-mismatch — HIGH (confirms line-ending/encoding canonicalization breaks cross-tool hashing)
- Tauri v2 security/capabilities, single-instance, autostart docs: https://v2.tauri.app/security/capabilities/ , https://v2.tauri.app/security/permissions/ , https://v2.tauri.app/plugin/single-instance/ , https://v2.tauri.app/plugin/autostart/ — HIGH
- Project spec + existing hook (`docs/design-spec.md`, `.planning/PROJECT.md`, `LifeOS/hooks/nightguard_curfew_guard.ps1`) — the honest-ceiling constraint, NTP/clock-tamper reuse, and hook-path open question are drawn directly from these — HIGH

---
*Pitfalls research for: self-binding Windows enforcement tool (Tauri v2 + Rust + DPAPI/HMAC + PowerShell auto-revert)*
*Researched: 2026-06-04*
