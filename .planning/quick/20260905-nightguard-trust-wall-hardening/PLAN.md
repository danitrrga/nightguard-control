---
gsd_plan_version: 1.0
type: quick
slug: nightguard-trust-wall-hardening
created: 2026-09-05
status: in-progress
---

# Close the nightguard trust-wall bypasses

Full audit on 2026-09-05 found five ways past the "anti-me" guarantee that need no
password, plus several smaller weaknesses. This closes them.

## Findings being fixed

| # | Finding | Proof from the audit |
|---|---------|----------------------|
| 1 | `docker` group is root-equivalent; the root-only `.guardkey` reads out of a container | `docker run -v .../nightguard:/n:ro alpine` returned `32  owner=root mode=600` while `head -c1 .guardkey` was `Permission denied` |
| 2 | `systemctl stop nightguard-watchdog.timer` succeeds with no polkit prompt | Timer went `inactive`; restarted immediately |
| 3 | Instance dir is user-owned `755`, so root-owned files can be renamed away and replaced with a self-consistent forged set | A `root:root 0600` file in a user-owned dir was moved by the user with no password |
| 4 | `NIGHTGUARD_TEST_NTP_OVERRIDE=1` + `NIGHTGUARD_NTP_OVERRIDE_UNIX` turns the curfew off; the adapter forwards the whole environment | Fixture curfew covering the current minute: no override → `deny/curfew`; override to 14:00 → `allow/outside_curfew` |
| 5 | A user-held `flock` on `.nightguard.lock` suppresses the revert silently | Two consecutive ticks logged `tick: ok` with a loosened config; released → `REVERTED` |
| 6 | Browser policy dirs are `0777`, files user-owned; watchdog only logs missing policies | `_missing_policies()` has no restore path |
| 7 | Scripts root executes every 60s are user-writable | `scripts/linux/*.py` are `644 danitrrga` in a user-owned dir |
| 8 | `guard-audit.log` is user-writable — deletion undetectable | `644 danitrrga` |
| 9 | Quota week anchor uses the system clock, not verified true time | `nightguard_ctl.py:236` `datetime.now()` |

## Tasks

1. **Kill the time-override seam in production.** Honor `NIGHTGUARD_TEST_NTP_OVERRIDE` only
   when the instance dir is not the pinned canonical one — self-enforcing, needs no trust in a
   second env var. Scrub `NIGHTGUARD_*` from the child environment in the hook adapter.
2. **Make the commit lock unusable as a freeze.** Root-own the lock file, tolerate an
   unreadable lock in user context, bound suppression by age so a stuck lock cannot hold the
   revert off forever, and log suppression instead of `tick: ok`.
3. **Restore browser policies.** Watchdog rewrites the managed-policy JSON from the config's
   `extension_id` when it is missing or altered, and logs the restore.
4. **Root-own the executed code.** Deploy the stack to `/usr/local/lib/nightguard`
   (`root:root`), repoint the systemd unit, the sudoers rule and the TUI's default stack dir.
5. **Root-own the instance dir.** Move to `/var/lib/nightguard` (`root:root 0755`) so the
   protected files cannot be renamed away. `config.yaml` stays user-writable in place.
6. **Machine changes** (shown before running): drop the user from `docker`, add a polkit rule
   requiring admin auth to manage the watchdog units, lock the browser policy dirs to
   `root:root 0755`.

## Out of scope

- Quota week anchor on the system clock (finding 9) — recorded, not fixed here; it needs the
  true-time source wired into the signer, which is a larger change.
- `sudo` authenticating by fingerprint. That is a deliberate earlier decision; a fingerprint
  touch is weaker anti-impulse friction than a typed password, but changing it is the owner's
  call, not a bug to patch.
- `watchdog.log` rotation.

## Verification

Every fix is proved able to fail before it is claimed working: tamper the live config and
watch the revert fire, re-run the override bypass and see it refused, hold the lock and see
the suppression logged and time-bounded, delete a browser policy and see it restored.
