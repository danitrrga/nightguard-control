"""Headless tests for the load-bearing anti-impulse copy in widgets/edit.py.

The three pure helpers carry the product's whole reason to exist: the tighten/
loosen direction + token cost must be the EXACT UI-SPEC strings, in the EXACT
colour role, and rendered BEFORE any sudo prompt. They are unit-tested without a
running App so the copy can never silently drift.

Strings are quoted verbatim from 10-UI-SPEC.md ("Anti-Impulse Edit Preview",
"Confirm gate", "State & Feedback Rendering"). Colour roles are $-variable names
(matching status.py's role-class convention).
"""
from __future__ import annotations

from ngtui.widgets.edit import confirm_copy, preview_line, result_line


# --- Test 1: preview_line (per-field, before `c`) ----------------------------


def test_preview_line_tighten_is_free_and_accent():
    text, role = preview_line("tighten", True)
    assert text == "▼ Tightens curfew · free"
    assert role == "accent"


def test_preview_line_loosen_allowed_costs_a_token_warning():
    text, role = preview_line("loosen", True)
    assert text == "▲ Loosens curfew · costs 1 token"
    assert role == "warning"


def test_preview_line_noop_is_dim_no_change():
    text, role = preview_line("noop", True)
    assert text == "· no change"
    assert role == "text-muted"
    # `allowed` is irrelevant for a noop — still dim "no change".
    assert preview_line("noop", False) == ("· no change", "text-muted")


def test_preview_line_loosen_blocked_is_error_with_monday():
    text, role = preview_line("loosen", False)
    assert text == (
        "▲ Loosens · BLOCKED — weekly tokens exhausted (3/3); available again Monday"
    )
    assert role == "error"


# --- Test 2: confirm_copy (modal gate, on `c`, BEFORE sudo) -------------------


def test_confirm_copy_free_tighten_has_no_token_language():
    decision = {"allowed": True, "costs_token": False, "is_noop": False, "effective_spent": 0}
    text, role, can_commit = confirm_copy(decision)
    assert text == "▼ This change TIGHTENS your curfew · free.  Commit?  [y] yes  [n] no"
    assert "token" not in text.lower()
    assert role == "accent"
    assert can_commit is True


def test_confirm_copy_loosen_with_tokens_states_cost_and_remaining():
    # effective_spent=0 -> after committing this loosen, 3 - (0+1) = 2 left.
    decision = {"allowed": True, "costs_token": True, "is_noop": False, "effective_spent": 0}
    text, role, can_commit = confirm_copy(decision)
    assert "costs 1 of 3 weekly tokens" in text
    assert "After commit: 2 left." in text
    assert text.startswith("▲ This change LOOSENS your curfew")
    assert role == "warning"
    assert can_commit is True


def test_confirm_copy_loosen_remaining_drops_to_one():
    decision = {"allowed": True, "costs_token": True, "is_noop": False, "effective_spent": 1}
    text, _role, _can = confirm_copy(decision)
    assert "After commit: 1 left." in text


def test_confirm_copy_no_tokens_disables_commit_with_monday():
    decision = {
        "allowed": False,
        "costs_token": False,
        "is_noop": False,
        "effective_spent": 3,
        "reason": "weekly loosen quota exhausted (3/3 used); available again Monday",
    }
    text, role, can_commit = confirm_copy(decision)
    assert text == (
        "✕ Cannot commit: weekly loosen quota exhausted (3/3). Available again Monday."
    )
    assert role == "error"
    assert can_commit is False


# --- Test 3: result_line (after commit, verbatim-keyed from CLI) --------------


def test_result_line_success_is_green_verbatim():
    text, role = result_line(0, "committed (tighten, free): config_hmac=abc · tokens 0/3 used")
    assert role == "success"
    # stdout surfaced verbatim (with a ✓ marker), never fabricated.
    assert "committed (tighten, free)" in text


def test_result_line_noop_is_muted():
    text, role = result_line(
        0, "no-op: proposed config is identical to sanctioned; nothing written."
    )
    assert role == "text-muted"
    assert "no-op" in text


def test_result_line_nonzero_is_error_returncode_keyed():
    # stderr stays on the TTY (inline sudo) — the in-widget line is returncode-keyed,
    # not an echo of stderr (intentional UI-SPEC "verbatim REFUSED" deviation).
    text, role = result_line(1, "")
    assert role == "error"
    assert "refused" in text.lower()
    # Even with empty stdout the user gets a non-empty, non-misleading line.
    assert text.strip() != ""
