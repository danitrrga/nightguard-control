---
phase: 07-root-integrity-wall
verified: 2026-06-22T20:45:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 7: Root Integrity Wall Verification Report

**Phase Goal:** Make the integrity wall root-backed and unforgeable from user space — root-own the key, run the watchdog as a systemd system service, and sign allowed edits only by elevating to the control-CLI via `sudo` (quota enforced in-CLI). Closes ROOT-01..04.
**Verified:** 2026-06-22
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | Watchdog runs as a systemd SYSTEM service (root), reverts a hand-edited config within one tick, verifies browser policy | VERIFIED | `/etc/systemd/system/nightguard-watchdog.{service,timer}` active; journal shows `systemd[1]` running it; `watchdog.log` shows `tick: REVERTED config.yaml -> sanctioned` on a hand-edit, steady `tick: ok` otherwise. |
| SC-2 | `.guardkey` root:root 0600 — non-root cannot read it; sanctioned + guard.json root:root 0644; config.yaml stays user:user 0644 | VERIFIED | `stat`: key `root:root 600`, sanctioned/guard.json `root:root 644`, config.yaml `danitrrga:danitrrga 644`. Non-root `cat .guardkey` → Permission denied; `read_key()` as user → None. |
| SC-3 | No protection gap during cutover (prove-then-switch) | VERIFIED | Root watchdog proven reverting BEFORE the key chown (07-01 Task 2), and again AFTER with the root key (07-01 Task 3); the system timer ran throughout. |
| SC-4 | Allowed edits signed only by the control-CLI as root (via sudo); a non-root invocation refuses | VERIFIED | Live: user-context `commit` → "cannot read .guardkey — run as root via sudo. Refusing (wrote nothing)" exit 2. `sudo … commit` signs and `verify` is all-green. |
| SC-5 | The control-CLI enforces the weekly quota in-process and chowns config.yaml back to the user | VERIFIED | Sandbox matrix: tighten free; loosen ×3 → 0→1→2→3 with ledger; 4th loosen REFUSED "available again Monday"; noop writes nothing; `--rebaseline` no token. Live: after a `sudo` commit, config.yaml is `danitrrga:danitrrga` again. |
| SC-6 | Hand-forge infeasible without the root key; sudo the sole bypass | VERIFIED | Live: a hand-edit (no sudo) was reverted by the root watchdog within a tick (ROOT-04). The only path to a sanctioned change is `sudo` → control-CLI. |

**Score:** 6/6 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `/etc/systemd/system/nightguard-watchdog.timer` | root system timer (60s) replacing the --user timer | VERIFIED | `OnUnitActiveSec=60`; active; `--user` timer retired. Version-controlled copy in `LifeOS/scripts/nightguard/systemd/`. |
| `/etc/sudoers.d/nightguard` | narrow, password-required rule scoped to the control-CLI | VERIFIED | `Cmnd_Alias` scoped to `commit*`/`verify`; no NOPASSWD; `visudo -c` passes for the whole set. Staged copy `LifeOS/scripts/nightguard/nightguard.sudoers`. |
| `LifeOS/scripts/nightguard/nightguard_ctl.py` | root signer + in-CLI quota + chown-back | VERIFIED | Committed `bfc67a5`; classify/quota ports validated; non-root refusal proven. |

---

## Requirements Traceability

| Requirement | Status | Evidence |
|-------------|--------|----------|
| ROOT-01 | COMPLETE | Key root:root 0600 (user denied); sanctioned/guard.json root-owned. |
| ROOT-02 | COMPLETE | Watchdog is a systemd system service (revert + browser-policy), prove-then-switch cutover. |
| ROOT-03 | COMPLETE | Control-CLI is the sole signer via sudo; in-CLI weekly quota under flock; no daemon/socket. |
| ROOT-04 | COMPLETE | Hand-forge reverts; non-root cannot sign; sudo is the sole (password-gated) bypass. |

---

## Notes
- **Execution mode:** guided-interactive — the user ran each `sudo` step in a real terminal (the session `!` runner has no TTY for the password/fingerprint); the agent prepared artifacts, ran non-privileged proofs, read the system journal, and verified. No `sudo` was run by the agent.
- **Quota proof scope:** the loosen-costs-token / 0-token-refusal matrix was proven in an isolated `/tmp` dir with a throwaway key (key-independent logic) so the live instance's real weekly quota stayed 0/3; the live proof used a free tighten + `--rebaseline` restore, leaving state at the exact baseline.
- **Phase-8 risk (carried):** the native-app kill folds into this root watchdog tick, but the root tick must reach the user's Hyprland socket at `/run/user/1000/hypr` — flagged, not solved here.

---
*Phase: 07-root-integrity-wall*
*Verified: 2026-06-22*
