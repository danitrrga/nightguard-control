# Phase 8 — Risk note: reaching the user's Hyprland from the root watchdog

**Status:** Feasibility **verified** 2026-06-22 (read-only investigation). Implementation deferred to Phase 8 execution. This de-risks the one real wrinkle the curation introduced by folding native-app killing into the *root* watchdog.

## The concern

Curation moved native-app killing (NBLK-01/02/03) out of a separate `--user` service and **into the root watchdog tick** (so it can't be `systemctl --user stop`-ed). But Hyprland's IPC socket is owned by the **user** session. A root process must therefore cross from root into the user's Wayland session to enumerate/kill windows. The brief originally said native blocking "*must* run as the user" for exactly this reason — this note shows the root approach is sound.

## Verified facts (this machine, 2026-06-22)

- Sockets: `/run/user/1000/hypr/$HIS/.socket.sock` (control) and `.socket2.sock` (events).
- Socket nodes are world-rwx (`srwxr-xr-x`); the gating is the parent dirs `/run/user/1000` and `/run/user/1000/hypr`, both `0700 danitrrga`. **Root traverses these via `CAP_DAC_OVERRIDE`** — no perms change needed.
- `$HIS` = `HYPRLAND_INSTANCE_SIGNATURE` = the single dir name under `/run/user/1000/hypr/`. It **embeds a timestamp and rotates on every Hyprland restart** → must be discovered each tick, never cached/hardcoded.
- `hyprctl clients -j` returns per-window: `class` + `initialClass` (blacklist match key), `pid` (for SIGKILL), `address` (for `hyprctl dispatch closewindow address:0x…`), and `xwayland: true/false` (Steam & friends are XWayland but still carry a `class`).
- `uid` is `1000` (`/run/user/1000`).

## Recommended approach (for Phase 8)

On each root-watchdog tick, **only while curfew is locked and no grace is active**:

1. **Discover the session:** for each `uid` dir under `/run/user/*/hypr/` (personal box: just `1000`), take the instance-signature subdir name as `$HIS`. Skip if none (Hyprland not running → no-op).
2. **Enumerate as the user:**
   `runuser -u danitrrga -- env XDG_RUNTIME_DIR=/run/user/1000 HYPRLAND_INSTANCE_SIGNATURE=$HIS hyprctl clients -j`
   (`runuser` drops to the user so hyprctl resolves its own socket — avoids running hyprctl as root and any root-owned side effects.)
3. **Match** each client's `class`/`initialClass` (case-insensitive) against `blocking.native_apps.blacklist`.
4. **Kill** (B2 decision — settle in Phase 8 planning):
   - gentle: `… hyprctl dispatch closewindow address:0x…` (app stays resident, window closes), or
   - hard: `kill -KILL <pid>` (root can signal the user's pid directly).
   Recommendation: start with `closewindow`; escalate to SIGKILL for apps that ignore it (per-app override).

### Live proof (run with `!` so it executes in-session)

```
sudo sh -c 'HIS=$(ls /run/user/1000/hypr); runuser -u danitrrga -- env XDG_RUNTIME_DIR=/run/user/1000 HYPRLAND_INSTANCE_SIGNATURE=$HIS hyprctl clients -j | python3 -c "import sys,json;print(sorted({c[\"class\"] for c in json.load(sys.stdin)}))"'
```
Expected: root prints the list of current window classes → proves the root→user-Hyprland bridge end-to-end.

## Edge cases to handle in Phase 8

- **HIS rotation** — re-discover every tick (it changes on each Hyprland restart).
- **No Hyprland running** (logged out / TTY) — native-kill no-ops; curfew is still enforced by config-revert + the browser layer.
- **Multiple instances** — loop over all `/run/user/*/hypr/*` (personal box has one).
- **XWayland apps** (Steam) — matched by `class` like native; SIGKILL by `pid` works regardless.
- **≤60s leakage** — accepted for v1 (the open→die→open loop is itself the deterrent); a `.socket2.sock` `openwindow` event-listener is the deferred "accelerate" upgrade only if 60s proves inadequate. That listener, if ever built, also needs the user session — same bridge, kept inside the root watchdog (e.g. a persistent `runuser` reader) rather than a separate user service.
- **Don't kill outside the lock / during grace** — gate strictly on the watchdog's existing lock+grace verdict.

## Verdict

The folded-into-root design is **viable**: root reaches the user's Hyprland cleanly via `runuser` + a per-tick `$HIS` discovery, with no permission changes. No reason to revert the curation back to a separate `--user` service. Implement in Phase 8.
</content>
