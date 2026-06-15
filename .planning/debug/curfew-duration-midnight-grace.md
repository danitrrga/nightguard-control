---
status: resolved
trigger: "Curfew bugs: (1) start/end classified independently not by total locked time; (2) start==end / 00:00 shows 24/7 lock diverging from guard; (3) grace untestable at 0 tokens + stale grace."
created: 2026-06-15
updated: 2026-06-15
---

# Debug: curfew duration / midnight / grace

## Current Focus
- hypothesis: three independent defects, all confirmed by reading source + the PowerShell guard.
- next_action: implement fixes + tests, then re-arm live instance to full tokens with an active test window.

## Root Causes (confirmed)

### RC1 — classification is per-field, not by locked time (classify.rs)
`curfew.start` = TimeLaterLoosens, `curfew.end` = TimeEarlierLoosens, judged independently.
For an overnight window the numeric comparison inverts: 22:00→02:00 reads `02:00 < 22:00`
=> Tighten (free), but it cuts an 8h curfew to 4h => a loosen. Exploit.
FIX (user decision: "locked-set" model): classify the curfew window (start+end) jointly —
a change is Loosen iff it un-locks ANY previously-locked minute; Tighten if it only adds
locked minutes; else Noop. Same model for `schedule.<day>` windows (off = empty set).

### RC2 — start==end shows 24/7 lock, diverging from the guard (lock_status.rs:198)
Rust: `wraps = end_min <= start_min` (<=) → start==end wraps → locked 24/7.
Guard (nightguard_guard.ps1:542): `if ($startMin -gt $endMin)` (strict) → start==end →
non-wrap → never locked. Disagreement exactly at equality → "00:00 breaks the system."
FIX: `wraps = end_min < start_min` (strict) to match the guard byte-for-byte.

### RC3 — grace untestable (state, not a code bug)
Traced the live prompt gate: `~/.claude/hooks/nightguard_adapter.ps1` (UserPromptSubmit) ->
`nightguard_guard.ps1`, which DOES honor grace (exit 0 = allow when grace.window_end > trueNow).
The grace-ignoring `nightguard_curfew_guard.ps1` is the legacy/unused hook, not wired.
So grace works once a valid window exists.
Live guard.json: weekly_spent=3 (0 tokens) + stale grace (2026-06-13). At 0 tokens the user
cannot commit a curfew change to create an active test window, and curfew 05:00-05:30 isn't
active now, so the +8 button stays disabled ("Unavailable while open").
FIX: re-arm via `state_interop_cli init-instance` (weekly_spent=0, grace=None, re-sign both
HMACs) + set an active test window (user opted in).

## Resolution
- files_changed: crates/mutation-engine/src/{classify.rs,lock_status.rs} + tests
- verification: cargo test + live re-arm + manual grace test by user
