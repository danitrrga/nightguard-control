"""GAP-02 (PORT-02/PORT-03): commit() runs the exact sudoers command, no injection.

Requirement (evolved): backend.commit(proposed_text, password) runs
``sudo -S -k -p '' /usr/bin/python3 <abs ctl.py> commit --from <tmp>``, feeding the
password on stdin, and maps exit/stdout/stderr to a result. Originally this used an
inline-TTY sudo prompt (App.suspend()), which broke in the walker-launched Wayland
float; a sudo -A GUI askpass hung; a dedicated terminal worked but opened a second
window. The reliable + in-window design collects the password with a masked field and
pipes it to ``sudo -S`` (debug: commit-freeze-launcher-sudo).

This test monkeypatches subprocess.run to capture the exact argv and verifies:
  1. argv is ``['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', CTL, 'commit', '--from', <tmp>]``
  2. the temp .yaml path is absolute (config is a FILE, never inline content)
  3. shell=False (the argv is exact — sudoers Cmnd_Alias must match)
  4. the password is on stdin (``input=``), never in argv
  5. stdout AND stderr are PIPE (the real REFUSED/auth line is captured)
  6. CTL_SCRIPT is absolute and under the validated STACK_DIR (CR-02)
  7. the temp file is cleaned up after the call (T-10-04)
"""
from __future__ import annotations

import os
import pathlib
from unittest.mock import patch

from ngtui import backend


class _FakeProc:
    """Minimal subprocess.CompletedProcess stand-in."""

    def __init__(self, returncode: int = 0, stdout: str = "committed (tighten, free)", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _capture_commit(proposed_text: str = "timezone: Europe/Amsterdam\n", password: str = "pw"):
    """Run backend.commit() with subprocess.run mocked; return (result, captured_call)."""
    captured: list[dict] = []

    def fake_run(argv, **kwargs):
        if argv and argv[0] == "pkill":
            return _FakeProc(0)
        captured.append({"argv": list(argv), "kwargs": kwargs})
        return _FakeProc()

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        result = backend.commit(proposed_text, password)

    return result, captured[0]


# --- Test 1: argv is the exact sudoers Cmnd shape (with -S -k -p '') ----------


def test_commit_argv_matches_sudoers_shape():
    """commit() builds ['sudo','-S','-k','-p','','/usr/bin/python3',CTL,'commit','--from',<tmp>]."""
    _result, call = _capture_commit()

    argv = call["argv"]
    assert argv[:5] == ["sudo", "-S", "-k", "-p", ""], (
        f"sudo option prefix must be `-S -k -p ''`, got {argv[:5]!r}"
    )
    assert argv[5] == "/usr/bin/python3", f"argv[5] must be '/usr/bin/python3', got {argv[5]!r}"
    assert argv[6] == backend.CTL_SCRIPT, (
        f"argv[6] must be the validated CTL_SCRIPT ({backend.CTL_SCRIPT!r}), got {argv[6]!r}"
    )
    assert argv[7] == "commit", f"argv[7] must be 'commit', got {argv[7]!r}"
    assert argv[8] == "--from", f"argv[8] must be '--from', got {argv[8]!r}"
    tmp_path = argv[9]
    assert pathlib.Path(tmp_path).is_absolute(), f"argv[9] (temp file) must be absolute, got {tmp_path!r}"
    assert tmp_path.endswith(".yaml"), f"argv[9] (temp file) must end with .yaml, got {tmp_path!r}"


# --- Test 2: shell=False -----------------------------------------------------


def test_commit_uses_no_shell():
    """commit() must NOT use shell=True — sudoers requires exact argv."""
    _result, call = _capture_commit()
    assert call["kwargs"].get("shell", False) is False, (
        f"commit() must not pass shell=True, got shell={call['kwargs'].get('shell')!r}"
    )


# --- Test 3: password on stdin, never in argv --------------------------------


def test_commit_password_is_on_stdin_not_argv():
    """The password must be piped via stdin (input=), never placed on the command line."""
    _result, call = _capture_commit(password="corr3ct-horse")
    assert call["kwargs"].get("input") == "corr3ct-horse\n", (
        f"password must be fed on stdin, got input={call['kwargs'].get('input')!r}"
    )
    assert "corr3ct-horse" not in " ".join(call["argv"]), (
        "password must NEVER appear in argv (process listing leak)"
    )


# --- Test 4: stdout AND stderr are captured ----------------------------------


def test_commit_captures_stdout_and_stderr():
    """Both streams are captured (the real REFUSED/auth reason surfaces in-widget)."""
    import subprocess as sp

    _result, call = _capture_commit()
    assert call["kwargs"].get("stdout") is sp.PIPE, "stdout must be captured"
    assert call["kwargs"].get("stderr") is sp.PIPE, "stderr must be captured"


# --- Test 5: CTL_SCRIPT is absolute and under the validated STACK_DIR --------


def test_commit_ctl_script_is_absolute_and_under_stack_dir():
    """The script path handed to sudo is absolute and under the pinned STACK_DIR (CR-02)."""
    ctl = pathlib.Path(backend.CTL_SCRIPT)
    assert ctl.is_absolute(), f"CTL_SCRIPT must be absolute, got {backend.CTL_SCRIPT!r}"
    assert backend.CTL_SCRIPT.startswith(backend.STACK_DIR), (
        f"CTL_SCRIPT ({backend.CTL_SCRIPT!r}) must be under STACK_DIR ({backend.STACK_DIR!r})"
    )
    assert ctl.name == "nightguard_ctl.py", (
        f"CTL_SCRIPT filename must be 'nightguard_ctl.py', got {ctl.name!r}"
    )


# --- Test 6: temp file is cleaned up after call (T-10-04) --------------------


def test_commit_temp_file_is_cleaned_up_after_call():
    """The mkstemp temp file must be unlinked after commit() returns (T-10-04)."""
    collected_tmp: list[str] = []

    def fake_run(argv, **kwargs):
        if argv and argv[0] == "pkill":
            return _FakeProc(0)
        collected_tmp.append(argv[9])  # the --from <tmp> path
        return _FakeProc()

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        backend.commit("timezone: Europe/Amsterdam\n", "pw")

    assert collected_tmp, "subprocess.run was not called — commit() did not run"
    tmp = collected_tmp[0]
    assert not os.path.exists(tmp), (
        f"Temp file {tmp!r} still exists after commit() returned (T-10-04)"
    )


# --- Test 7: result maps returncode + stdout ---------------------------------


def test_commit_maps_returncode_and_stdout_to_result():
    """commit() returns {returncode, stdout, stderr} from the subprocess result."""

    def fake_run(argv, **kwargs):
        if argv and argv[0] == "pkill":
            return _FakeProc(0)
        return _FakeProc(returncode=0, stdout="committed (tighten, free): config_hmac=abc\n")

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        result = backend.commit("timezone: Europe/Amsterdam\n", "pw")

    assert result["returncode"] == 0
    assert result["stdout"] == "committed (tighten, free): config_hmac=abc"
