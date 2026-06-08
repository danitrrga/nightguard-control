# SECURITY.md — Phase 03 Enforcement Guard

**Audited:** 2026-06-08
**ASVS Level:** 2
**block_on:** high
**Disposition model:** register authored at plan time — VERIFY mode (no new-threat scan).

Threat actor per project note: the legitimate host user/admin (the "late-night impulsive self")
who reads the scripts. "The host won't pass that argument" is NOT a valid defense. Absolute
unbreakability against repo-write is explicitly out of scope (T-03-18).

---

## Verdict: SECURED — threats_open: 0

All 18 threats CLOSED (15 mitigate verified present, 3 accept documented). The original audit
(2026-06-08 17:53) found T-03-13 OPEN — the audit-chain detection half was absent. That gap was
closed the same session: a `Verify-AuditChain` detector + `GARD-07` tamper-detection gate were
implemented and verified live (commits `32237f4`, `c985a20`). See the Audit Trail at the bottom.

---

## Threat Verification Table

| Threat ID | Category | Disp. | Status | Evidence (file:line) |
|-----------|----------|-------|--------|----------------------|
| T-03-01 | Spoofing | mitigate | CLOSED | nightguard_guard.ps1:114-128 (blank state_hmac, `ConvertTo-Json -Compress -Depth 10`, append 0x0A, HMAC); :212 `$stateValid = Tag -eq Expected`. Cross-checked equal to Rust `compute_state_hmac` via run_state_interop_gate.ps1:179-202 (Check 4 runtime re-derive) + state_interop_cli.rs:113,151. |
| T-03-02 | Tampering (TOCTOU) | mitigate | CLOSED | nightguard_guard.ps1:70-83 `Test-LockHeld` exclusive-open -> IOException == held; driven by live Rust `with_commit_lock` holder, run_guard_gate.ps1:299-341 GARD-05 (held->reverted=false; released->reverted=true). state_interop_cli.rs:173-201 real `LockFileEx`. |
| T-03-03 | Repudiation | accept | CLOSED | Accepted: correctness guard, not security. Scripts are ASCII-only (headers nightguard_guard.ps1:22-23; verify_hook_integrity.ps1:21-22). Documented as accept in register. |
| T-03-04 | Tampering | mitigate | CLOSED | nightguard_guard.ps1:229-249 `Get-FileHmacHex(config) != config_hmac` -> `File.Copy(sanctioned,live)` revert; GARD-01 run_guard_gate.ps1:210-228 proves byte-restore + reverted=true. |
| T-03-05 | Tampering (TOCTOU) | mitigate | CLOSED | nightguard_guard.ps1:241-243 `Test-LockHeld` checked BEFORE the revert branch; skips when held. GARD-05 run_guard_gate.ps1:320-325. |
| T-03-06 | Spoofing | mitigate | CLOSED | nightguard_guard.ps1:210-222 state mismatch -> `weeklySpent=3`, `graceUsed=true`, NO write; :227 `$configHmacTrusted` gates revert on `$stateValid` so a forged guard.json cannot steer the revert target. GARD-03 run_guard_gate.ps1:249-269 (tampered state inside active window -> deny). |
| T-03-07 | Tampering/DoS | mitigate | CLOSED | nightguard_guard.ps1:165-199 `Write-MaximalLockoutDefault` (24/7 curfew, block_when_offline, zero allow_commands); :250-256 both-invalid branch sets fail_closed. GARD-02 run_guard_gate.ps1:230-247. |
| T-03-08 | Elevation | mitigate | CLOSED | Guard NEVER re-signs: revert = `File.Copy` byte copy (:247); lockout = hardcoded literal (:165-199); state mismatch substitutes runtime `$weeklySpent`/`$graceUsed` only (:217-222), never writes guard.json. No HMAC sign call anywhere in guard. |
| T-03-09 | Tampering (EOL) | mitigate | CLOSED | All HMAC inputs via `Get-FileBytes` = `[IO.File]::ReadAllBytes` (nightguard_interop.ps1:45-50); config writes via `Write-RawBytes` = `WriteAllBytes` (:52-60); lockout uses LF-join + `UTF8.GetBytes` (nightguard_guard.ps1:196-198); audit via `AppendAllText` UTF8-no-BOM (:369-371). No Get-Content/Set-Content on any hashed/written path. |
| T-03-10 | Spoofing | mitigate | CLOSED | nightguard_guard.ps1:61-65 `if ($key.Length -ne 32) { throw }` 32-not-64 canary on unwrapped DPAPI key; Unprotect via raw `ProtectedData` CurrentUser/$null entropy (nightguard_interop.ps1:36-43), no SecureString. |
| T-03-11 | Tampering (clock) | mitigate | CLOSED | nightguard_guard.ps1:408-415 `Abs(trueNow - local) > 300 -> deny + fail_closed`; verdict uses guard-side SNTP `$trueNow` (:281-306). **CR-01 verified:** override gated behind `$env:NIGHTGUARD_TEST_NTP_OVERRIDE -eq '1'` (:383-384); production path cannot be steered. GARD-06 run_guard_gate.ps1:343-360 proves a production-shaped override is ignored -> deny+fail_closed. |
| T-03-12 | Tampering (isolation) | mitigate | CLOSED | nightguard_guard.ps1:281-306 SNTP re-queried every fire; any exception -> `$null` (:301-302); :401-407 `$null -eq $trueNow -> deny + fail_closed`, never honors last-known (no Get-Date fallback). GARD-04 offline path run_guard_gate.ps1:287-290 (unroutable server -> deny+fail_closed). |
| T-03-13 | Repudiation | mitigate | **CLOSED** | Chain CONSTRUCTED (`Append-AuditRecord` :315-372, genesis :273) AND now VERIFIED: `Verify-AuditChain` recomputes the chain from genesis each fire before append; on break it sets `audit_chain_broken=true` + `audit_chain_break_index` in the verdict JSON and emits a `chain-broken` record forward, without altering the curfew decision. Proven by GARD-07 (run_guard_gate.ps1): one-byte tamper of guard-audit.log -> `broken=True(idx=0) verdictUnchanged=True chainBrokenRecord=True appendedForward=True`. Verified live, gate exit 0. Commits 32237f4, c985a20. (Closes WR-01.) |
| T-03-14 | Info disclosure | accept | CLOSED | Accepted: verdict JSON carries only `decision/reason/grace_remaining_secs/reverted/fail_closed` (nightguard_guard.ps1:454-461) — no key/state bytes. Verified against the actual emitted object. |
| T-03-15 | Spoofing | mitigate | CLOSED | nightguard_guard.ps1:423 grace-honor branch gated on `$stateValid -and ... grace.window_end > trueNow`; worst-case (`$stateValid=false`) can never reach allow (:428 else -> deny). GARD-03 proves tampered state inside an active window denies. |
| T-03-16 | Tampering | mitigate | CLOSED | verify_hook_integrity.ps1:40-45 registers `nightguard_guard.ps1`; :120-132 drift/missing -> FAIL -> exit 1 (:148-151). Baseline hash guard.baseline.sha256:1 matches on-disk SHA256 (recomputed, identical). |
| T-03-17 | Tampering | mitigate | CLOSED | verify_hook_integrity.ps1 self-registers (:41 line 2 of `$registered`); editing it changes its own hash -> baseline FAIL. Baseline guard.baseline.sha256:2 matches on-disk. |
| T-03-18 | Repudiation | accept | CLOSED | Accepted per REQUIREMENTS: committed in-repo baseline + `-Update` rebaseline out of scope. Documented in 03-04-SUMMARY.md:111 and register. |

---

## CR Fix Verification (strengthen T-03-11/12 and T-03-16/17)

- **CR-01 (T-03-11/12):** CONFIRMED. The `-NtpOverrideUnixSecs` seam is gated behind
  `$env:NIGHTGUARD_TEST_NTP_OVERRIDE -eq '1'` (nightguard_guard.ps1:383-389). Without the env
  flag a passed override is ignored and the real SNTP + clock-tamper path runs. GARD-06
  (run_guard_gate.ps1:343-360) fires a production-shaped override with the flag ABSENT against an
  unroutable SNTP server and asserts `decision != allow` and `fail_closed = true`. The production
  path cannot be steered by the override.

- **CR-02 (T-03-16/17):** CONFIRMED. The baseline registers ALL 4 scripts including the interop
  crypto kernel: nightguard_guard.ps1, verify_hook_integrity.ps1, nightguard_interop.ps1,
  state_interop.ps1 (verify_hook_integrity.ps1:40-45; guard.baseline.sha256:1-4, all 4 hashes
  recomputed and matching on disk). `.gitattributes` pins both `scripts/guard/*.ps1 -text` and
  `scripts/interop/*.ps1 -text`. The earlier "interop scripts remain CRLF" observation is a
  pre-fix snapshot; current on-disk bytes are LF-only (0 CR bytes; `git check-attr text` = unset
  via `-text`), and the baseline hashes match those LF bytes. The interop kernel is now inside the
  trust surface.

---

## Unregistered Flags

None. No `## Threat Flags` section emitted by the executor; 03-04-SUMMARY.md `## Threat Model
Coverage` only restates registered threats T-03-16/17/18. No new attack surface mapping required.

---

## Open Threats

None. threats_open: 0.

T-03-13 (the only finding from the initial audit) was resolved by implementing the detector
rather than re-dispositioning — see Audit Trail.

---

## Tracked Debt (WARNINGS — not part of the STRIDE register)

WR-02..WR-05 from 03-REVIEW.md remain open follow-up debt. Assessed against the register:

- **WR-02** (silent audit-append failure) — touches the same T-03-13 repudiation surface.
  T-03-13's detection half now ships, but WR-02 (the empty `catch {}` around the append) is a
  distinct hardening item still open as tracked debt.
- **WR-03** (SNTP reply unvalidated: mode/LI/stratum) — within the 300s skew tolerance an on-path
  attacker is trusted. Does NOT currently produce an `allow` past the clock-tamper wall, so it
  does not open a `mitigate` threat; tracked debt.
- **WR-04** (`-eq` not constant-time for tag compare) — violates a CLAUDE.md locked invariant but
  local-attacker timing leak is negligible; no register threat opened. Document waiver or fix.
- **WR-05** (`[int64]grace.window_end` unguarded cast can throw, skipping JSON+audit) — reachable
  only with a validly-SIGNED malformed field; deny-on-exit still holds (fail-closed), so no
  permissive bypass. Intersects T-03-13 (skips audit append). Tracked debt.

None of WR-02..05 independently opens a `mitigate` threat to OPEN; only T-03-13 does.

---

## Audit Trail

### Security Audit 2026-06-08 (initial)
| Metric | Count |
|--------|-------|
| Threats in register | 18 |
| Closed | 17 |
| Open | 1 (T-03-13, BLOCKER) |

Register authored at plan time (VERIFY mode). Both prior code-review Criticals (CR-01 NTP-override
bypass, CR-02 unbaselined interop kernel) re-confirmed genuinely fixed. T-03-13 found OPEN: audit
HMAC chain constructed but never verified on read.

### Resolution 2026-06-08 (same session) — user chose "implement the verifier"
| Metric | Count |
|--------|-------|
| Threats in register | 18 |
| Closed | 18 |
| Open | 0 |

- `Verify-AuditChain` added to `scripts/guard/nightguard_guard.ps1` — recomputes the chain from the
  genesis tag each fire before `Append-AuditRecord`. Absent log = Ok (genesis); present-but-garbled
  or non-rederiving = break. On break: `audit_chain_broken=true` + `audit_chain_break_index` in the
  verdict JSON, plus a `chain-broken` record appended forward. Curfew decision never changed
  (repudiation control, not a curfew gate). Verifier exception treated as a break (fail-evident).
- `GARD-07 audit-chain-tamper-detected` added to `scripts/guard/run_guard_gate.ps1`.
- `scripts/guard/guard.baseline.sha256` regenerated (guard hash moved; other 3 unchanged).
- **Live verification (this Windows host, WinPS 5.1):** `run_guard_gate.ps1` exit 0, GARD-01..07 all
  PASS (GARD-07: `clean=True broken=True(idx=0) verdictUnchanged=True chainBrokenRecord=True
  appendedForward=True`); `verify_hook_integrity.ps1` exit 0, 4 scripts match regenerated baseline.
- Commits: `32237f4` (feat: verifier + gate), `c985a20` (chore: regenerate baseline).

**Final disposition: SECURED — threats_open: 0.** WR-02..WR-05 remain tracked non-blocking debt
in `03-REVIEW.md` (none open a `mitigate` threat).
