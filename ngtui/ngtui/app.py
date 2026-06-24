"""NightguardApp — the runnable TUI shell (Wave 1).

The real screens (read-only StatusScreen, anti-impulse EditScreen) land in
Waves 2-3; this is the minimal runnable app: the single-key BINDINGS (D-03 —
one keystroke per action, no arrow-menu primary nav) and a verdict placeholder
sourced from the guard. Uses Textual's default theme — the live omarchy theme
is registered in Wave 2 (theme.py).
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static

from ngtui import backend


class NightguardApp(App):
    """Single sanctioned editor — omarchy Textual thin client over the trust stack."""

    TITLE = "Nightguard Control"

    BINDINGS = [
        ("e", "edit", "Edit a field"),
        ("r", "refresh", "Refresh"),
        ("l", "ledger", "Ledger"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._verdict_line(), id="verdict")
        yield Footer()

    def _verdict_line(self) -> str:
        """Advisory verdict + remaining tokens, read live from the guard/state."""
        verdict = backend.live_verdict(backend.sanctioned_config(), backend.read_state())
        return f"verdict: {verdict}    tokens left: {backend.tokens_left()}"

    def action_refresh(self) -> None:
        """Re-read state and repaint the verdict (no optimism — re-read the guard)."""
        self.query_one("#verdict", Static).update(self._verdict_line())

    def action_edit(self) -> None:
        """Stub — the EditScreen is wired in Wave 3 (10-03)."""
        self.bell()

    def action_ledger(self) -> None:
        """Stub — the ledger panel is wired in Wave 2 (10-02)."""
        self.bell()
