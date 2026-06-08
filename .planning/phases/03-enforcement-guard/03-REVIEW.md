---
phase: 03-enforcement-guard
reviewed: 2026-06-08T14:30:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - scripts/guard/nightguard_guard.ps1
  - scripts/guard/run_guard_gate.ps1
  - scripts/guard/verify_hook_integrity.ps1
  - scripts/interop/run_state_interop_gate.ps1
  - scripts/guard/guard.baseline.sha256
  - crates/mutation-engine/src/bin/state_interop_cli.rs
  - crates/mutation-engine/tests/lock_probe.rs
  - .gitattributes
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
criticals_resolved: 2
criticals_resolved_in: [87b1eb0, e22ae72]
warnings_open: 5
---

> **Update 2026-06-08:** Both Critical findings (CR-01 NTP-override bypass, CR-02
> unbaselined interop crypto kernel) were fixed and verified — commits `87b1eb0`,
> `e22ae72`. Gate now exits 0 with GARD-01..06 PASS; integrity check covers all 4
> guard/interop scripts. The 5 Warning findings (WR-01..05) remain open as tracked
> follow-up debt.

# Phase 3: Enforcement Guard - Code Review Report

**Reviewed:** 2026-06-08T14:30:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the Phase 3 enforcement guard against the locked decisions (D-01..D-10), the
Rust interop contracts (`state.rs` A3 recipe, `canon.rs`, `grace.rs`), and the
fail-closed/anti-me threat model. The core integrity machinery is well built: the
state-verify -> config-trust gating (`$configHmacTrusted`) correctly closes the
forged-guard.json-steers-revert hole, the circuit-breaker probe is proven against a live
Rust lock holder, the A3 state_hmac re-derivation matches the Rust recipe byte-for-byte,
and the maximal-lockout literal is genuinely the most-restrictive config. The documented
deviations (gate self-signs guard.json; `$stateValid` gates the grace allow instead of the
self-contradictory `-not $graceUsed`; `hold-commit-lock` subcommand) are sound and not
flagged as bugs.

Two findings, however, undermine the load-bearing "anti-me" guarantee:

1. **`-NtpOverrideUnixSecs` is an unconditional production parameter that bypasses both SNTP
   and clock-tamper detection** — any invoker can inject true-time and force an `allow`.
2. **The dot-sourced interop scripts that hold the actual DPAPI/HMAC primitives are neither
   in the SHA256 integrity baseline nor pinned `-text`** — tampering them subverts the guard
   entirely while GARD-06 stays green and an autocrlf checkout can silently break parity.

Both are below the guard's headline behaviors but sit directly on the trust path. The
remaining findings are robustness/repudiation gaps and clarity issues.

A live-PowerShell check confirmed the SNTP `[uint32] -shl` parsing does NOT overflow on
WinPS 5.1 (UInt32 is preserved; `secs=3949628160`), so that path is correct as written.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: `-NtpOverrideUnixSecs` test seam ships in production and bypasses SNTP + clock-tamper

**File:** `scripts/guard/nightguard_guard.ps1:30-33, 379-394, 403`
**Issue:** The guard exposes `-NtpOverrideUnixSecs` as a first-class, always-available CLI
parameter. When `>= 0`, it sets `$trueNow` directly, sets `$usedOverride = $true`, and the
clock-tamper branch at line 403 (`(-not $usedOverride) -and ...`) is *skipped entirely*. So
any process that can invoke the guard can do:

```
powershell -File nightguard_guard.ps1 -DataDir <dir> -NtpOverrideUnixSecs 9999999999
```

and obtain `decision=allow` for any signed-but-expired grace window, with no SNTP query and
no skew check — defeating GARD-04, D-07 (offline -> deny), and the Pitfall-5 clock-tamper
defense in one argument. The whole point of "guard's OWN NTP, tamper-checked first" is that
the impulsive user cannot supply the time. This seam hands them exactly that lever. The
`NIGHTGUARD_NTP_SERVER` env seam (line 388) has the same shape but is lower-risk (it can only
force *deny* via an unroutable address); the override forces *allow*.

In the anti-me model the user controls how the host fires the guard, so "the host won't pass
it" is not a defense — the guarantee must hold against the user who reads this script.

**Why it matters:** Direct, trivial bypass of the curfew/grace verdict — the central
self-binding guarantee. A grace window that was legitimately signed days ago (and is long
expired) becomes re-honorable; even with no window, the seam removes the clock-tamper wall
that protects every future verdict.

**Fix:** Gate the override behind a test-only signal that production invocation cannot carry,
or remove it from the shipped script. Concretely, require an explicit opt-in env the host
never sets and that the gate sets only in tests, e.g.:

```powershell
$overrideAllowed = ($env:NIGHTGUARD_TEST_NTP_OVERRIDE -eq '1')
if (($NtpOverrideUnixSecs -ge 0) -and $overrideAllowed) {
    $trueNow = [int64]$NtpOverrideUnixSecs
    $usedOverride = $true
} else {
    # ... real SNTP path; ignore the override entirely in production ...
}
```

and have `run_guard_gate.ps1` set `NIGHTGUARD_TEST_NTP_OVERRIDE=1` around its `Invoke-Guard`
calls. Even better: keep the override but DO NOT skip the clock-tamper check under it — but
since the seam's purpose is clock-independence, env-gating is the correct fix. Document the
seam as test-only and assert in the gate that, without the env flag set, the override is
ignored.

### CR-02: Dot-sourced interop scripts are outside the integrity baseline AND unprotected from autocrlf

**File:** `scripts/guard/guard.baseline.sha256:1-2`, `.gitattributes:1-9`,
`scripts/guard/nightguard_guard.ps1:39-40`
**Issue:** `nightguard_guard.ps1` dot-sources `..\interop\nightguard_interop.ps1` and
`..\interop\state_interop.ps1` for every cryptographic primitive it uses
(`Unprotect-GuardKey`, `Get-FileHmacHex`, `Get-FileBytes`, `Write-RawBytes`,
`ConvertTo-LowerHex`). Those two scripts are the real trust surface — yet:

- The SHA256 baseline (`guard.baseline.sha256`) registers ONLY
  `scripts/guard/nightguard_guard.ps1` and `scripts/guard/verify_hook_integrity.ps1`. The
  interop scripts are not baselined.
- `.gitattributes` pins `scripts/guard/*.ps1 -text` but NOT `scripts/interop/*.ps1`
  (confirmed: `git check-attr text scripts/interop/nightguard_interop.ps1` -> `text:
  unspecified`).

Consequences, both real:

1. **Integrity bypass (worse than T-03-16):** an attacker who edits
   `Unprotect-GuardKey` to return an attacker-chosen 32-byte key, or `Get-FileHmacHex` to
   return whatever tag makes config verification pass, completely neuters the guard — and
   `verify_hook_integrity.ps1` reports PASS, because those files are not in the registered
   set. The guard self-protects but leaves its own dependencies undefended. This is a more
   direct attack than replacing `nightguard_guard.ps1` (which GARD-06 *does* catch).
2. **Silent parity break:** with `core.autocrlf=true` (set in this repo per 03-04-SUMMARY),
   a fresh clone checks the interop scripts out as CRLF. That does not break HMAC parity by
   itself (they are scripts, not signed inputs), but it is inconsistent with the deliberate
   `-text` hardening applied to the guard for exactly this reason, and any future
   here-string / byte literal in those files would drift.

**Why it matters:** GARD-06 / D-10 exist to close "silently replace the enforcement
mechanism." Leaving the dot-sourced crypto kernel out of the baseline is a hole in precisely
that guarantee — the integrity check gives false assurance.

**Fix:** Add both interop scripts to the registered set in `verify_hook_integrity.ps1`,
regenerate `guard.baseline.sha256` via `-Update`, and extend `.gitattributes`:

```powershell
# verify_hook_integrity.ps1
$registered = @(
    'scripts/guard/nightguard_guard.ps1',
    'scripts/guard/verify_hook_integrity.ps1',
    'scripts/interop/nightguard_interop.ps1',
    'scripts/interop/state_interop.ps1'
)
```

```gitattributes
# .gitattributes
scripts/interop/*.ps1 -text
```

If a deliberate decision was made to scope the baseline narrowly, record it explicitly with
the threat-model rationale; as it stands the dependency chain is unguarded.

## Warnings

### WR-01: Audit chain is constructed but never verified — tamper-evidence is not actually enforced

**File:** `scripts/guard/nightguard_guard.ps1:308-372`
**Issue:** `Append-AuditRecord` correctly chains `record_tag = HMAC(key, prevTag || payload)`
off the genesis constant (D-08). But nothing in the guard (or any reviewed script) ever
*verifies* the chain on read. On each fire the guard reads only the last line's tag to
continue chaining (lines 338-354); a deletion/edit/truncation simply makes the next record
chain off the new last tag with no alarm. D-08's promised property — "any
deletion/edit/truncation is detectable on the next run" — is *verifiable in principle* but
unimplemented: there is no detector, no exit signal, no audit-log entry recording a broken
chain.

**Why it matters:** The repudiation defense (T-03 "delete/edit/truncate the audit log to
hide events") is only as good as a verifier that runs. Right now the log is tamper-*evident*
to a human who recomputes the chain by hand, but the guard takes no action and raises no
flag, so in practice tampering is silent.

**Fix:** Add a chain-verification pass (in the guard's audit step, or in
`verify_hook_integrity.ps1`, or a dedicated `verify-audit` mode) that recomputes every
record's tag from genesis forward and raises a non-zero alert / emits a `chain-broken` audit
record on the first mismatch. If full verification each fire is too costly, at minimum record
the previous record's tag in a side-channel (e.g., the signed state) so truncation-to-empty
is detectable. Document if deferred.

### WR-02: Audit-append failure is silently swallowed, permanently disabling the repudiation log

**File:** `scripts/guard/nightguard_guard.ps1:439-444`
**Issue:** The `try { Append-AuditRecord ... } catch { }` swallows every append failure with
an empty catch and proceeds. The intent (don't crash into a permissive state) is right, but
an attacker who makes `guard-audit.log` unwritable (read-only attribute, ACL deny, parent
dir locked) suppresses ALL future audit records with zero signal — the guard keeps emitting
verdicts as if logging succeeded. For a log whose entire purpose is tamper-evidence, silent
permanent suppression is a meaningful gap.

**Why it matters:** Repudiation control silently defeated. The verdict still stands
(deny-leaning), so it is not a *permissive* bypass, but the audit guarantee is lost without
notice.

**Fix:** Keep the guard alive, but surface the failure: include an `audit_error` flag in the
emitted verdict JSON, and/or write a sentinel/stderr diagnostic the host can alert on. At
minimum do not discard the exception text:

```powershell
} catch {
    $verdict | Add-Member -NotePropertyName audit_error -NotePropertyValue "$_" -Force
}
```

### WR-03: SNTP response is trusted without validating mode / leap-indicator / stratum

**File:** `scripts/guard/nightguard_guard.ps1:288-306`
**Issue:** `Get-GuardNtpUnixSecs` sends a client packet and reads bytes 40-43 of whatever
comes back, with no validation that the reply is a server response (mode 4), that the leap
indicator is not 3 (`11` = unsynchronized / alarm), or that stratum is non-zero (stratum 0 =
"kiss-of-death", transmit timestamp may be 0). A reply with transmit timestamp 0 yields
`$trueNow = -2208988800`. That specific case is caught downstream by the clock-tamper skew
check (|trueNow - local| >> 300 -> deny), so it is not currently exploitable into an
*allow*. But the guard is relying on a coincidental downstream check rather than rejecting a
malformed/unsynchronized NTP reply at the source, and an on-path attacker who returns a
plausibly-near-but-wrong timestamp (within 300s) is fully trusted.

**Why it matters:** The guard's OWN NTP is the root of the grace verdict's trust. Accepting
an unvalidated datagram weakens that root; the only thing standing between a spoofed reply
and a widened window is the 300s skew tolerance.

**Fix:** Validate the reply before using it: require `($packet[0] -band 0xC0) -ne 0xC0` (LI
!= 3), `($packet[0] -band 0x07)` mode == 4, and `$packet[1] -ne 0` (stratum != 0); treat any
failure as `$null` (fail-closed deny), exactly like a timeout. Optionally cross-check the
transmit timestamp against the local clock with a tighter bound when available.

### WR-04: `Get-RuntimeStateHmac` does not constant-time-compare the state_hmac tag

**File:** `scripts/guard/nightguard_guard.ps1:212`
**Issue:** State validity is decided by `($stateResult.Tag -eq $stateResult.Expected)`, a
plain ordinal string compare, and config validity by `$liveHmac -eq [string]$guardObj.config_hmac`
(line 234). CLAUDE.md and the research explicitly call for constant-time / `verify_slice`-style
tag comparison ("`==` to compare HMAC tags -> timing side-channel ... use `verify_slice()`").
The Rust side honors this; the PowerShell guard reverts to `-eq`.

**Why it matters:** Listed as a locked invariant ("constant-time intent — locked both
languages"). The practical timing leak here is minor (local script, attacker already on the
box), which is why this is a Warning not a Blocker — but it is a stated invariant the guard
violates, and the existing `nightguard_interop.ps1` never provided a constant-time compare
helper to reuse.

**Fix:** Add a constant-time hex-string comparison helper to `nightguard_interop.ps1` (XOR
each byte of equal-length decoded tags, accumulate, compare to zero in fixed time) and use it
for both the state_hmac and config_hmac comparisons. If the project accepts the local-attacker
threat model and waives constant-time for the guard, document that waiver against the CLAUDE.md
invariant so it is a recorded decision rather than a silent drift.

### WR-05: `[int64]$guardObj.grace.window_end` casts unvalidated JSON and can throw inside the trusted branch

**File:** `scripts/guard/nightguard_guard.ps1:418-422`
**Issue:** Inside the grace-honor branch the guard does `[int64]$guardObj.grace.window_end`
without verifying the field exists or is numeric. The branch is gated on `$stateValid`, so a
*tampered* guard.json cannot reach here — but a structurally-odd-yet-validly-signed state
(e.g., `grace` present but `window_end` absent, or a non-numeric value that nonetheless
hashed into a valid tag because the app once wrote it) would throw a terminating error under
`$ErrorActionPreference='Stop'`. There is no try/catch around the verdict computation, so an
exception here propagates to an uncaught PowerShell error: the guard exits non-zero WITHOUT
emitting the verdict JSON and WITHOUT appending an audit record. Exit-non-zero is deny
(fail-closed for the host that reads the exit code), but a host that parses JSON gets nothing,
and the audit trail is silently skipped.

**Why it matters:** A single malformed-but-signed field turns a clean deny into a crash that
bypasses the audit append (WR-02 territory) and the JSON contract (D-02). Defensive parsing
(V5) is required to be uniform — config/state parse is defended, the verdict read is not.

**Fix:** Validate `grace.window_end` is present and numeric before the comparison, treating
absent/non-numeric as "no honorable window" (deny):

```powershell
$we = $null
if ($stateValid -and ($null -ne $guardObj) -and ($null -ne $guardObj.grace)) {
    [int64]$tmp = 0
    if ([int64]::TryParse([string]$guardObj.grace.window_end, [ref]$tmp)) { $we = $tmp }
}
if ($null -ne $we -and $we -gt $trueNow) { $decision = 'allow'; ... } else { $decision = 'deny'; ... }
```

Alternatively wrap the verdict block in try/catch that falls to deny + still appends audit.

## Info

### IN-01: `$weeklySpent` is computed and worst-cased but never affects the emitted verdict

**File:** `scripts/guard/nightguard_guard.ps1:204, 215, 220, 438`
**Issue:** `$weeklySpent` is defaulted to 3, conditionally overwritten from the trusted state,
and worst-cased to 3 on tamper — but it appears nowhere in the verdict logic; it only lands in
the audit detail string indirectly (it is not even in `$auditDetail`). The clock-half verdict
keys solely on `$stateValid` + grace presence + `window_end`. If weekly-token state is meant
to influence the guard's verdict, that wiring is missing; if (per the architecture map) token
accounting is an app-only concern and the guard never gates on it, the variable is dead in
this script.

**Why it matters:** Reads as half-wired logic; a future reader may assume `weekly_spent`
gates something it does not. Either wire it or drop it.

**Fix:** Remove `$weeklySpent`/`$graceUsed` from the guard if they are app-only concerns, or
add them to `$auditDetail` and document that they are observational. (Note `$graceUsed` is
likewise unused in the final verdict after the 03-03 `$stateValid` fix.)

### IN-02: Grace `window_start` is never checked — a not-yet-started window would be honored

**File:** `scripts/guard/nightguard_guard.ps1:418-419`
**Issue:** The honor condition is only `window_end > trueNow`; `window_start <= trueNow` is
not asserted. With the Rust `use_grace` writing `window_start = now` this is not currently
reachable (no future-start window is ever signed), so it is informational, not a bug. But the
guard is trusting an invariant of the writer rather than enforcing the window's lower bound
itself.

**Fix:** For defense-in-depth, also require `[int64]$guardObj.grace.window_start -le $trueNow`
(after the WR-05 numeric validation) so the guard honors only a window that has actually begun.

### IN-03: Audit timestamp hardcodes a `Z` suffix on a value that may not be UTC-formatted as claimed

**File:** `scripts/guard/nightguard_guard.ps1:434`
**Issue:** `...UtcDateTime.ToString('yyyy-MM-ddTHH:mm:ssZ')` — the trailing `Z` here is a
literal character in the format string, not a timezone designator (`.ToString` does not
interpret `Z` as UTC). It happens to be correct because `.UtcDateTime` is UTC, but relying on
a literal `Z` is fragile and obscures intent. The value is sound; the construction is a
foot-gun.

**Fix:** Use a round-trippable, unambiguous format, e.g. `.ToString("yyyy-MM-ddTHH:mm:ss'Z'")`
(explicitly quoted literal) or `.ToUniversalTime().ToString("o")`, to make the UTC intent
explicit.

### IN-04: `Test-LockHeld` opens with `ReadWrite` access — a sharing-violation source unrelated to the app lock could read as "held"

**File:** `scripts/guard/nightguard_guard.ps1:76-82`
**Issue:** The probe opens with `'ReadWrite', 'None'` and treats ANY `IOException` as "lock
held -> skip revert." If some unrelated process (AV scanner, backup agent, indexer) transiently
holds the `.nightguard.lock` file open, the probe reports held and the guard skips a
legitimate revert that cycle. This biases toward NOT reverting (the next fire re-checks, so
it is self-healing and fail-*safe* for the race it targets), so it is Info, not a bug — but a
persistent unrelated holder could stall reverts indefinitely.

**Fix:** Acceptable as-is given the self-healing re-check, but consider narrowing to a
read-share probe or logging when the breaker trips so a stuck breaker is observable. The
proven spike (`lock_probe.rs`) validates the happy path; an unrelated-holder case is untested.

---

_Reviewed: 2026-06-08T14:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
