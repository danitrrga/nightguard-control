# Ingest Conflicts — Linux Port Brief

**Generated:** 2026-06-22
**Mode:** merge (`.planning/` present)
**Docs ingested:** 1
**Precedence rule:** `ADR > SPEC > PRD > DOC` (default)
**Destination write status:** ✅ **RESOLVED via new milestone** — the Bucket-C contradictions were intentional supersessions of the *completed* v1.0 milestone, so an in-place merge was correctly blocked. Routed instead to **milestone v2.0 · Linux Port** (user-confirmed 2026-06-22). PROJECT.md / REQUIREMENTS.md / ROADMAP.md / STATE.md were then updated under the new-milestone flow, not by a merge-append. Milestone-open decisions: **Linux-only** (retire Windows paths) · **root commit-helper over a Unix socket** (B1) · no research pass.

## Documents

| Path | Type | Precedence | Notes |
|------|------|-----------|-------|
| `docs/linux-port-brief.md` | DOC | 4 (lowest) | Brainstorm capture, dated 2026-06-22. Self-describes as seeding a **new v2.0 milestone** that "supersedes/extends" the Windows-era requirements. |

No inter-document conflicts (single doc). All conflicts below are **doc-vs-existing-locked-planning**.

## Existing planning baseline

- Milestone **v1.0** — `status: milestone_complete` (STATE.md). All 23 v1 requirements mapped and complete; 5 phases done.
- The brief does not edit v1.0 — it proposes a *successor* milestone. That framing is the crux of the routing decision below.

---

## Bucket A — Auto-resolved

*(none)* — single doc, no precedence arbitration was needed.

---

## Bucket B — Competing variants (brief proposes, but leaves open)

These are unresolved **within the brief itself** — they are open design questions the brief flags, not contradictions with existing planning. They become real phase-planning decisions if this is routed to a milestone.

| # | Topic | Variants | Brief's lean |
|---|-------|----------|--------------|
| B1 | App→sanctioned-write path under a root-owned key | (1) root "commit helper" over Unix socket; (2) `pkexec`/polkit per commit; (3) keep key user-readable | **Option 1** (recommended in brief) |
| B2 | Native-app block mechanism | SIGKILL the process vs `hyprctl dispatch closewindow` (gentler) | undecided; "pick per-app or global" |
| B3 | StayFree extension lock-down depth | policy-lock disable/uninstall only vs also add `URLBlocklist` belt-and-suspenders | undecided |

---

## Bucket C — Unresolved blockers (contradict LOCKED v1.0 decisions)

The brief is a **platform + trust-architecture pivot**. Each item below directly contradicts a decision currently locked in the completed v1.0 milestone. Under the merge-mode BLOCKER rule these prevent an in-place merge into the existing PROJECT/REQUIREMENTS/ROADMAP — **but every one is an *intentional supersession* tied to the new milestone**, which is exactly why this should route to a new milestone rather than be force-merged or discarded.

| # | Locked v1.0 decision | Brief supersedes with | Locked in |
|---|----------------------|------------------------|-----------|
| C1 | **Platform: Windows-only** (DPAPI, PowerShell guard) | Linux-only (CachyOS + Hyprland); Windows path retired for personal instance | PROJECT.md Constraints; REQUIREMENTS.md Out-of-Scope |
| C2 | **Cross-platform (Linux) is Out of Scope** — "DPAPI + PowerShell guard are Windows-bound" | Linux becomes the *primary and only* target | PROJECT.md Out-of-Scope; REQUIREMENTS.md Out-of-Scope |
| C3 | **KERN-02: key at rest via Windows DPAPI (CurrentUser)** | File-based `.guardkey` (0600, 32 bytes), **root-owned** | REQUIREMENTS.md KERN-02 (Validated/complete) |
| C4 | **Enforcement guard is PowerShell** (GARD-01..06) on a Windows Scheduled Task | Python `nightguard_watchdog.py` as a **systemd system service** | REQUIREMENTS.md GARD-*; ROADMAP Phase 3 |
| C5 | **Trust model: "DPAPI app is sole signer"** — app (user) holds/derives the key and signs in-process | Root owns the key; app (user) **cannot sign**; signing moves behind a root commit-helper / privilege boundary (Bucket B1) | PROJECT.md Key Decisions; whole Trust-Kernel design |
| C6 | **Interop invariant: Rust app ↔ PowerShell guard verify the same DPAPI blob** | Rust engine ↔ Python watchdog over a file key; PowerShell interop retired | CLAUDE.md interop invariants; KERN-01/02 |

### New scope the brief ADDS (v1.0 explicitly deferred or never had these)

Not contradictions, but net-new requirements that only make sense inside the new milestone:

- **Native-app blocking** during curfew (Hyprland window-class blacklist) — v1.0 had no native-app enforcement.
- **Usage tracking via ActivityWatch** — replaces StayFree analytics (StayFree has no native Linux client).
- **Browser blocking via the StayFree Chromium extension**, force-installed by a root managed policy and locked alive (extension ID `elfaihghhjjoknimpccccmkioofjjfkf`, verified).

### Consistent with v1.0 (NOT conflicts — carried forward intact)

- "Making the system literally unbreakable is **out of scope** — friction past the impulse threshold, not an absolute lock." The brief preserves this exactly (root = `sudo` is the past-the-impulse threshold; admin can still break it).
- HMAC-signed config + auto-revert to a sanctioned snapshot — carried over (`config.sanctioned.yaml`).
- Tauri/Rust app is the **sole sanctioned editor** — unchanged; the Rust engine ports as-is.

---

## Brief's proposed phases (seed for the new milestone)

| Phase | Title | Value | Maps to blockers/scope |
|-------|-------|-------|------------------------|
| P1 | Config cleanup — retire dead Windows `uwp`/StayFree `package_id`; redefine targets as `browser_extension` + `native_apps` | low-risk first | new scope |
| P2 | Root integrity wall *(highest value)* — `.guardkey` + sanctioned config → root; watchdog → systemd **system** unit; build root commit helper (socket + quota + sign) | highest | C3, C4, C5, B1 |
| P3 | Native blocker — Hyprland socket2 `openwindow` listener as a `--user` service; curfew-gated kill-by-window-class | high | new scope, B2 |
| P4 | ActivityWatch — install + sync script feeding screen-time into LifeOS | medium | new scope |
| P5 | Tauri port *(biggest lift)* — swap DPAPI key module for socket-to-root-helper client; recompile for Linux; existing Rust engine tests pass unchanged | biggest | C1, C3, C5, C6 |

---

## Recommended routing

Because every Bucket-C item is a **deliberate supersession of a *completed* milestone** (not an edit to in-flight v1.0 work), the correct GSD entry point is **a new milestone (v2.0 · Linux Port)** seeded from this brief — *not* an in-place merge-append into the closed v1.0 ROADMAP, and *not* a hard stop.

→ Route via `/gsd-new-milestone` (v2.0), carrying the 5 proposed phases as the roadmap seed and the Bucket-C supersessions as the explicit "what changes from v1.0" delta. The Bucket-B open questions become discuss/plan-phase decisions (B1 should be settled before P2/P5).

Awaiting routing confirmation (see the question posed in-session).
