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


# Types that come from QtQuick, QtQuick.Controls or Quickshell rather than from
# this plugin or the shell's kit. Listing them is the point: anything
# capitalised that is NOT here and NOT a file must be a local component, and a
# local component that is not a file resolves to nothing.
_IMPORTED_TYPES = {
    "Item", "Rectangle", "Text", "Column", "Row", "Grid", "Flow", "Flickable",
    "Repeater", "MouseArea", "Component", "Loader", "Timer", "Connections",
    "FocusScope", "Behavior", "NumberAnimation", "PropertyAnimation",
    "SequentialAnimation", "ScrollBar", "Shape", "ShapePath", "PathAngleArc",
    "TextMetrics", "Process", "StdioCollector", "Image", "Canvas", "Keys",
    "QtObject", "Binding", "ListModel", "ListElement", "Scope", "Variants",
    "IpcHandler", "IpcCall", "SystemClock", "FileView", "Socket",
    "FloatingWindow", "PanelWindow", "PopupWindow", "ShellRoot", "Singleton",
    "WrapperItem", "WrapperRectangle", "MarginWrapperManager", "ClippingRectangle",
}


def test_every_component_a_qml_file_instantiates_actually_resolves():
    """Same-directory type resolution is what makes `NightguardWriter {}` work
    inside the panel. A component referenced but not shipped resolves to
    nothing, and QML says so once, quietly, at load.

    This used to look only at names beginning with "Nightguard", which meant
    `DayDial {}` -- extracted out of the panel into its own file -- was not
    covered by anything. qmllint does not cover it either: with no qmldir it
    resolves no local types at all, and returns 0 on a file that instantiates
    a name that does not exist (checked, by renaming one).
    """
    import glob
    import re as _re

    plugin = _plugin_dir()
    local = {os.path.basename(p)[:-4]
             for p in glob.glob(os.path.join(plugin, "*.qml"))}

    shell = os.environ.get("OMARCHY_PATH", "/usr/share/omarchy") + "/shell"
    kit = set()
    for sub in ("Ui", "Commons", "services", "Services", "Widgets"):
        kit |= {os.path.basename(p)[:-4]
                for p in glob.glob(os.path.join(shell, sub, "*.qml"))}
    assert "Panel" in kit and "Button" in kit, (
        "the shell kit was not found at %s — this test would pass by knowing "
        "nothing" % shell
    )

    known = local | kit | _IMPORTED_TYPES

    for path in sorted(glob.glob(os.path.join(plugin, "*.qml"))):
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        name = os.path.basename(path)
        declared = set(_re.findall(r"^\s*component\s+([A-Z][A-Za-z0-9]*)\s*:",
                                   "\n".join(lines), _re.MULTILINE))
        for index, line in enumerate(lines):
            match = _re.match(r"\s*([A-Z][A-Za-z0-9]*)\s*\{\s*$", line)
            if not match:
                continue
            kind = match.group(1)
            assert kind in known or kind in declared, (
                "%s:%d instantiates %s, which is neither a file in the plugin, "
                "a component in the shell kit, an inline component of this "
                "file, nor a listed imported type — it resolves to nothing"
                % (name, index + 1, kind)
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


def test_no_wrapping_text_hides_its_height_from_the_layout():
    """A wrapped line the enclosing Column cannot see is a popup that asks to be
    shorter than its own contents.

    This is the defect that cut the sites card and both action buttons off the
    bottom of the panel with no scrollbar to hint they were there. `Toggle` lays
    its `description` out inside an ANCHORED Row: a description long enough to
    wrap grows the row that is drawn without growing the `implicitHeight` the
    Column adds up, and `fittedContentHeight` then faithfully sizes the popup to
    a number that is too small. Measured at the time: the panel asked for 588
    logical pixels against a cap that allowed 607, so it was never being
    clamped — it was measuring itself wrong.

    Two rules, and between them the class of bug cannot come back:

    * no `Toggle` carries a `description` — the caption is a sibling Text that
      the Column lays out itself;
    * every `wrapMode: Text.WordWrap` has an explicit `width` above it, so the
      Text can resolve its own height before anything sums it.
    """
    import glob
    import re as _re

    for path in glob.glob(os.path.join(_plugin_dir(), "*.qml")):
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        name = os.path.basename(path)

        for index, line in enumerate(lines):
            if _re.match(r"\s*description:", line):
                assert False, (
                    "%s:%d sets a Toggle description. A wrapped one does not "
                    "reach the enclosing Column's implicitHeight — put the "
                    "caption in a sibling Text with an explicit width"
                    % (name, index + 1)
                )

            if "wrapMode: Text.WordWrap" not in line:
                continue
            # Walk back to the `Text {` that opens this block, not a fixed
            # number of lines: a multi-line `color: { ... }` switch sits
            # happily between the width and the wrapMode, and a short window
            # reads that as a missing width. (It did, on the first run.)
            width = None
            for back in range(index, max(0, index - 80), -1):
                if _re.search(r"\bwidth:", lines[back]):
                    width = lines[back]
                    break
                if lines[back].strip().endswith("Text {"):
                    break
            assert width is not None, (
                "%s:%d wraps with no width above it — its height is unknowable "
                "until after layout, so whatever sums it sums the wrong number"
                % (name, index + 1)
            )


def test_the_deploy_installs_a_launcher_entry_that_opens_the_workshop():
    """Searching the launcher for "nightguard" must find something.

    The terminal editor's .desktop entry was removed with the editor, and
    nothing replaced it — so for a while Nightguard was reachable only from the
    bar icon, and the launcher answered "No matches for nightguard". An
    application with no way in from the launcher reads as an application that
    is not installed.
    """
    root = os.path.dirname(os.path.dirname(_LINUX))
    entry = os.path.join(root, "packaging", "omarchy", "nightguard.desktop")
    assert os.path.isfile(entry), "the launcher entry is not in the repo"

    with open(entry, encoding="utf-8") as fh:
        lines = [l.strip() for l in fh if not l.lstrip().startswith("#")]
    exec_line = next((l for l in lines if l.startswith("Exec=")), "")
    assert "danitrrga.nightguard" in exec_line, "the entry does not open the plugin"
    # Checked on the Exec line and not the whole file: the file SHOULD explain in
    # prose what it used to launch. What must not be there is the command.
    assert "ngtui" not in exec_line, (
        "the entry still launches the retired terminal app, which now exits 2 — "
        "clicking it would look like the application being broken, not gone"
    )
    assert "Terminal=false" in lines

    with open(_DEPLOY, encoding="utf-8") as fh:
        deploy = fh.read()
    assert "nightguard.desktop" in deploy, (
        "deploy.sh does not install the launcher entry, so a fresh deploy leaves "
        "the application invisible to the launcher"
    )
    assert "update-desktop-database" in deploy, (
        "without refreshing the database the entry does not appear until the next "
        "login, which is the same symptom as a broken install"
    )


def test_the_deploy_clears_the_retired_terminal_entry():
    """A previous deploy installed an entry pointing at `ngtui`. Left behind, it
    exits 2 the moment it is clicked."""
    with open(_DEPLOY, encoding="utf-8") as fh:
        deploy = fh.read()
    assert "org.omarchy.ngtui.png" in deploy and "rm -f" in deploy, (
        "deploy.sh does not clean up the retired editor's icons"
    )


def test_every_shell_script_is_executable_in_the_index():
    """`core.filemode=false` in this repo, so chmod on disk never reaches git.

    A shell script committed 100644 is unrunnable after any fresh clone or
    checkout: `sudo /path/to/deploy.sh` answers `command not found`, which reads
    like a missing file rather than a missing permission bit. deploy.sh itself
    shipped that way and blocked the install.

    Only .sh files are checked. The Python modules carry shebangs but are always
    invoked as `python3 <path>` (the signer deliberately so, through pkexec), and
    deploy.sh installs each with an explicit `install -m 0644`, so their mode in
    the repo reaches nothing.
    """
    import subprocess

    root = os.path.dirname(os.path.dirname(_LINUX.rstrip(os.sep)))
    listing = subprocess.run(
        ["git", "ls-files", "-s", "--", "*.sh"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout
    assert listing.strip(), "git listed no shell scripts; this test stopped measuring anything"

    offenders = []
    for line in listing.splitlines():
        mode = line.split(" ", 1)[0]
        path = line.split("\t", 1)[1]
        full = os.path.join(root, path)
        if not os.path.isfile(full):
            continue
        with open(full, "rb") as fh:
            if fh.read(2) != b"#!":
                continue
        if mode != "100755":
            offenders.append(f"{path} is {mode}")

    assert not offenders, (
        "these scripts start with a shebang but are not executable in git, so a "
        "fresh checkout cannot run them: " + ", ".join(offenders)
    )
