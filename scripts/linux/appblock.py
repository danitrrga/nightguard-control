"""Which processes the curfew may end, decided as a pure function.

This is the second attempt at native app blocking. The first shipped in June 2026
and was removed a week later, because a code review found that the clock-tamper
branch was independent of the curfew window: a clock jump at three in the
afternoon made the root watchdog SIGKILL Steam and Discord in broad daylight. The
removal commit is explicit that the point was to stop "a root process from
SIGKILLing user apps on the live 60s tick".

So the design here is split deliberately. Everything that decides is in this
module, is pure, takes the world as arguments, and is tested. The part that
actually signals a process is a thin actuator in the watchdog that does nothing
but carry out a decision made here. The single most important line in the file is
the first branch of ``decide_kills``: nothing is ever killed unless the verdict is
exactly ``locked``.

Three facts about this machine shape the rest:

  * ``comm`` is forgeable. ``prctl(PR_SET_NAME)`` renames a running process to
    anything, and it was proven on this box by renaming a python process to
    ``totally-not-ste`` while ``exe`` and cgroup stayed truthful. Matching is on
    ``exe`` and install-path prefixes, never on ``comm``.
  * The cgroup scope name lies about identity for anything Electron-based.
    Chromium, Antigravity and Spotify all land in scopes named
    ``app-org.chromium.Chromium-<pid>.scope``.
  * Discord, the calendar, the todo list and the portal are all ``--app=`` windows
    of ONE chromium process. Killing that process to block Discord would take the
    allowlist with it, so webapps are not this module's business at all -- they
    are blocked by URL in the root-owned managed browser policy.
"""
from __future__ import annotations

import os
import re

# The verdict that permits any action at all. Deliberately a single string rather
# than "not outside_curfew": clock_tamper and offline_blocked are also not
# "outside_curfew", and treating them as kill-worthy is precisely the bug that
# retired the previous implementation.
LOCKED = "locked"

MODE_BLOCKLIST = "blocklist"
MODE_ALLOWLIST = "allowlist"

# --- the floor ---------------------------------------------------------------
# A hardcoded set that config cannot shrink. In allowlist mode the kill set is
# "everything not explicitly allowed", so a missing entry here does not degrade
# the feature -- it takes down the desktop, and with it the user's only route to
# the sanctioned editor. Read off the live machine under uwsm/Omarchy 4.

# Anything in these cgroup slices is session infrastructure, not an application.
FLOOR_CGROUP_MARKERS = (
    "/session.slice/",
    "/init.scope",
    "/system.slice/",
)

# Must survive even though they live in app.slice, where the naive rule
# "everything in app.slice is an app" would sweep them up.
FLOOR_EXES = frozenset({
    # compositor + shell
    "/usr/bin/Hyprland",
    "/usr/bin/start-hyprland",
    "/usr/bin/Xwayland",
    "/usr/bin/quickshell",          # Omarchy 4's bar AND notifications
    "/usr/bin/uwsm",                # the app launcher itself
    "/usr/bin/hyprsunset",
    # session plumbing
    "/usr/bin/dbus-broker",
    "/usr/bin/dbus-broker-launch",
    "/usr/bin/pipewire",
    "/usr/bin/wireplumber",
    "/usr/bin/gnome-keyring-daemon",  # browsers block without it
    "/usr/lib/dconf-service",
    "/usr/bin/fcitx5",                # input method
    "/usr/bin/wl-paste",
    "/usr/bin/systemd",
    "/usr/lib/systemd/systemd",
})

# Portals and the gvfs family are matched by prefix: their real paths vary by
# distro layout and there are a dozen of them.
FLOOR_EXE_PREFIXES = (
    "/usr/lib/xdg-desktop-portal",
    "/usr/lib/xdg-document-portal",
    "/usr/lib/xdg-permission-store",
    "/usr/lib/at-spi",
    "/usr/lib/gvfs",
    "/usr/lib/gvfsd",
    "/usr/bin/gvfs",
)

# The terminal the sanctioned editor runs inside. Killing terminals in allowlist
# mode would remove the user's ability to reach the control TUI at all -- the
# launcher is `xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui` -- which
# would make the curfew unappealable rather than merely strict.
FLOOR_TERMINAL_EXES = frozenset({
    "/usr/bin/foot",
    "/usr/bin/footclient",
    "/usr/bin/xdg-terminal-exec",
    "/usr/bin/alacritty",
    "/usr/bin/ghostty",
    "/usr/bin/kitty",
})


class Process:
    """The facts about a running process that can be trusted.

    ``comm`` is deliberately absent: it is user-writable and this module must not
    grow a caller that reaches for it.
    """

    __slots__ = ("pid", "exe", "cgroup", "cmdline")

    def __init__(self, pid, exe, cgroup="", cmdline=""):
        self.pid = int(pid)
        self.exe = exe or ""
        self.cgroup = cgroup or ""
        self.cmdline = cmdline or ""

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Process(pid=%d, exe=%r)" % (self.pid, self.exe)

    def __eq__(self, other):
        return (isinstance(other, Process)
                and (self.pid, self.exe, self.cgroup, self.cmdline)
                == (other.pid, other.exe, other.cgroup, other.cmdline))

    def __hash__(self):
        return hash((self.pid, self.exe, self.cgroup, self.cmdline))


def is_floor(proc):
    """True when this process must never be signalled, whatever the config says."""
    for marker in FLOOR_CGROUP_MARKERS:
        if marker in proc.cgroup:
            return True
    if proc.exe in FLOOR_EXES or proc.exe in FLOOR_TERMINAL_EXES:
        return True
    for prefix in FLOOR_EXE_PREFIXES:
        if proc.exe.startswith(prefix):
            return True
    return False


# --- identity ----------------------------------------------------------------

def _basename(path):
    return os.path.basename(path) if path else ""


def matches_identity(proc, identity, catalog=None):
    """Does ``proc`` match one config entry?

    An entry may be an absolute path (matched as an exact exe or a path prefix,
    which is how Proton- and JVM-hosted games are caught), or a bare name
    (matched against the exe basename). A bare name is never substring-matched:
    "portal" would otherwise hit xdg-desktop-portal, and killing that breaks
    every file picker on the desktop while the app the user meant -- a chromium
    webapp called EL PORTAL -- keeps running.
    """
    if not identity:
        return False
    identity = identity.strip()
    if identity.startswith("/"):
        if proc.exe == identity:
            return True
        prefix = identity if identity.endswith("/") else identity + "/"
        if proc.exe.startswith(prefix) or proc.cmdline.find(prefix) >= 0:
            return True
        return False
    if _basename(proc.exe) == identity:
        return True
    # A game named in the catalog resolves to its install path prefix, so
    # "rocket league" in the config still matches a wine process whose exe is
    # the Proton loader.
    if catalog:
        for entry in catalog:
            if entry.get("name", "").lower() == identity.lower():
                if _matches_install_path(proc, entry.get("path")):
                    return True
    return False


def _matches_install_path(proc, path):
    if not path:
        return False
    prefix = path if path.endswith("/") else path + "/"
    return proc.exe.startswith(prefix) or prefix in proc.cmdline


def matches_any(proc, identities, catalog=None):
    return any(matches_identity(proc, i, catalog) for i in (identities or []))


def matches_catalog(proc, catalog):
    """True when the process belongs to an auto-detected game install."""
    for entry in catalog or []:
        if _matches_install_path(proc, entry.get("path")):
            return True
        launcher = entry.get("exe")
        if launcher and proc.exe == launcher:
            return True
    return False


# --- the decision ------------------------------------------------------------

def _native_cfg(cfg):
    blocking = (cfg or {}).get("blocking") or {}
    native = blocking.get("native_apps") or {}
    return native


def decide_kills(verdict, cfg, processes, catalog=None):
    """The processes the curfew may end right now.

    ``verdict`` is the guard's own live verdict string. Anything other than
    ``locked`` returns an empty set, including ``clock_tamper`` and
    ``offline_blocked``: a clock that cannot be trusted is a reason to refuse
    changes, never a reason to start killing the user's applications at three in
    the afternoon. That distinction is the entire reason the previous
    implementation was reverted.
    """
    if verdict != LOCKED:
        return []
    native = _native_cfg(cfg)
    if not native.get("enabled"):
        return []

    mode = (native.get("mode") or MODE_BLOCKLIST).strip().lower()
    catalog = catalog or []
    block_games = bool(native.get("block_games"))

    victims = []
    for proc in processes:
        if is_floor(proc):
            continue
        if not proc.exe:
            # No readable exe means no trustworthy identity. In blocklist mode
            # that is simply no match; in allowlist mode, refusing to kill what
            # cannot be identified is the safe direction.
            continue
        if mode == MODE_ALLOWLIST:
            if matches_any(proc, native.get("allowlist"), catalog):
                continue
            victims.append(proc)
        else:
            if matches_any(proc, native.get("blacklist"), catalog):
                victims.append(proc)
            elif block_games and matches_catalog(proc, catalog):
                victims.append(proc)
    return victims


# --- game auto-detection -----------------------------------------------------
# Every source below is a file owned by the user, so a determined 2am edit can
# make a game vanish from the catalog. That is why the launchers themselves
# (steam, heroic, minecraft-launcher) belong in the signed blacklist, which lives
# in the root-owned sanctioned config: auto-detection is a convenience so newly
# installed titles are covered without an edit, not a control in its own right.

# Steam installs its runtimes as ordinary apps. Blocking them achieves nothing and
# would kill the machinery every Proton title needs. Both fields are checked: the
# display name and the install directory disagree ("Steam Linux Runtime 3.0
# (sniper)" installs into "SteamLinuxRuntime_sniper"), and the install directory
# is the more stable of the two because Valve renames the display strings.
STEAM_NON_GAME_NAMES = ("Proton", "Steam Linux Runtime", "SteamLinuxRuntime", "Steamworks Shared")
STEAM_NON_GAME_DIRS = ("Proton", "SteamLinuxRuntime", "SteamworksShared")


def _acf_field(text, field):
    match = re.search(r'"%s"\s+"([^"]*)"' % re.escape(field), text)
    return match.group(1) if match else None


def steam_catalog(steam_root):
    """Installed Steam titles as ``{name, path}`` from the appmanifest files.

    The install directory, not the app id, is what survives contact with
    reality: a Proton-hosted game's exe is the wine loader, so the identifier
    that works is the path prefix the game lives under.
    """
    out = []
    apps_dir = os.path.join(steam_root, "steamapps")
    try:
        names = sorted(os.listdir(apps_dir))
    except OSError:
        return out
    for name in names:
        if not (name.startswith("appmanifest_") and name.endswith(".acf")):
            continue
        try:
            with open(os.path.join(apps_dir, name), encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        title = _acf_field(text, "name")
        installdir = _acf_field(text, "installdir")
        if not title or not installdir:
            continue
        if any(title.startswith(prefix) for prefix in STEAM_NON_GAME_NAMES):
            continue
        if any(installdir.startswith(prefix) for prefix in STEAM_NON_GAME_DIRS):
            continue
        out.append({
            "name": title,
            "path": os.path.join(apps_dir, "common", installdir),
            "source": "steam",
        })
    return out


def heroic_catalog(heroic_config_root):
    """Installed Heroic titles from each store's ``installed.json``.

    Only the per-store installed files are read. The ``store_cache`` library
    files list everything the user *owns*, which would put uninstalled titles in
    the kill set for no reason.
    """
    import json

    out = []
    candidates = (
        os.path.join(heroic_config_root, "legendaryConfig", "legendary", "installed.json"),
        os.path.join(heroic_config_root, "gog_store", "installed.json"),
        os.path.join(heroic_config_root, "nile_config", "nile", "installed.json"),
        os.path.join(heroic_config_root, "sideload_apps", "library.json"),
    )
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        entries = data.values() if isinstance(data, dict) else data
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            install_path = entry.get("install_path") or entry.get("install", {}).get("install_path")
            title = entry.get("title") or entry.get("app_name")
            if install_path and title:
                out.append({"name": title, "path": install_path, "source": "heroic"})
    return out


def desktop_game_catalog(app_dirs):
    """Launchers whose desktop entry declares itself a game.

    ``Categories`` is a semicolon list and the token can sit anywhere in it --
    CurseForge ships ``Utility;Game;`` -- so an equality check would miss it.
    """
    out = []
    for directory in app_dirs:
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            continue
        for name in names:
            if not name.endswith(".desktop"):
                continue
            try:
                with open(os.path.join(directory, name), encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            categories = ""
            exec_line = ""
            title = ""
            for line in text.splitlines():
                if line.startswith("Categories=") and not categories:
                    categories = line.split("=", 1)[1]
                elif line.startswith("Exec=") and not exec_line:
                    exec_line = line.split("=", 1)[1]
                elif line.startswith("Name=") and not title:
                    title = line.split("=", 1)[1]
            if "Game" not in [c.strip() for c in categories.split(";")]:
                continue
            binary = exec_line.split()[0] if exec_line else ""
            out.append({
                "name": title or name[:-len(".desktop")],
                "path": None,
                "exe": binary if binary.startswith("/") else None,
                "source": "desktop",
            })
    return out


def build_catalog(home):
    """Every auto-detected game on this machine, from all three sources."""
    catalog = []
    catalog += steam_catalog(os.path.join(home, ".local", "share", "Steam"))
    catalog += heroic_catalog(os.path.join(home, ".config", "heroic"))
    catalog += desktop_game_catalog([
        "/usr/share/applications",
        os.path.join(home, ".local", "share", "applications"),
    ])
    return catalog


# --- reading the live process table ------------------------------------------

def read_processes(proc_root="/proc"):
    """Every process, described only by fields the user cannot forge."""
    out = []
    try:
        names = os.listdir(proc_root)
    except OSError:
        return out
    for name in names:
        if not name.isdigit():
            continue
        base = os.path.join(proc_root, name)
        try:
            exe = os.readlink(os.path.join(base, "exe"))
        except OSError:
            exe = ""
        try:
            with open(os.path.join(base, "cgroup"), encoding="utf-8", errors="replace") as fh:
                cgroup = fh.read().strip()
        except OSError:
            cgroup = ""
        try:
            with open(os.path.join(base, "cmdline"), "rb") as fh:
                cmdline = fh.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            cmdline = ""
        # A deleted binary readlinks as "/path/to/exe (deleted)" -- strip the
        # suffix so copying-then-deleting does not defeat path matching.
        if exe.endswith(" (deleted)"):
            exe = exe[: -len(" (deleted)")]
        out.append(Process(int(name), exe, cgroup, cmdline))
    return out
