"""The token pipeline — shell.toml's structural tokens to the $ng-* variable map.

Three controls, deliberately at three different depths:

- **3b** (``test_style_variables_is_pure_and_hex_free``) is pure. No App, no TTY,
  no repaint — ``style_variables()`` is a dict in, a dict out, so the whole
  hex-free guarantee is assertable one layer below the thing it protects.
- **2** (``test_controls_fill_alpha_reaches_the_row``) runs a real app and asks
  whether a theme's fill alpha reached a *rendered* row. It is the first test
  that can fail because of ``app.tcss``.
- **3** (``test_live_restyle_changes_the_border_style``) asks whether a *running*
  app follows a theme change — and asks it about a border STYLE, because a
  colour-only pipeline passes a colour-only test.

None of the three reads the live desktop theme: all take ``omarchy_theme_dir``,
which monkeypatches ``theme.OMARCHY_THEME_DIRS`` at the module attribute. A
control that read the live omarchy state directory would be rewritten out from
under itself by ``omarchy-theme-set`` (T-12.1-02).
"""
from __future__ import annotations

from ngtui.theme import BORDER_STYLES, omarchy_style, style_variables


def test_style_variables_is_pure_and_hex_free(omarchy_theme_dir, mutate_theme, monkeypatch):
    """Every $ng-* value is a plain string, and none of them is a $-reference.

    **Why this is the load-bearing assertion and not a tidiness check.** Textual
    substitutes variables at the token level but *not recursively*, so a variable
    whose value is itself a role reference does not degrade — it kills the app at
    stylesheet parse::

        StylesheetParseError — Invalid value ('$foreground') for the background property

    That happens during ``App.__init__``, before anything is on screen, so there is
    no partially-styled TUI to notice it in. The cost of catching it here is one
    pure call; the cost of not catching it is an afternoon.

    **Negative control, run 2026-09-13.** With ``style_variables`` prefixing every
    ``ng-fill-*`` with ``$foreground``, this test failed on the first key in sorted
    order — ``cursor``, not ``normal``::

        E       AssertionError: $ng-fill-cursor is '$foreground 8%' — a variable
                value may not be a $-reference (substitution is not recursive)
        E       assert not True

    The downstream failure is **measured, not predicted**: an ``App`` whose
    ``get_css_variables()`` returns ``{"ng-fill-normal": "$foreground 4%"}`` and
    whose CSS reads ``background: $ng-fill-normal`` raises
    ``StylesheetParseError`` carrying the ``Invalid value ('$foreground')`` line
    quoted above. That is the next plan's layer; this test catches it one layer
    earlier, where it is a pure call instead of an app that will not start.

    ``hypr_rounding`` is monkeypatched out: this test must not shell out, and the
    radius is an input to the assertion (it selects the border-style family), not
    a property of the box the suite happens to run on.
    """
    from ngtui import theme as theme_mod

    monkeypatch.setattr(theme_mod, "hypr_rounding", lambda *_a, **_k: 0)
    variables = style_variables(omarchy_style())

    # Vacuity guard, the house idiom: a mapper returning {} would pass every
    # assertion below. The map is the five rungs x five tokens, selection, the six
    # surfaces, the radius and its style family.
    assert len(variables) >= 30, "the $ng-* map collapsed: %r" % sorted(variables)

    for name, value in sorted(variables.items()):
        assert isinstance(value, str), "$%s is %r, not a str" % (name, type(value))
        assert not value.startswith("$"), (
            "$%s is %r — a variable value may not be a $-reference "
            "(substitution is not recursive)" % (name, value)
        )

    # Alphas are BARE PERCENTS, so app.tcss can write
    # `background: $ng-color-normal $ng-fill-normal;` with no hex in the file.
    alphas = [k for k in variables if k.startswith("ng-fill-") or k.endswith("-a")]
    assert alphas, "no alpha variables emitted"
    for name in alphas:
        value = variables[name]
        assert value.endswith("%"), "$%s is %r, not a bare percent" % (name, value)
        assert value[:-1].isdigit(), "$%s is %r, not a bare percent" % (name, value)

    # The generated fixture pins normal-fill-alpha = 0.42 — a value no real theme
    # ships, so a pipeline that ignored [controls] would land on the 0.04 default
    # and be caught here rather than passing on a rounding difference.
    assert variables["ng-fill-normal"] == "42%"

    # The border style is chosen by the radius family (§9.2), never hardcoded.
    assert variables["ng-border-style"] in BORDER_STYLES
    assert variables["ng-radius"] == "0"
    assert variables["ng-border-style"] == "hkey", "radius 0 is the hairline family"

    # Colours are resolved, because two installed themes pin per-state colours
    # that are not the palette foreground. This is the one place the pipeline
    # legitimately holds a hex — produced from the live theme at runtime.
    for name in [k for k in variables if k.startswith("ng-color-")] + [
        "ng-popup-bg", "ng-popup-text", "ng-popup-border",
        "ng-tip-bg", "ng-tip-text", "ng-tip-border",
    ]:
        value = variables[name]
        assert value.startswith("#") and len(value) in (4, 7, 9), (
            "$%s is %r, not a resolved colour — the next plan's stylesheet reads "
            "the $ng-* map, so a missing one is UnresolvedVariableError at compose"
            % (name, value)
        )

    # The width clamp. city-783 ships focus-border-width = 2; a grid has no
    # sub-cell borders and D-05 forbids a state growing the box, so the only
    # honest answer is 1 rather than a reflowed row.
    #
    # Asserted at BOTH layers on purpose. Measured 2026-09-13: with the clamp
    # removed from omarchy_style alone the end-to-end assertion still passes
    # (style_variables clamps again), and with it removed from style_variables
    # alone it also passes (omarchy_style already clamped) — only removing both
    # fires. One assertion therefore cannot say *which* layer holds the
    # invariant, which is the same blindness test_hypr_rounding_fails_closed
    # records for its mode 2. Two assertions make each layer observable.
    assert variables["ng-border-focus-w"] == "1"
    mutate_theme(omarchy_theme_dir, "controls", focus_border_width=2)

    parsed = omarchy_style()
    assert parsed["control_focus_border_width"] == 1, (
        "the parser must clamp where it reads the token, not leave it to the "
        "mapper: %r" % parsed["control_focus_border_width"]
    )

    clamped = style_variables({**parsed, "control_focus_border_width": 2})
    assert clamped["ng-border-focus-w"] == "1", (
        "the mapper must clamp its own input — style_variables takes an arbitrary "
        "dict and the one-cell width is a contract of the variable, not of the "
        "parser: %r" % clamped["ng-border-focus-w"]
    )

    # And the clamp is a clamp, not a constant: the fixture's
    # selected-border-width = 0 must survive as 0, or "fill only" becomes
    # unexpressible.
    assert clamped["ng-border-selected-w"] == "0"



async def _settled_background(pilot, row):
    """``row.styles.background`` once the ``.ctl`` fill cross-fade has finished.

    ``styles.background`` is the **animated** value. ``.ctl`` declares
    ``transition: background 120ms``, so the row Textual focuses on mount
    cross-fades from the normal rung to the cursor rung, and a sample taken
    before the fade ends returns an intermediate frame. ``pilot.pause()`` waits
    for the message queue; the animator runs on a timer and is not on it.

    **Textual's own two wait helpers do not work here, and that is measured, not
    assumed.** ``Animator.start()`` sets ``_idle_event`` AND ``_complete_event``
    unconditionally, and it runs *after* the first ``_animate`` — traced::

        TRACE [('_animate', 'background'), ('start', 1)]

    ``start`` sees one animation already in ``self._animations`` and sets both
    events over it, so for the first animation of an app's life
    ``pilot.wait_for_animation()`` and ``pilot.wait_for_scheduled_animations()``
    both return immediately. Sampled mid-fade with an animation in flight::

        pause        bg=0.2674 anims=1 idle=True complete=True being=True
        wait_anim    bg=0.2674 anims=1 idle=True complete=True being=True
        wait_sched   bg=0.1255 anims=1 idle=True complete=True being=True

    So settlement is established two independent ways, and either alone is
    enough:

    1. **Sleep out the fade, derived from the stylesheet** — the duration comes
       from ``styles.transitions["background"]``, never typed, so retuning the
       transition in ``app.tcss`` retunes this wait with it.
    2. **Ask the animator** — ``is_being_animated`` is keyed on
       ``styles.base``, which is the object ``Stylesheet.replace_rules`` hands
       to ``animator.animate``. This is the tight bound and it is also the
       vacuity guard's opposite number: if the key were wrong and this check
       were always False, leg 1 has already waited a full fade.
    """
    transition = row.styles.transitions.get("background")
    assert transition is not None, (
        "%s declares no background transition — this helper exists to settle "
        "past one, and without it the sample is unguarded" % row.id
    )
    fade = transition.duration + transition.delay
    animator = row.app.animator
    for _ in range(16):
        await pilot.pause(fade)
        if not animator.is_being_animated(row.styles.base, "background"):
            return row.styles.background
    raise AssertionError(
        "the fill cross-fade on %s never settled in %d x %.3fs — the animator "
        "still reports it in flight" % (row.id, 16, fade)
    )


def test_controls_fill_alpha_reaches_the_row(probe_app, omarchy_theme_dir, monkeypatch):
    """Control 2 — a theme's [controls] fill alpha reaches a RENDERED row.

    The fixture pins ``normal-fill-alpha = 0.42``, a value no real theme ships,
    so a pipeline that ignored ``[controls]`` would land on the ``0.04`` default
    and be caught here rather than passing on a rounding difference. The
    assertion is on the widget's **resolved** ``styles.background``, never on the
    theme file's text — Textual's colour system shifts some values on the way in.

    **Negative control, measured 2026-09-13.** With ``style_variables`` passing
    ``None`` instead of ``style.get("%s_fill_alpha")`` — i.e. the colour-only
    pipeline, ``[controls]`` ignored — this fires exactly as the plan predicted::

        E  AssertionError: the fixture's normal-fill-alpha did not reach the row:
           Color(169, 192, 191, a=0.04)
        E  assert 0.04 == 0.42

    ``theme.py`` was restored byte-identical afterwards (``diff -q`` empty).

    **The rung matters, and the plan's recipe picks the wrong row.** Textual
    focuses the first focusable widget when a screen mounts, so ``rows[0]``
    carries the cursor and paints ``$ng-fill-cursor``. Asserting the idle rung on
    ``rows[0]`` fails with ``assert 0.08 == 0.42`` **on a fully working
    pipeline** — a red that reads like a broken pipeline and is really a broken
    test. That was measured before this docstring was written, which is why the
    idle assertion is on ``rows[1]`` and the ``app.focused is rows[0]`` guard is
    above it: if the harness ever stops focusing on mount, this test says so
    instead of quietly changing which rung it measures.

    Both rungs are asserted because one alone cannot distinguish "the ladder is
    wired" from "every row paints the same fill".

    **The flake, and which assertion it was actually on (fixed 2026-09-13).**
    This control failed on roughly a fifth of runs — measured at 3/20 in
    isolation, and plan 12.1-06 measured 4/10 with its own files removed from the
    tree, so it never depended on anything downstream. ``deferred-items.md``
    attributed it to the **idle** read, ``rows[1].styles.background``. That was
    wrong: every captured failure was on the **cursor** read, and the value was
    always between the two rungs::

        E  AssertionError: the focused row is not on the cursor rung:
           Color(169, 192, 191, a=0.2206199511291925)
        E  assert 0.2206 == 0.08
        E  ... a=0.26817870630649854 / a=0.12513740546205854 on two other runs

    0.42 → 0.08 is exactly the ``.ctl`` fill cross-fade, and 0.22 / 0.27 / 0.13
    are frames of it. ``rows[1]`` is idle and is never animated, which is why it
    never flaked. The cause is the one plan 12.1-05 recorded — ``styles.background``
    is the ANIMATED value and ``pilot.pause()`` does not wait for the animator —
    but the assertion it lands on is the one that changes rung on mount, not the
    one that stays put.

    Fixed by :func:`_settled_background`, which settles past the fade two
    independent ways. Textual's own ``pilot.wait_for_scheduled_animations()``
    was tried first and measured **insufficient** — 23/30 — for the reason that
    function's docstring records.
    """
    import asyncio

    from textual.color import Color

    from test_ui_harness import SANCTIONED_SIZE

    from ngtui import theme as theme_mod

    monkeypatch.setattr(theme_mod, "hypr_rounding", lambda *_a, **_k: 0)

    async def _body():
        app = probe_app(rows=3)
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()

            # Query through app.screen, never app: App.query is scoped to the
            # DEFAULT screen and returns 0 after a push_screen, which would make
            # an "assert every row..." control pass over nothing.
            rows = list(app.screen.query(".ctl"))
            assert len(rows) == 3, "the probe composition collapsed: %r" % rows

            # The harness contract: Textual focuses the first focusable widget on
            # mount, so rows[0] carries the cursor and rows[1] is idle. Asserting
            # the idle rung on rows[0] measures the CURSOR rung instead and fails
            # with `assert 0.08 == 0.42` on a working pipeline.
            assert app.focused is rows[0], "the cursor is not where the harness puts it"

            expected = style_variables(omarchy_style())

            idle = await _settled_background(pilot, rows[1])
            assert round(idle.a, 4) == 0.42, (
                "the fixture's normal-fill-alpha did not reach the row: %r" % (idle,)
            )
            assert idle.rgb == Color.parse(expected["ng-color-normal"]).rgb

            cursor = await _settled_background(pilot, rows[0])
            assert round(cursor.a, 4) == 0.08, (
                "the focused row is not on the cursor rung: %r" % (cursor,)
            )
            assert round(cursor.a, 4) != round(idle.a, 4)

    asyncio.run(_body())


def test_live_restyle_changes_the_border_style(
    probe_app, omarchy_theme_dir, mutate_theme, monkeypatch
):
    """Control 3 — a live restyle moves a border STYLE on a running app.

    Assert on the **style**, not the colour: a colour-only pipeline passes a
    colour-only test, which is the entire reason this control exists. The style
    family is ``$ng-border-style``, driven by the compositor's live
    ``decoration:rounding`` — ``hkey`` at radius 0, ``round`` above it — so
    ``hypr_rounding`` is the seam that moves it, not a ``shell.toml`` key.
    (The plan's recipe says to move ``[controls] normal-border`` to a different
    border style. That token is a **colour**: ``omarchy_style`` resolves it
    through ``_resolve_border`` / ``_color_word`` and no ``*-border-style`` key
    is read anywhere. Moving it can only change a colour, so that recipe cannot
    assert what it set out to assert.)

    All three halves of the pipeline are moved in one repaint — the structural
    file read, the compositor read, and the palette — because each is carried by
    a different statement of ``_apply_omarchy_theme`` and an end-to-end assertion
    over all three cannot say which one rotted.

    **Negative control, measured 2026-09-13 — the shipped no-op reproduced.**
    With ``_apply_omarchy_theme`` reverted to its shipped two-statement body
    (``register_theme(...)`` + ``self.theme = "omarchy"``, no ``refresh_css``),
    nothing moved::

        BEFORE border=('hkey', Color(169, 192, 191, a=0.12))
               fill=Color(169, 192, 191, a=0.42) accent='#7FC9C4'
        AFTER  border=('hkey', Color(169, 192, 191, a=0.12))
               fill=Color(169, 192, 191, a=0.42) accent='#7FC9C4'
        changed? border=False fill=False accent=False

        E  AssertionError: the border STYLE did not move — a colour-only pipeline
           passes a colour-only test, which is the entire reason this control
           asserts on style: 'hkey'
        E  assert 'hkey' != 'hkey'

    All three legs stay put, which is why the first assertion short-circuiting
    the other two costs nothing here.

    **Each statement was armed separately, so none of the four is redundant:**

    - drop ``self._style = omarchy_style()``: ``border=False fill=False
      accent=True`` — the structural half goes stale while the palette still
      moves. That is precisely the colour-only failure this control is for, and
      the border assertion catches it.
    - drop ``self.register_theme(...)``: dies loudly with
      ``textual.app.InvalidThemeError: Theme 'omarchy' has not been registered``
      on the FIRST call. Worth knowing: that exception is NOT in
      ``_apply_omarchy_theme``'s four-exception tuple, so it propagates rather
      than degrading.
    - drop ``self.refresh_css(animate=False)``: the triple above.

    Restored, the same run gives ``border=True fill=True accent=True``:
    ``hkey`` -> ``round``, ``a=0.42`` -> ``a=0.61``, ``#7FC9C4`` -> ``#123456``.
    ``app.py`` was restored byte-identical after every arming.
    """
    import asyncio
    import re

    from textual.widgets import Static

    from test_ui_harness import SANCTIONED_SIZE

    from ngtui import theme as theme_mod

    radius = {"value": 0}
    monkeypatch.setattr(theme_mod, "hypr_rounding", lambda *_a, **_k: radius["value"])

    async def _body():
        app = probe_app(rows=3)
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()

            # The probe screen composes only .ctl rows, and a .ctl row's spine is
            # a LITERAL vkey by design — D-05 reserves the same one-column border
            # in every state, so its style must never move. The style FAMILY seam
            # is $ng-border-style, and the shipped rule that consumes it is
            # `.panel`. Mount one rather than assert on a widget that cannot move.
            region = Static("region", classes="panel")
            await app.screen.mount(region)
            await pilot.pause()

            before_style = region.styles.border.top[0]
            before_fill = round(list(app.screen.query(".ctl"))[1].styles.background.a, 4)
            before_accent = app.theme_variables["accent"]
            assert before_style == "hkey", "radius 0 is the hairline family: %r" % (
                region.styles.border.top,
            )
            assert before_fill == 0.42

            # Move all three halves of the pipeline at once: the structural file
            # read ([controls] fill alpha), the compositor read (the radius, which
            # selects the border-style FAMILY) and the palette (colors.toml).
            mutate_theme(omarchy_theme_dir, "controls", normal_fill_alpha=0.61)
            radius["value"] = 8
            colors = omarchy_theme_dir / "colors.toml"
            text = colors.read_text(encoding="utf-8")
            moved = re.sub(r'(?m)^accent\s*=.*$', 'accent = "#123456"', text)
            assert moved != text, "the fixture colors.toml has no accent line to move"
            colors.write_text(moved, encoding="utf-8")

            app._apply_omarchy_theme()
            await pilot.pause()

            after_style = region.styles.border.top[0]
            after_fill = round(list(app.screen.query(".ctl"))[1].styles.background.a, 4)
            after_accent = app.theme_variables["accent"]

            assert after_style != before_style, (
                "the border STYLE did not move — a colour-only pipeline passes a "
                "colour-only test, which is the entire reason this control asserts "
                "on style: %r" % (after_style,)
            )
            assert after_style == "round", (
                "a non-zero radius selects the round family: %r" % (after_style,)
            )
            assert after_fill == 0.61, "the fill alpha did not re-read: %r" % after_fill
            assert after_accent != before_accent, (
                "the palette did not re-read: %r" % after_accent
            )

    asyncio.run(_body())
