# Phase 11: Global Install + Status Subcommand - Pattern Map

**Mapped:** 2026-06-25
**Files analyzed:** 5 (2 modified, 2 new test, 1 new source helper — plus 1 packaging no-op)
**Analogs found:** 5 / 5 (every new/modified file has a strong in-repo analog)

> Phase 11 is **glue + packaging**: a key-less, stdlib-only `status` reader subcommand,
> a TTY guard on the TUI branch, and head-less tests. No new deps, no crypto. Every
> load-bearing pattern already exists in the Phase 10 read surface (`backend.py`,
> `widgets/status.py`) and the Phase 10 headless test suite — this map points each new
> file at its exact in-repo analog with line-referenced excerpts.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `ngtui/ngtui/__main__.py` (modify) | entry-point / argv router | request-response | itself (current bare `main()`) + RESEARCH Pattern 3 | exact (extends existing) |
| `ngtui/ngtui/status.py` (new — the pure `_shape`/verdict→class/JSON builder) | utility (pure read-surface) | transform | `ngtui/ngtui/widgets/status.py` pure helpers (`verdict_display`, `token_meter`) | exact (role + pure-transform) |
| `ngtui/tests/test_status_cli.py` (new) | test (headless unit) | transform | `ngtui/tests/test_status.py` + `test_backend_stackdir.py` + `test_port03_no_crypto.py` | exact |
| `ngtui/tests/conftest.py` (modify — add temp-`NIGHTGUARD_DIR` fixtures) | test fixture / bootstrap | — | existing `ngtui/tests/conftest.py` + `test_backend_stackdir.py` monkeypatch | exact |
| `ngtui/pyproject.toml` (likely no-op) | config / packaging | — | itself (already declares the script + pytest config) | exact (already satisfies DESK-01) |

> **Naming note for the planner:** a `tests/test_status.py` **already exists** and tests
> the Phase 10 status *widget* helpers (`verdict_display`/`token_meter`/`ledger_rows`).
> Do NOT overwrite it. Put the new subcommand tests in a distinct file
> (`test_status_cli.py` or `test_status_subcommand.py`). Likewise, the new pure builder
> should live in a new module (e.g. `ngtui/ngtui/status.py`) — there is no `cli.py`/
> `status.py` at the package root today (`ls ngtui/ngtui/` → app.py, app.tcss, backend.py,
> __init__.py, lineedit.py, __main__.py, theme.py, widgets/).

## Pattern Assignments

### `ngtui/ngtui/__main__.py` (entry-point, argv router) — MODIFY

**Analog:** the file itself (current bare entry point) + RESEARCH.md Pattern 3 (lines 184-218).

**Current state** (`ngtui/ngtui/__main__.py:1-17`) — bare, no argv routing, eager `ngtui.app` import:
```python
"""Console entry point for the ngtui Textual app (`ngtui = ngtui.__main__:main`).
...
"""
from __future__ import annotations

from ngtui.app import NightguardApp


def main() -> None:
    NightguardApp().run()


if __name__ == "__main__":
    main()
```

**Required changes (from RESEARCH Pattern 3 + Pitfalls 2/4/5):**
1. **Make the `ngtui.app`/`textual` import lazy** — move `from ngtui.app import NightguardApp` *inside* the TUI branch so `ngtui status` never pays textual's import cost (RESEARCH line 218, Anti-Pattern at 229).
2. **argparse (or bare-argv) front controller** routing `status` → head-less handler, bare `ngtui` → TUI (RESEARCH lines 189-194).
3. **TTY guard on the TUI branch ONLY** via `sys.stdin.isatty()` → loud fail `SystemExit(2)` (RESEARCH lines 196-199; Pitfall 4 lines 298-304 — must NOT be a blanket check at top of `main()`, it would break the head-less `status`).
4. **Update the stale docstring** (Pitfall 5, lines 306-308): it currently claims the bootstrap "sets NIGHTGUARD_DIR" — backend uses `os.environ.setdefault` to a hardcoded author path; reflect the argparse routing + hardcoded-default reality.

**Pattern to copy** (RESEARCH `__main__.py` skeleton, lines 187-216 — planner finalizes):
```python
import sys

def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] == "status":
        sys.exit(_status(argv[1:]))   # head-less; emits JSON, exits 0
    _run_tui()                         # bare `ngtui`

def _run_tui() -> None:
    if not sys.stdin.isatty():         # SC-4 loud fail — TUI path ONLY (Pitfall 4)
        sys.stderr.write("ngtui must be run in a terminal (no TTY on stdin).\n")
        raise SystemExit(2)
    from ngtui.app import NightguardApp   # lazy: status never imports textual
    NightguardApp().run()
```

**Fail-closed wrapper** (RESEARCH lines 202-216; Pitfall 2 — `import ngtui.backend` must be INSIDE the try, it raises `RuntimeError` at import on a bad `NIGHTGUARD_STACK_DIR`):
```python
def _status(args) -> int:
    import json
    UNAVAIL = {"text": "○ —", "class": "unavailable"}
    try:
        import ngtui.backend as b          # CAN raise RuntimeError (bad STACK_DIR)
        state = b.read_state()
        cfg = b.sanctioned_config()
        verdict = b.live_verdict(cfg, state)   # Pitfall 1: guard the cold-cache path
        tokens = b.tokens_left()
        obj = _shape(verdict, tokens, state)   # → ngtui/status.py (pure)
    except Exception:                          # broad on purpose — fail closed (SC-3)
        obj = UNAVAIL
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    return 0                                   # ALWAYS exit 0 (SC-3)
```

---

### `ngtui/ngtui/status.py` (utility, pure transform) — NEW

**Analog:** `ngtui/ngtui/widgets/status.py` — the Phase 10 pure read-surface helpers. This is the **exact** pattern to mirror: a `_VERDICT_MAP` dict + a pure `def f(verdict) -> ...` that fails closed to LOCKED, unit-tested headless without an App.

**Why a separate module from `__main__`:** the new core (verdict + tokens → Waybar `{text,tooltip,class}` object, plus the verdict→class map) MUST be a **pure, importable function** so it unit-tests without a TTY or subprocess (RESEARCH Wave-0 Gap, line 415: "mirrors Phase 10's `verdict_display`/`token_meter` pure-helper pattern"). Keeping it out of `__main__.py` also keeps it textual-free.

**Imports/module-doc pattern** to copy (`ngtui/ngtui/widgets/status.py:1-17, 17-27`) — module docstring states the "pure helpers, headless-testable" contract; import only stdlib here (no textual, no backend at module top if avoidable — the subcommand passes values in):
```python
"""status.py — the read-only StatusScreen (D-10) and its pure display helpers.
...
The load-bearing logic lives in PURE helpers (``verdict_display``, ``token_meter``,
``ledger_rows``) so it unit-tests headless without a running App; ...
"""
from __future__ import annotations
```

**The verdict-string set + fail-closed map** — the authoritative analog (`ngtui/ngtui/widgets/status.py:31-55`). The 5 verdict strings are fixed by `backend.live_verdict` (`backend.py:100-106`): `locked | grace_active | outside_curfew | clock_tamper | offline_blocked`. Mirror the `dict.get(verdict, default_locked)` fail-closed shape:
```python
_VERDICT_MAP: dict[str, tuple[str, str, str, str]] = {
    "locked": ("●", "LOCKED", "error", ""),
    "outside_curfew": ("○", "OPEN", "success", ""),
    "grace_active": ("◐", "GRACE", "accent", ""),
    "clock_tamper": ("●", "LOCKED", "error", "clock tamper detected — locked"),
    "offline_blocked": ("●", "LOCKED", "error", "time unverified — guard keeps the house closed"),
}

def verdict_display(verdict: str) -> tuple[str, str, str, str]:
    """... Unknown verdicts fail closed to LOCKED (never optimistically OPEN — T-10-05)."""
    return _VERDICT_MAP.get(verdict, _VERDICT_MAP["locked"])
```

**New Phase 11 requirement layered on top:** a verdict → Waybar **`class`** map covering all 5 strings (Pitfall 3, lines 288-296: empty data → `live_verdict` returns `"locked"` and MUST render as `locked`, NOT `unavailable`; `unavailable` is reserved for the `except` branch only). The `class` value should be the verdict string itself or a CSS-safe mapping (`locked`/`grace_active`/`outside_curfew`/`clock_tamper`/`offline_blocked`) — see RESEARCH line 296. The new `_shape(verdict, tokens, state) -> dict` returns `{"text","tooltip","class"}` (RESEARCH lines 323-336), emitted single-line via `json.dumps(obj, separators=(",", ":"))`.

**Token rendering analog** (`ngtui/ngtui/widgets/status.py:73-84`) — if the `text`/`tooltip` shows the token count, reuse the clamp + `WEEKLY_TOKENS` sourcing pattern (never a local `3` literal — re-export `backend.WEEKLY_TOKENS`, `backend.py:63`):
```python
left = max(0, min(WEEKLY_TOKENS, tokens_left))   # clamp before render
```

**Pitfall-1 cold-cache guard (the one design decision):** `live_verdict` → `guard.curfew_verdict` → `guard.true_unix()` can block ~2-4s on a cold NTP cache (RESEARCH lines 259-274). Recommendation = option 2 (status path performs NO synchronous network query — cache-only read). This shapes where the verdict is resolved; the pure `_shape` itself takes the already-resolved verdict string, so the guard lives at the `live_verdict` call site in `__main__._status`, not in `status.py`.

---

### `ngtui/tests/test_status_cli.py` (test, headless unit) — NEW

**Analogs (three, combined):**
1. `ngtui/tests/test_status.py` — the pure-helper headless test shape (import the pure function, assert exact tuples, cover every verdict incl. the unknown→LOCKED fail-closed case).
2. `ngtui/tests/test_backend_stackdir.py` — `monkeypatch.setenv("NIGHTGUARD_STACK_DIR", ...)` + `pytest.raises(RuntimeError)` for the bad-stack fail-closed path (SC-3).
3. `ngtui/tests/test_port02_commit_argv.py` — `unittest.mock.patch("ngtui.backend.<name>", ...)` to monkeypatch the backend seam and capture/inject behaviour (for the key-less + no-blocking-NTP assertions).

**Headless pure-helper assertion pattern** (`ngtui/tests/test_status.py:20-41`) — copy this shape for the new `_shape`/verdict→class tests, including the explicit "unknown fails closed" line:
```python
def test_verdict_display_maps_every_state():
    glyph, word, role, _caption = verdict_display("locked")
    assert (glyph, word, role) == ("●", "LOCKED", "error")
    ...
    # Unknown verdict fails closed to LOCKED (never optimistic OPEN — T-10-05).
    assert verdict_display("???")[:3] == ("●", "LOCKED", "error")
```

**Fail-closed-on-bad-stack pattern** (`ngtui/tests/test_backend_stackdir.py:25-32`) — for `test_status_fail_closed_on_bad_stack` (SC-3, `NIGHTGUARD_STACK_DIR=/nonexistent` → import raises → `_status` must emit `unavailable`, exit 0):
```python
def test_resolve_stack_dir_rejects_dir_without_ctl(tmp_path, monkeypatch):
    monkeypatch.setenv("NIGHTGUARD_STACK_DIR", str(tmp_path))
    with pytest.raises(RuntimeError) as exc:
        backend._resolve_stack_dir()
    assert "nightguard_ctl.py" in str(exc.value)
```

**Key-less proof pattern** — two analog options:
- *Static AST scan* (`ngtui/tests/test_port03_no_crypto.py:80-112`): asserts no `.read_key()` call appears in the ngtui package source. The new `status.py`/`__main__.py` are already covered by this existing test if they live under `ngtui/ngtui/` — confirm it still passes; no new `read_key`/`hmac`/`hexdigest`.
- *Runtime monkeypatch* (RESEARCH lines 171-174, 399): patch `ng.read_key`/`guard.ng.read_key`/`ctl.ng.read_key` to raise `AssertionError`, run the status path, assert no raise — the live-verified "status path made ZERO read_key() call" proof. Use `patch("ngtui.backend.<...>")` per the `test_port02_commit_argv.py:50` style.

**No-blocking-NTP assertion** (RESEARCH line 404) — monkeypatch `guard._sntp`/`guard._http_time` to raise/record, assert the status path never calls them (or assert runtime < threshold). Same `unittest.mock.patch` mechanics.

**The full DESK-02/SC-2/SC-3/SC-4 test map is already enumerated** in RESEARCH lines 399-405 (test names: `test_status_never_reads_key`, `test_status_json_shape`, `test_status_fail_closed_on_bad_stack`, `test_empty_data_is_locked_not_unavailable`, `test_verdict_class_map`, `test_status_no_blocking_ntp`, `test_tui_requires_tty`).

**TTY-guard test** (RESEARCH line 405) — `monkeypatch.setattr(sys.stdin, "isatty", lambda: False)` (or monkeypatch `sys.stdin`), call the TUI launch path, assert `SystemExit` with a non-zero code; assert the `status` path is unaffected.

---

### `ngtui/tests/conftest.py` (fixture / bootstrap) — MODIFY

**Analog:** the existing `ngtui/tests/conftest.py:1-18` (env bootstrap) + `test_backend_stackdir.py` `tmp_path`+`monkeypatch` fixtures.

**Existing bootstrap to keep** (`ngtui/tests/conftest.py:11-18`) — sets the author-instance defaults at collection time so `import ngtui.backend` (transitively imported by the status helpers) resolves cleanly:
```python
os.environ.setdefault(
    "NIGHTGUARD_STACK_DIR", "/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard"
)
os.environ.setdefault(
    "NIGHTGUARD_DIR", "/home/danitrrga/dev/Projects/LifeOS/nightguard"
)
```

**Fixtures to ADD** (RESEARCH Wave-0 Gap, line 416): a `tmp_path`-backed temp `NIGHTGUARD_DIR` fixture with crafted `guard.json` / `config.sanctioned.yaml` covering the verdict states (locked / grace / outside / empty), and a `read_key`-explodes monkeypatch fixture. Copy the `tmp_path` + `monkeypatch.setenv` shape from `test_backend_stackdir.py:15-18`:
```python
(tmp_path / "nightguard_ctl.py").write_text("# stand-in signer CLI\n")
monkeypatch.setenv("NIGHTGUARD_STACK_DIR", str(tmp_path))
```
For the temp `NIGHTGUARD_DIR` fixture, write `guard.json` (`weekly_spent`, `week_anchor`, `ledger`, `grace`) and `config.sanctioned.yaml` into `tmp_path` and `monkeypatch.setenv("NIGHTGUARD_DIR", str(tmp_path))`. Backend reads via `ng.load_state()` / `ng.file_bytes(ng.SANCTIONED)` (`backend.py:75-97`), so the fixture only needs the two `0644`-equivalent files on disk. Note the empty-dir behaviour to assert (Pitfall 3): missing files → `live_verdict="locked"`, `tokens_left=3`, no exception — maps to `class:"locked"`, NOT `unavailable`.

---

### `ngtui/pyproject.toml` (config / packaging) — LIKELY NO-OP

**Analog:** the file itself. DESK-01 is **already structurally satisfied** — no edit needed unless the planner adds metadata:
- `[project.scripts] ngtui = "ngtui.__main__:main"` already present (`pyproject.toml:8-9`) — the global shim entry point.
- `[tool.hatch.build.targets.wheel] packages = ["ngtui"]` (`pyproject.toml:15-16`) — wheel build for `uv tool install`. A new `ngtui/status.py` lands automatically (it is inside the `ngtui` package); no manifest edit needed.
- `[tool.pytest.ini_options] pythonpath=["."]`, `testpaths=["tests"]` (`pyproject.toml:18-22`) — the new test file is collected automatically.

The install itself is `uv tool install --python 3.14 .` (RESEARCH lines 80-86), an OS/packaging action, not a code change. Only touch `pyproject.toml` if adding e.g. a `[project] keywords`/`classifiers` or a `requires-python` bump (none required).

## Shared Patterns

### Key-less data path (the seam the status reader wraps)
**Source:** `ngtui/ngtui/backend.py:75-132`
**Apply to:** `ngtui/ngtui/status.py`, `__main__._status`
The four read functions are the entire status data path — all key-less, all sourcing `root:root 0644` files / pure functions:
```python
def read_state() -> dict:               # ng.load_state() → json.load(guard.json)  (backend.py:75-77)
def sanctioned_config() -> dict:        # ng.file_bytes(SANCTIONED) → yaml_load    (backend.py:80-85)
def live_verdict(cfg, state) -> str:    # guard.curfew_verdict — NO key (Pitfall 1) (backend.py:100-106)
def tokens_left() -> int:               # ctl.quota_decide([], state, tz) — pure    (backend.py:125-132)
```
`live_verdict` returns one of exactly 5 strings (docstring `backend.py:103-105`):
`"locked" | "grace_active" | "outside_curfew" | "clock_tamper" | "offline_blocked"`.
`WEEKLY_TOKENS` is re-exported from the signer (`backend.py:63`) — never a local `3`.

### Fail-closed-to-LOCKED on unknown input
**Source:** `ngtui/ngtui/widgets/status.py:48-55`
**Apply to:** `ngtui/ngtui/status.py` (verdict→display/class), and conceptually the `_status` except branch.
Pattern: `dict.get(key, _MAP["locked"])` so an unknown verdict renders LOCKED, never OPEN (T-10-05). DISTINCT from the `unavailable` fallback, which is reserved for the import/read **exception** path only (Pitfall 3).

### Env-bootstrap-before-import for headless tests
**Source:** `ngtui/tests/conftest.py:11-18`
**Apply to:** all new tests that transitively import `ngtui.backend`/`ngtui.status`.
Set `NIGHTGUARD_STACK_DIR` / `NIGHTGUARD_DIR` via `os.environ.setdefault(...)` at conftest top-level so `import ngtui.backend`'s module bootstrap (`backend.py:46-58`) resolves before collection.

### Backend-seam monkeypatch for behavioural tests
**Source:** `ngtui/tests/test_port02_commit_argv.py:46-53` (`patch("ngtui.backend.subprocess.run", ...)`)
**Apply to:** the key-less proof, no-blocking-NTP, and verdict-injection tests.
Use `unittest.mock.patch("ngtui.backend.<target>")` (or `monkeypatch.setattr`) to inject/forbid a backend behaviour and assert the status path's interaction — the live-verified technique for proving "zero read_key calls" / "no SNTP fall-through".

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | Every Phase 11 file maps to an existing in-repo analog. The phase is glue over the Phase 10 read surface; nothing is structurally new. |

## Metadata

**Analog search scope:** `ngtui/ngtui/` (package source), `ngtui/tests/` (Phase 10 headless suite), `ngtui/pyproject.toml`, and the LifeOS trust stack signatures in `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/ngcommon.py` (`read_key`/`load_state`/`file_bytes`/`SANCTIONED` confirmed).
**Files scanned:** `__main__.py`, `backend.py`, `app.py`, `widgets/status.py`, `pyproject.toml`, `tests/conftest.py`, `tests/test_status.py`, `tests/test_backend_stackdir.py`, `tests/test_port03_no_crypto.py`, `tests/test_port02_commit_argv.py` (head), plus a package/grep listing confirming no existing `status.py`/`cli.py`/argparse/isatty in the package.
**Pattern extraction date:** 2026-06-25
