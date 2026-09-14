"""Tests for backend STACK_DIR pinning (CR-02).

``_resolve_stack_dir`` reads NIGHTGUARD_STACK_DIR at call time, resolves it to an
absolute real path, and requires that the directory contains ``nightguard_ctl.py``.
A poisoned env that points at a directory WITHOUT the signer CLI must fail closed
rather than letting a substituted stack onto sys.path / into the sudo argv.
"""
from __future__ import annotations

import pytest

from ngtui import backend


def test_resolve_stack_dir_accepts_dir_with_ctl(tmp_path, monkeypatch):
    """A directory containing nightguard_ctl.py is accepted and returned absolute."""
    (tmp_path / "nightguard_ctl.py").write_text("# stand-in signer CLI\n")
    monkeypatch.setenv("NIGHTGUARD_STACK_DIR", str(tmp_path))

    resolved = backend._resolve_stack_dir()

    assert resolved == str(tmp_path.resolve())


def test_resolve_stack_dir_rejects_dir_without_ctl(tmp_path, monkeypatch):
    """A poisoned path lacking nightguard_ctl.py is rejected (fail closed)."""
    monkeypatch.setenv("NIGHTGUARD_STACK_DIR", str(tmp_path))

    with pytest.raises(RuntimeError) as exc:
        backend._resolve_stack_dir()

    assert "nightguard_ctl.py" in str(exc.value)


def test_legit_override_still_works(monkeypatch, tmp_path):
    """A valid override resolves cleanly.

    This used to pin the author's absolute checkout path and assert the result
    ended with "nightguard-control/scripts/linux" — so it proved the override
    works only for a directory named after one person's clone, and on any other
    machine it asserted against a path that does not exist.
    """
    stack = tmp_path / "scripts" / "linux"
    stack.mkdir(parents=True)
    # The resolver accepts a directory because it CONTAINS the signer, not
    # because of what it is called — which is the property worth asserting.
    (stack / "nightguard_ctl.py").write_text("# stand-in\n")
    monkeypatch.setenv("NIGHTGUARD_STACK_DIR", str(stack))
    resolved = backend._resolve_stack_dir()
    assert resolved == str(stack)


def test_ctl_script_lives_under_pinned_stack_dir():
    """The sudo argv path is derived from the validated STACK_DIR, not the raw env."""
    assert backend.CTL_SCRIPT == str(
        __import__("pathlib").Path(backend.STACK_DIR) / "nightguard_ctl.py"
    )
