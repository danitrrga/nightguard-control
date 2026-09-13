"""The weekly token count has one source, and it is the signer.

Two display modules once defined a local ``WEEKLY_TOKENS = 3`` that could drift
from ``nightguard_ctl.WEEKLY_TOKENS``. A meter that says three while the signer
charges from two is a meter that tells the user he has a token he cannot spend,
which he will find out at the one moment he is trying to spend it.

Those modules are gone with the terminal app. The rule did not go with them —
it moved to the panel payload and to the QML that draws the pips, so this is
the same rule pointed at its new consumers.
"""
from __future__ import annotations

import os
import re

# Importing backend first bootstraps the trust stack onto sys.path; reference
# the signer module through backend.ctl so this test does not depend on import
# order.
from ngtui import backend
from ngtui import panel


def test_backend_reexports_signer_constant():
    assert backend.WEEKLY_TOKENS == backend.ctl.WEEKLY_TOKENS


def test_the_payload_reports_the_signers_ceiling_and_clamps_to_it():
    """`tokens_total` is what the pips are drawn from and `tokens_left` is how
    many are filled, so a count above the ceiling would draw a pip that cannot
    exist."""
    built = panel.build("locked", 99, {}, {}, 0)
    assert built["tokens_total"] == backend.ctl.WEEKLY_TOKENS
    assert built["tokens_left"] == backend.ctl.WEEKLY_TOKENS
    assert panel.build("locked", -5, {}, {}, 0)["tokens_left"] == 0


def test_no_qml_hardcodes_a_different_ceiling():
    """The QML draws one pip per token and must take the count from the payload.

    A literal here is how the bar ends up showing four pips on a three-token
    week: harmless-looking, and wrong in the direction that promises the user
    something the signer will refuse.

    ``NightguardWriter.qml`` carries ``property int tokensTotal: 3`` as the
    value before the first payload arrives. That one is allowed and is checked
    separately below — it is a placeholder that every consumer overrides, not a
    second opinion about the ceiling.
    """
    plugin = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "packaging", "omarchy", "plugins", "danitrrga.nightguard",
    )
    for name in ("NightguardPanel.qml", "NightguardWorkshop.qml", "BarWidget.qml"):
        with open(os.path.join(plugin, name), encoding="utf-8") as fh:
            text = fh.read()
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
        text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
        for match in re.finditer(r"model:\s*(.+)$", text, flags=re.M):
            expression = match.group(1)
            assert expression.strip().isdigit() is False, (
                "%s draws a Repeater from a literal count: %s" % (name, expression.strip())
            )


def test_the_writers_placeholder_is_overridden_by_every_consumer():
    """The placeholder is only honest if nothing ever renders it. Both surfaces
    that instantiate the writer must assign tokensTotal from the payload."""
    plugin = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "packaging", "omarchy", "plugins", "danitrrga.nightguard",
    )
    for name in ("NightguardPanel.qml", "NightguardWorkshop.qml"):
        with open(os.path.join(plugin, name), encoding="utf-8") as fh:
            text = fh.read()
        if "NightguardWriter {" not in text:
            continue
        block = text.split("NightguardWriter {", 1)[1]
        assert "tokensTotal:" in block.split("}", 1)[0], (
            "%s instantiates the writer without giving it the signer's ceiling, "
            "so its cost line would count down from a placeholder" % name
        )
