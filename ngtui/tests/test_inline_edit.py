"""The field editor edits IN PLACE in the settings list — never a separate screen.

User requirement: "I want to change [the curfew time] in the same list where all the
other settings are displayed" (no modal/second screen that hides everything else).

This locks the contract: the field editor is an ``Input`` mounted into the field row,
NOT a ``Screen``/``ModalScreen``, and the EditScreen owns the inline submit/cancel
handlers. Editing a field must not push a new screen.
"""
from __future__ import annotations

from textual.screen import Screen
from textual.widgets import Input

from ngtui.widgets import edit


def test_field_editor_is_an_input_not_a_screen():
    """The in-row field editor subclasses Input (in-place), never a Screen/modal."""
    assert issubclass(edit._InlineFieldInput, Input), (
        "field editor must be an Input mounted in the row (in-place edit)"
    )
    assert not issubclass(edit._InlineFieldInput, Screen), (
        "field editor must NOT be a Screen/ModalScreen — that is the 'other screen' "
        "the user explicitly did not want"
    )


def test_editscreen_owns_inline_submit_and_cancel():
    """EditScreen handles the inline Input submit + cancel (no dismiss-a-modal flow)."""
    assert hasattr(edit.EditScreen, "on_input_submitted")
    assert hasattr(edit.EditScreen, "cancel_inline_edit")
    assert hasattr(edit.EditScreen, "_teardown_inline")


def _binding_keys(bindings) -> set[str]:
    """Keys from a Textual BINDINGS list (mixed ``(key, ...)`` tuples and ``Binding``)."""
    keys = set()
    for b in bindings:
        keys.add(b.key if hasattr(b, "key") else b[0])
    return keys


def test_inline_editor_cancels_on_escape():
    """The inline Input binds Escape to cancel_edit so it wins over the screen's back."""
    assert "escape" in _binding_keys(edit._InlineFieldInput.BINDINGS), (
        "inline field editor must bind Escape to cancel in place"
    )


def test_arrow_keys_mirror_jk_for_field_navigation():
    """Up/Down arrows navigate fields alongside j/k (user request)."""
    keys = _binding_keys(edit.EditScreen.BINDINGS)
    assert {"j", "k", "up", "down"} <= keys, (
        f"field navigation must accept both j/k and arrow keys, got {sorted(keys)}"
    )
