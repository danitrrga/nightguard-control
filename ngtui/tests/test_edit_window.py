"""Edit window: loosening the curfew is refused outside a configured clock window.

The weekly token quota rate-limits *how often* the user may weaken the curfew, but
it does nothing about *when*. The failure mode it misses is the 2am one: the user
spends a token at the exact hour his judgement is worst and carries on. The edit
window closes that by refusing every loosening change outside a configured
window, before the token is even considered.

Direction asymmetry is preserved: tightening the curfew is allowed at any hour.
Only loosening is time-gated, and inside the window it still costs a token, so the
window is a second gate rather than a replacement for the first.

Two properties in here are the load-bearing ones:

  * The window in force is read from the SANCTIONED config, never from the
    proposed one. Reading it from the proposal would let the user delete the
    ``edit_window`` block and disable the gate in the same commit it governs.
  * Removing or widening the block is classified as a loosening, so it costs a
    token and is itself refused outside the window.
"""
from __future__ import annotations

import pytest

from ngtui import backend

ctl = backend.ctl


# --- fixtures ----------------------------------------------------------------

def _doc(start="05:30", end="14:00", enabled=True, curfew_start="21:30", curfew_end="05:30"):
    """A config document shaped like the real one, with an edit window."""
    d = {
        "timezone": "Europe/Amsterdam",
        "curfew": {"enabled": True, "start": curfew_start, "end": curfew_end},
    }
    if start is not None:
        d["edit_window"] = {"enabled": enabled, "start": start, "end": end}
    return d


def _no_window_doc(curfew_start="21:30", curfew_end="05:30"):
    return _doc(start=None, curfew_start=curfew_start, curfew_end=curfew_end)


_FRESH_STATE = {"weekly_spent": 0, "week_anchor": "", "ledger": []}

# The exhausted state must carry the CURRENT week's anchor. An empty or stale
# anchor triggers quota_decide's lazy Monday reset, which would refund the three
# tokens and make the test assert the opposite of what it reads.
_THIS_MONDAY = ctl._current_week_monday("Europe/Amsterdam")
_SPENT_STATE = {"weekly_spent": 3, "week_anchor": _THIS_MONDAY, "ledger": []}

_WINDOW = {"enabled": True, "start": "05:30", "end": "14:00"}

# Minute-of-day markers, Europe/Amsterdam wall time.
_INSIDE = 10 * 60          # 10:00 — inside 05:30-14:00
_OUTSIDE_NIGHT = 2 * 60    # 02:00 — the hour this feature exists for
_OUTSIDE_EVENING = 22 * 60  # 22:00


def _loosen_dirs():
    """A change that loosens: the curfew window shrinks from both ends is NOT it —
    use a plain later start, which unlocks minutes."""
    return ctl.classify_change(_doc(), _doc(curfew_start="23:30"))


def _tighten_dirs():
    return ctl.classify_change(_doc(), _doc(curfew_start="20:00"))


# --- the gate ----------------------------------------------------------------

def test_loosening_is_refused_outside_the_window():
    """02:00 is outside 05:30-14:00, so a loosening commit is refused."""
    decision = ctl.quota_decide(
        _loosen_dirs(), _FRESH_STATE, "Europe/Amsterdam",
        edit_window=_WINDOW, now_minutes=_OUTSIDE_NIGHT,
    )
    assert decision["allowed"] is False
    assert decision["costs_token"] is False, "a refused change must not spend a token"
    assert "05:30" in decision["reason"] and "14:00" in decision["reason"], (
        "the refusal must name the window so the user knows when he may retry"
    )


def test_loosening_is_allowed_inside_the_window_and_still_costs_a_token():
    """The window is a second gate, not a replacement for the token quota."""
    decision = ctl.quota_decide(
        _loosen_dirs(), _FRESH_STATE, "Europe/Amsterdam",
        edit_window=_WINDOW, now_minutes=_INSIDE,
    )
    assert decision["allowed"] is True
    assert decision["costs_token"] is True


def test_tightening_is_allowed_outside_the_window():
    """Asymmetry: the user may always make the pact stricter, at any hour."""
    decision = ctl.quota_decide(
        _tighten_dirs(), _FRESH_STATE, "Europe/Amsterdam",
        edit_window=_WINDOW, now_minutes=_OUTSIDE_NIGHT,
    )
    assert decision["allowed"] is True
    assert decision["costs_token"] is False


def test_exhausted_quota_still_refuses_inside_the_window():
    """Both gates apply; passing the clock gate does not refund a token."""
    decision = ctl.quota_decide(
        _loosen_dirs(), _SPENT_STATE, "Europe/Amsterdam",
        edit_window=_WINDOW, now_minutes=_INSIDE,
    )
    assert decision["allowed"] is False
    assert "quota" in decision["reason"]


def test_unverifiable_time_refuses_loosening():
    """Fail closed. No verified clock means no loosening — matching the guard's
    ``block_when_offline`` posture. A gate that fails open is not a gate."""
    decision = ctl.quota_decide(
        _loosen_dirs(), _FRESH_STATE, "Europe/Amsterdam",
        edit_window=_WINDOW, now_minutes=None,
    )
    assert decision["allowed"] is False
    assert "time" in decision["reason"].lower()


def test_unverifiable_time_still_allows_tightening():
    """Failing closed must not also block the user from strengthening the pact."""
    decision = ctl.quota_decide(
        _tighten_dirs(), _FRESH_STATE, "Europe/Amsterdam",
        edit_window=_WINDOW, now_minutes=None,
    )
    assert decision["allowed"] is True


def test_disabled_window_does_not_gate():
    decision = ctl.quota_decide(
        _loosen_dirs(), _FRESH_STATE, "Europe/Amsterdam",
        edit_window={"enabled": False, "start": "05:30", "end": "14:00"},
        now_minutes=_OUTSIDE_NIGHT,
    )
    assert decision["allowed"] is True


def test_absent_window_does_not_gate():
    """Back-compat: a config with no edit window behaves exactly as before."""
    decision = ctl.quota_decide(
        _loosen_dirs(), _FRESH_STATE, "Europe/Amsterdam",
        edit_window=None, now_minutes=_OUTSIDE_NIGHT,
    )
    assert decision["allowed"] is True
    assert decision["costs_token"] is True


def test_default_call_is_ungated():
    """The three-argument call used before this feature must keep working, so the
    other callers (``tokens_left``) are not silently changed."""
    decision = ctl.quota_decide(_loosen_dirs(), _FRESH_STATE, "Europe/Amsterdam")
    assert decision["allowed"] is True


@pytest.mark.parametrize(
    "now_minutes,expected_allowed",
    [
        (23 * 60, True),       # 23:00 — inside 22:00-02:00
        (1 * 60, True),        # 01:00 — inside, past midnight
        (12 * 60, False),      # 12:00 — outside
        (2 * 60, False),       # 02:00 — the exclusive end bound
        (22 * 60, True),       # 22:00 — the inclusive start bound
    ],
)
def test_overnight_window_does_not_invert(now_minutes, expected_allowed):
    """An overnight window wraps midnight. A naive ``start <= now < end`` reads
    ``02:00 < 22:00`` and inverts — the same class of bug already on record for the
    curfew window itself (.planning/debug/curfew-duration-midnight-grace.md)."""
    decision = ctl.quota_decide(
        _loosen_dirs(), _FRESH_STATE, "Europe/Amsterdam",
        edit_window={"enabled": True, "start": "22:00", "end": "02:00"},
        now_minutes=now_minutes,
    )
    assert decision["allowed"] is expected_allowed


def test_degenerate_window_refuses_rather_than_allows():
    """start == end is zero minutes of editing, not twenty-four hours of it."""
    decision = ctl.quota_decide(
        _loosen_dirs(), _FRESH_STATE, "Europe/Amsterdam",
        edit_window={"enabled": True, "start": "05:30", "end": "05:30"},
        now_minutes=_INSIDE,
    )
    assert decision["allowed"] is False


def test_malformed_window_refuses_rather_than_allows():
    decision = ctl.quota_decide(
        _loosen_dirs(), _FRESH_STATE, "Europe/Amsterdam",
        edit_window={"enabled": True, "start": "not-a-time", "end": "14:00"},
        now_minutes=_INSIDE,
    )
    assert decision["allowed"] is False


# --- classifying changes to the window itself --------------------------------

def _edit_window_direction(old_doc, new_doc):
    dirs = dict(ctl.classify_change(old_doc, new_doc))
    return dirs["edit_window"]


def test_widening_the_window_is_a_loosening():
    assert _edit_window_direction(_doc(), _doc(end="16:00")) == ctl.LOOSEN


def test_narrowing_the_window_is_a_tightening():
    assert _edit_window_direction(_doc(), _doc(end="12:00")) == ctl.TIGHTEN


def test_disabling_the_window_is_a_loosening():
    assert _edit_window_direction(_doc(), _doc(enabled=False)) == ctl.LOOSEN


def test_deleting_the_window_block_is_a_loosening():
    """The bypass this closes: if a missing block classified as a no-op, the user
    could delete ``edit_window`` for free and the gate would be gone."""
    assert _edit_window_direction(_doc(), _no_window_doc()) == ctl.LOOSEN


def test_adding_the_window_block_is_a_tightening():
    assert _edit_window_direction(_no_window_doc(), _doc()) == ctl.TIGHTEN


def test_unchanged_window_is_a_noop():
    assert _edit_window_direction(_doc(), _doc()) == ctl.NOOP


def test_shifting_the_window_without_changing_its_length_still_loosens():
    """05:30-14:00 -> 08:00-16:30 is the same 8h30 but unlocks 14:00-16:30. Any
    minute newly available for loosening is a loosening, exactly as the curfew
    window's locked-set model already decides."""
    assert _edit_window_direction(_doc(), _doc(start="08:00", end="16:30")) == ctl.LOOSEN


def test_deleting_the_window_is_refused_outside_the_window():
    """The two halves compose: removing the gate is a loosening, and a loosening
    outside the window is refused. So the gate cannot be removed at 2am."""
    dirs = ctl.classify_change(_doc(), _no_window_doc())
    decision = ctl.quota_decide(
        dirs, _FRESH_STATE, "Europe/Amsterdam",
        edit_window=_WINDOW, now_minutes=_OUTSIDE_NIGHT,
    )
    assert decision["allowed"] is False


# --- the window in force comes from the sanctioned config --------------------

def test_window_in_force_is_read_from_the_sanctioned_config():
    """``effective_edit_window`` must resolve against the config currently signed,
    never the proposal. Otherwise a single commit could both widen the window and
    be judged by the widened one."""
    old = _doc(start="05:30", end="14:00")
    new = _doc(start="00:00", end="23:59")
    assert ctl.effective_edit_window(old, new) == {
        "enabled": True, "start": "05:30", "end": "14:00",
    }


def test_window_in_force_survives_deletion_in_the_proposal():
    old = _doc()
    new = _no_window_doc()
    assert ctl.effective_edit_window(old, new)["enabled"] is True


def test_window_in_force_is_none_when_sanctioned_has_none():
    assert ctl.effective_edit_window(_no_window_doc(), _doc()) is None
