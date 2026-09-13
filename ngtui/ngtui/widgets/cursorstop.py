"""cursorstop.py — what it means to be a stop on the home surface's one cursor.

The home surface has exactly one cursor and it is Textual focus (D-02, UIX-02). Two
different widgets carry it: ``ControlRow``, which is every changeable value, and
``DayRamp``, which is the read instrument at stop 1 of UI-SPEC §8.6's sixteen. They
are different widgets because they are different things — one is a ``height: 1`` row
with three cells, the other is a four-row instrument — but they are the same *kind of
stop*, and the walk has to treat them as one list.

**The seam this module closes.** ``ControlRow.action_cursor_down`` used to call
``focus_next(ControlRow)``. ``DayRamp`` is focusable and is **not** a ``ControlRow``,
so the ``j``/``k`` walk skipped it: the cursor started at stop 2, stop 1 was reachable
only by ``tab``, and the ramp — the screen's one idea — was the one control the
keyboard could not walk to. Plan 12.1-06 recorded it and left it because
``controlrow.py`` was not its file.

**Why a base class and not a CSS class.** ``Screen._move_focus`` takes
``str | type``; for a type it uses ``selector.__name__`` and matches it against the
node's ``_css_type_names``, which ``DOMNode.__init_subclass__`` fills from
``_css_bases`` — the chain of DOMNode ancestors. So a shared base is matched by name
by the same machinery that matches ``ControlRow``, with no marker class to remember to
add at every construction site. A CSS class would work too and would be forgotten
exactly once.

**The walk lives here, in one place, for the reason plan 12.1-05 put it on the widget
rather than on a screen**: the cursor is a property of the control strip, not of
whichever composition hosts it. Having it on the *stop* rather than on ``ControlRow``
is the same argument one level up — a second copy of ``focus_next`` on ``DayRamp``
would be two code paths that agree until one of them is edited, which is the shape
plan 12.1-06's control 11c exists to catch.

This module imports ``textual`` and nothing else. ``controlrow.py`` reaches the trust
stack transitively (it reads ``EDITABLE_FIELDS`` from ``widgets/edit.py``, which
imports ``backend``), and ``hero.py``'s pure helpers must stay importable with no
LifeOS stack on ``sys.path`` — so the shared piece cannot live in ``controlrow.py``.
"""
from __future__ import annotations

from textual.binding import Binding
from textual.widgets import Static


class CursorStop(Static):
    """A stop on the home surface's shared cursor. Carries the walk, nothing else.

    No ``DEFAULT_CSS`` and no ``can_focus``: a stop decides its own paint and its own
    focusability. This class contributes exactly two bindings and the two actions
    behind them, so that inheriting it cannot change how a widget looks.

    Both bindings are ``show=False``. No bracket hint appears anywhere on this surface
    (OD-2, UIX-03); the legend lives in the ``help`` chip.
    """

    BINDINGS = [
        Binding("j,down", "cursor_down", "Next control", show=False),
        Binding("k,up", "cursor_up", "Previous control", show=False),
    ]

    def action_cursor_down(self) -> None:
        """``j`` / ``down`` — the next stop, and nothing but stops.

        Filtered to ``CursorStop`` so the walk visits the registered order rather than
        every focusable widget that happens to be mounted, and so it visits **every**
        registered stop rather than only the ones that are rows. Textual's focus chain
        IS the cursor here, so this moves the one cursor the pointer also moves.
        """
        self.screen.focus_next(CursorStop)

    def action_cursor_up(self) -> None:
        """``k`` / ``up`` — the previous stop."""
        self.screen.focus_previous(CursorStop)
