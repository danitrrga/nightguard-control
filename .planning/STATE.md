---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Desktop App
status: "Phase 12.1 gate remains OPEN/rejected on the record. Phase 12.2.1 inserted after 12.2 to build the Omarchy shell panel as the full control surface and retire the ngtui terminal app; the polkit-vs-sudo/PTY gate is already proven live on this box. Run /gsd:discuss-phase 12.2.1 next."
stopped_at: Phase 12.2.1 context gathered
last_updated: "2026-09-13T14:08:04.275Z"
last_activity: 2026-09-13
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 18
  completed_plans: 18
  percent: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-24 — opened v2.1 · Desktop App)

**Core value:** A late-night, impulsive version of the user cannot quietly loosen their own curfew — loosening costs a limited weekly token, and hand-editing the raw config silently reverts. *(v2.0: the wall is now root-backed; `sudo` is the past-the-impulse threshold.)*
**Current focus:** Phase 12.2.1 — omarchy-native-panel

## Current Position

Phase: 12.2.1 (omarchy-native-panel) — NOT PLANNED
Plan: 0 of 0
Status: Phase 12.1 gate remains OPEN/rejected on the record. Phase 12.2.1 inserted after 12.2 to build the Omarchy shell panel as the full control surface and retire the ngtui terminal app; the polkit-vs-sudo/PTY gate is already proven live on this box. Run /gsd:discuss-phase 12.2.1 next.
Last activity: 2026-09-13

## Performance Metrics

**Velocity:**

- Total plans completed: 26
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 03 | 4 | - | - |
| 04 | 5 | - | - |
| 05 | 3 | - | - |
| 07.1 | 3 | - | - |
| 09 | 2 | - | - |
| 11 | 3 | - | - |
| 12 | 6 | - | - |

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
| Phase 06 P01 | 14 min | 1 tasks | 4 files |
| Phase 07.1 P01 | 13 | 2 tasks | 1 files |
| Phase 07.1 P02 | 20min | 1 tasks | 2 files |
| Phase 07.1 P03 | ~10min | 2 tasks | 1 files |
| Phase 08 P01 | 18 | 2 tasks | 1 files |
| Phase 08 P02 | 14 | 2 tasks | 1 files |
| Phase 10 P10-02 | ~20min | 3 tasks | 9 files |
| Phase 10 P10-03 | ~35min | 3 tasks | 6 files |
| Phase 11 P01 | 43 | 2 tasks | 4 files |
| Phase 11 P02 | 2 | 2 tasks | 2 files |
| Phase 11 P03 | ~1min | 2 tasks (human-verify) | 0 files |
| Phase 12 P01 | 2 | 2 tasks | 1 files |
| Phase 12 P02 | 4 | 2 tasks | 2 files |
| Phase 12 P03 | 4 | 1 tasks | 1 files |
| Phase 12 P04 | 5 | 3 tasks | 5 files |
| Phase 12 P05 | 12 | 2 tasks | 5 files |
| Phase 12 P06 | 40 | 2 tasks | 2 files |
| Phase 12.1 P01 | 22 | 3 tasks | 3 files |
| Phase 12.1 P02 | 9min | 2 tasks | 2 files |
| Phase 12.1 P03 | 41 | 3 tasks | 3 files |
| Phase 12.1 P04 | 17min | 3 tasks | 3 files |
| Phase 12.1 P06 | 25 | 3 tasks | 3 files |
| Phase 12.1 P07 | 40 | 5 tasks | 9 files |
| Phase 12.1 P08 | 48 | 2 tasks | 4 files |
| Phase 12.1 P09 | 25 | 2 tasks | 3 files |

## Accumulated Context

### Roadmap Evolution

- Phase 12.1 inserted after Phase 12: Native dashboard — TUI restyled from shell.toml structural tokens, one cursor shared between pointer and keyboard
- Phase 12.2 inserted after Phase 12.1: Blocking becomes editable — the four keys the signer classifies but the editor never exposed, at one token per list
- Phase 12.2.1 inserted after Phase 12.2: Omarchy Native Panel — polkit gate proven live on this box before opening the phase; supersedes 12.2's editing scope, delivered in the panel instead of the TUI (URGENT)

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
- [Phase 06]: [Phase 6, 06-01]: direction-classifier FIELD_TABLE re-pointed from the dead Windows watchdog.apps (uwp/package_id) list to the Linux blocking: model — blocking.browser_extension.enabled + blocking.native_apps.enabled (BoolTrueIsStrict), blocking.native_apps.blacklist (ListRemoveLoosens); extension_id intentionally omitted (id change = Noop); watchdog.enabled/check_interval_seconds kept. Grep gate clean. Rule-3 blocker: Windows-only state_interop_cli bin gated to #[cfg(windows)] so the crate compiles on Linux. LXCF-01 product half done; instance half + LXCF-02 remain in the still-blocked 06-02. — config.yaml is signed as opaque canonical bytes, so the schema change is transparent to signing; the classifier table is the only product code reading the blocking keys; Phase 8's native blocker reads blocking.native_apps.blacklist.
- [Phase 7.1, 07.1-01]: UserPromptSubmit fires BEFORE slash-command expansion (verified live on CC 2.1.186) — prompt field carries the raw /plan /shutdown leading token. MATCHER: leading-token (tighter than the Windows substring match; closes the loosening hole). Recorded in 07.1-MATCHER-DECISION.md for Plan 02's allowlist.
- [Phase ?]: [Phase 7.1, 07.1-02]: Adding to curfew.allow_commands is a LOOSEN (1 token spent), not free — the root signer correctly classifies widening the escape valve as a curfew loosening. /plan signed live (verify all-green, config_hmac=1a18fc24). Adapter committed in LifeOS at 3b470b9.
- [Phase ?]: 07.1-03: full-D-04 — generator emits the global curfew UserPromptSubmit hook into user-scope ~/.claude/settings.json; idempotent, survives SessionStart, un-dodgeable per-project (CURF-01 closed).
- [Phase ?]: [Phase 8, 08-01]: pure key-less curfew_verdict(cfg, state) extracted from decide(); decide() re-expressed in terms of it (D-09 single-source gating); grace_remaining_secs stays decide()-local (C2); per-tick true_unix() memo = one resolution per decide(); standalone-safe for 08-02. Behavior-preserving (byte-identical decide() JSON parity). LifeOS 7c2bc05 + faec552.
- [Phase ?]: [Phase 8, 08-02]: native-app kill folded into the root watchdog tick — _kill_native_apps enumerates Hyprland via runuser->user bridge (per-tick HIS discovery, runtime-derived username C7), substring class/initialClass match (D-03), pid dedup (D-02), SIGKILL-by-pid (D-01), per-pid watchdog.log audit (D-07); gated on key-less guard.curfew_verdict with state.grace worst-cased on a state_hmac mismatch (C5), fires on locked/clock_tamper/offline_blocked, suppressed otherwise; one butler toast per tick (C6/D-06); list argv no shell + bounded timeouts (T-08-04/08); un-stoppable from user space (NBLK-01/02/03). LifeOS d7bb61b + b6d819f.
- [Phase 10]: 10-02: omarchy-native theming — colours from live colors.toml, no fixed brand hex; running TUI repaints on an mtime poll (D-04/D-05)
- [Phase 10]: 10-02: read-surface logic is pure-function-first (verdict_display/token_meter/ledger_rows) so it unit-tests headless
- [Phase 10, 10-03]: EditScreen ships (PORT-01/02/03). lineedit.py = format-preserving per-field LINE editors (set_scalar/toggle_bool/list_add/list_remove) over config TEXT — indentation-tracked dotted-path resolution disambiguates same-named leaf keys (blocking.native_apps.enabled vs browser_extension.enabled); preserves indent + quote style + trailing comments; round-trips via the live ngcommon.yaml_load; NO YAML emitter (a re-emit would change the bytes the signer HMACs → the guard reverts the user's own commit, T-10-09). Proposed config = replay staged ops on backend.sanctioned_text() so every transform starts from the signed bytes. EditScreen edits the D-09 set via single-key nav (j/k/Enter/Space/c/u/Escape); each staged edit renders tighten/loosen direction + token cost from the signer's OWN backend.preview_change (classify_change/quota_decide) BEFORE auth (D-06/D-07, never recomputed). ConfirmScreen: y is the ONLY commit trigger; 0-token loosen disables commit with "available again Monday"; commit runs inside App.suspend() so sudo is inline (D-08); post-commit re-reads sanctioned state (no optimism); result_line is returncode-keyed (stderr stays on the TTY — intentional UI-SPEC deviation from verbatim-REFUSED). Pure copy helpers preview_line/confirm_copy/result_line unit-tested headless (exact UI-SPEC strings + $-var roles). Task-3 human-verify APPROVED LIVE. PHASE 10 COMPLETE (3/3).
- [Phase 11]: [Phase 11, 11-01]: ngtui status core is a pure stdlib status.py — _VERDICT_CLASS maps the 5 guard verdicts to same-name Waybar classes with dict.get(verdict,'locked') fail-closed (unknown -> locked, never unavailable/outside_curfew); UNAVAILABLE={text:'○ —',class:'unavailable'} is reserved for Plan 02's import/read except branch (empty data is 'locked', Pitfall 3); backend.cache_only_verdict neutralizes guard._sntp/_http_time (instant-raise, restored in finally) so a cold timecache falls to offline_blocked in <0.2s, never a ~4s block; key-less and zero new deps.
- [Phase 11]: [Phase 11, 11-03]: install/PTY boundary HUMAN-VERIFIED GREEN on the live box (no code change). SC-1: `uv tool install --python 3.14 .` puts a real `ngtui` on the bare login PATH (`~/.local/bin/ngtui`) that resolves the LifeOS stack under a scrubbed `env -i` (backend.py hardcoded defaults). DESK-02/SC-3: installed-shim `ngtui status --json` emits a single jq-valid Waybar object with a real verdict class, fails closed to `{"text":"○ —","class":"unavailable"}` exit 0 on a poisoned NIGHTGUARD_STACK_DIR. SC-5 GREEN: guard.json + sanctioned config `root:root 0644` (readable), `.guardkey` `root:root 0600` (denied) — isolated venv never reads the key. SC-4: a REAL loosen-with-token commit succeeded end-to-end from the installed shim, inline-`sudo` prompt appeared in-terminal (App.suspend() released a genuine PTY despite the global-install interpreter), token decremented, guard did NOT revert the sanctioned commit. DESK-01/DESK-02 satisfied; Phase 11 COMPLETE (3/3).
- [Phase ?]: [Phase 11, 11-02]: ngtui/__main__ is a bare-argv front-controller — `ngtui status [--json]` routes to head-less _status (import ngtui.backend INSIDE the try so a poisoned NIGHTGUARD_STACK_DIR RuntimeError-at-import degrades to UNAVAILABLE; verdict via cache_only_verdict not live_verdict; one json.dumps line; ALWAYS exit 0). Bare ngtui -> _run_tui behind a sys.stdin.isatty() SystemExit(2) guard on the TUI branch ONLY, with ngtui.app/textual imported lazily so status never pays textual's cost. 67 headless tests green.
- [Phase ?]: [Phase 12, 12-01]: ngtui install-gate PASSED — uv tool install --python 3.14 . reinstalled the shim; command -v ngtui -> ~/.local/bin/ngtui (T-12-01 mitigated, first-party wheel only). ngtui status --json jq-valid (class+text), exit 0, fail-closed. D-10 baseline LOCKED at 67 passing ngtui tests. Generated ngtui/uv.lock gitignored. All P12 live-wiring surfaces unblocked.
- [Phase 12]: [Phase 12, 12-02]: D-11/BAR-04 shipped — backend.commit() fires pkill -RTMIN+11 waybar ONLY on returncode==0, inside check=False + swallow-all try/except; result dict built independently so a refused commit never flips the bar (T-12-02) and a raising/absent pkill never perturbs the outcome (T-12-03). SIGRTMIN+11 free (7/8/9/10 taken). 71 ngtui tests (67 baseline +4).
- [Phase ?]: [Phase 12, 12-04]: five canonical omarchy artifacts shipped (D-06) — nightguard.desktop (app-id=org.omarchy.ngtui, Terminal=false, -e ngtui), explicit 3-line Hyprland float rule keyed on class not title (SC-1/T-12-07), key-less custom/nightguard module (signal 11, on-click omarchy-launch-or-focus-tui, on-click-right ngtui-menu), six-class semantic style.css (D-09), ngtui-menu walker --dmenu read-only/open-only menu (no loosen action, T-12-06). Marker-guarded for Plan 05. No ngtui code touched -> D-10 71-test baseline intact.
- [Phase 12]: [Phase 12, 12-06]: live omarchy integration landed + phase-gated. install.sh ran on the author's box (backup-first, idempotent); auto-verify 12/12; human-verify APPROVED for float/icon/bar/read-only-menu/SIGRTMIN+11 commit-refresh. Installer hardened for the live single-line modules-center array + no-match-grep abort under set -euo pipefail (1db34ff). Phase 12 COMPLETE (6/6).
- [Phase ?]: [Phase 12.1, 12.1-01]: async idiom for every Pilot control is asyncio.run(_body()) inside a plain sync test — no marker, no asyncio_mode; the suite stays runnable under a bare pytest. Rejected idiom's message recorded verbatim: 'async def functions are not natively supported.' reported as a FAILURE not an error (Pitfall 9/T-12.1-03).
- [Phase ?]: [Phase 12.1, 12.1-01]: UI controls must query through app.screen, never app — App.query is scoped to the default screen and returns 0 after push_screen (measured: app.query('.ctl')=0 vs app.screen.query('.ctl')=5). Every app.query(...) in RESEARCH/PATTERNS must be read as app.screen.query(...).
- [Phase ?]: [Phase 12.1, 12.1-01]: a Textual event handler cannot be replaced by overriding it — every on_mount in the MRO runs (message_pump.py:758). probe_app calls event.prevent_default(); without it the base pushed StatusScreen on top of the probe screen, which would have routed UI controls into live guard state (T-12.1-01).
- [Phase ?]: [Phase 12.1, 12.1-01]: a relative CSS_PATH resolves against the directory of the module where the App subclass is DEFINED — a probe subclass in tests/ resolved 'app.tcss' to tests/app.tcss. probe_app pins it absolute from ngtui.app.__file__.
- [Phase ?]: [Phase 12.1, 12.1-01]: Wave 1 complete — 4 UI fixtures + control 1 (literal-hex scan, seen to catch an injected #7aa2f7) + the async canary. Suite 459 passed / 1 failed / 3 skipped; baseline is 453 (not 458 — a theme was removed mid-planning, c40df13). No file under ngtui/ngtui/ touched.
- [Phase ?]: [Phase 12.1, 12.1-02]: Colour roles resolve through per-role pick chains, first declared key wins — 25 of 27 installed themes collapsed the verdict colours to one because the loader knew only the ANSI color1/2/3 vocabulary
- [Phase ?]: [Phase 12.1, 12.1-02]: The Textual-role sweep asserts provenance and verdict distinctness, never surface-vs-background: 4 of 27 themes legitimately resolve them equal (D-11)
- [Phase ?]: [Phase 12.1, 12.1-02]: Provenance cannot catch theme.py's 'or accent' fallback — it is an in-theme colour. Distinctness is the load-bearing assertion; measured, not assumed
- [Phase ?]: [Phase 12.1, 12.1-03] hypr_rounding's returncode check is invisible to a JSONDecodeError test — JSONDecodeError IS a ValueError, so the parse except already catches it. The discriminating control is a non-zero rc whose stdout parses: it returns 12 instead of 0
- [Phase ?]: [Phase 12.1, 12.1-03] Border widths clamped at both the parser and the mapper; measured, removing either layer alone leaves the end-to-end assertion green, so the clamp is asserted per layer
- [Phase ?]: [Phase 12.1, 12.1-03] ThemeWatch stats both colors.toml and shell.toml; paths added, path kept because two shipped tests pin watch.path by name
- [Phase ?]: [Phase 12.1, 12.1-03] UIX-01 still Pending after three plans: its text requires the running TUI to restyle, and nothing is wired into the App until plan 04
- [Phase ?]: 12.1-06: the Content + textual.style.Style colour route — an alpha never becomes a string, so rich's 8-digit-hex rejection is structurally unreachable
- [Phase ?]: 12.1-06: the now marker is painted only when the clock was verified — an unread clock produces no claim about the time
- [Phase ?]: 12.1-06: a control whose expectations are computed from the function under test cannot catch a uniformly-wrong version of it — measured, then fixed with an independent symmetry property
- [Phase ?]: 12.1-06: UIX-04 left Pending — the mechanism is finished but nothing composes DayRamp, so the day the user sees is still a number
- [Phase 12.1, 07]: The home surface is composed from home_controls()'s registry inside one #frame, landing exactly on UI-SPEC 7.2's 46 rows with the audit ledger as the only 1fr region (7 rows against a floor of 4 — the 3 rows of slack are 12.2's seam). Header and Footer are gone and e/r/l/q were measured firing with no Footer mounted; the help chip mounts a HelpPanel listing all four descriptions it replaced, and escape closes it because show_help_panel is not a toggle.
- [Phase 12.1, 07]: The j/k cursor walk moved to a shared base class, widgets/cursorstop.py::CursorStop, so it visits the DayRamp (stop 1 of 16) as well as the ControlRows. Its own module rather than controlrow.py because controlrow.py reaches the trust stack through widgets/edit.py and hero.py's pure helpers must stay importable without it.
- [Phase 12.1, 07]: DayRamp gave up h/l — l is one of the four single-key bindings pinned to NightguardApp (ledger) and the ramp holds the cursor on mount, so the ledger toggle was unreachable from the screen's opening state. left/right carry the read-out.
- [Phase 12.1, 07]: backend.py was NOT touched (the plan's own stop condition), so eight of home_controls()'s nine machine facts have no reader and degrade to their documented defaults in _machine_facts(). The WEAK MODE header alarm is raised only when enforcement was actually READ, never by the unread default.
- [Phase 12.1, 07]: A row budget needs three independent claims — measured: with one extra row, max_scroll_y stayed 0 because the 1fr ledger absorbed it. Assert that it fits, that exactly one region is flexible, AND that the flexible one keeps its slack. Plan 08's overflow control inherits the same blindness.
- [Phase 12.1, 12.1-08]: The ledger's min-height: 4 is enforced in app.tcss rather than stated: measured, the degradation ladder runs out of things to drop at 31 rows and the audit record was the region that kept shrinking — 3 rows at a 30-row terminal, 1 at 24.
- [Phase 12.1, 12.1-08]: The window budget is three claims, each armed to a different bug: max_scroll_y, the frame's own region, and every widget's bottom edge. Claims 1-2 are blind to a 1-3 row overrun the ledger absorbs; test_dashboard_home's ledger-slack claim catches those.
- [Phase ?]: [Phase 12.1, 12.1-09]: The no-crypto scan (PORT-03) had been scanning zero files — NGTUI_SRC resolved one parent.parent too deep, to a directory that does not exist. Fixed with a path correction plus a vacuity guard AND a wrong-tree guard, because the corrected path alone still reported 3 passed when re-pointed at a missing directory.
- [Phase ?]: [Phase 12.1, 12.1-09]: UIX-01 stays Pending after nine plans. Measured: omarchy_style() parses 31 spacing_* keys and font_base, style_variables() emits no variable for either, and the only reader in the tree is panel.py (out of bounds). The [controls] half, the rounding and the live-restyle path are proved; [spacing] and [font] have no path at all.
- [Phase ?]: [Phase 12.1, 12.1-09]: Feedback-latency budget revised 4 s to 45 s. Full suite measures 42.75 s (was 3.01 s) because the phase added 22 Pilot integration tests; five registry/ladder sweeps cost 24 s of it. The sign-off box is left UNTICKED rather than its number edited.

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: DPAPI + HMAC Rust↔PowerShell interop is the single genuine technical risk — must pass the byte-identical round-trip spike as the phase exit gate.
- [Phase 2]: Verify `sntpc 0.10.1` `sync::get_time` signature and `yamlpatch` round-trip against the actual PowerShell minimal YAML parser at integration.
- [Phase 3]: Verify hook-path resolution under Claude Code junctions before wiring (`$PSScriptRoot\..` may resolve to the drifted `~/.claude/nightguard`).
- [v2.0 P0 — HIGHEST RISK]: the Linux Python trust stack (`ngcommon`/`guard`/control-CLI/`nightguard_watchdog` .py) is absent from disk (only stale `.pyc`) and untracked in git. Blocks 06-02 and all of Phase 7. Restore + commit before any execution.
- [Phase 8 — DE-RISKED 2026-06-22]: root watchdog reaching the user-owned Hyprland socket (`/run/user/1000/hypr`). Verified feasible — `runuser`-to-user + per-tick `$HIS` discovery (root traverses via CAP_DAC_OVERRIDE; socket node is world-rwx). Full approach + edge cases + live-proof command in `.planning/phases/08-native-blocker/08-NOTES-hyprland-from-root.md`. Not a blocker; implement in Phase 8.
- [12.1 — RESOLVED 2026-09-13, plan 07]: plan 04's control 2 (test_controls_fill_alpha_reaches_the_row) was flaky at 4/10 runs. Fixed by settling past the fill cross-fade two independent ways (a wait derived from styles.transitions, plus animator.is_being_animated keyed on styles.base). 30/30 consecutive passes; both rung assertions re-armed and seen red. Textual's own pilot.wait_for_animation()/wait_for_scheduled_animations() do NOT work here — Animator.start() sets both wait events after the first _animate.
- [12.1 — OPEN 2026-09-13, plan 09]: the phase gate. The live walkthrough has NOT been performed: two real `omarchy theme set` switches with the app open (city-783 for the hand-written shell.toml, one generated-shell.toml theme for the other branch of the variable map), the real-mouse hover-then-j continuation, and the user's verdict on whether it reads as a native Omarchy application. The shim is already reinstalled from this tree (uv tool install --python 3.14 . --force; packaged app.tcss diff-identical to the repo's), so the walkthrough will test this phase's UI and not the old one. Nothing in 12.1-VALIDATION.md claims this was done.
- [12.1 — OPEN 2026-09-13, plan 09]: UIX-01 is the phase's one incomplete requirement. [spacing] and [font] are named in its text, parsed by omarchy_style() as 31 spacing_* keys plus font_base, and style_variables() emits no variable for either — the only reader in the tree is panel.py, which the scope fence puts out of bounds. Either wire them or amend the requirement's text to match what a character grid can express; do not close it silently.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 20260905 | Close five no-password bypasses of the trust wall (time-override env seam, lock-hold revert freeze, removable browser policy, root running user-writable code, user-owned instance dir) + docker group and polkit | 2026-09-05 | e0c820f | [20260905-nightguard-trust-wall-hardening](./quick/20260905-nightguard-trust-wall-hardening/) |
| 260616-grc | Grace "+8" button live across the curfew boundary (1s tick re-fetches get_state on boundary) | 2026-06-16 | 2257c04 | [260616-grc-grace-button-live-refresh](./quick/260616-grc-grace-button-live-refresh/) |
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

Last session: 2026-09-13T14:08:04.261Z
Stopped at: Phase 12.2.1 context gathered
Resume file: .planning/phases/12.2.1-omarchy-native-panel/12.2.1-CONTEXT.md
Env note: this machine has Windows PowerShell 5.1 (NOT pwsh 7) — PowerShell scripts/harnesses must stay 5.1-compatible (ASCII, no em-dash literals in -File scripts, gate on $LASTEXITCODE).

## Deferred Items

Items acknowledged and deferred at v2.0 milestone close on 2026-06-24 (11 total — see v2.0-MILESTONE-AUDIT.md for the integration/tech-debt detail):

| Category | Item | Status | Note |
|----------|------|--------|------|
| quick_task | 260612-fhu-polish-edit-view | missing | stale v1.0 Windows UI polish — superseded by omarchy TUI |
| quick_task | 260612-fsc-tray-number-badge | missing | stale v1.0 Windows UI polish — superseded by omarchy TUI |
| quick_task | 260612-gc2-global-curfew-autostart | missing | stale v1.0 — curfew now enforced via the Linux hook (CURF-01) |
| quick_task | 260613-opk-ui-polish-fix-layout-alignment-text | missing | stale v1.0 Windows UI polish |
| quick_task | 260614-dkp-polish-app-countdown-text-fit | missing | stale v1.0 Windows UI polish |
| quick_task | 260616-grc-grace-button-live-refresh | missing | stale v1.0 Windows UI polish |
| uat_gap | 04-HUMAN-UAT (Phase 04) | partial (0 open) | v1.0 Windows UI — superseded |
| uat_gap | 07.1-HUMAN-UAT (Phase 07.1) | partial (1 open) | curfew hook UAT — hook is live and wired |
| verification_gap | 04-VERIFICATION (Phase 04) | human_needed | v1.0 Windows UI — superseded |
| verification_gap | 07.1-VERIFICATION (Phase 07.1) | human_needed | CURF-01 wired + live; doc re-confirmation only |
| verification_gap | 10-VERIFICATION (Phase 10) | human_needed | D-06/D-05 approved LIVE during the 10-03 walkthrough; doc re-confirmation only |

Tech-debt carried forward (from v2.0-MILESTONE-AUDIT.md): NBLK descoped (native-kill reverted), TRAK parked (StayFree dead on Wayland; offline config-import a future-phase candidate), Nyquist backfill for phases 6/7/7.1/8/9, ROOT-02 watchdog wording, browser-policy root-lock.

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone

## Phase 12.1 — gate rejected

The nine plans all executed and the automated ledger is complete, but the live
walkthrough verdict on 2026-09-13 was **not approved**: the surface still reads as a
terminal form, not as a native Omarchy dashboard, and worse than what it replaced.

Phase verification was NOT run and the roadmap was NOT advanced. Do not treat 12.1 as
complete. The next move is an iterative design session, not a gap-closure pass — the
problem is the visual language, not a missing control.

Open items carried out of the phase:

- The structural-token keystone (UIX-01) is still Pending: the style reader parses 31
  spacing keys and the base font, and the variable emitter emits no variable for either.
  No path exists, not merely no consumer.

- Ten of the 34 style variables have no consumer; five structurally cannot have one.
- The stated "under 4 seconds" validation latency is false — measured 42.75 s.
- Deferred, not defects at 135x46: the editor has no on-screen legend since the footer was
  removed (and nothing is bound to f1 in textual 8.2.7); resize keys on the screen size, so
  a tiled split narrows the surface without the narrow class firing.
