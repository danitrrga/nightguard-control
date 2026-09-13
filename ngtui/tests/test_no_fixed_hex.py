"""No literal colour anywhere in the desktop surface — it all comes from the theme.

The rule behind this outlived the file it was written for. Nightguard does not
own a brand palette: every colour is sourced from the live omarchy theme at
runtime and reaches a control as a role, never as a value. A hex typed into a
stylesheet is invisible in review — it renders, it looks fine on the author's
theme, and it silently stops tracking the desktop on every other one.

It used to scan ``app.tcss`` and the widget modules. Those are gone with the
terminal app, and the surface the rule now protects is the QML: three files
that draw the bar icon, the panel and the workshop, and that a reader is far
more likely to drop a `"#1e1e2e"` into than a Python module was.

The second test is the control demonstrated able to fail: it injects
``#7aa2f7`` — the retired Moonlit Indigo accent, the exact class of value this
ban exists to keep out — into an in-memory copy and asserts the scan catches
it. A scan that has never been seen to find anything is not evidence.
"""
from __future__ import annotations

import glob
import os
import re

_PLUGIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "packaging", "omarchy", "plugins", "danitrrga.nightguard",
)

# A bare `#` followed only by hex letters/digits, 3/4/6/8 long. Nerd Font glyphs
# and Spanish prose are safe; a CSS-style id made entirely of hex letters would
# trip it, which is a trade this test takes on purpose — a false positive costs
# one rename, a false negative costs the whole contract.
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    return re.sub(r"\s//.*$", "", text, flags=re.M)


def _sources():
    paths = sorted(glob.glob(os.path.join(_PLUGIN, "*.qml")))
    assert paths, "no QML found at %s — this scan is pointed at nothing" % _PLUGIN
    out = {}
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            out[path] = fh.read()
    return out


def _offenders(sources):
    found = []
    for path, text in sources.items():
        for index, line in enumerate(_strip_comments(text).split("\n"), start=1):
            for match in _HEX.finditer(line):
                found.append("%s:%d %s" % (os.path.basename(path), index, match.group(0)))
    return found


def test_no_literal_hex_in_any_of_the_plugin_qml():
    sources = _sources()
    # Vacuity guard: a renamed plugin directory would make this pass over nothing.
    assert any(text.strip() for text in sources.values())
    assert any("Color." in text for text in sources.values()), (
        "no file references the theme at all — the scan is looking at the wrong tree"
    )
    offenders = _offenders(sources)
    assert offenders == [], (
        "literal colour in the desktop surface; take it from the theme instead:\n  "
        + "\n  ".join(offenders)
    )


def test_the_scan_catches_an_injected_hex():
    """The control. #7aa2f7 is the retired Moonlit Indigo accent — precisely the
    kind of value that renders fine on one theme and wrongly on the other 26."""
    sources = _sources()
    path = sorted(sources)[0]
    poisoned = dict(sources)
    poisoned[path] = sources[path] + '\n  property color bad: "#7aa2f7"\n'
    offenders = _offenders(poisoned)
    assert any("#7aa2f7" in o for o in offenders), (
        "the scan did not catch an injected literal — it is not evidence of anything"
    )
