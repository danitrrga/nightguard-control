# Phase 9: StayFree Desktop - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning (gated on a Wayland-blocking spike — see D-09)
**Re-scoped:** from "ActivityWatch" → "StayFree Desktop" on 2026-06-23 after a feasibility
investigation into integrating StayFree (see `<investigation>`).

<domain>
## Phase Boundary

Make **StayFree desktop** (AUR `stayfree-desktop`, an Electron AppImage) the **primary
app + website blocker and analytics source** on Linux, and make it **inescapable** by
having the **root watchdog keep it alive** (respawn if the user kills it).

> **SUPERSEDED 2026-06-23 (planning decision):** The original draft demoted Phase 8's root
> SIGKILL to a "backstop floor" for `steam`/`discord`. But Phase 8 was **descoped and reverted
> from the live stack** earlier the same day (commit `8055b86`: "native-app blocking not
> needed; the curfew layer is sufficient") — that code no longer exists. Per the user's
> planning decision, **D-05 is dropped**: the **hard floor is the curfew layer** (Claude-Code
> hook block + root config-revert + root-locked StayFree browser policy), NOT a Phase 8
> native-kill. D-02/D-05/D-06 below are revised accordingly. On spike-FAIL there is **no
> native app-kill** — accepted, consistent with the 18:59 descope.

> **RE-OPENED / RESOLVED 2026-06-24 (D-09 spike result = FAIL).** The gating spike ran on this
> box (Hyprland/Wayland) and returned **FAIL**: `stayfree-desktop` records **0 sessions**
> (`usage.db` empty, Dashboard `0s`) — it cannot track and therefore cannot block native *or*
> XWayland apps. See `09-NOTES-spike-verdict.md` (`## Verdict: FAIL` + `## Fallback resolution`).
> Resolution per D-09: **StayFree = analytics-only** (and degraded — no live data on Wayland);
> the **keep-alive supervisor (09-02) is NOT built** and `nightguard_watchdog.py` is unchanged;
> there is **no native-app hard guarantee** in this phase (hard floor = the curfew layer). The
> in-scope items below (install + keep-alive) are therefore superseded by the FAIL branch (09-03).
> **Correction to "Out of scope" / `<investigation>` below:** syncing StayFree's blocklist was
> marked *proven infeasible*, but that was about the browser-extension cloud list. The **desktop
> app's** `config.db` exposes the full blocklist **offline** (categories + brands + schedules) —
> so a list-import into Nightguard's own enforcement IS feasible. That is a **NEW future phase**,
> deferred for scoping, not re-opened here. Existing decisions below are preserved as history.

**In scope:**
- Install + configure `stayfree-desktop` as the primary blocker.
- A **keep-alive supervisor** folded into the existing root `nightguard_watchdog.py` `tick()`
  (runuser→user-session bridge, same pattern as the Phase 8 enumerate/kill) that respawns
  StayFree if it is not running.
- StayFree analytics replace the (now retired) ActivityWatch idea (TRAK-01/02).
- ~~Retain Phase 8's root native-kill for `steam`/`discord` as a backstop.~~ **DROPPED** (see
  SUPERSEDED note above): the curfew layer is the hard floor; Phase 8 native-kill stays
  descoped/reverted and is NOT re-instated by this phase.

**Out of scope:**
- Syncing StayFree's blocklist into nightguard's config (proven infeasible — see `<investigation>`).
- Editing/patching StayFree itself (closed-source, minified, auto-updates).
- Root-locking StayFree's rule store (rejected — accept the type-test as the soft tier, D-06).
- Browser-extension layer (P6/P7) and the TUI (P10).

</domain>

<investigation>
## Feasibility Investigation (2026-06-23) — why the original "sync StayFree's list" plan was dropped

The user's first idea was a daily script that extracts the StayFree **browser-extension**
settings and applies the app/website list to nightguard's Hyprland window-kill. Tested three
ways against the user's real data and **rejected**:

| Source tested | Result |
|---|---|
| StayFree settings export JSON | 2 of 13 targets syncable (**15%**); the **curfew rule (21:30–06:45) is 0% syncable** — pure category IDs |
| Live extension `Local Extension Settings` leveldb (readable when browser closed) | holds **usage/activity log** + category-ID rules, **no category→domain table** |
| Category/brand resolution | lives in **StayFree's cloud**, not on disk — no local "list of domains" exists to extract |

**Root cause:** StayFree blocks by **opaque cloud-resolved `categoryId`/`brandId` pointers**
(e.g. the night rule = `[-1,-2,-5,-6,-7,-8]`), not by stored domains. Also: websites are
enforced by **URLBlocklist** (browser policy), not by the Hyprland window-kill (a browser
window's class is just `chromium`); and `desktopAppIds` was empty (the extension tracks no
native apps). PoC extractor + raw-store probes: `09-spike-sf_extract.py` (read-only).

**Pivot:** instead of syncing StayFree's list *out*, install **StayFree desktop** as the
blocker itself and make it inescapable via a root keep-alive supervisor.

</investigation>

<decisions>
## Implementation Decisions

### Architecture (the role split)
- **D-01:** **StayFree desktop is the primary blocker** (apps + websites, categories,
  schedules) and the **analytics source** — retiring the parked ActivityWatch idea entirely.
- **D-02 (revised 2026-06-23):** **nightguard root watchdog = StayFree keep-alive supervisor**,
  not the primary blocker and **not a native-kill backstop**. Its new job is to *keep StayFree
  alive*. The existing curfew-layer steps (config-revert, browser-policy) remain; no native-kill
  step is added (Phase 8 stays descoped).

### Keep-alive supervisor (the "I cannot escape" mechanism)
- **D-03:** Fold a **keep-alive step into the existing root `nightguard_watchdog.py` `tick()`**
  — no new service. Each tick: check whether StayFree is running in the user session; if not,
  **respawn it** via the `runuser`→user-session bridge (same `XDG_RUNTIME_DIR` / HIS pattern
  proven in Phase 8, see `08-NOTES-hyprland-from-root.md`).
- **D-04:** Respawn cadence = the watchdog tick (≤60s gap accepted for v1, consistent with
  Phase 8's leakage budget). Detect "already running" (e.g. `pgrep`) to avoid duplicate instances.

### Hard floor (the root-owned guarantee) — REVISED
- **D-05 (DROPPED 2026-06-23):** ~~Keep Phase 8's root SIGKILL for `steam`/`discord` as a
  backstop.~~ Phase 8 was descoped + reverted (`8055b86`); there is no native-kill code to
  retain. **The hard floor is the curfew layer**: the Claude-Code hook block + root
  config-revert + root-locked StayFree **browser** policy (the already-shipped enforcement).
  This phase does **not** re-instate native app-kill. If steam/discord hard-blocking is later
  wanted, that is a new phase, not this one.

### Rule-tampering posture (accepted residual risk)
- **D-06 (revised 2026-06-23):** StayFree's own block/schedule rules are protected **only by
  its type-test (Strict Mode) friction** — accepted as the *soft tier*. The user can still
  reconfigure StayFree's rules at 3am by routing around the type-test; we **do not** root-lock
  StayFree's rule store (it cloud-syncs). With D-05 dropped, there is **no native-app hard
  guarantee** in this phase — the only hard enforcement is the curfew layer (browser/website +
  config-revert + hook), which does not cover native desktop apps. This is an eyes-open
  acceptance, consistent with the 2026-06-23 decision that "native blocking is not needed."
- **Implication:** "keep StayFree running" closes the *quit-the-app* escape for StayFree's own
  (soft) blocking, NOT the *reconfigure-the-rule* escape and NOT native-app blocking.

### Gating spike (run FIRST, before any build)
- **D-09:** **Prove StayFree desktop actually *blocks* (not merely tracks) under
  Hyprland/Wayland.** Many desktop blockers inspect X11 windows that don't exist on Wayland.
  - If it **blocks** → proceed with D-01..D-06 as written.
  - If it **only tracks / cannot block on Wayland** → fall back: StayFree = analytics-only,
    **Phase 8 stays primary**, and the keep-alive supervisor is moot. Re-open this CONTEXT.

### Claude's Discretion
- Exact respawn invocation (`runuser -u danitrrga -- env … /usr/bin/stayfree`), the
  is-running probe, and how StayFree is first launched/logged-in are planning details.
- Whether the keep-alive runs every tick or only during curfew (lean: every tick, since
  StayFree's own schedule governs *when* it blocks; but confirm in planning).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The watchdog this phase extends
- `LifeOS/scripts/nightguard/nightguard_watchdog.py` — the root systemd-system oneshot
  `tick()`; the keep-alive supervisor (D-03) folds in here alongside the existing
  config-revert + browser-policy + Phase 8 native-kill steps.
- `LifeOS/scripts/nightguard/guard.py` — `decide()` / verdict, `true_unix()`; consulted if
  keep-alive is curfew-gated.
- `LifeOS/scripts/nightguard/ngcommon.py` — config/state helpers.

### Phase 8 (the proven root→user bridge — backstop NOT retained, see D-05 DROPPED)
- `.planning/phases/08-native-blocker/08-NOTES-hyprland-from-root.md` — the verified
  `runuser`→user-session bridge (XDG_RUNTIME_DIR, HIS discovery) reused for respawn (D-03).
  **This is the only Phase 8 artifact still load-bearing for Phase 9.**
- `.planning/phases/08-native-blocker/08-CONTEXT.md` — D-01..D-10 of the native kill.
  **Historical only:** Phase 8 was descoped + reverted (`8055b86`); its native-kill is NOT
  re-instated and is NOT a Phase 9 backstop (D-05 dropped).

### Investigation artifacts (this phase's pivot rationale)
- `.planning/phases/09-stayfree-desktop/09-spike-sf_extract.py` — read-only PoC proving the StayFree-sync path is ~15% / 0%-curfew.
- StayFree settings export (user's vault): `LifeOS/vault/4 - Documents/rough material - sort/StayFree Settings 2025-10-29T09_52_31.176Z.json`.
- AUR: `stayfree-desktop` 3.4.0 — prebuilt AppImage from `github.com/stayfree-app/desktop-releases`, installs as `/usr/bin/stayfree`. `license=unknown` (closed source).

### Config + requirements
- `LifeOS/nightguard/config.yaml` — `blocking.native_apps` (steam/discord backstop),
  `blocking.browser_extension` (StayFree extension force-install, separate from this phase).
- `.planning/REQUIREMENTS.md` — TRAK-01, TRAK-02 (re-sourced from StayFree analytics).
- `.planning/ROADMAP.md` §"Phase 9: StayFree Desktop" — re-scoped goal + gating spike + criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `nightguard_watchdog.py:tick()` — host function; keep-alive (D-03) is a new step, same
  shape as the Phase 8 native-kill (enumerate→act→log).
- The Phase 8 `runuser`/`env XDG_RUNTIME_DIR=/run/user/1000 HYPRLAND_INSTANCE_SIGNATURE=$HIS`
  bridge — reused to **launch** StayFree as the user from the root service (respawn).
- `_log(...)` watchdog logging convention — record respawn events (class, pid).

### Established Patterns
- Watchdog is a systemd **system oneshot** (one tick per fire) — keep-alive must be
  tick-shaped (check-then-respawn), not a persistent supervisor loop.
- No Phase 8 native-kill exists in `tick()` (descoped + reverted, `8055b86`); the keep-alive
  step is added next to the existing config-revert + browser-policy steps, not next to a kill.

### Integration Points
- New keep-alive step slots into `tick()` next to the Phase 8 kill; both use the same
  user-session bridge. Order vs the kill step is a planning detail.

</code_context>

<specifics>
## Specific Ideas

- StayFree's **type-test (Strict Mode)** is the feature the user values — keep it as the
  soft-tier commitment device (D-06).
- StayFree desktop AppImage cold-start is non-instant; respawn has the same ≤60s leakage as
  the Phase 8 kill (accepted).

</specifics>

<deferred>
## Deferred Ideas

- **Root-locking StayFree's rule store** so even the user can't reconfigure curfew rules —
  rejected for v1 (cloud-sync fragility); revisit only if the type-test proves insufficient
  *with evidence*.
- **Browser-policy hole (noted, not actioned this phase):** `/etc/{chromium,brave}/policies/managed/`
  are **world-writable (0777)** with **user-owned** `nightguard.json`, and the watchdog only
  *logs* `MISSING browser policies` — it never restores them. So the shipped "browser block"
  is currently bypassable (`rm` the policy, no sudo). User chose "**just note it for now**"
  (2026-06-23). Should become its own gap-closure: chown root:root, lock dir 0755, make the
  watchdog re-write tampered/missing policies.
- **Instant respawn / sub-60s** via a persistent root-side listener — only if 60s leakage
  proves inadequate with evidence.

</deferred>

---

*Phase: 9-stayfree-desktop*
*Context gathered: 2026-06-23*
