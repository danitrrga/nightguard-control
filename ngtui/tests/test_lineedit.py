"""Headless tests for lineedit.py — format-preserving per-field LINE edits.

The whole point of lineedit.py is that the proposed config is composed by editing
the *specific* lines of the sanctioned text, NEVER by re-serializing through a YAML
emitter. A re-emit would change the bytes ``ngcommon.yaml_load`` parses and the root
signer HMACs → the guard would revert the user's own commit (T-10-09).

So every assertion here is two-pronged:
  1. the edit re-parses via the LIVE ``ngcommon.yaml_load`` to the expected value, and
  2. ONLY the targeted field's bytes changed — every other line is byte-identical
     (the round-trip guard).

conftest.py points NIGHTGUARD_STACK_DIR/NIGHTGUARD_DIR at the live stack so
``ngcommon`` imports cleanly for the round-trip parse.
"""
from __future__ import annotations

import os
import sys

import pytest

# Import the live ngcommon via the same bootstrap backend uses, to round-trip the edits.
_STACK = os.environ.get(
    "NIGHTGUARD_STACK_DIR", "/home/danitrrga/dev/Projects/nightguard-control/scripts/linux"
)
if _STACK not in sys.path:
    sys.path.insert(0, _STACK)
import ngcommon as ng  # noqa: E402

from ngtui.lineedit import (  # noqa: E402
    list_add,
    list_remove,
    set_scalar,
    toggle_bool,
)

# A representative fixture mirroring the real config.sanctioned.yaml layout
# (indentation, quoted times, comments, nested blocking:, and two list blocks).
FIXTURE = '''timezone: Europe/Amsterdam

curfew:
  enabled: true
  start: "20:45"
  end: "05:30"
  allow_commands:
    - "/shutdown"
    - "/plan"
  block_when_offline: true
  message: "the house is closed for the night."

clock_protection:
  enabled: true
  max_offset_minutes: 5

# Revert-watchdog cadence.
watchdog:
  enabled: true
  check_interval_seconds: 60

# What gets blocked during curfew (Linux).
blocking:
  browser_extension:
    enabled: true
    # StayFree force-installed via root managed policy.
    extension_id: elfaihghhjjoknimpccccmkioofjjfkf
  native_apps:
    enabled: true
    # Hyprland window classes killed during curfew.
    blacklist:
      - steam
      - discord
'''


def _changed_lines(before: str, after: str) -> list[tuple[int, str, str]]:
    """Return (idx, old, new) for every line that differs (byte-stable elsewhere)."""
    b, a = before.splitlines(), after.splitlines()
    diffs: list[tuple[int, str, str]] = []
    for i in range(max(len(b), len(a))):
        ob = b[i] if i < len(b) else "<absent>"
        oa = a[i] if i < len(a) else "<absent>"
        if ob != oa:
            diffs.append((i, ob, oa))
    return diffs


# --- Test 1: set_scalar (curfew.start) ---------------------------------------


def test_set_scalar_replaces_only_value_and_reparses():
    out = set_scalar(FIXTURE, "curfew.start", "21:30")
    # Re-parses via the LIVE parser to the new value.
    assert ng.yaml_load(out)["curfew"]["start"] == "21:30"
    # ONLY the start: line changed; indentation + quoting preserved.
    diffs = _changed_lines(FIXTURE, out)
    assert len(diffs) == 1
    _, old, new = diffs[0]
    assert old.strip() == 'start: "20:45"'
    assert new == '  start: "21:30"'  # original 2-space indent + quote style preserved
    # Every other field is byte-stable.
    base, after = ng.yaml_load(FIXTURE), ng.yaml_load(out)
    base["curfew"]["start"] = "21:30"
    assert after == base


def test_set_scalar_preserves_trailing_comment():
    full = (
        "blocking:\n"
        "  browser_extension:\n"
        "    extension_id: abc123   # the StayFree id\n"
    )
    out = set_scalar(full, "blocking.browser_extension.extension_id", "zzz999")
    assert "# the StayFree id" in out
    assert "zzz999" in out
    assert "abc123" not in out


def test_set_scalar_missing_field_raises():
    with pytest.raises(ValueError):
        set_scalar(FIXTURE, "curfew.nonexistent", "x")
    with pytest.raises(ValueError):
        set_scalar(FIXTURE, "no.such.parent", "x")


# --- Test 2: toggle_bool (watchdog.enabled) ----------------------------------


def test_toggle_bool_flips_only_target_line():
    out = toggle_bool(FIXTURE, "watchdog.enabled", False)
    assert ng.yaml_load(out)["watchdog"]["enabled"] is False
    diffs = _changed_lines(FIXTURE, out)
    assert len(diffs) == 1
    _, old, new = diffs[0]
    assert old.strip() == "enabled: true"
    assert new == "  enabled: false"
    # The OTHER enabled: true lines (curfew/clock/blocking) are untouched.
    assert out.count("enabled: true") == FIXTURE.count("enabled: true") - 1


def test_toggle_bool_emits_lowercase():
    out = toggle_bool(FIXTURE, "clock_protection.enabled", False)
    assert "false" in out
    assert "False" not in out  # lowercase YAML bool, not Python repr


def test_toggle_bool_distinguishes_nested_same_named_keys():
    # blocking.native_apps.enabled vs blocking.browser_extension.enabled both
    # named "enabled" — the dotted path must pick the right nesting.
    out = toggle_bool(FIXTURE, "blocking.native_apps.enabled", False)
    doc = ng.yaml_load(out)
    assert doc["blocking"]["native_apps"]["enabled"] is False
    # browser_extension.enabled stayed true.
    assert doc["blocking"]["browser_extension"]["enabled"] is True


# --- Test 3: list_add / list_remove ------------------------------------------


def test_list_add_inserts_under_key_block():
    out = list_add(FIXTURE, "curfew.allow_commands", "/relax")
    doc = ng.yaml_load(out)
    assert doc["curfew"]["allow_commands"] == ["/shutdown", "/plan", "/relax"]
    # Inserted at the end of the list block with the existing item indentation.
    assert "    - /relax" in out
    # The other list (blacklist) is untouched.
    assert doc["blocking"]["native_apps"]["blacklist"] == ["steam", "discord"]


def test_list_remove_drops_matching_entry():
    out = list_remove(FIXTURE, "blocking.native_apps.blacklist", "steam")
    doc = ng.yaml_load(out)
    assert doc["blocking"]["native_apps"]["blacklist"] == ["discord"]
    assert "- steam" not in out
    # allow_commands untouched.
    assert doc["curfew"]["allow_commands"] == ["/shutdown", "/plan"]


def test_list_remove_missing_entry_raises():
    with pytest.raises(ValueError):
        list_remove(FIXTURE, "blocking.native_apps.blacklist", "not-present")


def test_list_add_missing_key_raises():
    with pytest.raises(ValueError):
        list_add(FIXTURE, "curfew.no_such_list", "x")


# --- Test 4: round-trip guard — only the targeted field changes ---------------


def test_round_trip_changes_only_targeted_field():
    """Applying an edit then yaml_load must not raise and must change ONLY the
    targeted field; all other keys remain byte-stable in the parsed doc."""
    base = ng.yaml_load(FIXTURE)

    out = set_scalar(FIXTURE, "curfew.end", "06:00")
    after = ng.yaml_load(out)  # must not raise
    expected = {k: v for k, v in base.items()}
    expected["curfew"] = {**base["curfew"], "end": "06:00"}
    assert after == expected

    # Quoting style of the untouched neighbour line is preserved verbatim.
    assert 'start: "20:45"' in out
