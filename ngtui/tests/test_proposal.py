"""The staged-edit vocabulary: what the panel may propose, and what it may not.

Two properties carry the weight here. The editable set is CLOSED, so a key the
panel was not designed to explain the cost of cannot be addressed at all; and a
list entry is validated against a whitelist rather than escaped, because an
escape that is wrong once writes a config saying something the user never asked
for.

Everything goes through ``lineedit``, never a YAML emitter -- a re-serialised
config changes the bytes the root signer HMACs, and the guard would then revert
the user's own commit.
"""
from __future__ import annotations

import os
import sys

import pytest

_STACK = os.environ.get("NIGHTGUARD_STACK_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "linux",
)
if _STACK not in sys.path:
    sys.path.insert(0, _STACK)
import ngcommon as ng  # noqa: E402

from ngtui import proposal  # noqa: E402

FIXTURE = '''blocking:
  browser_extension:
    enabled: true
    blocked_urls: []
  native_apps:
    enabled: true
    blacklist:
      - steam
      - discord
    mode: blocklist
    block_games: false
    allowlist:
      - zen-bin
curfew:
  enabled: true
  start: "21:30"
'''


def _blocking(text):
    return ng.yaml_load(text)["blocking"]


# --- what it can do ----------------------------------------------------------

def test_a_boolean_flips_and_nothing_else_moves():
    out = proposal.apply_ops(FIXTURE, [
        {"key": "blocking.native_apps.block_games", "action": "set", "value": True},
    ])
    assert _blocking(out)["native_apps"]["block_games"] is True
    assert ng.yaml_load(out)["curfew"] == ng.yaml_load(FIXTURE)["curfew"]


def test_ops_apply_in_the_order_given():
    """Moving an app between lists is a remove and an add, and the panel is
    allowed to express that as two ops in one proposal."""
    out = proposal.apply_ops(FIXTURE, [
        {"key": "blocking.native_apps.blacklist", "action": "remove", "value": "discord"},
        {"key": "blocking.native_apps.allowlist", "action": "add", "value": "discord"},
    ])
    native = _blocking(out)["native_apps"]
    assert native["blacklist"] == ["steam"]
    assert native["allowlist"] == ["zen-bin", "discord"]


def test_the_first_site_ever_blocked_is_readable_yaml():
    out = proposal.apply_ops(FIXTURE, [
        {"key": "blocking.browser_extension.blocked_urls", "action": "add",
         "value": "youtube.com"},
    ])
    assert _blocking(out)["browser_extension"]["blocked_urls"] == ["youtube.com"]


def test_the_mode_takes_only_its_two_values():
    out = proposal.apply_ops(FIXTURE, [
        {"key": "blocking.native_apps.mode", "action": "set", "value": "allowlist"},
    ])
    assert _blocking(out)["native_apps"]["mode"] == "allowlist"


def test_a_game_title_with_punctuation_survives():
    """Real titles on this machine include ``Yu-Gi-Oh!  Master Duel`` and
    ``100% Orange Juice``. A charset that refused them would make the picker
    offer games it then could not accept."""
    for title in ("Yu-Gi-Oh!  Master Duel", "100% Orange Juice", "Pokémon Unite"):
        out = proposal.apply_ops(FIXTURE, [
            {"key": "blocking.native_apps.blacklist", "action": "add", "value": title},
        ])
        assert title in _blocking(out)["native_apps"]["blacklist"]


# --- what it refuses ---------------------------------------------------------

@pytest.mark.parametrize("key", [
    "timezone",                  # shifts the hour the edit window is judged in
    "curfew.message",            # prose, not a rule
    "curfew.block_when_offline",
    "clock_protection.max_offset_minutes",
    "watchdog.check_interval_seconds",
])
def test_a_key_outside_the_editable_set_is_refused(key):
    """The panel prices what it proposes, so it may only propose what it was
    built to explain. `timezone` is the sharp one: the signer judges the edit
    window in the SIGNED config's timezone, so editing it from a surface that
    does not say so would move the gate without ever mentioning the gate."""
    with pytest.raises(ValueError, match="not an editable field"):
        proposal.apply_ops(FIXTURE, [
            {"key": key, "action": "set", "value": False},
        ])


@pytest.mark.parametrize("value", ["a\nb", "a\tb", "a#b", "a:b", '"q"', "'q'", "-x", ""])
def test_an_entry_that_would_change_the_line_is_refused(value):
    with pytest.raises(ValueError):
        proposal.apply_ops(FIXTURE, [
            {"key": "blocking.native_apps.blacklist", "action": "add", "value": value},
        ])


def test_a_newline_cannot_smuggle_a_second_entry():
    """The whole reason the check is a whitelist: one accepted newline is one
    extra kill the user never asked for."""
    with pytest.raises(ValueError):
        proposal.apply_ops(FIXTURE, [
            {"key": "blocking.native_apps.blacklist", "action": "add",
             "value": "spotify\n      - firefox"},
        ])


def test_a_list_op_on_a_boolean_is_refused():
    with pytest.raises(ValueError, match="takes 'set'"):
        proposal.apply_ops(FIXTURE, [
            {"key": "blocking.native_apps.block_games", "action": "add", "value": "x"},
        ])


def test_a_boolean_that_is_not_a_boolean_is_refused():
    with pytest.raises(ValueError, match="true or false"):
        proposal.apply_ops(FIXTURE, [
            {"key": "blocking.native_apps.block_games", "action": "set", "value": "true"},
        ])


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError, match="blocklist or allowlist"):
        proposal.apply_ops(FIXTURE, [
            {"key": "blocking.native_apps.mode", "action": "set", "value": "off"},
        ])


def test_nothing_is_applied_when_a_later_op_fails():
    """A half-applied proposal is the one outcome with no honest description --
    the cost line would price a config that is not the one on disk."""
    with pytest.raises(ValueError):
        proposal.apply_ops(FIXTURE, [
            {"key": "blocking.native_apps.blacklist", "action": "add", "value": "spotify"},
            {"key": "timezone", "action": "set", "value": "UTC"},
        ])
    # The input text is untouched -- apply_ops returns a new string or raises.
    assert _blocking(FIXTURE)["native_apps"]["blacklist"] == ["steam", "discord"]


def test_no_ops_is_the_config_itself_byte_for_byte():
    assert proposal.apply_ops(FIXTURE, []) == FIXTURE
    assert proposal.apply_ops(FIXTURE, None) == FIXTURE
