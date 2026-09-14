"""A machine that has never run this must end up with a working instance.

For a year the deploy bound to one username written into the script and refused
to run unless an instance already existed. Both were invisible to every test,
because every test ran on the machine that already had one.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEPLOY = os.path.join(_ROOT, "scripts", "linux", "deploy.sh")
_SUDOERS = os.path.join(_ROOT, "scripts", "linux", "nightguard.sudoers")
_EXAMPLE = os.path.join(_ROOT, "config.example.yaml")
_LINUX = os.path.join(_ROOT, "scripts", "linux")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_no_install_artefact_carries_a_personal_username():
    """The author's username in the installer grants his account the right to
    sign on every machine that installs this, and grants nobody that right on
    the machines where the account does not exist."""
    offenders = []
    for root, _dirs, files in os.walk(_LINUX):
        if "__pycache__" in root:
            continue
        for name in files:
            if name == "migrate_from_lifeos.sh":
                continue  # a one-shot move between two paths on one machine
            path = os.path.join(root, name)
            try:
                text = _read(path)
            except (OSError, UnicodeDecodeError):
                continue
            # The plugin id is a namespace, not a path, and is meant to carry
            # the author's name the way every first-party plugin carries theirs.
            stripped = text.replace("danitrrga.nightguard", "")
            if "danitrrga" in stripped:
                offenders.append(os.path.relpath(path, _ROOT))
    assert not offenders, (
        "these ship with one person's username baked in: %s" % ", ".join(offenders)
    )


def test_the_sudoers_names_the_owner_through_a_placeholder():
    text = _read(_SUDOERS)
    assert "@NIGHTGUARD_OWNER@ ALL=(root)" in text, (
        "the sudoers file no longer carries a placeholder for the owner"
    )
    deploy = _read(_DEPLOY)
    assert "s/@NIGHTGUARD_OWNER@/$OWNER/" in deploy, (
        "nothing substitutes the placeholder, so the installed sudoers would "
        "grant the right to a user literally called @NIGHTGUARD_OWNER@"
    )
    assert re.search(r'grep -q "@NIGHTGUARD_OWNER@" "\$SUDOERS_STAGED"', deploy), (
        "the deploy does not check that the substitution happened"
    )
    assert 'visudo -cf "$SUDOERS_STAGED"' in deploy, (
        "the file validated is not the file installed — visudo must see the "
        "substituted one, or a bad username reaches /etc/sudoers.d unchecked"
    )


def test_the_owner_is_derived_and_the_deploy_refuses_to_guess():
    deploy = _read(_DEPLOY)
    assert "resolve_owner()" in deploy
    for source in ("NIGHTGUARD_OWNER", "SUDO_USER", "PKEXEC_UID"):
        assert source in deploy, "the owner is no longer derived from %s" % source
    assert "cannot tell whose machine this is" in deploy, (
        "with no owner resolvable the deploy must stop, not pick one"
    )


def test_a_first_install_creates_the_instance_and_signs_it():
    deploy = _read(_DEPLOY)
    assert "first install — creating $DATA" in deploy, (
        "the deploy still exits when no instance exists, so it can only ever "
        "run on a machine that already had one"
    )
    assert "nightguard_ctl.py\" init" in deploy or "nightguard_ctl.py' init" in deploy, (
        "a first install never creates the signing key, so the watchdog would "
        "read the fresh config as tampered"
    )
    # Order matters: the key is made after the code is deployed, and `init`
    # signs whatever config.yaml says, so the seed has to be there first.
    seed = deploy.index("seeding config.yaml from config.example.yaml")
    init = deploy.index("first install: creating the signing key")
    assert seed < init, "the config is signed before it is seeded"


def test_the_example_config_parses_with_the_guards_own_parser():
    """It is what a first install copies into place. If it stops parsing, a
    fresh machine gets a config the guard cannot read -- and the guard's
    posture on an unreadable config is to close everything."""
    sys.path.insert(0, _LINUX)
    try:
        import ngcommon
    finally:
        sys.path.pop(0)
    doc = ngcommon.yaml_load(_read(_EXAMPLE))

    assert doc["curfew"]["enabled"] is True
    assert re.match(r"^\d{2}:\d{2}$", doc["curfew"]["start"])
    assert re.match(r"^\d{2}:\d{2}$", doc["curfew"]["end"])
    assert doc["edit_window"]["enabled"] is True
    assert doc["watchdog"]["enabled"] is True
    assert doc["clock_protection"]["enabled"] is True

    apps = doc["blocking"]["native_apps"]
    assert apps["mode"] == "blocklist"
    # Lists, not None. An inline `[]` that parsed as None is exactly the bug
    # that made the first site anybody blocked write an unreadable config.
    for key in ("blacklist", "allowlist"):
        assert isinstance(apps[key], list), "%s parsed as %r" % (key, apps[key])
    assert isinstance(doc["blocking"]["browser_extension"]["blocked_urls"], list)


def test_the_example_config_ships_nothing_personal():
    text = _read(_EXAMPLE)
    for leak in ("danitrrga", "Master Duel", "CurseForge", "zen-bin", "discord"):
        assert leak not in text, "the example config still carries %r" % leak


def test_the_deploy_is_syntactically_valid_bash():
    """Every guard above reads the file as text. This one asks bash."""
    result = subprocess.run(["bash", "-n", _DEPLOY], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_the_readme_points_at_things_that_exist():
    """The previous README described a Windows PowerShell product that had not
    shipped for months: it told the reader to run setup.ps1, referenced a
    config.example.yaml that was not in the repo, and documented a watchdog
    that ran as a Scheduled Task. Nothing failed, because nothing checked.
    """
    readme = _read(os.path.join(_ROOT, "README.md"))

    for path in ("scripts/linux/deploy.sh", "config.example.yaml", "banner.png",
                 "docs/panel.png", "LICENSE"):
        assert path in readme, "the README no longer mentions %s" % path
        assert os.path.exists(os.path.join(_ROOT, path)), (
            "the README points at %s, which is not in the repo" % path
        )

    # The uninstall instructions name real paths. A wrong one here leaves the
    # watchdog running on a machine whose owner believes they removed it.
    units = os.path.join(_ROOT, "scripts", "linux", "systemd")
    assert "nightguard-watchdog.timer" in readme
    for unit in ("nightguard-watchdog.service", "nightguard-watchdog.timer"):
        assert os.path.exists(os.path.join(units, unit)), unit
    assert "/etc/polkit-1/rules.d/00-nightguard.rules" in readme
    assert os.path.exists(os.path.join(_ROOT, "scripts", "linux", "polkit",
                                       "00-nightguard.rules"))

    deploy = _read(_DEPLOY)
    assert "/usr/local/lib/nightguard" in deploy and "/usr/local/lib/nightguard" in readme
    assert "/var/lib/nightguard" in deploy and "/var/lib/nightguard" in readme

    # The retired product must not be described as if it ships. Scanned only
    # above the section that says it is retired -- naming PowerShell there is
    # the whole point of that paragraph.
    heading = "## The retired Windows version"
    assert heading in readme, "the README no longer says where the old product went"
    current = readme[:readme.index(heading)]
    for ghost in ("setup.ps1", "PowerShell", "Scheduled Task", "Cold Turkey",
                  "Windows 10/11", "src-tauri", "Cargo.toml"):
        assert ghost not in current, (
            "the README still describes the retired Windows product as if it "
            "ships: %r" % ghost
        )


def test_the_readme_does_not_promise_a_feature_nothing_grants():
    """The guard honours a daily grace window if the signed state carries one,
    but nothing in this build writes one -- no CLI subcommand, no panel button.
    Documenting it would be the old README's mistake in a new place."""
    readme = _read(os.path.join(_ROOT, "README.md")).lower()
    assert "grace" not in readme, (
        "the README mentions grace; nothing in this build can grant it"
    )
