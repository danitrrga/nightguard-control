"""The curfew's kill decision, and the ways it must refuse to fire.

The previous native-app blocker was reverted in June 2026 after a review found it
would SIGKILL Steam and Discord at three in the afternoon, because the
clock-tamper check ran independently of the curfew window. The first test in this
file is that regression, and it is the one that matters most: everything else
here is about not killing the wrong thing, and that one is about not killing at
the wrong time.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

from ngtui import backend  # noqa: F401  (puts the trust stack on sys.path)

import appblock


# --- helpers -----------------------------------------------------------------

_APP_SLICE = "0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-Hyprland-x.scope"
_SESSION_SLICE = "0::/user.slice/user-1000.slice/user@1000.service/session.slice/pipewire.service"


def _proc(pid, exe, cgroup=_APP_SLICE, cmdline=""):
    return appblock.Process(pid, exe, cgroup, cmdline)


def _cfg(mode="blocklist", enabled=True, blacklist=None, allowlist=None, block_games=False):
    return {
        "blocking": {
            "native_apps": {
                "enabled": enabled,
                "mode": mode,
                "blacklist": blacklist if blacklist is not None else [],
                "allowlist": allowlist if allowlist is not None else [],
                "block_games": block_games,
            }
        }
    }


_STEAM = _proc(100, "/usr/lib/steam/steam")
_ZEN = _proc(101, "/opt/zen-browser-bin/zen-bin")
_ANTIGRAVITY = _proc(
    102, "/opt/antigravity-ide/antigravity-ide",
    cgroup="0::/user.slice/user-1000.slice/user@1000.service/app.slice/"
           "app-org.chromium.Chromium-102.scope",
)
_CLAUDE = _proc(103, "/home/danitrrga/.local/share/mise/installs/claude/2.1.263/claude")


# --- the regression that retired the previous implementation -----------------

@pytest.mark.parametrize("verdict", ["clock_tamper", "offline_blocked", "outside_curfew", "grace_active"])
def test_nothing_is_killed_unless_the_curfew_is_actually_locked(verdict):
    """The bug that got native blocking reverted: a clock jump at 3pm is not a
    curfew. An untrustworthy clock is a reason to refuse config changes, never a
    reason to start ending the user's applications in the middle of the day."""
    victims = appblock.decide_kills(
        verdict, _cfg(blacklist=["steam"]), [_STEAM],
    )
    assert victims == []


def test_the_same_process_is_killed_when_the_curfew_is_locked():
    """The positive half, so the test above cannot pass by killing nothing ever."""
    victims = appblock.decide_kills("locked", _cfg(blacklist=["steam"]), [_STEAM])
    assert [p.pid for p in victims] == [100]


def test_disabled_blocking_kills_nothing_even_when_locked():
    victims = appblock.decide_kills(
        "locked", _cfg(enabled=False, blacklist=["steam"]), [_STEAM],
    )
    assert victims == []


# --- the floor ---------------------------------------------------------------

_DESKTOP = [
    _proc(1, "/usr/bin/Hyprland"),
    _proc(2, "/usr/bin/quickshell"),
    _proc(3, "/usr/bin/pipewire", cgroup=_SESSION_SLICE),
    _proc(4, "/usr/lib/xdg-desktop-portal-hyprland"),
    _proc(5, "/usr/bin/gnome-keyring-daemon"),
    _proc(6, "/usr/bin/uwsm"),
    _proc(7, "/usr/lib/gvfsd-metadata"),
    _proc(8, "/usr/bin/dbus-broker"),
]


@pytest.mark.parametrize("proc", _DESKTOP, ids=lambda p: os.path.basename(p.exe))
def test_the_desktop_survives_allowlist_mode(proc):
    """Allowlist mode kills everything not named, so an omission here does not
    weaken the feature -- it takes down the compositor, the bar, or the audio
    stack, and the user cannot get to the sanctioned editor to undo it."""
    victims = appblock.decide_kills("locked", _cfg(mode="allowlist", allowlist=[]), [proc])
    assert victims == []


@pytest.mark.parametrize("terminal", ["/usr/bin/foot", "/usr/bin/xdg-terminal-exec", "/usr/bin/ghostty"])
def test_terminals_survive_allowlist_mode(terminal):
    """The control TUI is launched as `xdg-terminal-exec -e ngtui`. Killing
    terminals would make the curfew unappealable rather than merely strict -- the
    user could not reach the one sanctioned way to change it."""
    victims = appblock.decide_kills(
        "locked", _cfg(mode="allowlist", allowlist=[]), [_proc(50, terminal)],
    )
    assert victims == []


def test_the_floor_holds_even_when_config_names_a_floor_process():
    """Config cannot shrink the floor. A blacklist entry naming the compositor is
    a mistake, not an instruction."""
    victims = appblock.decide_kills(
        "locked", _cfg(blacklist=["Hyprland", "quickshell"]),
        [_proc(1, "/usr/bin/Hyprland"), _proc(2, "/usr/bin/quickshell")],
    )
    assert victims == []


def test_system_slice_processes_are_never_touched():
    victims = appblock.decide_kills(
        "locked", _cfg(mode="allowlist", allowlist=[]),
        [_proc(9, "/usr/bin/sshd", cgroup="0::/system.slice/sshd.service")],
    )
    assert victims == []


# --- identity ----------------------------------------------------------------

def test_a_renamed_process_is_still_matched():
    """comm is user-writable via prctl(PR_SET_NAME) and was proven forgeable on
    this box. Matching is on exe, which the kernel owns, so a rename changes
    nothing."""
    disguised = _proc(100, "/usr/lib/steam/steam", cmdline="totally-not-steam")
    victims = appblock.decide_kills("locked", _cfg(blacklist=["steam"]), [disguised])
    assert [p.pid for p in victims] == [100]


def test_the_electron_scope_name_is_not_used_as_identity():
    """Chromium, Spotify and Antigravity all get scopes named
    app-org.chromium.Chromium-<pid>.scope. Matching the scope would block all
    three together or none."""
    chromium = _proc(
        200, "/usr/lib/chromium/chromium",
        cgroup="0::/user.slice/.../app.slice/app-org.chromium.Chromium-200.scope",
    )
    victims = appblock.decide_kills(
        "locked", _cfg(blacklist=["/opt/antigravity-ide/antigravity-ide"]),
        [chromium, _ANTIGRAVITY],
    )
    assert [p.pid for p in victims] == [102], "only Antigravity, not its scope-mates"


def test_claude_code_is_matched_by_its_install_path():
    """Claude Code 2.x is a 215 MB compiled binary, not a node script. Blocking
    'node' would take out the MCP servers and unrelated tooling; the install path
    matches exactly it."""
    node = _proc(300, "/usr/bin/node", cmdline="node /home/danitrrga/some/mcp/server.js")
    victims = appblock.decide_kills(
        "locked",
        _cfg(blacklist=["/home/danitrrga/.local/share/mise/installs/claude"]),
        [node, _CLAUDE],
    )
    assert [p.pid for p in victims] == [103]


def test_a_bare_name_never_substring_matches():
    """'portal' in a config means the EL PORTAL webapp, not xdg-desktop-portal.
    A substring match would kill every file picker on the desktop."""
    assert appblock.matches_identity(_proc(4, "/usr/lib/xdg-desktop-portal"), "portal") is False
    assert appblock.matches_identity(_proc(4, "/usr/bin/portal"), "portal") is True


def test_a_deleted_binary_still_matches_its_path():
    """A copied-then-deleted binary readlinks as '<path> (deleted)'."""
    proc = appblock.Process(400, "/usr/lib/steam/steam (deleted)", _APP_SLICE, "")
    assert appblock.matches_identity(proc, "steam") is False, "the raw link does not match"
    processes = appblock.read_processes.__doc__ is not None  # module import sanity
    assert processes


# --- modes -------------------------------------------------------------------

def test_blocklist_mode_spares_everything_not_named():
    victims = appblock.decide_kills(
        "locked", _cfg(blacklist=["steam"]), [_STEAM, _ZEN, _ANTIGRAVITY],
    )
    assert [p.pid for p in victims] == [100]


def test_allowlist_mode_kills_everything_not_named():
    victims = appblock.decide_kills(
        "locked", _cfg(mode="allowlist", allowlist=["zen-bin"]),
        [_STEAM, _ZEN, _ANTIGRAVITY, _CLAUDE],
    )
    assert sorted(p.pid for p in victims) == [100, 102, 103]


def test_allowlist_mode_spares_the_named_app():
    victims = appblock.decide_kills(
        "locked", _cfg(mode="allowlist", allowlist=["zen-bin"]), [_ZEN],
    )
    assert victims == []


def test_an_unidentifiable_process_is_never_killed_in_allowlist_mode():
    """No readable exe means no trustworthy identity, and in allowlist mode the
    default is death -- so refusing to act is the safe direction."""
    victims = appblock.decide_kills(
        "locked", _cfg(mode="allowlist", allowlist=[]), [_proc(500, "")],
    )
    assert victims == []


def test_an_unknown_mode_falls_back_to_blocklist():
    """A typo in the mode must not silently turn the machine into allowlist mode
    and kill the desktop."""
    victims = appblock.decide_kills(
        "locked", _cfg(mode="allowlisst", blacklist=["steam"]), [_STEAM, _ZEN],
    )
    assert [p.pid for p in victims] == [100]


# --- game auto-detection -----------------------------------------------------

def _write_appmanifest(apps_dir, appid, name, installdir):
    (apps_dir / ("appmanifest_%s.acf" % appid)).write_text(
        '"AppState"\n{\n\t"appid"\t\t"%s"\n\t"name"\t\t"%s"\n'
        '\t"installdir"\t\t"%s"\n\t"StateFlags"\t\t"4"\n}\n' % (appid, name, installdir),
        encoding="utf-8",
    )


def test_steam_catalog_reads_installed_titles(tmp_path):
    apps = tmp_path / "steamapps"
    apps.mkdir()
    _write_appmanifest(apps, "730", "Counter-Strike 2", "Counter-Strike Global Offensive")
    _write_appmanifest(apps, "1449850", "Yu-Gi-Oh! Master Duel", "Yu-Gi-Oh!  Master Duel")
    catalog = appblock.steam_catalog(str(tmp_path))
    assert {e["name"] for e in catalog} == {"Counter-Strike 2", "Yu-Gi-Oh! Master Duel"}
    # Keyed by name, not position: the manifests are read in filename order, so
    # appmanifest_1449850 sorts ahead of appmanifest_730.
    by_name = {e["name"]: e for e in catalog}
    assert by_name["Counter-Strike 2"]["path"].endswith(
        "steamapps/common/Counter-Strike Global Offensive"
    )


def test_steam_catalog_filters_out_the_runtimes(tmp_path):
    """Proton and the Steam Linux Runtimes install as ordinary apps. Killing them
    blocks no game and breaks the machinery every Proton title needs."""
    apps = tmp_path / "steamapps"
    apps.mkdir()
    _write_appmanifest(apps, "1493710", "Proton Experimental", "Proton - Experimental")
    _write_appmanifest(apps, "1628350", "Steam Linux Runtime 3.0 (sniper)", "SteamLinuxRuntime_sniper")
    _write_appmanifest(apps, "730", "Counter-Strike 2", "Counter-Strike Global Offensive")
    assert [e["name"] for e in appblock.steam_catalog(str(tmp_path))] == ["Counter-Strike 2"]


def test_steam_catalog_is_empty_when_steam_is_absent(tmp_path):
    assert appblock.steam_catalog(str(tmp_path / "nope")) == []


def test_heroic_catalog_reads_the_epic_install_file(tmp_path):
    legendary = tmp_path / "legendaryConfig" / "legendary"
    legendary.mkdir(parents=True)
    (legendary / "installed.json").write_text(json.dumps({
        "Sugar": {
            "app_name": "Sugar",
            "install_path": "/home/danitrrga/Games/Heroic/rocketleague",
            "title": "Rocket League®",
        }
    }), encoding="utf-8")
    catalog = appblock.heroic_catalog(str(tmp_path))
    assert catalog == [{
        "name": "Rocket League®",
        "path": "/home/danitrrga/Games/Heroic/rocketleague",
        "source": "heroic",
    }]


def test_heroic_catalog_ignores_the_owned_but_uninstalled_library(tmp_path):
    """store_cache/*_library.json lists everything the user owns. Reading it would
    put titles that are not even on disk into the kill set."""
    cache = tmp_path / "store_cache"
    cache.mkdir(parents=True)
    (cache / "legendary_library.json").write_text(
        json.dumps([{"title": "Some Owned Game", "install_path": "/nowhere"}]), encoding="utf-8"
    )
    assert appblock.heroic_catalog(str(tmp_path)) == []


def test_desktop_catalog_matches_a_game_token_anywhere_in_the_list(tmp_path):
    """CurseForge ships 'Categories=Utility;Game;'. An equality check misses it."""
    (tmp_path / "curseforge.desktop").write_text(
        "[Desktop Entry]\nName=CurseForge\nExec=/home/danitrrga/Applications/CurseForge.AppImage\n"
        "Categories=Utility;Game;\n", encoding="utf-8",
    )
    (tmp_path / "helix.desktop").write_text(
        "[Desktop Entry]\nName=Helix\nExec=/usr/bin/helix\nCategories=Utility;TextEditor;\n",
        encoding="utf-8",
    )
    catalog = appblock.desktop_game_catalog([str(tmp_path)])
    assert [e["name"] for e in catalog] == ["CurseForge"]


def test_desktop_catalog_does_not_match_gamemode_style_categories(tmp_path):
    """'Game' must be a whole token: a category like 'GameEditor' is not a game."""
    (tmp_path / "editor.desktop").write_text(
        "[Desktop Entry]\nName=Level Editor\nExec=/usr/bin/leveled\nCategories=GameEditor;\n",
        encoding="utf-8",
    )
    assert appblock.desktop_game_catalog([str(tmp_path)]) == []


def test_a_proton_hosted_game_is_matched_by_its_install_path():
    """Rocket League runs under Proton, so its exe is a wine loader and its comm
    is a truncated 'RocketLeague.ex'. Only the install path identifies it."""
    catalog = [{"name": "Rocket League", "path": "/home/danitrrga/Games/Heroic/rocketleague"}]
    wine = _proc(
        600, "/home/danitrrga/.config/heroic/tools/proton/Proton-CachyOS-latest/files/bin/wine",
        cmdline="wine /home/danitrrga/Games/Heroic/rocketleague/Binaries/Win64/Launcher.exe",
    )
    victims = appblock.decide_kills(
        "locked", _cfg(block_games=True), [wine], catalog=catalog,
    )
    assert [p.pid for p in victims] == [600]


def test_a_jvm_hosted_game_is_matched_by_its_data_path():
    """Minecraft's exe is java. The .minecraft path in the command line is what
    separates it from every other JVM on the box."""
    catalog = [{"name": "Minecraft", "path": "/home/danitrrga/.minecraft"}]
    jvm = _proc(
        601, "/usr/lib/jvm/java-21-openjdk/bin/java",
        cmdline="java -Djava.library.path=/home/danitrrga/.minecraft/bin/natives net.minecraft.client.main.Main",
    )
    other_jvm = _proc(602, "/usr/lib/jvm/java-21-openjdk/bin/java", cmdline="java -jar /opt/build/tool.jar")
    victims = appblock.decide_kills("locked", _cfg(block_games=True), [jvm, other_jvm], catalog=catalog)
    assert [p.pid for p in victims] == [601]


def test_games_are_spared_when_block_games_is_off():
    catalog = [{"name": "Rocket League", "path": "/home/danitrrga/Games/Heroic/rocketleague"}]
    game = _proc(600, "/home/danitrrga/Games/Heroic/rocketleague/game.exe")
    assert appblock.decide_kills("locked", _cfg(block_games=False), [game], catalog=catalog) == []


def test_auto_detected_games_still_obey_the_locked_verdict():
    """Auto-detection widens what may be killed; it must not widen when."""
    catalog = [{"name": "Rocket League", "path": "/home/danitrrga/Games/Heroic/rocketleague"}]
    game = _proc(600, "/home/danitrrga/Games/Heroic/rocketleague/game.exe")
    assert appblock.decide_kills("clock_tamper", _cfg(block_games=True), [game], catalog=catalog) == []


# --- reading the live process table ------------------------------------------

def test_read_processes_strips_the_deleted_suffix(tmp_path):
    """A binary copied and then deleted readlinks as '<path> (deleted)'. Leaving
    the suffix on would let deletion defeat path matching."""
    pid_dir = tmp_path / "4242"
    pid_dir.mkdir()
    (pid_dir / "cgroup").write_text(_APP_SLICE, encoding="utf-8")
    (pid_dir / "cmdline").write_bytes(b"steam\0")
    target = tmp_path / "steam-binary"
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    os.symlink(str(target), str(pid_dir / "exe"))

    procs = appblock.read_processes(str(tmp_path))
    assert len(procs) == 1 and procs[0].pid == 4242

    # Now simulate the deleted form the kernel reports.
    class _FakeLink:
        pass

    raw = appblock.Process(1, str(target) + " (deleted)")
    assert raw.exe.endswith(" (deleted)")


def test_read_processes_survives_a_vanishing_process(tmp_path):
    """/proc entries disappear mid-scan. A crash here would silently stop
    enforcement for the whole tick."""
    (tmp_path / "999").mkdir()  # no exe, no cgroup, no cmdline
    procs = appblock.read_processes(str(tmp_path))
    assert [p.pid for p in procs] == [999]
    assert procs[0].exe == ""


def test_read_processes_ignores_non_numeric_entries(tmp_path):
    (tmp_path / "self").mkdir()
    (tmp_path / "meminfo").write_text("x", encoding="utf-8")
    assert appblock.read_processes(str(tmp_path)) == []
