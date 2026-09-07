"""The edit window reaches the user BEFORE he authenticates.

The project's standing UI rule is that the cost and direction of a change are
rendered before any sudo/password/fingerprint prompt is reached — there is no path
where the user authenticates first and learns the cost after. A refusal that only
the root signer knows about would break that: the user would present a fingerprint
at 2am and only then be told the hour is wrong.

So the gate lives in ``quota_decide``, which the TUI's pre-auth preview calls
directly, and these tests hold that seam in place. They also pin the two clock
properties the preview depends on: it must never issue a synchronous network
query, and a cold cache must fail closed rather than open.
"""
from __future__ import annotations

import os
from datetime import datetime

import pytest

from ngtui import backend
from ngtui.widgets import edit as edit_mod

ctl = backend.ctl
guard = backend.guard
ng = backend.ng


_CONFIG_WITH_WINDOW = '''\
timezone: Europe/Amsterdam

curfew:
  enabled: true
  start: "21:30"
  end: "05:30"

edit_window:
  enabled: true
  start: "05:30"
  end: "14:00"
'''

# A loosening proposal: the curfew starts two hours later.
_LOOSENED = _CONFIG_WITH_WINDOW.replace('start: "21:30"', 'start: "23:30"')
# A tightening proposal: the curfew starts earlier.
_TIGHTENED = _CONFIG_WITH_WINDOW.replace('start: "21:30"', 'start: "20:00"')


def _unix_at(hour: int, minute: int = 0) -> int:
    """A Wednesday at the given Europe/Amsterdam wall-clock time."""
    from zoneinfo import ZoneInfo

    return int(
        datetime(2026, 9, 9, hour, minute, tzinfo=ZoneInfo("Europe/Amsterdam")).timestamp()
    )


@pytest.fixture
def sanctioned_window(monkeypatch):
    """Point the preview at a sanctioned config that carries an edit window."""
    monkeypatch.setattr(backend, "sanctioned_config",
                        lambda: ng.yaml_load(_CONFIG_WITH_WINDOW))
    monkeypatch.setattr(ng, "load_state",
                        lambda: {"weekly_spent": 0, "week_anchor": "", "ledger": []})


@pytest.fixture
def clock(monkeypatch):
    """Pin the guard's resolved true time for the duration of one test.

    The guard's own ``NIGHTGUARD_TEST_NTP_OVERRIDE`` seam is not usable here: it
    is gated on the instance directory not being the canonical one, and this
    checkout resolves to the canonical instance. That gate is deliberate — the
    adversary is the user, so an env-settable clock would be a passwordless
    bypass in production — so the tests reach one level up instead and replace
    the resolver.

    Everything above the time source is still under test: the timezone comes
    from the signed config, the minute-of-day arithmetic, the window comparison
    and the pre-auth surfacing. The resolver's own network behaviour is covered
    separately by the tests below, which leave ``true_unix`` alone.
    """

    def _set(unix_ts):
        monkeypatch.setattr(guard, "true_unix", lambda: (unix_ts, "ntp"))

    return _set


# --- the seam ----------------------------------------------------------------

def test_preview_refuses_a_loosening_at_two_in_the_morning(sanctioned_window, clock):
    """The whole point of the feature, seen from where the user actually sees it."""
    clock(_unix_at(2))
    preview = backend.preview_change(_LOOSENED)
    assert preview["loosening"] is True
    assert preview["decision"]["allowed"] is False
    assert "edit window" in preview["decision"]["reason"]


def test_preview_allows_the_same_loosening_at_ten_in_the_morning(sanctioned_window, clock):
    clock(_unix_at(10))
    preview = backend.preview_change(_LOOSENED)
    assert preview["decision"]["allowed"] is True
    assert preview["decision"]["costs_token"] is True


def test_preview_allows_a_tightening_at_two_in_the_morning(sanctioned_window, clock):
    """Tightening is never time-gated, so the pact can always be strengthened."""
    clock(_unix_at(2))
    preview = backend.preview_change(_TIGHTENED)
    assert preview["decision"]["allowed"] is True


def test_the_refusal_blocks_the_commit_before_authentication(sanctioned_window, clock):
    """``confirm_copy`` decides whether the confirm screen can reach sudo at all.

    ``can_commit`` False means ``action_do_commit`` rings the bell and returns
    without invoking sudo, so no fingerprint is ever requested for a change the
    hour forbids.
    """
    clock(_unix_at(2))
    preview = backend.preview_change(_LOOSENED)
    _text, _role, can_commit = edit_mod.confirm_copy(preview["decision"])
    assert can_commit is False


def test_the_same_change_can_be_confirmed_inside_the_window(sanctioned_window, clock):
    clock(_unix_at(10))
    preview = backend.preview_change(_LOOSENED)
    _text, _role, can_commit = edit_mod.confirm_copy(preview["decision"])
    assert can_commit is True


# --- the clock the preview uses ----------------------------------------------

def test_preview_never_issues_a_synchronous_network_query(sanctioned_window, monkeypatch):
    """A ~4s SNTP+HTTP fall-through on a cold cache would freeze the TUI on every
    keystroke, because the edit screen re-previews as the user types."""
    calls = []

    def _boom(*_a, **_k):
        calls.append(1)
        raise AssertionError("preview_change issued a synchronous network query")

    monkeypatch.setattr(guard, "_sntp", _boom)
    monkeypatch.setattr(guard, "_http_time", _boom)
    monkeypatch.delenv("NIGHTGUARD_TEST_NTP_OVERRIDE", raising=False)
    guard._end_tick()

    backend.preview_change(_LOOSENED)
    assert calls == []


def test_a_cold_clock_fails_closed_in_the_preview(sanctioned_window, monkeypatch):
    """No verifiable time must refuse the loosening, not wave it through."""
    monkeypatch.setattr(guard, "_sntp", lambda *_a, **_k: (_ for _ in ()).throw(OSError("cold")))
    monkeypatch.setattr(guard, "_http_time", lambda *_a, **_k: (_ for _ in ()).throw(OSError("cold")))
    monkeypatch.setattr(guard, "TIMECACHE", "/nonexistent/nightguard-timecache-for-tests")
    monkeypatch.delenv("NIGHTGUARD_TEST_NTP_OVERRIDE", raising=False)
    guard._end_tick()

    preview = backend.preview_change(_LOOSENED)
    assert preview["decision"]["allowed"] is False
    assert "time" in preview["decision"]["reason"].lower()


def test_the_network_stubs_are_restored_after_the_preview(sanctioned_window, clock):
    """The suppression is scoped to the preview; the later live commit still needs
    real time resolution."""
    clock(_unix_at(10))
    before_sntp, before_http = guard._sntp, guard._http_time
    backend.preview_change(_LOOSENED)
    assert guard._sntp is before_sntp
    assert guard._http_time is before_http


# --- the window in force is the sanctioned one -------------------------------

def test_widening_the_window_in_the_same_commit_does_not_authorise_itself(
    sanctioned_window, clock
):
    """The bypass this closes: propose a 00:00-23:59 window at 2am and, if the
    preview judged the proposal by its own new bounds, the change would let
    itself through."""
    clock(_unix_at(2))
    wide = _CONFIG_WITH_WINDOW.replace('start: "05:30"\n  end: "14:00"',
                                       'start: "00:00"\n  end: "23:59"')
    preview = backend.preview_change(wide)
    assert preview["decision"]["allowed"] is False


def test_deleting_the_window_in_the_same_commit_does_not_disable_the_gate(
    sanctioned_window, clock
):
    clock(_unix_at(2))
    stripped = _CONFIG_WITH_WINDOW.split("edit_window:")[0]
    preview = backend.preview_change(stripped)
    assert preview["decision"]["allowed"] is False


def test_shifting_the_timezone_in_the_proposal_does_not_move_the_hour(
    sanctioned_window, clock
):
    """The hour is read in the SANCTIONED timezone. Reading it in the proposal's
    zone would let a single commit relabel 02:00 as 10:00 — and the box grants a
    passwordless ``timedatectl set-timezone``, so the system zone is untrusted
    too."""
    clock(_unix_at(2))
    shifted = _LOOSENED.replace("timezone: Europe/Amsterdam", "timezone: Pacific/Kiritimati")
    preview = backend.preview_change(shifted)
    assert preview["decision"]["allowed"] is False


# --- the migration -----------------------------------------------------------

def test_the_migration_block_parses_to_the_documented_defaults():
    """deploy.sh appends this text to a live config; if it did not parse back the
    gate would ship inert."""
    parsed = ng.yaml_load(ctl.EDIT_WINDOW_BLOCK)
    window = ctl._read_edit_window(parsed)
    assert window == {
        "enabled": True,
        "start": ctl.EDIT_WINDOW_DEFAULT_START,
        "end": ctl.EDIT_WINDOW_DEFAULT_END,
    }


def test_the_migration_block_appends_cleanly_to_a_real_config():
    combined = _CONFIG_WITH_WINDOW.split("edit_window:")[0].rstrip("\n") + "\n" + ctl.EDIT_WINDOW_BLOCK
    parsed = ng.yaml_load(combined)
    assert ctl._read_edit_window(parsed)["enabled"] is True
    assert parsed["curfew"]["start"] == "21:30", "the existing config must survive intact"


def test_the_migrated_window_actually_gates():
    """End to end on the defaults the migration installs: a loosening at 02:00 is
    refused by the very block deploy.sh writes."""
    migrated = ng.yaml_load(
        _CONFIG_WITH_WINDOW.split("edit_window:")[0].rstrip("\n") + "\n" + ctl.EDIT_WINDOW_BLOCK
    )
    decision = ctl.quota_decide(
        [("curfew.window", ctl.LOOSEN)],
        {"weekly_spent": 0, "week_anchor": "", "ledger": []},
        "Europe/Amsterdam",
        edit_window=ctl.effective_edit_window(migrated, migrated),
        now_minutes=2 * 60,
    )
    assert decision["allowed"] is False


def test_the_editable_field_list_exposes_the_window():
    """Without these rows the user could never change the window from the TUI, and
    the only way to adjust it would be a hand edit the watchdog reverts."""
    keys = {key for _label, key, _kind in edit_mod.EDITABLE_FIELDS}
    assert {"edit_window.enabled", "edit_window.start", "edit_window.end"} <= keys
