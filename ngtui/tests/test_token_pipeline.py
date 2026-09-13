"""The token pipeline — shell.toml's structural tokens to the $ng-* variable map.

This module's Pilot-driven controls (2, 3 — consumption and live restyle) arrive
with the plan that wires ``get_css_variables()``. Control 3b lands first and
deliberately needs none of that: ``style_variables()`` is pure, so the whole
hex-free guarantee can be asserted on a dict with no App, no TTY and no repaint.
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
