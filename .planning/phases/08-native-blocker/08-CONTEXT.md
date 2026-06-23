# Phase 8: Native Blocker - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning

<domain>
## Phase Boundary

During an active curfew lock, the **root watchdog tick** (the same systemd *system*
service from ROOT-02) enumerates Hyprland clients and kills windows whose class is on
`blocking.native_apps.blacklist`. The kill is folded **into the existing watchdog tick**
— no separate service — so it cannot be stopped from user space
(`systemctl --user stop` does not apply). Cadence = the watchdog tick (≤60s leakage
accepted for v1). Requirements: NBLK-01, NBLK-02, NBLK-03.

**In scope:** per-tick enumerate-and-kill of blacklisted native windows, gated on
lock + no-active-grace, living inside `nightguard_watchdog.py`'s `tick()`.

**Out of scope:** an instant `.socket2.sock` `openwindow` event-listener (deferred
"accelerate" upgrade — only built if 60s leakage proves inadequate *with evidence*);
the browser-extension layer (already shipped in P6/P7); ActivityWatch (P9); the TUI (P10).

</domain>

<decisions>
## Implementation Decisions

### Kill mechanism (B2 — the explicitly-deferred decision)
- **D-01:** Kill via **SIGKILL by PID** (`kill -KILL <pid>`, root signals the user pid
  directly). Chosen over `hyprctl dispatch closewindow` because closewindow leaves
  Steam/Discord resident in tray/background; SIGKILL fully removes the app — strongest
  deterrent, simplest, most aligned with the "anti-me" guarantee.
- **D-02:** Dedup pids before killing (multiple windows can share one pid). A killed app
  that respawns is simply re-killed on the next tick (≤60s re-kill loop is the deterrent,
  accepted).

### Blacklist matching
- **D-03:** Match a client's `class` **and** `initialClass` against each blacklist entry
  using **substring, case-insensitive** containment (entry ⊆ class). "steam" therefore
  catches `steam`, `steamwebhelper`, `steam_app_*`. Accept the small over-broad-match risk.
- **D-04:** Known gap (accepted for v1): games launched *through* Steam carry their own
  window class (the game's name), not "steam", so they won't match unless their class is
  added. This is acceptable because killing Steam itself removes the game-launch path.
  Per-game classes can be added later via the signed control-CLI.

### Kill notification
- **D-05:** Kills are **announced**, not silent — a Spanish-butler-style notification
  consistent with the curfew-hook deny-message theme (e.g. *"Cerré Steam y Discord —
  es hora de descansar, señor"*).
- **D-06:** **One summary notification per tick** listing the distinct apps closed (not
  one-per-window) to avoid toast spam when several windows die at once. Delivered into the
  user session via `runuser` (`notify-send` / `hyprctl notify`), same bridge as enumeration.
- **D-07:** Always also append the kill to `watchdog.log` (class, pid, mechanism) for
  audit, independent of the on-screen notification.

### Verdict gating (NBLK-02 — curfew/grace awareness)
- **D-08:** Gate the kill on the **same full verdict guard.py uses** — curfew window +
  daily grace + NTP true-time + clock-tamper + `block_when_offline` — so native-app kills
  are always consistent with the session-block verdict. Kills fire even when NTP is
  unreachable if `block_when_offline` is true; kills are suppressed during an active grace
  window and outside curfew.
- **D-09:** Reuse guard's **decision logic without re-triggering its side-effects** — the
  watchdog already calls `guard.verify_and_revert()` and writes audit lines; the native-kill
  gate must consume the curfew/grace/true-time *verdict* only (no second revert, no
  duplicate audit chain write). Refactor `guard.py` to expose a side-effect-free verdict
  the watchdog can call, rather than copy-pasting the curfew/grace math.

### v1 blacklist membership (Claude's discretion — "you decide")
- **D-10:** Ship v1 with **`steam` + `discord`** (the current `config.yaml` entries).
  Only `steam` is confirmed installed on this box; do **not** pre-blacklist launchers
  (lutris/heroic/bottles) that aren't present. Membership is trivially editable later via
  the signed control-CLI (it's a tighten/loosen the engine governs). With substring
  matching, `steam` already covers `steamwebhelper`/`steam_app_*`.

### Claude's Discretion
- Exact `runuser`/`env` invocation shape, pid-dedup, and notification command
  (`notify-send` vs `hyprctl notify`) are implementation details for planning.
- The `guard.py` refactor to expose a side-effect-free verdict (D-09) — shape left to
  the planner, but the constraint (no double-revert / no double-audit) is locked.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 8 de-risking (the proven bridge — READ FIRST)
- `.planning/phases/08-native-blocker/08-NOTES-hyprland-from-root.md` — the verified
  root→user-Hyprland approach: per-tick `$HIS` (HYPRLAND_INSTANCE_SIGNATURE) discovery,
  `runuser -u danitrrga -- env XDG_RUNTIME_DIR=/run/user/1000 HYPRLAND_INSTANCE_SIGNATURE=$HIS hyprctl clients -j`,
  the `class`/`initialClass`/`pid`/`address`/`xwayland` fields, CAP_DAC_OVERRIDE traversal,
  HIS rotation, no-Hyprland no-op, XWayland (Steam) handling, and the live-proof command.

### The watchdog this phase extends
- `LifeOS/scripts/nightguard/nightguard_watchdog.py` — the systemd *system* oneshot
  `tick()` (one tick per timer fire). The native-kill logic folds into this `tick()`.
- `LifeOS/scripts/nightguard/guard.py` — `decide()` (verdict), `in_curfew(cfg, true_dt)`,
  grace evaluation, `true_unix()` (NTP + `.timecache`), `app_holds_lock()`,
  `verify_and_revert()`. Source of the verdict the kill gate reuses (D-08/D-09).
- `LifeOS/scripts/nightguard/ngcommon.py` — `NIGHTGUARD_DIR`, `CONFIG`, `yaml_load`,
  `file_bytes`, `load_state`, `read_key`. Config/state access helpers.

### Config schema (the blacklist source)
- `LifeOS/nightguard/config.yaml` — `blocking.native_apps.{enabled,blacklist}` (current:
  steam, discord) and `blocking.browser_extension`. This is the root-signed instance config.
- `.planning/REQUIREMENTS.md` — NBLK-01, NBLK-02, NBLK-03 (full requirement text + the
  ≤60s-leakage / B2-deferral curation notes).
- `.planning/ROADMAP.md` §"Phase 8: Native Blocker" — goal, success criteria, curation note.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `nightguard_watchdog.py:tick()` — the host function; native-kill is a new step after the
  existing `verify_and_revert` + browser-policy check, reusing `ng.yaml_load(...)` of CONFIG.
- `guard.py:in_curfew()` + grace block in `decide()` + `true_unix()` — the curfew/grace/
  true-time logic to reuse for the kill gate (D-08). Needs a side-effect-free entry point (D-09).
- `ngcommon.yaml_load` / `ngcommon.file_bytes(ng.CONFIG)` — already used in `tick()` to read
  config; the `blocking.native_apps.blacklist` list comes from the same parse.

### Established Patterns
- Watchdog is a **systemd system oneshot** — one `tick()` per timer fire, no long-lived
  loop. Native-kill must be tick-shaped (enumerate → match → kill → notify → return), not a
  persistent listener.
- `runuser`-to-user bridge pattern (from 08-NOTES) is how root reaches the user session
  for both enumeration and notification — keep it inside the root watchdog (no new service).
- Logging convention: `_log(...)` appends one local-time ISO line to `watchdog.log`.

### Integration Points
- New kill step slots into `tick()` between the policy check and the `_log` summary; its
  outcome (apps killed) folds into the same tick log line and triggers the butler notification.
- Gate strictly on the lock + no-active-grace verdict (D-08) — must NOT fire outside curfew
  or during grace, and must NOT run a second revert/audit (D-09).

</code_context>

<specifics>
## Specific Ideas

- Spanish-butler notification voice, e.g. *"Cerré Steam y Discord — es hora de descansar,
  señor"* — one summary toast per tick (D-05/D-06), matching the curfew-hook deny-message tone.
- SIGKILL is the intended user-felt behavior: the app *dies*, it doesn't just minimize.

</specifics>

<deferred>
## Deferred Ideas

- **Instant `.socket2.sock` `openwindow` event-listener** — sub-60s kill latency. Only build
  if the ≤60s tick leakage proves inadequate with evidence (per NBLK-02 curation). If built,
  it stays inside the root watchdog (a persistent `runuser` reader), never a separate `--user`
  service.
- **Per-app kill-mechanism override** (closewindow for some apps, SIGKILL for others) and
  **expanded blacklist** (game launchers / per-game classes) — add via the signed control-CLI
  when those apps actually appear on the box.

None of the above changed this phase's scope — discussion stayed within the native-blocker domain.

</deferred>

---

*Phase: 8-native-blocker*
*Context gathered: 2026-06-23*
