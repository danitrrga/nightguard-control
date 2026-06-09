---
status: partial
phase: 04-ui-moonlit-indigo
source: [04-VERIFICATION.md]
started: 2026-06-09T11:55:00Z
updated: 2026-06-09T11:55:00Z
---

## Current Test

[awaiting human testing — requires `tauri dev` with a populated NIGHTGUARD_DIR + signed config.yaml/guard.json fixture]

## Tests

### 1. Moonlit Indigo visual rendering
expected: App window paints the Moonlit Indigo palette (bg #0c0e14, surface #161a24, accent #7aa2ff), Roboto renders from the bundled woff2, the 56px left icon-rail shows Status + Edit, and the hero countdown uses tabular-nums so digits do not jitter as they tick.
result: [pending]

### 2. Hand-edit flips display to "State unverified" within ~1s
expected: With the app open, hand-editing config.yaml or guard.json out of band triggers the plugin-fs watch; within ~1 second the display re-reads, fails HMAC verification, and shows the fail-closed "State unverified" copy (never an optimistic OPEN).
result: [pending]

### 3. "+8 minutes" grace button — gating + grant + retarget
expected: The +8 button is enabled ONLY during an active lock when grace is available; pressing it calls use_grace, grants the window, and the hero countdown retargets to the new grace_end boundary on the next re-render.
result: [pending]

### 4. Loosen confirm dialog + token-meter decrement
expected: Editing a field to loosen the curfew shows the one-step "Spend a weekly token?" confirm; confirming commits and the 3-dot weekly token meter decrements by one from the returned re-verified state. At 0 tokens the loosen commit is disabled with a visible reason.
result: [pending]

### 5. Empty-state rendering
expected: Pointing the app at an empty/uninitialized NIGHTGUARD_DIR renders the "No signed config yet" empty state rather than erroring or showing a misleading OPEN status.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
