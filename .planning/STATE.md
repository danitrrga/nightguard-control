---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 3 context gathered
last_updated: "2026-06-08T14:11:37.208Z"
last_activity: 2026-06-08
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 12
  completed_plans: 11
  percent: 40
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-04)

**Core value:** A late-night, impulsive version of the user cannot quietly loosen their own curfew — loosening costs a limited weekly token, and hand-editing the raw config silently reverts.
**Current focus:** Phase 03 — enforcement-guard

## Current Position

Phase: 03 (enforcement-guard) — EXECUTING
Plan: 4 of 4
Next: Phase 03 (Enforcement Guard) — needs planning
Status: Ready to execute
Last activity: 2026-06-08

Phase progress: [████░░░░░░] 2/5 phases complete (Phase 02: 5/5 plans)

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

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
- [Phase 3, 03-03]: Guard clock-half COMPLETE. Guard-side SNTP (48-byte packet, byte0=0x1B, parse bytes 40..43 BE, NTP1900->unix via -2208988800; $null on ANY error -> deny+fail_closed, NEVER Get-Date / D-07). A4 clock-tamper: |trueNow-local|>300s -> deny (skipped under override seam). Grace honored gated on $stateValid (NOT (-not $graceUsed) -- plan-02 sets graceUsed=window-present, so the plan's literal condition was unreachable; a state_hmac mismatch -> $stateValid=false -> never allow / T-03-15) AND grace.window_end>trueNow. HMAC-chained audit (record_tag=HMAC(key, prev_tag||payload), 64-zero genesis, AppendAllText UTF-8 no-BOM, pipe-delim escaped payload / D-08; @() forces array so a single line never collapses to a scalar char-index). D-02 JSON {decision,reason,grace_remaining_secs,reverted,fail_closed} + exit 0=allow/1=deny. run_guard_gate.ps1 GREEN proving GARD-01/02/03/04/05 end-to-end vs real DPAPI/HMAC fixtures, -NtpOverrideUnixSecs seam, Rust verify-state-hmac cross-check, and a live with_commit_lock holder (new state_interop_cli hold-commit-lock subcommand). Gate self-signs guard.json in PS (config_hmac=real HMAC(config.yaml), state_hmac via A3) because emit-state-hmac's fixed dummy config_hmac can't drive a byte-exact revert.

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: DPAPI + HMAC Rust↔PowerShell interop is the single genuine technical risk — must pass the byte-identical round-trip spike as the phase exit gate.
- [Phase 2]: Verify `sntpc 0.10.1` `sync::get_time` signature and `yamlpatch` round-trip against the actual PowerShell minimal YAML parser at integration.
- [Phase 3]: Verify hook-path resolution under Claude Code junctions before wiring (`$PSScriptRoot\..` may resolve to the drifted `~/.claude/nightguard`).

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-08T14:11:37.198Z
Stopped at: Completed 03-03-PLAN.md (guard clock-half + end-to-end GARD gate green)
Resume file: None
Env note: this machine has Windows PowerShell 5.1 (NOT pwsh 7) — PowerShell scripts/harnesses must stay 5.1-compatible (ASCII, no em-dash literals in -File scripts, gate on $LASTEXITCODE).
