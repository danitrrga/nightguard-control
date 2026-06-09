---
phase: 04-ui-moonlit-indigo
audited: 2026-06-09
auditor: gsd-security-auditor
disposition: SECURED
threats_total: 22
threats_closed: 22
threats_open: 0
block_on: [critical, high]
status: secured
---

# SECURITY.md — Phase 04 (ui-moonlit-indigo)

**Audited:** 2026-06-09
**Auditor:** gsd-security-auditor
**Disposition:** SECURED — 25/25 threats CLOSED (22 registered + 3 named code-review trust-boundary fixes)
**block_on:** critical,high — none open

This is a verification audit: each declared mitigation was confirmed present in the
implemented code (grep + read of the cited file/line). Implementation files were not
modified. Evidence is `file:line`.

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-04-01 | InfoDisclosure | mitigate | CLOSED | `commands.rs:70-83` AppCtx holds `key: [u8;32]`; no DTO field carries it (`StateDto` 129-148, `ClassifyDto` 160-170); `lib.rs:44` `.manage(ctx)` — key never serialized/returned |
| T-04-02 | EoP | mitigate | CLOSED | `commands.rs:109` single key path `load_or_create_key(data_dir.join(".guardkey"))`; `key.rs:41-60` Scope::User via dpapi_protect/unprotect, `None` entropy; no second path |
| T-04-03 | Spoofing | mitigate (was accept→superseded) | CLOSED | `get_state` (`commands.rs:352-355`) delegates to `build_state_dto` (198-311); full read→re-verify→worst-case. No optimistic placeholder remains |
| T-04-04 | EoP | mitigate (deferred→done) | CLOSED | superseded by T-04-17; see fs:scope below |
| T-04-SC | Tampering (supply chain) | mitigate | CLOSED | `package.json:12-20` only `@tauri-apps/*`, typescript, vite; `src-tauri/Cargo.toml`, `crates/*/Cargo.toml` match STACK pins (hmac 0.12.1, sha2 0.10.9, subtle 2, windows-dpapi 0.2.0, sntpc 0.10.1, yamlpath/yamlpatch 1.25, fd-lock 4). No typosquat/unexpected dep |
| T-04-05 | Spoofing | mitigate | CLOSED | `lock_status.rs:155-166` only explicit `false` disables; absent/malformed `enabled` → `fail_safe_locked` (83-90, `locked=true`). Overnight-wrap explicit (198-213) |
| T-04-06 | Tampering | mitigate | CLOSED | `lock_status.rs:180-194` malformed window/missing start-end → `fail_safe_locked`; `read` (281-295) folds malformed YAML to fail-safe; no panic, no silent unlock |
| T-04-07 | DoS | mitigate | CLOSED | `lock_status.rs:273-275` `parse_tz` `.unwrap_or(chrono_tz::UTC)`; `config_timezone` (125-134) UTC default; no panic on bad tz |
| T-04-08 | Spoofing | mitigate | CLOSED | `commands.rs:226` constant-time `verify_tag_hex` re-verify of state_hmac; mismatch → worst-case branch (249-267): `weekly_spent=3`, `tokens_remaining=0`, `grace_available_today=false`, `grace_active=false`, `maximal_lockout=true` |
| T-04-09 | Tampering | mitigate | CLOSED | `commands.rs:215-219` `canonicalize_bytes` + constant-time `verify_bytes` over config; `config_verified=false` → `maximal_lockout=true` (245) |
| T-04-10 | InfoDisclosure | mitigate | CLOSED | constant-time BOTH paths: config `verify_bytes` (`hmac.rs:37-41`, `commands.rs:217`), state `verify_tag_hex` (`hmac.rs:55-64` subtle ct_eq, `commands.rs:226`). Grep confirms NO `==`/`!=` on any HMAC tag in commands.rs (only doc-comments + `g.date != today` string compare). CR-01 fix landed |
| T-04-11 | EoP | mitigate | CLOSED | `commands.rs:468-472` re-checks `decision.allowed` in-command; `commit.rs:148` re-checks again; sole writer `commit::commit_change` (`commands.rs:481`); no hand-rolled writer |
| T-04-12 | Tampering | mitigate | CLOSED | `commit.rs:155` `with_commit_lock`; ordered sanctioned(FIRST)→guard.json→config.yaml(LAST) (`commit.rs:164-173`, doc 3-23); grace also lock-wrapped (`grace.rs:51`) |
| T-04-13 | Spoofing | mitigate | CLOSED | `commands.rs:475-478` commit sources `SntpTrueTime`, maps failure → `IpcError` (fail-closed, no clock fallback); `use_grace` (505) via engine `grace.rs:56` NtpUnreachable refuse; display time advisory (`time_unverified=true`, `commands.rs:304`) |
| T-04-14 | Spoofing | mitigate | CLOSED | `main.ts:201-210` `renderCountdownOnly` touches only `#countdown`, never status word; `main.ts:524-526` tick calls only `renderCountdownOnly`; passed boundary shows 00:00:00 awaiting watch refresh |
| T-04-15 | Spoofing | mitigate | CLOSED | `main.ts:118-145` render derives from DTO; `verifyFail` → "State unverified" fully-locked copy (127-132); `last` assigned only by `refresh()`/grace/commit re-read (53, 231-235) |
| T-04-16 | Tampering | mitigate | CLOSED | `styles.css:11-25` two local `@font-face` (`./assets/roboto-{400,500}.woff2`); no remote URL in CSS/HTML; CSP `font-src 'self'` (`tauri.conf.json:25`) enforces it |
| T-04-17 | EoP (fs:scope) | mitigate | CLOSED | `lib.rs:27-41` setup extends fs scope to runtime-resolved `ctx.data_dir` via `app.fs_scope().allow_directory`; capability (`default.json:6-18`) grants only `fs:allow-watch`/`fs:allow-unwatch` + scoped paths. WR-02 fix landed |
| T-04-18 | EoP | mitigate | CLOSED | `commands.rs:468-472` server-side `decision.allowed` re-check; a forced `invoke('commit_change')` at 0-token loosen is refused regardless of UI gating |
| T-04-19 | Spoofing | mitigate | CLOSED | `main.ts:465-468` commit re-renders from returned re-verified `StateDto`; no local token mutation; `commands.rs:483-484` re-reads via `build_state_dto` |
| T-04-20 | EoP | mitigate | CLOSED | `main.ts:188-191` +8 enabled only `locked && grace_available_today` (real `disabled` attr); server `grace::use_grace` refuses NtpUnreachable/GraceAlreadyUsedToday (`grace.rs:56,65`) |
| T-04-21 | Tampering | mitigate | CLOSED | `main.ts:453-461` one `window.confirm` naming token cost fires only when `loosens`; tighten-only/neutral skips confirm |
| T-04-22 | Repudiation | mitigate | CLOSED | `main.ts:477-481` server refusal surfaces inline (`editReasonEl`), Status state unchanged; success path (465-468) re-renders returned verified DTO |

## Code-Review Trust-Boundary Fixes (cross-checked — landed, fail-closed preserved)

| Fix | Status | Evidence |
|-----|--------|----------|
| CR-01 (state tag constant-time) | CLOSED | `commands.rs:226` `verify_tag_hex`; `hmac.rs:55-64` subtle ct_eq; no `==` on tags |
| WR-01 (`today_in_tz` fail-closed) | CLOSED | `commands.rs:320-326` returns `Option<String>`; `278-282` `(Some(_), None) => false` — unresolvable today → grace NOT re-armed |
| WR-05 (commit re-verifies on-disk config HMAC as baseline) | CLOSED | `commands.rs:446-457` `canonicalize_bytes`+`verify_bytes` of `old` side against `gs.config_hmac`; mismatch → commit refused |
| WR-06 (quota/grace tz from config, not hardcoded) | CLOSED | `commands.rs:237` `config_timezone(&config_yaml)` drives `quota::decide`/`today_in_tz`; same in classify (404), commit (464), grace (500-502) |
| WR-03 (restrictive CSP) | CLOSED | `tauri.conf.json:25` explicit `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self' ipc: http://ipc.localhost` (no longer null) |

## Unregistered Flags

None. The only `## Threat Flags` section across the five SUMMARYs (`04-01-SUMMARY.md:158`)
reports "None — no security surface beyond the plan's threat_model was introduced." The
net-new attack surface (IPC boundary + webview, per `04-RESEARCH.md:542`) is fully covered
by the registered threats T-04-01..T-04-22.

## Accepted Risks Log

None outstanding. T-04-03 (optimistic placeholder, accepted at plan 01) and T-04-04
(broad fs:scope, deferred) were both superseded by implemented mitigations (plan 03's
re-verified read; T-04-17's runtime scope narrowing) — neither remains an accepted risk.

## Residual / Tracked Debt (non-blocking, informational only)

The code review left IN-01..IN-05 as tracked debt; none is a declared-threat gap:
- IN-01 dead `VerifyFailed` variant (`commands.rs:43-45`) — no security impact.
- IN-02 empty-state detection via error-string substring (`main.ts:240`) — UX brittleness, fail-safe.
- IN-03 `console.error`/`warn` artifacts (`main.ts:244,263`) — no secret leaked.
- IN-04 `parse_list` flow-only (`classify.rs`) — outside Phase 4 file set; loosen-detection edge, tracked.
- IN-05 LOCKED fail-safe `00:00:00` countdown — acceptable fail-safe, cosmetic.

None of these weakens a declared mitigation; all are CLOSED-with-note, not OPEN.
