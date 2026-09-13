"""The author-facing installer is idempotent, backup-first, and never clobbers.

It merges into a hand-maintained config the author also edits, so the three
properties that matter are: a re-run detects its own marker and does not
duplicate; the file is copied to `<name>.bak.<epoch>` BEFORE the first edit;
and everything outside the managed block comes out byte-identical, comments
included.

`NG_*` env vars redirect every write into a temp dir and `NG_SKIP_RELOAD`
suppresses the prereq check and the hyprland reload, so the run is fully
headless and never touches the live desktop.

This file used to test the Waybar merge as well — a structural TEXT insertion
into `config.jsonc` that had to preserve `//` comments. That merge is gone with
the terminal app it launched, and it was already inert before that: Omarchy 4
replaced Waybar with Quickshell, and `~/.config/waybar` does not exist on this
box, so the module had been merging into a file nobody reads.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
_INSTALLER = os.path.join(_REPO, "packaging", "omarchy", "install.sh")
_FIXTURES = os.path.join(_HERE, "fixtures")
_MARKER = ">>> nightguard (managed)"


def _run(tmp_path, hypr):
    env = dict(os.environ)
    env.update({
        "HOME": str(tmp_path / "home"),
        "NG_HYPR_CONF": str(hypr),
        "NG_ICON_BASE": str(tmp_path / "icons"),
        "NG_APPLICATIONS_DIR": str(tmp_path / "applications"),
        "NG_BIN_DIR": str(tmp_path / "bin"),
        "NG_SKIP_RELOAD": "1",
    })
    os.makedirs(env["HOME"], exist_ok=True)
    proc = subprocess.run(["bash", _INSTALLER], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc


def _hypr_fixture(tmp_path):
    path = tmp_path / "hyprland.conf"
    shutil.copy(os.path.join(_FIXTURES, "hyprland.conf"), path)
    return path


def test_running_it_twice_adds_the_block_once(tmp_path):
    hypr = _hypr_fixture(tmp_path)
    original = hypr.read_text(encoding="utf-8")

    _run(tmp_path, hypr)
    after_one = hypr.read_text(encoding="utf-8")
    assert after_one.count(_MARKER) == 1, "the managed block was not injected once"

    _run(tmp_path, hypr)
    after_two = hypr.read_text(encoding="utf-8")
    assert after_two.count(_MARKER) == 1, (
        "a second run duplicated the managed block — the marker guard is not working"
    )
    assert after_two == after_one, "the second run changed the file at all"

    # Everything the author wrote is still there, byte for byte, ahead of ours.
    assert after_one.startswith(original), (
        "the injection rewrote the author's own config instead of appending to it"
    )


def test_the_file_is_backed_up_before_it_is_touched(tmp_path):
    hypr = _hypr_fixture(tmp_path)
    original = hypr.read_text(encoding="utf-8")

    _run(tmp_path, hypr)
    backups = glob.glob(str(hypr) + ".bak.*")
    assert len(backups) == 1, "no backup, or more than one: %s" % backups
    with open(backups[0], encoding="utf-8") as fh:
        assert fh.read() == original, "the backup is not the file as it was"

    # A second run makes no edit, so it must not leave a second backup either.
    _run(tmp_path, hypr)
    assert len(glob.glob(str(hypr) + ".bak.*")) == 1


def test_comments_outside_the_block_survive(tmp_path):
    hypr = _hypr_fixture(tmp_path)
    comments = [line for line in hypr.read_text(encoding="utf-8").splitlines()
                if line.strip().startswith("#")]
    assert comments, "the fixture has no comments, so this test would pass over nothing"

    _run(tmp_path, hypr)
    after = hypr.read_text(encoding="utf-8").splitlines()
    for line in comments:
        assert line in after, "the installer ate a comment: %r" % line


def test_it_installs_nothing_that_opens_the_retired_terminal_app(tmp_path):
    """The launcher, the right-click menu and the Waybar module all existed to
    OPEN the terminal editor. Retiring it and leaving them behind would put a
    desktop entry in the launcher that fails with exit 2."""
    hypr = _hypr_fixture(tmp_path)
    _run(tmp_path, hypr)

    applications = tmp_path / "applications"
    assert not (applications / "nightguard.desktop").exists()
    assert not (tmp_path / "bin" / "ngtui-menu").exists()

    import re as _re

    with open(_INSTALLER, encoding="utf-8") as fh:
        script = fh.read()
    # Comments stripped first: the script SHOULD explain in prose what was
    # removed and why. What must be gone is the code.
    script = _re.sub(r"^\s*#.*$", "", script, flags=_re.M)
    for gone in ("merge_waybar_config", "nightguard.desktop", "ngtui-menu",
                 "NG_WAYBAR_CONFIG", "NG_WAYBAR_STYLE"):
        assert gone not in script, "install.sh still installs %s" % gone
