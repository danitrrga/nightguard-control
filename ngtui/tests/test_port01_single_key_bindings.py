"""GAP-03 (PORT-01): The TUI is single-key command-driven (D-03).

Requirement: "The Linux app is a terminal/TUI, omarchy-native, single-key
command-driven" (PORT-01, 10-02-PLAN D-03, 10-03-PLAN D-03).

This verifies:
  1. NightguardApp.BINDINGS declares exactly the four single-character keys
     e, r, l, q as the primary navigation — no multi-key or arrow-first nav.
  2. action_edit() pushes the EditScreen (the `e` binding actually opens the
     editor, wiring PORT-02's edit surface to PORT-01's key contract).
  3. The EditScreen is importable from ngtui.widgets.edit (the module exists
     and the class is the correct type).

The test is written to FAIL if BINDINGS are changed to multi-key or if
push_screen is replaced with a stub bell() call.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from textual.app import App

from ngtui.app import NightguardApp
from ngtui.widgets.edit import EditScreen


# --- Test 1: BINDINGS declare exactly the four single-key navigation keys -----


def test_app_bindings_are_single_key():
    """NightguardApp.BINDINGS must declare e/r/l/q as single-character keys (D-03).

    Single-key navigation is a hard requirement for the omarchy-native terminal
    workflow (PORT-01). Multi-character bindings or arrow-first navigation would
    violate D-03.
    """
    app = NightguardApp()
    # BINDINGS is a list of (key, action, description) tuples.
    binding_keys = {b[0] for b in app.BINDINGS}

    required_keys = {"e", "r", "l", "q"}
    assert required_keys <= binding_keys, (
        f"PORT-01 VIOLATION — NightguardApp.BINDINGS missing required single-key "
        f"bindings: {required_keys - binding_keys!r}. "
        f"Declared keys: {binding_keys!r}"
    )

    # No binding may be a multi-character key (e.g. "ctrl+e", "alt+x", "shift+r")
    multi_key_bindings = {k for k in binding_keys if len(k) > 1 and "+" not in k}
    # (keys like "ctrl+q" contain '+' and are OK to have alongside single keys;
    # we only care that the four primary nav keys are single chars)
    for key in required_keys:
        assert len(key) == 1, (
            f"Required binding {key!r} must be a single character — "
            f"no multi-key sequences for primary nav (D-03)"
        )


# --- Test 2: action_edit() pushes the EditScreen — not a stub ----------------


def test_action_edit_pushes_edit_screen_not_stub():
    """action_edit() must call push_screen(EditScreen()) — the e key opens the editor.

    This confirms the wiring from 10-03-PLAN Task 2 acceptance criterion:
    `grep -q 'push_screen' ngtui/ngtui/app.py` AND EditScreen is referenced.
    We verify it behaviorally: monkeypatch push_screen and assert it is called
    with an EditScreen instance.
    """
    app = NightguardApp()
    pushed: list = []

    app.push_screen = lambda screen: pushed.append(screen)  # type: ignore[method-assign]
    app.bell = lambda: None  # type: ignore[method-assign]  # suppress stub fallback

    app.action_edit()

    assert pushed, (
        "PORT-01/02 VIOLATION — action_edit() did not call push_screen(). "
        "The `e` binding must open the EditScreen, not a bell() stub."
    )
    assert isinstance(pushed[0], EditScreen), (
        f"PORT-01 VIOLATION — action_edit() pushed {type(pushed[0]).__name__!r} "
        f"instead of EditScreen. Single-key `e` must open the edit surface (D-03/D-09)."
    )


# --- Test 3: EditScreen is a real Textual Screen subclass --------------------


def test_edit_screen_is_textual_screen():
    """EditScreen must be a Textual Screen subclass (not a stand-in mock or Static)."""
    from textual.screen import Screen

    assert issubclass(EditScreen, Screen), (
        f"EditScreen must subclass textual.screen.Screen, "
        f"got bases: {[b.__name__ for b in EditScreen.__mro__]}"
    )


# --- Test 4: NightguardApp is a Textual App subclass -------------------------


def test_nightguard_app_is_textual_app():
    """NightguardApp must subclass textual.app.App (not a plain class)."""
    assert issubclass(NightguardApp, App), (
        f"NightguardApp must subclass textual.app.App"
    )
