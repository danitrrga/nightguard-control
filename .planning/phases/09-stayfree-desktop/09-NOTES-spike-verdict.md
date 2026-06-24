# Phase 9 — D-09 gating spike: does StayFree desktop *block* (not just track) on Hyprland/Wayland?

**Status:** Spike **run + decided** 2026-06-24 on this box (Hyprland/Wayland, CachyOS). Empirical verdict established. This is the unconditional Phase 9 deliverable and the gate that routes 09-02 (PASS) vs 09-03 (FAIL/PARTIAL).

## Install target (verified)

- `stayfree-desktop 3.4.0-1` (AUR, maintainer `bailwillharr`), AppImage sha256 `7a343a61560c9396dbceff8879ca0d10a2c4eddc14ca628b2e47b244e4d2b417` — legitimacy gate (Task 1) human-approved before install (threat T-09-SC).
- Installs `/usr/bin/stayfree` (150 MB Electron AppImage, root-owned, world-rx). `pacman -Q stayfree-desktop` succeeds.

## Verified facts (this machine, 2026-06-24)

### Step 1 — Install / launch
- Launches directly into the Hyprland session. **`appimagelauncherd` (pid 998) intercepts** unless `APPIMAGELAUNCHER_DISABLE=1` is set in the env — with it set, the binfmt bypass launches the AppImage directly and a window opens. Electron multi-process (main + zygote/renderer forks); `pgrep -f /usr/bin/stayfree` sees them in the global pid view.
- Relevant for any future launch/keep-alive: the env needs `APPIMAGELAUNCHER_DISABLE=1` to avoid the launcher prompt.

### Step 2 — First-run / login
- Account-based Electron app; first run shows a dashboard. (Login is StayFree's own cloud account — irrelevant to the verdict because tracking never produced data regardless; see Step 3.)

### Step 3 — Tracking (THE precondition) — **FAIL**
- After ~10+ minutes of an active Hyprland session (native Wayland terminal + other apps focused), StayFree's own Dashboard shows **`Usage Time: 0s`** and **"No usage history"** (screenshot captured during the spike).
- Objective on-disk corroboration: `~/.config/StayFree/usage.db` → `SELECT COUNT(*) FROM sessions;` returns **0**. StayFree recorded **zero** app sessions.
- Conclusion: StayFree's window/active-app detection (X11-only deps; open upstream Wayland issues) sees **nothing** under Hyprland — not native Wayland *and* not even XWayland in this run. Tracking is dead on Wayland.

### Step 4 — Blocking (THE D-09 question) — **moot → FAIL**
- Blocking depends on detecting the focused/running app. With Step 3 returning **0 detected sessions**, StayFree has no signal to act on; it cannot close/overlay/limit an app it cannot see. The blocking guarantee is therefore unattainable on this box, consistent with the RESEARCH HIGH-confidence prediction.

### Step 5 — Website block (recorded SEPARATELY)
- Not relied upon: any web-block would work via the browser's own URLBlocklist policy (the curfew layer already owns that), independent of StayFree's Wayland detection. A web-block "working" does **not** rescue the app-block FAIL and is explicitly not counted toward PASS.

### Step 6 — Local store (for TRAK-02) — **better than predicted**
- `~/.config/StayFree/` is **SQLite (knex)**, not the opaque leveldb RESEARCH guessed:
  - `usage.db` → `sessions(id, appId, startedAt, endedAt, imported, generated, createdBy)` — clean, queryable (but empty here, since tracking is dead).
  - `config.db` → `config(key, value)` holding `preferences/categories` (2,493 app/domain→categoryId memberships), `app-groups.value` (1,147 brands → name + websites + apps), `remote-config.identifierListDefaultCategories` (adult/gambling lists).
- **Blocklist is fully recoverable offline.** A user "Export Settings" produces `genericWebsiteLimits` (rules: schedules + target category/brand IDs); the IDs resolve to concrete app/domain lists entirely from `config.db` — no cloud needed. Verified by resolving the live config (custom category "Sleep Dont" = 28 members; 2 active schedule rules; brand IDs → domains). Resolved snapshot built during the spike.
- Built-in negative-category *display names* (-1..-6, -99) are not cleanly stored locally, but their *membership* is — so functionally nothing is lost.

## Verdict: FAIL — StayFree records 0 sessions on Hyprland/Wayland (usage.db empty, Dashboard 0s); it cannot track and therefore cannot block native or XWayland apps on this box.

Routes to **09-03** (analytics-only fallback). NB: because tracking is dead, StayFree is not even a useful *analytics* source on Wayland in its current form — the durable value found is the **importable, fully-offline blocklist** (categories + brands + schedules in `config.db`), which can seed Nightguard's own curfew-layer enforcement. The keep-alive supervisor (09-02) is **not built** (a non-tracking app gains nothing from forced uptime).
