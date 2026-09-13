"""Controls 11, 11b and 11c — the hero is an instrument, and it is readable.

The hero is the screen's one idea (UIX-04, D-06): the day as a full-width density ramp
whose density is hours-until-the-curfew, a second channel marking the hours a loosening
is accepted, one bright cell for now, and a read-out that answers a pointer and a
keyboard with the same string.

Three things have to hold for that to be true rather than claimed:

  * **11** the density function never emits index 0. Index 0 is the space, and a blank
    cell in the day reads as *missing data* rather than as "far from the curfew" — an
    instrument that renders a gap where it means "plenty of time" lies in the direction
    that costs the user his curfew. Exhaustive over all 1440 minutes, no App.
  * **11b** hovering the curfew-edge column reads out the curfew start — *at the width
    the ramp actually got*, not at a width somebody typed.
  * **11c** ``h``/``l`` write byte-identically what the pointer writes. Keyboard parity
    is the requirement, and comparing rendered strings is the only assertion that proves
    the two inputs share one destination rather than two code paths that agree today.

# Why every column here is derived and none is typed (RESEARCH Pitfall 7).
# `column_minute` is width-dependent: the probe that de-risked this phase measured
# column 107 of a 120-wide ramp resolving to 21:30, the exact curfew start — but at the
# real content width of 129 that same column reads 20:00, and the first column inside a
# 21:30 curfew is 116. A test that hardcoded that column and expected 21:30 would assert
# the wrong thing at the real width and pass or fail for reasons unrelated to the code.
# Measured again here: the ramp on this probe screen is 131 columns wide, not 120, 129
# or 135 — the screen rule in app.tcss takes two columns of padding either side. Every
# expected column below is computed from `ramp.content_size.width` read inside the test.

Harness facts these controls depend on, all measured earlier in this phase:

  * ``app.query(...)`` is scoped to the DEFAULT screen, so every query goes through
    ``app.screen``.
  * Textual focuses the first focusable widget when a screen mounts. 11c asserts that
    explicitly before it presses anything — a control that starts wherever it likes
    cannot say whether the keyboard walked from where it thought it did.
  * ``prevent_default()`` in the probe's ``on_mount``: Textual dispatches to the handler
    of every class in the MRO, so without it the real ``StatusScreen`` is pushed on top
    of the probe and every assertion runs against live guard state (T-12.1-01).
  * the ``asyncio.run()`` wrapper from ``tests/test_ui_harness.py`` is the phase's idiom;
    a bare ``async def`` is reported as a *failure*, not an error.

Nothing here reads a live config, a live clock or live guard state: the probe hands
``DayRamp`` a config, an edit window and a verified minute, which is the widget's
documented "handed in, never read" path.
"""
from __future__ import annotations

import asyncio
import os

from textual import events
from textual.screen import Screen
from textual.widgets import Static

from ngtui.widgets.hero import (
    MINUTES_PER_DAY,
    RAMP_CHARS,
    DayRamp,
    column_minute,
    density_index,
    density_row,
    minutes_to_hhmm,
    now_column,
)
from tests.test_ui_harness import SANCTIONED_SIZE

# The live curfew's shape, as the sanctioned config carries it. Written as HH:MM
# arithmetic rather than as bare minute counts so a reader can check the table in
# UI-SPEC 12 against it without doing division.
CURFEW_START = 21 * 60 + 30      # 21:30
CURFEW_END = 5 * 60 + 30         # 05:30
EDIT_START = "05:30"
EDIT_END = "14:00"

# A verified minute-of-day inside the edit window, matching the contract's own read-out
# example (`09:14   open - a loosening is allowed here`). Handed to the widget, so the
# now marker and the keyboard's starting column are deterministic.
NOW_MINUTES = 9 * 60 + 14

CFG = {
    "timezone": "Europe/Amsterdam",
    "curfew": {"enabled": True, "start": "21:30", "end": "05:30"},
    "edit_window": {"enabled": True, "start": EDIT_START, "end": EDIT_END},
}
WINDOW = CFG["edit_window"]


class _ProbeScreen(Screen):
    """A bare screen carrying nothing but the hero, so the ramp gets the full width."""

    def compose(self):
        yield DayRamp(cfg=CFG, window=WINDOW, now_minutes=NOW_MINUTES, id="hero")


def _probe_app():
    """The real ``NightguardApp`` showing only the hero — real stylesheet, real tokens.

    Subclassed from the shipped app rather than from a bare ``App`` for the reason
    ``conftest.py`` gives: ``#ramp``'s ``width: 1fr`` and the ``$ng-*`` variables are
    properties of the shipped app, and a hand-built App would measure a width the real
    ramp never has. ``conftest.py``'s ``probe_app`` is not reused because it composes
    its own rows — it was written before this widget existed.
    """
    from ngtui import app as ngtui_app
    from ngtui.app import NightguardApp

    class _ProbeApp(NightguardApp):
        # Textual resolves a relative CSS_PATH against the directory of the module where
        # the App subclass is DEFINED, so a subclass declared in tests/ would look for
        # tests/app.tcss and die. Pinned to the shipped stylesheet.
        CSS_PATH = os.path.join(
            os.path.dirname(os.path.abspath(ngtui_app.__file__)), "app.tcss"
        )

        def on_mount(self, event: events.Mount) -> None:
            event.prevent_default()
            self._apply_omarchy_theme()
            self.push_screen(_ProbeScreen())

        def action_edit(self) -> None:
            raise AssertionError(
                "a hero control routed into the editor — the write path is not "
                "reachable from a UI control test (T-12.1-01)"
            )

    return _ProbeApp()


def _readout(app) -> str:
    """What the reserved read-out row actually PAINTS, not what a widget remembers.

    ``render_line`` rather than an attribute on ``DayRamp``: the claim under test is
    that both inputs reach one *destination*, and an attribute the widget sets is not
    the destination. Measured: the strip is not right-padded, so this is the exact
    string and 11c's byte-identical comparison means what it says.
    """
    return app.screen.query_one("#readout", Static).render_line(0).text


def _curfew_edge(width: int) -> int:
    """The first column at or after the curfew start, for a ramp ``width`` wide.

    Derived, never typed. At the probe's measured width this lands one column past the
    last open column; 11b asserts that the column before it still reads ``open`` so the
    mapping is proved to land ON the edge rather than merely near it.
    """
    for index in range(width):
        if column_minute(index, width) >= CURFEW_START:
            return index
    raise AssertionError(
        "no column of a %d-wide ramp reaches the curfew start — the mapping no longer "
        "covers the day" % width
    )


# --- Control 11 — pure, exhaustive, no App -----------------------------------


def test_density_never_emits_index_zero():
    """Every minute of the day maps to a density in 1-9. The space is never painted.

    All 1440 minutes, not a sample, and then the rendered row at three widths — because
    "the function never returns 0" and "the ramp never shows a gap" are two claims and
    only the second is what a reader sees.

    Negative control, demonstrated able to fail: let index 0 through by changing the
    ladder's fallthrough from ``return 1`` to ``return 0`` in ``density_index``. The set
    comparison goes red naming the extra member. The recorded message is in
    ``12.1-06-SUMMARY.md``.
    """
    # Vacuity guard first. The whole control rests on index 0 being the space and the
    # ladder being ten long; if RAMP_CHARS were re-spelled, `set(range(1, 10))` would
    # still pass while meaning something else entirely.
    assert RAMP_CHARS[0] == " ", (
        "index 0 is no longer the space — this control's whole premise has moved: %r"
        % (RAMP_CHARS,)
    )
    assert len(RAMP_CHARS) == 10

    # The real curfew: start AND end, so the inside-the-curfew band is the full 9.
    assert {
        density_index(minute, CURFEW_START, CURFEW_END)
        for minute in range(MINUTES_PER_DAY)
    } == set(range(1, 10))

    # And the two-argument form, which is what a config carrying no `curfew.end`
    # degrades to. It must not open a hole at index 0 either.
    assert {
        density_index(minute, CURFEW_START) for minute in range(MINUTES_PER_DAY)
    } == set(range(1, 10))

    # What the reader actually sees. Verified at the three widths RESEARCH measured
    # the index set at, plus the width this probe screen really gets.
    for width in (120, 129, 131, 135):
        row = density_row(width, CURFEW_START, CURFEW_END)
        assert len(row) == width
        assert " " not in row, (
            "a %d-wide ramp paints a gap — a blank cell reads as missing data, not as "
            "'far from the curfew': %r" % (width, row)
        )
        assert {RAMP_CHARS.index(glyph) for glyph in row} == set(range(1, 10)), (
            "a %d-wide ramp does not use the whole 1-9 ladder: %r" % (width, row)
        )


# --- Control 11b — the column read-out, at the measured width ----------------


def test_hovering_a_column_reads_out_its_hour():
    """Hovering the curfew-edge column reads out the curfew start, at the real width.

    Four assertions, and the first is the one that makes the rest mean anything:

      1. the ramp samples the day **symmetrically** — the first column's minute is the
         same distance from midnight as the last column's is from the end of the day.
         That is the half-cell offset stated as a property rather than as the formula,
         so it can catch an off-by-one that the derived expectations below cannot: a
         mapping that is uniformly wrong stays self-consistent, and every expectation
         computed from `column_minute` moves with it.
      2. the edge column is genuinely the edge — the column before it is before the
         curfew start, the edge column is at or after it.
      3. hovering the edge reads `curfew - locked`, with the exact hour that column
         covers.
      4. hovering the column before it still reads `open` — and still refuses a
         loosening, because the edit window closed hours earlier. The two channels of
         the read-out are independent and this proves it.

    Negative control, demonstrated able to fail: off-by-one the mapping,
    ``i / width`` instead of ``(i + 0.5) / width`` in ``column_minute``. Assertion 1
    fires. The resulting off-by-one column and the verbatim message are recorded in
    ``12.1-06-SUMMARY.md``.
    """

    async def _body():
        app = _probe_app()
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()

            ramp = app.screen.query_one("#ramp", Static)
            width = ramp.content_size.width
            assert width > 0, "the ramp has no width — nothing below measures anything"

            # 1. Symmetry. Independent of the implementation's formula: it says the day
            # is sampled by column CENTRES, so the first and last columns sit the same
            # distance in from the two ends. The left-edge form pins the first column at
            # 00:00 and leaves the last one a whole column short of midnight.
            first = column_minute(0, width)
            last = column_minute(width - 1, width)
            assert abs(first - (MINUTES_PER_DAY - last)) <= 1, (
                "the ramp does not sample the day symmetrically — column 0 reads %s and "
                "the last column reads %s, %d minutes from midnight versus %d. The "
                "column-to-minute mapping is reporting each column's left EDGE instead "
                "of its centre."
                % (
                    minutes_to_hhmm(first),
                    minutes_to_hhmm(last),
                    first,
                    MINUTES_PER_DAY - last,
                )
            )

            # 2. The edge, derived from the measured width.
            edge = _curfew_edge(width)
            assert edge > 0, "the curfew starts in column 0 — there is no edge to assert"
            assert column_minute(edge - 1, width) < CURFEW_START <= column_minute(
                edge, width
            )

            # 3. The edge column reads the curfew.
            landed = await pilot.hover("#ramp", offset=(edge, 0))
            await pilot.pause()
            assert landed, (
                "the hover did not land on #ramp at column %d — a missed hover is how "
                "this control passes for the wrong reason" % edge
            )
            expected = "%s   curfew — locked · a loosening is refused here" % (
                minutes_to_hhmm(column_minute(edge, width)),
            )
            assert _readout(app) == expected, (
                "hovering the curfew-edge column of a %d-wide ramp did not read out the "
                "curfew\n  got:      %r\n  expected: %r"
                % (width, _readout(app), expected)
            )

            # 4. One column earlier is still open — and a loosening is still refused
            # there, because the edit window is a separate channel.
            landed = await pilot.hover("#ramp", offset=(edge - 1, 0))
            await pilot.pause()
            assert landed
            expected_before = "%s   open · a loosening is refused here" % (
                minutes_to_hhmm(column_minute(edge - 1, width)),
            )
            assert _readout(app) == expected_before, (
                "the column before the curfew edge does not read open\n  got:      %r\n"
                "  expected: %r" % (_readout(app), expected_before)
            )

            # And a column inside the signed edit window reads the other permission.
            # Derived from the window's own start so it moves with the config.
            inside = now_column(NOW_MINUTES, width)
            landed = await pilot.hover("#ramp", offset=(inside, 0))
            await pilot.pause()
            assert landed
            assert _readout(app).endswith("open · a loosening is allowed here"), (
                "a column inside the signed edit window does not read as allowed: %r"
                % (_readout(app),)
            )

    asyncio.run(_body())


# --- Control 11c — keyboard parity, byte for byte ----------------------------


def test_keyboard_readout_matches_the_pointer():
    """``h``/``l`` write the pointer's string, not merely a similar one.

    The keyboard walks to a column, its rendered read-out is captured, then the pointer
    is sent to that same column and the read-out captured again. The two strings must be
    identical. Anything weaker — "both contain the hour", "both mention the curfew" —
    passes on two formatters that happen to agree today and goes red the day one of them
    is edited, which is the day nobody is looking.

    The keyboard's landing column is asserted against the derived expectation as well as
    read off the widget, so a walk that moved the wrong distance is caught here rather
    than silently making both captures agree about the wrong hour.

    Negative control, demonstrated able to fail: give the keyboard path its own format
    string in ``action_readout_right`` instead of routing through the one ``readout()``
    call site. The two captures diverge. The verbatim message is in
    ``12.1-06-SUMMARY.md``.

    **This control pressed ``l``/``h`` until plan 12.1-07 composed the ramp into the
    real home surface and measured the collision:** ``l`` is one of the four
    single-key bindings pinned to ``NightguardApp`` (``ledger``), and the ramp holds
    the cursor on mount because it is stop 1 of 16 — so ``l`` reached the ramp and
    the ledger toggle was unreachable from the screen's opening state. The ramp gave
    up the vim pair; ``left``/``right`` were already bound to the same two actions
    and are what this control presses now. The claim under test is unchanged: two
    inputs, one destination.
    """

    async def _body():
        app = _probe_app()
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()

            hero = app.screen.query_one(DayRamp)
            ramp = app.screen.query_one("#ramp", Static)
            width = ramp.content_size.width

            # Textual focuses the first focusable widget on mount. Asserted rather than
            # assumed: if the cursor were somewhere else, `right` would be walking a
            # widget this control never names and both captures would still agree.
            assert app.focused is hero, (
                "the cursor is not on the ramp — `right` is walking something else: %r"
                % (app.focused,)
            )

            # The read-out starts where the instrument already points: the now marker.
            start_column = now_column(NOW_MINUTES, width)
            assert hero.readout_column == start_column

            steps = 5
            await pilot.press(*(["right"] * steps))
            await pilot.pause()

            assert hero.readout_column == start_column + steps, (
                "`right` x%d moved the read-out column from %s to %s"
                % (steps, start_column, hero.readout_column)
            )
            keyboard_string = _readout(app)
            assert keyboard_string.strip(), "the keyboard wrote an empty read-out"

            # The same column, reached by the other input.
            column = hero.readout_column
            landed = await pilot.hover("#ramp", offset=(column, 0))
            await pilot.pause()
            assert landed
            assert hero.readout_column == column
            pointer_string = _readout(app)

            assert keyboard_string == pointer_string, (
                "the keyboard and the pointer write different read-outs for column %d "
                "— they are two code paths, not one destination\n  keyboard: %r\n"
                "  pointer:  %r" % (column, keyboard_string, pointer_string)
            )

            # Vacuity guard: two empty strings are also identical. The captured string
            # must be the read-out for the column both inputs landed on.
            assert pointer_string.startswith(
                minutes_to_hhmm(column_minute(column, width))
            ), (
                "the read-out does not name the hour of column %d: %r"
                % (column, pointer_string)
            )

            # And `left` walks back the way it came, through the same destination.
            await pilot.press("left")
            await pilot.pause()
            assert hero.readout_column == column - 1
            assert _readout(app).startswith(
                minutes_to_hhmm(column_minute(column - 1, width))
            )

    asyncio.run(_body())
