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
                 "docs/panel.png", "LICENSE",
                 # The generated set. A README that stops linking these is a
                 # repository where five documents exist and nothing points at
                 # them, which is the same as not having written them.
                 "docs/GETTING-STARTED.md", "docs/CONFIGURATION.md",
                 "docs/ARCHITECTURE.md", "docs/DEVELOPMENT.md",
                 "docs/TESTING.md"):
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


def test_the_plugin_does_not_carry_anyones_home_directory():
    """Both QML surfaces hard-coded /home/danitrrga/.local/bin/ngtui.

    The shell does not inherit the login PATH, so an absolute path is right --
    but a literal one meant that on any machine but the author's, every Process
    call in the panel failed and the panel showed a reading that never arrived.
    The deploy resolves an arbitrary owner and installs into THEIR home, so this
    was the one thing left that made the product personal.
    """
    import glob

    plugin = os.path.join(_ROOT, "packaging", "omarchy", "plugins",
                          "danitrrga.nightguard")
    paths = sorted(glob.glob(os.path.join(plugin, "*.qml")))
    assert paths, "no QML found — this test would pass by looking at nothing"

    users = set()
    for path in paths:
        text = _read(path)
        for match in re.finditer(r"/home/([A-Za-z0-9._-]+)", text):
            users.add((os.path.basename(path), match.group(1)))
    assert not users, (
        "these QML files name a literal home directory: %s"
        % ", ".join("%s -> /home/%s" % pair for pair in sorted(users))
    )

    # And the path it does use has to be derived, not merely absent.
    # Declarations only. NightguardWorkshop.qml reads `writer.ngtuiPath`; it is
    # the declaring file that has to derive it.
    declared = [p for p in paths
                if re.search(r"property string ngtuiPath:", _read(p))]
    assert declared, "nothing declares where the CLI is any more"
    for path in declared:
        assert 'Quickshell.env("HOME")' in _read(path), (
            "%s declares ngtuiPath without deriving it from HOME"
            % os.path.basename(path)
        )


def test_no_surface_presents_the_config_key_as_the_watchdog_cadence():
    """`watchdog.check_interval_seconds` does not govern anything: the watchdog
    is a systemd oneshot and never reads it; the cadence is OnUnitActiveSec in
    the timer. A panel that printed the key as the cadence stated a number that
    changing the key would not change -- and raising the key classifies as a
    loosening, so it cost a weekly token to make the panel lie."""
    import glob

    timer = _read(os.path.join(_LINUX, "systemd", "nightguard-watchdog.timer"))
    assert "OnUnitActiveSec=" in timer, "the timer no longer sets the cadence"

    watchdog = _read(os.path.join(_LINUX, "nightguard_watchdog.py"))
    assert "check_interval_seconds" not in watchdog.split('"""')[2], (
        "the watchdog now reads check_interval_seconds outside its docstring — "
        "if that is deliberate, this test and the panel wording both need to "
        "change with it"
    )

    plugin = os.path.join(_ROOT, "packaging", "omarchy", "plugins",
                          "danitrrga.nightguard")
    for path in sorted(glob.glob(os.path.join(plugin, "*.qml"))):
        text = _read(path)
        for index, line in enumerate(text.split("\n")):
            if "check_interval_seconds" not in line or line.strip().startswith("//"):
                continue
            assert False, (
                "%s:%d puts check_interval_seconds on screen"
                % (os.path.basename(path), index + 1)
            )


def test_nothing_shipped_describes_the_grace_window_as_a_feature():
    """`guard.py` honours a grace record in the signed state, and the surfaces
    can render the verdict, but nothing in this build writes one. It was still
    advertised in CLAUDE.md as "a small once-daily timed bypass" — in the file
    contributors and agents read first, describing a button that does not
    exist. The plumbing half-exists, so a superficial grep confirms the lie."""
    granters = []
    for root, _dirs, files in os.walk(_ROOT):
        if any(part in root for part in (".git", "__pycache__", ".planning", "node_modules")):
            continue
        for name in files:
            if not name.endswith((".py", ".qml", ".sh")):
                continue
            if name == os.path.basename(__file__):
                continue  # this file names the patterns it forbids
            text = _read(os.path.join(root, name))
            if re.search(r'state\[["\']grace["\']\]\s*=\s*\{|use_grace|grant_grace', text):
                granters.append(os.path.relpath(os.path.join(root, name), _ROOT))
    assert not granters, (
        "something grants a grace window now (%s) — if that is deliberate, the "
        "docs may describe it again and this test should go" % granters
    )

    claude = _read(os.path.join(_ROOT, "CLAUDE.md"))
    assert "once-daily timed bypass" not in claude
    assert "There is NO daily bypass" in claude, (
        "CLAUDE.md no longer says the bypass does not exist, so the next reader "
        "has nothing to stop them looking for it"
    )


def test_no_package_module_imports_a_dependency_this_package_does_not_declare():
    """`ngtui/ngtui/theme.py` did `from textual.theme import Theme` at module
    level. Textual was a dependency when the terminal app existed; pyproject now
    declares none. So three test modules could not be COLLECTED on any machine
    without a leftover virtualenv — which is every machine but the author's,
    where a stale `ngtui/.venv` carrying textual 8.2.7 made the suite look green.

    A suite that passes only on one disk is not a suite. This asserts the import
    surface, which is the part that decides whether a module can be loaded at
    all; a lazy import inside a function is fine and is what the Theme builders
    use now.
    """
    import ast

    package = os.path.join(_ROOT, "ngtui", "ngtui")
    # First-party. The four trust-stack modules are not in this package: they
    # live in scripts/linux and are reached through NIGHTGUARD_STACK_DIR, which
    # is the whole point — the repo is not what runs, /usr/local/lib is.
    declared = {"ngtui", "ngcommon", "guard", "nightguard_ctl", "appblock"}
    stdlib = set(sys.stdlib_module_names)

    offenders = []
    for name in sorted(os.listdir(package)):
        if not name.endswith(".py"):
            continue
        tree = ast.parse(_read(os.path.join(package, name)), filename=name)
        for node in tree.body:  # module level only — nested imports are deliberate
            roots = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]
            for root in roots:
                if root not in stdlib and root not in declared:
                    offenders.append("%s imports %s" % (name, root))

    assert not offenders, (
        "these modules import something pyproject does not declare, so they "
        "cannot be imported on a clean checkout: " + ", ".join(offenders)
    )


def test_every_document_that_describes_the_retired_product_says_so_at_the_top():
    """Four documents under docs/ describe the Windows product or a design that
    was never built, and two of them still open with "Approved for planning" and
    "authorized to run autonomously". They are the most detailed and most
    convincing writing in the repository, and a person cloning it finds them
    before they find the README.

    One of them is worse than misleading: the re-skin spec prescribes the exact
    hex palette that test_no_fixed_hex now fails the build over, using that
    document's own accent as its control. An agent handed it would produce a
    commit that cannot pass.

    Kept rather than deleted — they are a real record. Stamped so nobody reads
    them as instructions.
    """
    stamped = {
        "docs/design-spec.md": "Superseded",
        "docs/2026-06-04-nightguard-control-design.md": "Superseded",
        "docs/superpowers/specs/2026-06-11-ui-polish-design.md": "do not execute",
        "docs/focus-mode-brief.md": "Never built",
        "docs/linux-port-brief.md": "superseded",
        "HARDENING-SUMMARY.md": "Dated record",
    }
    for path, marker in stamped.items():
        full = os.path.join(_ROOT, path)
        assert os.path.exists(full), "%s is gone — drop its row here too" % path
        head = _read(full)[:1200]
        assert marker in head, (
            "%s no longer carries its historical banner in the first lines, so "
            "it reads as current" % path
        )
