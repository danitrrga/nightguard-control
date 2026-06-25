"""status.py — the pure, headless-testable Waybar status builder (DESK-02).

This is the key-less core of ``ngtui status``: pure functions that map a guard
verdict + remaining-token count + signed state into a Waybar-shaped
``{text, tooltip, class}`` object. Plan 02's ``__main__`` router is thin glue
that resolves the verdict (cache-only, never blocking — see
``backend.cache_only_verdict``) and ``json.dumps``-es one of these objects.

Contract (load-bearing):
  - The verdict→class map covers all five guard verdict strings and FAILS CLOSED
    to ``"locked"`` on any unknown verdict — never ``"unavailable"``, never an
    optimistic ``"outside_curfew"`` (T-11-02 / Pitfall 3).
  - ``UNAVAILABLE`` is the single object Plan 02 emits ONLY from its except
    branch (the trust stack failed to import / read). Empty data is "locked",
    not "unavailable".
  - The object is a flat dict of strings so ``json.dumps(obj,
    separators=(",", ":"))`` yields a single jq-valid line (T-11-03).

Stdlib-only at module top: no ``textual`` import, no ``backend`` import — the
subcommand passes the resolved verdict/token values in. ``WEEKLY_TOKENS`` is
sourced from the signer (via a deferred local import) so the token clamp never
hardcodes the literal ``3`` (WR-03). This module computes no HMAC and reads no
key (PORT-03 / inherits the test_port03_no_crypto AST guard).
"""
from __future__ import annotations

# Verdict string -> CSS-safe Waybar class. The class equals the verdict name so
# a Waybar stylesheet can target ``#custom-nightguard.locked`` etc. directly. The
# lookup is always done with ``dict.get(verdict, "locked")`` so an UNKNOWN verdict
# fails closed to "locked" (never "unavailable", never "outside_curfew").
_VERDICT_CLASS: dict[str, str] = {
    "locked": "locked",
    "grace_active": "grace_active",
    "outside_curfew": "outside_curfew",
    "clock_tamper": "clock_tamper",
    "offline_blocked": "offline_blocked",
}

# Glyph + short word per verdict for the bar ``text`` and the ``tooltip`` headline.
# Glyph + word always travel together (accessibility: meaning survives a
# monochrome bar). Mirrors widgets/status.py::_VERDICT_MAP intent without the
# Textual colour-role coupling.
_VERDICT_LABEL: dict[str, tuple[str, str]] = {
    "locked": ("●", "LOCKED"),
    "grace_active": ("◐", "GRACE"),
    "outside_curfew": ("○", "OPEN"),
    "clock_tamper": ("●", "TAMPER"),
    "offline_blocked": ("●", "OFFLINE"),
}

# The fail-closed except-branch object Plan 02 emits when the trust stack cannot
# be imported / read at all. Distinct from any verdict: "unavailable" means "I
# could not even ask the guard", whereas every verdict (incl. empty-data
# "locked") means "I asked and the house is in <state>".
UNAVAILABLE: dict[str, str] = {"text": "○ —", "class": "unavailable"}


def _verdict_class(verdict: str) -> str:
    """Map a guard verdict to its Waybar class, failing closed to "locked"."""
    return _VERDICT_CLASS.get(verdict, "locked")


def _shape(verdict: str, tokens_left: int, state: dict) -> dict:
    """Build the Waybar ``{text, tooltip, class}`` object from a verdict + tokens.

    ``class`` comes from the fail-closed verdict map. ``text`` is a compact bar
    label: glyph + remaining-token count (clamped to ``[0, WEEKLY_TOKENS]`` —
    sourced from the signer's constant, never a local ``3``). ``tooltip`` is a
    human-readable verdict word + "N token(s) left" line. The exact glyph/word
    copy is display detail; the class-mapping + fail-closed-to-locked behaviour
    is the fixed contract.

    Pure: ``state`` is accepted for forward-compatibility (e.g. a future grace
    countdown in the tooltip) but this builder reads no key and issues no query.
    """
    # Deferred import keeps the module top textual/backend-free while still
    # sourcing the token ceiling from the signer (WR-03).
    from ngtui.backend import WEEKLY_TOKENS

    cls = _verdict_class(verdict)
    glyph, word = _VERDICT_LABEL.get(verdict, _VERDICT_LABEL["locked"])

    left = max(0, min(WEEKLY_TOKENS, int(tokens_left)))
    noun = "token" if left == 1 else "tokens"

    text = f"{glyph} {left}"
    tooltip = f"{word} · {left} {noun} left"
    return {"text": text, "tooltip": tooltip, "class": cls}
