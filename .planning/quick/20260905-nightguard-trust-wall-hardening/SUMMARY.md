---
gsd_summary_version: 1.0
type: quick
slug: nightguard-trust-wall-hardening
completed: 2026-09-05
status: complete
---

# Summary — trust-wall hardening

Every bypass below was reproduced against the running system first, then re-tested after the
fix. A check never seen to fail is not evidence, so the reproductions are recorded here.

## Closed

**Time override turned the curfew off with two environment variables.** `guard.py` honored
`NIGHTGUARD_TEST_NTP_OVERRIDE` unconditionally — replacing verified true time and skipping
the clock-tamper check — and the hook adapter forwarded the whole ambient environment.
*Reproduced:* fixture curfew covering the current minute, no override → `deny/curfew`,
override to 14:00 → `allow/outside_curfew`; through the real adapter against the production
instance, override to 02:30 → butler message, exit 2. *After:* same command against
production → exit 0, refused. Fixture dirs still honor it, so tests keep the seam.

**A user-held `flock` on `.nightguard.lock` froze the revert silently.** *Reproduced:*
`flock -x .nightguard.lock sleep 200` as an ordinary user, config loosened, two consecutive
ticks logged `tick: ok`, config stayed tampered ~4 minutes; lock gone → `REVERTED`. *After:*
lock is `root:root 0600`, `flock` as the user returns `Permission denied`; suppression also
expires after 90s (verified: suppress, suppress, then revert-anyway once the marker ages past
the bound) and a suppressed tick now says so in the log.

**The browser block was removable with `rm`.** Both policy dirs were `0777`, both files
user-owned, and the watchdog only logged `MISSING browser policies`. *After:* `rm` returns
`Permission denied`; the watchdog rewrites the policy from `config.yaml`'s `extension_id` —
verified for both the missing file and the altered-content case.

**Root executed user-writable code.** The unit ran the watchdog from the working tree and
sudoers named `nightguard_ctl.py` there. *After:* both point at `/usr/local/lib/nightguard`,
`root:root`, installed by `scripts/linux/deploy.sh`.

**The instance dir was user-owned, so root-owned files could be renamed aside.** *Reproduced:*
a `root:root 0600` file, unreadable to the user, moved with no password — rename and unlink
are governed by the directory's mode. *After:* `/var/lib/nightguard`, `root:root 0755`.

**`docker` group membership was root without a password.** *Reproduced:* `head -c1 .guardkey`
→ `Permission denied`, while `docker run -v .../nightguard:/n:ro` returned
`32  owner=root mode=600`. *After:* dropped from the group; takes effect at next login.

**The watchdog stopped with no prompt.** *Reproduced:* `systemctl stop
nightguard-watchdog.timer` succeeded silently (restarted immediately). *After:* polkit rule
requiring `AUTH_ADMIN` for those two units.

## Found while working, also fixed

**An unimportable guard stack failed OPEN.** The adapter died at module scope with exit 1,
which this runtime treats as non-blocking, so a missing or half-deployed stack let every
prompt through at curfew. Now exits 2 with the fail-closed message — verified by pointing it
at an absent stack.

**The launcher had been dead since 2026-08-28.** `ngtui` is a uv-tool snapshot with paths
baked in; it still pointed at the LifeOS tree deleted during that migration, so the desktop
entry launched a process that died on import. Reinstalled, and `deploy.sh` now rebuilds it on
every deploy so a path change cannot rot it again.

## Verified live after deploy

Timer active; tamper `config.yaml` in place → `REVERTED config.yaml -> sanctioned` on the next
tick, hash back to `a6496c5d…` byte-exact; guard `allow/outside_curfew`; hook exit 0; ngtui
renders and reports 3 of 3 tokens.

## Left open, deliberately

- **The quota week anchor uses the system clock** (`nightguard_ctl.py:236` `datetime.now()`),
  not verified true time. Needs the true-time source wired into the signer.
- **`--rebaseline` matches the sudoers wildcard**, so a no-token policy reset costs only the
  sudo authentication.
- **`sudo` authenticates by fingerprint.** A touch is far weaker anti-impulse friction than a
  typed password, and it is now the entire cost of the reset above. Deliberate earlier
  decision, so left as the owner's call.
- **`guard-audit.log` deletion** is now blocked by the root-owned directory, but the audit
  chain still cannot prove absence of a wholesale replacement by root.
- `watchdog.log` (2.1 MB) is unrotated.

## Untested

The sudoers path (`sudo /usr/bin/python3 /usr/local/lib/nightguard/nightguard_ctl.py commit`)
could not be exercised without interactive authentication. The rule validated with `visudo -c`
and the path exists root-owned, but the first real commit through the TUI is the proof.
