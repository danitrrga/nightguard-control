---
status: partial
phase: 04-ui-moonlit-indigo
source: [04-VERIFICATION.md]
started: 2026-06-09T11:55:00Z
updated: 2026-06-09T16:40:00Z
---

## Current Test

[testing complete — 1 passed (witnessed), 4 blocked on Phase-5 app-key fixture + Tauri runtime]

## Tests

### 1. Moonlit Indigo visual rendering
expected: App window paints the Moonlit Indigo palette (bg #0c0e14, surface #161a24, accent #7aa2ff), Roboto renders from the bundled woff2, the 56px left icon-rail shows Status + Edit, and the hero countdown uses tabular-nums so digits do not jitter.
result: pass
evidence: |
  Witnessed live in a real browser engine (Playwright against `vite dev` :1420, full-page screenshot read).
  Computed styles, exact: body background `rgb(12,14,20)` = #0c0e14; text `rgb(232,234,240)` = #e8eaf0;
  rail background `rgb(22,26,36)` = #161a24; accent `rgb(122,162,255)` = #7aa2ff on 3 elements (🌙 rail icon, etc.).
  `document.fonts`: "Roboto 400 loaded", "Roboto 500 loaded" (bundled woff2, no CDN). Countdown element
  `font-variant-numeric: tabular-nums`, font-family Roboto. Left rail present with Status (accent, active) + Edit (dim) items.
  Screenshot showed the hero `--:--:--` + 3-dot meter, surface/border Curfew edit panel, and a dim/disabled "+8 minutes".

### 2. Hand-edit flips display to "State unverified" within ~1s
expected: Hand-editing config.yaml/guard.json out of band triggers the plugin-fs watch; within ~1s the display re-reads, fails HMAC verification, and shows the fail-closed "State unverified" copy (never optimistic OPEN).
result: blocked
blocked_by: prior-phase
reason: |
  Live ~1s watch-driven flip needs the Tauri fs backend + an app-key-signed fixture in NIGHTGUARD_DIR (Phase 5 wiring).
  Logic verified by proxy: the `!state_verified` branch renders fully-locked "State unverified" copy
  (security audit T-04-15, build_state_dto worst-casing T-04-08/09 with file:line evidence; lock_status fail-closed
  unit tests 11/11). In the browser-only run (no IPC bridge), the path degraded fail-closed — `--:--:--` + a warn
  caption, no crash, no optimistic OPEN (console: get_state + watch errors caught) — partial corroboration.

### 3. "+8 minutes" grace button — gating + grant + retarget
expected: +8 is enabled ONLY during an active lock when grace is available; pressing it calls use_grace, grants the window, and the hero countdown retargets to the new grace_end boundary.
result: blocked
blocked_by: prior-phase
reason: |
  Disabled-state witnessed CORRECT in the screenshot (+8 dim/disabled because not locked / no grace). Live grant flow
  needs a locked signed session (Phase-5 fixture + Tauri runtime + SNTP). Gating rule `locked && grace_available_today`
  and the server-side refusals (NtpUnreachable / GraceAlreadyUsedToday) are audit-verified (T-04-20, grace.rs:56/65).

### 4. Loosen confirm dialog + token-meter decrement
expected: Editing a field to loosen shows the one-step "Spend a weekly token?" confirm; confirming commits and the 3-dot meter decrements by one from the returned re-verified state. At 0 tokens the loosen commit is disabled with a reason.
result: blocked
blocked_by: prior-phase
reason: |
  Edit panel + Commit button witnessed rendering (Moonlit surface/border). Live debounced-classify feedback, the
  window.confirm dialog, and the token-meter decrement need classify_change/commit_change over a signed fixture
  (Phase-5 + Tauri runtime). Logic audit-verified: server-side 0-token gate (T-04-18, commit.rs:148), confirm-only-on-loosen
  (T-04-21, main.ts), re-render from returned DTO only (T-04-19, main.ts) — no optimistic mutation.

### 5. Empty-state rendering
expected: Pointing the app at an empty/uninitialized NIGHTGUARD_DIR renders the "No signed config yet" empty state rather than erroring or showing a misleading OPEN status.
result: blocked
blocked_by: prior-phase
reason: |
  The exact backend NotInitialized "No signed config yet" branch needs the Tauri host returning IpcError::NotInitialized
  (requires the Tauri runtime). Source-verified by the phase verifier in main.ts. In the browser-only run the adjacent
  no-bridge degraded path was witnessed fail-closed (no optimistic OPEN), which corroborates the defensive intent but is
  a different code branch than backend-NotInitialized.

## Summary

total: 5
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 4

## Gaps

[none — no code issues found. The 4 blocked items are prerequisite gates (live Tauri runtime + an app-key-signed
fixture, which Phase 5 "instance wiring" provides), not defects. All underlying logic is covered by the green
workspace test suite, the phase verifier (5/5 must-haves), and the security audit (22/22 threats closed).]
