"""config.yaml must come back to the user, however root was obtained.

The file is written by root and deliberately left owned by the user, because
the revert model needs the hand edit to be POSSIBLE so the watchdog can be seen
undoing it. Its parent directory is ``root:root 0755``, so a root-owned
config.yaml cannot be edited, recreated or even moved aside by its owner: half
of what this product promises stops being demonstrable.

There is a second consumer that nobody would think to check.
``nightguard_watchdog.py`` derives the user's HOME from this file's owner in
order to find the Steam and Heroic libraries::

    return pwd.getpwuid(os.stat(ng.CONFIG).st_uid).pw_dir

A root-owned config.yaml points the game catalog at /root, where there are no
games. Game blocking would silently stop covering anything.

The old implementation read ``SUDO_UID`` and nothing else. The desktop panel
authorises through polkit, and ``pkexec`` sets ``PKEXEC_UID`` and no
``SUDO_UID`` at all (man pkexec), so the guard clause was simply false and the
chown never ran. These tests are about the moment that became the ordinary
path rather than the exotic one.
"""
from __future__ import annotations

import os
import sys

import pytest

_STACK = os.environ.get("NIGHTGUARD_STACK_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "linux",
)
if _STACK not in sys.path:
    sys.path.insert(0, _STACK)
import nightguard_ctl as ctl  # noqa: E402


@pytest.fixture
def config_at(tmp_path, monkeypatch):
    """Point the signer's CONFIG at a file this test owns."""
    path = tmp_path / "config.yaml"
    path.write_text("timezone: Europe/Amsterdam\n", encoding="utf-8")
    monkeypatch.setattr(ctl.ng, "CONFIG", str(path), raising=False)
    return path


def _clear_env(monkeypatch):
    for name in ("SUDO_UID", "SUDO_GID", "PKEXEC_UID"):
        monkeypatch.delenv(name, raising=False)


def test_the_current_owner_wins_over_every_environment_variable(config_at, monkeypatch):
    """The strongest answer, and the only one that does not care how this
    process got its privileges: whoever owns the file right now."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("SUDO_UID", "4242")
    monkeypatch.setenv("SUDO_GID", "4242")
    assert ctl._config_owner() == (os.getuid(), os.getgid()), (
        "a file already owned by a real user answers the question by itself"
    )


def test_pkexec_is_read_when_the_file_is_root_owned(config_at, monkeypatch):
    """`pkexec` sets PKEXEC_UID and no SUDO_UID. Reading only SUDO_UID is why
    the chown silently never happened once the panel became the writer."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("PKEXEC_UID", str(os.getuid()))
    monkeypatch.setenv("SUDO_GID", str(os.getgid()))
    monkeypatch.setattr(os, "stat", lambda p, *a, **k: _root_owned(), raising=False)
    assert ctl._config_owner() == (os.getuid(), os.getgid())


def test_sudo_still_works(config_at, monkeypatch):
    """The terminal path is retired, not forbidden. A sudo-run commit must keep
    behaving exactly as it did."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("SUDO_UID", str(os.getuid()))
    monkeypatch.setenv("SUDO_GID", str(os.getgid()))
    monkeypatch.setattr(os, "stat", lambda p, *a, **k: _root_owned(), raising=False)
    assert ctl._config_owner() == (os.getuid(), os.getgid())


def test_nothing_knowable_reports_nothing_rather_than_guessing(config_at, monkeypatch):
    """Guessing an owner is worse than leaving it root and saying so: a wrong
    chown hands the file to somebody who is not the owner."""
    _clear_env(monkeypatch)
    monkeypatch.setattr(os, "stat", lambda p, *a, **k: _root_owned(), raising=False)
    assert ctl._config_owner() is None


def test_an_unknown_owner_is_announced_and_never_silent(config_at, monkeypatch, capsys):
    ctl._chown_back_config(None)
    err = capsys.readouterr().err
    assert "root" in err and "Hand edits will be impossible" in err


def test_the_owner_is_read_before_the_write_not_after():
    """`_atomic_write_bytes` replaces config.yaml with a fresh root-owned file,
    so asking afterwards would only ever answer "root". The order is the fix."""
    import inspect

    source = inspect.getsource(ctl._write_commit)
    owner_line = source.index("_config_owner()")
    write_line = source.index("_atomic_write_bytes(ng.CONFIG")
    assert owner_line < write_line, (
        "the owner must be read before config.yaml is replaced, or the answer "
        "is always root"
    )


def test_the_watchdog_still_derives_home_from_this_file():
    """Guards the reason the test above matters. If this ever stops being true,
    the comment explaining the second consumer should go with it."""
    with open(os.path.join(_STACK, "nightguard_watchdog.py"), encoding="utf-8") as fh:
        text = fh.read()
    assert "pwd.getpwuid(os.stat(ng.CONFIG).st_uid).pw_dir" in text


class _root_owned:
    st_uid = 0
    st_gid = 0
    st_mode = 0o100644
