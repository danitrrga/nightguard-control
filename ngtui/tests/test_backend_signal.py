"""BAR-04 / D-11: commit() fires a success-only, non-perturbing Waybar refresh.

Requirement: "backend.commit() fires `pkill -RTMIN+11 waybar` exactly once when
the commit succeeded (rc 0), NEVER on failure, and a raising pkill subprocess is
swallowed so commit() still returns the real result" (BAR-04 / D-11 / 12-02-PLAN).

commit() now runs the real `sudo … commit` inside a spawned terminal (native TTY
password prompt — the inline prompt and a GUI askpass both hung in the walker-
launched Wayland float; debug: commit-freeze-launcher-sudo). The terminal writes
its exit code to a temp .rc file, which commit() reads back. So the mock:
  - for the terminal launcher call: simulates the terminal by writing the desired
    rc (and some output) to the .rc/.out paths embedded in the inner command;
  - for "pkill": records the refresh signal (or makes it raise).
"""
from __future__ import annotations

import re
from unittest.mock import patch

from ngtui import backend


class _FakeProc:
    """Minimal subprocess.CompletedProcess stand-in."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _run_commit(sim_rc: int, *, pkill_raises: bool = False):
    """Run backend.commit() with subprocess.run mocked.

    The terminal-launcher call is simulated by writing `sim_rc` (and a fake committed
    line) to the .rc/.out temp files named in the inner shell command. Returns
    (result_dict, list_of_pkill_argvs).
    """
    pkill_calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        head = argv[0]
        if head == "pkill":
            pkill_calls.append(list(argv))
            if pkill_raises:
                raise OSError("pkill absent / no waybar running")
            return _FakeProc(returncode=0)
        # Otherwise this is the terminal launcher: `[launcher, "-e", "sh", "-c", inner]`.
        inner = argv[-1]
        rc_match = re.search(r"> (\S+\.rc)", inner)
        assert rc_match, f"inner must redirect the exit code to a .rc file: {inner!r}"
        with open(rc_match.group(1), "w", encoding="utf-8") as f:
            f.write(str(sim_rc))
        out_match = re.search(r"> (\S+\.out)", inner)
        if out_match:
            with open(out_match.group(1), "w", encoding="utf-8") as f:
                f.write("committed (tighten, free)")
        return _FakeProc(returncode=0)  # the terminal's own exit code (commit ignores it)

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        result = backend.commit("timezone: Europe/Amsterdam\n")

    return result, pkill_calls


# --- Test A: success -> signal fires exactly once ----------------------------


def test_success_fires_pkill_signal_once():
    """rc 0 (from the terminal's .rc file) -> exactly one `pkill -RTMIN+11 waybar`."""
    result, pkill_calls = _run_commit(sim_rc=0)

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
    """A non-zero commit rc must NOT fire the refresh signal (T-12-02)."""
    result, pkill_calls = _run_commit(sim_rc=1)

    assert pkill_calls == [], (
        f"a refused/failed commit must not flip the bar, got {pkill_calls!r}"
    )
    assert result["returncode"] == 1, (
        f"commit() must return the real returncode, got {result!r}"
    )


# --- Test C: raising pkill is swallowed (non-perturbing) ----------------------


def test_raising_pkill_is_non_perturbing():
    """A pkill that raises must not propagate or change the commit result (T-12-03)."""
    result, pkill_calls = _run_commit(sim_rc=0, pkill_raises=True)

    assert len(pkill_calls) == 1, "the signal should still be attempted on success"
    assert result["returncode"] == 0, (
        f"a raising pkill must leave the commit result unchanged, got {result!r}"
    )
    assert result["stdout"] == "committed (tighten, free)"


# --- Test D: result dict shape -----------------------------------------------


def test_result_dict_shape():
    """The returned dict is {returncode, stdout, stderr}; the signal adds no keys."""
    result, _pkill_calls = _run_commit(sim_rc=0)

    assert set(result.keys()) == {"returncode", "stdout", "stderr"}, (
        f"unexpected commit result keys, got {sorted(result)!r}"
    )
    assert result["stdout"] == "committed (tighten, free)"


# --- Test E: commit runs sudo in a real terminal (regression) ----------------


def test_commit_runs_sudo_in_a_spawned_terminal():
    """Regression (commit-freeze-launcher-sudo): the sudo prompt must have a real TTY.

    The inline prompt needed App.suspend() (broken in the Wayland float) and a sudo -A
    GUI askpass hung on walker. The reliable design runs the exact sudo command inside a
    spawned terminal via `-e sh -c <inner>`, capturing the exit code from a .rc file.
    """
    seen: dict = {}

    def fake_run(argv, **kwargs):
        if argv[0] == "pkill":
            return _FakeProc(0)
        seen["argv"] = list(argv)
        inner = argv[-1]
        seen["inner"] = inner
        rc_match = re.search(r"> (\S+\.rc)", inner)
        with open(rc_match.group(1), "w", encoding="utf-8") as f:
            f.write("0")
        return _FakeProc(0)

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        backend.commit("timezone: Europe/Amsterdam\n")

    argv = seen["argv"]
    assert argv[1:4] == ["-e", "sh", "-c"], f"must spawn a terminal via -e sh -c, got {argv!r}"
    inner = seen["inner"]
    # The exact sudoers Cmnd shape runs inside the terminal.
    assert "sudo /usr/bin/python3" in inner, f"sudo command missing/altered: {inner!r}"
    assert backend.CTL_SCRIPT in inner, "the validated CTL_SCRIPT must be the sudo target"
    assert "commit --from" in inner, f"commit --from <tmp> shape lost: {inner!r}"
    # It captures the exit code from a .rc file rather than the terminal's own rc.
    assert re.search(r"> \S+\.rc", inner), "commit must capture the sudo exit code to a .rc file"
