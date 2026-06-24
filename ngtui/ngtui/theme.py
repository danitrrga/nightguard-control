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

# Live omarchy theme files. omarchy atomically dir-swaps ``current/theme`` on every
# theme change, so the new ``colors.toml`` carries a fresh mtime — an mtime poll on
# this exact path catches the swap (RESEARCH "Detecting a theme change").
OMARCHY_COLORS = os.path.expanduser("~/.config/omarchy/current/theme/colors.toml")
OMARCHY_ALACRITTY = os.path.expanduser(
    "~/.config/omarchy/current/theme/alacritty.toml"
)


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
    colors_path = path if path is not None else OMARCHY_COLORS
    try:
        with open(colors_path, "rb") as fh:
            return _theme_from_colors(tomllib.load(fh))
    except (FileNotFoundError, IsADirectoryError):
        pass

    # Fall back to alacritty.toml next to the (missing) colors.toml.
    alacritty_path = (
        OMARCHY_ALACRITTY
        if path is None
        else os.path.join(os.path.dirname(colors_path), "alacritty.toml")
    )
    with open(alacritty_path, "rb") as fh:
        return _theme_from_alacritty(tomllib.load(fh))


class ThemeWatch:
    """Live-watch primitive for D-05 repaint-on-theme-change (stdlib mtime poll).

    Stores the last-seen mtime of the watched ``colors.toml`` (0 on ``OSError``,
    e.g. file absent). ``changed()`` re-stats and returns ``True`` iff the mtime
    differs from the stored value, updating the stored mtime so each change fires
    exactly once. Driven from the app's existing 1s tick — no new dependency.
    """

    def __init__(self, path: str | None = None) -> None:
        self.path = path if path is not None else OMARCHY_COLORS
        self._mtime = self._stat()

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
