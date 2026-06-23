---
phase: 8
reviewers: [opencode]
reviewed_at: 2026-06-23T13:44:23Z
plans_reviewed: [08-01-PLAN.md, 08-02-PLAN.md]
reviewer_status:
  opencode: ok (model: big-pickle)
  gemini: skipped — CLI not authenticated (GEMINI_API_KEY/Vertex unset)
  codex: skipped — 401 Unauthorized at api.openai.com
  claude: skipped — self (review runs inside Claude Code; skipped for independence)
  agy_gemini_3_5_flash: failed — `agy --print` returns only first-turn preamble and exits before doing work (4 attempts: inlined prompt, no-tools directive+sandbox, agentic file-read, write-to-file). Print mode is not headlessly scriptable for a multi-step review.
---

# Cross-AI Plan Review — Phase 8 (Native Blocker)

> **Reviewer coverage note:** Of the requested `--all` reviewers, only **OpenCode** produced a
> usable review. Gemini and Codex CLIs are unauthenticated on this machine; the Antigravity CLI
> (`agy`, Gemini 3.5 Flash) could not be driven in non-interactive `--print` mode — it returns a
> single turn of preamble narration and exits before reading files or emitting a review (verified
> across 4 prompt strategies). Treat the consensus below as **single-source**, not multi-model
> agreement. To add Gemini 3.5 Flash's perspective, run `agy` **interactively** and paste the
> prompt at `/tmp/gsd-review-prompt-08.md`, then re-run synthesis.

## OpenCode Review

*(model: `big-pickle`, via GitHub Copilot)*

### Overall Assessment

Both plans are **well-structured, internally consistent, and correctly scoped**. 08-01 is a textbook extraction refactor; 08-02 correctly integrates into the root watchdog with appropriate gating, no-shell-subprocess discipline, and fail-closed posture. The dependency ordering (08-01 → 08-02) is correct. **Overall risk: LOW** — the main concerns are small coordination gaps and test coverage breadth.

---

### Plan 08-01: guard.py verdict extraction

#### Strengths
- **Clean boundary**: `curfew_verdict` is explicitly pure — no `verify_and_revert`, no `_verdict`/`append_audit`. The side-effect-free contract is enforced by the acceptance criteria and grep-verified.
- **Behavior-preserving**: `decide()` is re-expressed in terms of the new function, not replaced. The JSON + exit-code contract remains unchanged — critical for the existing hook path.
- **Fail-closed ordering**: The verdict sequence preserves the correct priority (tamper > in_curfew > offline > grace), so grace correctly overrides all other gates for suppression.
- **Threat model is thorough**: T-08-01 (tampered grace), T-08-02 (exception toward locked), and T-08-03 (no double-audit) all have concrete mitigations.

#### Concerns

| # | Severity | Concern | Plan Reference |
|---|----------|---------|----------------|
| C1 | **MEDIUM** | **`key` parameter in `curfew_verdict` is dead weight** — it's declared, never used in the body, passed pointlessly by `decide()`. This creates a misleading API contract (reader expects HMAC verification inside the function). | "curfew_verdict(cfg, state, key=None)" — no usage described |
| C2 | **MEDIUM** | **"Curfew math defined once" overstated** — only the gating logic is unified. `grace_remaining_secs` calculation still lives in `decide()` (Task 2: "recomputes grace_remaining_secs itself"). If 08-02 needs remaining seconds (it doesn't yet), it has no access. | Task-2 action |
| C3 | **LOW** | **Test coverage gaps**: The 5 verdicts return correct values for: `locked` ✓, `outside_curfew` ✓, [`grace_active`, `clock_tamper`, `offline_blocked`] ✗ — none tested in automated acceptance. | Task-1 verify block |

#### Suggestions
- **S1 (C1 fix)**: Either drop `key` from `curfew_verdict` entirely and have `decide()` pass it only to `verify_and_revert`, or add a docstring-level comment (project anti-comment convention may prohibit this). If the latter, accept the dead parameter.
- **S2 (C2 clarity)**: Note in the plan that `grace_remaining_secs` remains `decide()`-local, and if 08-02 ever needs it, extract it as a separate helper.
- **S3 (C3 fix)**: Add acceptance tests for `grace_active` (set grace dict to cover tnow), `clock_tamper` (mock a large system-time skew), and `offline_blocked` (force `true_unix()` to return `(None, "cache")` while in curfew with `block_when_offline=True`). Simple stdlib-mock additions.

---

### Plan 08-02: watchdog native-kill integration

#### Strengths
- **Security-first subprocess discipline**: Lists argv everywhere, explicit no-`shell=True` gate in acceptance. $HIS and class strings never touch a shell.
- **Fail-closed at every stage**: Kill fires only on explicit `{"locked", "clock_tamper", "offline_blocked"}` allowlist; any other value, exception, or None suppresses the kill. No way to widen on uncertainty.
- **Correct runtime safeguarding**: `timeout` on subprocess, try/except on enumeration failure, try/except on each `os.kill`. Kill-path failure never blocks the existing revert.
- **D-06/D-07 logging discipline**: One summary toast, one folded log line, per-pid kill audit. No toast spam.
- **Global state for uid/his**: Properly derived per tick from glob, not cached — handles HIS rotation correctly.

#### Concerns

| # | Severity | Concern | Plan Reference |
|---|----------|---------|----------------|
| C4 | **LOW** | **`timeout` value unspecified** — "Every subprocess.run uses a `timeout`" but no value given. If defaulted to `None`, a hung hyprctl blocks the tick indefinitely. If set too tight (e.g. 1s), a loaded Hyprland might fail sporadically. | Task-1 action |
| C5 | **LOW** | **State worst-casing in `tick()` is underspecified** — "worst-case state for grace validity exactly as guard.decide() does (if key present and state_hmac invalid → grace=None)". The watchdog already has `verify_and_revert`'s `state_invalid` return; the plan should explicitly reference this rather than punting with "or call a small shared helper if Plan 01 exposed one" (it didn't). | Task-2 action |
| C6 | **LOW** | **uid/his sharing pattern ambiguous** — "pass them out of _kill_native_apps or re-derive once". If `_kill_native_apps` returns `[]` (no matches), the notification is skipped, so re-derivation is fine. But if it returns matches but the second glob fails, the notification silently dies. Minor, but the plan should pick one pattern. | Task-2 action |
| C7 | **LOW** | **Hardcoded username `danitrrga`** — works for the personal instance but would break on a renamed user or multi-user box. Should derive from `pwd.getpwuid(uid).pw_name`. | Task-1 action (runuser invocation) |
| C8 | **LOW** | **Corrupt config → `native_apps.enabled` defaults to True** — if config is unparseable, `curfew_verdict` returns "locked" (fail-closed) and `_kill_native_apps` reads `enabled=True` by default (fail-closed). This is correct per threat model T-08-06, but the security implication should be documented for the admin. | Task-1 action, `na.get("enabled", True)` |

#### Suggestions
- **S4 (C4 fix)**: Specify `timeout=10` for hyprctl enumeration and `timeout=5` for notify-send. Document rationale: hyprctl should be near-instant; 10s covers worst-case load; 5s for notification is generous.
- **S5 (C5 fix)**: Replace the underspecified worst-casing with explicit code shape:
  ```python
  if state_invalid:
      state = {**state, "grace": None}  # or mutate in place
  verdict = guard.curfew_verdict(cfg, state, key)
  ```
  This removes the ambiguity.
- **S6 (C6 fix)**: Pick re-derive (simpler, no signature change to `_kill_native_apps`). Add a small comment at the derivation site.
- **S7 (C7 fix)**: Replace `"danitrrga"` with runtime derivation: `pwd.getpwuid(int(uid)).pw_name`. Add `import pwd` function-local.
- **S8 (C8 fix)**: Add a note to the threat model or acceptance criteria that `enabled` defaults to True when the config node is missing — this is a fail-closed choice, not an oversight.

---

### Risk Assessment

**Overall: LOW**

The plans are well-considered within their vertical slice. The HIGHEST risk is a coordination gap between 08-01 and 08-02 (the `key` parameter and state worst-casing contract), but both are easily resolved in planning/execution with the suggestions above. No plan-level changes are needed — only implementation-level attention to the specifics highlighted in C4-C7.

The security posture is sound: kill fires only on explicit verdict allowlist, fails suppressed on any uncertainty, uses no shell injection surface, and lives inside the root-system service so it cannot be `systemctl --user stop`-ed. All three NBLK requirements are met by the combined plans.

---

## Consensus Summary

> Single-source (OpenCode only) — see coverage note above. No cross-model agreement could be
> established because the other three reviewers were unavailable/unauthenticated.

### Agreed Strengths
- Fail-closed kill gating on an explicit verdict allowlist (`locked`/`clock_tamper`/`offline_blocked`); any uncertainty suppresses the kill.
- No shell-injection surface — list-argv subprocess discipline throughout, explicit no-`shell=True` gate.
- Kill lives inside the **root** system watchdog → un-stoppable from user space (satisfies NBLK-03).
- Correct dependency ordering: 08-01 (pure `curfew_verdict` extraction) precedes 08-02 (consumer).

### Agreed Concerns (highest priority for the planner)
1. **[MEDIUM] Dead `key` parameter on `curfew_verdict`** (C1) — misleading contract; drop it or justify it.
2. **[MEDIUM] `grace_remaining_secs` not actually unified** (C2) — "curfew math defined once" is overstated; still lives in `decide()`.
3. **[MEDIUM-effective] State worst-casing in `tick()` underspecified** (C5) — pin the exact `state_invalid → grace=None` shape; don't punt to a non-existent shared helper.
4. **[LOW] `subprocess.run` timeout value unspecified** (C4) — a hung `hyprctl` would stall the root tick; specify concrete values (e.g. 10s / 5s).
5. **[LOW] Hardcoded username `danitrrga`** (C7) — derive via `pwd.getpwuid(uid).pw_name` for portability/publishability.
6. **[LOW] Verdict test coverage gaps** (C3) — add acceptance tests for `grace_active`, `clock_tamper`, `offline_blocked`.
7. **[LOW] `native_apps.enabled` defaults True on corrupt config** (C8) — correct (fail-closed) but document the implication.

### Divergent Views
- None — single reviewer.
