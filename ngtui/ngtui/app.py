"""NightguardApp — the runnable TUI shell wired to the live status surface + theme.

Wave 2 turns the Wave-1 placeholder shell into the real home app:
- registers the live omarchy ``Theme`` on mount and repaints the running TUI when
  the desktop theme changes (D-04/D-05) — detected by an mtime poll on the 1s tick;
- shows the read-only ``StatusScreen`` as home (D-10);
- a 1s interval refreshes ONLY the countdown cell (the status word/meter never
  re-render on tick — UI-SPEC) and drives the theme watch.

The EditScreen (anti-impulse preview + inline-sudo commit) lands in Wave 3; here
``action_edit`` is a stub. The module imports cleanly without a TTY (the interactive
run is a human/verifier walkthrough).
"""
from __future__ import annotations

from textual.app import App

from ngtui.theme import (
    ThemeWatch,
    load_omarchy_theme,
    omarchy_style,
    style_variables,
)
from ngtui.widgets.edit import EditScreen
from ngtui.widgets.status import StatusScreen


class NightguardApp(App):
    """Single sanctioned editor — omarchy Textual thin client over the trust stack."""

    TITLE = "Nightguard Control"
    CSS_PATH = "app.tcss"

    # Omarchy's kit uses `ToolTip { delay: 400 }` (Ui/Button.qml). Textual's
    # default is 0.5, which is close enough to look deliberate if it is missed —
    # which is exactly why it is set explicitly rather than left to the default
    # (D-15, UI-SPEC §8.5).
    TOOLTIP_DELAY = 0.4

    # Bindings live on StatusScreen (the home surface); kept here too because
    # `tests/test_port01_single_key_bindings.py:29-50` reads `app.BINDINGS`
    # directly — that test is what pins them to this class. It never touches the
    # Footer, so the bindings stay valid when the Footer goes (OD-2).
    BINDINGS = [
        ("e", "edit", "Edit a field"),
        ("r", "refresh", "Refresh"),
        ("l", "ledger", "Ledger"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        # BEFORE super().__init__(), and that order is load-bearing rather than
        # stylistic. `App.__init__` builds the stylesheet with
        # `Stylesheet(variables=self.get_css_variables())` (textual/app.py:729),
        # so any state `get_css_variables()` reads must already exist by then.
        # Assigning `_style` after the super call — the natural order, and the
        # order this file used until now — raises
        # `AttributeError: 'NightguardApp' object has no attribute '_style'`
        # during construction, before any screen exists, so it reads as an
        # import-time crash rather than a styling problem (RESEARCH Pitfall 3).
        self._style = omarchy_style()
        super().__init__()
        # Watch the live omarchy colours.toml + shell.toml for desktop-theme
        # swaps (D-05). Either file moving is a restyle signal.
        self._theme_watch = ThemeWatch()

    def get_css_variables(self) -> dict[str, str]:
        """Textual's own extension point — the `$ng-*` structural tokens (UIX-01).

        This is called during `App.__init__` and again from every
        `refresh_css()`, which is what makes it the right seam: the tokens exist
        on the FIRST stylesheet parse, so `app.tcss` can reference `$ng-*`
        without the app dying at compose.

        The naive route — registering a `Theme` in `on_mount` and referencing
        `$ng-*` from `app.tcss` — does not work: the stylesheet is parsed before
        `on_mount` runs and raises `UnresolvedVariableError: reference to
        undefined variable '$ng-border-normal'`. Do not wire it that way.

        `style_variables()` is pure and Textual-free; everything it guarantees
        (every value a plain string, never a `$`-reference — substitution is not
        recursive) is asserted in `tests/test_token_pipeline.py` without an App.
        """
        variables = super().get_css_variables()
        variables.update(style_variables(self._style))
        return variables

    def on_mount(self) -> None:
        """Register the live omarchy theme, show StatusScreen, start the 1s tick."""
        self._apply_omarchy_theme()
        self.push_screen(StatusScreen())
        # Reuse a single 1s interval for both the countdown and the theme poll.
        self.set_interval(1.0, self._tick)

    # --- theme (D-04/D-05) ---

    def _apply_omarchy_theme(self) -> None:
        """Re-read the desktop's structure AND palette, then repaint — four statements.

        **Re-assigning `App.theme` repaints nothing**, and the claim that it does
        (which this docstring used to make) was measured false on the installed
        Textual. `App.theme` is a plain `Reactive` with `always_update` unset
        (textual/app.py:560), so assigning the same string never fires
        `_watch_theme` — and `_watch_theme` is the ONLY caller of `refresh_css`.
        Measured across a theme swap using the old two-statement body: the border
        stayed ``('hkey', Color(169, 192, 191, a=0.4))``, the fill stayed
        ``a=0.04`` and the accent stayed ``#7FC9C4``. All three unchanged.

        The order below is the measured minimum, and each line earns its place:

        1. `omarchy_style()` — re-read the structure. Without it the refresh
           re-runs `get_css_variables()` over a stale `_style`.
        2. `register_theme(...)` — re-read the palette. Must come BEFORE the
           refresh: with `refresh_css` alone the accent stayed at its old value.
        3. `self.theme = "omarchy"` — a no-op after the first call, kept for the
           first, where it is what selects the theme at all.
        4. `refresh_css(animate=False)` — the statement that does the work. It
           internally runs set_variables(get_css_variables()) -> a stylesheet
           re-parse -> a stylesheet update over the app -> a screen layout
           refresh -> that same update for every OTHER screen in the stack.
           Calling any of those by hand instead would skip the other-screens
           pass, so this file has exactly one repaint call site and nothing
           else. `animate=False` matches Textual's own `_watch_theme` and avoids
           cross-fading the whole surface on a swap.

        `refresh_css()` re-parses the entire stylesheet, so this must stay gated
        on `ThemeWatch.changed()` in `_tick` and never run per tick (T-12.1-12).

        If the live theme files are unreadable, keep the current styling rather
        than crash (T-10-07 — cosmetic, low impact). `refresh_css` reparses into
        a fresh `Stylesheet` and keeps the old one on error, so a malformed theme
        degrades rather than taking the app down.
        """
        try:
            self._style = omarchy_style()
            self.register_theme(load_omarchy_theme())
            self.theme = "omarchy"
            self.refresh_css(animate=False)
        except (FileNotFoundError, OSError, KeyError, ValueError):
            # No omarchy theme on this box, or it is malformed mid-swap
            # (tomllib.TOMLDecodeError is a ValueError) — default theme stands.
            pass

    # --- 1s tick: countdown + theme watch ---

    def _tick(self) -> None:
        """Per-second tick: refresh ONLY the countdown, then poll the theme.

        The status word, token meter, and panels are NOT re-rendered here — only the
        countdown cell updates (UI-SPEC: countdown is the only 1s-refreshed cell).
        A detected desktop-theme change re-registers the theme and repaints.
        """
        screen = self.screen
        if isinstance(screen, StatusScreen):
            screen.refresh_countdown()
        elif isinstance(screen, EditScreen):
            # The edit-window banner is time-sensitive the same way the
            # countdown is — a screen left open across the window boundary
            # must not keep showing stale OPEN/CLOSED state (Codex + opencode
            # cross-model review, 2026-09-07).
            screen.refresh_countdown()
        if self._theme_watch.changed():
            self._apply_omarchy_theme()

    # --- actions ---

    def action_refresh(self) -> None:
        """Re-read state and repaint the whole status surface (no optimism).

        Replaces the StatusScreen with a freshly-composed one so every value (verdict,
        token meter, grace, hmacs, ledger) is re-read from the guard/state — never an
        optimistic local update.

        The binding is app-level, so `r` is reachable from the EditScreen too. Always
        pop the current screen before pushing a fresh StatusScreen (WR-02) so a refresh
        never stacks a StatusScreen on top of an EditScreen — otherwise Escape from the
        new status would fall back to a stale edit surface instead of leaving cleanly.
        """
        if self.screen_stack:
            self.pop_screen()
        self.push_screen(StatusScreen())

    def action_ledger(self) -> None:
        """Toggle the ledger panel expanded ↔ collapsed."""
        if isinstance(self.screen, StatusScreen):
            self.screen.toggle_ledger()

    def action_edit(self) -> None:
        """Open the EditScreen — the anti-impulse preview + inline-sudo commit (10-03).

        The `e` binding pushes the editable surface (D-09); each staged edit shows its
        tighten/loosen direction + token cost BEFORE any sudo prompt (D-06/D-07), and
        commit runs inside `App.suspend()` so sudo's prompt is inline (D-08).
        """
        self.push_screen(EditScreen())
