"""BAR-04 / D-11: commit() fires a success-only, non-perturbing Waybar refresh.

Requirement: "backend.commit() fires `pkill -RTMIN+11 waybar` exactly once when the
commit succeeded (rc 0), NEVER on failure, and a raising pkill subprocess is swallowed
so commit() still returns the real result" (BAR-04 / D-11 / 12-02-PLAN).

commit() now takes the user's password (collected by a masked in-TUI field) and pipes
it to `sudo -S` on stdin — no TTY prompt, no App.suspend(), no GUI askpass, no second
terminal (all of which failed in the walker-launched Wayland float; debug:
commit-freeze-launcher-sudo). The mock branches on argv[0]:
  - "sudo"  -> the commit call (returns a _FakeProc with the desired returncode)
  - "pkill" -> the refresh signal (recorded, or made to raise)
"""
from __future__ import annotations

from unittest.mock import patch

from ngtui import backend


class _FakeProc:
    """Minimal subprocess.CompletedProcess stand-in."""

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

    Returns (result_dict, list_of_pkill_argvs). The "sudo" call returns a _FakeProc with
    returncode=sudo_rc; the "pkill" call is recorded (and raises OSError when requested).
    """
    pkill_calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        head = argv[0]
        if head == "sudo":
            return _FakeProc(returncode=sudo_rc)
        if head == "pkill":
            pkill_calls.append(list(argv))
            if pkill_raises:
                raise OSError("pkill absent / no waybar running")
            return _FakeProc(returncode=0, stdout="")
        raise AssertionError(f"unexpected subprocess.run argv[0]={head!r}")

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        result = backend.commit("timezone: Europe/Amsterdam\n", "hunter2")

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
    result, pkill_calls = _run_commit(sudo_rc=0, pkill_raises=True)

    assert len(pkill_calls) == 1, "the signal should still be attempted on success"
    assert result["returncode"] == 0, (
        f"a raising pkill must leave the commit result unchanged, got {result!r}"
    )
    assert result["stdout"] == "committed (tighten, free)"


# --- Test D: result dict shape -----------------------------------------------


def test_result_dict_shape():
    """The returned dict is {returncode, stdout, stderr}; the signal adds no keys."""
    result, _pkill_calls = _run_commit(sudo_rc=0)

    assert set(result.keys()) == {"returncode", "stdout", "stderr"}, (
        f"unexpected commit result keys, got {sorted(result)!r}"
    )
    assert result["stdout"] == "committed (tighten, free)"


# --- Test E: password is piped to `sudo -S` (regression) ---------------------


def test_commit_pipes_password_to_sudo_S_on_stdin():
    """Regression (commit-freeze-launcher-sudo): password goes to `sudo -S` via stdin.

    No TTY prompt / App.suspend() / GUI askpass / second terminal. `-S` reads from stdin,
    `-k` forces real re-auth (friction), `-p ''` silences sudo's own prompt.
    """
    seen: dict = {}

    def fake_run(argv, **kwargs):
        if argv[0] == "pkill":
            return _FakeProc(0)
        seen["argv"] = list(argv)
        seen["kwargs"] = kwargs
        return _FakeProc(0)

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        backend.commit("timezone: Europe/Amsterdam\n", "s3cret")

    argv = seen["argv"]
    assert argv[0] == "sudo", f"argv[0] must be sudo, got {argv!r}"
    assert "-S" in argv, "sudo must read the password from stdin (-S)"
    assert "-k" in argv, "sudo must force re-auth every commit (-k) — the friction"
    # -p '' silences sudo's own prompt (the TUI shows the password field).
    i = argv.index("-p")
    assert argv[i + 1] == "", "sudo prompt must be silenced with -p ''"
    # Exact sudoers Cmnd shape follows the options.
    assert "/usr/bin/python3" in argv and backend.CTL_SCRIPT in argv
    assert "commit" in argv and "--from" in argv
    # The password is fed on stdin, never on the command line.
    assert seen["kwargs"].get("input") == "s3cret\n", "password must be piped via stdin"
    assert "s3cret" not in " ".join(argv), "password must never appear in argv"
    import subprocess as sp

    assert seen["kwargs"].get("stdout") is sp.PIPE
    assert seen["kwargs"].get("stderr") is sp.PIPE
