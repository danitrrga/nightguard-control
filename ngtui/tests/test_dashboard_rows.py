"""Control 6c — the refusal seam: four frozen keys, refused, and no row carrying both.

Pure. No App, no Pilot, no live guard state. The row model is where the seam lives, so
this is where it is asserted — the same shape as ``test_status.py``'s
``verdict_display`` unit: unpack, compare the whole tuple in one comparison, and close
with the fail-closed case.

**What this guards.** ``mode``, ``always allowed``, ``game blocking`` and
``blocked sites`` are frozen in 12.1: the sanctioned editor cannot reach those keys
yet, and each says so on its own row in the contract's verbatim words. 12.2's whole
job on this surface is turning those four ``refusal``s into ``route``s — one field per
row, with no change to the widget, the paint ladder or the row budget. A row that
carried both a route and a refusal would have let that seam rot: it would render as
refused and route anyway.

**The refusal is presentation, not enforcement** (T-12.1-15). What refuses a weakening
is the signer — its direction classifier and its edit window. Nothing in
``controlrow.py`` decides whether a change is allowed, and a test that read this file
as an access-control assertion would be reading it wrong.

**Two layers, asserted separately.** The invariant is enforced in
``Control.__post_init__`` *and* holds over the built registry. Either one alone would
keep an end-to-end check green after the other was removed, which is the failure shape
phase 12.1 has hit in every wave so far. So: one assertion that the constructor refuses,
one that walks the registry.

Negative control, demonstrated (measured 2026-09-13). Giving ``mode`` a route alongside
its refusal in ``home_controls`` — the exact 12.2-half-done mistake — turns the
constructor guard into the failure, at import of the registry:

    E   ValueError: mode carries both a route (curfew.start) and a refusal
        ('unreachable — the only sanctioned editor cannot change this yet') — the seam
        stays a one-field swap for 12.2 only while exactly one of the two is set

and with the constructor guard ALSO removed (both layers gone, which is what a
single end-to-end assertion would have missed), the registry walk fires instead:

    E   AssertionError: mode carries both a route and a refusal: (('curfew.start',
        'unreachable — the only sanctioned editor cannot change this yet'),)
    E   assert not ('curfew.start' and 'unreachable — the only sanctioned editor
        cannot change this yet')

and the layer-1 control goes red on its own in the same run, naming which layer
went — which is the whole reason the two are separate tests:

    E   Failed: DID NOT RAISE ValueError
"""
from __future__ import annotations

import pytest

from ngtui.widgets.controlrow import (
    FROZEN_REFUSAL,
    ROUTE_VOCABULARY,
    Control,
    home_controls,
)

# The four keys the sanctioned editor cannot reach in 12.1 (UI-SPEC 8.6), and the
# registry keys they are carried by. Written out rather than derived from the
# registry: deriving "the refused ones" from the registry and then asserting they are
# refused is a tautology that passes on an empty set.
_FROZEN = ("mode", "always-allowed", "game-blocking", "blocked-sites")

_CFG = {
    "curfew": {"start": "21:30", "end": "05:30"},
    "edit_window": {"start": "05:30", "end": "14:00"},
    "blocking": {
        "native_apps": {"enabled": True, "blacklist": ["steam", "discord"]},
        "browser_extension": {"enabled": True},
    },
}


def test_frozen_keys_are_refused():
    """The four frozen keys carry a refusal and no route, in the contract's words."""
    controls = {control.key: control for control in home_controls(_CFG)}

    # Vacuity guard: a registry that lost these keys would make every loop below
    # iterate over nothing and pass. The same job as test_deploy_completeness.py's
    # "the install loop this test reads is gone" assertion.
    assert len(controls) == 16, "the registry is 16 stops, found %d" % len(controls)
    missing = [key for key in _FROZEN if key not in controls]
    assert not missing, "frozen keys vanished from the registry: %s" % missing

    for key in _FROZEN:
        # The whole seam in one comparison — no route, and the verbatim refusal.
        assert controls[key].seam == (None, FROZEN_REFUSAL), (
            "%s does not read as frozen: %r" % (key, (controls[key].seam,))
        )

    # ...and exactly those four. A fifth row quietly going refused is a capability
    # silently withdrawn, which is the same class of lie as a refusal that does not
    # refuse.
    refused = sorted(key for key, control in controls.items() if control.is_refused)
    assert refused == sorted(_FROZEN)


def test_no_control_carries_both_a_route_and_a_refusal():
    """Layer 2: the built registry. A route beside a refusal is the seam rotting."""
    controls = home_controls(_CFG)
    assert len(controls) == 16

    for control in controls:
        assert not (control.route and control.refusal), (
            "%s carries both a route and a refusal: %r"
            % (control.key, (control.seam,))
        )


def test_the_constructor_refuses_a_row_that_carries_both():
    """Layer 1: the guard itself. Removing it alone leaves the registry walk green.

    Asserted separately from the walk above for the reason phase 12.1 keeps
    rediscovering: a value defended at two layers stays green when either layer is
    taken away, so an end-to-end assertion cannot say which one rotted.
    """
    with pytest.raises(ValueError, match="carries both a route"):
        Control(
            key="mode",
            label="mode",
            route="curfew.start",
            refusal=FROZEN_REFUSAL,
        )


def test_every_route_is_a_key_the_editor_already_has():
    """Routes are read out of EDITABLE_FIELDS; this phase adds no editable field.

    A route outside that vocabulary would render as reachable and then reach nothing —
    a row that looks live, opens the editor and lands on no field. The constructor
    refuses it, so this also pins that the vocabulary is READ rather than extended.
    """
    routes = [c.route for c in home_controls(_CFG) if c.route]
    assert routes == [
        "curfew.start",
        "edit_window.start",
        "blocking.native_apps.enabled",
        "blocking.native_apps.blacklist",
        "blocking.browser_extension.enabled",
    ]
    assert set(routes) <= ROUTE_VOCABULARY

    with pytest.raises(ValueError, match="not in the editable vocabulary"):
        Control(key="x", label="x", route="curfew.forbidden_new_key")


def test_an_empty_list_reads_as_a_finding_not_as_an_absence():
    """`no site is blocked` in the alarm role, with what the emptiness costs beside it.

    `—` and "no items" are both wrong: the list being empty IS the finding (UI-SPEC
    10.4). A dash renders as "nothing to report" on a row whose whole point is that
    the browser policy has nothing to enforce.
    """
    sites = {c.key: c for c in home_controls(_CFG)}["blocked-sites"]
    assert sites.value == "no site is blocked"
    assert sites.value_role == "error"
    assert "0 entries" in sites.detail
    assert "the browser policy has nothing to enforce" in sites.detail
    assert "—" not in sites.value and "no items" not in sites.value

    # Non-empty: the alarm goes away and the entries are named.
    filled = {
        c.key: c for c in home_controls(_CFG, {"blocked_sites": ["a.example", "b.example"]})
    }["blocked-sites"]
    assert (filled.value, filled.value_role) == ("a.example, b.example", "")
