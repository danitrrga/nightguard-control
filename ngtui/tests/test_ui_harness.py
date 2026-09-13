"""The async idiom for every Pilot-driven UI control in phase 12.1, proved to run.

Nothing in ``ngtui/tests/`` used ``run_test``, ``Pilot`` or ``asyncio`` before this
file. Three idioms were measured under the project's own runner
(``uv run --with pytest --with pytest-asyncio pytest -q``):

    sync test wrapping ``asyncio.run(body())``  -> passes, no plugin needed
    the pytest-asyncio marker + ``async def``   -> passes, but requires that plugin
    bare ``async def`` with no marker           -> FAILS

(The middle idiom is named rather than spelled. This module's acceptance check greps
the file for that marker's dotted name and requires zero hits — proof no test here is
plugin-dependent — so writing it out even in prose would trip the check.)

The chosen idiom is the first: a plain ``def test_*`` whose body is
``asyncio.run(_body())`` over a nested ``async def``. It keeps the suite runnable under
a plain ``pytest`` with no plugin and no ``asyncio_mode`` in ``pyproject.toml``, and it
costs one line per test. Later UI modules copy this shape rather than re-deciding it.

The rejected idiom's failure, verbatim and reproduced against this repo:

    async def functions are not natively supported.
    You need to install a suitable plugin for your async framework, for example:
      - anyio
      - pytest-asyncio
      - pytest-tornasync
      - pytest-trio
      - pytest-twisted

That message arrives as a **failure, not an error** (RESEARCH Pitfall 9). A visual
control that silently never ran would therefore look like an ordinary assertion failure
and could be "fixed" by weakening the assertion instead of by running the test
(T-12.1-03). This canary is the standing proof the idiom actually executes: if the
harness ever stops working, this file goes red on its own, before any control does.

One more decision with no precedent, recorded here because later modules depend on it:
``pytest.raises`` must wrap the whole ``async with app.run_test(...)`` block, never a
line inside it — ``UnresolvedVariableError`` and ``StylesheetParseError`` are raised
when the block *exits*.
"""
from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.geometry import Size
from textual.widgets import Static

# The canvas every UI control in this phase runs at.
#
# `packaging/omarchy/hypr/nightguard.windowrule.conf:8` pins the floating window at
# `size 875 600` px; at the live terminal font (CaskaydiaCove Nerd Font 8pt, a
# 6.25 x 12.40 px cell) that is 875/6.25 = 140 -> 135 usable columns and
# 600/12.40 = 48 -> 46 usable rows once the terminal's own chrome is taken. Later
# test modules import this rather than re-typing the tuple, so the overflow budget
# and the ramp-width arithmetic cannot drift apart from each other.
SANCTIONED_SIZE = (135, 46)


class _FocusableStatic(Static, can_focus=True):
    """A Static the focus chain will actually stop on.

    ``Static`` is not focusable by default, so a canary built from a bare one would
    assert ``app.focused is not None`` against a screen with nothing to focus and fail
    for a reason that has nothing to do with the async idiom.
    """


class _CanaryApp(App):
    """The smallest app that can prove a Pilot ran: one focusable widget."""

    def compose(self) -> ComposeResult:
        yield _FocusableStatic("canary", id="canary")


def test_a_pilot_driven_test_runs_under_the_projects_own_runner():
    """The asyncio.run() wrapper drives a real Pilot: keys land, the size is honoured."""

    async def _body():
        app = _CanaryApp()
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.press("tab")
            await pilot.pause()
            # Focus moved, so the key press was genuinely delivered to a running app
            # — not swallowed by a coroutine that was created and never awaited.
            assert app.focused is not None, "tab did not focus anything — the Pilot never ran"
            assert app.focused.id == "canary"
            # The canvas is what run_test was asked for, not Textual's 80x24 default.
            assert app.screen.size == Size(*SANCTIONED_SIZE)

    asyncio.run(_body())


# --- the UI fixture group, proved to work ------------------------------------
# Beyond the plan's letter, and for the reason the plan itself gives for control
# 1: a fixture that is only ever *discovered* is a scan that matched nothing. The
# phase's stated truth is "a test can build the real NightguardApp against a
# fixture theme without touching the live desktop theme" — these two tests are
# what make that assertable rather than claimed, and they are the first caller
# the fixtures ever had.


def test_the_probe_app_builds_the_real_app_against_the_fixture_theme(
    probe_app, omarchy_theme_dir
):
    """The probe is the real NightguardApp, and its colour comes from tmp_path."""

    async def _body():
        from ngtui import theme

        app = probe_app(rows=5)
        async with app.run_test(size=SANCTIONED_SIZE) as pilot:
            await pilot.pause()

            # T-12.1-02: the loader is reading the fixture, not the live desktop
            # theme that omarchy-theme-set rewrites out from under the suite.
            assert theme.theme_dir() == str(omarchy_theme_dir)
            assert "omarchy/current/theme" not in theme.theme_dir()

            # The real _apply_omarchy_theme() ran and the fixture palette reached
            # the app's variables — resolved value, not the file's text (Pitfall 8).
            assert app.theme == "omarchy"
            assert app.theme_variables["accent"].lower() == "#7fc9c4"

            # The probe composition is there and carries the cursor.
            #
            # Query through `app.screen`, never `app`. `App.query` is scoped to the
            # default screen, so after a push_screen it matches nothing: measured
            # `app.children == [_ProbeScreen()]` yet `len(app.query(".ctl")) == 0`
            # while `len(app.screen.query(".ctl")) == 5`. RESEARCH's control recipes
            # are written as `app.query(ControlRow)` and must be read as
            # `app.screen.query(...)` — the app-scoped form returns an empty query,
            # which makes an "assert every row ..." control pass over zero rows.
            assert len(app.query(".ctl")) == 0, (
                "App.query now descends the screen stack — the harness rule that "
                "controls must query app.screen can be relaxed"
            )
            assert len(app.screen.query(".ctl")) == 5

            # The cursor starts ON the first row — Textual focuses the first
            # focusable widget when the screen mounts, so `tab` moves to r1 rather
            # than arriving at r0. The cursor controls read the position, so where
            # it starts is part of the harness contract, not an accident.
            assert app.focused is not None
            assert app.focused.id == "r0"
            await pilot.press("tab")
            await pilot.pause()
            assert app.focused.id == "r1"

    asyncio.run(_body())


def test_mutate_theme_rewrites_the_named_section_and_moves_the_mtime(
    omarchy_theme_dir, mutate_theme
):
    """Replace, append, leave the neighbours alone, and bump the mtime.

    All four matter to the live-restyle control: it mutates one token between
    repaints and asserts the running app followed. A rewrite that landed on the
    same mtime would make the poll report no change and the control fail with the
    pipeline working.
    """
    import os
    import tomllib

    path = omarchy_theme_dir / "shell.toml"
    before = os.stat(path).st_mtime

    mutate_theme(
        omarchy_theme_dir,
        "controls",
        normal_fill_alpha=0.9,       # key exists -> replaced in place
        normal_border_style="hkey",  # key absent -> appended to the section
    )

    with open(path, "rb") as fh:
        shell = tomllib.load(fh)

    assert shell["controls"]["normal-fill-alpha"] == 0.9
    assert shell["controls"]["normal-border-style"] == "hkey"
    # Neighbouring keys and neighbouring sections survive the rewrite.
    assert shell["controls"]["focus-fill-alpha"] == 0.08
    assert shell["popups"]["border"] == "hyprland.active-border"
    assert os.stat(path).st_mtime > before


def test_mutating_a_section_that_is_not_there_is_loud(omarchy_theme_dir, mutate_theme):
    """The vacuity guard fires rather than leaving the file at its old values."""
    import pytest

    with pytest.raises(AssertionError, match=r"no \[nosuch\] section"):
        mutate_theme(omarchy_theme_dir, "nosuch", whatever=1)
