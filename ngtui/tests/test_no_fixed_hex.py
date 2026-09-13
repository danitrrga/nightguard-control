"""No literal hex in the stylesheet or in any widget — colour comes from the desktop.

D-12, and UIX-06 behind it: the TUI does not own a brand palette. Every colour is
sourced from the live omarchy theme at runtime and reaches a widget as a ``$``-role
name, never as a value. A hex typed into ``app.tcss`` or a widget module is invisible
in review — it renders, it looks fine on the author's theme, and it silently stops
tracking the desktop on every other one. This test makes it red instead.

The scan lands before any styling work in this phase rather than as an audit at the
end, so it guards every file the phase writes as the file is written.

Caveat, measured rather than assumed: the pattern matches a bare ``#`` followed only by
hex letters, so a CSS id made entirely of them — ``#bad``, ``#face``, ``#decade`` — trips
it. Those ids are therefore forbidden by this test too. That is a deliberate trade: the
alternative is a pattern that understands CSS context, and a false positive on a
pathological id name costs one rename while a false negative costs the whole contract.

The second test is the control demonstrated able to fail: it injects ``#7aa2f7`` (the
retired Moonlit Indigo accent — the exact class of value this ban exists to keep out)
into an in-memory copy and asserts the scan catches it. A scan that has never been seen
to find anything is not evidence.
"""
from __future__ import annotations

import glob
import os
import re

# ngtui/tests/ -> ngtui/ -> ngtui/ngtui/. Two dirname levels, one fewer than
# test_deploy_completeness.py's three, because that test reaches a sibling of the
# repo root and this one reaches a sibling of its own parent. Resolved from
# __file__ so the test works from any cwd.
_PKG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ngtui",
)
_TCSS = os.path.join(_PKG, "app.tcss")
_WIDGETS_GLOB = os.path.join(_PKG, "widgets", "*.py")

# A literal colour: #rgb, #rgba, #rrggbb or #rrggbbaa, not followed by anything
# that would make it a longer word. The trailing look-ahead is what stops the
# pattern from matching the first six characters of a longer identifier.
_HEX = re.compile(
    r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9A-Za-z_-])"
)


def _sources():
    """The stylesheet and every widget module, as (path, text) pairs."""
    paths = [_TCSS] + sorted(glob.glob(_WIDGETS_GLOB))
    out = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            out.append((path, fh.read()))
    return out


def test_no_literal_hex_in_the_stylesheet_or_any_widget():
    """Colour reaches the UI only as a role name fed by the live theme (D-12/UIX-06)."""
    sources = _sources()
    by_path = dict(sources)

    # Vacuity guard first, same job as test_deploy_completeness.py's
    # `assert match, "deploy.sh no longer has the install loop this test reads"`.
    # A scan that reads nothing reports an empty match list and passes for exactly
    # the wrong reason — a renamed stylesheet or a moved widgets package would turn
    # this from a guard into a no-op without a word of output.
    assert _TCSS in by_path, "app.tcss is not where this test looks: %s" % _TCSS
    assert by_path[_TCSS].strip(), "app.tcss is empty — the scan would pass over nothing"
    widget_modules = [p for p, _text in sources if p != _TCSS]
    assert len(widget_modules) >= 3, (
        "expected at least three widget modules under %s, found %s — the glob no "
        "longer reaches the widgets package" % (_WIDGETS_GLOB, widget_modules)
    )

    for path, text in sources:
        found = _HEX.findall(text)
        assert not found, (
            "%s contains literal hex %s — colour must come from the live omarchy "
            "theme as a $role, not from a value typed into the source (D-12/UIX-06)"
            % (os.path.relpath(path, _PKG), found)
        )


def test_the_scan_catches_an_injected_hex():
    """The control, demonstrated able to fail. The file on disk is never written.

    Asserting the exact one-element list (rather than merely "something was found")
    is what couples this to the test above: it can only hold while app.tcss is
    itself hex-free, so the two cannot both pass on a file full of hex.
    """
    with open(_TCSS, encoding="utf-8") as fh:
        clean = fh.read()

    assert _HEX.findall(clean) == []
    injected = clean + "\n#x { color: #7aa2f7; }\n"
    assert _HEX.findall(injected) == ["#7aa2f7"]
