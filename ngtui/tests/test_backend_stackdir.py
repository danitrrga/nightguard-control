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


def test_legit_override_still_works(monkeypatch):
    """The real LifeOS override resolves cleanly (no regression for the author box)."""
    monkeypatch.setenv(
        "NIGHTGUARD_STACK_DIR",
        "/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard",
    )
    resolved = backend._resolve_stack_dir()
    assert resolved.endswith("LifeOS/scripts/nightguard")


def test_ctl_script_lives_under_pinned_stack_dir():
    """The sudo argv path is derived from the validated STACK_DIR, not the raw env."""
    assert backend.CTL_SCRIPT == str(
        __import__("pathlib").Path(backend.STACK_DIR) / "nightguard_ctl.py"
    )
