---
phase: 11
slug: global-install-status-subcommand
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Critical failure modes (from RESEARCH.md): **key-lessness** of the status path,
> **fail-closed** behavior, **clean-env resolution**, and **PTY survival**.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (configured in `ngtui/pyproject.toml` → `[tool.pytest.ini_options]`, `pythonpath=["."]`, `testpaths=["tests"]`) |
| **Config file** | `ngtui/pyproject.toml` |
| **Quick run command** | `cd ngtui && .venv/bin/python -m pytest -x -q` |
| **Full suite command** | `cd ngtui && .venv/bin/python -m pytest` |
| **Estimated runtime** | ~5 seconds (stdlib-only unit tests, no subprocess/TTY) |

---

## Sampling Rate

- **After every task commit:** Run `cd ngtui && .venv/bin/python -m pytest -x -q`
- **After every plan wave:** Run `cd ngtui && .venv/bin/python -m pytest`
- **Before `/gsd:verify-work`:** Full suite green + the two manual checkpoints (SC-1 clean-env shim, SC-4 live token commit)
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-xx | — | 0 | DESK-02 | T-V4 | status path makes ZERO `read_key()` calls (key-less) | unit | `pytest tests/test_status.py::test_status_never_reads_key -x` (monkeypatch `read_key`→raise; assert no raise) | ❌ W0 | ⬜ pending |
| 11-xx | — | 0 | DESK-02 | — | `status --json` emits single-line, `jq`-valid `{text,tooltip,class}` | unit | `pytest tests/test_status.py::test_status_json_shape -x` | ❌ W0 | ⬜ pending |
| 11-xx | — | 0 | DESK-02/SC-3 | — | import/stack failure → `{"text":"○ —","class":"unavailable"}` exit 0 | unit | `pytest tests/test_status.py::test_status_fail_closed_on_bad_stack -x` (`NIGHTGUARD_STACK_DIR=/nonexistent`) | ❌ W0 | ⬜ pending |
| 11-xx | — | 0 | SC-3 | — | empty data dir → `locked` class, NOT `unavailable` | unit | `pytest tests/test_status.py::test_empty_data_is_locked_not_unavailable -x` | ❌ W0 | ⬜ pending |
| 11-xx | — | 0 | DESK-02 | — | verdict→class map covers all 5 verdict strings | unit | `pytest tests/test_status.py::test_verdict_class_map -x` | ❌ W0 | ⬜ pending |
| 11-xx | — | 0 | DESK-02 | T-DoS | `status` performs no synchronous network query (fast on cold cache) | unit | `pytest tests/test_status.py::test_status_no_blocking_ntp -x` (assert no `_sntp`/`_http_time` call) | ❌ W0 | ⬜ pending |
| 11-xx | — | 0 | SC-4 | — | bare `ngtui` with no TTY fails loudly (exit≠0) | unit | `pytest tests/test_status.py::test_tui_requires_tty -x` (monkeypatch `sys.stdin.isatty`→False; assert `SystemExit`) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are placeholders — the planner assigns final `{phase}-{plan}-{task}` IDs.*

---

## Wave 0 Requirements

- [ ] `ngtui/tests/test_status.py` — covers DESK-02, SC-2, SC-3, SC-4 (the new subcommand + TTY guard). The status handler core (verdict/tokens → JSON shape, and the fail-closed wrapper) must be a **pure, importable function** unit-testable without a TTY or subprocess (mirrors Phase 10's `verdict_display`/`token_meter` pure-helper pattern).
- [ ] `ngtui/tests/conftest.py` — fixtures for a temp `NIGHTGUARD_DIR` with crafted `guard.json`/`config.sanctioned.yaml` (locked / grace / outside / empty), plus a `read_key`-explodes monkeypatch fixture.
- [ ] Framework install: already present (`.venv` has pytest; `ngtui/tests/` exists with prior Phase 10 headless tests).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `uv tool install` shim resolves the stack from a clean login shell | DESK-01 / SC-1 | Requires a real isolated-venv install + scrubbed env; not reproducible in-process | `uv tool install --python 3.14 .` then `env -i HOME=$HOME PATH=$HOME/.local/bin:/usr/bin:/bin ngtui status --json` returns valid JSON (verified live during research) |
| Real loosen-with-token commit from the installed shim (PTY path) | DESK-01 / SC-4 | Consumes a real weekly token; needs an interactive terminal + live `sudo` | Live walkthrough: launch installed `ngtui`, stage a loosen, confirm, enter `sudo` password, observe commit succeeds (human-verify checkpoint) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`tests/test_status.py`, `tests/conftest.py`)
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
