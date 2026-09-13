"""The composed home surface — the budget, the chrome, the chips, the walk.

Everything in this file mounts the **real** ``StatusScreen`` against the crafted
``ng_data_dir`` (``conftest.py``), not a probe. That is the whole point: plans 05
and 06 proved their mechanisms on probe screens, and the seam this phase kept
finding is the difference between a probe composition and the real one — plan 06's
own handover names it, and control 6d in ``test_dashboard_cursor.py`` exists
because control 6's probe renders every stop as a ``ControlRow`` while the real
screen does not.

``ng_data_dir`` re-points the trust stack at a temp directory and pins true-time, so
none of this reads the author's live guard state (T-12.1-01).

Two harness facts every control here depends on, both measured earlier in this phase:

  * ``app.query(...)`` is scoped to the DEFAULT screen and matches nothing after a
    ``push_screen``. Every query goes through ``app.screen``.
  * A stylesheet parse error surfaces at app **teardown**, after the
    ``async with app.run_test()`` body has run — so a control that only asserts
    inside the block reads green while the stylesheet is broken. Each test here
    exits the block normally, which is what lets the teardown raise.
"""
from __future__ import annotations

import asyncio
import io
import os

from rich.console import Console

from tests.test_ui_harness import SANCTIONED_SIZE

#: UI-SPEC §7.2. Fixed rows total 39 of the 46, so the ledger — the only flexible
#: region — gets 7. Its stated floor is 4, and the 3 rows of slack between them are
#: the seam phase 12.2 takes its hairline, its row and its blank from.
LEDGER_MINIMUM_ROWS = 4


def _home_app():
    """The real ``NightguardApp``, with only its stylesheet path pinned.

    Textual resolves a relative ``CSS_PATH`` against the directory of the module
    where the ``App`` subclass is DEFINED, so a subclass declared in ``tests/``
    inherits the literal ``"app.tcss"`` and dies looking for ``tests/app.tcss``.
    Pinning it to the shipped file is also what keeps these controls honest — they
    assert against the stylesheet that ships.
    """
    from ngtui import app as ngtui_app
    from ngtui.app import NightguardApp

    class _HomeApp(NightguardApp):
        CSS_PATH = os.path.join(
            os.path.dirname(os.path.abspath(ngtui_app.__file__)), "app.tcss"
        )

    return _HomeApp()


def _render(screen) -> str:
    """The screen as the terminal would show it. What is PAINTED, not what was set."""
    console = Console(
        file=io.StringIO(),
        width=screen.size.width,
        height=screen.size.height,
        legacy_windows=False,
    )
    console.print(screen._compositor)
    return console.file.getvalue()


def test_the_home_surface_fits_its_row_budget_and_has_one_flexible_region(ng_data_dir):
    """The composition fits 46 rows, and the ledger is the only thing that gives.

    UI-SPEC §7.2's budget is only meaningful if something checks it. Two independent
    claims, because either alone passes on a broken surface:

    1. **It fits.** ``#frame`` does not scroll — ``max_scroll_y == 0``. A composition
       that outgrew the window would silently scroll rather than look broken, and a
       silent scroll is how a row budget stops being a budget.
    2. **Exactly one region is flexible, and it is the ledger.** Every other row is a
       fixed height. If a second region were ``1fr`` the budget would still "fit" —
       the two would just share the slack — and the ledger could be squeezed below
       its floor without anything going red.

    3. **The ledger keeps its slack.** Its floor is 4 and it gets 7; the 3 in between
       are what 12.2 takes. Without this the first two claims are satisfied by a
       ledger squeezed to exactly 4.

    **Claim 1 alone is blind, and that is measured rather than reasoned.** Armed with
    ONE extra blank row in ``compose()``, ``max_scroll_y`` stayed **0** — the ledger
    is ``1fr``, so it silently absorbed the row and the surface still "fit". What
    fired was claim 3::

        E  AssertionError: no slack left for the 12.2 seam — the ledger has 6 rows
           and the next phase needs 3 of them

    Claim 1 only fires once the overrun is bigger than the ledger's entire slack.
    Armed with TEN extra rows::

        E  AssertionError: the composition outgrew the 46-row budget by 4 rows — it
           is scrolling instead of fitting

    Claim 2 armed by making ``#integrity`` a second ``1fr`` region — a change that
    leaves the surface fitting perfectly::

        E  AssertionError: the ledger must be the only flexible region; these are
           1fr: [('Static', 'integrity'), ('VerticalScroll', 'ledger')]

    Three claims, three different arms, and no two of them catch the same bug.
    """

    async def _body():
        app = _home_app()
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            screen = app.screen
            assert type(screen).__name__ == "StatusScreen", (
                "the home surface is not StatusScreen: %r" % (screen,)
            )

            frame = screen.query_one("#frame")
            assert frame.region.height == SANCTIONED_SIZE[1], (
                "the frame is not the whole window: %r" % (frame.region,)
            )
            assert frame.max_scroll_y == 0, (
                "the composition outgrew the 46-row budget by %d rows — it is "
                "scrolling instead of fitting" % frame.max_scroll_y
            )

            # Claim 2. Scoped to the frame's DIRECT children, because those are the
            # budget's rows. `#state-col` and `#week-col` are `1fr` too and are not
            # a breach: they divide the band's own fixed six rows and cannot take a
            # row from anything above or below them.
            #
            # `1fr` is read off the declared STYLE, not off a measured height: two
            # regions sharing the slack produce perfectly plausible heights, and the
            # claim is about which of them is allowed to give.
            flexible = [
                widget
                for widget in frame.children
                if widget.styles.height is not None
                and widget.styles.height.unit.name == "FRACTION"
            ]
            assert [w.id for w in flexible] == ["ledger"], (
                "the ledger must be the only flexible region; these are 1fr: %s"
                % [(type(w).__name__, w.id) for w in flexible]
            )

            ledger = screen.query_one("#ledger")
            assert ledger.region.height >= LEDGER_MINIMUM_ROWS, (
                "the ledger is below its stated floor of %d rows: %d"
                % (LEDGER_MINIMUM_ROWS, ledger.region.height)
            )
            # The seam for 12.2 is the slack above the floor, and it must be real.
            assert ledger.region.height >= LEDGER_MINIMUM_ROWS + 3, (
                "no slack left for the 12.2 seam — the ledger has %d rows and the "
                "next phase needs 3 of them" % ledger.region.height
            )

            # Nothing is drawn for edits that cannot be staged yet (T-12.1-27).
            painted = _render(screen)
            for lie in ("nothing staged", "staged tray", "no edits staged"):
                assert lie not in painted.lower(), (
                    "the surface claims a tray exists: %r" % lie
                )

    asyncio.run(_body())


def test_the_framework_chrome_is_gone_and_its_bindings_still_fire(ng_data_dir):
    """No ``Header``, no ``Footer``, and ``e r l q`` still reach their actions (D-16).

    The Footer only *rendered* the legend; ``BINDINGS`` are owned by
    ``NightguardApp`` and by the screen. This asserts the two halves separately,
    because "the chrome is gone" and "the bindings survived it" are different claims
    and a surface can satisfy one while breaking the other.

    What is under test is the **dispatch** — that a key press with no Footer mounted
    reaches the named action. What each action then does is
    ``tests/test_port01_single_key_bindings.py``'s subject and is not re-asserted
    here; the actions are recorded rather than run so pressing ``e`` does not push a
    real ``EditScreen`` on top of the surface being measured, and ``q`` does not end
    the app mid-control.
    """
    fired: list[str] = []

    async def _body():
        app = _home_app()
        for name in ("edit", "refresh", "ledger", "quit"):
            setattr(
                type(app),
                "action_%s" % name,
                (lambda n: lambda self: fired.append(n))(name),
            )
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            screen = app.screen

            chrome = [
                type(widget).__name__
                for widget in screen.walk_children()
                if type(widget).__name__ in ("Header", "Footer", "FooterKey")
            ]
            assert chrome == [], "framework chrome is still mounted: %s" % chrome

            # And no bracket hint is painted anywhere (OD-2, UIX-03).
            painted = _render(screen)
            for hint in ("[e]", "[r]", "[l]", "[q]", "^p palette"):
                assert hint not in painted, "a bracket hint is on the surface: %r" % hint

            for key in ("e", "r", "l", "q"):
                await pilot.press(key)
                await pilot.pause()

            assert fired == ["edit", "refresh", "ledger", "quit"], (
                "the single-key bindings did not fire with no Footer mounted: %s"
                % fired
            )

    asyncio.run(_body())


def test_the_help_chip_opens_the_panel_that_replaced_the_legend(ng_data_dir):
    """Discoverability moved to the ``help`` chip, and the panel really lists them.

    The legend is not merely removed — it is relocated. A control that only asserted
    the Footer was gone would pass on a surface with no discoverability at all, which
    is the outcome OD-2 is trading against.

    The panel's contents are read from what is **painted**, not from the widget's
    attributes: the claim is that a user can read the bindings, and an attribute the
    panel happens to hold is not a thing anyone can read.
    """

    async def _body():
        app = _home_app()
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            screen = app.screen

            def panels():
                return [
                    w
                    for w in app.screen.walk_children()
                    if type(w).__name__ == "HelpPanel"
                ]

            assert panels() == [], "the help panel is mounted before it was asked for"

            chip = screen.query_one("#ctl-chip-help")
            chip.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            assert len(panels()) == 1, "the help chip did not mount a HelpPanel"

            painted = _render(app.screen)
            listed = [
                description
                for description in ("Edit a field", "Refresh", "Ledger", "Quit")
                if description in painted
            ]
            assert listed == ["Edit a field", "Refresh", "Ledger", "Quit"], (
                "the help panel does not list the bindings it replaced: %s" % listed
            )

            await app.run_action("hide_help_panel")
            await pilot.pause()
            assert panels() == [], "hiding the panel did not remove it"

    asyncio.run(_body())


def test_exactly_one_chip_is_filled_and_the_accent_stays_on_its_reserve(ng_data_dir):
    """One primary chip, and the accent appears in exactly one painted place.

    Two claims that are easy to conflate and must not be:

    * **One filled chip, ever** (UI-SPEC §10.7). ``edit`` is the primary.
    * **The filled chip does NOT invert to the accent.** It inverts to
      ``$background`` on ``$foreground``. The accent reserve is a closed two-item
      list — one dot beside the wordmark, and the verdict word plus its countdown on
      a GRACE verdict — and a chip is not on it. A control that only counted the
      filled chips would pass on a chip painted in the accent, which is the breach
      that actually happened twice in this phase.

    The accent is compared as a **resolved colour** against
    ``app.theme_variables``, not as the string ``$accent``: the stylesheet is where
    a breach is written, but the resolved colour is where it lands, and the two are
    different questions.

    **The two claims were armed separately and neither arm fires the other's
    assertion** (measured 2026-09-13). A second ``-primary`` chip::

        E  AssertionError: exactly one chip may be filled, and it is `edit`:
           ['ctl-chip-edit', 'ctl-chip-ledger']

    and the one filled chip inverted to ``$accent`` instead of ``$foreground`` —
    still exactly one filled chip, so the count assertion stays green::

        E  AssertionError: the accent reserve is a closed two-item list and this
           paint breaches it: [('wordmark-dot', 'color'),
           ('ctl-chip-edit', 'background')]
    """

    async def _body():
        from textual.color import Color

        app = _home_app()
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            screen = app.screen

            chips = list(screen.query(".chip"))
            assert len(chips) == 5, "the chip strip is not five chips: %r" % chips
            filled = [chip.id for chip in chips if chip.has_class("-primary")]
            assert filled == ["ctl-chip-edit"], (
                "exactly one chip may be filled, and it is `edit`: %s" % filled
            )

            accent = Color.parse(app.theme_variables["accent"])
            wearing_accent = []
            for widget in screen.walk_children():
                colour = widget.styles.color
                background = widget.styles.background
                if colour is not None and colour.rgb == accent.rgb:
                    wearing_accent.append((widget.id, "color"))
                if background is not None and background.rgb == accent.rgb and background.a:
                    wearing_accent.append((widget.id, "background"))

            # The fixture's verdict is `locked`, so the GRACE half of the reserve is
            # not in play and the dot is the only permitted accent on this paint.
            assert wearing_accent == [("wordmark-dot", "color")], (
                "the accent reserve is a closed two-item list and this paint breaches "
                "it: %s" % wearing_accent
            )

    asyncio.run(_body())


def test_the_real_home_surface_walks_all_sixteen_stops(ng_data_dir):
    """Control 6d, against the SHIPPED composition rather than a probe of it.

    ``test_dashboard_cursor.py`` asserts the same property on a screen this test
    file's own docstring explains: a probe built to have the seam in it. This one
    asserts it on what actually ships, so the two together say both "the mechanism
    works" and "the composition uses the mechanism".

    The expected order is read from ``home_controls()`` rather than typed, so it
    cannot drift from the registry — and the ramp's identity is asserted explicitly,
    because a composition that rendered stop 1 as a ``ControlRow`` would walk
    sixteen of sixteen and prove nothing.
    """

    async def _body():
        from ngtui import backend
        from ngtui.widgets.controlrow import ControlRow, home_controls
        from ngtui.widgets.hero import DayRamp

        expected = [
            "ctl-%s" % control.key
            for control in home_controls(backend.sanctioned_config())
        ]
        assert len(expected) == 16

        app = _home_app()
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            screen = app.screen

            ramp = screen.query_one("#ctl-ramp")
            assert isinstance(ramp, DayRamp) and not isinstance(ramp, ControlRow), (
                "stop 1 is not the instrument: %r" % (ramp,)
            )
            assert app.focused is ramp, (
                "the cursor does not start on stop 1: %r" % (app.focused,)
            )

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
                "the shipped home surface does not walk its own registry\n"
                "walked:   %s\nexpected: %s" % (walked, expected)
            )

    asyncio.run(_body())


def test_a_frozen_row_cannot_reach_the_editor_from_the_shipped_surface(ng_data_dir):
    """The refusal seam, on the real screen: four rows are frozen and stay frozen.

    Plan 12.1-05 made a refused row post ``Refused`` rather than ``Activated`` so a
    screen handler that opens the editor is *structurally* unreachable from one of
    the four frozen keys. That was proved on the registry and on a probe. This asks
    the shipped composition, which is where the handler actually lives — a screen
    that happened to route ``Refused`` into the editor too would have passed every
    control written so far (T-12.1-15, T-12.1-25).

    Both halves are asserted, and the routed half is not a courtesy: a control that
    only checked the frozen row would also pass on a surface where *no* row reaches
    the editor, which is a different bug wearing the same green.
    """
    opened: list[str] = []

    async def _body():
        app = _home_app()
        type(app).action_edit = lambda self: opened.append("edit")
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()
            screen = app.screen

            frozen = screen.query_one("#ctl-mode")
            assert frozen.control.is_refused, "the `mode` row is not the frozen one"
            frozen.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert opened == [], (
                "a frozen row reached the editor — the seam is a message TYPE, and "
                "this composition routed around it: %s" % opened
            )

            routed = screen.query_one("#ctl-curfew")
            assert routed.control.route == "curfew.start"
            routed.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert opened == ["edit"], (
                "a routed row did not reach the editor: %s" % opened
            )

    asyncio.run(_body())
