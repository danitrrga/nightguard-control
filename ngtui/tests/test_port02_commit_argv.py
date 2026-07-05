"""GAP-02 (PORT-02/PORT-03): commit() runs the exact sudoers command, no injection.

Requirement (evolved): backend.commit() runs
``sudo /usr/bin/python3 <abs ctl.py> commit --from <tmp>`` and maps exit/stdout to a
result. Originally this was a direct ``subprocess.run(['sudo', …])`` with an inline TTY
prompt; that hung in the walker-launched Wayland float (App.suspend()/TTY handoff broke),
and a ``sudo -A`` GUI askpass hung on walker (debug: commit-freeze-launcher-sudo).

The reliable design runs the SAME sudo command inside a freshly-spawned terminal
(``[launcher, '-e', 'sh', '-c', inner]``) so the password prompt has a genuine TTY. This
test monkeypatches subprocess.run to capture the spawn and verifies:
  1. argv is ``[<launcher>, '-e', 'sh', '-c', <inner>]`` (a real terminal, not headless)
  2. inner contains the exact ``sudo /usr/bin/python3 <CTL_SCRIPT> commit --from <tmp>``
  3. the temp .yaml path (config is a FILE, never inline content — no injection)
  4. shell=False on subprocess.run (the argv list is exact; sh is the terminal's child)
  5. the exit code is captured from a .rc file and mapped to the result
  6. all three temp files (.yaml/.rc/.out) are cleaned up after the call
"""
from __future__ import annotations

import os
import pathlib
import re
from unittest.mock import patch

from ngtui import backend


class _FakeProc:
    """Minimal subprocess.CompletedProcess stand-in."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _capture_commit(
    proposed_text: str = "timezone: Europe/Amsterdam\n", *, sim_rc: str = "0", sim_out: str = ""
):
    """Run backend.commit() with subprocess.run mocked; simulate the terminal writing
    the .rc/.out files. Returns (result_dict, captured_terminal_call_dict)."""
    captured: list[dict] = []

    def fake_run(argv, **kwargs):
        if argv and argv[0] == "pkill":
            return _FakeProc(0)
        inner = argv[-1]
        captured.append({"argv": argv, "inner": inner, "kwargs": kwargs})
        rc_match = re.search(r"> (\S+\.rc)", inner)
        if rc_match:
            with open(rc_match.group(1), "w", encoding="utf-8") as f:
                f.write(sim_rc)
        out_match = re.search(r"> (\S+\.out)", inner)
        if out_match and sim_out:
            with open(out_match.group(1), "w", encoding="utf-8") as f:
                f.write(sim_out)
        return _FakeProc(0)

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        result = backend.commit(proposed_text)

    return result, captured[0]


# --- Test 1: spawns a real terminal running the exact sudo command -----------


def test_commit_spawns_terminal_with_exact_sudo_command():
    """commit() runs `[launcher, -e, sh, -c, inner]` where inner is the sudoers Cmnd."""
    _result, call = _capture_commit()

    argv = call["argv"]
    assert argv[1:4] == ["-e", "sh", "-c"], (
        f"commit must spawn a terminal via `-e sh -c`, got {argv!r}"
    )
    inner = call["inner"]
    # The exact sudoers Cmnd shape (order preserved) runs inside the terminal.
    m = re.search(
        r"sudo /usr/bin/python3 (\S+) commit --from (\S+\.yaml)", inner
    )
    assert m, f"inner must contain the exact sudo commit command, got: {inner!r}"
    assert m.group(1) == backend.CTL_SCRIPT, (
        f"sudo target must be the validated CTL_SCRIPT ({backend.CTL_SCRIPT!r}), "
        f"got {m.group(1)!r}"
    )
    tmp_path = m.group(2)
    assert pathlib.Path(tmp_path).is_absolute(), f"temp file must be absolute: {tmp_path!r}"


# --- Test 2: shell=False (the sudo argv is exact; sh is the terminal's child) -


def test_commit_uses_no_shell_on_subprocess():
    """subprocess.run must NOT use shell=True — the launcher argv is an exact list."""
    _result, call = _capture_commit()
    assert call["kwargs"].get("shell", False) is False, (
        f"commit() must not pass shell=True. Got shell={call['kwargs'].get('shell')!r}"
    )


# --- Test 3: config content is a FILE, never inline (no injection) ------------


def test_commit_does_not_put_config_content_on_command_line():
    """The proposed config text must never appear in the shell command (injection guard)."""
    sentinel = "curfew:\n  start: '99:99'  # INJECT_SENTINEL_$(rm -rf)\n"
    _result, call = _capture_commit(sentinel)
    assert "INJECT_SENTINEL" not in call["inner"], (
        "config content must be passed via the temp FILE, never interpolated into the "
        f"shell command. Inner was: {call['inner']!r}"
    )


# --- Test 4: CTL_SCRIPT is absolute and under the validated STACK_DIR ---------


def test_commit_ctl_script_is_absolute_and_under_stack_dir():
    """The script path handed to sudo is absolute and lives under the pinned STACK_DIR (CR-02)."""
    ctl = pathlib.Path(backend.CTL_SCRIPT)
    assert ctl.is_absolute(), f"CTL_SCRIPT must be absolute, got {backend.CTL_SCRIPT!r}"
    assert backend.CTL_SCRIPT.startswith(backend.STACK_DIR), (
        f"CTL_SCRIPT ({backend.CTL_SCRIPT!r}) must be under STACK_DIR ({backend.STACK_DIR!r})"
    )
    assert ctl.name == "nightguard_ctl.py", (
        f"CTL_SCRIPT filename must be 'nightguard_ctl.py', got {ctl.name!r}"
    )


# --- Test 5: exit code is captured from the .rc file and mapped to result -----


def test_commit_maps_rc_file_and_output_to_result():
    """commit() reads the terminal's .rc exit code + .out output into the result dict."""
    result, _call = _capture_commit(
        sim_rc="0", sim_out="committed (tighten, free): config_hmac=abc\n"
    )
    assert result["returncode"] == 0
    assert result["stdout"] == "committed (tighten, free): config_hmac=abc"

    # A refused commit (rc 1) maps through faithfully.
    result2, _ = _capture_commit(sim_rc="1", sim_out="REFUSED (quota)")
    assert result2["returncode"] == 1


# --- Test 6: all temp files are cleaned up after the call --------------------


def test_commit_temp_files_are_cleaned_up_after_call():
    """The .yaml/.rc/.out temp files must be unlinked after commit() returns (T-10-04)."""
    seen_paths: list[str] = []

    def fake_run(argv, **kwargs):
        if argv and argv[0] == "pkill":
            return _FakeProc(0)
        inner = argv[-1]
        # Collect every temp path referenced in the inner command.
        for m in re.finditer(r"(/\S+\.(?:yaml|rc|out))", inner):
            seen_paths.append(m.group(1))
        rc_match = re.search(r"> (\S+\.rc)", inner)
        if rc_match:
            with open(rc_match.group(1), "w", encoding="utf-8") as f:
                f.write("0")
        return _FakeProc(0)

    with patch("ngtui.backend.subprocess.run", side_effect=fake_run):
        backend.commit("timezone: Europe/Amsterdam\n")

    assert seen_paths, "no temp files were referenced — commit() did not run"
    for p in set(seen_paths):
        assert not os.path.exists(p), f"temp file {p!r} still exists after commit() (T-10-04)"
