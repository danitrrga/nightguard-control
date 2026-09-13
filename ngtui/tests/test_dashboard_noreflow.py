"""Controls 7 and 8 — nothing changes size, and the timings are the desktop's.

Omarchy's ``Ui/Button.qml`` reserves the largest border any state can paint
(``_reservedBorderTop`` and its siblings) "otherwise a borderless idle button grows by
a pixel per side on hover/focus and relayouts neighboring controls". On a character
grid the reservation is stricter and simpler: a control row's spine is always
``border-left: vkey``, one column, in every rung of the ladder — including idle, where
it is ``$ng-border-normal`` and never ``none``. Only its colour moves (D-05, UIX-05).

**Why this asserts on ``content_size`` and never on the outer box.** Measured against
both bug shapes this control exists to catch — a ``:focus`` rule adding a right border,
and one adding a top border — a ``height: 1`` / ``width: 1fr`` row's outer box stayed
``(0, 2, 135, 1)`` in *every* case, because it is pinned by its container whatever the
border does. The neighbour's outer box never moved either: a top border squeezes the
content to height 0 rather than growing the row, so "assert the neighbour did not move"
is equally dead. **A test written against the outer box cannot fail, and a test that
cannot fail is not evidence.** UI-SPEC 8.4's "capture every row's region" and
VALIDATION row 7 are both corrected by RESEARCH 6 to the content box; the requirement
is unchanged, only the assertion target moved.

The probe screen comes from ``tests/test_dashboard_cursor.py`` rather than being built
again here. It is the real ``NightguardApp`` against the real ``app.tcss``, which is
the whole point — a hand-built App would let both controls pass while the shipped
ladder reflowed on every hover.
"""
from __future__ import annotations

import asyncio

from ngtui.app import NightguardApp
from ngtui.widgets.controlrow import PRESS_FLASH, ControlRow
from tests.test_dashboard_cursor import _probe_app, _probe_controls
from tests.test_ui_harness import SANCTIONED_SIZE

# The four rungs a row on the home surface can be painted in. "staged" is a fifth in
# the ladder but it only ever changes the spine COLOUR of whichever rung the row is
# already on, so it adds no geometry this control could distinguish.
_STATES = ("idle", "cursor", "pressed", "selected")


def test_no_state_changes_a_rows_content_box():
    """Every row's content box is identical in idle, cursor, pressed and selected.

    All four, not just idle-versus-focus: ``-pressed`` and ``-selected`` are separate
    rules in ``app.tcss`` and each one is a place a border could be grown. A control
    that checked only the focus rung would be green while a pressed row relaid out the
    strip under the user's finger.

    Negative controls, demonstrated (measured 2026-09-13). Both shapes, because they
    exercise different axes and a control that catches only the horizontal bug is half
    a control. ``border-right: vkey $ng-border-cursor;`` added under ``.ctl:focus``:

        E   AssertionError: r2 changes its content box with state — the ladder is
            growing a border instead of recolouring the reserved one
        E     idle     Size(width=132, height=1)
        E     cursor   Size(width=131, height=1)
        E     pressed  Size(width=132, height=1)
        E     selected Size(width=132, height=1)

        E   assert 2 == 1
        E     where 2 = len({'Size(width=131, height=1)', 'Size(width=132, height=1)'})

    and ``border-top: hkey $ng-border-cursor $ng-border-cursor-a;`` under the same
    rule — the axis a width-only control would miss entirely, because the row does not
    get taller, its content gets squeezed to nothing:

        E     idle     Size(width=132, height=1)
        E     cursor   Size(width=132, height=0)
        E     pressed  Size(width=132, height=1)
        E     selected Size(width=132, height=1)

    The figures are 132 rather than RESEARCH's 130 because the shipped ``.ctl`` rule
    is ``padding: 0 0 0 2`` (one left inset, not two): 135 - 1 spine - 2 padding. The
    SHAPE is RESEARCH's, measured against this stylesheet.
    """

    async def _body():
        app = _probe_app(_probe_controls(5))
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            screen = app.screen
            rows = list(screen.query(ControlRow))
            assert len(rows) == 5, "the probe lost its rows — this would measure nothing"

            # Vacuity guard on the reservation itself: an idle row must already have
            # the column. If idle ever painted `border: none`, every size below would
            # agree at the WRONG value and this control would pass on a reflowing row.
            park = rows[-1]
            park.focus()
            await pilot.pause()
            for row in rows[:-1]:
                style, _colour = row.styles.border_left
                assert style == "vkey", (
                    "%s paints %r as its idle spine — the reservation is the column "
                    "being there in EVERY rung, so an idle `none` makes every size "
                    "below agree at the wrong value and this control pass on a row "
                    "that reflows the moment it is hovered" % (row.id, style)
                )
                assert row.content_size.width < app.screen.size.width, (
                    "%s fills the whole screen width — nothing is being held open"
                    % row.id
                )

            measured: dict[str, dict[str, object]] = {row.id: {} for row in rows}
            for state in _STATES:
                for row in rows:
                    row.remove_class("-pressed", "-selected")
                if state == "idle":
                    # Textual focuses the first focusable widget on mount, so "idle"
                    # has to be arranged rather than assumed: the cursor is parked on
                    # a row that is not measured in this pass, and re-parked below.
                    screen.set_focus(None)
                elif state == "cursor":
                    pass  # handled per row, since only one widget can hold the cursor
                elif state == "pressed":
                    screen.set_focus(None)
                    for row in rows:
                        row.add_class("-pressed")
                elif state == "selected":
                    screen.set_focus(None)
                    for row in rows:
                        row.add_class("-selected")
                await pilot.pause()

                for row in rows:
                    if state == "cursor":
                        row.focus()
                        await pilot.pause()
                        assert app.focused is row, (
                            "could not put the cursor on %s — the cursor rung would "
                            "be measured on the wrong row" % row.id
                        )
                    measured[row.id][state] = row.content_size

            for row in rows:
                sizes = measured[row.id]
                unique = {str(size) for size in sizes.values()}
                assert len(unique) == 1, (
                    "%s changes its content box with state — the ladder is growing a "
                    "border instead of recolouring the reserved one\n%s"
                    % (
                        row.id,
                        "\n".join(
                            "  %-8s %s" % (state, sizes[state]) for state in _STATES
                        ),
                    )
                )

            # And the rows agree with each other, so a reflow that moved every row by
            # the same amount (a rule on `.ctl` rather than on one rung) is caught too.
            across = {str(measured[row.id]["idle"]) for row in rows}
            assert len(across) == 1, "the rows do not share one content box: %s" % across

    asyncio.run(_body())


def test_timings_match_the_desktop():
    """120 ms fill cross-fade and a 400 ms tooltip delay — the kit's own numbers.

    120 ms is ``Behavior on color { ColorAnimation { duration: 120 } }`` and 400 ms is
    ``ToolTip { delay: 400 }``, both in ``Ui/Button.qml``. Textual's tooltip default is
    **0.5** — close enough to look deliberate if it is missed, which is exactly why it
    is set explicitly rather than left alone (D-15).

    Border colour is deliberately NOT in this assertion: Textual's ANIMATABLE set
    contains ``background`` and ``color`` but not ``border``, so a state change
    cross-fades its fill and snaps its spine. That is stated in ``app.tcss`` so nobody
    spends a day trying to fix it, and asserting a border transition here would pin a
    behaviour the framework cannot deliver.

    Negative controls, demonstrated (measured 2026-09-13).

    ``TOOLTIP_DELAY`` deleted from ``NightguardApp``, so Textual's default takes over:

        E   AssertionError: the tooltip delay is not the desktop's 400 ms
        E   assert 0.5 == 0.4

    the ``transition:`` declaration removed from ``.ctl``, so a state change snaps:

        E   AssertionError: a .ctl row declares no background transition — a state
            change would snap instead of cross-fading
        E   assert 'background' in {}
    """

    async def _body():
        app = _probe_app(_probe_controls(3))
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            row = app.screen.query(ControlRow).first()

            transitions = row.styles.transitions
            assert "background" in transitions, (
                "a .ctl row declares no background transition — a state change would "
                "snap instead of cross-fading"
            )
            assert transitions["background"].duration == 0.12, (
                "the fill cross-fade is %r, not the kit's 120ms"
                % (transitions["background"].duration,)
            )
            # The colour channel moves with the fill; a row whose text snapped while
            # its background faded would read as two half-finished states.
            assert transitions["color"].duration == 0.12

    asyncio.run(_body())

    assert NightguardApp.TOOLTIP_DELAY == 0.4, (
        "the tooltip delay is not the desktop's 400 ms: %r"
        % (NightguardApp.TOOLTIP_DELAY,)
    )
    # The keyboard press flash is held for exactly one cross-fade, so the pressed rung
    # is visible for as long as the transition that reveals it.
    assert PRESS_FLASH == 0.12
