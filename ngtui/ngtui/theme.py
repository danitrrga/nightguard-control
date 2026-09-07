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


def raw_tokens() -> dict:
    """The live theme's colour tokens, straight from ``colors.toml``.

    Separate from ``load_omarchy_theme`` because the desktop panel needs the
    values without Textual: the panel path is head-less and must not pay a UI
    framework's import cost to learn what colour the accent is. Returns {} when
    the theme cannot be read, so the caller can fall back rather than crash.
    """
    try:
        with open(colors_path(), "rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def shell_path() -> str:
    """Path to the live ``shell.toml`` (Omarchy 4's surface/style tokens)."""
    directory = theme_dir() or os.path.expanduser(OMARCHY_THEME_DIRS[0])
    return os.path.join(directory, "shell.toml")


def raw_shell() -> dict:
    """The live ``shell.toml``, or {} when absent (an Omarchy 3 box has none)."""
    try:
        with open(shell_path(), "rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


# Omarchy's own defaults, from shell/Commons/Style.qml. Used per-token when the
# theme does not pin a value, so a partial shell.toml loses one token rather than
# the whole style.
STYLE_DEFAULTS = {
    "popup_background": "#2d353b",
    "popup_text": "#d3c6aa",
    "popup_border": "#7fbbb3",
    "control_border": "#d3c6aa",
    "control_fill_alpha": 0.04,
    "control_border_alpha": 0.4,
    "control_border_width": 1,
    "font_base": 12,
    "spacing_scale": 1.0,
    "spacing_scale_with_font": True,
}


def _resolve_border(value, hyprland):
    """Resolve a border token, which may name a Hyprland-derived colour.

    shell.toml writes ``border = "hyprland.active-border"`` rather than a hex
    value, so popups stay aligned with the compositor's active-window border as
    the theme changes. A gradient string is rejected here: the panel paints a
    solid border and half a gradient is worse than the fallback.
    """
    text = str(value or "").strip()
    if text.startswith("hyprland."):
        text = str((hyprland or {}).get(text[len("hyprland."):], "") or "").strip()
    if text.startswith("#") and len(text) in (4, 7, 9):
        return text
    return None


NAME_PATH = "~/.local/state/omarchy/current/theme.name"


def theme_name() -> str:
    """The active theme's name, or "" when it cannot be read.

    Lives OUTSIDE ``current/theme``, which omarchy replaces wholesale on every
    theme change — so this path is stable and is rewritten on each switch. That
    makes it the one reliable change signal: a watch on it survives the directory
    swap that silently drops a watch on anything inside.
    """
    try:
        with open(os.path.expanduser(NAME_PATH), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def theme_mode(tokens=None) -> str:
    """"light" or "dark", as the theme declares itself.

    Five of the installed themes are light. The panel does not derive colours
    from this — it takes Omarchy's own generated surface tokens, which already
    carry the right contrast either way — but a consumer that wants to know
    which way round the world is should not have to guess from a hex value.
    """
    tokens = raw_tokens() if tokens is None else tokens
    return "light" if str((tokens or {}).get("mode", "")).strip().lower() == "light" else "dark"


def omarchy_style() -> dict:
    """The structural tokens Omarchy's own popups are built from.

    Colour alone was not enough to make a third-party panel look native: the
    corner radius, the border weight, the translucent control fills and the
    spacing/type scale are what actually carry the family resemblance. Reading
    them here rather than hardcoding means a theme change moves the panel too.

    The surface colours are taken from the generated ``[popups]`` section rather
    than derived from the palette, which is what makes light themes work without
    a second code path: omarchy has already decided what text colour reads on
    what background for that theme, in whichever mode, and this inherits that
    decision instead of re-making it.

    When ``shell.toml`` is absent (an Omarchy 3 box, or a half-staged theme) the
    surface tokens fall back to the palette's own background/foreground/accent —
    the same three omarchy generates them from — rather than to a fixed set,
    because a fixed set is a dark theme's set and would invert a light box.

    Corner radius is deliberately absent: it mirrors Hyprland's
    ``decoration:rounding``, which is a live compositor value rather than a
    theme file, so the panel asks hyprctl for it directly.
    """
    shell = raw_shell()
    colors = raw_tokens()
    popups = shell.get("popups") or {}
    controls = shell.get("controls") or shell.get("style") or {}
    hyprland = shell.get("hyprland") or {}
    spacing = shell.get("spacing") or {}
    font = shell.get("font") or {}

    def palette(key):
        value = str((colors or {}).get(key, "") or "").strip()
        return value if value.startswith("#") and len(value) in (4, 7, 9) else None

    # Fall back through the palette before the fixed defaults, so a missing
    # shell.toml still tracks the theme instead of pinning it to a dark one.
    derived = {
        "popup_background": palette("background"),
        "popup_text": palette("foreground"),
        "popup_border": palette("accent"),
        "control_border": palette("foreground"),
    }

    def hexval(section, key, fallback_key):
        value = str(section.get(key, "") or "").strip()
        if value.startswith("#") and len(value) in (4, 7, 9):
            return value
        return derived.get(fallback_key) or STYLE_DEFAULTS[fallback_key]

    def number(section, key, fallback_key):
        try:
            return float(section[key])
        except (KeyError, TypeError, ValueError):
            return STYLE_DEFAULTS[fallback_key]

    return {
        "mode": theme_mode(colors),
        "name": theme_name(),
        "popup_background": hexval(popups, "background", "popup_background"),
        "popup_text": hexval(popups, "text", "popup_text"),
        "popup_border": (_resolve_border(popups.get("border"), hyprland)
                         or derived["popup_border"] or STYLE_DEFAULTS["popup_border"]),
        "popup_background_alpha": number(popups, "background-alpha", "spacing_scale"),
        "control_border": (_resolve_border(controls.get("normal-border"), hyprland)
                           or derived["control_border"] or STYLE_DEFAULTS["control_border"]),
        "control_fill_alpha": number(controls, "normal-fill-alpha", "control_fill_alpha"),
        "control_border_alpha": number(controls, "normal-border-alpha", "control_border_alpha"),
        "control_border_width": int(number(controls, "normal-border-width", "control_border_width")),
        "font_base": int(number(font, "base-size", "font_base")),
        "spacing_scale": number(spacing, "scale", "spacing_scale"),
        "spacing_scale_with_font": bool(
            spacing.get("scale-with-font", STYLE_DEFAULTS["spacing_scale_with_font"])
        ),
    }


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
