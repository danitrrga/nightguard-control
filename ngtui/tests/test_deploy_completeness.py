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


def _plugin_dir():
    root = os.path.dirname(os.path.dirname(_LINUX))
    return os.path.join(root, "packaging", "omarchy", "plugins",
                        "danitrrga.nightguard")


def test_deploy_installs_every_file_the_plugin_ships():
    """The shell only loads plugins from the owner's own plugin directory, so a
    deploy that misses a file leaves the bar on the previous version forever --
    and a missed .qml is worse than a missed everything: the plugin half-loads,
    the shell logs "is not a type" for the one component it cannot resolve, and
    the widget goes blank with no other symptom.

    This is why the deploy copies the directory by glob rather than by a
    hand-kept list. NightguardPanel.qml was named in NEITHER for two phases:
    every deploy shipped a manifest pointing at a panel it did not install.
    """
    with open(_DEPLOY, encoding="utf-8") as fh:
        text = fh.read()
    assert "plugins/danitrrga.nightguard" in text
    assert "*.qml" in text, (
        "deploy.sh names plugin files one by one again -- the next file added "
        "will be forgotten exactly as NightguardPanel.qml was"
    )
    assert "manifest.json" in text


def test_the_manifest_entry_points_all_exist():
    """A manifest naming a file that is not there is a plugin the shell refuses
    to mount, and the only symptom is a line in the journal."""
    import json

    plugin = _plugin_dir()
    with open(os.path.join(plugin, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["entryPoints"], "a plugin with no entry point mounts nothing"
    for kind, name in manifest["entryPoints"].items():
        assert os.path.isfile(os.path.join(plugin, name)), (
            "manifest entry point %r names %s, which is not in the plugin" % (kind, name)
        )


def test_every_qml_file_the_plugin_references_is_in_the_plugin():
    """Same-directory type resolution is what makes `NightguardWriter {}` work
    inside the panel. A component referenced but not shipped resolves to
    nothing, and QML says so once, quietly, at load."""
    import glob
    import re as _re

    plugin = _plugin_dir()
    present = {os.path.basename(p)[:-4]
               for p in glob.glob(os.path.join(plugin, "*.qml"))}
    for path in glob.glob(os.path.join(plugin, "*.qml")):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for referenced in _re.findall(r"\b(Nightguard[A-Za-z]*)\s*\{", text):
            assert referenced in present, (
                "%s instantiates %s, which is not a file in the plugin"
                % (os.path.basename(path), referenced)
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
    """Standing rule: the bar widget may not exec anything privileged and may
    not change state. It reads; the panel it opens is where an edit is staged."""
    widget = os.path.join(_plugin_dir(), "BarWidget.qml")
    with open(widget, encoding="utf-8") as fh:
        text = fh.read()
    for forbidden in ("sudo", "pkexec", "nightguard_ctl", "commit"):
        assert forbidden not in text, (
            "the bar widget references %r — it must stay read-only" % forbidden
        )


def test_no_qml_ever_builds_a_privileged_argv_itself():
    """The panel can write now, and this is the line that keeps that safe.

    Every privileged call goes out as `ngtui commit`, never as a `pkexec` or
    `sudo` argv assembled in QML. The reason is `_resolve_stack_dir()`: it
    refuses to hand a path to a root-run interpreter unless that directory
    really contains nightguard_ctl.py. QML naming the signer directly would run
    a stack nothing had validated -- and it would be a SECOND place the argv
    shape lives, free to drift from the sudoers/polkit-pinned one.
    """
    import glob
    import re as _re

    for path in glob.glob(os.path.join(_plugin_dir(), "*.qml")):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        # Comments are stripped first. The QML SHOULD say, in prose, that a
        # commit ends at pkexec and what its exit codes mean -- that is the
        # explanation a reader needs. What must not appear is the word in the
        # code.
        text = _re.sub(r"/\*.*?\*/", " ", text, flags=_re.S)
        text = _re.sub(r"^\s*//.*$", "", text, flags=_re.M)
        text = _re.sub(r"\s//.*$", "", text, flags=_re.M)
        for forbidden in ("pkexec", "sudo", "nightguard_ctl", "/usr/bin/python3"):
            assert forbidden not in text, (
                "%s names %r — the privileged argv belongs in backend.py, which "
                "validates the stack directory before root ever runs it"
                % (os.path.basename(path), forbidden)
            )


def test_deploy_runs_the_config_migration():
    """Without it the edit window ships inert: the gate reads its window from the
    sanctioned config, and a config with no block is ungated by design."""
    with open(_DEPLOY, encoding="utf-8") as fh:
        text = fh.read()
    assert "ensure-config" in text
