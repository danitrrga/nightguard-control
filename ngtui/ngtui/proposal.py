"""proposal.py — turn a list of staged edits into the proposed config TEXT.

The desktop panel stages field edits; this is where they become bytes. It exists
so that exactly one implementation of "what an edit does to the config" lives in
the codebase, in Python, next to the signer -- and never in QML. A second
implementation in the panel would drift from this one and start signing configs
the user did not describe.

Two rules the surface depends on:

* **No YAML emitter.** Every op goes through ``lineedit``, which edits the
  addressed lines and leaves every other byte alone. Re-serialising would change
  the bytes the root signer HMACs and the guard would revert the user's own
  commit.
* **The editable set is closed.** A key not in ``EDITABLE`` is refused, loudly.
  The panel can only propose what it was designed to explain the cost of; an
  open key set would let a typo silently address ``curfew.enabled``.

Ops are plain dicts so they cross the ``Process`` boundary as JSON:

    {"key": "blocking.native_apps.blacklist", "op": "add", "value": "spotify"}
    {"key": "blocking.native_apps.block_games", "op": "set", "value": true}
"""
from __future__ import annotations

from ngtui import lineedit

# key -> kind. The kind decides which ops are legal on it, so a list op on a
# boolean is refused rather than producing nonsense the signer would then judge.
#
# This set is the retirement gate. The terminal app is retired "once the panel
# can do everything it did" (PANEL-03), and everything it did is its own
# ``EDITABLE_FIELDS`` table -- so every key there has to be here, and
# ``test_parity.py`` fails if one goes missing. The extra keys beyond it
# (block_games, mode, allowlist, blocked_urls) are the four the terminal app
# could never reach, which is why the phase that replaces it exists.
EDITABLE = {
    # the curfew itself
    "curfew.enabled": "bool",
    "curfew.start": "time",
    "curfew.end": "time",
    "curfew.allow_commands": "list",
    # the defences around it
    "clock_protection.enabled": "bool",
    "watchdog.enabled": "bool",
    # when the pact may be weakened
    "edit_window.enabled": "bool",
    "edit_window.start": "time",
    "edit_window.end": "time",
    # what the curfew ends
    "blocking.native_apps.enabled": "bool",
    "blocking.native_apps.block_games": "bool",
    "blocking.native_apps.mode": "mode",
    "blocking.native_apps.blacklist": "list",
    "blocking.native_apps.allowlist": "list",
    "blocking.browser_extension.enabled": "bool",
    "blocking.browser_extension.blocked_urls": "list",
    # blocking.browser_extension.extension_id is DELIBERATELY absent, and it is
    # the one field the terminal app could edit that this one will not.
    #
    # The signer's FIELD_TABLE has no entry for it, so `classify_change` returns
    # no direction for it at all: a change would classify as nothing, price as
    # free, and be written anyway. Pointing the managed browser policy at a
    # different or non-existent extension is how site blocking gets switched off
    # entirely, so "free and unjudged" is the wrong answer for it twice over.
    #
    # Offering it here would be building a control for a write the trust
    # boundary cannot judge. Giving it a direction means changing the signer's
    # own table -- which decides what costs a token -- and that is the owner's
    # call, not a side effect of a UI migration.
}

MODES = ("blocklist", "allowlist")

# What a list entry may contain. Entries are executable basenames (``steam``),
# absolute install paths (``/home/x/.steam/.../game.exe``), game titles
# (``Yu-Gi-Oh!  Master Duel``) or hostnames (``youtube.com``). The rule is a
# whitelist and not an escape, because an escape that is wrong once writes a
# config that says something the user never asked for.
#
# Any printable character, minus four that change what the line MEANS to the
# parser: ``#`` opens a comment, ``:`` opens a mapping, and the two quotes would
# be stripped back off on read, so a value containing one does not round-trip.
# Accented titles are allowed on purpose -- the config is UTF-8 and the parser
# reads it as UTF-8, so refusing ``Pokémon`` would be inventing a limit.
_FORBIDDEN_ENTRY_CHARS = frozenset("#:\"'")

# Characters that are ordinary mid-scalar but are YAML indicators in the first
# column of a value. Refused as a first character only.
_FORBIDDEN_FIRST_CHARS = frozenset("-#&*!|>%@`?,[]{}")


def validate_entry(value: str) -> str:
    """Return the entry, or raise ``ValueError`` naming what is wrong with it."""
    entry = str(value)
    if entry != entry.strip():
        raise ValueError("a list entry may not begin or end with a space")
    if not entry:
        raise ValueError("a list entry may not be empty")
    if len(entry) > 256:
        raise ValueError("a list entry may not be longer than 256 characters")
    bad = sorted({
        c for c in entry
        if c in _FORBIDDEN_ENTRY_CHARS or c < " " or c == "\x7f"
    })
    if bad:
        raise ValueError(
            "a list entry may not contain %s" % ", ".join(repr(c) for c in bad)
        )
    if entry[0] in _FORBIDDEN_FIRST_CHARS:
        raise ValueError("a list entry may not begin with %r" % entry[0])
    return entry


def validate_time(value) -> str:
    """Return ``HH:MM``, or raise saying what is wrong with it.

    The signer parses these with ``_parse_hhmm`` and treats an unparseable one
    as "no window", which for the edit window means the gate silently stops
    applying. A malformed time must be refused here, where the message reaches
    a person, rather than becoming a curfew that quietly does nothing.
    """
    text = str(value).strip()
    parts = text.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError("a time must look like HH:MM, got %r" % str(value))
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("a time must be between 00:00 and 23:59, got %r" % text)
    return "%02d:%02d" % (hour, minute)


def _apply_one(text: str, op: dict) -> str:
    key = str((op or {}).get("key") or "")
    action = str((op or {}).get("action") or (op or {}).get("op") or "")
    value = (op or {}).get("value")

    kind = EDITABLE.get(key)
    if kind is None:
        raise ValueError("not an editable field: %r" % key)

    if kind == "bool":
        if action != "set":
            raise ValueError("%r takes 'set', not %r" % (key, action))
        if not isinstance(value, bool):
            raise ValueError("%r takes true or false, got %r" % (key, value))
        return lineedit.toggle_bool(text, key, value)

    if kind == "time":
        if action != "set":
            raise ValueError("%r takes 'set', not %r" % (key, action))
        return lineedit.set_scalar(text, key, validate_time(value))

    if kind == "text":
        if action != "set":
            raise ValueError("%r takes 'set', not %r" % (key, action))
        return lineedit.set_scalar(text, key, validate_entry(value))

    if kind == "mode":
        if action != "set":
            raise ValueError("%r takes 'set', not %r" % (key, action))
        if value not in MODES:
            raise ValueError("%r must be one of %s" % (key, " or ".join(MODES)))
        return lineedit.set_scalar(text, key, str(value))

    # kind == "list"
    entry = validate_entry(value if isinstance(value, str) else str(value))
    if action == "add":
        return lineedit.list_add(text, key, entry)
    if action == "remove":
        return lineedit.list_remove(text, key, entry)
    raise ValueError("%r takes 'add' or 'remove', not %r" % (key, action))


def apply_ops(text: str, ops) -> str:
    """Apply every op in order and return the proposed text.

    Order matters and is the caller's: moving an app from the blocklist to the
    allowlist is a remove then an add, and the two touch different lines, so the
    result is the same either way -- but a remove of something a previous op
    added is not, and the panel is allowed to express that.

    Any failure raises before a single byte is returned. A half-applied proposal
    is the one outcome with no honest description, so there is no partial result.
    """
    out = text
    for op in list(ops or []):
        out = _apply_one(out, op)
    return out
