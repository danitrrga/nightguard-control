"""Headless tests for theme.py — colors.toml/alacritty.toml → Theme + ThemeWatch.

These import ``ngtui.theme`` only (no App, no TTY, no trust stack). Fixtures are
written to a tmp dir so the role mapping and the fallback/mtime behaviour are
exercised without touching the live omarchy theme.
"""
from __future__ import annotations

import os

from ngtui.theme import ThemeWatch, load_omarchy_theme

# everforest values (today's live illustration only — NOT the contract).
COLORS_TOML = """\
accent = "#7fbbb3"
cursor = "#d3c6aa"
foreground = "#d3c6aa"
background = "#2d353b"

color0 = "#475258"
color1 = "#e67e80"
color2 = "#a7c080"
color3 = "#dbbc7f"
color4 = "#7fbbb3"
"""

ALACRITTY_TOML = """\
[colors.primary]
background = "#2d353b"
foreground = "#d3c6aa"

[colors.normal]
black = "#475258"
red = "#e67e80"
green = "#a7c080"
yellow = "#dbbc7f"
blue = "#7fbbb3"
"""


def _write(path: str, body: str) -> str:
    with open(path, "w") as fh:
        fh.write(body)
    return path


def test_load_colors_toml_maps_roles(tmp_path):
    """colors.toml → Theme named 'omarchy' with the verified role mapping."""
    p = _write(str(tmp_path / "colors.toml"), COLORS_TOML)
    theme = load_omarchy_theme(p)

    assert theme.name == "omarchy"
    # accent drives BOTH primary and accent (reserved accent role).
    assert theme.primary == "#7fbbb3"
    assert theme.accent == "#7fbbb3"
    assert theme.background == "#2d353b"
    assert theme.foreground == "#d3c6aa"
    assert theme.surface == "#475258"  # color0
    assert theme.error == "#e67e80"  # color1
    assert theme.success == "#a7c080"  # color2
    assert theme.warning == "#dbbc7f"  # color3
    assert theme.dark is True


def test_falls_back_to_alacritty_when_colors_absent(tmp_path):
    """colors.toml absent → parse alacritty.toml ([colors.primary]/[colors.normal])."""
    # Only write alacritty.toml; point the loader at the (missing) colors.toml.
    _write(str(tmp_path / "alacritty.toml"), ALACRITTY_TOML)
    missing_colors = str(tmp_path / "colors.toml")
    assert not os.path.exists(missing_colors)

    theme = load_omarchy_theme(missing_colors)

    assert theme.name == "omarchy"
    assert theme.background == "#2d353b"
    assert theme.foreground == "#d3c6aa"
    assert theme.error == "#e67e80"  # normal.red -> color1 -> error
    assert theme.success == "#a7c080"  # normal.green -> color2 -> success
    assert theme.warning == "#dbbc7f"  # normal.yellow -> color3 -> warning
    # accent borrows normal.blue (== omarchy accent/color4 on this box).
    assert theme.accent == "#7fbbb3"


def test_malformed_colors_falls_back_to_alacritty(tmp_path):
    """colors.toml present but malformed (partial write mid-swap) → alacritty fallback.

    Guards CR-01: tomllib raises TOMLDecodeError (a ValueError) on a partial write
    during omarchy's atomic dir-swap; the loader must fall back rather than escape.
    """
    _write(str(tmp_path / "colors.toml"), "accent = \"#7fbbb3\"\nbackground = ")  # truncated
    _write(str(tmp_path / "alacritty.toml"), ALACRITTY_TOML)

    theme = load_omarchy_theme(str(tmp_path / "colors.toml"))

    assert theme.name == "omarchy"
    assert theme.background == "#2d353b"  # came from alacritty fallback
    assert theme.accent == "#7fbbb3"


def test_malformed_alacritty_fallback_raises_for_app_handler(tmp_path):
    """Both files malformed → TOMLDecodeError propagates so the app keeps its default.

    Guards CR-01: the app-level handler catches ValueError (TOMLDecodeError's base)
    and keeps Textual's default theme instead of crashing on_mount.
    """
    import tomllib

    import pytest

    _write(str(tmp_path / "colors.toml"), "background = ")  # truncated
    _write(str(tmp_path / "alacritty.toml"), "[colors.primary\n")  # malformed

    with pytest.raises(tomllib.TOMLDecodeError):
        load_omarchy_theme(str(tmp_path / "colors.toml"))


def test_theme_watch_detects_mtime_change(tmp_path):
    """ThemeWatch.changed() is False on a stable file, True after a rewrite."""
    p = _write(str(tmp_path / "colors.toml"), COLORS_TOML)
    watch = ThemeWatch(p)

    # Unchanged file -> no change.
    assert watch.changed() is False

    # Bump the mtime explicitly (rewriting fast can land on the same second).
    st = os.stat(p)
    os.utime(p, (st.st_atime + 5, st.st_mtime + 5))

    assert watch.changed() is True
    # The change is consumed exactly once.
    assert watch.changed() is False


# --- Omarchy 4 moved the staged theme out of ~/.config -------------------------

def test_theme_dir_prefers_the_omarchy_4_location(tmp_path, monkeypatch):
    """A box running both layouts must read the newer one."""
    from ngtui import theme as theme_mod

    v4 = tmp_path / "state" / "omarchy" / "current" / "theme"
    v3 = tmp_path / "config" / "omarchy" / "current" / "theme"
    v4.mkdir(parents=True)
    v3.mkdir(parents=True)
    monkeypatch.setattr(
        theme_mod, "OMARCHY_THEME_DIRS", (str(v4), str(v3))
    )
    assert theme_mod.theme_dir() == str(v4)


def test_theme_dir_falls_back_to_the_omarchy_3_location(tmp_path, monkeypatch):
    from ngtui import theme as theme_mod

    v4 = tmp_path / "state" / "omarchy" / "current" / "theme"
    v3 = tmp_path / "config" / "omarchy" / "current" / "theme"
    v3.mkdir(parents=True)
    monkeypatch.setattr(theme_mod, "OMARCHY_THEME_DIRS", (str(v4), str(v3)))
    assert theme_mod.theme_dir() == str(v3)


def test_theme_dir_is_none_when_omarchy_is_absent(tmp_path, monkeypatch):
    from ngtui import theme as theme_mod

    monkeypatch.setattr(
        theme_mod, "OMARCHY_THEME_DIRS", (str(tmp_path / "nope"), str(tmp_path / "also-nope"))
    )
    assert theme_mod.theme_dir() is None


def test_the_default_loader_resolves_without_a_name_error(monkeypatch, tmp_path):
    """Regression: the module-level path constants were replaced by functions, and
    a shadowed local kept a reference to the deleted constant. Every test passed
    an explicit path, so the no-argument call — the one the running app makes —
    was the only broken caller."""
    from ngtui import theme as theme_mod

    directory = tmp_path / "theme"
    directory.mkdir()
    (directory / "colors.toml").write_text(
        'background = "#2d353b"\n'
        'foreground = "#d3c6aa"\n'
        'accent = "#7fbbb3"\n'
        'red = "#e67e80"\n'
        'green = "#a7c080"\n'
        'yellow = "#dbbc7f"\n'
        'blue = "#7fbbb3"\n'
        'magenta = "#d699b6"\n'
        'cyan = "#83c092"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(theme_mod, "OMARCHY_THEME_DIRS", (str(directory),))
    assert theme_mod.load_omarchy_theme().name == "omarchy"


def test_the_watch_follows_a_directory_move(tmp_path, monkeypatch):
    """omarchy replaces current/theme wholesale, and an upgrade can move the tree
    between layouts under a running TUI. Re-resolving on each stat is what makes
    the poll survive that; a path frozen at construction would not."""
    from ngtui.theme import ThemeWatch
    from ngtui import theme as theme_mod

    old_dir = tmp_path / "old" / "theme"
    new_dir = tmp_path / "new" / "theme"
    old_dir.mkdir(parents=True)
    monkeypatch.setattr(theme_mod, "OMARCHY_THEME_DIRS", (str(new_dir), str(old_dir)))
    (old_dir / "colors.toml").write_text("background = '#000000'", encoding="utf-8")

    watch = ThemeWatch()
    assert watch.path == str(old_dir / "colors.toml")

    new_dir.mkdir(parents=True)
    (new_dir / "colors.toml").write_text("background = '#111111'", encoding="utf-8")
    assert watch.path == str(new_dir / "colors.toml")
    assert watch.changed() is True
