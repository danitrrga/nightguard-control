"""The Textual role mapping must follow every installed theme, not just ANSI ones.

There was a sweep for the bar panel's mapping (`test_theme_sync.py`) and none for
the Textual one, and that gap is the whole diagnosis: `_theme_from_colors()` knew
only the `color1`/`color2`/`color3` vocabulary, so on the 25 of 27 installed themes
that declare `red`/`green`/`yellow` instead, `error`, `success`, `warning` and
`accent` all resolved to the same colour. LOCKED, OPEN and GRACE painted one hue.
Glyph and word carry the verdict independently, so nothing was unreadable — but the
colour channel, which exists so meaning survives *losing* a channel, was itself the
dead one.

This file is a deliberate mirror of `test_theme_sync.py`, not an inspiration.
`_THEME_ROOTS`, `_installed_themes()` and `_HAVE_THEMES` are copied verbatim,
because a second, divergent idea of what "installed" means is how the first gap
survived. The vacuity guard at the bottom asserts the two agree.

**What this sweep may not assert.** Not that a theme's `surface` role differs from
its ground. Four installed themes legitimately resolve them equal: `last-horizon`
and `solitude` declare a `lighter_background` byte-equal to `background`, and
`city-783` and `dos-moos` resolve through `color0`, which both set equal to
`background`. That measured fact is *why* the control ladder fills with
`$foreground` at 4/8/18/22 % rather than with a `surface` role — an alpha fill over
the ground can never collide with it, whereas a surface role can and does on one
theme in seven.

These tests read the real theme files off disk rather than fixtures, because the
question is "does this work on HIS themes", not "does this work on a theme I
invented".
"""
from __future__ import annotations

import os
import tomllib

import pytest

from ngtui import theme

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

# Every role the pick chains resolve. `panel` is included because this change is
# what introduced it — it was previously never set at all, and a role added
# without a sweep is the exact shape of the bug being fixed.
_PICKED_ROLES = ("error", "success", "warning", "surface", "panel")


def _load(path):
    with open(path, "rb") as fh:
        return tomllib.load(fh)


@_HAVE_THEMES
@pytest.mark.parametrize("name,path", _THEMES, ids=[n for n, _ in _THEMES])
def test_every_installed_theme_resolves_its_roles_from_its_own_palette(name, path):
    """No Textual role may resolve to a colour from outside the theme.

    Provenance, not inequality: comparing against a known default cannot tell
    "fell back" from "this theme happens to use that colour". So every role must
    be a colour the theme itself declares.

    **Measured limit of this assertion, and it is the important part.** In the
    panel sweep this idea copies from, the fallback is `THEME_FALLBACK` — one
    other theme's hexes — so provenance catches it. Here the fallback tail is
    `or accent`, a colour from *this* theme, so provenance **cannot** catch the
    collapse bug: reverting all three verdict chains to ANSI-only leaves this
    test green on 27 of 27 while 25 themes paint one hue. Verified by doing it.
    The distinctness test below is what catches that; this one stands guard over
    a different regression — a hardcoded constant creeping into `theme.py` the
    way one did into `panel.py`.
    """
    tokens = _load(path)
    resolved = theme.load_omarchy_theme(path)

    declared = {str(v).lower() for v in tokens.values() if str(v).startswith("#")}
    for role in _PICKED_ROLES:
        value = getattr(resolved, role)
        assert isinstance(value, str) and value.startswith("#"), (
            "%s.%s is not a colour: %r" % (name, role, value)
        )
        assert value.lower() in declared, (
            "%s.%s is %s, which the theme does not declare — it fell back"
            % (name, role, value)
        )


@_HAVE_THEMES
@pytest.mark.parametrize("name,path", _THEMES, ids=[n for n, _ in _THEMES])
def test_the_three_verdict_roles_are_distinct_in_every_theme(name, path):
    """LOCKED, OPEN and GRACE must not share a hue on any installed theme.

    `accent` is deliberately **not** in this set. `dos-moos` declares
    `accent = "#819890"` and `color2 = "#819890"` — its `color2` *is* its accent,
    by that theme's own design. A four-way distinctness assertion would fail on a
    theme behaving correctly, and a test that cannot pass on a valid theme is a
    broken test rather than a caught bug.
    """
    t = theme.load_omarchy_theme(path)
    assert t.error != t.success, (
        "%s: locked and open share a colour (%s)" % (name, t.error)
    )
    assert t.success != t.warning, (
        "%s: open and grace share a colour (%s)" % (name, t.success)
    )
    assert t.error != t.warning, (
        "%s: locked and grace share a colour (%s)" % (name, t.error)
    )


@_HAVE_THEMES
def test_this_sweep_sees_the_same_themes_the_panel_sweep_sees():
    """Guards the two tests above from passing as a silent no-op.

    A `skipif`-guarded sweep that discovers nothing reports green. Worse, a
    discovery helper that drifts from the panel sweep's would let one mapping be
    swept over 27 themes and the other over 3, with both green. So this asserts
    both that themes were found at all and that the two helpers agree on which.
    """
    import test_theme_sync

    assert _THEMES, "no installed themes discovered — this whole file was vacuous"
    assert _THEMES == test_theme_sync._THEMES, (
        "the two theme sweeps disagree about what is installed: %s vs %s"
        % (sorted(n for n, _ in _THEMES),
           sorted(n for n, _ in test_theme_sync._THEMES))
    )
