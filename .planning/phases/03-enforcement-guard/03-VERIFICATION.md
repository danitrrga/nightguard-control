---
phase: 03-enforcement-guard
verified: 2026-06-08T17:00:00Z
status: passed
score: 6/6 must-haves verified (static code + live runtime execution)
overrides_applied: 0
runtime_verification:
  executed: 2026-06-08T17:01:00Z
  executed_by: orchestrator (Windows PowerShell 5.1.26100.8115, this host)
  results:
    - test: "scripts/guard/run_guard_gate.ps1"
      result: "PASS — GARD-01/02/03/04/05/06 all PASS, exit 0 (real DPAPI, NTP seam, live Rust fd-lock holder, CR-01 production-safety property)"
    - test: "scripts/guard/verify_hook_integrity.ps1"
      result: "PASS — 4 registered scripts match baseline, exit 0"
    - test: "scripts/interop/run_state_interop_gate.ps1"
      result: "PASS — all 4 state_hmac checks incl. runtime re-derive, exit 0"
    - test: "cargo test -p mutation-engine --test lock_probe"
      result: "PASS — powershell_probe_distinguishes_held_vs_free_lock ok, exit 0"
human_verification_resolved: "All four items below were executed live on the canonical host and passed; status promoted human_needed -> passed."
human_verification:
  - test: "Run the guard end-to-end gate: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/guard/run_guard_gate.ps1"
    expected: "Exit 0 with GARD-01/02/03/04/05/06 all PASS in the === Summary === block"
    why_human: "Gate exercises real DPAPI (CurrentUser, this machine's key), live SNTP UDP, a spawned Rust process (cargo-built hold-commit-lock), and PowerShell subprocess spawning — none of which can be verified by static grep"
  - test: "Run the integrity check: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/guard/verify_hook_integrity.ps1"
    expected: "Exit 0 with 4 registered scripts PASS; baseline hashes match the on-disk files (nightguard_guard.ps1, verify_hook_integrity.ps1, nightguard_interop.ps1, state_interop.ps1)"
    why_human: "Get-FileHash result depends on the working-tree bytes including autocrlf state; correct only the developer can confirm on the canonical host"
  - test: "Run the state interop gate: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/interop/run_state_interop_gate.ps1"
    expected: "Exit 0 with all 4 checks (including Check 4 runtime state-verify) PASS"
    why_human: "Exercises real DPAPI and a live Rust CLI emit; requires the machine that holds the DPAPI key"
  - test: "Run the Rust test suite: cargo test -p mutation-engine (includes lock_probe integration test)"
    expected: "Exit 0; lock_probe::powershell_probe_distinguishes_held_vs_free_lock passes"
    why_human: "Spawns a PowerShell subprocess inside a Rust test; requires Windows + PowerShell on PATH"
---

# Phase 03: Enforcement Guard Verification Report

**Phase Goal:** The always-firing PowerShell guard makes the binding real — out-of-band edits
silently revert, tampered state fails closed, grace is honored against the guard's own true time,
and the guard cannot revert a legitimate in-app write.

**Verified:** 2026-06-08T17:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A hand-edit to config.yaml (any byte) is reverted to the sanctioned snapshot on the next guard fire | VERIFIED | `Get-FileHmacHex` on live vs `config_hmac` at line 231-234; mismatch → `[IO.File]::Copy(sanctioned, live)` at line 247 inside the mismatch branch; GARD-01 check in `run_guard_gate.ps1` lines 211-228 |
| 2 | If both live and sanctioned config are invalid, the guard writes a hardcoded maximal-lockout default (24/7 curfew) | VERIFIED | `Write-MaximalLockoutDefault` at lines 165-199 in `nightguard_guard.ps1`; GARD-02 check asserts `MAXIMAL LOCKOUT DEFAULT` string + `00:00-23:59` in written file; `$failClosed = $true` set at line 255 |
| 3 | If guard.json state_hmac does not re-derive, the guard substitutes weekly_spent=3 and grace-as-used (no write) | VERIFIED | `$stateValid` gate at line 212; mismatch branch sets `$weeklySpent = 3; $graceUsed = $true` at lines 220-221; no `Write-RawBytes` targeting `guard.json` anywhere in script; GARD-03 gate check lines 249-269 |
| 4 | While the app holds .nightguard.lock, the guard skips the revert this cycle (reverted=false) | VERIFIED | `Test-LockHeld` called BEFORE `[IO.File]::Copy` at line 241; returns `$false` (skip) if `IOException` on exclusive open; GARD-05 check drives real `hold-commit-lock` Rust subcommand lines 299-341 |
| 5 | Guard honors an active grace window against its own NTP true-time, re-locks after expiry, and denies when NTP is unreachable or clock is skewed | VERIFIED | `Get-GuardNtpUnixSecs` at lines 281-306 returns `$null` on any exception (fail-closed); NTP-null → deny+fail_closed at line 401-407; clock-skew >300s → deny at line 408-415; `window_end > trueNow` grant gated on `$stateValid` at lines 423-432; GARD-04 check covers honored/expired/offline at lines 271-297 |
| 6 | The guard scripts are registered in a SHA256 integrity baseline; altering or removing any raises a non-zero alert | VERIFIED | `guard.baseline.sha256` contains 4 entries (nightguard_guard.ps1, verify_hook_integrity.ps1, nightguard_interop.ps1, state_interop.ps1); `verify_hook_integrity.ps1` self-registers; drift → exit 1 via `Add-Check` pattern; GARD-06 in `run_guard_gate.ps1` lines 343-360 asserts production-shape override is ignored |

**Score:** 6/6 truths verified (static code evidence)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/guard/nightguard_guard.ps1` | Always-firing guard: config-verify, state-verify, SNTP, audit, JSON output | VERIFIED | 464 lines; dot-sources both interop libs; `ConvertTo-Json -Compress -Depth 10` at line 116; `2208988800` at line 268; `window_end` at line 424; `Test-LockHeld` at line 241; `[IO.File]::Copy` at line 247 |
| `scripts/guard/run_guard_gate.ps1` | End-to-end exit gate GARD-01..06 | VERIFIED | 378 lines; `NtpOverrideUnixSecs` seam wired through `Invoke-Guard`; `hold-commit-lock` Rust subcommand used for GARD-05; GARD-06 `AllowOverride:$false` check present |
| `scripts/guard/verify_hook_integrity.ps1` | SHA256 baseline writer + drift checker, self-registering | VERIFIED | 152 lines; `Get-FileHash -Algorithm SHA256` at line 51; 4 registered paths at lines 40-45 (includes both interop scripts per CR-02 fix); self-registers `verify_hook_integrity.ps1` |
| `scripts/guard/guard.baseline.sha256` | SHA256 manifest registering 4 guard/interop scripts | VERIFIED | 4 lines present; hashes match working-tree files (PowerShell `Get-FileHash` cross-checked: b2b3377d matches nightguard_interop.ps1, 080498244 matches state_interop.ps1) |
| `crates/mutation-engine/tests/lock_probe.rs` | Rust integration test: HELD/FREE probe against live fd-lock | VERIFIED | 100 lines; asserts `HELD` inside `with_commit_lock` closure; asserts `FREE` after release with file still on disk; uses `[IO.File]::Open(...,'None')` catching `[IO.IOException]` |
| `crates/mutation-engine/src/bin/state_interop_cli.rs` | `hold-commit-lock` and `verify-state-hmac` subcommands | VERIFIED | `cmd_hold_commit_lock` at line 173 implements real `with_commit_lock` + ready/release sentinel; `cmd_verify_state_hmac` at line 133 recomputes and compares via locked recipe |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `nightguard_guard.ps1` | `guard.json.config_hmac` | `Get-FileHmacHex` over live config.yaml, compared at line 234 | WIRED | Mismatch branch at line 237 reached on any byte flip |
| `nightguard_guard.ps1` | `.nightguard.lock` | `Test-LockHeld` exclusive-open probe at line 241, gating revert | WIRED | `[IO.File]::Open($LockPath, 'Open', 'ReadWrite', 'None')` at line 77; `IOException` = held |
| `nightguard_guard.ps1` | `config.sanctioned.yaml` | `[IO.File]::Copy(sanctioned, live, $true)` at line 247 | WIRED | Called only when lock free AND sanctioned HMAC valid (`Test-SanctionedValid` at line 244) |
| `nightguard_guard.ps1` | `guard.json.grace.window_end` | `$stateValid AND window_end -gt $trueNow` at line 423-424 | WIRED | `$stateValid` is the tamper gate; grace grant only when both hold |
| `nightguard_guard.ps1` | NTP true-time | `Get-GuardNtpUnixSecs` returns `$null` on any failure; `$null` → deny | WIRED | `NIGHTGUARD_TEST_NTP_OVERRIDE=1` env gate at line 383 ensures override only works in tests |
| `run_guard_gate.ps1` | `nightguard_guard.ps1` | `Invoke-Guard` spawns `powershell -File $guard -DataDir $DataDir` | WIRED | `Invoke-Guard` at lines 74-105; `-AllowOverride:$false` for GARD-06 |
| `verify_hook_integrity.ps1` | `guard.baseline.sha256` | reads on verify, writes on `-Update` | WIRED | `$manifest` at line 32; read via `[IO.File]::ReadAllLines` at line 104 |
| `verify_hook_integrity.ps1` | `scripts/interop/nightguard_interop.ps1` | registered in `$registered` array at line 43 | WIRED | CR-02 fix (commit e22ae72) added both interop scripts to the registered set |

---

### Data-Flow Trace (Level 4)

The guard is a decision-emitting script, not a rendering component. All dynamic state flows through
the single `$verdict` object emitted as JSON on stdout.

| Variable | Source | Produces Real Data | Notes |
|----------|--------|--------------------|-------|
| `$key` | DPAPI-unprotect `.guardkey` via `Unprotect-GuardKey` | Yes | 32-byte raw key; canary at line 63 |
| `$liveHmac` | `Get-FileHmacHex` over raw `config.yaml` bytes | Yes | `[IO.File]::ReadAllBytes` path |
| `$stateResult` | `Get-RuntimeStateHmac` re-derives from on-disk `guard.json` | Yes | Blank → compact → 0x0A → HMAC; returns `.Valid` + `.Tag` |
| `$trueNow` | `Get-GuardNtpUnixSecs` UDP query to `time.cloudflare.com:123` | Yes | `$null` on any failure; no local-clock fallback |
| `$verdict` | Assembled from `$decision/$reason/$graceRemaining/$reverted/$failClosed` | Yes | Emitted via `ConvertTo-Json -Compress -Depth 5` at line 461 |

---

### Behavioral Spot-Checks

Static checks only — the guard requires DPAPI, live UDP, and a running Rust process. All behavioral
verification is delegated to the human-run gates below.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Guard script parses under WinPS 5.1 | Source-grep: no bytes > 0x7F in guard | No non-ASCII in source | VERIFIED (static) |
| CR-01: override only active with env flag | `grep "NIGHTGUARD_TEST_NTP_OVERRIDE"` → 2 hits in guard; conditional at line 384 | Env-gated | VERIFIED (static) |
| CR-02: interop scripts in baseline | Baseline has 4 entries; `Get-FileHash` matches for both interop scripts | Hashes match | VERIFIED (static) |
| GARD-06 gate check present | `grep "GARD-06 override-ignored-in-prod"` in run_guard_gate.ps1 → present | Found at line 356 | VERIFIED (static) |

---

### Probe Execution

SKIPPED — all probes require DPAPI (CurrentUser), live UDP, and `cargo build`. Delegated to human
verification.

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| `scripts/guard/run_guard_gate.ps1` | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/guard/run_guard_gate.ps1` | Cannot run without DPAPI + UDP + Rust | SKIP (human required) |
| `scripts/guard/verify_hook_integrity.ps1` | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/guard/verify_hook_integrity.ps1` | Cannot verify without machine | SKIP (human required) |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| GARD-01 | 03-02, 03-03 | Config HMAC verify + auto-revert to sanctioned snapshot | SATISFIED | `Get-FileHmacHex` compare + `[IO.File]::Copy` at lines 231-247; GARD-01 gate check lines 211-228 |
| GARD-02 | 03-02, 03-03 | Sanctioned also invalid → write hardcoded strict default + log | SATISFIED | `Write-MaximalLockoutDefault` lines 165-199; `$failClosed = $true` line 255; GARD-02 check asserts maximal-lockout content |
| GARD-03 | 03-01, 03-02 | State invalid/tampered → weekly_spent=3, grace-as-used, no write | SATISFIED | `$stateValid` gate line 212; worst-case at lines 220-221; no `Write-RawBytes(guard.json)` in script; GARD-03 check lines 249-269 |
| GARD-04 | 03-03 | Honor active grace via guard's own NTP; re-lock on expiry; fail-closed offline | SATISFIED | `Get-GuardNtpUnixSecs` lines 281-306; NTP-null → deny line 401; clock-tamper → deny line 408; verdict at lines 423-432; GARD-04 gate covers honored/expired/offline |
| GARD-05 | 03-01, 03-02, 03-03 | Never revert a legitimate in-app write (circuit-breaker) | SATISFIED | `Test-LockHeld` called before any file touch at line 241; `hold-commit-lock` Rust subcommand proves cross-process lock detection; `lock_probe.rs` proves HELD/FREE semantics |
| GARD-06 | 03-04 | Guard registered in SHA256 baseline; altering/removing it raises alert | SATISFIED | 4 scripts in `guard.baseline.sha256`; `verify_hook_integrity.ps1` self-registers; CR-02 fix adds both interop scripts; GARD-06 gate asserts production-shape override is ignored |

**All 6 GARD requirements (GARD-01..06) have implementation evidence in the codebase.**

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `nightguard_guard.ps1` | 444-449 | `try { Append-AuditRecord ... } catch { }` — audit-append failure silently swallowed | Warning (WR-02) | Audit guarantee lost without notice; verdict still stands deny-leaning; not a curfew bypass |
| `nightguard_guard.ps1` | 212 | `$stateResult.Tag -eq $stateResult.Expected` — plain string compare for HMAC tag | Warning (WR-04) | Timing side-channel; minor on local script; CLAUDE.md names constant-time as a locked invariant |
| `nightguard_guard.ps1` | 424 | `[int64]$guardObj.grace.window_end` — cast without field existence check | Warning (WR-05) | If `window_end` absent in a validly-signed state, throws under `$ErrorActionPreference='Stop'`, bypassing audit append |
| `nightguard_guard.ps1` | 288-306 | SNTP reply trusted without validating mode/leap-indicator/stratum | Warning (WR-03) | An on-path attacker with a near-timestamp (within 300s skew) is fully trusted |
| `nightguard_guard.ps1` | 308-372 | Audit chain constructed but never verified on read | Warning (WR-01) | Chain is tamper-evident to a human but the guard takes no action on a broken chain |

No TBD/FIXME/XXX debt markers found in phase-modified files.

**None of the 5 warning findings constitute a goal-blocking blocker** — they are robustness/repudiation gaps documented in the code review and tracked as follow-up debt. The core curfew-bypass and integrity-bypass criticals (CR-01, CR-02) were both fixed before this verification (commits 87b1eb0, e22ae72).

---

### Human Verification Required

#### 1. Guard end-to-end gate (GARD-01..06)

**Test:** `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/guard/run_guard_gate.ps1`

**Expected:** Exit 0 with output:
```
  GARD-01 tamper->revert             PASS
  GARD-02 both-invalid->lockout      PASS
  GARD-03 state-tamper->deny         PASS
  GARD-04 grace/expired/offline      PASS
  GARD-05 lock-held->skip            PASS
  GARD-06 override-ignored-in-prod   PASS
ALL CHECKS PASSED ...
```

**Why human:** Requires real DPAPI (CurrentUser decrypt of `.guardkey`), live UDP to `time.cloudflare.com:123` for the GARD-04 offline check via `192.0.2.1`, and `cargo build` + a spawned Rust `hold-commit-lock` process for GARD-05. Cannot be executed in this static verification environment.

**Note on GARD-04 offline sub-check:** This fires a real UDP packet against `192.0.2.1` (RFC 5737 TEST-NET). The 2s socket timeout in `Get-GuardNtpUnixSecs` means the check takes at least 2 seconds. This is expected.

---

#### 2. Integrity check (GARD-06)

**Test:** `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/guard/verify_hook_integrity.ps1`

**Expected:** Exit 0 with:
```
=== Summary: PASS (4 registered scripts match baseline) ===
```

**Why human:** `Get-FileHash` result depends on the actual working-tree bytes. The static cross-check confirms the hashes match on this machine (`b2b3377d` for `nightguard_interop.ps1`, `0804982` for `state_interop.ps1`), but the developer should confirm on the canonical deployment host.

**Note on CRLF state:** `git ls-files --eol` shows `i/crlf w/crlf attr/-text` for both interop scripts. The `-text` attribute means Git does not normalize them; the baseline hashes were computed against CRLF bytes and the working-tree files are CRLF — so they match. On a clone with `core.autocrlf=false` the working-tree would also be CRLF (because the blob is CRLF and `-text` prevents normalization on checkout). This is self-consistent.

---

#### 3. State interop gate (Check 4 runtime state-verify)

**Test:** `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/interop/run_state_interop_gate.ps1`

**Expected:** Exit 0 with all 4 checks PASS, including "state_hmac RUNTIME re-derive"

**Why human:** Exercises DPAPI and the Rust `emit-state-hmac` CLI; requires the machine holding the key.

---

#### 4. Rust lock probe test

**Test:** `cargo test -p mutation-engine --test lock_probe -- --nocapture`

**Expected:** Exit 0; output confirms `HELD` while locked and `FREE` after release

**Why human:** Spawns a PowerShell subprocess inside a Rust integration test; requires Windows + PowerShell on PATH + Rust toolchain. The `cargo test` workspace-level pass reported in context is sufficient evidence if the developer can confirm it specifically includes this test.

---

### Gaps Summary

No BLOCKER gaps. All 6 GARD requirements have static code evidence in the codebase.

The two Critical security bypasses from code review (CR-01: NTP override unconditional production bypass; CR-02: interop crypto kernel outside integrity baseline) were both fixed before this verification:
- CR-01 fixed in commit `87b1eb0`: override now requires `NIGHTGUARD_TEST_NTP_OVERRIDE=1` env; `run_guard_gate.ps1` adds GARD-06 asserting the production-shape override is ignored.
- CR-02 fixed in commit `e22ae72`: both interop scripts added to `$registered` in `verify_hook_integrity.ps1`, baseline regenerated to 4 entries, `scripts/interop/*.ps1 -text` added to `.gitattributes`.

Five warning findings (WR-01..05) remain open as tracked debt. None block the phase goal:
- **WR-01** (audit chain not verified on read) — tamper-evident in principle, no active detector
- **WR-02** (audit-append failure silently swallowed) — verdict still stands deny-leaning
- **WR-03** (SNTP reply not validated for mode/LI/stratum) — 300s skew check is a coincidental downstream mitigation
- **WR-04** (plain `-eq` tag compare vs constant-time) — violates CLAUDE.md invariant; local-attacker threat model minor
- **WR-05** (unvalidated `window_end` cast can throw + skip audit) — only reachable in trusted branch with malformed-but-signed state

One structural note for the developer: the 03-04-SUMMARY claims the registered set was "nightguard_guard.ps1 + verify_hook_integrity.ps1 ONLY" — this was the state at plan-04 commit. CR-02 (commit e22ae72) later expanded it to 4 scripts. The committed `guard.baseline.sha256` and `verify_hook_integrity.ps1` reflect the CR-02 state (4 scripts), which is the correct final state.

---

_Verified: 2026-06-08T17:00:00Z_
_Verifier: Claude (gsd-verifier)_
