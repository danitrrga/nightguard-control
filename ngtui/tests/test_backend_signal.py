"""BAR-04 / D-11: commit() fires a success-only, non-perturbing Waybar refresh.

Requirement: "backend.commit() fires `pkill -RTMIN+11 waybar` exactly once when
the commit returncode is 0, NEVER on a non-zero returncode, and a raising pkill
subprocess is swallowed so commit() still returns the real {returncode, stdout}
result" (BAR-04 / D-11 / 12-02-PLAN).

The bar reflects a token spend the instant it happens, not on the next 30s poll —
without the signal ever faking or corrupting the anti-impulse commit outcome
(T-12-02 / T-12-03).

These properties cannot be verified by reading the source alone; they require
running commit() with a monkeypatched subprocess.run. With the signal added there
are now TWO subprocess.run calls per commit, so the mock branches on argv[0]:
  - "sudo"  -> the commit call (returns a _FakeProc)
  - "pkill" -> the refresh signal (recorded, or made to raise)
"""
from __future__ import annotations

from unittest.mock import patch

from ngtui import backend


class _FakeProc:
    """Minimal subprocess.CompletedProcess stand-in (mirrors test_port02)."""

    def __init__(
        self,
        returncode: int = 0,
        stdout: str = "committed (tighten, free)",
        stderr: str = "",
    ):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _run_commit(sudo_rc: int, *, pkill_raises: bool = False):
    """Run backend.commit() with subprocess.run mocked to branch on argv[0].

    Returns (result_dict, list_of_pkill_argvs). The "sudo" call returns a
    _FakeProc with returncode=sudo_rc; the "pkill" call is recorded (and raises
    OSError first when pkill_raises).
    """
    pkill_calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        head = argv[0]
        if head == "sudo":
            # The commit call now authenticates via a GUI askpass dialog (sudo -A +
            # SUDO_ASKPASS), so stderr IS captured (no TTY prompt to preserve). The
            # detailed askpass contract is asserted in test_commit_uses_gui_askpass.
            return _FakeProc(returncode=sudo_rc)
        if head == "pkill":
            pkill_calls.append(list(argv))
            if pkill_raises:
                raise OSError("pkill absent / no waybar running")
            return _FakeProc(returncode=0, stdout="")
        raise AssertionError(f"unexpected subprocess.run argv[0]={head!r}")

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        result = backend.commit("timezone: Europe/Amsterdam\n")

    return result, pkill_calls


# --- Test A: success -> signal fires exactly once ----------------------------


def test_success_fires_pkill_signal_once():
    """returncode 0 -> exactly one `pkill -RTMIN+11 waybar` call."""
    result, pkill_calls = _run_commit(sudo_rc=0)

    assert result["returncode"] == 0
    assert len(pkill_calls) == 1, (
        f"expected exactly one pkill call on success, got {pkill_calls!r}"
    )
    argv = pkill_calls[0]
    assert argv[0] == "pkill", f"signal argv[0] must be 'pkill', got {argv!r}"
    assert "-RTMIN+11" in argv, f"signal must use -RTMIN+11, got {argv!r}"
    assert "waybar" in argv, f"signal must target waybar, got {argv!r}"


# --- Test B: failure -> NO signal, real result returned ----------------------


def test_failure_does_not_fire_signal():
    """A non-zero commit returncode must NOT fire the refresh signal (T-12-02)."""
    result, pkill_calls = _run_commit(sudo_rc=1)

    assert pkill_calls == [], (
        f"a refused/failed commit must not flip the bar, got {pkill_calls!r}"
    )
    assert result["returncode"] == 1, (
        f"commit() must return the real returncode, got {result!r}"
    )


# --- Test C: raising pkill is swallowed (non-perturbing) ----------------------


def test_raising_pkill_is_non_perturbing():
    """A pkill that raises must not propagate or change the commit result (T-12-03)."""
    # sudo succeeds (rc 0) but the pkill subprocess raises OSError.
    result, pkill_calls = _run_commit(sudo_rc=0, pkill_raises=True)

    # It was attempted...
    assert len(pkill_calls) == 1, "the signal should still be attempted on success"
    # ...but the exception was swallowed and the real result returned unchanged.
    assert result["returncode"] == 0, (
        f"a raising pkill must leave the commit result unchanged, got {result!r}"
    )
    assert result["stdout"] == "committed (tighten, free)"


# --- Test D: result dict shape (signal adds no keys; askpass adds stderr) ------


def test_result_dict_shape():
    """The returned dict is {returncode, stdout, stderr} — the signal adds no keys.

    ``stderr`` is present because the GUI-askpass commit captures it (there is no
    TTY prompt to leave it attached to anymore).
    """
    result, _pkill_calls = _run_commit(sudo_rc=0)

    assert set(result.keys()) == {"returncode", "stdout", "stderr"}, (
        f"unexpected commit result keys, got {sorted(result)!r}"
    )
    # stdout is stripped (mirrors the existing commit contract).
    assert result["stdout"] == "committed (tighten, free)"


# --- Test E: GUI askpass contract (regression: commit-freeze-launcher-sudo) ----


def test_commit_uses_gui_askpass_not_tty():
    """commit() must authenticate via `sudo -A` + an executable SUDO_ASKPASS helper.

    Regression for the walker-launched-float freeze: the inline-terminal sudo prompt
    (App.suspend() + TTY) hangs in a Wayland float. The fix routes the password through
    a GUI askpass dialog, so the sudo call must pass `-A`, capture stderr, and point
    SUDO_ASKPASS at an existing executable — while keeping the sudoers Cmnd shape.
    """
    import os
    import subprocess as sp

    seen: dict = {}

    def fake_run(argv, **kwargs):
        if argv[0] == "sudo":
            seen["argv"] = list(argv)
            seen["kwargs"] = kwargs
            ap = kwargs.get("env", {}).get("SUDO_ASKPASS")
            seen["askpass"] = ap
            # Must exist + be executable AT CALL TIME (cleaned up in commit's finally).
            assert ap and os.path.exists(ap), f"SUDO_ASKPASS must be a real file, got {ap!r}"
            assert os.access(ap, os.X_OK), "SUDO_ASKPASS helper must be executable"
            return _FakeProc(returncode=0)
        if argv[0] == "pkill":
            return _FakeProc(returncode=0, stdout="")
        raise AssertionError(f"unexpected argv[0]={argv[0]!r}")

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        backend.commit("timezone: Europe/Amsterdam\n")

    argv = seen["argv"]
    assert argv[0] == "sudo" and argv[1] == "-A", f"must be `sudo -A …`, got {argv!r}"
    # sudoers Cmnd shape preserved after the -A option.
    assert argv[2] == "/usr/bin/python3", f"argv after -A must be python3, got {argv!r}"
    assert "commit" in argv and "--from" in argv, f"commit argv shape lost: {argv!r}"
    assert seen["kwargs"].get("stderr") is sp.PIPE, "commit must capture stderr now"
    # The helper is cleaned up after commit returns (no leaked temp files).
    assert not os.path.exists(seen["askpass"]), "askpass helper must be removed after commit"
