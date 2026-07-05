"""GAP-02 (PORT-02/PORT-03): commit() runs the exact sudoers command, on a PTY, no injection.

Requirement (evolved): backend.commit(proposed_text) authorises
``sudo -k /usr/bin/python3 <abs ctl.py> commit --from <tmp>`` on a pseudo-terminal so PAM's
interactive auth works in-window (fingerprint touch — pam_fprintd first + sufficient), and
maps exit/output to a result. Inline-TTY (App.suspend()), GUI askpass, a dedicated terminal,
and piping a password to ``sudo -S`` all failed or were clumsy in the walker-launched
Wayland float (debug: commit-freeze-launcher-sudo).

This test mocks the PTY seam (``_run_sudo_pty``) to capture the exact argv and verifies:
  1. argv == ['sudo', '-k', '/usr/bin/python3', CTL, 'commit', '--from', <tmp>]
  2. the temp .yaml path is absolute (config is a FILE, never inline content)
  3. no password anywhere in argv (no -S; nothing to leak)
  4. CTL_SCRIPT is absolute and under the validated STACK_DIR (CR-02)
  5. the (returncode, output) from the PTY is mapped into the result
  6. the temp file is cleaned up after the call (T-10-04)
"""
from __future__ import annotations

import os
import pathlib
from unittest.mock import patch

from ngtui import backend


class _FakeProc:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode


def _capture_commit(proposed_text: str = "timezone: Europe/Amsterdam\n", *, rc: int = 0, output: str = "committed (tighten, free)"):
    """Run backend.commit() with the PTY + pkill mocked; return (result, captured_argv)."""
    captured: dict = {}

    def fake_pty(argv, cancel_event=None, status_cb=None):
        captured["argv"] = list(argv)
        return rc, output

    with patch("ngtui.backend._run_sudo_pty", side_effect=fake_pty), patch(
        "ngtui.backend.subprocess.run", side_effect=lambda *a, **k: _FakeProc(0)
    ):
        result = backend.commit(proposed_text)

    return result, captured["argv"]


# --- Test 1: argv is the exact sudoers Cmnd shape (sudo -k …) -----------------


def test_commit_argv_matches_sudoers_shape():
    _result, argv = _capture_commit()
    assert argv[0] == "sudo", f"argv[0] must be 'sudo', got {argv[0]!r}"
    assert argv[1] == "-k", f"argv[1] must be '-k' (force re-auth), got {argv[1]!r}"
    assert argv[2] == "/usr/bin/python3", f"argv[2] must be '/usr/bin/python3', got {argv[2]!r}"
    assert argv[3] == backend.CTL_SCRIPT, (
        f"argv[3] must be the validated CTL_SCRIPT ({backend.CTL_SCRIPT!r}), got {argv[3]!r}"
    )
    assert argv[4] == "commit", f"argv[4] must be 'commit', got {argv[4]!r}"
    assert argv[5] == "--from", f"argv[5] must be '--from', got {argv[5]!r}"
    tmp_path = argv[6]
    assert pathlib.Path(tmp_path).is_absolute(), f"argv[6] (temp file) must be absolute: {tmp_path!r}"
    assert tmp_path.endswith(".yaml"), f"argv[6] (temp file) must end with .yaml: {tmp_path!r}"


# --- Test 2: no password / no -S in argv (nothing to leak) -------------------


def test_commit_has_no_password_and_no_dash_S():
    _result, argv = _capture_commit()
    assert "-S" not in argv, "must not use sudo -S (it hangs on the fingerprint-first PAM stack)"
    # The whole argv is fixed tokens + paths — no free-form secret material.
    assert all(isinstance(a, str) for a in argv)


# --- Test 3: CTL_SCRIPT is absolute and under the validated STACK_DIR --------


def test_commit_ctl_script_is_absolute_and_under_stack_dir():
    ctl = pathlib.Path(backend.CTL_SCRIPT)
    assert ctl.is_absolute(), f"CTL_SCRIPT must be absolute, got {backend.CTL_SCRIPT!r}"
    assert backend.CTL_SCRIPT.startswith(backend.STACK_DIR), (
        f"CTL_SCRIPT ({backend.CTL_SCRIPT!r}) must be under STACK_DIR ({backend.STACK_DIR!r})"
    )
    assert ctl.name == "nightguard_ctl.py", f"filename must be 'nightguard_ctl.py', got {ctl.name!r}"


# --- Test 4: (rc, output) from the PTY maps into the result ------------------


def test_commit_maps_pty_result():
    result, _argv = _capture_commit(rc=0, output="committed (tighten, free): config_hmac=abc")
    assert result["returncode"] == 0
    assert result["stdout"] == "committed (tighten, free): config_hmac=abc"

    result2, _ = _capture_commit(rc=1, output="REFUSED (quota)")
    assert result2["returncode"] == 1


# --- Test 5: temp file is cleaned up after call (T-10-04) --------------------


def test_commit_temp_file_is_cleaned_up_after_call():
    seen: dict = {}

    def fake_pty(argv, cancel_event=None, status_cb=None):
        seen["tmp"] = argv[6]  # the --from <tmp> path
        return 0, "committed (tighten, free)"

    with patch("ngtui.backend._run_sudo_pty", side_effect=fake_pty), patch(
        "ngtui.backend.subprocess.run", side_effect=lambda *a, **k: _FakeProc(0)
    ):
        backend.commit("timezone: Europe/Amsterdam\n")

    assert "tmp" in seen, "_run_sudo_pty was not called — commit() did not run"
    assert not os.path.exists(seen["tmp"]), f"temp file {seen['tmp']!r} still exists after commit() (T-10-04)"


# --- Test 6: auth chatter is stripped from the surfaced result ---------------


def test_fingerprint_chatter_is_stripped_from_result():
    """The signer's real line is surfaced; fingerprint/sudo prompts are filtered out."""
    stdout, stderr = backend._split_commit_output(
        "Place your right index finger on the fingerprint reader\n"
        "Verify\n"
        "committed (loosen -1 token): config_hmac=abc · tokens 1/3 used\n",
        0,
    )
    assert stdout.startswith("committed (loosen -1 token)"), f"got {stdout!r}"
    assert "finger" not in stdout.lower()
    assert stderr == ""
