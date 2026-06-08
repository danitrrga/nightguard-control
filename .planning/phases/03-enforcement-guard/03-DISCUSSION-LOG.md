# Phase 3: Enforcement Guard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 03-enforcement-guard
**Areas discussed:** Curfew-gate enforcement boundary, Fail-closed strict default, State-tamper repair semantics, Revert circuit-breaker, Verdict output contract, Audit log, Path configuration, Integrity baseline, NTP-offline edge

---

## Curfew-gate enforcement boundary (GARD-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Emit verdict; host enforces | Pure verified-state oracle: revert config, print allow/deny + reason + grace-remaining, deterministic exit code; host maps deny→block | ✓ |
| Guard IS the hook, blocks directly | Guard implements CC hook contract itself (exit 2 / JSON block) | |
| Config-revert only, no curfew verdict | Guard does integrity/revert only; curfew/grace entirely host's job | |

**User's choice:** Emit verdict; host enforces
**Notes:** Keeps the publishable repo host-agnostic; teeth = thin host adapter (Phase 5 / LifeOS). Config auto-revert is unconditional, not advisory.

---

## Verdict output contract

| Option | Description | Selected |
|--------|-------------|----------|
| Exit code + JSON stdout | exit 0=allow / non-zero=deny; `{decision, reason, grace_remaining_secs, reverted, fail_closed}` | ✓ |
| Exit code only + text reason | Codes encode state; human reason to stderr | |
| Claude Code hook JSON schema | CC-native `{continue, decision, reason}` | |

**User's choice:** Exit code + JSON stdout
**Notes:** Deliberately not CC-native — that would couple the guard to the CC protocol against the host-agnostic decision.

---

## Fail-closed strict default (GARD-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Maximal lockout | Curfew always-on 24/7, no grace, zero tokens; forces in-app repair | ✓ |
| Safe nightly window | Hardcoded 23:00–07:00-style curfew, livable fallback | |

**User's choice:** Maximal lockout
**Notes:** Anti-me — worst case is maximally restrictive; corrupting both files buys nothing.

---

## State-tamper repair semantics (GARD-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Bless the worst-case for the week | Repair re-signs weekly_spent=3 + grace-used for current week; forfeit the week | ✓ |
| Clean slate (weekly_spent=0) | Repair resets quota to full | |
| Re-sign current on-disk values | Trust surviving numbers and re-sign | |

**User's choice:** Bless the worst-case for the week
**Notes:** Tampering = pure loss, never gain. DPAPI gate proves identity, not a loosening lever. Both other options are anti-me escape hatches.

---

## Revert circuit-breaker (GARD-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Lock-file presence check | On mismatch, check fd-lock; if app holds it, skip revert this cycle | ✓ |
| Retry-and-recheck | Sleep ~Nms, re-read+re-HMAC, revert only if still mismatched after K retries | |
| Lock-check + one retry | Lock primary + one short retry fallback | |

**User's choice:** Lock-file presence check
**Notes:** The lock is the real signal (already exists from Phase 2), not a guessed sleep. Live-last ordering makes consistency arrive moments later.

---

## NTP-offline gate edge (GARD-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-closed: deny grace, treat as curfew | No verifiable true time → deny; config revert still runs | ✓ |
| Honor last-known grace from guard.json | Trust signed window_end without re-checking NTP | |

**User's choice:** Fail-closed: deny grace, treat as curfew
**Notes:** Matches Phase 2 use_grace refusing on NtpUnreachable + CLAUDE.md block_when_offline. Last-known would let a network-isolation trick hold a window open.

---

## Audit log (GARD-01/02/03)

| Option | Description | Selected |
|--------|-------------|----------|
| Append-only HMAC-chained log | `<data_dir>/guard-audit.log`, records chained with HMAC; edits/truncation detectable | ✓ |
| Plain append-only log | Same format, no signing | |
| Windows Event Log | Write-EventLog | |

**User's choice:** Append-only HMAC-chained log
**Notes:** Tamper-evidence fits the self-binding threat model. Plain log is silently editable; Event Log is host-specific and hard to assert in tests.

---

## Path configuration

| Option | Description | Selected |
|--------|-------------|----------|
| Single base dir, fixed filenames | `--data-dir` / `NIGHTGUARD_DIR`; fixed names within | ✓ |
| Per-file args/env | Each path passed independently | |

**User's choice:** Single base dir, fixed filenames
**Notes:** One thing for Phase 5 to wire; trivial to point at a scratch dir in tests. Per-file = more misconfiguration surface.

---

## Integrity baseline (GARD-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Ship the baseline mechanism in-repo | Phase 3 creates verify_hook_integrity.ps1 + SHA256 baseline; guard self-registers | ✓ |
| Host owns it; repo documents the contract | Integrity tool lives in personal LifeOS host | |

**User's choice:** Ship the baseline mechanism in-repo
**Notes:** Repo stays self-contained/publishable; GARD-06 acceptance verifiable in-repo.

---

## Claude's Discretion

- Exact JSON field encodings/casing for the verdict object
- Log record delimiter/escaping and HMAC-chain construction details
- Precise fixed filenames within the data dir
- Whether the integrity baseline file is JSON or a flat `sha256  path` manifest

## Deferred Ideas

- Repair-flow UI copy / UX surface → Phase 4 (UI)
- Real host hook wiring → Phase 5 (Instance Wiring)
- Log rotation / size management for guard-audit.log → revisit if it becomes a problem
