"""Headless tests for the status.py pure display helpers.

These exercise verdict_display / token_meter / ledger_rows without a running App —
the load-bearing read-surface logic must be correct independent of Textual layout.
Importing ngtui.widgets.status pulls in backend (the trust stack), so the env vars
that point at the live stack are set in conftest.py before collection.
"""
from __future__ import annotations

from ngtui.widgets.status import ledger_rows, token_meter, verdict_display


def test_verdict_display_maps_every_state():
    """Each of the five verdicts maps to its exact glyph/word/colour-role triple."""
    glyph, word, role, _caption = verdict_display("locked")
    assert (glyph, word, role) == ("●", "LOCKED", "error")

    glyph, word, role, _caption = verdict_display("outside_curfew")
    assert (glyph, word, role) == ("○", "OPEN", "success")

    glyph, word, role, _caption = verdict_display("grace_active")
    assert (glyph, word, role) == ("◐", "GRACE", "accent")

    # tamper + offline both fail closed to LOCKED/error with their fixed captions.
    glyph, word, role, caption = verdict_display("clock_tamper")
    assert (glyph, word, role) == ("●", "LOCKED", "error")
    assert caption == "clock tamper detected — locked"

    glyph, word, role, caption = verdict_display("offline_blocked")
    assert (glyph, word, role) == ("●", "LOCKED", "error")
    assert caption == "time unverified — guard keeps the house closed"

    # Unknown verdict fails closed to LOCKED (never optimistic OPEN — T-10-05).
    assert verdict_display("???")[:3] == ("●", "LOCKED", "error")


def test_token_meter_glyphs_and_caption():
    """tokens_left filled ● + spent ○, plus the 'N of 3 left · resets Mon' caption."""
    out = token_meter(2, "2026-06-30")
    assert out.startswith("● ● ○")
    assert "2 of 3 left" in out
    assert "resets Mon 2026-06-30" in out

    # Boundaries: all spent and all available.
    assert token_meter(0, "2026-06-30").startswith("○ ○ ○")
    assert token_meter(3, "2026-06-30").startswith("● ● ●")
    # tokens_left=3 must NOT render a 4th hollow glyph.
    assert "○" not in token_meter(3, "2026-06-30").split("  ")[0]


def test_ledger_rows_empty_and_populated():
    """Empty ledger -> 'no audit entries yet'; entries -> one formatted row each."""
    assert ledger_rows({}) == "no audit entries yet"
    assert ledger_rows({"ledger": []}) == "no audit entries yet"

    state = {
        "ledger": [
            {"ntp_timestamp": 1782211095, "fields": ["curfew.allow_commands"]},
        ]
    }
    rows = ledger_rows(state)
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert "curfew.allow_commands" in rows[0]
    # 1782211095 == 2026-06-23 16:38 UTC — the date prefix is present.
    assert rows[0].startswith("2026-06-23")
