"""The edit window has to shut the door, not print a sign next to an open one.

Reported live on 2026-09-07 at 21:15, with the window signed as 05:30-14:00:
"lets me edit things now, should be blocked" — the screenshot shows `curfew.start`
open for editing at an hour when loosening the curfew is refused.

The signer was right the whole time (`allowed: False`, reason "outside the edit
window (05:30-14:00)"). Two things were wrong above it:

  1. The refusal was only enforced at the confirm gate, three keystrokes after the
     value had already been typed and shown as the field's new value. Every one of
     those keystrokes is the impulse being rehearsed, which is the exact thing this
     tool exists to interrupt.
  2. The copy LIED about why. `confirm_copy` hardcoded "weekly loosen quota
     exhausted (3/3). Available again Monday." for every refusal, so a window
     refusal was reported as a quota refusal — with 3 of 3 tokens visibly left on
     the status screen one screen back. Being told an obvious falsehood is how a
     gate loses its authority.
"""
from __future__ import annotations

from ngtui.widgets import edit
from ngtui.widgets.edit import confirm_copy, preview_line, stage_refusal


_WINDOW_REASON = "outside the edit window (05:30-14:00); loosening is refused until then"
_QUOTA_REASON = "weekly loosen quota exhausted (3/3)"


def _refused(reason: str) -> dict:
    return {"allowed": False, "is_noop": False, "costs_token": False,
            "effective_spent": 0, "reason": reason}


# --- the copy tells the truth about WHICH gate refused ------------------------


def test_confirm_copy_window_refusal_names_the_window_not_the_quota():
    text, role, can_commit = confirm_copy(_refused(_WINDOW_REASON))
    assert can_commit is False
    assert role == "error"
    assert "edit window" in text.lower()
    assert "05:30-14:00" in text
    assert "quota" not in text.lower(), (
        "a window refusal reported as a quota refusal is a lie the user can check "
        "against the token count on the previous screen"
    )
    assert "Monday" not in text


def test_confirm_copy_quota_refusal_still_names_the_quota():
    text, role, can_commit = confirm_copy(_refused(_QUOTA_REASON))
    assert can_commit is False
    assert role == "error"
    assert "quota" in text.lower()


def test_confirm_copy_refusal_without_a_reason_still_blocks():
    """A signer that refuses without saying why must still disable the commit."""
    text, role, can_commit = confirm_copy({"allowed": False})
    assert can_commit is False
    assert role == "error"
    assert text.startswith("✕")


def test_preview_line_blocked_loosen_carries_the_signer_reason():
    text, role = preview_line("loosen", False, _WINDOW_REASON)
    assert role == "error"
    assert "BLOCKED" in text
    assert "edit window" in text.lower()


def test_preview_line_blocked_loosen_without_reason_keeps_the_old_wording():
    """Two-argument callers (the existing suite, any older path) keep working."""
    text, role = preview_line("loosen", False)
    assert role == "error"
    assert "BLOCKED" in text


# --- the refusal happens at the keystroke, not at the confirm gate ------------


def test_stage_refusal_is_none_when_the_change_is_permitted():
    assert stage_refusal({"allowed": True}) is None


def test_stage_refusal_states_the_signer_reason():
    msg = stage_refusal(_refused(_WINDOW_REASON))
    assert msg is not None
    assert "edit window" in msg.lower()
    assert "05:30-14:00" in msg


def test_stage_refusal_survives_a_reasonless_refusal():
    msg = stage_refusal({"allowed": False})
    assert msg is not None and msg.startswith("✕")


class _FakeScreen(edit.EditScreen):
    """An EditScreen with the Textual machinery and the backend stubbed out.

    Built with ``__new__`` on purpose: ``EditScreen.__init__`` reads the live
    sanctioned config, and this test must run on a machine with no instance.
    """

    def __init__(self, decision):  # noqa: D107 - test double
        self._staged = []
        self._focus = 0
        self._pending = None
        self._editing_row = None
        self._base_cfg = {}
        self._base_text = ""
        self._decision = decision
        self.rejections = []
        self.refreshes = 0
        self.status_clears = 0

    def _preview_for(self, staged):
        return {"dirs": [], "decision": self._decision}

    def _refresh_preview(self):
        self.refreshes += 1

    def _refresh_value_cells(self):
        pass

    def _reject_stage(self, message):
        self.rejections.append(message)

    def _clear_stage_status(self):
        self.status_clears += 1


def _screen(decision):
    s = _FakeScreen.__new__(_FakeScreen)
    _FakeScreen.__init__(s, decision)
    return s


def test_a_refused_edit_is_never_staged():
    """THE regression. The value must not land in the field at all."""
    s = _screen(_refused(_WINDOW_REASON))
    s._stage("set", "curfew.start", "23:30")
    assert s._staged == [], (
        "a loosening typed outside the edit window was accepted into the staged "
        "edits — the door was open and only the confirm gate said no"
    )
    assert s.rejections and "edit window" in s.rejections[0].lower()


def test_a_permitted_edit_is_staged_normally():
    s = _screen({"allowed": True})
    s._stage("set", "curfew.start", "20:30")
    assert s._staged == [("set", "curfew.start", "20:30")]
    assert s.rejections == []
    assert s.refreshes == 1


def test_a_refused_edit_leaves_earlier_staged_edits_untouched():
    """Rejecting the new keystroke must not discard work already accepted."""
    s = _screen({"allowed": True})
    s._stage("set", "curfew.start", "20:30")
    s._decision = _refused(_WINDOW_REASON)
    s._stage("set", "curfew.end", "07:00")
    assert s._staged == [("set", "curfew.start", "20:30")]


def test_a_preview_that_blows_up_does_not_stage_the_edit():
    """Fail closed: an unreadable proposal is not a permitted one."""
    s = _screen({"allowed": True})

    def boom(_staged):
        raise ValueError("malformed yaml")

    s._preview_for = boom
    s._stage("set", "curfew.start", "23:30")
    assert s._staged == []
    assert s.rejections


# --- the screen says the door is shut BEFORE a key is pressed -----------------


def test_window_banner_closed_is_an_error_and_says_tightening_still_works():
    text, role = edit.window_banner(
        {"enabled": True, "start": "05:30", "end": "14:00"}, _WINDOW_REASON
    )
    assert role == "error"
    assert "05:30" in text and "14:00" in text
    assert "closed" in text.lower()
    assert "tighten" in text.lower(), (
        "a banner that only says NO teaches the user the tool is arbitrary; it must "
        "say what is still possible, which is the whole asymmetry of the pact"
    )


def test_window_banner_open_is_not_an_error():
    text, role = edit.window_banner(
        {"enabled": True, "start": "05:30", "end": "14:00"}, None
    )
    assert role != "error"
    assert "open" in text.lower()
    assert "05:30" in text


def test_window_banner_disabled_says_so_rather_than_claiming_protection():
    text, role = edit.window_banner({"enabled": False}, None)
    assert "off" in text.lower()
    assert role == "text-muted"


def test_window_banner_absent_block_reads_as_off():
    text, role = edit.window_banner(None, None)
    assert "off" in text.lower()
    assert role == "text-muted"


def test_backend_exposes_the_signers_own_window_refusal():
    """The banner must not re-derive the rule — one function decides, everywhere."""
    from ngtui import backend as be
    import inspect

    assert hasattr(be, "edit_window_refusal")
    src = inspect.getsource(be.edit_window_refusal)
    assert "_edit_window_refusal" in src, (
        "the banner has to ask the signer's own gate, not reimplement the clock "
        "comparison — a second copy is a second thing that can disagree"
    )


# --- cross-model review findings, 2026-09-07 -----------------------------
# Codex (gpt-5.6-luna) and opencode (big-pickle) reviewed the patch above
# independently. Both flagged that the banner can go stale; Codex additionally
# found it overclaims when the window is open but the weekly token quota is
# already spent. The actual staging gate (`_stage`) was already correct in
# both reviews — these three are UI-truthfulness bugs, not bypasses.


def test_banner_does_not_claim_a_loosen_is_possible_at_zero_tokens():
    """Window open + 0/3 tokens left must not say 'a loosening is possible now'.

    `_stage` already refuses this correctly (quota_decide checks the window,
    THEN the quota) — this is about the banner telling the truth about it
    BEFORE a keystroke, which is the entire point of showing it up front.
    """
    text, role = edit.window_banner(
        {"enabled": True, "start": "05:30", "end": "14:00"}, None, tokens_left=0
    )
    assert "a loosening is possible" not in text.lower()
    assert "0" in text and ("token" in text.lower() or "ficha" in text.lower())
    assert "tighten" in text.lower(), "tightening is still free and must still be said"
    assert role != "accent", "an all-clear colour on a gate that will refuse is a lie"


def test_banner_still_reports_open_with_tokens_available():
    """Unchanged case: window open, tokens left — the original OPEN message."""
    text, role = edit.window_banner(
        {"enabled": True, "start": "05:30", "end": "14:00"}, None, tokens_left=2
    )
    assert "a loosening is possible now" in text.lower()
    assert role == "accent"


def test_banner_omitting_tokens_left_keeps_the_open_message():
    """``tokens_left=None`` (unknown) must not manufacture a false 'no tokens' claim."""
    text, role = edit.window_banner(
        {"enabled": True, "start": "05:30", "end": "14:00"}, None
    )
    assert "a loosening is possible now" in text.lower()


def test_banner_closed_by_the_window_ignores_tokens_left():
    """A window refusal is reported as the window, even at full tokens."""
    text, role = edit.window_banner(
        {"enabled": True, "start": "05:30", "end": "14:00"}, _WINDOW_REASON, tokens_left=3
    )
    assert "edit window" in text.lower()
    assert role == "error"


def test_editscreen_refreshes_the_banner_on_a_tick():
    """The countdown-style 1s tick (app.py `_tick`) must also repaint the banner.

    Otherwise a screen left open across the window boundary keeps showing the
    minute-old OPEN/CLOSED state while the underlying gate has already moved on.
    """
    assert hasattr(edit.EditScreen, "refresh_countdown"), (
        "EditScreen needs the same tick hook name StatusScreen uses "
        "(app.py._tick dispatches by isinstance + this method)"
    )
    s = _screen({"allowed": True})
    calls = []
    s._refresh_window_banner = lambda: calls.append(1)
    s.refresh_countdown()
    assert calls == [1]


def test_a_successful_stage_clears_a_stale_rejection_message():
    """Reject once, then stage something permitted — the old error must not linger."""
    s = _screen(_refused(_WINDOW_REASON))
    s._stage("set", "curfew.start", "23:30")
    assert s.rejections == [f"✕ not staged — {_WINDOW_REASON}"]

    s._decision = {"allowed": True}
    s._stage("set", "curfew.end", "06:00")
    assert s._staged == [("set", "curfew.end", "06:00")]
    assert s.status_clears == 1, (
        "a successful stage must clear the status cell — otherwise it still "
        "reads the earlier rejection even though the edit above it just landed"
    )
