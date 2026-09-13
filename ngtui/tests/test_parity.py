"""The retirement gate, as a test rather than as a promise.

The rule the project set itself is one sentence: *"The `ngtui` Textual terminal
app is retired in one deliberate step, once the panel can do everything it did
— not incrementally, and not until parity is reached."*

"Everything it did" is not a judgement call. The terminal editor's whole
surface is one table — ``ngtui/ngtui/widgets/edit.py:EDITABLE_FIELDS`` — and
the panel's is another — ``ngtui/ngtui/proposal.py:EDITABLE``. Parity is the
first being a subset of the second, and nothing else needs arguing about.

This test exists so the retirement can be PROVEN on the day it happens instead
of asserted, and so that a field quietly dropped from the panel afterwards
fails here rather than being discovered by someone who cannot change their
curfew any more.

When the terminal app is deleted, `edit.py` goes with it. At that point this
test keeps working from the frozen copy below, which is what the table said on
the day parity was reached — the historical record the claim rests on.
"""
from __future__ import annotations

import os

import pytest

from ngtui import proposal

# The terminal editor's table, verbatim, on the day parity was reached
# (2026-09-13). Frozen here on purpose: it is evidence, and evidence that is
# read out of a file which is about to be deleted is evidence that disappears
# exactly when someone would want to check it.
TERMINAL_EDITOR_FIELDS = (
    "curfew.enabled",
    "curfew.start",
    "curfew.end",
    "curfew.allow_commands",
    "clock_protection.enabled",
    "watchdog.enabled",
    "blocking.browser_extension.enabled",
    "blocking.browser_extension.extension_id",
    "blocking.native_apps.enabled",
    "blocking.native_apps.blacklist",
    "edit_window.enabled",
    "edit_window.start",
    "edit_window.end",
)

_EDIT_PY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ngtui", "widgets", "edit.py",
)


@pytest.mark.skipif(not os.path.exists(_EDIT_PY),
                    reason="the terminal editor is retired; the frozen copy is the record")
def test_the_frozen_copy_still_matches_the_living_table():
    """While the terminal app is still here, the frozen list must not drift
    from it — otherwise the parity claim is measured against a fiction."""
    from ngtui.widgets.edit import EDITABLE_FIELDS

    live = tuple(dotted for _label, dotted, _kind in EDITABLE_FIELDS)
    assert live == TERMINAL_EDITOR_FIELDS, (
        "the terminal editor's field table changed; update the frozen copy in "
        "this file and re-check parity before retiring anything"
    )


# The one field the panel deliberately will not take over, and the reason.
# Not a gap in the panel: a hole in the terminal app that is not being copied.
UNJUDGED_BY_THE_SIGNER = ("blocking.browser_extension.extension_id",)


def test_the_one_field_left_behind_is_one_the_signer_cannot_judge():
    """The terminal app let you edit the extension id. The signer's FIELD_TABLE
    has no entry for it, so `classify_change` returns no direction: the change
    classified as nothing, priced as free, and was written anyway.

    Pointing the managed browser policy at a different or non-existent
    extension is how site blocking gets switched off entirely, so "free and
    unjudged" is the wrong answer for it twice over. The panel does not build a
    control for a write the trust boundary cannot judge. Giving it a direction
    means changing the signer's own table — which decides what costs a token —
    and that is the owner's call, not a side effect of a UI migration.
    """
    import nightguard_ctl as ctl

    classified = {label for label, _keys, _kind in ctl.FIELD_TABLE}
    for key in UNJUDGED_BY_THE_SIGNER:
        assert key in TERMINAL_EDITOR_FIELDS, "%s was never in the old editor" % key
        assert key not in proposal.EDITABLE, "%s must not be offered" % key
        assert key not in classified, (
            "%s now HAS a direction in the signer — it can be given back to the "
            "panel, and this exception should go" % key
        )


def test_the_panel_can_edit_everything_the_terminal_app_could():
    missing = [f for f in TERMINAL_EDITOR_FIELDS
               if f not in proposal.EDITABLE and f not in UNJUDGED_BY_THE_SIGNER]
    assert missing == [], (
        "the panel cannot edit %s — the terminal app is not retirable until it "
        "can, because retiring it would take those away from the only person "
        "who uses this" % ", ".join(missing)
    )


def test_the_panel_reaches_the_four_the_terminal_app_never_could():
    """Parity is the floor, not the point. These four are the reason the panel
    replaced the terminal app rather than being restyled alongside it: they are
    the blocking keys that had no editor at all."""
    for key in ("blocking.native_apps.block_games",
                "blocking.native_apps.mode",
                "blocking.native_apps.allowlist",
                "blocking.browser_extension.blocked_urls"):
        assert key in proposal.EDITABLE, key
        assert key not in TERMINAL_EDITOR_FIELDS, (
            "%s was reachable from the terminal app after all — the claim that "
            "these four were unreachable is in REQUIREMENTS.md and would be wrong" % key
        )


def test_every_editable_key_is_one_the_signer_classifies():
    """A key the signer has no direction for is a key the panel would price as
    'no change' and then successfully write. The cost line would be honest
    about a classification that never happened."""
    import nightguard_ctl as ctl

    classified = {label for label, _keys, _kind in ctl.FIELD_TABLE}
    # The signer judges the two curfew times jointly, as a window, rather than
    # one at a time — `classify_change` appends `curfew.window` for the pair.
    classified |= {"curfew.start", "curfew.end", "curfew.window"}
    # Same shape for the edit window: one verdict for the whole block.
    classified |= {"edit_window.enabled", "edit_window.start", "edit_window.end"}

    unclassified = sorted(k for k in proposal.EDITABLE if k not in classified)
    assert unclassified == [], (
        "the signer has no direction for %s, so a change to it would price as "
        "free and still be written" % ", ".join(unclassified)
    )
