"""The migration that makes the new features non-inert, and its refusal to corrupt.

The edit-window gate reads its window from the sanctioned config, and a config
without the block is ungated by design so older installs keep working. That
back-compat is also a trap: without a migration the feature would ship, pass its
tests, and enforce nothing. deploy.sh runs this once.

It edits line-by-line rather than round-tripping YAML. The config is
human-written, carries comments explaining each field, and is parsed by a
deliberately minimal parser shared with the guard. A real YAML emitter would
reformat it and change the bytes the HMAC signs for no reason.
"""
from __future__ import annotations

from ngtui import backend  # noqa: F401  (puts the trust stack on sys.path)

import ngcommon as ng
import nightguard_ctl as ctl


_BEFORE = '''\
timezone: Europe/Amsterdam

curfew:
  enabled: true
  start: "21:30"
  end: "05:30"
  allow_commands:
    - "/shutdown"
    - "/plan"

# What gets blocked during curfew (Linux).
blocking:
  browser_extension:
    enabled: true
    # StayFree - Website Blocker.
    extension_id: elfaihghhjjoknimpccccmkioofjjfkf
  native_apps:
    enabled: true
    # Killed during curfew.
    blacklist:
      - steam
      - discord
'''


def _migrate(text):
    out = text.rstrip("\n") + "\n" + ctl.EDIT_WINDOW_BLOCK
    out = ctl._append_to_block(out, "  native_apps:", ctl.NATIVE_APPS_KEYS)
    out = ctl._append_to_block(out, "  browser_extension:", ctl.BROWSER_KEYS)
    return out


def test_every_new_key_parses_back_through_the_guards_own_parser():
    doc = ng.yaml_load(_migrate(_BEFORE))
    assert doc["edit_window"] == {"enabled": True, "start": "05:30", "end": "14:00"}
    native = doc["blocking"]["native_apps"]
    assert native["mode"] == "blocklist"
    assert native["block_games"] is False
    assert native["allowlist"] == ["zen-bin", "foot"]
    assert doc["blocking"]["browser_extension"]["blocked_urls"] == []


def test_nothing_that_was_already_there_changes_value():
    before = ng.yaml_load(_BEFORE)
    after = ng.yaml_load(_migrate(_BEFORE))
    for path in (
        ("timezone",),
        ("curfew", "enabled"), ("curfew", "start"), ("curfew", "end"),
        ("curfew", "allow_commands"),
        ("blocking", "browser_extension", "enabled"),
        ("blocking", "browser_extension", "extension_id"),
        ("blocking", "native_apps", "enabled"),
        ("blocking", "native_apps", "blacklist"),
    ):
        old = ctl._read_field(before, list(path))
        new = ctl._read_field(after, list(path))
        assert old == new, "%s changed from %r to %r" % (".".join(path), old, new)


def test_the_human_comments_survive():
    """They are the reason the config is not round-tripped through a YAML emitter."""
    migrated = _migrate(_BEFORE)
    assert "# StayFree - Website Blocker." in migrated
    assert "# What gets blocked during curfew (Linux)." in migrated
    assert "# Killed during curfew." in migrated


def test_new_keys_land_inside_their_parent_block():
    """Indentation is the whole of YAML nesting. A key inserted at the wrong depth
    parses as a sibling of `blocking` and the feature reads as unconfigured."""
    for line in _migrate(_BEFORE).split("\n"):
        stripped = line.strip()
        if stripped.startswith(("mode:", "block_games:", "allowlist:", "blocked_urls:")):
            assert line.startswith("    ") and not line.startswith("     "), (
                "wrong indent for %r" % line
            )


def test_the_migration_is_idempotent():
    """deploy.sh runs on every deploy. Re-adding the keys would corrupt the file
    and re-signing on every run would churn the audit chain for nothing."""
    once = _migrate(_BEFORE)
    doc = ng.yaml_load(once)
    assert ctl._read_edit_window(doc) is not None
    assert "mode" in (ctl._read_field(doc, ["blocking", "native_apps"]) or {})
    assert "blocked_urls" in (ctl._read_field(doc, ["blocking", "browser_extension"]) or {})


def test_appending_to_a_missing_block_changes_nothing():
    """A config that never had the parent must be left alone rather than half-
    edited into something the parser reads differently."""
    text = "timezone: Europe/Amsterdam\n"
    assert ctl._append_to_block(text, "  native_apps:", ["    mode: blocklist"]) == text


def test_appending_lands_after_a_list_not_inside_it():
    """The last child of native_apps is a list. Inserting between its items would
    turn `mode: blocklist` into a list element."""
    doc = ng.yaml_load(_migrate(_BEFORE))
    assert doc["blocking"]["native_apps"]["blacklist"] == ["steam", "discord"]
    assert doc["blocking"]["native_apps"]["mode"] == "blocklist"


def test_a_trailing_blank_line_does_not_push_keys_out_of_the_block():
    with_blank = _BEFORE.replace(
        "    blacklist:\n      - steam\n      - discord\n",
        "    blacklist:\n      - steam\n      - discord\n\n",
    )
    doc = ng.yaml_load(_migrate(with_blank))
    assert doc["blocking"]["native_apps"]["mode"] == "blocklist"


def test_the_migrated_defaults_change_no_behaviour_by_themselves():
    """Blocklist mode with the existing blacklist, games off, no blocked sites.
    Turning any of it on is the user's decision, made from the TUI at the usual
    cost -- not something a deploy does to him."""
    doc = ng.yaml_load(_migrate(_BEFORE))
    native = doc["blocking"]["native_apps"]
    assert native["mode"] == "blocklist", "allowlist mode would close his terminals"
    assert native["block_games"] is False
    assert doc["blocking"]["browser_extension"]["blocked_urls"] == []


def test_the_new_fields_are_all_classified():
    """Every editable field is a bypass vector. A field the classifier does not
    know about can be changed for free, so a new key with no entry is a hole."""
    labels = {label for label, _keys, _kind in ctl.FIELD_TABLE}
    assert {
        "blocking.native_apps.mode",
        "blocking.native_apps.allowlist",
        "blocking.native_apps.block_games",
        "blocking.browser_extension.blocked_urls",
    } <= labels


def test_switching_to_allowlist_mode_is_a_tightening():
    before = ng.yaml_load(_migrate(_BEFORE))
    after = ng.yaml_load(_migrate(_BEFORE).replace("mode: blocklist", "mode: allowlist"))
    assert dict(ctl.classify_change(before, after))["blocking.native_apps.mode"] == ctl.TIGHTEN


def test_switching_away_from_allowlist_mode_is_a_loosening():
    strict = ng.yaml_load(_migrate(_BEFORE).replace("mode: blocklist", "mode: allowlist"))
    loose = ng.yaml_load(_migrate(_BEFORE))
    assert dict(ctl.classify_change(strict, loose))["blocking.native_apps.mode"] == ctl.LOOSEN


def test_a_typo_in_the_mode_is_not_a_free_tightening():
    """Anything that is not the strict mode counts as the permissive one, so a
    misspelling cannot be used to leave allowlist mode without paying."""
    strict = ng.yaml_load(_migrate(_BEFORE).replace("mode: blocklist", "mode: allowlist"))
    typo = ng.yaml_load(_migrate(_BEFORE).replace("mode: blocklist", "mode: allowlisst"))
    assert dict(ctl.classify_change(strict, typo))["blocking.native_apps.mode"] == ctl.LOOSEN


def test_adding_to_the_allowlist_is_a_loosening():
    """Mirror polarity to the blacklist: the allowlist permits, so growing it
    permits more."""
    before = ng.yaml_load(_migrate(_BEFORE))
    after = ng.yaml_load(_migrate(_BEFORE).replace("      - foot", "      - foot\n      - steam"))
    assert dict(ctl.classify_change(before, after))["blocking.native_apps.allowlist"] == ctl.LOOSEN


def test_removing_a_blocked_site_is_a_loosening():
    with_site = ng.yaml_load(
        _migrate(_BEFORE).replace("blocked_urls: []", "blocked_urls:\n      - discord.com")
    )
    without = ng.yaml_load(_migrate(_BEFORE))
    dirs = dict(ctl.classify_change(with_site, without))
    assert dirs["blocking.browser_extension.blocked_urls"] == ctl.LOOSEN


def test_turning_off_game_blocking_is_a_loosening():
    on = ng.yaml_load(_migrate(_BEFORE).replace("block_games: false", "block_games: true"))
    off = ng.yaml_load(_migrate(_BEFORE))
    assert dict(ctl.classify_change(on, off))["blocking.native_apps.block_games"] == ctl.LOOSEN
