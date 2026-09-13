"""Headless tests for the key-less `ngtui status` core (Plan 11-01, DESK-02).

These exercise the pure Waybar status builder (``ngtui.status``) and the
``backend.cache_only_verdict`` seam without a TTY, subprocess, or argv. The
load-bearing contract — key-less, fail-closed-to-locked, single-line jq-valid
JSON, and NO synchronous SNTP/HTTP query on the read path — must hold in pure
functions so Plan 02's ``__main__`` router is thin glue.

Importing ``ngtui.status`` / ``ngtui.backend`` pulls in the trust stack; the env
vars that point at the live stack are set in conftest.py before collection.
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import time

import pytest

from ngtui import backend
from ngtui import status


# --- the pure builder ---------------------------------------------------------


def test_status_json_shape():
    """``_shape`` returns exactly {text,tooltip,class} and json.dumps-es single-line."""
    obj = status._shape("locked", 2, {"week_anchor": "2026-06-22"})
    assert set(obj.keys()) == {"text", "tooltip", "class"}

    line = json.dumps(obj, separators=(",", ":"))
    assert "\n" not in line  # single-line: Waybar reads one object per line
    # round-trips through a strict JSON parse (jq-valid by construction).
    assert json.loads(line) == obj


def test_verdict_class_map():
    """All 5 verdicts map to their own class; UNKNOWN fails closed to 'locked'."""
    assert status._VERDICT_CLASS["locked"] == "locked"
    assert status._VERDICT_CLASS["grace_active"] == "grace_active"
    assert status._VERDICT_CLASS["outside_curfew"] == "outside_curfew"
    assert status._VERDICT_CLASS["clock_tamper"] == "clock_tamper"
    assert status._VERDICT_CLASS["offline_blocked"] == "offline_blocked"

    # Unknown verdict -> "locked" (never "unavailable", never "outside_curfew").
    assert status._VERDICT_CLASS.get("???", "locked") == "locked"
    assert status._shape("???", 3, {})["class"] == "locked"
    assert status._shape("???", 3, {})["class"] != "unavailable"
    assert status._shape("???", 3, {})["class"] != "outside_curfew"


def test_unavailable_object():
    """The module's UNAVAILABLE object is the fixed fail-closed except-branch object."""
    assert status.UNAVAILABLE == {"text": "○ —", "class": "unavailable"}
    line = json.dumps(status.UNAVAILABLE, separators=(",", ":"))
    assert "\n" not in line
    assert json.loads(line) == status.UNAVAILABLE


# --- empty data is LOCKED, not unavailable (Pitfall 3) ------------------------


def test_empty_data_is_locked_not_unavailable(ng_data_dir_empty):
    """An empty/uninitialized data dir renders 'locked', never 'unavailable'."""
    verdict = backend.live_verdict({}, {})
    assert verdict == "locked"
    assert backend.tokens_left() == 3

    obj = status._shape(verdict, backend.tokens_left(), {})
    assert obj["class"] == "locked"
    assert obj["class"] != "unavailable"


# --- the cache-only seam never blocks on the network (Pitfall 1 / T-11-04) ----


def test_status_no_blocking_ntp(ng_data_dir_empty, monkeypatch):
    """cache_only_verdict resolves WITHOUT a synchronous SNTP/HTTP query.

    The override seam is removed for this test so a forced-cold cache would
    normally fall through to ``_sntp``/``_http_time``. Those are swapped for
    record-and-raise stubs; the call must complete instantly (well under the
    real ~4s two-timeout block) and end in a fail-closed offline verdict.
    """
    # Drop the deterministic override so true_unix() must hit the fall-through.
    monkeypatch.delenv("NIGHTGUARD_TEST_NTP_OVERRIDE", raising=False)
    monkeypatch.delenv("NIGHTGUARD_NTP_OVERRIDE_UNIX", raising=False)

    calls = {"sntp": 0, "http": 0}

    def rec_sntp(*_a, **_k):
        calls["sntp"] += 1
        raise OSError("no network in test")

    def rec_http(*_a, **_k):
        calls["http"] += 1
        raise OSError("no network in test")

    monkeypatch.setattr(backend.guard, "_sntp", rec_sntp, raising=False)
    monkeypatch.setattr(backend.guard, "_http_time", rec_http, raising=False)

    cfg = backend.sanctioned_config()
    state = backend.read_state()

    t0 = time.monotonic()
    verdict = backend.cache_only_verdict(cfg, state)
    elapsed = time.monotonic() - t0

    assert verdict in {
        "locked",
        "grace_active",
        "outside_curfew",
        "clock_tamper",
        "offline_blocked",
    }
    # Cold cache + no verifiable time -> fail-closed offline (the wanted behaviour).
    assert verdict == "offline_blocked"
    # No blocking: instant-raise stubs, not the real 2s+2s timeouts.
    assert elapsed < 0.2, f"cache_only_verdict blocked for {elapsed:.2f}s"


# --- DESK-02: the status path never reads the key -----------------------------


def test_status_never_reads_key(ng_data_dir, read_key_explodes):
    """read_state / sanctioned_config / cache_only_verdict / tokens_left read no key."""
    # None of these should trigger a read_key() — the explode fixture asserts it.
    state = backend.read_state()
    cfg = backend.sanctioned_config()
    backend.cache_only_verdict(cfg, state)
    backend.tokens_left()
    # If we got here, zero read_key calls fired (the fixture would have raised).
    assert isinstance(state, dict)


# --- Plan 02: the __main__ router (fail-closed / exit-0 / TTY / no-textual) ----
#
# These exercise the argv front-controller in ``ngtui.__main__`` (``_status`` and
# ``_run_tui``). The load-bearing contract: ``status`` ALWAYS emits one JSON line
# and exits 0 — a poisoned stack import, an arbitrary backend error, anything —
# degrades to the fixed ``unavailable`` object (SC-3); and the head-less path
# never pulls ``textual`` into the process (the import cost lives on the TUI
# branch only, behind a TTY guard).


def _capture_status(argv):
    """Run ``__main__._status(argv)`` capturing stdout; return (rc, stdout)."""
    from ngtui import __main__ as cli

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli._status(argv)
    return rc, buf.getvalue()


@pytest.fixture
def _restore_backend_module():
    """Restore a healthy ``ngtui.backend`` after a test evicts it from sys.modules.

    ``test_status_fail_closed_on_bad_stack`` deletes ``ngtui.backend`` so the
    in-try import re-runs against a poisoned ``NIGHTGUARD_STACK_DIR``. Without this
    finalizer the evicted/half-imported module would leak into later tests.
    """
    saved = sys.modules.get("ngtui.backend")
    try:
        yield
    finally:
        if saved is not None:
            sys.modules["ngtui.backend"] = saved
        else:  # pragma: no cover - backend is always imported by this module
            sys.modules.pop("ngtui.backend", None)
        import ngtui.backend  # noqa: F401  (re-import a clean module for later tests)


def test_status_fail_closed_on_bad_stack(tmp_path, monkeypatch, _restore_backend_module):
    """A poisoned NIGHTGUARD_STACK_DIR makes the in-try import raise -> unavailable.

    The import of ``ngtui.backend`` lives INSIDE ``_status``'s try (Pitfall 2), so
    a ``RuntimeError`` raised at *import* (the stack dir lacks nightguard_ctl.py)
    degrades to the fixed object and STILL exits 0 — never a traceback.
    """
    # tmp_path has no nightguard_ctl.py -> _resolve_stack_dir raises at import.
    monkeypatch.setenv("NIGHTGUARD_STACK_DIR", str(tmp_path))
    # Evict so the in-try `import ngtui.backend` re-executes the bootstrap.
    monkeypatch.delitem(sys.modules, "ngtui.backend", raising=False)

    rc, out = _capture_status(["--json"])

    assert rc == 0
    assert out.count("\n") == 1
    obj = json.loads(out)
    assert obj == {"text": "○ —", "class": "unavailable"}


def test_status_exit_zero_on_arbitrary_error(ng_data_dir, monkeypatch):
    """ANY backend error on the read path -> unavailable, exit 0 (broad-except)."""

    def _boom(*_a, **_k):
        raise RuntimeError("simulated read failure")

    monkeypatch.setattr(backend, "read_state", _boom)

    rc, out = _capture_status(["--json"])

    assert rc == 0
    assert json.loads(out) == {"text": "○ —", "class": "unavailable"}


def test_status_jq_valid_single_line(ng_data_dir_outside):
    """On a healthy stack, status emits exactly one jq-valid {text,class,...} line."""
    rc, out = _capture_status(["--json"])

    assert rc == 0
    assert out.count("\n") == 1  # single line, one trailing newline
    obj = json.loads(out)  # jq-valid by construction
    assert {"text", "class"} <= set(obj.keys())
    # A healthy read never degrades to the except-branch object.
    assert obj["class"] != "unavailable"


def test_the_bare_command_says_where_the_editor_went(capsys):
    """A bare ``ngtui`` used to start an interactive editor. It is retired, and
    somebody with that in muscle memory — or a stale .desktop file — deserves a
    sentence rather than a traceback or a silent success.

    Exit 2 and not 0: a launcher that treats success as "it opened" must not be
    told this opened.
    """
    from ngtui import __main__ as cli

    with pytest.raises(SystemExit) as exc:
        cli._no_terminal_app([])
    assert exc.value.code == 2

    err = capsys.readouterr().err
    assert "terminal editor is retired" in err
    assert "danitrrga.nightguard" in err, "it must say where the editor went"
    assert "status --json" in err, "and what this command still answers"


def test_an_unknown_subcommand_is_named_back(capsys):
    from ngtui import __main__ as cli

    with pytest.raises(SystemExit):
        cli._no_terminal_app(["edit"])
    assert "unknown command 'edit'" in capsys.readouterr().err

def test_status_does_not_import_textual():
    """The status path must not pull ``textual`` into sys.modules (head-less).

    Run in a fresh subprocess so import pollution from earlier tests (which may
    have imported textual) cannot mask a regression.
    """
    prog = (
        "import sys, io, contextlib\n"
        "from ngtui import __main__ as cli\n"
        "buf = io.StringIO()\n"
        "with contextlib.redirect_stdout(buf):\n"
        "    rc = cli._status(['--json'])\n"
        "assert rc == 0, rc\n"
        "assert 'textual' not in sys.modules, 'textual was imported on the status path'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", prog],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "OK" in result.stdout


class _ExplodingModule:
    """A stand-in module object whose any attribute access raises (import guard)."""

    def __init__(self, message: str) -> None:
        self._message = message

    def __getattr__(self, _name):  # pragma: no cover - only hit on a guard regression
        raise AssertionError(self._message)
