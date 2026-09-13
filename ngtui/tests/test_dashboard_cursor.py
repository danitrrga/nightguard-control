"""Controls 5, 6 and 6b — one cursor, shared by the pointer and the keyboard.

Omarchy's kit keeps a control hot when the pointer is over it *or* the keyboard cursor
is on it (``Ui/Button.qml``'s ``hot = containsMouse || hasCursor``), and a
``hovered(bool)`` signal moves the panel's keyboard cursor on mouse-enter so the two
can never disagree (``plugins/panels/monitor/Panel.qml:42``). In Textual the cursor IS
focus, so ``ControlRow.on_enter`` calling ``self.focus()`` is the whole mechanism —
one model instead of two, and two models are how a pointer and a keyboard end up
disagreeing (D-02, UIX-02).

These three controls are what make that assertable rather than claimed.

The probe screen is built HERE from the real ``ControlRow`` rather than from
``conftest.py``'s ``probe_app``: that fixture defines its own local row precisely
because this widget did not exist when it was written, and a control that asserted the
shared cursor against the fixture's row would be asserting the fixture. It still runs
at ``SANCTIONED_SIZE`` and uses the ``asyncio.run()`` wrapper
(``tests/test_ui_harness.py``), which is the phase's idiom.

Two harness facts these controls depend on, both measured earlier in this phase:

  * ``app.query(...)`` is scoped to the DEFAULT screen. After a ``push_screen`` it
    matches nothing, so every query here goes through ``app.screen``.
  * Textual focuses the first focusable widget when a screen mounts, so the cursor
    starts on ``r0`` without anyone pressing anything. Control 5 asserts that
    explicitly before it hovers — a control that starts wherever it likes cannot say
    whether ``j`` continued from the pointer or merely landed somewhere.

And one Pilot fact: ``pilot.hover()`` returns a **bool**, ``False`` when the hover did
not land on the selected widget. A silently-missed hover is exactly how control 5
passes for the wrong reason, so the return value is asserted rather than discarded.
"""
from __future__ import annotations

import asyncio

from textual import events
from textual.screen import Screen

from ngtui.widgets.controlrow import PRESS_FLASH, Control, ControlRow, home_controls
from tests.test_ui_harness import SANCTIONED_SIZE

# Comfortably past the stylesheet's 120ms fill cross-fade. Derived from the widget's
# own constant rather than typed, so a change to the transition cannot leave this
# sampling the middle of the fade.
SETTLE = PRESS_FLASH * 2.5


def _probe_controls(count: int) -> list[Control]:
    """``count`` plain reachable stops. Routes are real keys; nothing is refused."""
    return [
        Control(
            key="r%d" % index,
            label="row %d" % index,
            value="value %d" % index,
            # A non-empty detail on purpose: the detail cell is `width: auto`, so an
            # empty one is ZERO columns wide and the "far right edge" click would land
            # back on the value cell — a far-edge control that never reaches the far
            # cell.
            detail="right-hand detail %d" % index,
        )
        for index in range(count)
    ]


class _ProbeScreen(Screen):
    """A bare screen of real ControlRows that records every activation it sees.

    Recording on the SCREEN rather than on the row is deliberate: ``Activated`` and
    ``Refused`` are bubbling messages, so a screen that hears them is the same
    arrangement the real composition will use, and a row that stopped its own message
    from bubbling would turn these controls red instead of passing locally.
    """

    def __init__(self, controls: list[Control]) -> None:
        self._controls = controls
        self.activated: list[str] = []
        self.refused: list[str] = []
        super().__init__()

    def compose(self):
        for control in self._controls:
            yield ControlRow(control, id=control.key)

    def on_control_row_activated(self, message: ControlRow.Activated) -> None:
        self.activated.append(message.model.key)

    def on_control_row_refused(self, message: ControlRow.Refused) -> None:
        self.refused.append(message.model.key)


def _probe_app(controls: list[Control]):
    """The real NightguardApp showing a probe screen — real stylesheet, real tokens.

    Subclassed from the shipped app rather than from a bare ``App`` for the reason
    ``conftest.py`` gives: the ladder, the reserved spine and the ``$ng-*`` variables
    are all properties of the shipped app, and a hand-built App would let these
    controls pass while the real one stayed unstyled.
    """
    import os

    from ngtui import app as ngtui_app
    from ngtui.app import NightguardApp

    class _ProbeApp(NightguardApp):
        # Textual resolves a relative CSS_PATH against the directory of the module
        # where the App subclass is DEFINED, so a subclass declared in tests/ would
        # look for tests/app.tcss and die. Pinned to the shipped stylesheet, which is
        # also what keeps these controls honest.
        CSS_PATH = os.path.join(
            os.path.dirname(os.path.abspath(ngtui_app.__file__)), "app.tcss"
        )

        def on_mount(self, event: events.Mount) -> None:
            # prevent_default() is load-bearing: Textual dispatches to the handler of
            # EVERY class in the MRO, so defining on_mount here does NOT replace
            # NightguardApp.on_mount — without this the real StatusScreen is pushed on
            # top of the probe and every query below runs against live guard state
            # (T-12.1-01).
            event.prevent_default()
            self._apply_omarchy_theme()
            self.push_screen(_ProbeScreen(controls))

        def action_edit(self) -> None:
            raise AssertionError(
                "a cursor control routed into the editor — the write path is not "
                "reachable from a UI control test (T-12.1-01)"
            )

    return _ProbeApp()


def test_hover_then_j_continues():
    """Control 5. Hover r2, press j, land on r3 — not back at the top.

    This is the contract in one line. The pointer moved the keyboard cursor, so the
    keyboard continues from where the pointer left it. If hover and focus were two
    models, `j` would continue from whatever the KEYBOARD last touched (r0) and the
    user would watch the highlight jump away from his mouse.

    Negative control, demonstrated (measured 2026-09-13). Remove
    ``on_enter`` -> ``self.focus()`` from ``ControlRow``. The pointer then moves
    nothing, focus stays where the screen mount put it, and this test goes red at the
    hover rather than at the keystroke:

        E   AssertionError: the pointer did not move the keyboard cursor: focus is
            on 'r0'
        E   assert 'r0' == 'r2'

    The plan's prescribed figure for this arm is ``assert 'r1' == 'r3'``, and it
    reproduces exactly — measured by removing the intermediate assertion above and
    re-running the same arm:

        E   AssertionError: j did not continue from the pointer — focus was on 'r1'
        E   assert 'r1' == 'r3'

    Both are the same bug. The intermediate assertion is kept because the second
    message says "the walk is wrong" about a walk that is fine, and the first says
    which half actually broke.

    The hover's own return value is asserted too: `hover()` returns False when the
    hover did not land, and a missed hover would leave focus at r0, step to r1, and
    fail with a message blaming the shared cursor for a mis-aimed test.
    """

    async def _body():
        app = _probe_app(_probe_controls(5))
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()

            # Where the cursor starts is part of the contract, not an accident:
            # Textual focuses the first focusable widget on mount.
            assert app.focused is not None, "nothing is focused — the probe has no rows"
            assert app.focused.id == "r0"

            landed = await pilot.hover("#r2")
            assert landed, (
                "the hover did not land on #r2 — everything after this would be "
                "measuring a mis-aimed pointer, not the shared cursor"
            )
            assert app.focused is not None
            assert app.focused.id == "r2", (
                "the pointer did not move the keyboard cursor: focus is on %r"
                % (app.focused.id,)
            )

            await pilot.press("j")
            await pilot.pause()
            assert app.focused.id == "r3", (
                "j did not continue from the pointer — focus was on %r"
                % (app.focused.id,)
            )

    asyncio.run(_body())


def test_every_control_is_keyboard_reachable():
    """Control 6. The j-walk visits the whole registry, and Enter fires each one.

    Keyboard-only operation stays complete (UIX-03): every control reachable without
    a pointer, and every control activatable once reached. The registry walked here is
    the real 16-stop ``home_controls()`` list, chips included — a control set that
    only tested five hand-made rows would not notice a chip that lost its focus.

    Negative control, demonstrated (measured 2026-09-13). ``mode`` made unreachable
    while still in the registry (``self.can_focus = False`` for that key in
    ``ControlRow.__init__``) — the shape a control takes when it quietly stops being
    a control. Fifteen walked against sixteen registered, and the diff names it:

        E   AssertionError: the j-walk does not visit the registry
        E     walked:   ['ramp', 'curfew', 'may-weaken', 'app-blocking',
                         'blocked-apps', 'always-allowed', 'game-blocking',
                         'site-blocking', 'blocked-sites', 'enforcement',
                         'chip-edit', 'chip-ledger', 'chip-refresh', 'chip-help',
                         'chip-quit']
        E     expected: [... 'app-blocking', 'mode', 'blocked-apps', ...]
        E   assert ['ramp', 'cur...allowed', ...] == ['ramp', 'cur...ed-apps', ...]
        E     At index 4 diff: 'blocked-apps' != 'mode'
        E     Right contains one more item: 'chip-quit'

    Note what this arm does NOT use: dropping a stop from ``home_controls`` would
    leave this control green, because ``expected`` is read from the registry and
    would shrink with it. The bug worth catching is a stop that is registered and
    unreachable, not one that was never registered.
    """

    async def _body():
        registry = home_controls(
            {
                "curfew": {"start": "21:30", "end": "05:30"},
                "edit_window": {"start": "05:30", "end": "14:00"},
                "blocking": {
                    "native_apps": {"enabled": True, "blacklist": ["steam"]},
                    "browser_extension": {"enabled": True},
                },
            }
        )
        expected = [control.key for control in registry]
        assert len(expected) == 16

        app = _probe_app(list(registry))
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()

            # Walk with j until the cursor returns to where it started. The loop is
            # bounded so a broken walk fails on the assertion below rather than
            # hanging the suite.
            start = app.focused.id
            walked = [start]
            for _ in range(len(expected) * 2):
                await pilot.press("j")
                await pilot.pause()
                here = app.focused.id
                if here == start:
                    break
                walked.append(here)

            assert walked == expected, (
                "the j-walk does not visit the registry\nwalked:   %s\nexpected: %s"
                % (walked, expected)
            )

            # ...and every stop activates from the keyboard alone. Refused stops post
            # Refused rather than Activated — both count as "fired", and which one
            # fired is the seam control 6c owns.
            screen = app.screen
            for key in expected:
                row = screen.query_one("#%s" % key, ControlRow)
                row.focus()
                await pilot.pause()
                assert app.focused is row, "could not put the cursor on %s" % key
                await pilot.press("enter")
                await pilot.pause()

            fired = sorted(screen.activated + screen.refused)
            assert fired == sorted(expected), (
                "Enter did not fire every control\nfired:    %s\nexpected: %s"
                % (fired, sorted(expected))
            )
            # The four frozen keys refused; nothing else did.
            assert sorted(screen.refused) == sorted(
                ["mode", "always-allowed", "game-blocking", "blocked-sites"]
            )

    asyncio.run(_body())


def test_the_whole_row_is_the_click_target():
    """Control 6b. A click anywhere on a row activates it — no part of it is dead.

    A dead region in a control the user believes is live is how a late-night user
    concludes the app is broken and reaches for the raw config instead (T-12.1-18).
    The row is the widget, so the target comes free — but the row composes three inner
    Statics, and a cell that stopped the Click from bubbling would create exactly that
    dead region while the row still looked and highlighted normally.

    Asserted on the ACTIVATION, never on ``pilot.click()``'s return value. That return
    value is ``widget_at is target_widget`` (``pilot.py:519``), and over the three
    cells the widget under the pointer is the CELL, so it reads False on a perfectly
    live row. Measured on working code, clicking #r2:

        x=  0  click() -> True   widget_at=ControlRow   activated=['r2']
        x=  5  click() -> False  widget_at=row-label    activated=['r2']
        x= 20  click() -> False  widget_at=row-label    activated=['r2']
        x= 66  click() -> False  widget_at=row-detail   activated=['r2']
        x=131  click() -> False  widget_at=row-detail   activated=['r2']

    A control written against that return value would be red on four of five live
    positions.

    Negative control, demonstrated twice (measured 2026-09-13), because one cell is
    not the whole row. An ``on_click`` calling ``event.stop()`` — the ordinary way a
    cell grows a behaviour of its own — put on the VALUE cell:

        E   AssertionError: clicking #r2 at x=68 did not activate it — that part of
            the row is dead
        E   assert [] == ['r2']

    and on the DETAIL cell, which is the one that owns the far right edge:

        E   AssertionError: clicking #r2 at x=125 did not activate it — that part of
            the row is dead
        E   assert [] == ['r2']
    """

    async def _body():
        app = _probe_app(_probe_controls(5))
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            screen = app.screen
            row = screen.query_one("#r2", ControlRow)
            width = row.size.width
            assert width >= 100, (
                "the probe row is %d cells wide — the far-edge click below would not "
                "be testing a far edge" % width
            )

            # The offsets are DERIVED from where the cells actually landed, not typed:
            # a hardcoded x that drifts off the cell it was meant to cover turns a
            # three-cell control into a one-cell control without a word of output.
            cells = {}
            for cell in row.children:
                name = next(c for c in cell.classes if c.startswith("row-"))
                cells[name] = cell
            assert set(cells) == {"row-label", "row-value", "row-detail"}, cells
            for name, cell in cells.items():
                assert cell.size.width > 0, "%s is zero columns wide" % name

            origin = row.region.offset.x
            offsets = [0]  # the reserved spine column — the very first cell of the row
            for name in ("row-label", "row-value", "row-detail"):
                cell = cells[name]
                offsets.append(cell.region.x - origin + cell.size.width // 2)
            offsets.append(width - 1)  # the last addressable column
            assert offsets == sorted(offsets) and offsets[-1] == width - 1

            for x in offsets:
                screen.activated.clear()
                await pilot.click(row, offset=(x, 0))
                await pilot.pause()
                assert screen.activated == ["r2"], (
                    "clicking #r2 at x=%d did not activate it — that part of the row "
                    "is dead" % x
                )

            # The click also moves the cursor there, so pointer and keyboard still
            # agree after a click, not only after a hover.
            assert app.focused is row

    asyncio.run(_body())


def test_the_paint_ladder_keeps_its_priority(omarchy_theme_dir):
    """pressed > cursor > selected > idle, with the theme's own alphas (UIX-02).

    The second half of UIX-02, and the half nothing guarded until now. Rule ORDER is
    the mechanism: `:focus` counts as a class for specificity, so `.ctl:focus` and
    `.ctl.-pressed` TIE and the later rule wins. That makes the ladder's correctness a
    property of where six lines sit in a file — invisible in review, and silently
    changed by any tidy-up that sorts them. Plan 04's handover says so in as many
    words; this is the test that makes the warning enforceable.

    Run against the fixture theme rather than the live desktop one, for two reasons:
    the four rungs are pinned to four distinct alphas there (0.42 / 0.08 / 0.18 /
    0.22), and a desktop theme swap mid-suite cannot move the numbers out from under
    it (T-12.1-02).

    Asserting all four rungs are DISTINCT is load-bearing on its own: one rung alone
    cannot tell "the ladder is wired" from "every row paints the same fill".

    Negative control, demonstrated (measured 2026-09-13). `.ctl.-pressed` moved ABOVE
    `.ctl:focus` in `app.tcss` — a re-sort, not a rewrite, and the two rules are
    byte-identical before and after:

        E   AssertionError: a focused AND pressed row paints the cursor rung, not the
            pressed one — the ladder has been re-sorted
        E   assert 0.08 == 0.22
    """

    async def _body():
        app = _probe_app(_probe_controls(3))
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            screen = app.screen
            rows = list(screen.query(ControlRow))

            async def fill(row, *classes, cursor=False):
                for other in rows:
                    other.remove_class("-pressed", "-selected")
                screen.set_focus(row if cursor else None)
                if classes:
                    row.add_class(*classes)
                # Past the 120ms cross-fade, not merely past the message queue.
                # `styles.background` is the ANIMATED value: measured, reading it
                # straight after a class change returned 0.2037 for a rung whose
                # settled alpha is 0.08 — an intermediate frame of the fade from 0.18.
                # A control that sampled mid-fade would be flaky in whichever
                # direction the machine happened to be slow.
                await pilot.pause(SETTLE)
                if cursor:
                    assert app.focused is row, "the cursor is not on the measured row"
                # `% (color,)` and never `% color`: textual.color.Color is a
                # NamedTuple, so the bare form raises TypeError instead of printing —
                # a control whose failure message raises says nothing on the day it
                # fires (found in this phase's plan 04).
                return round(row.styles.background.a, 4)

            row = rows[1]
            idle = await fill(row)
            cursor = await fill(row, cursor=True)
            selected = await fill(row, "-selected")
            pressed = await fill(row, "-pressed")

            rungs = {"idle": idle, "cursor": cursor, "selected": selected,
                     "pressed": pressed}
            assert len(set(rungs.values())) == 4, (
                "the four rungs do not paint four different fills, so nothing below "
                "can tell a wired ladder from a flat one: %s" % (rungs,)
            )

            # pressed beats the cursor...
            both = await fill(row, "-pressed", cursor=True)
            assert both == pressed, (
                "a focused AND pressed row paints the cursor rung, not the pressed "
                "one — the ladder has been re-sorted"
            )
            # ...the cursor beats selected...
            cursor_over_selected = await fill(row, "-selected", cursor=True)
            assert cursor_over_selected == cursor, (
                "a focused AND selected row paints the selected rung, not the cursor "
                "— the ladder has been re-sorted"
            )
            # ...and pressed beats selected.
            pressed_over_selected = await fill(row, "-pressed", "-selected")
            assert pressed_over_selected == pressed, (
                "a pressed AND selected row paints the selected rung — the ladder "
                "has been re-sorted"
            )

    asyncio.run(_body())
