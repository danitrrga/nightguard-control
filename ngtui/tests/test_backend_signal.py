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

    def __init__(self, returncode: int = 0, stdout: str = "committed (tighten, free)"):
        self.returncode = returncode
        self.stdout = stdout


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
            # The commit call — stderr must stay UNCAPTURED (TTY prompt).
            import subprocess as sp

            assert kwargs.get("stderr", None) is not sp.PIPE, (
                "commit()'s sudo call must not capture stderr (TTY prompt)."
            )
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


# --- Test D: result dict shape is unchanged by the signal --------------------


def test_result_dict_shape_unchanged():
    """The returned dict stays exactly {returncode, stdout} — signal adds no keys."""
    result, _pkill_calls = _run_commit(sudo_rc=0)

    assert set(result.keys()) == {"returncode", "stdout"}, (
        f"signal must not add keys to the commit result, got {sorted(result)!r}"
    )
    # stdout is stripped (mirrors the existing commit contract).
    assert result["stdout"] == "committed (tighten, free)"
