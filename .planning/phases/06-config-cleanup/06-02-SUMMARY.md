---
phase: 06-config-cleanup
plan: 02
subsystem: instance
tags: [linux-port, instance, hmac, python, recovery, watchdog, control-cli, blocking]

# Dependency graph
requires:
  - phase: 06-config-cleanup
    provides: 06-01 — the matching product-side classifier for the blocking. schema
provides:
  - "Live LifeOS instance re-baselined onto the Linux `blocking:` schema (curfew 20:45), re-signed guard.json verifying in the Python stack"
  - "Recovered + git-tracked Linux Python trust stack: ngcommon.py, guard.py, nightguard_ctl.py (control CLI), nightguard_watchdog.py"
  - "Restored systemd revert-watchdog (config-integrity protection was OFF ~5h)"
affects: [07-root-integrity-wall, 08-native-blocker]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Recovered deleted Python sources by disassembling stale .pyc with the matching interpreter (3.14) and reconstructing against an HMAC oracle (stored guard.json)"
    - "Control CLI commits sanctioned→guard.json→config LAST under .nightguard.lock flock (Rust commit.rs RULE-06 ordering, ported to Python)"

key-files:
  created:
    - .planning/phases/06-config-cleanup/06-02-SUMMARY.md
    - LifeOS/scripts/nightguard/ngcommon.py          # recovered from bytecode (byte-exact)
    - LifeOS/scripts/nightguard/guard.py             # recovered from bytecode (byte-exact)
    - LifeOS/scripts/nightguard/nightguard_ctl.py    # rebuilt (control CLI / signer)
    - LifeOS/scripts/nightguard/nightguard_watchdog.py  # rebuilt (systemd oneshot)
  modified:
    - LifeOS/nightguard/config.yaml
    - LifeOS/nightguard/config.sanctioned.yaml
    - LifeOS/nightguard/guard.json

key-decisions:
  - "Recovered ngcommon.py/guard.py from .pyc rather than uploading bytecode to a web decompiler — security tool, kept local; used Python 3.14 dis + an HMAC oracle (state_hmac match) to prove byte-exactness"
  - "Sanctioned re-baseline preserves weekly_spent/week_anchor/ledger/grace (NOT a quota-charged loosen) per D-3/D-4; curfew 20:45 written straight to sanctioned"
  - "LXCF-02 scoped to the single Python stack (REVIEWS curation): Python parses+signs the new schema and the watchdog accepts it; Rust↔Python byte-parity is algorithmic (HMAC-SHA256 over identical canonical bytes) and repo-hygiene, not a runtime gate"
  - "Committed the recovered tooling to LifeOS git (was untracked → unrecoverable) so the loss cannot recur"

patterns-established:
  - "config_hmac is HMAC over raw canonical file bytes (UTF-8/no-BOM/LF/one trailing \\n); the CLI canonicalizes on write so raw==canonical and Rust/Python agree"

requirements-completed: [LXCF-01, LXCF-02]

# Metrics
completed: 2026-06-22
---

# Phase 6 Plan 02: Instance Re-baseline + Trust-Stack Recovery Summary

**Re-baselined the author's live LifeOS nightguard instance onto the Linux `blocking:` schema (curfew 20:45) and re-signed `guard.json` via the Python control CLI — but first had to recover the entire Linux Python trust stack, which had been deleted from disk and was unrecoverable via git.**

## Context: the plan's blocker was real, and worse than recorded

06-02 was marked `status: blocked` — the Linux Python tooling absent from disk. On execution, the live state was worse than the snapshot: the systemd `nightguard-watchdog.service` had been **crash-looping every 60s for ~5h** (`No such file or directory` for `nightguard_watchdog.py`), so config-revert protection was **OFF**. `config.yaml` still held the old Windows `watchdog.apps`/`uwp` schema and did not match `guard.json` (which was signed over `config.sanctioned.yaml`).

User chose **"Recover now, then 06-02"** (the largest-scope option).

## Recovery (the load-bearing work)

**ngcommon.py + guard.py — recovered byte-exact from bytecode.** Standard decompilers cap at Python 3.8; uploading a security tool's signing bytecode to a web decompiler was unacceptable. Instead I disassembled the stale `__pycache__/*.cpython-314.pyc` with the *matching* Python 3.14 (`dis` + `marshal`), giving a complete, accurate disassembly + all string/const literals, and reconstructed both modules from it.

**Validated against an oracle, not by eyeballing:** the reconstructed `ngcommon.state_hmac` over the live `guard.json` reproduces the **stored `state_hmac` byte-for-byte**, `verify_chain` over the live audit log returns `(True, -1)`, and `yaml_load` parses the schema. Since `config_hmac`, `state_hmac`, and the audit chain all share the same proven `hmac_hex`, the crypto core is provably correct. `guard.py` was then validated end-to-end against an **isolated copy** (via the `NIGHTGUARD_DIR` seam): inside-curfew → `deny/curfew` + revert; outside → `allow/outside_curfew`; chain still verifies.

**nightguard_ctl.py + nightguard_watchdog.py — rebuilt** (no bytecode existed). The control CLI commits in the Rust `commit.rs` RULE-06 order (sanctioned → re-signed `guard.json` → live config **last**) under the `.nightguard.lock` `fcntl` flock. The watchdog is the systemd oneshot: `verify_and_revert` + browser-policy check + one `tick:` log line (format matched to the live `watchdog.log`).

## Re-baseline (06-02 proper)

Ran `nightguard_ctl.py commit --from <target>` on the live instance:
- `config.yaml` ≡ `config.sanctioned.yaml` (byte-identical), new `blocking:` schema, curfew **20:45**, no `uwp`/`package_id`.
- `guard.json` re-signed: `config_hmac = 78847ce57985d43b…`; `state_hmac` via the A3 recipe.
- **Preserved** `weekly_spent=0`, `week_anchor=2026-06-22`, `ledger=[]`, `grace=null` (sanctioned re-baseline, not a token-charged loosen — D-4).

## Proof (LXCF-01 instance half + LXCF-02)
- **`verify` all-green:** `config.yaml` and `config.sanctioned.yaml` HMAC == `guard.json`; `state_hmac` == stored; audit chain verifies.
- **Watchdog accepts it:** the real systemd timer logs steady `tick: ok` on the new schema (no revert loop).
- **Tamper still reverts:** hand-editing `config.yaml` (removing `discord` from `native_apps.blacklist` — a loosen) without re-signing → next watchdog tick logs `REVERTED config.yaml -> sanctioned`, restores the entry, then steady `tick: ok`.
- **Parse parity:** Python `yaml_load` returns the expected `blocking.browser_extension.{enabled,extension_id}` and `blocking.native_apps.{enabled,blacklist}` values.

## Durability fix
The recovered sources were committed to **LifeOS git** (`scripts/nightguard/`, `__pycache__` ignored) — they were previously untracked, the exact reason today's deletion was unrecoverable. Commit `33df4c3` in the LifeOS repo.

## Deviations from Plan
- **Scope expansion (authorized):** the plan assumed the tooling merely needed restoring; in fact the sources were gone and had to be recovered from bytecode + rebuilt, and live protection had to be brought back up. The user explicitly authorized this ("Recover now, then 06-02"). The re-baseline itself followed Task 2/3 as written.
- **LXCF-02 Rust↔Python runtime parity check:** not executed as a live cross-binary diff — the Rust app does not run on Linux (Phase 10) and the curation note (REVIEWS.md) downgraded it to repo-hygiene. Parity holds by construction (HMAC-SHA256 over identical canonical bytes; 06-01 validated the Rust classifier side).

## Next Phase Readiness
- LXCF-01 (instance half) + LXCF-02 complete; Phase 6 fully done.
- Phase 7 (root-integrity wall) can now build on a present, git-tracked, validated Python stack — and should move the `.guardkey` + watchdog to root/systemd-system per its plan.

---
*Phase: 06-config-cleanup*
*Completed: 2026-06-22*
