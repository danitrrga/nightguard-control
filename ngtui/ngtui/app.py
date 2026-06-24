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

from ngtui.theme import ThemeWatch, load_omarchy_theme
from ngtui.widgets.edit import EditScreen
from ngtui.widgets.status import StatusScreen


class NightguardApp(App):
    """Single sanctioned editor — omarchy Textual thin client over the trust stack."""

    TITLE = "Nightguard Control"
    CSS_PATH = "app.tcss"

    # Bindings live on StatusScreen (the home surface); kept here too so the
    # app-level Footer legend is populated before the screen mounts.
    BINDINGS = [
        ("e", "edit", "Edit a field"),
        ("r", "refresh", "Refresh"),
        ("l", "ledger", "Ledger"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # Watch the live omarchy colours.toml for desktop-theme swaps (D-05).
        self._theme_watch = ThemeWatch()

    def on_mount(self) -> None:
        """Register the live omarchy theme, show StatusScreen, start the 1s tick."""
        self._apply_omarchy_theme()
        self.push_screen(StatusScreen())
        # Reuse a single 1s interval for both the countdown and the theme poll.
        self.set_interval(1.0, self._tick)

    # --- theme (D-04/D-05) ---

    def _apply_omarchy_theme(self) -> None:
        """(Re-)register the omarchy theme and (re)assign App.theme to repaint.

        Re-registering the same name overwrites the prior definition, so reassigning
        the ``theme`` reactive forces Textual to refresh every ``$variable`` and
        repaint (RESEARCH Pattern 4, A3). If the live theme files are unreadable,
        keep Textual's default rather than crash (T-10-07 — cosmetic, low impact).
        """
        try:
            self.register_theme(load_omarchy_theme())
            self.theme = "omarchy"
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
        if self._theme_watch.changed():
            self._apply_omarchy_theme()

    # --- actions ---

    def action_refresh(self) -> None:
        """Re-read state and repaint the whole status surface (no optimism).

        Replaces the StatusScreen with a freshly-composed one so every value (verdict,
        token meter, grace, hmacs, ledger) is re-read from the guard/state — never an
        optimistic local update.
        """
        if isinstance(self.screen, StatusScreen):
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
