# Phase 9: StayFree Desktop - Research

**Researched:** 2026-06-23
**Domain:** Linux desktop time-tracker/blocker (Electron AppImage) under Hyprland/Wayland; root→user keep-alive supervision
**Confidence:** HIGH (on the gating-spike outcome prediction and process/bridge mechanics), MEDIUM (on StayFree's exact local data layout, since the desktop app is closed-source and undocumented)

## Summary

Phase 9 wants `stayfree-desktop` (AUR, an Electron AppImage at `/usr/bin/stayfree`, pinned at 3.4.0) to be the **primary app+website blocker and analytics source**, kept inescapable by a keep-alive step folded into the root `nightguard_watchdog.py` `tick()`. The whole phase is gated on spike **D-09**: prove the desktop app actually *blocks* (not merely tracks) under Hyprland/Wayland before building anything.

The research strongly predicts the spike will **fail (analytics-only fallback)**, but does not pre-empt it — the spike must still be run empirically on this box. Three independent lines of evidence:
1. The AUR PKGBUILD declares X11-only detection dependencies: **`libxss`** (XScreenSaver — idle/active-window), **`libxtst`** (XTEST), **`at-spi2-core`** (AT-SPI accessibility). These are the classic X11 foreground-window/idle-detection mechanisms that do **not** function under Wayland. `[VERIFIED: AUR cgit PKGBUILD]`
2. Two **open, unresolved** upstream issues confirm the app cannot even *track* on Wayland: issue #13 ("Stay free cannot track apps running on wayland platforms", Debian 13 / KDE Plasma Wayland, opened 2026-02-04, no maintainer response) and #10 ("linux (wayland) — Stayfree not noticing/timing other applications"). If it cannot *track* on Wayland, it certainly cannot *block*. `[VERIFIED: github.com/stayfree-app/desktop-releases/issues]`
3. The AUR package `pkgdesc` is literally *"Analytics to help you understand and control your pc usage"* — analytics-forward, not block-forward. Desktop blocking is buggy even on X11 (issue #6: "Can't block single app" → blocks the whole system). `[VERIFIED: AUR cgit PKGBUILD]`

**Primary recommendation:** Plan this phase as a **spike-first, branch-on-result** phase. Wave 0 = the D-09 spike (install + a decisive blocks-vs-tracks test on Hyprland). Gate every build task behind a spike-PASS. Pre-write the **fallback plan** (StayFree = analytics-only viewed in its own UI; Phase 8 stays the primary blocker; keep-alive supervisor is moot/optional) because the evidence says fallback is the likely outcome. Do **not** let the planner schedule keep-alive/respawn build tasks that assume PASS.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| App/website blocking enforcement | StayFree desktop (user session) *if spike PASSes* | Root watchdog Phase 8 native-kill (backstop) | D-01/D-05: StayFree is the broad soft layer; root SIGKILL is the hard floor |
| Keep-alive / respawn supervision | Root watchdog `tick()` (system oneshot) | — | D-03: must live in root so `systemctl --user stop` can't disable it; reaches user session via runuser bridge |
| Foreground-app / idle detection | StayFree (X11 APIs) | — | **This is the spike's failure point on Wayland** |
| Screen-time analytics (TRAK-01/02) | StayFree local store + its own UI / cloud | — | D-01: analytics source; export path unverified (see Open Questions) |
| Critical-app hard guarantee (steam/discord) | Root watchdog Phase 8 SIGKILL-by-pid | — | D-05: root-signed, StayFree cannot reconfigure it away |
| Rule-tamper resistance | StayFree type-test (Strict Mode) only | — | D-06: accepted soft tier; NOT root-locked |

## Standard Stack

This is not a "pick a library" phase — the stack is fixed by the project (closed-source AppImage + existing Python watchdog). The relevant "stack" is the install target and the host code being extended.

### Core
| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| `stayfree-desktop` (AUR) | **3.4.0** (pkgrel 1) | The blocker/analytics app under test | Only Linux distribution path; prebuilt AppImage `[VERIFIED: AUR cgit PKGBUILD]` |
| Upstream AppImage | latest **3.4.1** (2026-06-21) | What the AUR repackages | Releases ~every 1–2 weeks → churn risk `[VERIFIED: github releases page]` |
| `nightguard_watchdog.py` `tick()` | live (LifeOS) | Host for the keep-alive step (D-03) | The systemd **system** oneshot; can't be user-stopped `[VERIFIED: read source]` |
| Phase 8 runuser bridge | verified 2026-06-22 | root→user-session launch path for respawn | Proven in `08-NOTES-hyprland-from-root.md` `[VERIFIED: read notes]` |

### Install target (verified from PKGBUILD)
`[VERIFIED: AUR cgit PKGBUILD, fetched 2026-06-23]`
- Binary installed at **`/usr/bin/stayfree`** — this is the **raw AppImage** itself (`install -Dm755 …AppImage /usr/bin/stayfree`), NOT an extracted tree. The `--appimage-extract` in `prepare()` only harvests the `.desktop` and `.png`; the runtime artifact at `/usr/bin/stayfree` is the self-mounting AppImage.
- Desktop entry: `/usr/share/applications/stayfree-desktop.desktop` with `Exec=/usr/bin/stayfree`.
- Icon: `/usr/share/pixmaps/stayfree-desktop.png`.
- `depends=('zlib' 'hicolor-icon-theme' 'fuse2' 'gtk3' 'libnotify' 'nss' 'libxss' 'libxtst' 'xdg-utils' 'at-spi2-core' 'libsecret')`
  - **`fuse2`** → AppImage self-mounts via FUSE at runtime (relevant to process naming below).
  - **`libxss` + `libxtst` + `at-spi2-core`** → X11 active-window/idle/accessibility detection. **The Wayland-blocking smoking gun.**
  - **`libsecret`** → likely where its login/account token or local secrets are kept (Secret Service / keyring).
- `license=('unknown')` → closed source. Do not plan to patch/inspect internals.
- Source: `https://github.com/stayfree-app/desktop-releases/releases/download/v3.4.0/stayfree-linux-x86_64.AppImage`, sha256 `7a343a61560c9396dbceff8879ca0d10a2c4eddc14ca628b2e47b244e4d2b417`.

**Installation:**
```bash
# AUR helper (paru/yay). NOT a pacman-native package.
paru -S stayfree-desktop      # or: yay -S stayfree-desktop
# Verify:
pacman -Q stayfree-desktop    # currently: NOT installed on this box (verified 2026-06-23)
ls -la /usr/bin/stayfree
```
As of 2026-06-23 the box has **no `stayfree-desktop` installed** and **no stayfree process running** (verified — the spike has not been run yet). `appimagelauncherd` IS running, which can intercept AppImage launches (see Pitfalls).

## Package Legitimacy Audit

> StayFree desktop is a **closed-source prebuilt binary** from a third-party GitHub releases repo, repackaged by an AUR community maintainer. It is not an npm/PyPI package; slopcheck/registry verification does not apply. The relevant trust facts:

| Artifact | Source | Pinned | Integrity | Disposition |
|----------|--------|--------|-----------|-------------|
| `stayfree-desktop` AUR PKGBUILD | aur.archlinux.org (maintainer: bailwillharr) | 3.4.0-1 | community PKGBUILD; sha256 pins the AppImage | Approved with caveats |
| `stayfree-linux-x86_64.AppImage` | github.com/stayfree-app/desktop-releases | v3.4.0 | sha256 `7a343a6…` in PKGBUILD | Approved; closed-source — treat as untrusted-internals |

**Trust posture for the planner:** This is a closed-source binary running in the user's session with X11/accessibility access. It is *not* part of the cryptographic trust kernel and must never be given the `.guardkey` or any signing role. Its rules are user-editable and cloud-synced (D-06). The hard guarantee remains the root watchdog + Phase 8 backstop, not StayFree.

## Architecture Patterns

### System flow (intended, IF spike PASSes)

```
                       systemd system timer (60s)
                                │  fires
                                ▼
                  nightguard_watchdog.py  tick()   [root]
        ┌───────────────────────┼───────────────────────────┐
        ▼                       ▼                             ▼
  verify_and_revert      browser-policy check         [NEW] keep-alive (D-03)
  (config integrity)     (extension force-install)    is StayFree running?
                                                        │  no
                                                        ▼
                                       runuser -u danitrrga -- env
                                       XDG_RUNTIME_DIR=/run/user/1000
                                       HYPRLAND_INSTANCE_SIGNATURE=$HIS
                                       /usr/bin/stayfree   (respawn into session)
        ┌───────────────────────┼───────────────────────────┐
        ▼                                                     ▼
  [retained] Phase 8 native-kill (steam/discord)        _log() one summary line
  SIGKILL-by-pid via same runuser bridge (D-05 backstop)
```

The keep-alive step is the **same shape** as the Phase 8 native-kill: discover `$HIS` → act-as-user via runuser → log. It is a check-then-act per tick, **never a persistent supervisor loop** (the watchdog is a oneshot).

### Pattern: tick-shaped check-then-respawn (D-03/D-04)
**What:** Each tick, probe whether StayFree is alive in the user session; if not, launch one instance via the runuser bridge.
**When to use:** Inside `tick()`, after the existing steps. Per Claude's-discretion note in CONTEXT, lean = run **every tick** (StayFree's own schedule governs *when* it blocks), but confirm in planning.
**Probe + respawn (recommended shape — see is-running probe section for the exact pattern):**
```python
# pseudo, inside tick() — runs as root, acts as the user
import subprocess
HIS = _discover_his()  # ls /run/user/1000/hypr — same as Phase 8, re-discover each tick
RUNUSER = ["runuser", "-u", "danitrrga", "--",
           "env", "XDG_RUNTIME_DIR=/run/user/1000",
           f"HYPRLAND_INSTANCE_SIGNATURE={HIS}"]

def _stayfree_running():
    # pgrep in the GLOBAL pid namespace (root sees all); match the binary path,
    # not a bare 'stayfree' comm (Electron forks children — see Pitfalls).
    r = subprocess.run(["pgrep", "-f", "/usr/bin/stayfree"], capture_output=True)
    return r.returncode == 0

if HIS and not _stayfree_running():
    subprocess.Popen(RUNUSER + ["/usr/bin/stayfree"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    _log("keep-alive: respawned StayFree")
```
Note: `pgrep` runs fine **as root** (global pid view) — it does NOT need the runuser bridge; only the *launch* does. This is simpler than Phase 8's enumerate step (which needed hyprctl, hence runuser).

### Anti-patterns to avoid
- **Persistent supervisor loop inside the oneshot.** The watchdog fires once per timer tick and exits. A `while True` would hang the oneshot. Keep it check-then-act.
- **Caching `$HIS`.** It rotates on every Hyprland restart — re-discover every tick (Phase 8 invariant).
- **Matching `pgrep stayfree` (comm-only).** Electron truncates `comm` to 15 chars and forks zygote/renderer children; bare-name matching is ambiguous. Use `pgrep -f /usr/bin/stayfree`.
- **Launching without dedup.** Always probe-then-launch; never unconditionally respawn (would spawn duplicate instances).
- **Giving StayFree any trust-kernel role.** It is closed-source; never near the `.guardkey`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| root→user session launch | a custom setuid helper / dbus dance | the **existing Phase 8 runuser+env(XDG_RUNTIME_DIR,HIS) bridge** | Already verified end-to-end (`08-NOTES`); CAP_DAC_OVERRIDE traverses the 0700 dirs, no perm changes |
| "is it running" check | parse `ps aux` output / window enumeration | `pgrep -f /usr/bin/stayfree` (root, global pid view) | Simpler than hyprctl; no session bridge needed for the probe |
| supervision cadence | a new systemd service/timer | fold into existing `tick()` | D-03: a new `--user` service is user-stoppable; the whole point is it can't be |
| app blocking itself | re-implementing a window-watcher | **StayFree if spike PASS, else Phase 8 native-kill** | Don't rebuild a blocker; that's exactly what the spike decides |

**Key insight:** Almost nothing new is needed mechanically — the runuser bridge and the tick() host already exist. The phase's real work is (a) the spike decision and (b) wiring ~15 lines into tick(). The risk is entirely in the spike outcome, not implementation difficulty.

## The D-09 Gating Spike (design it concretely)

This is the most important deliverable for the planner. Design the spike as a **decisive, observable blocks-vs-only-tracks test on this Hyprland/Wayland box**, run **before any build task**.

### Spike hypothesis
StayFree desktop detects the foreground app/window via X11 APIs (`libxss`/`libxtst`/`at-spi2-core`). Under Hyprland (Wayland), native Wayland windows are invisible to those APIs. Therefore StayFree will **fail to even track** native Wayland apps, and consequently **cannot block** them. (XWayland apps like Steam *might* be visible to it — test both.)

### Spike steps (Wave 0, ordered)
1. **Install:** `paru -S stayfree-desktop`; confirm `/usr/bin/stayfree` exists and launches a window under Hyprland. Record: does it launch directly, or does `appimagelauncherd` intercept it (prompt to integrate)?
2. **First-run / login:** complete account login (StayFree desktop requires/uses an account for sync — see First-Run). Record where it lands and whether login is mandatory for blocking to work.
3. **Tracking test (necessary precondition for blocking):** with StayFree open, switch focus between (a) a **native Wayland** app (e.g. a Hyprland-native terminal/editor), and (b) an **XWayland** app (e.g. Steam, `xwayland: true` per Phase 8 notes). After a few minutes, check StayFree's own usage UI. **Observable PASS:** StayFree shows nonzero, app-attributed time for the native Wayland app. **Observable FAIL:** native app shows zero/“unknown”/desktop-wide blob (matches issues #13/#10).
4. **Blocking test (the actual D-09 question):** create a StayFree schedule/limit/Focus-Mode rule that should **block** a specific app right now. Launch that app. **Observable PASS:** StayFree actively closes it, or shows a blocking overlay/prevents focus, repeatably. **Observable FAIL:** the app opens and stays usable; or "blocking a single app blocks the whole system" (matches issue #6).
5. **Website blocking test (secondary):** add a website limit/block for a domain; open it in the browser. Note: per the prior investigation, web blocking is enforced by **browser URLBlocklist policy**, not by StayFree watching windows — so this may "work" via the browser-policy layer independently of the Wayland question. Record separately; don't let a web-block PASS mask an app-block FAIL.

### Decisive PASS/FAIL criteria (write these into the plan)
- **PASS (proceed with D-01..D-06):** Step 4 shows StayFree **actively prevents/closes** at least native-app targets on Hyprland, repeatably, with the app correctly attributed in Step 3.
- **FAIL → fallback (the predicted outcome):** Step 3 shows StayFree cannot attribute native Wayland app time (or Step 4 shows it cannot block them). Then:
  - StayFree = **analytics-only**, sourced however Step 3 reveals (likely XWayland-app + browser-extension data only).
  - **Phase 8 native-kill stays PRIMARY** for the critical apps.
  - **Keep-alive supervisor (D-03/D-04) becomes moot** — do NOT build it (a tracker doesn't need root-enforced uptime). Optionally keep a *lightweight* keep-alive purely so analytics keep flowing, but that's a downgrade decision, not a guarantee.
  - **Re-open `09-CONTEXT.md`** per D-09.
- **PARTIAL (XWayland blocks, native-Wayland doesn't):** treat as FAIL for the guarantee (the user's escape apps may be native Wayland), but note it.

### Optional XWayland-forcing experiment (only if Step 4 FAILs)
Electron/Chromium can be forced onto X11 via `--ozone-platform=x11`, and StayFree's *own* X11 detection of *other* apps would still require those apps to be X11/XWayland — forcing StayFree itself to X11 does **not** make native Wayland apps visible to it. So this is unlikely to rescue the spike, but a quick `/usr/bin/stayfree --ozone-platform=x11` run can be tried to rule it out. Do not over-invest; the detection target (other apps) is the blocker, not StayFree's own renderer.

## First-Run / Login / Local Data (MEDIUM confidence — closed-source, undocumented)

`[ASSUMED]` except where noted:
- StayFree desktop is account-based and **cloud-syncs** rules/categories (consistent with the prior investigation: categories resolve in StayFree's cloud, not on disk). Expect a **login screen on first run**; blocking rules likely require an account. Confirm in spike Step 2.
- **Local storage location (to discover during spike):** Electron apps store under `~/.config/<AppName>/` (Chromium profile: `Local Storage`, `IndexedDB`, leveldb). The browser-extension investigation found rules in a `leveldb` under `Local Extension Settings`; the desktop app likely uses an analogous Electron `~/.config/StayFree*/` leveldb. **`libsecret` dependency** suggests the auth token sits in the Secret Service keyring, not a flat file. The planner should add a spike sub-step: after login, `ls -la ~/.config/ | grep -i stay` and inspect for a leveldb/IndexedDB.
- **Strict Mode / type-test (D-06):** the friction feature the user values. Configured in StayFree's settings; it's a soft commitment device only — the user can still route around it (web dashboard / leveldb edit). Do not attempt to root-lock it.

## TRAK-01 / TRAK-02 — Analytics source

> **STALE REQUIREMENT WARNING:** `.planning/REQUIREMENTS.md` lines 81–82 still describe TRAK-01/02 in **ActivityWatch** terms ("ActivityWatch is installed with aw-watcher-window…", "…replacing StayFree desktop analytics"). This contradicts the 2026-06-23 re-scope (ROADMAP §Phase 9 + CONTEXT D-01 retire ActivityWatch and source analytics **from** StayFree). The planner must treat the ROADMAP/CONTEXT intent as authoritative and should flag/propose a REQUIREMENTS.md rewrite of TRAK-01/02 to match. `[VERIFIED: read REQUIREMENTS.md + ROADMAP.md]`

**Re-scoped intent (per CONTEXT D-01 / ROADMAP):**
- **TRAK-01:** StayFree desktop is installed and is the screen-time/analytics source (replacing the parked ActivityWatch). Acceptance hinges on the spike: if tracking works on Wayland → StayFree is the source; if not → only XWayland-app + browser data are captured, and the planner must state that gap explicitly.
- **TRAK-02:** "Export analytics into LifeOS." **Likely answer: there is no clean local export.** Categories/brands resolve in StayFree's cloud; the local store is an Electron leveldb of usage logs without a domain/category table (per the prior browser-extension investigation, which applies by analogy). **Acceptable v1 answer per CONTEXT scope: "view in StayFree's own UI"** — state that plainly rather than inventing a fragile leveldb-scraper. If a scraper is wanted later, it's a separate deferred gap, not part of this phase's guarantee. Confirm the actual desktop local-store shape during the spike before committing to any export task.

## Runtime State Inventory

> Rename/refactor categories largely N/A (this is an install+wire phase, not a rename). Answered explicitly:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | StayFree creates a new Electron profile under `~/.config/StayFree*/` on first run; cloud-synced account state | None to migrate; discover layout during spike |
| Live service config | StayFree rules live in StayFree's cloud + local leveldb, user-editable (D-06) — **NOT** in git, **NOT** root-locked (deliberate) | None — accepted soft tier |
| OS-registered state | New `/usr/share/applications/stayfree-desktop.desktop` (from AUR); optional autostart entry (StayFree tray autostart is buggy per issue #7) | Keep-alive in watchdog supersedes autostart reliability (IF spike PASS) |
| Secrets/env vars | StayFree auth token likely in Secret Service (libsecret keyring) — **separate from and irrelevant to** `.guardkey`; no nightguard secret changes | None |
| Build artifacts | AppImage at `/usr/bin/stayfree`; AUR pin 3.4.0 vs upstream 3.4.1 already diverged | Auto-update churn — see Pitfalls |
| Watchdog code | `nightguard_watchdog.py` `tick()` gains a keep-alive step alongside Phase 8 native-kill (IF spike PASS) | Code edit (live LifeOS file) |
| Stale requirement | REQUIREMENTS.md TRAK-01/02 still say "ActivityWatch" | Rewrite to StayFree (flagged above) |

## Common Pitfalls

### Pitfall 1: Wayland blindness (the phase-defining risk)
**What goes wrong:** StayFree detects apps via X11 (`libxss`/`libxtst`/`at-spi2-core`); native Wayland (Hyprland) windows are invisible. It silently tracks zero / can't block them.
**Why:** No portable Wayland API for "what app is focused"; X11 trackers break on Wayland.
**How to avoid:** Run the D-09 spike FIRST. Don't build keep-alive until the spike PASSes.
**Warning signs:** Open upstream issues #13, #10 (unresolved); native-app usage shows zero in StayFree.

### Pitfall 2: Electron multi-process pgrep ambiguity
**What goes wrong:** An Electron app forks a main process + GPU + zygote + N renderer children. `comm` is truncated to 15 chars; a bare `pgrep stayfree` may match children, miss the main, or both — leading to false "still running" or duplicate launches.
**How to avoid:** Probe with `pgrep -f /usr/bin/stayfree` (full args contain the invoked path) and treat "≥1 match" as running. For respawn, launch once and rely on the next tick to re-check. Run `pgrep` as root (global pid namespace) — no bridge needed for the probe.
**Warning signs:** Duplicate StayFree windows; respawn fires every tick despite app running.

### Pitfall 3: AppImage / appimagelauncher launch interception
**What goes wrong:** `appimagelauncherd` is running on this box. Launching an AppImage can trigger a "do you want to integrate this AppImage?" prompt or move/rename it — which would break a hardcoded `/usr/bin/stayfree` respawn or spawn a GUI dialog from a root-launched process.
**How to avoid:** During the spike, verify that `runuser … /usr/bin/stayfree` launches cleanly without an integration prompt. If appimagelauncher interferes, pass `--appimage-extract-and-run` is NOT applicable here (it's the AUR-installed file, not user-dropped) — but confirm. Consider `APPIMAGELAUNCHER_DISABLE=1` in the respawn env if it prompts.
**Warning signs:** A dialog appears; the binary gets relocated to `~/Applications`.

### Pitfall 4: AppImage auto-update / version churn
**What goes wrong:** Upstream ships ~every 1–2 weeks (3.4.0 → 3.4.1 in 8 days). The app may self-update or prompt; the AUR pin lags. A self-updated binary could change its process name or move, breaking the pgrep/respawn.
**How to avoid:** Pin to the AUR package; treat `/usr/bin/stayfree` as the stable handle (it's the install target regardless of internal version). Disable in-app auto-update if a setting exists. Re-verify the pgrep pattern after any update.
**Warning signs:** `/usr/bin/stayfree` version differs from `pacman -Q`; respawn stops matching.

### Pitfall 5: Cold-start leakage ≤60s (accepted)
**What goes wrong:** AppImage cold-start is non-instant; between user-quit and next-tick respawn there's up to ~60s where StayFree isn't enforcing.
**How to avoid:** Accepted for v1 (CONTEXT D-04, same budget as Phase 8). The D-05 backstop covers the critical apps during that window regardless.

### Pitfall 6: Rule-tamper escape remains open (accepted, eyes-open — D-06)
**What goes wrong:** Keep-alive closes the *quit-the-app* escape but NOT the *reconfigure-the-rule* escape. The user can edit StayFree's rules at 3am (web dashboard / leveldb). StayFree's rule store is NOT root-locked.
**How to avoid:** This is a deliberate downgrade vs Phase 8's root-signed blacklist, traded for UX/analytics/breadth. The hard guarantee for steam/discord stays the D-05 backstop. Document it in the plan as accepted residual risk; do NOT add scope to root-lock the store (deferred).

### Pitfall 7: Don't re-derive the curfew verdict twice
**What goes wrong:** If keep-alive is curfew-gated (a discretion item), naively calling guard could double-revert/double-audit (the Phase 8 D-09 hazard).
**How to avoid:** CONTEXT leans "every tick" (StayFree's own schedule decides *when* to block), which sidesteps this entirely — no verdict needed for keep-alive. If the planner chooses curfew-gating, reuse the side-effect-free verdict entry point (the Phase 8 D-09 refactor), never re-trigger revert/audit.

## Validation Architecture

> Nyquist validation is disabled for this run; this section is the spike's observable acceptance gates plus light wiring checks. No automated test framework applies to a closed-source GUI behavior test — validation is **manual, observable, recorded**.

### Spike gate (Wave 0 — blocks all build)
| Check | Type | Observable PASS |
|-------|------|-----------------|
| Install | manual | `/usr/bin/stayfree` exists, launches a window under Hyprland |
| Native-Wayland tracking | manual | StayFree attributes nonzero time to a native Hyprland app |
| **App blocking** (the D-09 decision) | manual | StayFree repeatably closes/prevents a scheduled-blocked native app |
| Website blocking | manual (separate) | Blocked domain refused (note: via browser policy, independent of Wayland) |

### Build gates (only if spike PASS)
| Check | Type | Command |
|-------|------|---------|
| is-running probe correctness | manual | kill StayFree → `pgrep -f /usr/bin/stayfree` returns nonzero → next tick respawns it |
| respawn via bridge | manual | `sudo sh -c 'HIS=$(ls /run/user/1000/hypr); runuser -u danitrrga -- env XDG_RUNTIME_DIR=/run/user/1000 HYPRLAND_INSTANCE_SIGNATURE=$HIS /usr/bin/stayfree &'` → StayFree window appears in session |
| no duplicate instances | manual | with StayFree already up, tick does NOT spawn a second instance |
| Phase 8 backstop intact | manual | steam/discord still SIGKILLed during lock (regression check) |
| watchdog still logs/ticks | manual | `watchdog.log` shows `keep-alive: …` lines; tick doesn't hang (oneshot exits) |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| AUR helper (paru/yay) | install | assumed (Arch/CachyOS box) | — | manual makepkg from PKGBUILD |
| Hyprland session w/ `/run/user/1000/hypr/$HIS` | spike + respawn | ✓ | wayland, XDG_SESSION_TYPE=wayland | — |
| `runuser` + CAP_DAC_OVERRIDE (root watchdog) | respawn bridge | ✓ (Phase 8 verified) | — | — |
| `pgrep` | is-running probe | ✓ (procps) | — | parse /proc |
| `/usr/bin/stayfree` | everything | ✗ **NOT INSTALLED** | — | spike installs it |
| StayFree blocking on Wayland | the entire PASS branch | **UNKNOWN — this is the spike** | — | **analytics-only + Phase 8 primary** |
| appimagelauncherd | (interferes) | ✓ running (pid 998) | — | `APPIMAGELAUNCHER_DISABLE=1` in respawn env if it prompts |

**Missing dependencies with no fallback:** StayFree's Wayland-blocking capability — the spike resolves this; the fallback is the whole point of D-09.
**Missing with fallback:** StayFree itself (install in spike); analytics export (fall back to "view in StayFree UI").

## State of the Art

| Old plan | Current plan | When changed | Impact |
|----------|--------------|--------------|--------|
| ActivityWatch as tracker (TRAK-01/02) | StayFree desktop as blocker+analytics | 2026-06-23 re-scope | ActivityWatch retired; REQUIREMENTS.md text still stale |
| Sync StayFree's blocklist OUT into nightguard | Use StayFree desktop AS the blocker | 2026-06-23 investigation | Prior path rejected (~15%/0%-curfew syncable); do NOT research it |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | StayFree desktop uses X11 (libxss/libxtst/at-spi2) for app detection → fails on Wayland | Summary, Spike | If it has a Wayland portal path, spike could PASS — but #13/#10 say it doesn't track on Wayland, so risk is low |
| A2 | StayFree requires account login on first run | First-Run | Spike Step 2 verifies; affects whether blocking even activates |
| A3 | Local store is an Electron leveldb under `~/.config/StayFree*/`; no clean export | TRAK / First-Run | Affects TRAK-02 feasibility; spike discovers actual layout |
| A4 | AppImage main process matches `pgrep -f /usr/bin/stayfree` | Probe | Wrong pattern → false running/duplicate spawns; verify in spike |
| A5 | appimagelauncher may intercept the launch | Pitfall 3 | Could break root respawn; verify in spike |
| A6 | Keep-alive runs every tick (not curfew-gated) | Patterns | CONTEXT leans this; planner confirms |

## Open Questions

1. **Does StayFree desktop block native Wayland apps on Hyprland?** — THE spike question (D-09). Evidence says no; must be proven empirically. Recommendation: run spike Wave 0 before any build.
2. **Where does StayFree store local usage data, and is there any export?** — Unknown (closed source). Recommendation: discover in spike; if no clean export, TRAK-02 = "view in StayFree UI" (acceptable).
3. **Does login/account gate blocking?** — Likely. Recommendation: complete login in spike Step 2.
4. **Does appimagelauncherd prompt on root-launched respawn?** — Recommendation: test the runuser launch in the spike; add `APPIMAGELAUNCHER_DISABLE=1` to env if needed.

## Phase Requirements

| ID | Description (re-scoped intent) | Research Support |
|----|--------------------------------|------------------|
| TRAK-01 | StayFree desktop installed as the screen-time/analytics source (ActivityWatch retired) | Install path verified (AUR PKGBUILD → /usr/bin/stayfree); but tracking on Wayland is the spike's open question. REQUIREMENTS.md text stale — flag for rewrite. |
| TRAK-02 | StayFree analytics available to LifeOS | Likely no clean local export; acceptable v1 = view in StayFree UI. Spike discovers local-store shape. REQUIREMENTS.md text stale — flag for rewrite. |

## Sources

### Primary (HIGH confidence)
- AUR cgit PKGBUILD + .SRCINFO for `stayfree-desktop` (fetched 2026-06-23 via `aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=stayfree-desktop`) — pkgver 3.4.0, install path `/usr/bin/stayfree`, deps incl. `libxss`/`libxtst`/`at-spi2-core`/`fuse2`/`libsecret`, sha256, closed-source license.
- github.com/stayfree-app/desktop-releases — issues #13 (Wayland tracking broken, open), #10 (Wayland not timing apps), #6 ("Can't block single app" → whole system), #7 (autostart broken); releases page (3.4.1 latest, ~1–2wk cadence).
- Live machine probe (2026-06-23): no stayfree installed/running; `appimagelauncherd` pid 998; `XDG_SESSION_TYPE=wayland`.
- `08-NOTES-hyprland-from-root.md` (read) — verified runuser bridge, `$HIS` discovery, CAP_DAC_OVERRIDE.
- `nightguard_watchdog.py` (read) — tick() shape, systemd system oneshot.
- `09-CONTEXT.md`, `08-CONTEXT.md`, `ROADMAP.md`, `REQUIREMENTS.md` (read).
- Memory notes: `nightguard-linux-python-trust-stack`, `stayfree-integration-feasibility`.

### Secondary (MEDIUM confidence)
- StayFree userguide (userguide.stayfreeapps.com) — documents the **browser extension only**, not the desktop app's blocking internals.
- WebSearch on Electron AppImage process naming (FUSE self-mount, comm truncation).

## Metadata

**Confidence breakdown:**
- Spike outcome prediction (likely FAIL/fallback): HIGH — three independent evidence lines (X11 deps, open Wayland issues, analytics-forward framing).
- Install path / process / bridge mechanics: HIGH — PKGBUILD verified, bridge proven in Phase 8.
- StayFree local data layout / export: MEDIUM — closed-source, inferred by analogy; spike must confirm.
- TRAK requirement intent: HIGH on intent (ROADMAP/CONTEXT), but REQUIREMENTS.md text is stale.

**Research date:** 2026-06-23
**Valid until:** ~2026-07-07 (StayFree ships ~weekly; re-verify AppImage version/process name if more than 2 weeks elapse before execution)
