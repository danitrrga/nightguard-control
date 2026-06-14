---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: milestone_complete
stopped_at: Milestone complete (Phase 05 was final phase)
last_updated: 2026-06-11T16:05:23.406Z
last_activity: 2026-06-10
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 20
  completed_plans: 20
  percent: 80
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-04)

**Core value:** A late-night, impulsive version of the user cannot quietly loosen their own curfew — loosening costs a limited weekly token, and hand-editing the raw config silently reverts.
**Current focus:** Milestone complete

## Current Position

Phase: 05
Plan: Not started
Next: 05-02-PLAN.md — build deployable hooks (adapter + watchdog rewrite + install/deploy)
Status: Milestone complete
Last activity: 2026-06-14 - 260614-dkp: fixed countdown overflowing the ring (288px ring, 44px digits) + redesigned logo/mark (cobalt guard-arc + bone crescent), icons regenerated

Phase progress: [████████░░] 4/5 phases complete (Phase 04: 5/5 plans)

## Performance Metrics

**Velocity:**

- Total plans completed: 12
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 03 | 4 | - | - |
| 04 | 5 | - | - |
| 05 | 3 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 1 P01-02 | 5 | 2 tasks | 8 files |
| Phase 1 P01-03 | 10 | 3 tasks | 5 files |
| Phase 2 P02-01 | 8 | 2 tasks | 13 files |
| Phase 2 P02-02 | 14 | 3 tasks | 6 files |
| Phase 2 P02-03 | 6 | 1 task | 2 files |
| Phase 2 P02-04 | 5 | 2 tasks | 4 files |
| Phase 2 P02-05 | 11 | 2 tasks | 4 files |
| Phase 3 P01 | 6 | 2 tasks | 2 files |
| Phase 3 P02 | 12 | 2 tasks | 1 files |
| Phase 3 P03 | 22 | 2 tasks | 3 files |
| Phase 3 P04 | 4 | 1 task | 3 files |
| Phase 04 P01 | 7 | 2 tasks | 15 files |
| Phase 04 P02 | 14 | 1 tasks | 4 files |
| Phase 04 P03 | 5 | 2 tasks | 1 files |
| Phase 04 P04 | 6 | 2 tasks | 8 files |
| Phase 04 P05 | 8 | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 1]: DPAPI-stored HMAC key shared by Rust + PowerShell (raw `CryptProtectData` blob, never SecureString framing).
- [Phase 1]: HMAC input form LOCKED to raw file bytes (resolved in 01-01); writer emits one byte form (UTF-8/no-BOM/LF/one-trailing-newline); empty/BOM-only -> single LF.
- [Phase 1]: Atomic write hand-rolled (temp+rename in same parent dir, no tempfile crate) to guarantee atomic same-volume rename on Windows.
- [Phase 2]: Direction classifier is Rust-only; the guard is direction-agnostic (reverts anything not matching the signature).
- [Phase 5]: Propagation fix is instance-level config, not product surface — point the hook at the LifeOS canonical config (zero-copy).
- [Phase 1]: HMAC-SHA256 known-answer vector = HMAC(32x0x0b, "Hi There") derived via an RFC 4231 TC1-faithful oracle (resolved in 01-02); constant-time verify via `verify_slice`, never `==`; signer hashes raw bytes (no internal normalization).
- [Phase 1]: DPAPI key store uses `windows-dpapi` 0.2.0 (`Scope::User`, `None` entropy) — raw `CryptProtectData` blob; 32-not-64 length guard (`KernelError::BadKeyLength`) is the SecureString-framing canary.
- [Phase 1]: Cross-language exit gate PROVEN GREEN — Rust<->PowerShell DPAPI key round-trips to identical 32 bytes both directions, HMAC-SHA256 tags byte-identical both signing directions over raw file bytes, CRLF/BOM tampers flagged both sides; the project's single genuine technical risk is closed.
- [Phase 1]: interop harness is host-agnostic ([ProtectedData]/[HMACSHA256] are .NET framework types identical in pwsh 7 and Windows PowerShell 5.1); signs raw bytes on disk with no re-canonicalization at sign time so cosmetic CRLF/BOM/trailing-newline drift is tamper.
- [Phase 2, 02-01]: state_hmac recipe LOCKED (A3) — serialize GuardState with state_hmac blanked to "", canonicalize_bytes, sign_bytes, tag_to_hex; the field is re-blanked on every computation so its prior value never affects the tag (Phase 3 PS guard must re-derive identically).
- [Phase 2, 02-01]: sign_config returns (hex tag, canonical bytes) so the caller writes EXACTLY the signed bytes (sign-the-canonical-bytes invariant; closes Pitfall 3 / T-02-02 by construction).
- [Phase 2, 02-01]: guard.json field names/types locked as the Phase 3 PowerShell interop contract (A1); GuardState derives PartialEq for round-trip assertions.
- [Phase 2, 02-01]: sntpc 0.10.1 + sntpc-net-std 1.2 pairing confirmed by a clean dependency-tree resolve (Pitfall 1 did not materialize).
- [Phase 2, 02-02]: Defensive A2 covers BOTH a missing leaf key (yamlpath query_exact -> Ok(None)) AND structural absence on the path (ExhaustedMapping/ExpectedMapping/Exhausted-/ExpectedList query errors) — all map to field-absent Noop; only malformed YAML folds to Serde (never a panic, never a silent loosen, T-02-05).
- [Phase 2, 02-02]: week reset is DST-aware via from_local_datetime + explicit MappedLocalTime (Ambiguous->earliest deterministic); next_monday_midnight re-derives from the local Monday DATE + 7 days (transition week = 169h), never +7*24h (T-02-06; grep gate = 0).
- [Phase 2, 02-02]: QuotaDecision.next_reset is always populated (upcoming Monday), and decide() applies the lazy week reset to an EFFECTIVE weekly_spent before charging — a stale spent=3 never blocks a fresh-week loosen; blocked reason carries the locked 'available again Monday' substring (RULE-04).
- [Phase 2, 02-03]: true-time is behind a TrueTime trait — SntpTrueTime (real sntpc::sync::get_time over UdpSocketWrapper) in production, FakeTrueTime injected in tests; only the #[ignore] live test touches UDP. Every sntpc::Error (incl. #[non_exhaustive] variants via catch-all Err(_)) maps to NtpUnreachable — NO system/local clock fallback path exists (fail-closed, T-02-08). NtpUnreachable is both a zero-size type (for local matches!) and folds into MutationError via From (for ? propagation). Built-in NTP fallback list: cloudflare/google/pool, first success wins.
- [Phase 2, 02-05]: Assumption A3 CLOSED in-phase — state_hmac is byte-identical Rust<->PowerShell both directions, proven by run_state_interop_gate.ps1 (GREEN under Windows PowerShell 5.1.26100). The Rust bin emits the EXACT pre-sign canonical bytes (.signbytes); the PS side HMACs them verbatim (raw-bytes HMAC, no sign-time canonicalization) reusing the Phase 1 Get-FileHmacHex; shared key via DPAPI blob (PS protects, Rust load_or_create_key unprotects). state_interop_cli reuses the single locked GuardState::compute_state_hmac recipe (no duplicate). Tamper proven two-pronged: guard.json byte-flip -> Rust verify exit 2; .signbytes byte-flip -> PS tag differs. This is the template the Phase 3 PS guard's state-verification path follows.
- [Phase 2, 02-04]: commit ordering LOCKED — sanctioned -> guard.json (re-signed, config_hmac=HMAC(NEW canonical bytes), state_hmac via A3) -> live config.yaml LAST (write_canonical_text, same canonical bytes). Crash converges to OLD or NEW, never a forged middle (commit_order.rs stop-after-N for N in {0,1,2,3} + a local copy of the guard's verify-and-revert rule). One fd-lock exclusive lock (with_commit_lock, LockFileEx) wraps BOTH commit_change and use_grace so they never interleave guard.json writes. commit trusts the supplied QuotaDecision (token++/ledger only when costs_token), it does not re-classify. Grace (RULE-05) derives true-day from the NTP instant in the configured tz (Pitfall 4, never Local::now()), costs no token, and is refused — leaving guard.json byte-unchanged — on same-true-day reuse (GraceAlreadyUsedToday) or NtpUnreachable.
- [Phase ?]: [Phase 3, 03-01]: RUNTIME state_hmac re-derive proven green (Check 4) -- parse pretty guard.json, blank state_hmac, ConvertTo-Json -Compress -Depth 10, UTF-8 no BOM, append one 0x0A, HMAC; matches on-disk tag WITHOUT reading .signbytes. T-03-01 mitigated.
- [Phase ?]: [Phase 3, 03-01]: fd-lock presence probe proven green (lock_probe.rs) -- [IO.File]::Open(p,'Open','ReadWrite','None') IOException == held against a live Rust with_commit_lock holder; lock file persists so existence != held; FREE after release. T-03-02 mitigated; plan 02 lifts this shape into Test-LockHeld.
- [Phase ?]: [Phase 3, 03-02]: Guard config_hmac is trusted ONLY when state-verify passes; a forged/unverifiable guard.json folds to maximal-lockout rather than trusting its config_hmac (fail-closed vs T-03-06/07/08). Revert is [IO.File]::Copy(sanctioned,live) gated by Test-LockHeld; maximal-lockout is a hardcoded 24/7-curfew canonical-bytes literal via Write-RawBytes; guard NEVER writes guard.json (re-sign is the Rust DPAPI repair, D-05).
- [Phase 3, 03-04]: GARD-06 / D-10 shipped in-repo. verify_hook_integrity.ps1 = SHA256 baseline writer (-Update) + drift checker (default), self-registering nightguard_guard.ps1 AND itself (editing/removing EITHER -> exit 1 alert; T-03-16/T-03-17). Get-FileHash -Algorithm SHA256 (raw bytes, no EOL normalization); manifest line form "<sha256>  <fwd-slash-relpath>", ASCII, LF. guard.baseline.sha256 committed against the final plan-02/03 guard. run_guard_gate.ps1 deliberately NOT registered (dev test harness, not enforcement surface). Rule 2 fix: added scripts/guard/*.ps1 -text to .gitattributes (mirrors the Pitfall-2 config*.yaml/*.guardkey defense) so core.autocrlf=true cannot LF->CRLF the hashed scripts into false drift on a fresh checkout -- keeps "clean checkout verifies green" true cross-host. Verified: clean=exit 0 (both PASS), one-byte append=exit 1 naming the path, byte-exact restore=exit 0, both files ASCII-only. Phase 3 enforcement-guard COMPLETE.
- [Phase 3, 03-03]: Guard clock-half COMPLETE. Guard-side SNTP (48-byte packet, byte0=0x1B, parse bytes 40..43 BE, NTP1900->unix via -2208988800; $null on ANY error -> deny+fail_closed, NEVER Get-Date / D-07). A4 clock-tamper: |trueNow-local|>300s -> deny (skipped under override seam). Grace honored gated on $stateValid (NOT (-not $graceUsed) -- plan-02 sets graceUsed=window-present, so the plan's literal condition was unreachable; a state_hmac mismatch -> $stateValid=false -> never allow / T-03-15) AND grace.window_end>trueNow. HMAC-chained audit (record_tag=HMAC(key, prev_tag||payload), 64-zero genesis, AppendAllText UTF-8 no-BOM, pipe-delim escaped payload / D-08; @() forces array so a single line never collapses to a scalar char-index). D-02 JSON {decision,reason,grace_remaining_secs,reverted,fail_closed} + exit 0=allow/1=deny. run_guard_gate.ps1 GREEN proving GARD-01/02/03/04/05 end-to-end vs real DPAPI/HMAC fixtures, -NtpOverrideUnixSecs seam, Rust verify-state-hmac cross-check, and a live with_commit_lock holder (new state_interop_cli hold-commit-lock subcommand). Gate self-signs guard.json in PS (config_hmac=real HMAC(config.yaml), state_hmac via A3) because emit-state-hmac's fixed dummy config_hmac can't drive a byte-exact revert.
- [Phase ?]: [Phase 4, 04-01]: src-tauri added as the third workspace member (single root [workspace]); the four IPC commands (get_state/classify_change/commit_change/use_grace) registered with FINAL signatures as stubs over a fixed StateDto/ClassifyDto/IpcError contract (D-01). AppCtx::load resolves NIGHTGUARD_DIR like the guard and loads .guardkey once (Scope::User, single key path); placeholder get_state ships fail-closed (maximal_lockout, 0 tokens) so the scaffold never looks less locked than the guard; fs:scope left broad with a plan-03 tighten TODO.
- [Phase ?]: [Phase 4, 04-02]: lock_status is a pure (config_yaml, now) -> LockStatus curfew evaluator in mutation-engine. Precedence: curfew.enabled=false => not locked; schedule.<day> overrides start/end (off => unlocked, HH:MM-HH:MM => that window); overnight-wrap inside = minute>=start||minute<end with the boundary on the CORRECT calendar day (next day for a late-entered wrap, never naive +24h, DST-aware via explicit MappedLocalTime like week.rs); absent/malformed field => fail-safe LOCKED (D-04/A2, never a silent unlock). grace_active=false here -- get_state overlays the signed guard.json grace window. Reuses classify::parse_hhmm/parse_window made pub(crate) -- exactly ONE HH:MM parser. 11 offline tests green.
- [Phase 4, 04-04]: Status view + liveness shipped (UI-01/UI-02/UI-05). render() derives every assertion from a fresh get_state DTO (D-03); !state_verified||maximal_lockout -> fully-locked "State unverified" warm-tone copy, never optimism. Hero countdown is 64px tabular-nums (Display); status word 🌙 LOCKED / · grace / OPEN ("next lock at {time}"); 3-dot accent token meter ("{n} of 3 tokens · resets Monday {date}") + grace caption; NotInitialized -> empty state. plugin-fs watch(dataDir, refresh, {delayMs:250}) re-invokes get_state on any data-dir change (D-05/D-09); 1s setInterval re-renders ONLY countdown digits and never the status word (T-04-14). New additive data_dir IPC command surfaces the absolute watch target (AppCtx.data_dir consumed, its #[allow(dead_code)] removed). fs:scope narrowed off bare ** to $HOME/.nightguard + $APPDATA/nightguard (least-privilege T-04-17; residual: non-conventional NIGHTGUARD_DIR is out of watch scope -> tick+load-fetch+re-read-on-action still keep displayed state correct). Roboto 400/500 woff2 bundled locally from fontsource mirror, no runtime CDN (T-04-16). Moonlit Indigo hand CSS (palette tokens + 4-size type scale + 8pt spacing + 56px aria-labelled inline-SVG left rail), no UI framework/icon package. tsc clean, vite build green (fonts in dist/assets), cargo build zero warnings.
- [Phase 4, 04-05]: Edit view shipped (UI-03/UI-04/UI-05) — vertical slice complete. Single --surface per-field editor (curfew.enabled/start/end) runs classify_change debounced (~250ms) per field -> exact UI-SPEC feedback ("Tightens curfew · free"=accent / "Loosens curfew · costs 1 token"=warn / noop silent); Commit disabled with the locked "available again Monday" reason on a 0-token loosen (UI-04) + "Commit (spends 1 token)" loosen label; one-step "Spend a weekly token?" confirm ONLY on loosening commits (D-08, tighten-only skips). commit_change/use_grace re-render Status ONLY from the returned re-verified StateDto (D-09 — no optimistic token decrement / grace flip; grep-clean). +8 button enabled IFF locked && grace_available_today with the REAL disabled attribute (D-10, not styling-only) + accent .enabled fill; use_grace -> re-render (boundary retargets to grace_end), NtpUnreachable/GraceAlreadyUsedToday surfaced inline amber non-punitively. Added a read-only read_config IPC seam (Rule 3 blocking — the edit classify old/new pair needs the live config text); new_yaml composed by per-field line edit on the loaded config (yamlpath-faithful, comment/format-preserving), absent field left untouched. Reuses plan-04 tokens/scale (no second design system). tsc clean, vite build green, cargo check zero warnings. Task 3 human-verify checkpoint auto-approved under AUTO_MODE; live tauri-dev walkthrough deferred to the phase verifier.
- [Phase 5, 05-01]: Author's LifeOS instance INITIALIZED and verifying. NIGHTGUARD_DIR (User scope) = C:\Users\20252128\dev\Projects\LifeOS\nightguard (reads back in a fresh process). New `init-instance <data_dir>` subcommand in state_interop_cli composes the locked primitives (canonicalize_bytes + load_or_create_key DPAPI Scope::User + compute_state_hmac A3 + most_recent_monday_midnight DST-aware) — never fixed test state. The data dir now holds config.yaml (canonical bytes, content no-op — curfew 20:45->05:30 + watchdog/StayFree + Spanish-butler msgs intact), a byte-identical config.sanctioned.yaml, a fresh DPAPI .guardkey (unprotects to exactly 32 bytes), and a fully-armed guard.json (weekly_spent=0 -> 3 tokens, week_anchor 2026-06-08, grace=null, ledger=[]). Cross-language parity PROVEN on a real Windows CurrentUser session: state_hmac=94d8... and config_hmac=7618... re-derive identically Rust<->PowerShell, verify-state-hmac exit 0, HMAC(sanctioned)==config_hmac. CARRY-FORWARD: NIGHTGUARD_DIR is already set (do not re-set); the live curfew gate is still the OLD hook (untouched) — WIRE-01 only partially advanced, drift not eliminated until Plan 03's prove-then-switch cutover (T-05-05 accepted).
- [Phase ?]: [Phase 4, 04-03]: four IPC commands real + signature-frozen. get_state/commit_change/use_grace all return ONE build_state_dto helper re-verifying config_hmac (constant-time verify_bytes over canonicalize_bytes) + state_hmac (A3 compute_state_hmac), worst-casing on tamper EXACTLY like the guard (weekly_spent=3/tokens=0/grace_available=false/maximal_lockout) in one place; lock/boundary from lock_status with active guard.json grace overlaid (boundary_kind=grace_end). classify_change wraps classify+quota::decide (disable-at-0-tokens preview; took a managed AppCtx body-fill, JS shape unchanged). commit_change gates decision.allowed in-command -> true NTP fail-closed -> engine ordered fd-locked commit::commit_change -> re-read (D-09); use_grace -> grace::use_grace -> re-read. No hand-rolled writer, no == on a config tag.

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: DPAPI + HMAC Rust↔PowerShell interop is the single genuine technical risk — must pass the byte-identical round-trip spike as the phase exit gate.
- [Phase 2]: Verify `sntpc 0.10.1` `sync::get_time` signature and `yamlpatch` round-trip against the actual PowerShell minimal YAML parser at integration.
- [Phase 3]: Verify hook-path resolution under Claude Code junctions before wiring (`$PSScriptRoot\..` may resolve to the drifted `~/.claude/nightguard`).

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260612-fhu | Polish the edit view (sole sanctioned editor) — Ceramic Night | 2026-06-12 | 03a57e9 | [260612-fhu-polish-edit-view](./quick/260612-fhu-polish-edit-view/) |
| 260612-fsc | Tray number-badge — runtime time-remaining on the tray icon | 2026-06-12 | 8f67492 | [260612-fsc-tray-number-badge](./quick/260612-fsc-tray-number-badge/) |
| 260612-gc2 | Globalize curfew guard hook + app login-autostart (close-to-tray) | 2026-06-12 | d96c76c | [260612-gc2-global-curfew-autostart](./quick/260612-gc2-global-curfew-autostart/) |
| 260613-opk | UI Polish: fix layout, alignment, text inconsistencies plus add custom window chrome | 2026-06-13 | 14e3bc7 | [260613-opk-ui-polish-fix-layout-alignment-text-inco](./quick/260613-opk-ui-polish-fix-layout-alignment-text-inco/) |
| 260614-dkp | Polish: fix countdown overflowing the ring + redesign logo/mark | 2026-06-14 | 4edcfc8 | [260614-dkp-polish-app-countdown-text-doesnt-fit-in-](./quick/260614-dkp-polish-app-countdown-text-doesnt-fit-in-/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-09T15:28:12.150Z
Stopped at: Phase 5 context gathered
Resume file: .planning/phases/05-instance-wiring/05-CONTEXT.md
Env note: this machine has Windows PowerShell 5.1 (NOT pwsh 7) — PowerShell scripts/harnesses must stay 5.1-compatible (ASCII, no em-dash literals in -File scripts, gate on $LASTEXITCODE).
