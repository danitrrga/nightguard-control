# Curation Review — Phases 6/7/8 (Musk's algorithm)

**Date:** 2026-06-22
**Ask:** "Run Musk's algorithm — simplify, curate, make everything cohesive, get to the bare minimum that most results will get us." Scope: phases 6, 7, 8.
**Reviewers:** Claude CLI ✅ (full review); Gemini ❌ (no `GEMINI_API_KEY`); Codex ❌ (401 unauthorized). Plus the orchestrator's own pass. The two available perspectives **converge tightly**.

---

## The fact that reframes everything

On Linux **today, only the Python stack runs** — the systemd watchdog reverts tampered config, `guard.py` enforces curfew+grace, `ngcommon.py` signs, the control CLI commits under flock. The Rust/Tauri app does **not** run on Linux (that's P10). Almost every heavy requirement in 7/8 is designed for a Rust app that isn't there yet.

→ **Corollary:** the cohesion decision and the Phase-10 decision are the *same* decision. Keep P10 in v2.0 and you own two byte-identical crypto stacks + a socket protocol forever; defer it and 6/7/8 collapse into one coherent thing.

## Step 1 — Question the requirements

| Requirement | Verdict |
|---|---|
| **ROOT-01** root-own the key | **Load-bearing** — *the* v2.0 upgrade. Key is a user-readable 0600 file today, so the impulsive self can re-sign a loosened config and beat the revert. Root ownership turns "reverts" into "can't forge without crossing a friction threshold." |
| **ROOT-02** watchdog → systemd *system* service | **Load-bearing** — necessary consequence of ROOT-01 (a `--user` watchdog can't read a root key). |
| **ROOT-04** sudo = sole bypass (friction, not lock) | **Load-bearing as philosophy** — and it quietly kills ROOT-03. |
| **LXCF-01** Linux blocking schema | **Load-bearing** — the contract every layer reads. |
| **ROOT-03** socket commit-helper | **Dumbest surviving requirement** — dumb *because* a smart person chose it (B1 opt 1). Its only consumer is the Rust app that doesn't exist on Linux. The Python control CLI already enforces quota + signs + writes under flock in the right order. ROOT-03 re-implements a working CLI as a daemon + socket protocol + peer-cred auth + client, purely so a future GUI feels seamless. |
| **NBLK-01/02** separate event-driven blocker service | **Scope-creep shape** — a `--user` listener is `systemctl --user stop`-able by the person it polices (NBLK-03 admits this). If it needs the root watchdog to be trustworthy, it should *live in* the root watchdog. |
| **LXCF-02** cross-language parity proof | **Tax that serves P10** — only load-bearing because two crypto stacks must agree. At runtime there's one (Python). |

## Step 2 — Delete (most impactful first)

- **(a) Delete ROOT-03 entirely.** Root owns the key; sign by invoking the existing control CLI via `pkexec`/`sudo`. Preserves every claimed property (quota, sole-signer, ordered commit) with **zero new code**.
- **(b) Delete Phase 8 as a service; fold window-kill into the root watchdog tick.** It already runs as root every 60s and knows lock/grace state. ~15 lines: during a lock, enumerate Hyprland clients, kill blacklisted classes. Deletes a service *and* makes the blocker un-stoppable from user space. Accept ≤60s leakage.
- **(c) Defer Phase 10 → delete a whole crypto stack at runtime.** A GUI isn't the core value; a signer you must deliberately invoke is — and the control CLI already is one. Deferring P10 leaves **one HMAC implementation**, kills ROOT-03's only consumer, shrinks LXCF-02 to "Python parses the new schema."
- **Add-back (≥10% test):** keep **06-01** (re-point the Rust classifier) — not for Linux, but because the repo is the *publishable product* and shouldn't ship a dead Windows shape. Cheap, off the critical path.

## Step 3 — Cohesion

The unifying primitive is real: **one root-owned key → one root systemd watchdog (verify-revert + true-time + browser-policy + native-kill) → one signer (control CLI behind sudo) → one config schema → one HMAC (Python).** 6/7/8 only *feel* like three phases because of the unstated assumption that the Rust app is live on Linux.

## Step 4 — Trade-offs, honestly

- **pkexec/sudo prompt vs seamless socket:** the prompt **is the product**, not a cost. ROOT-04's whole point is friction past the impulse. A seamless socket makes loosening feel free — exactly the late-night behavior the tool exists to interrupt. The socket is **anti-aligned** with core value. (Caveat: pkexec needs a polkit agent under Hyprland; sudo-in-terminal is the even-more-deliberate fallback.)
- **≤60s leakage vs instant socket2:** 60s is fine for impulse control; the open→die→open→die loop *is* the deterrent. Build socket2 only if the folded-in version proves inadequate with evidence — a later "accelerate" step.

## Step 5 — Curated minimum

Collapse 6+7+8 into **one phase: "Root trust layer + Linux config model."**

- **P0 (do first — the scary one):** get the Python trust stack into version control. The entire Linux integrity layer exists only as live files + stale `.pyc`, untracked, actively edited — one `rm` from unrecoverable. This is also the 06-02 blocker.
1. **ROOT-01** root-own `.guardkey` + `config.sanctioned.yaml`.
2. **ROOT-02** watchdog → root systemd *system* service (verify-revert + true-time + browser-policy) **+ fold blacklisted-window-kill into the same tick** (deletes Phase 8 as a service; ≤60s accepted).
3. **Sign via the control CLI through pkexec/sudo** — root key = sole signer, quota in-CLI (deletes ROOT-03; satisfies ROOT-04 by construction).
4. **LXCF-01 instance** — rewrite live config to the `blocking:` schema + re-sign via the control CLI (curfew 20:45 as sanctioned re-baseline).
5. **06-01 repo hygiene** — keep, off the critical path.

**Explicitly cut/deferred:** ROOT-03 socket helper → DELETED · Phase 8 separate service → FOLDED · Phase 10 Tauri port → DEFERRED post-milestone · LXCF-02 parity → SHRUNK to "Python parses new schema" · Phase 9 ActivityWatch → parked (orthogonal analytics).

---

## Outcome — decisions adopted (user, 2026-06-22)

| Decision | Choice | Effect |
|---|---|---|
| ROOT-03 signing path | **Delete socket → sign via `sudo`/control-CLI** | ROOT-03 redefined; no daemon/socket; sudo prompt = anti-impulse friction |
| Phase 8 native blocker | **Fold into the root watchdog tick** | NBLK-01/02/03 redefined; no separate service; ≤60s leakage accepted |
| Phase 10 app | **Keep in v2.0, but Tauri → omarchy TUI** | PORT-01/02/03 redefined: terminal/TUI, *aether*-themed, **thin client over the one Python stack** (calls control-CLI to sign; no 2nd crypto stack) |
| Structure | **Keep 3 phases (6/7/8), curated** | Not collapsed; each phase curated in place |
| LXCF-02 | **Narrowed** | Single Python stack reads+signs the new schema; Rust classifier agrees on shape only (repo hygiene); cross-language byte-parity no longer a runtime requirement |

**Applied to:** `PROJECT.md` (Active + Key Decisions), `REQUIREMENTS.md` (ROOT/NBLK/PORT/LXCF-02 + curation banner + P0), `ROADMAP.md` (v2.0 overview + Phase 7/8/10 details, checklist, progress).

**Unchanged:** Phase 6 plans 06-01 (Rust classifier — the deliberate ≥10% add-back for publishable-repo hygiene) and 06-02 (instance re-baseline) stand; 06-02's parity task is now repo-hygiene rather than a runtime gate.

**P0 still open (highest risk):** restore + version-control the Python trust stack (`ngcommon.py`/`guard.py`/control-CLI/`nightguard_watchdog.py`) — currently absent/untracked, and the standing 06-02 / Phase-7 blocker.

---
*Raw reviewer output: `.planning/phases/.review-out/claude.txt`. Gemini (no API key) and Codex (401) were unauthenticated this run.*
