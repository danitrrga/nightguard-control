"""WR-03: the display modules must source WEEKLY_TOKENS from the signer.

Both widgets/status.py and widgets/edit.py once defined a local ``WEEKLY_TOKENS = 3``
literal that could drift from the signer's ``nightguard_ctl.WEEKLY_TOKENS``. The
confirm gate and token meter must report the same count the signer charges, so the
constant is re-exported through backend.py and imported by the display modules.
"""
from __future__ import annotations

# Importing backend first bootstraps the trust stack onto sys.path; reference the
# signer module through backend.ctl so this test does not depend on import order.
from ngtui import backend
from ngtui.widgets import edit, status


def test_backend_reexports_signer_constant():
    assert backend.WEEKLY_TOKENS == backend.ctl.WEEKLY_TOKENS


def test_status_and_edit_use_the_backend_constant():
    # Same object identity as the signer's value, not a re-typed literal.
    assert status.WEEKLY_TOKENS is backend.WEEKLY_TOKENS
    assert edit.WEEKLY_TOKENS is backend.WEEKLY_TOKENS
    assert status.WEEKLY_TOKENS == backend.ctl.WEEKLY_TOKENS
    assert edit.WEEKLY_TOKENS == backend.ctl.WEEKLY_TOKENS
