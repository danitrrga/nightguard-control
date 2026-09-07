"""Everything the deployed stack imports must actually be deployed.

A module added to scripts/linux/ but left out of deploy.sh's install loop is a
silent, total failure: the watchdog is a systemd oneshot, so it would raise
ModuleNotFoundError on every 60-second tick, log nothing useful, and quietly stop
reverting hand edits. Nothing in the test suite would notice, because the suite
imports from the working tree where the file exists.

This caught exactly that: appblock.py was written, imported by the watchdog, and
missing from the install list.
"""
from __future__ import annotations

import ast
import os
import re

import pytest

_LINUX = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "linux",
)
_DEPLOY = os.path.join(_LINUX, "deploy.sh")

# The stack's own modules. Anything else a module imports is either stdlib or a
# sibling that appears here too.
_LOCAL_MODULES = {"ngcommon", "guard", "nightguard_ctl", "nightguard_watchdog", "appblock"}


def _installed_modules():
    """The module basenames deploy.sh copies into /usr/local/lib/nightguard."""
    with open(_DEPLOY, encoding="utf-8") as fh:
        text = fh.read()
    match = re.search(r"^for f in ([^;]+); do$", text, re.MULTILINE)
    assert match, "deploy.sh no longer has the install loop this test reads"
    return {name[:-3] for name in match.group(1).split() if name.endswith(".py")}


def _local_imports(path):
    """Sibling modules this file imports."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _LOCAL_MODULES:
                    found.add(root)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in _LOCAL_MODULES:
                found.add(root)
    return found


@pytest.mark.parametrize("module", sorted(_LOCAL_MODULES))
def test_every_stack_module_is_installed_by_deploy(module):
    """The list in deploy.sh is the whole of what reaches the running system."""
    assert os.path.exists(os.path.join(_LINUX, module + ".py")), (
        "%s.py is named in this test but not in the tree" % module
    )
    assert module in _installed_modules(), (
        "%s.py exists and is imported, but deploy.sh does not install it — "
        "the deployed watchdog would fail on every tick" % module
    )


def test_no_deployed_module_imports_something_that_is_not_deployed():
    """The closure check, so a NEW module added later is caught too."""
    installed = _installed_modules()
    for module in sorted(installed):
        path = os.path.join(_LINUX, module + ".py")
        for dependency in _local_imports(path):
            assert dependency in installed, (
                "%s.py imports %s, which deploy.sh does not install"
                % (module, dependency)
            )


def test_the_watchdog_really_does_import_the_blocker():
    """Guards the test above from passing vacuously if the import is ever dropped
    while the enforcement call stays."""
    assert "appblock" in _local_imports(os.path.join(_LINUX, "nightguard_watchdog.py"))


def test_deploy_installs_the_bar_widget_it_ships():
    """The desktop surface is an omarchy-shell bar widget, and the shell only
    loads plugins from the owner's own plugin directory -- so a deploy that does
    not copy them there leaves the bar showing the previous version forever."""
    with open(_DEPLOY, encoding="utf-8") as fh:
        text = fh.read()
    assert "plugins/danitrrga.nightguard" in text
    for name in ("manifest.json", "BarWidget.qml"):
        assert name in text, "deploy.sh does not install %s" % name


def test_the_bar_widget_files_exist_where_deploy_expects_them():
    root = os.path.dirname(_LINUX)
    plugin = os.path.join(os.path.dirname(root), "packaging", "omarchy",
                          "plugins", "danitrrga.nightguard")
    for name in ("manifest.json", "BarWidget.qml"):
        assert os.path.isfile(os.path.join(plugin, name)), (
            "%s is named in deploy.sh but missing from the repo" % name
        )


def test_the_bar_widget_is_installed_as_the_owner_not_as_root():
    """The shell runs as the user. A root-owned file in his plugin directory
    would be a path he cannot fix without sudo, in a directory the shell reloads
    from automatically."""
    with open(_DEPLOY, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    # Only actual invocations, not prose: an `echo "== installing ..."` line
    # mentions both words and means nothing.
    invocations = [
        line for line in lines
        if "PLUGIN_DIR" in line and re.search(r"(^|\s|--\s)install\b", line)
        and not line.strip().startswith(("#", "echo"))
    ]
    assert invocations, "deploy.sh no longer installs the plugin at all"
    for line in invocations:
        assert "runuser" in line, "plugin install runs as root: %s" % line.strip()


def test_the_widget_never_reaches_for_a_privileged_command():
    """Standing rule: a bar widget may not exec anything privileged, and may not
    change state. It opens the TUI; the TUI is where the signer is reached."""
    root = os.path.dirname(os.path.dirname(_LINUX))
    widget = os.path.join(root, "packaging", "omarchy", "plugins",
                          "danitrrga.nightguard", "BarWidget.qml")
    with open(widget, encoding="utf-8") as fh:
        text = fh.read()
    for forbidden in ("sudo", "pkexec", "nightguard_ctl", "commit"):
        assert forbidden not in text, (
            "the bar widget references %r — it must stay read-only" % forbidden
        )


def test_deploy_runs_the_config_migration():
    """Without it the edit window ships inert: the gate reads its window from the
    sanctioned config, and a config with no block is ungated by design."""
    with open(_DEPLOY, encoding="utf-8") as fh:
        text = fh.read()
    assert "ensure-config" in text
