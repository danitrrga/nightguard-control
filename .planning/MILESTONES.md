# Milestones

## v2.0 Linux Port (Shipped: 2026-06-24)

**Phases completed:** 6 phases, 15 plans, 23 tasks

**Key accomplishments:**

- Re-pointed the Rust direction-classifier's FIELD_TABLE from the dead Windows `watchdog.apps` (uwp/package_id) list to the Linux `blocking:` model (`browser_extension` + `native_apps`), so loosening/tightening of the new keys classifies correctly and no product code carries the Windows shape.
- Re-baselined the author's live LifeOS nightguard instance onto the Linux `blocking:` schema (curfew 20:45) and re-signed `guard.json` via the Python control CLI — but first had to recover the entire Linux Python trust stack, which had been deleted from disk and was unrecoverable via git.
- Made the integrity wall root-backed: the watchdog now runs as a systemd system service (root) and the `.guardkey` is `root:root 0600`, so a non-root user can no longer forge a valid signature — done as a prove-then-switch cutover with no protection gap. Closes ROOT-01 + ROOT-02.
- Made the control-CLI the sole root signer — reachable only by elevating via `sudo` (password = the anti-impulse friction) — enforcing the weekly token quota in-process and chowning `config.yaml` back to the user after each commit. Closes ROOT-03 + ROOT-04.
- Live runtime probe proved the Claude Code `UserPromptSubmit` hook fires BEFORE slash-command expansion (raw `prompt` text, not an expanded `<command-name>` blob), so the curfew allowlist uses the tighter leading-token matcher — recorded as `MATCHER: leading-token` for Plan 02.
- Built `LifeOS/hooks/nightguard_adapter.py` — the Linux curfew adapter that translates a `guard.py` `deny` verdict (exit 1) into a Claude Code hard-block (exit 2 + Spanish-butler stderr), honors a leading-token slash-command allowlist, and fails closed on every error branch — and signed `/plan` into `config.yaml curfew.allow_commands` via the root control-CLI (verify all-green).
- Taught the LifeOS generator (`sync_agent_config.py`) to idempotently emit a global `UserPromptSubmit` curfew hook into user-scope `~/.claude/settings.json` (the full-D-04 Q2 resolution), applied it to make the hook live in every Claude Code session, and verified all three ROADMAP success criteria end-to-end — closing CURF-01 so curfew now actually blocks sessions.
- Extracted a pure, key-less, string-only `curfew_verdict(cfg, state)` from `guard.py`'s `decide()` and re-expressed `decide()` in terms of it, so the curfew/grace/true-time/clock-tamper/offline gating math is defined exactly once and the Phase-8 watchdog native-kill gate can consume the same verdict without re-running `verify_and_revert` or the HMAC audit chain.
- 1. [Rule 3 - Blocking] Plan `<verify>` greps for `shell=True` and a single `verify_and_revert` would have failed on doc/comment mentions of those literals
- VERDICT: FAIL — `stayfree-desktop` records 0 sessions on Hyprland/Wayland (usage.db empty, Dashboard shows 0s), so it cannot track and therefore cannot block native or XWayland apps. Routes to 09-03 (analytics-only fallback); 09-02 keep-alive is NOT built.
- StayFree recorded as analytics-only (degraded — no live tracking on Wayland); keep-alive moot and NOT built; no native-app hard guarantee accepted; 09-CONTEXT.md re-opened per D-09. No enforcement code added.
- Greenfield `ngtui/` Textual package with `backend.py` as the single key-less seam to the LifeOS Python trust stack, plus a Wave-0 spike that proved inline sudo via `App.suspend()` works.
- The read-only StatusScreen (lock status / countdown / token meter / grace / hmacs / ledger) sourced entirely from the guard verdict + signed state, painted in live omarchy desktop colours that repaint the running TUI when the desktop theme changes.
- Textual EditScreen that edits the D-09 field set via single-key nav, composes the proposed config by format-preserving per-field line edits (no YAML emit), front-loads the signer's own tighten/loosen + token-cost verdict BEFORE any sudo prompt, and commits inside App.suspend() so sudo's prompt is inline — the core anti-impulse moment the product exists for.

---

---

## v2.2 · Deferred maintenance — opened 2026-09-14

The milestone that exists to be *not* worked on yet. Four phases, all recorded on
the day they were found, all deferred by the owner with the same reasoning: the
product works for the one person using it, and a defect that costs nothing today
is not worth the churn. Each carries the condition that should reopen it, so the
decision is a decision rather than a thing that was forgotten.

- **Phase 14 — a stranger's first install.** Three ways the installer leaves
  somebody with a product that looks installed and is not: `sudo -i` clears the
  variable owner detection reads, a missing `uv` degrades into a read-only panel
  with no explanation, and a first install tells you to clean up a directory that
  never existed. *Reopens when somebody else's install fails.*
- **Phase 15 — browser lock coverage.** The Gecko browser map is two hard-coded
  Arch paths, in both the installer and the verifier. A third browser gets no
  policy and no probe, and the verifier still prints `LOCKED: yes`. Tracked as
  issue #1. *Reopens on a third browser, or when someone asks.*
- **Phase 16 — config surface truth.** Four keys are priced and editable that
  nothing in this repository reads; four keys the code does read appear in no
  example. *Reopens when somebody changes one of the dead keys and nothing
  happens.*
- **Phase 17 — suite dead weight.** Four unused fixtures (about 250 of 579
  lines), one importing a module that no longer exists; three live-stack tests
  that skip on every machine. *Reopens on collection time, or on somebody
  trusting a fixture that no test uses.*

Everything above was found by agents reading the code while writing the
reference documentation, not by a test failing. That is the point worth keeping:
the suite was green for all of it.
