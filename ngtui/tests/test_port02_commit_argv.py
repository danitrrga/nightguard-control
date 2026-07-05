"""GAP-02 (PORT-02/PORT-03): commit() uses the exact sudoers argv with no shell.

Requirement: "backend.commit() shells exactly ['sudo','/usr/bin/python3',
<abs ctl.py>,'commit','--from',tmp] and maps exit/stdout to a result"
(PORT-02 / T-10-03 / 10-01-PLAN).

This test monkeypatches subprocess.run to capture the exact argv the commit()
function builds and verifies:
  1. argv[0] == "sudo"
  2. argv[1] == "-A"  (read the password from the GUI SUDO_ASKPASS dialog, not the TTY)
  3. argv[2] == "/usr/bin/python3"
  4. argv[3] is the absolute path to nightguard_ctl.py (== backend.CTL_SCRIPT)
  5. argv[4] == "commit"
  6. argv[5] == "--from"
  7. argv[6] is a real temp-file path (absolute, ends .yaml)
  8. shell=False (not shell=True — the sudoers alias requires an exact match)
  9. stdout AND stderr are PIPE (the GUI dialog carries the prompt, so the CLI's
     REFUSED line is captured for in-widget display — the old TTY-inline design,
     which left stderr uncaptured, hung in a walker-launched Wayland float)
 10. The temp file is cleaned up after the call (mkstemp 0600, then unlink)

The `-A` is a sudo *option*; it does not change the matched command, so the sudoers
Cmnd_Alias (`/usr/bin/python3 <ctl> commit *`) still matches.

These properties cannot be verified by reading the source alone; they require
actually running the function with a captured subprocess.run.
"""
from __future__ import annotations

import os
import pathlib
from unittest.mock import MagicMock, patch

import pytest

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


def _capture_commit(proposed_text: str = "timezone: Europe/Amsterdam\n") -> tuple[dict, "_Call"]:
    """Run backend.commit() with a monkeypatched subprocess.run and return
    (result_dict, mock_call_args_dict)."""
    captured: list[dict] = []

    def fake_run(argv, *, stdout, text, **kwargs):
        captured.append({"argv": argv, "stdout": stdout, "text": text, "kwargs": kwargs})
        return _FakeProc()

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        result = backend.commit(proposed_text)

    return result, captured[0]


# --- Test 1: argv shape is the exact sudoers Cmnd_Alias ----------------------


def test_commit_argv_matches_sudoers_shape():
    """commit() builds ['sudo', '-A', '/usr/bin/python3', CTL_SCRIPT, 'commit', '--from', <tmp>]."""
    result, call = _capture_commit()

    argv = call["argv"]
    assert len(argv) == 7, f"Expected 7 argv items, got {len(argv)}: {argv}"
    assert argv[0] == "sudo", f"argv[0] must be 'sudo', got {argv[0]!r}"
    assert argv[1] == "-A", f"argv[1] must be '-A' (GUI askpass), got {argv[1]!r}"
    assert argv[2] == "/usr/bin/python3", f"argv[2] must be '/usr/bin/python3', got {argv[2]!r}"
    assert argv[3] == backend.CTL_SCRIPT, (
        f"argv[3] must be the validated CTL_SCRIPT ({backend.CTL_SCRIPT!r}), "
        f"got {argv[3]!r}"
    )
    assert argv[4] == "commit", f"argv[4] must be 'commit', got {argv[4]!r}"
    assert argv[5] == "--from", f"argv[5] must be '--from', got {argv[5]!r}"
    # argv[6] is the temp file path — must be absolute and end with .yaml
    tmp_path = argv[6]
    assert pathlib.Path(tmp_path).is_absolute(), (
        f"argv[6] (temp file) must be absolute, got {tmp_path!r}"
    )
    assert tmp_path.endswith(".yaml"), (
        f"argv[6] (temp file) must end with .yaml, got {tmp_path!r}"
    )


# --- Test 2: shell=False (not shell=True) -------------------------------------


def test_commit_uses_no_shell():
    """commit() must NOT use shell=True — sudoers requires exact argv match."""
    _result, call = _capture_commit()

    # shell is not passed as a kwarg (defaulting to False) — that is correct.
    # If it were passed as shell=True that would be a violation.
    shell = call["kwargs"].get("shell", False)
    assert shell is False, (
        f"commit() must not pass shell=True — sudoers Cmnd_Alias requires exact argv. "
        f"Got shell={shell!r}"
    )


# --- Test 3: stderr IS captured (GUI askpass carries the prompt) -------------


def test_commit_captures_stderr():
    """stderr must be captured now that authentication is a GUI askpass dialog.

    The old design left stderr on the TTY so the inline sudo prompt was visible —
    but that inline prompt hangs in a walker-launched Wayland float
    (commit-freeze-launcher-sudo). With `sudo -A` the dialog carries the prompt, so
    stderr is free to be captured and the CLI's REFUSED line surfaced in-widget.
    """
    import subprocess as sp

    _result, call = _capture_commit()

    stderr = call["kwargs"].get("stderr", None)
    assert stderr is sp.PIPE, (
        "commit() must capture stderr now (GUI askpass carries the prompt). "
        f"Got stderr={stderr!r}"
    )


# --- Test 4: CTL_SCRIPT is absolute and under the validated STACK_DIR --------


def test_commit_ctl_script_is_absolute_and_under_stack_dir():
    """The script path handed to sudo is absolute and lives under the pinned STACK_DIR.

    This ensures the env cannot redirect the sudo call to a different script by
    manipulating NIGHTGUARD_STACK_DIR after module load (CR-02).
    """
    ctl = pathlib.Path(backend.CTL_SCRIPT)
    assert ctl.is_absolute(), f"CTL_SCRIPT must be absolute, got {backend.CTL_SCRIPT!r}"
    assert backend.CTL_SCRIPT.startswith(backend.STACK_DIR), (
        f"CTL_SCRIPT ({backend.CTL_SCRIPT!r}) must be under STACK_DIR "
        f"({backend.STACK_DIR!r}) — env redirect attack vector"
    )
    assert ctl.name == "nightguard_ctl.py", (
        f"CTL_SCRIPT filename must be 'nightguard_ctl.py', got {ctl.name!r}"
    )


# --- Test 5: temp file is cleaned up after call (T-10-04) --------------------


def test_commit_temp_file_is_cleaned_up_after_call():
    """The mkstemp temp file must be unlinked after commit() returns (T-10-04).

    Leaving the proposed-config temp file on disk after commit is an information
    disclosure and a potential symlink-race target for the next call.
    """
    collected_tmp: list[str] = []

    def fake_run(argv, *, stdout, text, **kwargs):
        # Record the temp path before it might get deleted (argv[6] after `sudo -A`).
        collected_tmp.append(argv[6])
        return _FakeProc()

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        backend.commit("timezone: Europe/Amsterdam\n")

    assert collected_tmp, "subprocess.run was not called — commit() did not run"
    tmp = collected_tmp[0]
    assert not os.path.exists(tmp), (
        f"Temp file {tmp!r} still exists after commit() returned — "
        "it must be unlinked in the finally block (T-10-04)"
    )


# --- Test 6: result dict maps returncode and stdout correctly -----------------


def test_commit_maps_returncode_and_stdout_to_result():
    """commit() returns {returncode, stdout} from the subprocess result."""

    def fake_run(argv, *, stdout, text, **kwargs):
        return _FakeProc(returncode=0, stdout="committed (tighten, free): config_hmac=abc\n")

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        result = backend.commit("timezone: Europe/Amsterdam\n")

    assert result["returncode"] == 0
    # stdout is stripped
    assert result["stdout"] == "committed (tighten, free): config_hmac=abc"
