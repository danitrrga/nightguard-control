# Phase 9: StayFree Desktop - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning (gated on a Wayland-blocking spike — see D-09)
**Re-scoped:** from "ActivityWatch" → "StayFree Desktop" on 2026-06-23 after a feasibility
investigation into integrating StayFree (see `<investigation>`).

<domain>
## Phase Boundary

Make **StayFree desktop** (AUR `stayfree-desktop`, an Electron AppImage) the **primary
app + website blocker and analytics source** on Linux, and make it **inescapable** by
having the **root watchdog keep it alive** (respawn if the user kills it). Phase 8's root
SIGKILL is **demoted to a backstop floor** for the critical native apps (`steam`/`discord`)
so a root-owned hard guarantee survives even if StayFree's user-editable rules are changed.

**In scope:**
- Install + configure `stayfree-desktop` as the primary blocker.
- A **keep-alive supervisor** folded into the existing root `nightguard_watchdog.py` `tick()`
  (runuser→user-session bridge, same pattern as the Phase 8 enumerate/kill) that respawns
  StayFree if it is not running.
- StayFree analytics replace the (now retired) ActivityWatch idea (TRAK-01/02).
- Retain Phase 8's root native-kill for `steam`/`discord` as a backstop.

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
- **D-02:** **nightguard root watchdog = supervisor + backstop**, not the primary blocker.
  Its new job is to *keep StayFree alive*, not to enumerate/kill the full app set.

### Keep-alive supervisor (the "I cannot escape" mechanism)
- **D-03:** Fold a **keep-alive step into the existing root `nightguard_watchdog.py` `tick()`**
  — no new service. Each tick: check whether StayFree is running in the user session; if not,
  **respawn it** via the `runuser`→user-session bridge (same `XDG_RUNTIME_DIR` / HIS pattern
  proven in Phase 8, see `08-NOTES-hyprland-from-root.md`).
- **D-04:** Respawn cadence = the watchdog tick (≤60s gap accepted for v1, consistent with
  Phase 8's leakage budget). Detect "already running" (e.g. `pgrep`) to avoid duplicate instances.

### Backstop floor (the root-owned hard guarantee)
- **D-05:** **Keep Phase 8's root SIGKILL for `steam`/`discord`** as a root-signed backstop
  that StayFree's UI/account cannot reconfigure away. This is the hard floor; StayFree is the
  soft+broad layer on top. Phase 8 is **demoted, not deleted**.

### Rule-tampering posture (accepted residual risk)
- **D-06:** StayFree's own block/schedule rules are protected **only by its type-test
  (Strict Mode) friction** — accepted as the *soft tier*. The user can still reconfigure
  StayFree's rules at 3am by routing around the type-test (web dashboard / leveldb edit); we
  **do not** try to root-lock StayFree's rule store (too fragile — it cloud-syncs). The hard
  guarantee for the apps that matter comes from the D-05 backstop, not from StayFree.
- **Implication:** "keep it running" closes the *quit-the-app* escape, NOT the
  *reconfigure-the-rule* escape. This is a deliberate, eyes-open downgrade vs Phase 8's
  root-signed blacklist, traded for StayFree's UX/analytics/category breadth.

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

### Phase 8 (the proven root→user bridge + the backstop being retained)
- `.planning/phases/08-native-blocker/08-NOTES-hyprland-from-root.md` — the verified
  `runuser`→user-session bridge (XDG_RUNTIME_DIR, HIS discovery) reused for respawn (D-03).
- `.planning/phases/08-native-blocker/08-CONTEXT.md` — D-01..D-10 of the native kill that
  becomes the D-05 backstop (SIGKILL-by-pid, substring class match, `steam`/`discord`).

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
- Phase 8 native-kill (`steam`/`discord`) stays in `tick()` unchanged as the D-05 backstop.

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
