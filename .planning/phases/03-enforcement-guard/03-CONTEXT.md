# Phase 3: Enforcement Guard - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

The always-firing PowerShell guard that makes the Phase 1–2 binding real. Rust is the
sole writer/signer; **this guard is the reader/enforcer**, fired by the host on
SessionStart + UserPromptSubmit. It delivers six behaviors (GARD-01..06):

1. Verify the config HMAC and **auto-revert** the live `config.yaml` to the sanctioned
   snapshot on any mismatch (direction-agnostic).
2. **Fail closed** to a hardcoded strict default when the sanctioned snapshot is also
   invalid (no brick), logging the event.
3. Treat tampered signed state as worst-case (`weekly_spent=3`, grace-as-used) until an
   in-app DPAPI-gated repair re-syncs.
4. A **curfew/grace verdict** re-checked against the guard's OWN NTP (tamper-checked
   first), re-locking after the grace window expires.
5. **Never revert a legitimate in-app write** (atomic ordering + single-writer lock +
   revert circuit-breaker close the sign-vs-write race).
6. Register the guard in `verify_hook_integrity.ps1`'s SHA256 baseline so
   altering/removing it raises an alert.

**Platform:** Windows PowerShell 5.1 host-agnostic (ASCII-only, no SecureString framing,
no `Get-Content` for byte reads) — this machine runs WinPS 5.1, not pwsh 7.

**Out of scope:** the Tauri/TS app UI (Phase 4, incl. the repair-flow UI surface) and the
actual host wiring that points a real hook at the canonical config (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Curfew-gate enforcement boundary (GARD-04)
- **D-01:** The guard is a **pure verified-state oracle**, not the enforcer. On each fire
  it (a) unconditionally performs the config integrity-check + auto-revert, then (b) emits
  a curfew/grace **verdict**. The host decides what to do with a deny. Keeps this
  publishable repo host-agnostic; the teeth are a thin host adapter (Phase 5 / personal
  LifeOS instance maps `deny → block`).
- **D-02:** **Output contract:** exit code + JSON on stdout. `exit 0 = allow`, non-zero =
  deny. JSON object shape: `{decision, reason, grace_remaining_secs, reverted, fail_closed}`.
  A host can rely on the exit code alone OR parse the JSON for richer state. (Deliberately
  NOT the Claude-Code-native `{continue,decision,reason}` schema — that would couple the
  guard to the CC hook protocol against the host-agnostic decision.)

### Fail-closed strict default (GARD-02)
- **D-03:** When BOTH live and sanctioned config are invalid, write a hardcoded
  **maximal-lockout** default: curfew always-on (24/7), no grace available, zero tokens.
  The worst case is maximally restrictive, never permissive — corrupting both files buys
  the impulsive version nothing. Forces an in-app repair to restore a real config. Logged.

### State-tamper repair semantics (GARD-03)
- **D-04:** When signed state is invalid/tampered, the guard runtime-treats it as
  `weekly_spent=3` + grace-used (fail-closed) until re-sync.
- **D-05:** The DPAPI-gated in-app repair **blesses the worst-case for the current week**:
  it re-signs `weekly_spent=3` + grace-used for the current `week_anchor`, making state
  valid again but forfeiting the rest of the week (natural Monday reset restores tokens).
  **Tampering state is pure loss, never a gain.** The DPAPI gate only proves the actor is
  the real user (holds the key) — it is NOT a loosening lever. Explicitly rejected: clean
  slate (`weekly_spent=0`) and "re-sign current on-disk values" — both are anti-me escape
  hatches.

### Revert circuit-breaker (GARD-05)
- **D-06:** On a config HMAC mismatch, before reverting the guard checks the existing
  **fd-lock presence** at `<data_dir>/.nightguard.lock`. If the app holds it (a commit is
  in progress), the guard **skips the revert this cycle** — Phase 2's live-written-LAST
  ordering guarantees consistency moments later, and the next hook fire re-checks. Reuses
  the lock primitive already established in Phase 2; no new schema. (No fixed-delay retry as
  primary — the lock is the real signal, not a guessed sleep.)

### NTP-offline gate behavior (GARD-04 edge)
- **D-07:** If NTP is unreachable when the gate fires, **fail closed: deny grace, treat as
  curfew** (`decision=deny`, `fail_closed=true`). No verifiable true time ⇒ the grace
  window cannot be trusted. Consistent with Phase 2 `use_grace` already refusing on
  `NtpUnreachable` and CLAUDE.md `block_when_offline`. Config auto-revert still runs (it
  needs no clock). Explicitly rejected: honoring last-known `window_end` from guard.json
  without re-checking (a network-isolation trick could hold a window open).

### Audit log (GARD-01/02/03)
- **D-08:** **Append-only, HMAC-chained** log at `<data_dir>/guard-audit.log`. One record
  per event (ISO-8601 true-time where available + event type + detail), each record chained
  with HMAC so any deletion/edit/truncation is detectable on the next run. Tamper-evidence
  fits the self-binding threat model. (Plain log and Windows Event Log rejected — the former
  is silently editable, the latter is host-specific and hard to assert in repo tests.)

### Path configuration (Phase 5 wires the real values)
- **D-09:** The guard takes a **single base directory** — `--data-dir` arg (or
  `NIGHTGUARD_DIR` env) — and uses **fixed filenames within it** for every artifact
  (`config.yaml`, the sanctioned snapshot, `guard.json`, `.nightguard.lock`, the DPAPI key
  blob, `guard-audit.log`). One thing for Phase 5 to set; trivially point at a scratch dir
  in tests. (Per-file args rejected — more misconfiguration surface.)

### Integrity baseline (GARD-06)
- **D-10:** **Ship the integrity mechanism in-repo.** Phase 3 creates/extends
  `verify_hook_integrity.ps1`: it records the SHA256 of the guard script(s) in a baseline
  file and alerts on drift; the guard self-registers in that baseline. The repo stays
  self-contained and publishable, and GARD-06's acceptance criterion is verifiable inside
  this repo (not deferred to the personal host).

### Claude's Discretion
- Exact JSON field encodings/casing for the verdict object, log record delimiter/escaping,
  HMAC-chain construction details (e.g., prev-tag-in-next-record), and the precise
  fixed filenames — provided they honor the decisions above and the locked interop
  invariants. The researcher/planner choose the concrete forms.
- Whether the integrity baseline file is JSON or a flat `sha256  path` manifest.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked interop contract (Rust ↔ PowerShell parity — MUST mirror exactly)
- `crates/mutation-engine/src/state.rs` — `GuardState` / `LedgerEntry` / `GraceWindow`
  serde model (LOCKED field names) + the `state_hmac` **A3 recipe** the guard MUST
  re-derive identically (blank `state_hmac` → JSON → `canonicalize_bytes` → `sign_bytes` →
  `tag_to_hex`).
- `scripts/interop/nightguard_interop.ps1` — the PS half of the DPAPI+HMAC kernel:
  `Protect/Unprotect-GuardKey` (CurrentUser, `$null` entropy, raw blob, 32-not-64 canary),
  `Get-FileBytes` (raw `[IO.File]::ReadAllBytes`, never `Get-Content`), `Get-FileHmacHex`,
  `ConvertTo/From-LowerHex`. The guard reuses these by dot-sourcing.
- `scripts/interop/state_interop.ps1` — `Get-StateHmacHex`: the PS re-derivation of the A3
  state_hmac recipe (signs the exact pre-sign canonical bytes). The guard's state-verify
  path builds on this.

### Commit ordering & revert rule (the guard's core contract)
- `crates/mutation-engine/src/commit.rs` — `with_commit_lock` (fd-lock exclusive
  single-writer at `<lock_dir>/.nightguard.lock`), `commit_change` ordered atomic write
  **sanctioned → guard.json → live (live LAST)**. The guard's revert rule is the documented
  inverse: `HMAC(live config.yaml) ≠ guard.json.config_hmac ⇒ copy sanctioned over live`.
- `crates/mutation-engine/src/grace.rs` — `use_grace`: 8-min once-per-true-day window,
  NTP-true-time-in-configured-tz, refuses on `NtpUnreachable` / same-true-day reuse. The
  gate's grace-honoring + NTP-offline handling must match this fail-closed posture.
- `crates/mutation-engine/src/ntp.rs` — `TrueTime` trait / `NtpTrueTime` / `NtpUnreachable`.
  Reference for the guard's OWN NTP re-check and clock-tamper detection.
- `.planning/phases/02-mutation-engine/02-04-SUMMARY.md` — the crash-convergence contract
  (stop-after-N proof) and the GARD-05 "live-first is forbidden" anti-pattern; its local
  revert rule in `tests/commit_order.rs` is the reference behavior to mirror.

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 3: Enforcement Guard" — goal + 5 success criteria.
- `.planning/REQUIREMENTS.md` — GARD-01..06 full text.
- `./CLAUDE.md` — security invariants (DPAPI CurrentUser, `$null` entropy parity, fail-closed,
  `block_when_offline`), WinPS 5.1 constraint, Moonlit Indigo (Phase 4, not here).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/interop/nightguard_interop.ps1` + `state_interop.ps1`: the guard dot-sources
  these for ALL DPAPI/HMAC/byte-read primitives — do not reimplement hashing or key
  unwrapping in the guard.
- `crates/mutation-engine` (state/commit/grace/ntp): the authoritative behavior the PS
  guard mirrors; `tests/commit_order.rs` already encodes the revert rule as reference.

### Established Patterns
- Raw-bytes HMAC over canonical bytes, lowercase-hex tags, constant-time intent — locked
  both languages.
- fd-lock single-writer at `.nightguard.lock` — the lock the circuit-breaker (D-06) probes.
- Ordered-by-construction atomicity (revert target first, live last) — the guard recovers
  by re-applying the documented revert rule, not by journaling.
- Fail-closed everywhere: tamper/NtpUnreachable ⇒ most-restrictive outcome, byte-unchanged
  refusals.

### Integration Points
- Guard ↔ host: stdout JSON + exit code (D-01/D-02). Host wiring is Phase 5.
- Guard ↔ app: shared `<data_dir>` artifacts + the `.nightguard.lock`; the DPAPI-gated
  repair (D-05) is invoked from the Phase 4 app, the guard only consumes its re-signed state.
- Guard ↔ integrity: `verify_hook_integrity.ps1` SHA256 baseline (D-10).

</code_context>

<specifics>
## Specific Ideas

- Anti-me is the lodestar for every fail/edge decision: when in doubt, the more-restrictive
  branch wins (D-03 maximal lockout, D-05 forfeit-the-week repair, D-07 deny-on-offline).
- Repo is the **publishable product**; personal LifeOS instance is the host that wires the
  teeth — hence the oracle/host split (D-01) and host-agnostic output (D-02) and paths (D-09).

</specifics>

<deferred>
## Deferred Ideas

- Repair-flow UI copy / UX surface — Phase 4 (UI). Phase 3 only ships the guard runtime
  posture + the re-sign contract the repair invokes.
- Real host hook wiring (pointing SessionStart/UserPromptSubmit at the canonical config) —
  Phase 5 (Instance Wiring).
- Log rotation / size management for `guard-audit.log` — not in scope; revisit if the
  append-only log becomes a problem in practice.

None of these block Phase 3.

</deferred>

---

*Phase: 03-enforcement-guard*
*Context gathered: 2026-06-08*
