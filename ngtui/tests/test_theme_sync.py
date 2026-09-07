"""The panel must follow whatever theme is active — every installed one.

Five of the themes on this box are light, and a light theme inverts what
"lighter background" and "dark foreground" mean. Deriving panel colours from the
palette by hand would need a second code path for that and would drift from the
desktop the first time omarchy changed its mind.

So the panel takes omarchy's own generated surface tokens instead. Those already
encode which text colour reads on which background for that theme, in whichever
mode, and inheriting them is what makes light and dark work without a branch.

These tests run the real theme files off disk rather than fixtures, because the
question they answer is "does this work on HIS themes", not "does this work on a
theme I invented".
"""
from __future__ import annotations

import os
import tomllib

import pytest

from ngtui import panel, theme

_THEME_ROOTS = [
    "/usr/share/omarchy/themes",
    os.path.expanduser("~/.config/omarchy/themes"),
]


def _installed_themes():
    found = []
    for root in _THEME_ROOTS:
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for name in names:
            colors = os.path.join(root, name, "colors.toml")
            if os.path.isfile(colors):
                found.append((name, colors))
    return found


_THEMES = _installed_themes()
_HAVE_THEMES = pytest.mark.skipif(not _THEMES, reason="no omarchy themes installed")


def _load(path):
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def _hex_to_rgb(value):
    v = value.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def _relative_luminance(value):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _hex_to_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _relative_luminance(a), _relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


@_HAVE_THEMES
@pytest.mark.parametrize("name,path", _THEMES, ids=[n for n, _ in _THEMES])
def test_every_installed_theme_maps_to_a_complete_palette(name, path):
    """No role may fall through to a hardcoded colour on a theme that has one."""
    tokens = _load(path)
    view = panel.theme_view(tokens)
    assert set(view) == set(panel.THEME_FALLBACK)

    # Provenance, not inequality: comparing against the built-in defaults cannot
    # tell "fell back" from "this theme happens to use that colour" — the
    # defaults are one real theme's values. Every role must instead be a colour
    # the theme itself declares.
    declared = {str(v).lower() for v in tokens.values() if str(v).startswith("#")}
    for role, value in view.items():
        assert isinstance(value, str) and value.startswith("#"), (
            "%s.%s is not a colour: %r" % (name, role, value)
        )
        assert value.lower() in declared, (
            "%s.%s is %s, which the theme does not declare — it fell back"
            % (name, role, value)
        )


@_HAVE_THEMES
@pytest.mark.parametrize("name,path", _THEMES, ids=[n for n, _ in _THEMES])
def test_text_is_readable_on_its_background_in_every_theme(name, path):
    """The whole reason for inheriting omarchy's tokens rather than deriving.

    A light theme puts near-black text on cream; a dark one puts warm grey on
    slate. Both must clear a legibility floor, and a mapping that quietly picked
    the wrong end of the palette would fail here on exactly one mode.
    """
    view = panel.theme_view(_load(path))
    ratio = _contrast(view["foreground"], view["background"])
    assert ratio >= 4.5, (
        "%s: foreground %s on background %s is %.1f:1, below the 4.5:1 floor"
        % (name, view["foreground"], view["background"], ratio)
    )


@_HAVE_THEMES
@pytest.mark.parametrize("name,path", _THEMES, ids=[n for n, _ in _THEMES])
def test_muted_text_is_dimmer_than_body_text_but_still_visible(name, path):
    """Muted must sit between the body text and the background, in both modes.

    In a dark theme that means lighter than the background; in a light theme it
    means darker than it. Asserting the ordering rather than the direction is
    what makes one rule cover both.
    """
    view = panel.theme_view(_load(path))
    to_bg = _contrast(view["muted"], view["background"])
    body_to_bg = _contrast(view["foreground"], view["background"])
    assert to_bg >= 2.0, (
        "%s: muted %s on %s is only %.1f:1 — invisible"
        % (name, view["muted"], view["background"], to_bg)
    )
    assert to_bg <= body_to_bg, (
        "%s: muted is not dimmer than body text" % name
    )


@_HAVE_THEMES
@pytest.mark.parametrize("name,path", _THEMES, ids=[n for n, _ in _THEMES])
def test_the_state_colours_are_distinguishable_from_each_other(name, path):
    """The verdict is read from a colour before it is read as a word, so locked
    and open must not collapse into the same hue on any theme."""
    view = panel.theme_view(_load(path))
    assert view["ok"] != view["alert"], "%s: open and locked share a colour" % name
    assert view["warn"] != view["alert"], "%s: grace and locked share a colour" % name


@_HAVE_THEMES
def test_both_modes_are_actually_represented_on_this_box():
    """Guards the tests above from passing vacuously on an all-dark machine."""
    modes = {theme.theme_mode(_load(path)) for _name, path in _THEMES}
    assert modes == {"light", "dark"}, (
        "expected both light and dark themes installed, found %s" % modes
    )


# --- the structural tokens ---------------------------------------------------

def test_a_missing_shell_file_falls_back_to_the_palette_not_to_a_dark_theme(
    tmp_path, monkeypatch
):
    """An omarchy 3 box, or a half-staged theme, ships no shell.toml. Pinning the
    surface to fixed values there would render a dark card on a light desktop."""
    directory = tmp_path / "theme"
    directory.mkdir()
    (directory / "colors.toml").write_text(
        'mode = "light"\n'
        'background = "#FFFCF0"\n'
        'foreground = "#100F0F"\n'
        'accent = "#205EA6"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(theme, "OMARCHY_THEME_DIRS", (str(directory),))

    style = theme.omarchy_style()
    assert style["mode"] == "light"
    assert style["popup_background"] == "#FFFCF0", "the card must be light on a light theme"
    assert style["popup_text"] == "#100F0F"
    assert style["popup_border"] == "#205EA6"


def test_a_border_naming_a_compositor_colour_is_resolved(tmp_path, monkeypatch):
    """shell.toml writes `border = "hyprland.active-border"` rather than a hex, so
    popups track the compositor's active-window border as the theme changes."""
    directory = tmp_path / "theme"
    directory.mkdir()
    (directory / "colors.toml").write_text('background = "#000000"\n', encoding="utf-8")
    (directory / "shell.toml").write_text(
        '[hyprland]\nactive-border = "#7fbbb3"\n\n'
        '[popups]\nbackground = "#2d353b"\ntext = "#d3c6aa"\n'
        'border = "hyprland.active-border"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(theme, "OMARCHY_THEME_DIRS", (str(directory),))
    assert theme.omarchy_style()["popup_border"] == "#7fbbb3"


def test_a_gradient_border_is_rejected_rather_than_half_painted(tmp_path, monkeypatch):
    """Borders may be a Hyprland-style gradient. The panel paints a solid border,
    and half a gradient looks worse than the theme's accent."""
    directory = tmp_path / "theme"
    directory.mkdir()
    (directory / "colors.toml").write_text('accent = "#7fbbb3"\n', encoding="utf-8")
    (directory / "shell.toml").write_text(
        '[popups]\nborder = "rgba(11111111) rgba(22222222) 45deg"\n', encoding="utf-8",
    )
    monkeypatch.setattr(theme, "OMARCHY_THEME_DIRS", (str(directory),))
    assert theme.omarchy_style()["popup_border"] == "#7fbbb3"


def test_the_theme_name_is_read_from_outside_the_swapped_directory():
    """omarchy replaces current/theme wholesale on every change, so a watch on
    anything inside it is silently dropped. theme.name is a sibling, rewritten on
    each switch, which makes it the one reliable change signal."""
    assert "current/theme.name" in theme.NAME_PATH
    assert "current/theme/" not in theme.NAME_PATH


def test_the_style_view_keeps_every_key_the_panel_reads():
    live = panel.style_view(theme.omarchy_style())
    assert set(live) == set(panel.STYLE_FALLBACK)
    assert set(panel.UNAVAILABLE["style"]) == set(panel.STYLE_FALLBACK)
