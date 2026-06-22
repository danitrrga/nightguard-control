# Phase 7: Root Integrity Wall — Context

**Gathered:** 2026-06-22
**Status:** Planned — **execution blocked on P0** (restore + commit the Python trust stack)
**Milestone:** v2.0 · Linux Port (curated — see `.planning/phases/REVIEWS.md`)

<domain>
## Phase Boundary

Make the integrity wall **root-backed and unforgeable from user space**, on the existing
Python trust stack. Curated to the bare minimum (no bespoke daemon/socket): root-own the
key, run the watchdog as a systemd **system** service, and sign allowed edits by elevating
to the existing **control-CLI via `sudo`**.

**In scope:** the perms/ownership flip (ROOT-01), the watchdog→systemd-system cutover
(ROOT-02), and sign-via-sudo + quota in the control-CLI (ROOT-03/04).

**Out of scope:** the native-app kill (Phase 8 — folds into this watchdog's tick later); the
omarchy TUI (Phase 10). The browser-policy verification already works and is preserved.

## The core protection model (revert, not prevent)

- **`.guardkey`** → `root:root 0600` — the secret. Only root reads it ⇒ a non-root user cannot
  forge a valid signature. This is *the* v2.0 upgrade (today it's a user-readable 0600 file).
- **`config.sanctioned.yaml`** → `root:root 0644` — user may read it, only root writes it ⇒ the
  revert target can't be replaced by the impulsive user.
- **`guard.json`** (signed state) → `root:root 0644` — user/TUI reads state; only root re-signs.
- **`config.yaml`** (live) → **stays `user:user 0644`** — the user CAN hand-edit it; the root
  watchdog **reverts** it on HMAC mismatch. Prevention is for the key/sanctioned; revert is for
  the live file. (If config.yaml were root-owned the user couldn't hand-edit at all — wrong model.)
- **`sudo` is the sole bypass** — the user is a sudoer, so they can always cross the wall; the
  point is friction past the impulse, not an absolute lock (ROOT-04). The sudo password prompt IS
  that friction.
</domain>

<decisions>
## Implementation Decisions (discuss, 2026-06-22)

- **D-1 — Keep all files in `LifeOS/nightguard`; change ownership only** (no path re-wire).
  `NIGHTGUARD_DIR = /home/danitrrga/dev/Projects/LifeOS/nightguard` stays the single home.
  Perms model = the table above. Root reads/traverses the user home dir fine (root ignores perms).
- **D-2 — Watchdog → systemd *system* service, running as root.** A *system* unit has no `%h`,
  so the unit uses the **absolute** ExecStart path and `Environment=NIGHTGUARD_DIR=/home/danitrrga/dev/Projects/LifeOS/nightguard`.
  Replaces the current `--user` timer (`OnUnitActiveSec=60`).
- **D-3 — Prove-then-switch cutover (Phase-5 D-11 discipline).** Stand up + PROVE the root
  watchdog (reading the still-user-readable key) reverts correctly BEFORE chowning the key to root
  and retiring the `--user` timer — never a window where nothing verifies the config.
- **D-4 — Sign via `sudo` → control-CLI, password required (no NOPASSWD).** A narrow sudoers
  entry scoped to the control-CLI command. The TUI/CLI shells `sudo <control-cli> commit …`.
- **D-5 — The control-CLI restores config.yaml ownership.** It runs as root (via sudo) and writes
  sanctioned→guard.json→config.yaml under flock; after writing config.yaml it **chowns it back to
  `$SUDO_UID:$SUDO_GID`** so the user can still hand-edit and the watchdog can still revert.
- **D-6 — Watchdog identity = bare root** (not a dedicated system user). Simplest, and root IS the
  threshold in this model. (A least-privilege `nightguard` user is a possible later refinement.)
</decisions>

<canonical_refs>
## Canonical References

### The trust stack to root-ify (RESTORE FIRST — see Blockers)
- `LifeOS/scripts/nightguard/ngcommon.py` — shared `yaml_load` + `config_hmac`/`state_hmac` (A3);
  must resolve `NIGHTGUARD_DIR` and read the (now root-owned) key.
- `LifeOS/scripts/nightguard/guard.py` — verify→revert curfew guard (the watchdog's core).
- `LifeOS/scripts/nightguard/nightguard_watchdog.py` — the systemd entrypoint (tick).
- the **control-CLI** (the signer — holds `.nightguard.lock` flock, commits sanctioned→config→re-sign).

### Live system facts (verified)
- `~/.config/systemd/user/nightguard-watchdog.{service,timer}` — current `--user` timer.
  `service` ExecStart = `/usr/bin/env python3 %h/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py`;
  `timer` = `OnBootSec=30`, `OnUnitActiveSec=60`, `AccuracySec=15`. (To be retired.)
- `LifeOS/nightguard/` holds `.guardkey` (32B, currently `-rw------- user`), `config.yaml`,
  `config.sanctioned.yaml`, `guard.json`, `.nightguard.lock`, `policies/` (Chromium/Firefox
  managed-policy JSON the watchdog verifies each tick), `guard-audit.log`, `watchdog.log`.
- The system target uid is `1000` (`/run/user/1000`).

### Product/contract refs
- `.planning/REQUIREMENTS.md` — ROOT-01..04 (curated definitions).
- `.planning/ROADMAP.md` §"Phase 7" — curated goal + success criteria.
- `.planning/phases/REVIEWS.md` — the curation rationale (why sudo, not a socket).
- Phase 5 `05-CONTEXT.md` D-11 — the prove-then-switch cutover pattern to mirror.
</canonical_refs>

<code_context>
## Insights / Seams

- **HMAC is opaque-bytes** — root-owning files doesn't change the signing recipe; it only changes
  *who can read the key*. The A3 state recipe and canonicalization are untouched.
- **Phase 8 seam (Hyprland-from-root):** the native-kill folds into THIS watchdog's tick (Phase 8),
  but Hyprland's IPC socket is user-owned at `/run/user/1000/hypr/$HIS/.socket.sock`. A root tick
  CAN reach it but must discover `$XDG_RUNTIME_DIR` + the instance signature for uid 1000. Phase 7
  just needs the watchdog to run as root with a stable tick; Phase 8 owns the bridge. **This is the
  main Phase-8 technical risk — flagged now, not solved here.**
- **Sudoers footgun:** wildcard args in a sudoers rule enable arg-injection. Scope the rule tightly
  (fixed interpreter + script path; avoid permissive `*` on the whole command line) — prefer a
  single `commit`-style subcommand surface, validate args inside the root CLI.
</code_context>

<blockers>
## Blockers / Preconditions

- **⛔ P0 — the Python trust stack is absent + untracked.** `ngcommon.py`/`guard.py`/the
  control-CLI/`nightguard_watchdog.py` are NOT on disk (only stale `.pyc`), not in git. The
  current `--user` timer's ExecStart points at a missing file (watchdog effectively broken now).
  **All of Phase 7 is blocked until these sources are restored and committed to version control.**
  This is the single highest-risk item in the milestone.
- **No-gap invariant:** chowning the key to root immediately disables any user-context reader, so
  ROOT-01 (key chown) and ROOT-02 (root watchdog) MUST land together via the D-3 prove-then-switch,
  or the config is briefly unverified.
</blockers>

---
*Phase: 7 — Root Integrity Wall (curated)*
*Context gathered: 2026-06-22*
</content>
