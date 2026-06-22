---
phase: 07-root-integrity-wall
plan: 01
subsystem: instance
tags: [linux-port, root, systemd, watchdog, perms, prove-then-switch]

# Dependency graph
requires:
  - phase: 06-config-cleanup
    provides: the recovered + git-tracked Python trust stack this plan root-ifies
provides:
  - "Root systemd-system watchdog (60s) reverting config tampering with the root-owned key"
  - ".guardkey root:root 0600 (non-root cannot read → cannot forge a signature); sanctioned + guard.json root:root 0644"
  - "Version-controlled system unit + timer (LifeOS/scripts/nightguard/systemd/)"
affects: [07-02-sign-via-sudo, 08-native-blocker]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Prove-then-switch cutover: stand up + prove the root watchdog reverts BEFORE chowning the key to root and retiring the --user timer — never a window where nothing verifies"

key-files:
  created:
    - .planning/phases/07-root-integrity-wall/07-01-SUMMARY.md
    - LifeOS/scripts/nightguard/systemd/nightguard-watchdog.service
    - LifeOS/scripts/nightguard/systemd/nightguard-watchdog.timer
  modified:
    - /etc/systemd/system/nightguard-watchdog.service   # installed (system)
    - /etc/systemd/system/nightguard-watchdog.timer     # installed (system)
    - LifeOS/nightguard/.guardkey                        # chown root:root 0600
    - LifeOS/nightguard/config.sanctioned.yaml           # chown root:root 0644
    - LifeOS/nightguard/guard.json                       # chown root:root 0644

key-decisions:
  - "Watchdog/ngcommon were already path-clean (everything from NIGHTGUARD_DIR, no $HOME/%h/cwd) so 07-01 Task 1 needed no code change — the system unit just sets Environment=NIGHTGUARD_DIR + absolute ExecStart=/usr/bin/python3 (3.14, root-available; mise shims are user-only)"
  - "Executed guided-interactive: the user ran every sudo step in a real terminal (the harness ! runner has no TTY for the sudo password/fingerprint); the agent never ran sudo"
  - "config.yaml stays user:user 0644 (revert model, not prevention); only key/sanctioned/state are root"

patterns-established:
  - "User-context guard.py now runs in soft mode (key unreadable → read_key()==None → curfew still evaluated, integrity enforced solely by the root watchdog)"

requirements-completed: [ROOT-01, ROOT-02]

# Metrics
completed: 2026-06-22
---

# Phase 7 Plan 01: Root Integrity Wall — Watchdog→Root + Key Chown Summary

**Made the integrity wall root-backed: the watchdog now runs as a systemd system service (root) and the `.guardkey` is `root:root 0600`, so a non-root user can no longer forge a valid signature — done as a prove-then-switch cutover with no protection gap. Closes ROOT-01 + ROOT-02.**

## Execution mode

Guided-interactive: the user ran each `sudo` step in their own terminal and pasted output (the session's `!` runner has no TTY, so `sudo` can't prompt for the password/fingerprint there). The agent prepared all artifacts, hand-edited the user-owned `config.yaml` for the proofs, and verified each step (including reading the system journal) but never ran `sudo`.

## Prove-then-switch sequence (D-3)
1. **Prep:** wrote the version-controlled system `.service` + `.timer` to `LifeOS/scripts/nightguard/systemd/`. Confirmed the watchdog is path-clean (resolves everything from `NIGHTGUARD_DIR`) — Task 1 needed no code change. Confirmed `/usr/bin/python3` is 3.14.5 and the stdlib-only stack imports under it.
2. **Install + prove (key still user-readable):** installed the units to `/etc/systemd/system/`, `daemon-reload`, `enable --now` the system timer (alongside the still-running `--user` one). Stopped the `--user` timer for clean attribution, hand-edited `config.yaml` (removed `discord` — a loosen) → the **root** service reverted it within one tick (`watchdog.log: tick: REVERTED`; journal `systemd[1]`).
3. **Switch (ROOT-01):** `sudo chown root:root .guardkey config.sanctioned.yaml guard.json`; `chmod 0600` key, `0644` sanctioned/state; `config.yaml` left user-owned. Retired the `--user` timer (`disable --now` + removed the user unit files).
4. **Re-proved with the ROOT key:** hand-edited `config.yaml` again → the root service reverted it at 22:20:44 now reading the **root-owned** key (`read_key()` as the user returns `None`).

## Verification (all green)
- `.guardkey` = `root:root 600`; a non-root read is **Permission denied**. `config.sanctioned.yaml` + `guard.json` = `root:root 644` (user can read, not write). `config.yaml` = `danitrrga:danitrrga 644`.
- Root system timer **active**; `--user` timer **gone**.
- Root watchdog reverts a hand-edit within one tick (proven twice — before and after the chown); browser-policy check stays green (`tick: ok` cadence).
- No moment in the cutover left the config unverified (the system timer ran throughout).

## Deviations from Plan
- **Task 1 (path-cleanliness) was a no-op edit:** the recovered watchdog/`ngcommon` already resolve all paths from `NIGHTGUARD_DIR`, so nothing needed changing — only verification. No scope change.

## Threats mitigated
- T-07-01 (forge a loosened config): key `root:root 0600` → non-root cannot read it → cannot produce a valid HMAC. **The wall.**
- T-07-02 (replace the revert target): `sanctioned` root-owned 0644 → only root writes it.
- T-07-03 (gap during cutover): prove-then-switch held — root watchdog proven reverting before the chown.

## Next Phase Readiness
- 07-02 can now make the control-CLI the sole root signer (sign-via-sudo + in-CLI quota), since the key is root-only. Until then, signing is unavailable to the user by design (no sudo path yet) — 07-02 wires it up in this same session.

---
*Phase: 07-root-integrity-wall*
*Completed: 2026-06-22*
