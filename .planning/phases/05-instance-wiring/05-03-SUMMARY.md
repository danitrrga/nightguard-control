# Plan 05-03 Summary — Live Cutover (prove-then-switch)

**Status:** EXECUTED — live in-session verification pending (requires a fresh Claude Code session; see below)
**Requirements:** WIRE-01, WIRE-02

## What was done

1. **Guard gap fixed (the blocker).** The published guard had **no curfew-schedule evaluation** — its verdict denied 24/7 unless an active grace window, so swapping it in as the sole UserPromptSubmit gate would have blocked every prompt all day. Added `Read-GuardConfig` / `Resolve-GuardTimeZone` / `Get-InCurfew` and a schedule pre-gate to the verdict: **allow outside today's window, deny inside** (per-day `schedule.<day>` + `off` supported; overnight wrap; `enabled:false` honored). **Fail-closed** on any parse/tz error (treat as in-curfew → deny). Commit `6404c3a`.
   - Regression: `run_guard_gate.ps1` GARD-01..07 kept green (fixtures switched to a 24/7 window so the schedule pre-gate is a no-op there); added **GARD-08** (outside→allow / inside→deny). All 8 PASS.

2. **Deploy fixes.**
   - `install_nightguard.ps1` now deploys interop to **`~/.claude/interop`** (where the guard's `$here\..\interop` lexically resolves under the `~/.claude/hooks` junction) — the previous `LifeOS/hooks/interop` target would have made the deployed guard throw on load → adapter fail-closed → total lockout.
   - Stopped the install from clobbering the live SessionStart `verify_hook_integrity.ps1` (repo-layout-only version would fail from `~/.claude/hooks`). Integrity enforced at repo-source scope; deployed-layout-aware verifier deferred (A5).

3. **D-11 prove-then-switch gate** (`run_cutover_gate.ps1`) — GREEN before any switch:
   - D11-1 key round-trips to 32 bytes (DPAPI CurrentUser).
   - D11-2 guard.json `state_hmac` verifies in **both** PowerShell (A3 re-derive) and Rust (`verify-state-hmac` exit 0).
   - D11-3 curfew schedule verdict: 12:00 → allow/outside curfew; 21:30 → deny/curfew.
   - D11-4 auto-revert: hand-edit config.yaml → guard reverts (`reverted=true`), HMAC restored, sanctioned identity holds.
   - D11-5 adapter: `/shutdown` → exit 0 (allow-pass); fail-closed → exit 2 (the confirmed CC block contract).

4. **Live switch (only after green):**
   - Deployed guard/adapter/watchdog into `~/.claude/hooks` + interop into `~/.claude/interop`; re-stamped repo baseline.
   - **Watchdog** `NightguardWatchdog` re-registered → `nightguard_watchdog.ps1`, Stop/Start so a fresh process inherits `NIGHTGUARD_DIR` (Pitfall 2). It read the **canonical** config and **relaunched StayFree (PID confirmed running)** — the visible WIRE-01 signal (D-05).
   - **settings.json** UserPromptSubmit swapped `curfew_guard.ps1` → `nightguard_adapter.ps1` (D-01 retirement, the last action). Backup: `~/.claude/settings.json.pre-cutover.bak`. Old script files left on disk (non-load-bearing).

## Known operational dependency (Pitfall 2)

The adapter fail-closes when `NIGHTGUARD_DIR` is absent from the **launching process's** env (by design — D-08, never guess the data dir). The adapter therefore only works in a Claude Code session **started after** the user-scope var was set. The session that performed the cutover has a stale env; **Claude Code must be restarted** for the adapter to take effect. The watchdog already inherits it via the freshly-started scheduled task.

## Pending verification (Task 2 human-verify — do in a NEW Claude Code session)

1. During curfew (or simulated): a normal prompt is BLOCKED with the Spanish-butler curfew message (via the adapter).
2. `/shutdown` passes during curfew (allow-command pass).
3. Outside curfew: normal prompts pass (schedule fix — no 24/7 lockout).
4. `Get-ScheduledTask NightguardWatchdog` → action points at `nightguard_watchdog.ps1`, State Running; `Get-Process StayFree` running.
5. Hand-edit `LifeOS/nightguard/config.yaml` → it auto-reverts on the next guard fire.

## Deviations

- Did NOT delete the orphan `nightguard_curfew_guard.ps1` / old `curfew_guard.ps1` files (only removed from settings.json) — leaving them avoids any in-flight reference error; harmless (T-05-16 accept).
- `install_nightguard` no longer deploys `verify_hook_integrity.ps1` / baseline into the hooks dir (would break the live SessionStart check) — see deploy fix #2.
