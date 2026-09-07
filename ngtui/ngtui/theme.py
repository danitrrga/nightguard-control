"""theme.py — live omarchy desktop theme → Textual ``Theme`` + change detector.

The TUI is **omarchy-native** (D-02): it does not own a brand palette (the Windows
"Moonlit Indigo" hexes are superseded). Colours are sourced from the live desktop
theme at ``~/.config/omarchy/current/theme/colors.toml`` and parsed into a Textual
``Theme`` (D-04). The running TUI repaints when the desktop theme changes (D-05) —
``ThemeWatch`` is the stdlib mtime-poll primitive driven from the app's 1s tick.

Pure module: imports only ``tomllib`` (stdlib) and ``textual.theme.Theme`` so the
loader and watcher are unit-testable headless (no App, no TTY).

Role map (RESEARCH Pattern 4, schema verified on this box / everforest):
    accent      -> Theme.primary + Theme.accent
    background  -> Theme.background
    foreground  -> Theme.foreground
    color0      -> Theme.surface   (fallback: background)
    color1      -> Theme.error     color2 -> Theme.success   color3 -> Theme.warning

If ``colors.toml`` is absent (some themes ship only ``alacritty.toml`` until
``omarchy-theme-set`` generates one — Pitfall 6) the loader falls back to
``alacritty.toml`` (``[colors.primary]`` + ``[colors.normal]``). On total failure
the caller keeps Textual's default theme rather than crashing (T-10-07, cosmetic).
"""
from __future__ import annotations

import os
import tomllib

from textual.theme import Theme

# Live omarchy theme directories, newest layout first. Omarchy 4 moved the staged
# theme out of ~/.config into ~/.local/state; on a v4 box the old path does not
# exist at all, so a loader pinned to it silently falls through to Textual's
# default theme and the TUI stops matching the desktop. Both are probed so the
# same build works either side of that move.
OMARCHY_THEME_DIRS = (
    "~/.local/state/omarchy/current/theme",  # Omarchy 4
    "~/.config/omarchy/current/theme",       # Omarchy 3 and earlier
)


def theme_dir() -> str | None:
    """The live theme directory, or None when omarchy is not installed.

    Resolved on every call rather than cached at import: omarchy replaces
    ``current/theme`` wholesale on a theme change, and an upgrade can move the
    whole tree between the two locations under a running TUI.
    """
    for candidate in OMARCHY_THEME_DIRS:
        expanded = os.path.expanduser(candidate)
        if os.path.isdir(expanded):
            return expanded
    return None


def colors_path() -> str:
    """Path to the live ``colors.toml`` (the newest layout when none exists)."""
    directory = theme_dir() or os.path.expanduser(OMARCHY_THEME_DIRS[0])
    return os.path.join(directory, "colors.toml")


def alacritty_path() -> str:
    directory = theme_dir() or os.path.expanduser(OMARCHY_THEME_DIRS[0])
    return os.path.join(directory, "alacritty.toml")


def _theme_from_colors(c: dict) -> Theme:
    """Build the omarchy ``Theme`` from a parsed ``colors.toml`` dict."""
    return Theme(
        name="omarchy",
        primary=c["accent"],
        background=c["background"],
        foreground=c["foreground"],
        surface=c.get("color0", c["background"]),
        accent=c["accent"],
        success=c.get("color2", c["accent"]),
        warning=c.get("color3", c["accent"]),
        error=c.get("color1", c["accent"]),
        dark=True,
    )


def _theme_from_alacritty(a: dict) -> Theme:
    """Fallback: build the omarchy ``Theme`` from a parsed ``alacritty.toml`` dict.

    Maps the same roles: ``[colors.primary]`` background/foreground and
    ``[colors.normal]`` red/green/yellow (color1/2/3 analogues). The accent role has
    no direct alacritty key, so it borrows ``[colors.normal].blue`` (color4 ==
    omarchy ``accent`` on this box) and finally foreground as a last resort.
    """
    primary = a.get("colors", {}).get("primary", {})
    normal = a.get("colors", {}).get("normal", {})
    foreground = primary.get("foreground", "#d3c6aa")
    background = primary.get("background", "#000000")
    accent = normal.get("blue", foreground)
    # Reuse _theme_from_colors so the role mapping lives in exactly one place.
    return _theme_from_colors(
        {
            "accent": accent,
            "background": background,
            "foreground": foreground,
            "color0": background,
            "color1": normal.get("red", accent),
            "color2": normal.get("green", accent),
            "color3": normal.get("yellow", accent),
        }
    )


def load_omarchy_theme(path: str | None = None) -> Theme:
    """Parse the live omarchy theme into a Textual ``Theme`` named ``"omarchy"``.

    ``path`` overrides the default ``colors.toml`` location (tests pass a fixture).
    When ``colors.toml`` is absent, falls back to ``alacritty.toml`` in the same
    directory (Pitfall 6). Both formats are TOML.
    """
    resolved = path if path is not None else colors_path()
    try:
        with open(resolved, "rb") as fh:
            return _theme_from_colors(tomllib.load(fh))
    except (FileNotFoundError, IsADirectoryError, tomllib.TOMLDecodeError, KeyError):
        # Missing OR malformed (partial write during an atomic dir-swap, Pitfall 6)
        # OR missing a required colour key — fall back to alacritty.toml.
        pass

    # Fall back to alacritty.toml next to the (missing) colors.toml. A malformed
    # alacritty.toml raises TOMLDecodeError here; let it propagate so the app-level
    # handler keeps Textual's default theme rather than crashing (T-10-07).
    fallback = (
        alacritty_path()
        if path is None
        else os.path.join(os.path.dirname(resolved), "alacritty.toml")
    )
    with open(fallback, "rb") as fh:
        return _theme_from_alacritty(tomllib.load(fh))


class ThemeWatch:
    """Live-watch primitive for D-05 repaint-on-theme-change (stdlib mtime poll).

    Stores the last-seen mtime of the watched ``colors.toml`` (0 on ``OSError``,
    e.g. file absent). ``changed()`` re-stats and returns ``True`` iff the mtime
    differs from the stored value, updating the stored mtime so each change fires
    exactly once. Driven from the app's existing 1s tick — no new dependency.
    """

    def __init__(self, path: str | None = None) -> None:
        self._fixed_path = path
        self._mtime = self._stat()

    @property
    def path(self) -> str:
        """Re-resolved on every read, so a theme change that also moves the
        directory (an omarchy 3 to 4 upgrade under a running TUI) is still seen.
        An mtime poll by path is what makes that safe: unlike an inotify watch on
        the inner file, re-stat'ing follows the directory omarchy swapped in."""
        return self._fixed_path if self._fixed_path is not None else colors_path()

    def _stat(self) -> float:
        try:
            return os.stat(self.path).st_mtime
        except OSError:
            return 0.0

    def changed(self) -> bool:
        m = self._stat()
        if m != self._mtime:
            self._mtime = m
            return True
        return False
