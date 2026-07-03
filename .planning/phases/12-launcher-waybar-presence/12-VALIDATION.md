---
phase: 12
slug: launcher-waybar-presence
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-03
approved: 2026-07-03
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 12-RESEARCH.md §Validation Architecture (verified against the live box).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (invoked via `uv run`; `[tool.pytest.ini_options]` in `ngtui/pyproject.toml`, `pythonpath=["."]`, `testpaths=["tests"]`) |
| **Config file** | `ngtui/pyproject.toml` |
| **Quick run command** | `cd ngtui && uv run pytest tests/test_backend_signal.py -x -q` |
| **Full suite command** | `cd ngtui && uv run pytest -q` |
| **Estimated runtime** | ~5–10 seconds (full ngtui suite) |

---

## Sampling Rate

- **After every task commit:** Run the relevant quick pytest file (`test_backend_signal.py`) **plus** the static greps on the touched artifact (`.desktop`, windowrule snippet, `ngtui-menu`).
- **After every plan wave:** Run `cd ngtui && uv run pytest -q` (full ngtui suite — guards the D-10 "no change to `status.py`" contract).
- **Before `/gsd:verify-work`:** Full suite green **and** the human-verify checkpoint for live desktop behaviors (below) complete.
- **Max feedback latency:** ~10 seconds (automated); live GUI checks are session-bound.

---

## Per-Task Verification Map

> Task IDs (`12-NN-MM`) are assigned by the planner; rows below are keyed by requirement and MUST each map to at least one task's `<automated>` verify (or a Wave 0 stub).

| Requirement | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|------------|-----------------|-----------|-------------------|-------------|--------|
| BAR-04 | `backend.commit()` fires `pkill -RTMIN+11 waybar` ONLY on `returncode==0`; never on non-zero; a raising `pkill` doesn't perturb the commit result | T-signal (Tampering) | Signal is fire-and-forget after success; errors swallowed; return value unchanged | unit (mock `subprocess.run`) | `cd ngtui && uv run pytest tests/test_backend_signal.py -x` | ❌ W0 | ⬜ pending |
| BAR-01 / D-10 | `status.py` still emits `{text,tooltip,class}` unchanged (regression — no change made) | — | No new mutation surface added to status path | unit | `cd ngtui && uv run pytest tests/test_status.py tests/test_status_cli.py -x` | ✅ | ⬜ pending |
| BAR-03 | `ngtui-menu` emits only open/read actions; NEVER a loosening/commit/grace action | T-lever (EoP — defeats self-binding) | "A window, never a lever" — menu is read-only + open-only | static/grep | `! grep -Eiq 'loosen\|token.*spend\|grace\|commit' packaging/omarchy/bin/ngtui-menu` | ❌ W0 | ⬜ pending |
| DESK-03 | `nightguard.desktop` `Exec` uses `--app-id=org.omarchy.ngtui -e ngtui`; `Terminal=false` | T-spoof (match class not title) | Float rule binds to stable `app_id`, not spoofable title | static | `grep -q 'app-id=org.omarchy.ngtui' <desktop> && grep -q 'Terminal=false' <desktop>` | ❌ W0 | ⬜ pending |
| DESK-03 (live) | launched window has `app_id == org.omarchy.ngtui` and floats/centers; other terminals still tile | — | — | manual/human-verify | `hyprctl clients -j \| jq '.[].class'` after launch | manual | ⬜ pending |
| DESK-04 (live) | icon appears in walker/launcher WITHOUT relogin | — | — | manual/human-verify | visual | manual | ⬜ pending |
| DESK-04 | icon SVG authored + hicolor PNGs (16→512) present; `.desktop` `Icon=org.omarchy.ngtui` | — | Own-brand asset only | static | `test -f <icon.svg> && grep -q 'Icon=org.omarchy.ngtui' <desktop>` | ❌ W0 | ⬜ pending |
| D-07 (BAR-02/DESK-03 install) | installer run twice → no duplicate injected blocks; backups created before mutation | T-clobber (DoS — locks author out of desktop) | Backup-first (`cp -a …bak.<epoch>`), marker-guarded, no JSON round-trip | integration (temp fixture configs) | `cd ngtui && uv run pytest tests/test_installer_idempotent.py -x` (or bash harness over fixtures) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `ngtui/tests/test_backend_signal.py` — BAR-04: success-only `pkill -RTMIN+11`, non-perturbing on `pkill` failure. Mock `subprocess.run` for both the `sudo` commit and the `pkill`.
- [ ] `ngtui/tests/test_installer_idempotent.py` (or a bash harness under `packaging/omarchy/`) — D-07: run-twice-no-dup + backup created, against fixture copies of `config.jsonc` / `hyprland.conf`.
- [ ] Static-grep checks for the `.desktop`, windowrule snippet, and `ngtui-menu` (no-loosening) — small pytest or shell check.
- [ ] **Prerequisite (BLOCKING, not a test):** `command -v ngtui` — `ngtui` is NOT currently on PATH (Phase 11's `~/.local/bin/ngtui` is absent). Reinstall + verify before any live-wiring task.
- Framework install: none needed (pytest already configured; run via `uv run`).

---

## Manual-Only Verifications

> These are GUI/session-bound and cannot be verified headless. Required at the phase gate (human-verify checkpoint).

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Launched window floats + centers with `app_id org.omarchy.ngtui`; other terminals still tile | DESK-03 | Needs a live Hyprland session + window manager | Launch from walker → `hyprctl clients -j \| jq '.[]\|select(.class=="org.omarchy.ngtui")'` shows `floating:true` |
| Icon renders on the launcher entry without relogin | DESK-04 | Requires the live icon cache + launcher GUI | After install, open walker → Nightguard entry shows the crescent-on-tile icon |
| Bar module renders live glyph+tokens, colored by state | BAR-01 | Requires running Waybar rendering the module | Observe `custom/nightguard` in the bar; class-colored per verdict |
| Left-click opens/focuses TUI; right-click opens read-only menu (no loosen action) | BAR-02 / BAR-03 | Requires live click interaction | Click the module; verify menu header (verdict/tokens/grace) + only open actions |
| Bar refreshes instantly after a real token-loosen commit (PTY path intact) | BAR-04 | End-to-end sudo-PTY commit + signal, session-bound | Run a real loosen commit from the launched TUI; bar updates before the poll interval |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (`test_backend_signal.py`, `test_installer_idempotent.py`, static greps)
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

> `wave_0_complete` stays `false` until execution: the Wave 0 test files
> (`test_backend_signal.py`, `test_installer_idempotent.py`) are authored RED-first
> during Plans 02/05, not at plan time. The executor flips it after Wave 0 runs.

**Approval:** approved 2026-07-03 (plan-checker: 0 blockers; strategy satisfied by plans)
