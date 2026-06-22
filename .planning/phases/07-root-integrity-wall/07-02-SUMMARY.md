---
phase: 07-root-integrity-wall
plan: 02
subsystem: instance
tags: [linux-port, root, sudo, sudoers, quota, classifier, control-cli, signer]

# Dependency graph
requires:
  - phase: 07-root-integrity-wall
    provides: 07-01 — the root-owned key (only root can sign)
provides:
  - "Control-CLI is the sole root signer (sign only via sudo); non-root invocation refuses"
  - "In-process weekly-token quota (port of Rust classify.rs/quota.rs): loosen costs 1/3, refuse at 0 with 'available again Monday'; tighten/noop free"
  - "config.yaml chowned back to the invoking user after every commit (D-5)"
  - "Narrow, password-required /etc/sudoers.d/nightguard scoped to the control-CLI"
affects: [08-native-blocker, phase-10-tui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Python port of the Rust direction classifier + weekly-token quota, operating on ngcommon.yaml_load'd dicts (no yamlpath needed)"
    - "sudoers drop-in validated with `visudo -cf <staged>` BEFORE install -m0440 to /etc/sudoers.d (never place an unvalidated file in /etc)"

key-files:
  created:
    - .planning/phases/07-root-integrity-wall/07-02-SUMMARY.md
    - LifeOS/scripts/nightguard/nightguard.sudoers
    - /etc/sudoers.d/nightguard          # installed (0440 root:root)
  modified:
    - LifeOS/scripts/nightguard/nightguard_ctl.py   # +classifier +quota +chown-back +root-refusal

key-decisions:
  - "commit became the quota'd path (classify sanctioned-vs-proposed, charge a token on any loosen); --rebaseline kept as the no-token admin reset (what 06-02 used)"
  - "Quota matrix proven exhaustively in an isolated /tmp dir with a throwaway key (logic is key-independent) so the live instance's real quota stayed 0/3; the live proof used a free tighten + rebaseline-restore"
  - "sudoers scoped to fixed subcommands (commit*/verify) via Cmnd_Alias, not a bare trailing '*'; password required (no NOPASSWD) — the prompt is the ROOT-04 friction"
  - "Under sudo the CLI resolves NIGHTGUARD_DIR via the ROOT/nightguard fallback (env_reset strips env); SUDO_UID/GID survive for chown-back"

patterns-established:
  - "config_hmac stays HMAC over raw canonical bytes; the CLI canonicalizes input (UTF-8/no-BOM/LF/one trailing \\n) so raw==canonical"

requirements-completed: [ROOT-03, ROOT-04]

# Metrics
completed: 2026-06-22
---

# Phase 7 Plan 02: Sign-via-Sudo + In-CLI Quota Summary

**Made the control-CLI the sole root signer — reachable only by elevating via `sudo` (password = the anti-impulse friction) — enforcing the weekly token quota in-process and chowning `config.yaml` back to the user after each commit. Closes ROOT-03 + ROOT-04.**

## Execution mode
Guided-interactive (same as 07-01): the user ran every `sudo` step in their own terminal; the agent prepared all artifacts, ran the non-privileged proofs, and verified. The agent never ran `sudo`.

## What was built
- **`nightguard_ctl.py` gained a faithful Python port of the Rust `classify.rs` + `quota.rs`:** the FIELD_TABLE (the same Linux `blocking:` model from 06-01), per-field direction (`bool`/`num`/`list_add`/`list_remove`/`schedule`/`any`), the curfew-window locked-set model, and `is_loosening`. Quota: lazy week reset (Monday, Europe/Amsterdam), `WEEKLY_TOKENS=3`, all-noop writes nothing, no-loosen is free, a loosen costs 1 token and is refused at 3/3 with the locked substring **"available again Monday"**.
- **Root-only signing:** `commit` refuses (exit 2, writes nothing) when it can't read the key — which is exactly the non-root case now that the key is `root:root 0600`.
- **Ownership restore (D-5):** after the ordered `sanctioned → guard.json → config.yaml` write under flock, the CLI `os.chown`s `config.yaml` back to `$SUDO_UID:$SUDO_GID`.
- **`/etc/sudoers.d/nightguard`:** a `Cmnd_Alias`-scoped, password-required rule (no NOPASSWD), `visudo`-validated before install.

## Proofs (ROOT-03 + ROOT-04)
**Sandbox (`/tmp/ngq`, throwaway key — full quota matrix without touching the real quota):**
- tighten (add to blacklist) → free, 0 tokens. loosen ×3 (remove entry / disable native_apps / disable browser_extension) → 0→1→2→3, ledger entries recorded. 4th loosen → **REFUSED "available again Monday"**. noop → nothing written. `--rebaseline` of a loosen → no token. no key → refuse (wrote nothing).

**Live instance (real quota preserved at 0/3):**
- **Non-root cannot sign:** user-context `commit` → refused (exit 2). ✓
- **`sudo` commit (free tighten):** signed as root, `verify` all-green, tokens 0/3, and `config.yaml` returned to `danitrrga:danitrrga 644` (chown-back). The root watchdog **accepted** it (`tick: ok`, no revert). ✓
- **Restore:** `--rebaseline` back to the captured baseline → `config_hmac=78847ce5…`, `weekly_spent=0`, `ledger=[]`. ✓
- **ROOT-04 hand-forge:** hand-edit `config.yaml` (no sudo) → root watchdog **reverted** within a tick. ✓

## Deviations from Plan
- **Quota proven in sandbox, not by exhausting the live tokens:** spending the user's 3 real weekly tokens on a proof would be a destructive side effect. The classify/quota logic is key-independent, so the `/tmp` matrix is authoritative; the live proof covered the integration (sudo→sign→chown-back→accept→non-root-refuse→revert). No scope change.

## Threats mitigated
- T-07-05 (broaden root via sudoers): `Cmnd_Alias`-scoped to commit/verify, password required, in-CLI argparse validation, `visudo`-checked.
- T-07-06 (config.yaml left root-owned): chown-back to `$SUDO_UID` after every commit (proven).
- T-07-07 (quota skipped): quota is in the single root signer; non-root cannot sign at all, so there is no un-quota'd path.
- T-07-08 (residual): the user is a sudoer and can always `sudo` — by design (friction, not absolute lock); the HMAC-chained audit records each elevated commit.

## Next Phase Readiness
- The integrity wall is complete: one root key → one root watchdog → one signer (sudo→control-CLI) → one schema → one HMAC.
- Phase 8 (native-app kill) folds into the root watchdog tick; the flagged risk remains the root tick reaching the user's Hyprland socket (`/run/user/1000/hypr`).

---
*Phase: 07-root-integrity-wall*
*Completed: 2026-06-22*
