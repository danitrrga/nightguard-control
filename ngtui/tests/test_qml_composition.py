"""The window is four files that must keep agreeing with each other.

Everything here guards a defect that was actually in the tree, not a style
preference. The dial and the reading of the hours each existed twice for a
while; two copies of "how long until the curfew" is how a dropdown and a window
start telling the same person different times.
"""
from __future__ import annotations

import glob
import os
import re

_PLUGIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "packaging", "omarchy", "plugins", "danitrrga.nightguard",
)


def _read(name):
    with open(os.path.join(_PLUGIN, name), encoding="utf-8") as fh:
        return fh.read()


def _every_qml():
    return sorted(glob.glob(os.path.join(_PLUGIN, "*.qml")))


def test_the_dial_is_drawn_by_exactly_one_file():
    """It was an inline `component DayDial` in the dropdown and would have been
    copied into the window. Two rings drawn by two implementations disagree the
    first time either is touched."""
    assert os.path.exists(os.path.join(_PLUGIN, "DayDial.qml"))
    for path in _every_qml():
        text = open(path, encoding="utf-8").read()
        assert "component DayDial" not in text, (
            "%s defines its own dial instead of using DayDial.qml"
            % os.path.basename(path)
        )
    drawers = [os.path.basename(p) for p in _every_qml()
               if "PathAngleArc" in open(p, encoding="utf-8").read()]
    assert drawers == ["DayDial.qml"], (
        "more than one file draws an arc: %s" % drawers
    )


def test_the_hours_are_read_by_exactly_one_file():
    """`humanDuration` and the edit-window sentence are the two places the
    dropdown and the window most easily drift apart, because both are wording
    rather than data."""
    owners = [os.path.basename(p) for p in _every_qml()
              if "function humanDuration" in open(p, encoding="utf-8").read()]
    assert owners == ["NightguardClock.qml"], (
        "the duration wording lives in %s — it belongs in one file" % owners
    )
    for path in _every_qml():
        name = os.path.basename(path)
        if name == "NightguardClock.qml":
            continue
        text = open(path, encoding="utf-8").read()
        assert "quedan \" + humanDuration" not in text, (
            "%s composes the edit-window sentence itself" % name
        )


def test_the_window_lands_on_the_glance():
    """Opening straight into a hundred-row picker answers a question nobody has
    asked yet. It also steals the keyboard for a filter field, which is how a
    window eats the first thing somebody types."""
    workshop = _read("NightguardWorkshop.qml")
    assert re.search(r'property string view:\s*"glance"', workshop), (
        "the window no longer lands on the glance"
    )
    assert "NightguardGlance {" in workshop, "the glance is not mounted"
    focus = re.search(r'if \(root\.view === "apps"\)\s*\n\s*Qt\.callLater', workshop)
    assert focus, (
        "open() focuses the filter field unconditionally — on the glance that "
        "field is not on screen, and the keystroke goes nowhere"
    )


def test_the_glance_never_draws_an_unread_defence_as_switched_off():
    """An older ngtui carries no reading of the watchdog or the clock check. The
    first version of this view rendered that absence as OFF: a red dot and "las
    ediciones a mano se quedan" on a machine whose watchdog was running fine.

    A protection reported as off when it is on is the cheapest way to teach
    somebody to ignore the only colour on the screen that means anything.
    """
    glance = _read("NightguardGlance.qml")
    watchdog_rows = [block for block in glance.split("FactRow {")
                     if "glance.defences.watchdog" in block]
    assert watchdog_rows, "the watchdog row is gone"
    for block in watchdog_rows:
        assert "visible: !!glance.defences" in block, (
            "the watchdog row renders even with no reading, which draws "
            "'not running' over a watchdog that is running"
        )
    assert "No se puede leer el estado de las defensas" in glance, (
        "nothing tells the reader that the absence is an absence"
    )


def test_the_editor_switches_refuse_to_move_before_the_reading_arrives():
    """Same defect, the other surface. The two defence switches defaulted to
    checked, so the schedule view drew both protections ON regardless of what
    the signed config said — and a click then staged a change away from a state
    that was never true."""
    workshop = _read("NightguardWorkshop.qml")
    for key in ("clock_protection.enabled", "watchdog.enabled"):
        match = re.search(
            r'checked: root\.stagedBool\("%s",\s*\n?\s*(.{0,120})' % re.escape(key),
            workshop)
        assert match, "the switch for %s is gone" % key
        assert "true)" not in match.group(1), (
            "the switch for %s still falls back to ON instead of reading the "
            "signed config" % key
        )
    assert workshop.count("enabled: root.defencesRead") == 2, (
        "a defence switch can be clicked before its reading has arrived"
    )


def test_the_window_only_accepts_a_view_it_actually_has():
    """`summon` hands the plugin whatever JSON the caller wrote. A payload that
    named a view the window does not have would leave `view` set to a string no
    branch matches — every pane invisible, an empty window, and nothing in the
    log to say why."""
    workshop = _read("NightguardWorkshop.qml")
    guard = re.search(
        r'if \(asked === "glance" \|\| asked === "apps" \|\| asked === "schedule"\)',
        workshop)
    assert guard, "open() no longer checks the view name against the views it has"
    assert "catch (e)" in workshop.split("function open(")[1][:600], (
        "an unparseable payload must not stop the window opening"
    )
