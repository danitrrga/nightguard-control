"""The two guardrails nobody was counting — the window budget and the accent reserve.

UI-SPEC §6.3 and §7.2 both state a number. A number nobody counts is a preference,
and the difference between the aesthetic surviving the next six months and drifting
is whether something goes red when it is exceeded. These are those controls.

Every test here mounts the **real** ``StatusScreen`` against the crafted
``ng_data_dir``, through ``test_dashboard_home._home_app`` — imported rather than
copied, because two copies of the ``CSS_PATH`` pin drift and the one that drifts
silently measures a stylesheet that does not ship.

**The sanctioned window is not a preference either.** ``packaging/omarchy/hypr/
nightguard.windowrule.conf`` pins the floating window at ``size 875 600``; at the
live terminal font that is exactly 135 × 46 cells, and every budget in the contract
is calibrated to it. Changing that file invalidates all of them — and it is installed
into the user's Hyprland config rather than re-read from the repo, so the change would
not even take effect until a reinstall.

Two harness facts these controls depend on, both measured earlier in this phase:

  * ``app.query(...)`` is scoped to the DEFAULT screen and matches nothing after a
    ``push_screen``. Every query goes through ``app.screen``.
  * A stylesheet parse error surfaces at app **teardown**, after the
    ``async with app.run_test()`` body has run, so each test exits its block
    normally rather than asserting its way out of it.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from tests.test_dashboard_home import _home_app
from tests.test_ui_harness import SANCTIONED_SIZE

#: UI-SPEC §6.3. 135 × 46 = 6210 cells, and the measured total from
#: ``render_strips()`` is exactly that — which is also the proof that ``cell_len``
#: is the right width function and ``len(text)`` is not.
SANCTIONED_CELLS = SANCTIONED_SIZE[0] * SANCTIONED_SIZE[1]

#: UI-SPEC §6.3. The ceiling is 5 % of the surface; failing it fails the phase. The
#: design target is 1 %, and the two are different claims — the ceiling is what may
#: never be crossed, the target is what the composition is supposed to cost. Both
#: are asserted, the target with the count in its message so a rise is legible
#: rather than merely red.
ACCENT_CEILING_CELLS = 310
ACCENT_DESIGN_TARGET_CELLS = 62

#: UI-SPEC §7.2. The audit ledger is the only region allowed to give, and it is the
#: one that must not be given away: it is the record. ``app.tcss`` enforces this as
#: ``min-height``; this is the number that rule is keeping.
LEDGER_FLOOR_ROWS = 4

#: UI-SPEC §7.4, the degradation triggers, mirrored from ``status.py`` so that the
#: contract and the implementation are asserted against each other rather than the
#: implementation being asserted against itself. A test that imported the module's
#: own constants would stay green if all three were changed together, which is
#: exactly the shape of the self-consistency this phase keeps finding.
DEGRADATION_LADDER = [
    # (size, the classes #frame must be wearing)
    ((135, 46), []),
    ((135, 45), ["-compact"]),
    ((135, 43), ["-compact"]),
    ((135, 42), ["-compact", "-tiny"]),
    ((135, 31), ["-compact", "-tiny"]),
    ((100, 46), []),
    ((80, 46), []),
    ((79, 46), ["-compact", "-narrow"]),
    ((79, 40), ["-compact", "-narrow", "-tiny"]),
]


def count_accent_cells(app) -> tuple[int, int, list[tuple[str, str, int]]]:
    """``(accent-painted cells, total cells, what painted them)`` for the screen.

    ``render_strips()`` is **private API**. It is acceptable inside a test against a
    pinned dependency (``textual==8.2.7``) and it must **never** be reached from
    application code — ``test_render_strips_never_reaches_application_code`` below is
    the standing enforcement of the second half of that sentence.

    Two rules, and the difference between them is not cosmetic:

      * a **background** match paints every cell of the segment, spaces included;
      * a **foreground** match paints only the segment's non-space glyphs, because a
        run of spaces in the accent's foreground colour is not visible ink.

    Width comes from ``rich.cells.cell_len``, never ``len(text)``, and the total
    assertion in ``test_accent_stays_under_five_percent`` is what enforces the
    difference. **Measured, and not what was expected**: on today's composition the
    two functions agree exactly — swapping in ``len(text)`` leaves the control green,
    because nothing currently painted is double-width (the wordmark's Nerd Font glyph
    and the hero's block characters are all one cell). Put one double-width character
    on the surface and they part company::

        cell_len  -> total 6210, green
        len(text) -> the rendered surface is 6207 cells, not the sanctioned 6210 —
                     the ratio below would be against the wrong denominator

    So ``cell_len`` is correct rather than currently load-bearing, and the ``== 6210``
    assertion is the control that will notice the day that changes.

    The third return value is the breakdown, carried so a breach can NAME what
    painted it instead of only reporting that the number rose.
    """
    from rich.cells import cell_len
    from textual.color import Color

    # The RESOLVED accent, never the raw `colors.toml` hex. Textual's colour system
    # shifts some roles — city-783's `accent = "#ad2222"` resolves to `#AC2222` — so
    # a test parsing the theme file counts zero accent cells and passes for the
    # wrong reason (RESEARCH Pitfall 8).
    accent = Color.parse(app.theme_variables["accent"])
    target = (accent.r, accent.g, accent.b)

    hits = 0
    total = 0
    breakdown: dict[tuple[str, str], int] = {}
    for strip in app.screen._compositor.render_strips():
        for text, style, _control in strip:
            width = cell_len(text)
            total += width
            if style is None:
                continue
            foreground = style.color.get_truecolor() if style.color else None
            background = style.bgcolor.get_truecolor() if style.bgcolor else None
            if background is not None and (
                background.red,
                background.green,
                background.blue,
            ) == target:
                hits += width
                breakdown[("background", text[:24])] = (
                    breakdown.get(("background", text[:24]), 0) + width
                )
            elif foreground is not None and (
                foreground.red,
                foreground.green,
                foreground.blue,
            ) == target:
                glyphs = sum(1 for character in text if not character.isspace())
                if glyphs:
                    hits += glyphs
                    breakdown[("color", text[:24])] = (
                        breakdown.get(("color", text[:24]), 0) + glyphs
                    )
    painted = sorted(
        ((channel, text, count) for (channel, text), count in breakdown.items()),
        key=lambda entry: -entry[2],
    )
    return hits, total, painted


def _bottoms(screen, rows: int) -> tuple[int, list[tuple[str, int]]]:
    """``(the lowest row any displayed widget reaches, the ones past ``rows``)``.

    Read off every mounted widget rather than off the ``ControlRow``s alone. The rows
    are what UI-SPEC §7.2 counts, but the widget that falls off the bottom is usually
    not one of them, and naming the offenders is the difference between a red test
    and a red test somebody can act on.
    """
    frame = screen.query_one("#frame")
    # Scoped to the frame and its descendants, not to every widget on the screen.
    # Measured: below about 120 columns Textual's own `HelpPanel` puts a `Static` at
    # row 47 — one row past the window — and that is a third-party widget we mount
    # but do not lay out. A budget control that went red for it would be reporting
    # someone else's overflow as ours, and the first person to see it would weaken
    # the assertion rather than read it.
    bottoms = [
        (widget.id or type(widget).__name__, widget.region.bottom)
        for widget in [frame, *frame.walk_children()]
        if widget.display
    ]
    offenders = sorted(
        ((name, bottom) for name, bottom in bottoms if bottom > rows),
        key=lambda entry: -entry[1],
    )
    return max(bottom for _, bottom in bottoms), offenders


def _assert_fits(screen, rows: int, where: str) -> None:
    """The window budget, as three claims, each armed and each catching what the
    others do not. The measurements are in ``12.1-08-SUMMARY.md``; the short form:

    1. **The content fits its container** — ``#frame`` does not scroll. A composition
       that outgrew the window would scroll rather than look broken, and a silent
       scroll is how a row budget stops being a budget. Fires at **four** extra rows
       of content (not one: the ledger is ``1fr`` and absorbs the first three out of
       its own slack — see the note below). Blind to claims 2 and 3.

       ``virtual_size.height <= container_size.height`` is asserted alongside it and
       is the **same claim** read off the layout instead of the scroll offset. It is
       kept because it states the sizes in the failure message, not because it is
       independent: no arm separated the two, including ``overflow-y: hidden`` on
       ``#frame``, which left ``max_scroll_y`` at 1 with the overrun present.

    2. **The frame fits the window.** ``#frame { height: 50 }`` leaves the content
       fitting perfectly inside an oversized frame — ``max_scroll_y`` stays 0 and
       claim 1 is green — while the frame's bottom edge sits at row 50.

    3. **No widget reaches past the last row.** The only claim that catches a single
       region pushed off the bottom while everything else is fine: ``offset: 0 6`` on
       ``#chips`` puts the whole action strip at row 50 with ``max_scroll_y == 0``,
       ``virtual == container == 44`` and the frame's region exactly right.

    **The blind spot, stated rather than discovered later.** Claims 1 and 2 cannot
    see an overrun the ledger can absorb, which is now bounded at three rows by its
    ``min-height: 4`` — it was the whole region before that. A one-to-three-row
    overrun is caught instead by ``test_dashboard_home.py``'s third claim, the
    ledger-slack assertion, measured firing with one extra row::

        E  AssertionError: no slack left for the 12.2 seam — the ledger has 6 rows
           and the next phase needs 3 of them

    That control and this one are two halves of one guardrail. Neither is sufficient.
    """
    frame = screen.query_one("#frame")
    virtual = frame.virtual_size.height
    container = frame.container_size.height
    lowest, offenders = _bottoms(screen, rows)

    assert frame.max_scroll_y == 0, (
        "%s: the composition outgrew the %d-row window by %d rows — it is scrolling "
        "instead of fitting" % (where, rows, frame.max_scroll_y)
    )
    assert virtual <= container, (
        "%s: the frame's content is %d rows inside a %d-row container"
        % (where, virtual, container)
    )
    assert frame.region.height == rows and frame.region.bottom <= rows, (
        "%s: the frame is not the window — %r against %d rows"
        % (where, frame.region, rows)
    )
    assert lowest <= rows, (
        "%s: %d widget(s) reach past row %d — the lowest is at %d: %s"
        % (where, len(offenders), rows, lowest, offenders[:6])
    )


def test_the_composition_fits_the_sanctioned_window(ng_data_dir):
    """Control 9. The home surface fits 135 × 46 — the window the windowrule pins.

    **Proved able to fail before it was written.** Measured during research on a
    probe composition: 40 rows of content gives ``content_height=46 overflows=False
    max_widget_bottom=40``, 46 rows gives ``content_height=46 overflows=False
    max_widget_bottom=46``, and 60 rows gives ``content_height=60 overflows=True
    max_widget_bottom=60``. It passes at the budget and fails above it, which is the
    discrimination this assertion needed and is why the shape was reused here rather
    than re-derived.

    **A scrollbar is not a valid overflow signal.** ``show_vertical_scrollbar`` was
    measured ``False`` while the content overflowed, because a container only grows
    one when its overflow is ``auto`` or ``scroll``. That is why this reads the
    virtual size and the widget bottoms, and why the string does not appear in this
    module at all.
    """

    async def _body():
        app = _home_app()
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            screen = app.screen
            assert type(screen).__name__ == "StatusScreen", (
                "the home surface is not StatusScreen: %r" % (screen,)
            )
            _assert_fits(screen, SANCTIONED_SIZE[1], "at the sanctioned window")

            # The rows are what UI-SPEC §7.2 counts, so they are named separately —
            # the generic claim above would still pass if every row fitted and some
            # other region did not, and the reverse is the bug that matters here.
            # `CursorStop` and not `ControlRow`: the registry's 16 stops are 15
            # rows plus the hero, which is a stop and is not a row. Querying the
            # rows alone would count 15, and a test that asserted 15 would go green
            # the day the hero stopped composing.
            from ngtui.widgets.cursorstop import CursorStop

            stops = list(screen.query(CursorStop))
            assert len(stops) == 16, (
                "the 16-stop registry did not compose: %d" % len(stops)
            )
            lowest_stop = max(stop.region.bottom for stop in stops)
            assert lowest_stop <= SANCTIONED_SIZE[1], (
                "a cursor stop reaches row %d, past the %d-row window"
                % (lowest_stop, SANCTIONED_SIZE[1])
            )

    asyncio.run(_body())


def test_the_composition_fits_with_the_help_panel_open(ng_data_dir):
    """Control 9, in the state the user can actually put the surface in.

    ``HelpPanel.DEFAULT_CSS`` is ``split: right; width: 33%; min-width: 30;
    max-width: 60``, and ``split`` **takes** space rather than overlaying it. Opening
    the panel therefore leaves the home surface roughly 90 columns wide, not 135.
    That is above the ``-narrow`` threshold, so no class fires and the ``1fr``
    regions simply narrow — but the help chip is a first-class action on this
    surface and the only discoverability left after the framework chrome went, so
    "the layout cannot quietly outgrow the window" has to include the state the help
    chip puts it in. A control that only measured the pristine surface would be
    green on a layout that breaks the moment anyone presses the one key it teaches.

    Asserted before, during and after, because the panel is a ``split`` and closing
    it has to give the space back.

    **Proved able to fail on a bug the plain control cannot see.** A 484-character
    advisory line at ``height: auto`` wraps to 4 rows in the 129-column content area
    and to 6 in the 85-column one. At 135 columns the ledger absorbs the three extra
    rows out of its slack and control 9 stays **green**; with the panel open::

        E  AssertionError: with the help panel open (91 cols): the composition
           outgrew the 46-row window by 2 rows — it is scrolling instead of fitting

    **One finding this control does NOT cover, stated rather than implied.**
    ``StatusScreen.on_resize`` keys on the SCREEN's size, and mounting a ``split``
    panel does not resize the screen — it re-lays out inside it. So the degradation
    classes never see the ~45 columns the panel takes: measured at an 80-column
    terminal, the frame drops to 50 columns with the panel open and ``#frame`` still
    wears no ``-narrow``, so the band stays side by side and its 62-column left half
    clips the right one. At the sanctioned 135 the panel leaves 91 columns, well
    above the 80-column threshold, so the shipped window is unaffected. Recorded in
    ``deferred-items.md``; not fixed here, because the fix is a resize seam on the
    frame rather than on the screen and this plan does not own one.
    """

    async def _body():
        app = _home_app()
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            screen = app.screen
            rows = SANCTIONED_SIZE[1]

            def panels():
                return [
                    widget
                    for widget in app.screen.walk_children()
                    if type(widget).__name__ == "HelpPanel"
                ]

            _assert_fits(screen, rows, "before the help panel was opened")
            width_before = screen.query_one("#frame").region.width

            chip = screen.query_one("#ctl-chip-help")
            chip.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert len(panels()) == 1, "the help chip did not mount a HelpPanel"

            # The premise of this control: the panel really does TAKE the columns.
            # Without this the test could pass on a Textual release that changed
            # `split` to an overlay, and it would pass for the wrong reason —
            # measuring the pristine surface twice.
            width_open = screen.query_one("#frame").region.width
            assert width_open < width_before, (
                "the help panel did not take any columns (%d -> %d) — `split` is no "
                "longer taking space and this control is measuring nothing"
                % (width_before, width_open)
            )
            _assert_fits(screen, rows, "with the help panel open (%d cols)" % width_open)

            await pilot.press("escape")
            await pilot.pause()
            assert panels() == [], "escape did not close the help panel"
            assert screen.query_one("#frame").region.width == width_before, (
                "the help panel did not give its columns back"
            )
            _assert_fits(screen, rows, "after the help panel was closed")

    asyncio.run(_body())


def test_accent_stays_under_five_percent(ng_data_dir):
    """Control 10. The accent reserve is COUNTED, against the screen that is painted.

    UI-SPEC §6.2 keeps the accent to a closed two-item list — one dot beside the
    wordmark, and the verdict word with its countdown when and only when the verdict
    is ``GRACE``. §6.3 turns that into a number, because a list is enforced by
    reviewing every diff forever and a number is enforced by this test.

    The accent is the surface's only attention-grabbing channel. Spending it badly is
    how a real alarm stops being seen on the night it is true (T-12.1-29), and that
    failure is invisible in any single diff — it happens one reasonable-looking
    addition at a time.

    Two claims, and the second is the one that will fire first:

      * the **ceiling**, 310 of 6210 (5 %). Crossing it fails the phase.
      * the **design target**, 62 (1 %). The composition is supposed to spend one
        cell on the dot, so anything approaching 62 means something is painting
        outside the reserve even though the ceiling is nowhere in sight.

    **The composed surface spends 1 cell.** One: the wordmark dot, on a ``locked``
    verdict where the GRACE half of the reserve is not in play. 1 of 6210 is 0.02 %,
    against a 62-cell target and a 310-cell ceiling.

    **Both claims proved able to fail, and they fire independently.** Painting
    ``#frame``'s four borders in ``$accent`` and giving one row an accent background
    takes it to **488 of 6210 (7.86 %)** and trips the ceiling::

        E  AssertionError: the accent covers 488 of 6210 cells (7.86%), past the
           310-cell ceiling (5%). Painted by: [('color', '▔▔▔…', 133),
           ('color', '▁▁▁…', 133), ('background', '   …', 86), ('color', '▏', 44),
           ('color', '▕', 44), ('background', 'status reflects what the', 43), …]

    The accent background row **alone** stays under the ceiling at 130 cells and is
    caught by the design target instead — which is the whole reason the target is
    asserted and not merely written down::

        E  AssertionError: the accent covers 130 of 6210 cells (2.09%) against a
           design target of 62 (1%) — under the ceiling, but the reserve is a closed
           two-item list and something is painting outside it.
    """

    async def _body():
        app = _home_app()
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()

            hits, total, painted = count_accent_cells(app)

            # The total is a claim in its own right, not a sanity check: if it is not
            # 6210 then the surface being measured is not the sanctioned window and
            # every ratio below is against the wrong denominator.
            assert total == SANCTIONED_CELLS, (
                "the rendered surface is %d cells, not the sanctioned %d — the ratio "
                "below would be against the wrong denominator" % (total, SANCTIONED_CELLS)
            )
            assert hits <= ACCENT_CEILING_CELLS, (
                "the accent covers %d of %d cells (%.2f%%), past the %d-cell ceiling "
                "(5%%). Painted by: %s"
                % (hits, total, 100 * hits / total, ACCENT_CEILING_CELLS, painted[:8])
            )
            assert hits <= ACCENT_DESIGN_TARGET_CELLS, (
                "the accent covers %d of %d cells (%.2f%%) against a design target of "
                "%d (1%%) — under the ceiling, but the reserve is a closed two-item "
                "list and something is painting outside it. Painted by: %s"
                % (
                    hits,
                    total,
                    100 * hits / total,
                    ACCENT_DESIGN_TARGET_CELLS,
                    painted[:8],
                )
            )

    asyncio.run(_body())


def test_render_strips_never_reaches_application_code():
    """``_compositor`` is test-only. Enforced, not intended (T-12.1-30).

    ``count_accent_cells`` above reaches into ``app.screen._compositor`` and says in
    its own docstring that this is acceptable in a test against a pinned dependency.
    That sentence is worth nothing on its own — the way a private API leaks is that
    someone reads the test, sees the idiom, and uses it in the app. This is the
    difference between having said so and having enforced it.

    The vacuity guard is not decoration: a scan that silently stopped finding the
    package would pass forever. It fires before the real assertion.
    """
    import ngtui

    package = Path(ngtui.__file__).resolve().parent
    sources = sorted(package.rglob("*.py"))
    assert len(sources) >= 6, (
        "expected the ngtui package to hold at least six modules, found %d at %s — "
        "the scan no longer reaches the package it is meant to guard"
        % (len(sources), package)
    )

    leaked = [
        "%s:%d" % (source.relative_to(package), number)
        for source in sources
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1)
        if "_compositor" in line
    ]
    assert leaked == [], (
        "`_compositor` is Textual private API and is reachable from application "
        "code: %s" % leaked
    )


def test_the_degradation_ladder_keeps_the_hero_and_the_ledger(ng_data_dir):
    """UI-SPEC §7.4: the surface sheds rows in ONE order, and two things never go.

    The windowrule fixes the sanctioned window, but ``ngtui`` can be run in any tiled
    terminal and must not look broken there. Textual has no media queries, so
    ``StatusScreen.on_resize`` toggles classes on ``#frame`` and ``app.tcss`` decides
    what each class drops.

    Three claims:

      * the **triggers** match the contract's table, asserted against the table
        written out in this module rather than against ``status.py``'s own constants.
        Importing those would make the test self-consistent with any values at all —
        the exact shape of blindness this phase kept finding.
      * the **hero is never dropped**, at any size. It is the screen's one idea, and
        a degradation path that takes it has degraded into a different screen. It
        loses its hour axis and its read-out row under ``-compact``, which is the
        contract's own drop order; the ramp row itself stays.
      * the **ledger never goes below 4 rows**. It is the audit record (T-12.1-28).
        Measured before ``min-height: 4`` was added: the ladder runs out of things to
        drop at 31 rows and the ledger then kept shrinking — 3 rows at a 30-row
        terminal, 1 row at 24. Below 31 rows ``#frame`` scrolls instead, which is
        visible; a record quietly squeezed to one line is not.

    This control asserts by MEASUREMENT and not by inspecting the source. A grep for
    a rule that hides the ramp cannot see a ramp dropped by a layout that gives it
    zero rows, which is the way it would actually happen.

    Armed twice. ``#frame.-compact #ctl-ramp { display: none; }``::

        E  AssertionError: the hero has no rows at 135x45: display=False
           region=Region(x=0, y=0, width=0, height=0)

    and the ``-tiny`` trigger mis-set from 43 rows to 40::

        E  AssertionError: at 135x42 the frame wears ['-compact'], and UI-SPEC §7.4
           says ['-compact', '-tiny']
    """

    async def _body():
        for size, expected_classes in DEGRADATION_LADDER:
            app = _home_app()
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                screen = app.screen
                frame = screen.query_one("#frame")

                classes = sorted(
                    name for name in frame.classes if name.startswith("-")
                )
                assert classes == sorted(expected_classes), (
                    "at %dx%d the frame wears %s, and UI-SPEC §7.4 says %s"
                    % (size[0], size[1], classes, sorted(expected_classes))
                )

                ramp = screen.query("#ctl-ramp")
                assert len(ramp) == 1, (
                    "the hero is gone at %dx%d — it is never dropped" % size
                )
                assert ramp[0].display and ramp[0].region.height >= 1, (
                    "the hero has no rows at %dx%d: display=%r region=%r"
                    % (size[0], size[1], ramp[0].display, ramp[0].region)
                )

                ledger = screen.query_one("#ledger")
                assert ledger.region.height >= LEDGER_FLOOR_ROWS, (
                    "the audit ledger is %d rows at %dx%d, below its floor of %d"
                    % (ledger.region.height, size[0], size[1], LEDGER_FLOOR_ROWS)
                )

    asyncio.run(_body())


def test_the_ledger_holds_its_floor_below_the_ladders_last_rung(ng_data_dir):
    """Past the point where there is nothing left to drop, the ledger still holds 4.

    The degradation ladder bottoms out at 31 rows: with ``-compact`` and ``-tiny``
    both set, the fixed rows total 27 and the ledger gets exactly its floor. Below
    that the contract has nothing left to say, and what the layout did — measured —
    was take the remaining rows out of the audit record, because it is the only
    flexible region and flexible regions are where overruns go.

    So the floor is enforced in ``app.tcss`` and the frame scrolls instead. A
    terminal this small cannot show everything; the decision recorded here is WHICH
    thing it refuses to shrink, and it is the record (T-12.1-28, T-12.1-32).

    This is deliberately separate from the ladder control above: that one asserts the
    contract's own table, this one asserts what happens past its edge, and a reader
    who changes the ladder should not have to guess which of the two he broke.

    Armed by removing ``min-height: 4`` — which is what the code did before this
    plan::

        E  AssertionError: the audit ledger is 3 rows at 135x30 — past the ladder's
           last rung it is still the one region that may not give
    """

    async def _body():
        for size in [(135, 30), (135, 28), (135, 24), (135, 20), (60, 24)]:
            app = _home_app()
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                screen = app.screen
                ledger = screen.query_one("#ledger")
                assert ledger.region.height >= LEDGER_FLOOR_ROWS, (
                    "the audit ledger is %d rows at %dx%d — past the ladder's last "
                    "rung it is still the one region that may not give"
                    % (ledger.region.height, size[0], size[1])
                )
                assert screen.query_one("#ctl-ramp").display, (
                    "the hero was dropped at %dx%d" % size
                )

    asyncio.run(_body())
