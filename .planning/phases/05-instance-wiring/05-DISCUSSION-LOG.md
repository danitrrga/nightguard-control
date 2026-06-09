# Phase 5: Instance Wiring - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-09
**Phase:** 5-Instance Wiring
**Areas discussed:** Cutover & old hook fate, Canonical path & schema, Hook resolution / drift fix, Instance init & safety, Watchdog (live diagnosis)

---

## Cutover & old hook fate

| Option | Description | Selected |
|--------|-------------|----------|
| Full replace | New guard + adapter is sole curfew gate + auto-revert; old hook retired | ✓ |
| New guard + thin adapter, old archived | Same but keep old script for rollback a few days | |
| Side-by-side | New does revert, old keeps the gate; two evaluators | |

**User's choice:** Full replace.
**Notes:** —

### Watchdog fate (sub-question)

| Option | Description | Selected |
|--------|-------------|----------|
| Out of scope — keep separate | Leave watchdog scripts running untouched | |
| Drop it entirely | Retire watchdog with old hook | |
| Bring into product later | Defer, leave running | |

**User's choice (free-text):** "bring into product, but this is running always, use the same code that they had actually. This is just an update of the normal nightguard." → **Later revised** (see Schema) to "rewrite watchdog and adapter for this new design."
**Notes:** Reframed the whole phase: nightguard-control IS the next version of the author's personal nightguard, watchdog included. Plain-text confirmations: (1) watchdog scripts stay in `~/.claude/hooks`; (2) adapter preserves butler messages; (3) per-day schedule carried over.

---

## Canonical path & schema

| Option (data dir) | Description | Selected |
|--------|-------------|----------|
| LifeOS/nightguard | NIGHTGUARD_DIR = LifeOS path; co-locate 5 files; single source of truth | ✓ |
| ~/.claude/nightguard | Keep under ~/.claude where old hook reads | |

| Option (schema) | Description | Selected |
|--------|-------------|----------|
| Preserve as-is, superset | Keep config verbatim; product reads known fields only | |
| Normalize to product schema | Rewrite config to product-canonical; rewrite watchdog + adapter for new design | ✓ |
| You decide | Recommend at plan time | |

**User's choice:** LifeOS/nightguard + "normalize to product schema and rewrite watchdog and adapter for this new design."
**Notes:** This superseded the earlier "keep watchdog as-is" decision.

---

## Watchdog (live diagnosis — user asked "check the watchdog, StayFree is not running and it doesn't trigger StayFree again")

**Finding:** Live demonstration of WIRE-01 drift. `NightguardWatchdog` Scheduled Task is *Running*, but reads stale `~/.claude/nightguard/config.yaml` (`watchdog.enabled: false`, Jun 2) instead of canonical `LifeOS/nightguard/config.yaml` (`enabled: true`, Jun 4). `Invoke-Pass` early-returns every cycle → StayFree never relaunched (watchdog.log: loop start 2026-06-07 12:27, no "restarting" lines after). StayFree confirmed not running.

| Option | Description | Selected |
|--------|-------------|----------|
| Stopgap now + fix in phase | Relaunch + repoint now, proper fix in Phase 5 | |
| Fold into Phase 5 only | No live-env change; capture as WIRE-01 proof-case | ✓ |
| Just relaunch StayFree now | Manual one-off relaunch | |

**User's choice:** Fold into Phase 5 only.
**Notes:** Becomes the acceptance proof-case for WIRE-01. Research item logged: verify StayFree's real UWP process name vs `process_name: StayFree`.

---

## Hook resolution / drift fix

| Option (resolution) | Description | Selected |
|--------|-------------|----------|
| Persistent NIGHTGUARD_DIR env var | One user-level env var, absolute LifeOS path; junction-proof | ✓ (Claude's call) |
| Hardcoded absolute path constant | Baked path; needs override seam for public repo | |
| settings.json env injection | Two mechanisms (hook env + setx) | |

| Option (deploy) | Description | Selected |
|--------|-------------|----------|
| Install/deploy into ~/.claude/hooks | Copy built scripts + re-stamp integrity baseline | ✓ (Claude's call) |
| Run in place from repo checkout | Reference repo path directly | |
| You decide | Recommend at plan time | |

**User's choice (free-text):** "nightguard_dir will be inside their lifeos lifeos/nightguard. the rest i dont really understand what you mean, im stupid i dont know about technology explain yourself better" / "same, no idea what you say."
**Notes:** Confirmed NIGHTGUARD_DIR = LifeOS/nightguard. The resolution mechanism + deploy location are technical implementation — taken off the user's plate and decided by Claude (persistent env var + install-into-hooks with integrity re-stamp), to be confirmed by researcher against the junction blocker. Explained both in plain language.

---

## Instance init & safety

| Option (go-live) | Description | Selected |
|--------|-------------|----------|
| Live immediately, fully armed | Enforce now; 3 tokens, no grace used, curfew 20:45→05:30, watchdog on | ✓ |
| Install but stay off until flipped on | Dormant until enabled | |
| Live immediately, but strict | Start with 0 tokens | |

| Option (safety) | Description | Selected |
|--------|-------------|----------|
| Prove-then-switch | Verify sign/lock/unlock before retiring old hook | ✓ |
| Switch directly | Replace in one step, fix after | |

**User's choice:** Live immediately, fully armed + Prove-then-switch.
**Notes:** —

## Claude's Discretion

- Path resolution mechanism (persistent `NIGHTGUARD_DIR` env var; never resolve relative to script).
- Script deployment (install/update step into `~/.claude/hooks` + hook-integrity SHA256 re-stamp).
- Instance-init internals (fresh DPAPI key, sanctioned seed, signed guard.json via Phase 2 A3 recipe).

## Deferred Ideas

- Watchdog as a first-class product feature (currently a personal-instance rewrite).
- Browser/zen lock hooks (other Hermes-era enforcement surfaces) — future "consolidate discipline hooks" phase.
