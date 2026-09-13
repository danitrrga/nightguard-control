"""The desktop panel's payload: read-only, fail-closed, and honest about the hour.

Omarchy 4 replaced Waybar with quickshell, so the bar module this project shipped
has no host any more and there is currently no read-only surface on the desktop at
all. This is its replacement's data source.

The property that matters most is that the panel never says the edit window is
open when the signer would refuse. A panel that disagrees with the signer is worse
than no panel: it invites the user to spend a fingerprint on a change that is
going to be rejected.
"""
from __future__ import annotations

import json

import pytest

from ngtui import panel


def _cfg(enabled=True, start="05:30", end="14:00", with_window=True,
         native=None, browser=None):
    cfg = {"blocking": {
        "native_apps": native if native is not None else {
            "enabled": True, "mode": "blocklist", "blacklist": ["steam", "discord"],
            "allowlist": [], "block_games": False,
        },
        "browser_extension": browser if browser is not None else {
            "enabled": True, "extension_id": "abc", "blocked_urls": [],
        },
    }}
    if with_window:
        cfg["edit_window"] = {"enabled": enabled, "start": start, "end": end}
    return cfg


# --- the edit window view ----------------------------------------------------

def test_the_window_reads_open_inside_its_hours():
    view = panel.edit_window_view(_cfg(), 10 * 60)
    assert view["open"] is True
    assert "14:00" in view["detail"]


def test_the_window_reads_closed_at_two_in_the_morning():
    view = panel.edit_window_view(_cfg(), 2 * 60)
    assert view["open"] is False
    assert "05:30" in view["detail"], "it must say when it opens again"


def test_an_unverified_clock_reads_closed():
    """Fail closed, matching the signer. Showing OPEN on an unresolvable clock
    would send the user to a fingerprint prompt for a change about to be refused."""
    view = panel.edit_window_view(_cfg(), None)
    assert view["open"] is False
    assert "unverified" in view["detail"]


def test_a_malformed_window_reads_closed():
    view = panel.edit_window_view(_cfg(start="half past five"), 10 * 60)
    assert view["open"] is False


def test_a_disabled_window_reads_open_at_any_hour():
    view = panel.edit_window_view(_cfg(enabled=False), 2 * 60)
    assert view["open"] is True
    assert view["configured"] is True


def test_an_absent_window_says_so_rather_than_implying_one():
    view = panel.edit_window_view(_cfg(with_window=False), 2 * 60)
    assert view["configured"] is False
    assert view["open"] is True


@pytest.mark.parametrize("minutes,expected", [
    (23 * 60, True), (1 * 60, True), (12 * 60, False), (2 * 60, False), (22 * 60, True),
])
def test_an_overnight_window_does_not_invert(minutes, expected):
    view = panel.edit_window_view(_cfg(start="22:00", end="02:00"), minutes)
    assert view["open"] is expected


def test_a_degenerate_window_reads_closed():
    view = panel.edit_window_view(_cfg(start="05:30", end="05:30"), 5 * 60 + 30)
    assert view["open"] is False


# --- the blocking view -------------------------------------------------------

def test_blocking_counts_the_list_the_mode_actually_uses():
    """In allowlist mode the blacklist is inert, so showing its length would tell
    the user the wrong number about the wrong list."""
    blocklist = panel.blocking_view(_cfg())
    assert blocklist["mode"] == "blocklist" and blocklist["apps"] == 2

    allow = panel.blocking_view(_cfg(native={
        "enabled": True, "mode": "allowlist",
        "blacklist": ["steam", "discord"], "allowlist": ["zen-bin"], "block_games": False,
    }))
    assert allow["mode"] == "allowlist" and allow["apps"] == 1


def test_an_unknown_mode_is_reported_as_blocklist():
    view = panel.blocking_view(_cfg(native={"enabled": True, "mode": "nonsense",
                                            "blacklist": ["steam"], "allowlist": []}))
    assert view["mode"] == "blocklist"


def test_blocking_view_survives_a_config_with_nothing_in_it():
    view = panel.blocking_view({})
    assert view["apps"] == 0 and view["sites"] == 0 and view["apps_enabled"] is False


def test_the_blocked_names_are_in_the_payload():
    """This reverses an earlier rule, deliberately, and the reason is recorded.

    The panel used to emit counts only, so a passer-by could not read which
    things the owner blocks himself from. The owner weighed that against a panel
    that says "2" and cannot say WHICH two -- and a count can never show that an
    entry matches nothing. On this machine "discord" named nothing for months:
    the pact was not kept and the panel had no way to say so.
    """
    payload = panel.build("locked", 2, _cfg(), {"week_anchor": "2026-09-07"}, 2 * 60)
    names = [e["name"] for e in payload["blocking"]["entries"]]
    assert names == ["steam", "discord"]


def test_an_entry_nobody_resolved_reports_nothing_rather_than_guessing():
    """Not read is not the same as fine, and it is not the same as broken.

    A wrong "matches nothing" accuses the owner of a defect he does not have; a
    wrong silence tells him a pact is kept when it is not. Both are worse than
    an em dash, so an unresolved entry must carry None and the panel must draw
    it as unknown.
    """
    payload = panel.build("locked", 2, _cfg(), {}, 0)
    entries = payload["blocking"]["entries"]
    assert [e["state"] for e in entries] == [None, None]
    assert [e["label"] for e in entries] == [None, None]


def test_resolution_is_injected_and_reported_verbatim():
    """The panel renders what the enforcer's own matcher found; it never decides.

    A second opinion about what counts as a match would drift from the watchdog
    and start lying by degrees, so the only thing tested here is that what goes
    in comes out attached to the right entry.
    """
    payload = panel.build(
        "locked", 2, _cfg(), {}, 0,
        app_resolution={
            "steam": {"state": "running", "label": "Steam"},
            "discord": {"state": "unmatched", "label": None},
        },
    )
    assert payload["blocking"]["entries"] == [
        {"name": "steam", "label": "Steam", "state": "running"},
        {"name": "discord", "label": None, "state": "unmatched"},
    ]


def test_an_entry_missing_from_the_resolution_is_unknown_not_unmatched():
    """A partial read must degrade per entry, never spill one entry's verdict
    onto another."""
    payload = panel.build(
        "locked", 2, _cfg(), {}, 0,
        app_resolution={"steam": {"state": "running", "label": None}},
    )
    by_name = {e["name"]: e["state"] for e in payload["blocking"]["entries"]}
    assert by_name == {"steam": "running", "discord": None}


# --- the whole payload -------------------------------------------------------

def test_an_unknown_verdict_fails_closed_to_locked():
    """Never optimistic. An unrecognised verdict must not paint the panel green."""
    payload = panel.build("something-new", 3, _cfg(), {}, 10 * 60)
    assert payload["verdict"] == "locked"
    assert payload["word"] == "LOCKED"


@pytest.mark.parametrize("verdict,word", [
    ("locked", "LOCKED"), ("grace_active", "GRACE"), ("outside_curfew", "OPEN"),
    ("clock_tamper", "TAMPER"), ("offline_blocked", "OFFLINE"),
])
def test_every_guard_verdict_has_a_word(verdict, word):
    assert panel.build(verdict, 0, _cfg(), {}, 0)["word"] == word


def test_the_token_count_is_clamped_to_the_signers_ceiling():
    from ngtui.backend import WEEKLY_TOKENS

    assert panel.build("locked", 99, _cfg(), {}, 0)["tokens_left"] == WEEKLY_TOKENS
    assert panel.build("locked", -5, _cfg(), {}, 0)["tokens_left"] == 0
    assert panel.build("locked", 1, _cfg(), {}, 0)["tokens_total"] == WEEKLY_TOKENS


def test_the_payload_is_json_serialisable():
    """The panel parses this with JSON.parse; anything exotic would blank it."""
    json.dumps(panel.build("locked", 2, _cfg(), {"week_anchor": "2026-09-07"}, 2 * 60))
    json.dumps(panel.UNAVAILABLE)


def test_the_unavailable_payload_has_every_key_the_panel_reads():
    """The fail-closed object is rendered by the same QML as a live one, so a
    missing key shows as 'undefined' on the desktop."""
    live = panel.build("locked", 2, _cfg(), {}, 0)
    assert set(panel.UNAVAILABLE) == set(live)
    assert set(panel.UNAVAILABLE["edit_window"]) == set(live["edit_window"])
    assert set(panel.UNAVAILABLE["blocking"]) == set(live["blocking"])
    assert set(panel.UNAVAILABLE["theme"]) == set(live["theme"])


def test_the_unavailable_payload_is_not_reassuring():
    assert panel.UNAVAILABLE["edit_window"]["open"] is False
    assert panel.UNAVAILABLE["warnings"], "silence would read as 'all fine'"


# --- theme -------------------------------------------------------------------

def test_theme_roles_come_from_the_live_palette():
    view = panel.theme_view({
        "background": "#2d353b", "foreground": "#d3c6aa", "accent": "#7fbbb3",
        "green": "#a7c080", "red": "#e67e80", "yellow": "#dbbc7f",
        "lighter_background": "#343f44", "light_foreground": "#9da9a0",
    })
    assert view["background"] == "#2d353b"
    assert view["accent"] == "#7fbbb3"
    assert view["alert"] == "#e67e80"
    assert view["ok"] == "#a7c080"


def test_a_partial_palette_loses_one_colour_not_all_of_them():
    view = panel.theme_view({"background": "#111111"})
    assert view["background"] == "#111111"
    assert view["accent"] == panel.THEME_FALLBACK["accent"]


def test_a_missing_palette_falls_back_whole():
    assert panel.theme_view({}) == panel.THEME_FALLBACK
    assert panel.theme_view(None) == panel.THEME_FALLBACK


def test_non_colour_values_are_ignored():
    """colors.toml carries `mode = "dark"` alongside the hex values."""
    view = panel.theme_view({"background": "dark", "accent": 7})
    assert view["background"] == panel.THEME_FALLBACK["background"]
    assert view["accent"] == panel.THEME_FALLBACK["accent"]


# --- warnings ----------------------------------------------------------------

def test_membership_of_the_empower_group_is_surfaced():
    """`run0 --empower` makes every polkit action return YES with no prompt, which
    silently undoes the rule that makes stopping the watchdog cost an
    authentication. If it ever happens, the panel should say so."""
    message = panel.empower_warning("empower:x:997:danitrrga")
    assert message and "empower" in message


def test_an_empty_empower_group_is_not_a_warning():
    assert panel.empower_warning("empower:x:997:") is None


def test_a_missing_empower_group_is_not_a_warning():
    assert panel.empower_warning(None) is None
    assert panel.empower_warning("") is None
