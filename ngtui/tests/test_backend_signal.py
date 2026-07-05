"""BAR-04 / D-11: commit() fires a success-only, non-perturbing Waybar refresh.

Requirement: "backend.commit() fires `pkill -RTMIN+11 waybar` exactly once when the
commit succeeded (rc 0), NEVER on failure, and a raising pkill subprocess is swallowed
so commit() still returns the real result" (BAR-04 / D-11 / 12-02-PLAN).

commit() authorises `sudo` on a PTY (``_run_sudo_pty``) so PAM's interactive auth works
in-window — on this box a fingerprint touch (pam_fprintd first + sufficient). A piped
password to `sudo -S` hangs on that stack (debug: commit-freeze-launcher-sudo). Tests
mock the PTY seam (``_run_sudo_pty``) for the auth result and ``subprocess.run`` for the
pkill signal.
"""
from __future__ import annotations

from unittest.mock import patch

from ngtui import backend


class _FakeProc:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode


def _run_commit(sudo_rc: int, *, pkill_raises: bool = False, output: str = "committed (tighten, free)"):
    """Run backend.commit() with the PTY auth + pkill mocked.

    Returns (result_dict, list_of_pkill_argvs). ``_run_sudo_pty`` returns (sudo_rc, output);
    the "pkill" subprocess.run is recorded (and raises OSError when requested).
    """
    pkill_calls: list[list[str]] = []

    def fake_pty(argv, cancel_event=None, status_cb=None):
        return sudo_rc, output

    def fake_run(argv, **kwargs):
        if argv and argv[0] == "pkill":
            pkill_calls.append(list(argv))
            if pkill_raises:
                raise OSError("pkill absent / no waybar running")
            return _FakeProc(0)
        raise AssertionError(f"unexpected subprocess.run argv={argv!r}")

    with patch("ngtui.backend._run_sudo_pty", side_effect=fake_pty), patch(
        "ngtui.backend.subprocess.run", side_effect=fake_run
    ):
        result = backend.commit("timezone: Europe/Amsterdam\n")

    return result, pkill_calls


# --- Test A: success -> signal fires exactly once ----------------------------


def test_success_fires_pkill_signal_once():
    result, pkill_calls = _run_commit(sudo_rc=0)
    assert result["returncode"] == 0
    assert len(pkill_calls) == 1, f"expected one pkill on success, got {pkill_calls!r}"
    argv = pkill_calls[0]
    assert argv[0] == "pkill" and "-RTMIN+11" in argv and "waybar" in argv, argv


# --- Test B: failure -> NO signal, real result returned ----------------------


def test_failure_does_not_fire_signal():
    result, pkill_calls = _run_commit(sudo_rc=1, output="")
    assert pkill_calls == [], f"a failed commit must not flip the bar, got {pkill_calls!r}"
    assert result["returncode"] == 1


# --- Test C: raising pkill is swallowed (non-perturbing) ----------------------


def test_raising_pkill_is_non_perturbing():
    result, pkill_calls = _run_commit(sudo_rc=0, pkill_raises=True)
    assert len(pkill_calls) == 1, "the signal should still be attempted on success"
    assert result["returncode"] == 0
    assert result["stdout"] == "committed (tighten, free)"


# --- Test D: result dict shape -----------------------------------------------


def test_result_dict_shape():
    result, _pkill = _run_commit(sudo_rc=0)
    assert set(result.keys()) == {"returncode", "stdout", "stderr"}, sorted(result)
    assert result["stdout"] == "committed (tighten, free)"


# --- Test E: commit authorises via sudo -k on a PTY (regression) --------------


def test_commit_authorises_via_sudo_on_a_pty():
    """Regression (commit-freeze-launcher-sudo): auth runs `sudo -k …` on a PTY.

    No `-S` password piping (which hangs on the fingerprint-first PAM stack). The PTY lets
    PAM do the fingerprint touch in-window.
    """
    seen: dict = {}

    def fake_pty(argv, cancel_event=None, status_cb=None):
        seen["argv"] = list(argv)
        return 0, "committed (tighten, free)"

    with patch("ngtui.backend._run_sudo_pty", side_effect=fake_pty), patch(
        "ngtui.backend.subprocess.run", side_effect=lambda *a, **k: _FakeProc(0)
    ):
        backend.commit("timezone: Europe/Amsterdam\n")

    argv = seen["argv"]
    assert argv[0] == "sudo", f"auth must run sudo, got {argv!r}"
    assert "-k" in argv, "sudo must force re-auth every commit (-k) — the friction"
    assert "-S" not in argv, "must NOT pipe a password (-S hangs on fingerprint-first PAM)"
    assert "/usr/bin/python3" in argv and backend.CTL_SCRIPT in argv
    assert "commit" in argv and "--from" in argv
