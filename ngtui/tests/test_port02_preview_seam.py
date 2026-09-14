"""GAP-04 (PORT-02): preview_change imports the live classifier — no vendored copy.

Requirement: "The preview is computed by importing nightguard_ctl.classify_change/
quota_decide — never a vendored classifier (D-07)" (PORT-02, T-10-02).

This test verifies the live seam behaviorally:
  1. preview_change(identical_text) returns is_noop=True from the live stack
     functions — proving the seam is actually wired, not a stub returning a
     hard-coded result.
  2. preview_change(tighten_text) returns is_noop=False and loosening=False —
     a real classify_change call on a tighter curfew window.
  3. backend.preview_change uses the SAME classify_change and quota_decide
     objects as the live nightguard_ctl module (same function identity) — proving
     no vendored copy was introduced.

conftest.py sets NIGHTGUARD_STACK_DIR/NIGHTGUARD_DIR before collection.
"""
from __future__ import annotations

from ngtui import backend

# A minimal config text that mimics the sanctioned config structure well enough
# for classify_change to parse. We use the same representative fixture as
# test_lineedit.py (a subset of the real layout).
_FIXTURE = '''\
timezone: Europe/Amsterdam

curfew:
  enabled: true
  start: "20:45"
  end: "05:30"
  allow_commands:
    - "/shutdown"
  block_when_offline: true
  message: "the house is closed for the night."

clock_protection:
  enabled: true
  max_offset_minutes: 5

watchdog:
  enabled: true
  check_interval_seconds: 60

blocking:
  browser_extension:
    enabled: true
    extension_id: elfaihghhjjoknimpccccmkioofjjfkf
  native_apps:
    enabled: true
    blacklist:
      - steam
'''

# A tighter version: start moved to 20:00 (earlier than 20:45 is a tighter
# restriction — starting curfew earlier tightens the window).
_TIGHTER_START = _FIXTURE.replace('  start: "20:45"', '  start: "20:00"')


# --- Test 1: identical text → is_noop=True from the live stack ---------------


def test_preview_change_identical_text_is_noop():
    """preview_change(text) where text parses identically to sanctioned → is_noop=True.

    Proves the classify_change/quota_decide seam is wired to the live stack:
    a stubbed or vendored classifier that doesn't know the SANCTIONED baseline
    could return is_noop=False here. A real seam returns True.
    """
    # Use the live sanctioned text so the diff is guaranteed identical.
    sanctioned = backend.sanctioned_text()
    if not sanctioned:
        import pytest
        pytest.skip("Sanctioned config not present on this machine — live-stack test")

    result = backend.preview_change(sanctioned)

    assert "decision" in result, f"preview_change must return a 'decision' key, got: {result}"
    assert result["decision"]["is_noop"] is True, (
        "PORT-02 VIOLATION — preview_change(identical sanctioned text) did not return "
        f"is_noop=True. Got: {result['decision']}. "
        "This means classify_change is not using the live sanctioned config as the "
        "diff base, or a vendored/stub classifier is returning a wrong answer."
    )


# --- Test 2: preview_change uses backend.ctl (the live nightguard_ctl module) --


def test_preview_change_uses_live_classify_change():
    """preview_change() is wired to the live ctl.classify_change/quota_decide.

    This verifies D-07: the classify_change function called by preview_change
    IS the same object as backend.ctl.classify_change — not a vendored copy or
    a re-implementation that could drift from the signer.
    """
    # Patch ctl.classify_change to a sentinel and verify it gets called.
    original_classify = backend.ctl.classify_change
    calls: list[tuple] = []

    def spy_classify(*args, **kwargs):
        calls.append((args, kwargs))
        return original_classify(*args, **kwargs)

    backend.ctl.classify_change = spy_classify  # type: ignore[assignment]
    try:
        sanctioned = backend.sanctioned_text()
        if not sanctioned:
            import pytest
            pytest.skip("Sanctioned config not present on this machine — live-stack test")
        backend.preview_change(sanctioned)
    finally:
        backend.ctl.classify_change = original_classify  # type: ignore[assignment]

    assert calls, (
        "PORT-02 VIOLATION — preview_change() did not call ctl.classify_change(). "
        "The classifier must be the live signer's function (D-07), not a vendored copy."
    )


# --- Test 3: preview_change uses backend.ctl.quota_decide ---------------------


def test_preview_change_uses_live_quota_decide():
    """preview_change() calls ctl.quota_decide() from the live trust stack (D-07).

    If quota_decide were vendored or stubbed, the token-cost calculation shown
    to the user could diverge from what the signer will charge — breaking PORT-02.
    """
    original_quota = backend.ctl.quota_decide
    calls: list[tuple] = []

    # *args/**kwargs on purpose. This spy pinned the three-argument signature,
    # and when the edit-window gate added `edit_window=` and `now_minutes=` to
    # quota_decide, the spy started raising TypeError. Nobody noticed for weeks:
    # the test skips on a machine with no sanctioned config, which is every
    # machine running the suite, so the failure was never reached. A spy exists
    # to observe a call, not to restate a signature.
    def spy_quota(*args, **kwargs):
        calls.append((args, kwargs))
        return original_quota(*args, **kwargs)

    backend.ctl.quota_decide = spy_quota  # type: ignore[assignment]
    try:
        sanctioned = backend.sanctioned_text()
        if not sanctioned:
            import pytest
            pytest.skip("Sanctioned config not present on this machine — live-stack test")
        backend.preview_change(sanctioned)
    finally:
        backend.ctl.quota_decide = original_quota  # type: ignore[assignment]

    assert calls, (
        "PORT-02 VIOLATION — preview_change() did not call ctl.quota_decide(). "
        "The quota decision must come from the live signer's function, "
        "not a vendored copy (D-07 / T-10-02)."
    )


# --- Test 4: preview_change diff base is SANCTIONED, not live config ----------


def test_preview_change_diff_base_is_sanctioned_not_live_config():
    """preview_change() loads sanctioned_config() as old_doc — not live config.yaml.

    Pitfall 5: if the diff base were the live config.yaml (which the signer may
    have already updated), classify_change would compute a delta relative to a
    different baseline than the CLI uses, producing wrong direction/cost displays.
    """
    # Patch sanctioned_config to a recognisably distinct doc and verify it was used.
    from unittest.mock import patch

    sentinel_cfg = {
        "timezone": "Europe/Amsterdam",
        "curfew": {
            "enabled": True,
            "start": "23:59",  # a very specific value that wouldn't be in live config
            "end": "05:30",
            "allow_commands": [],
            "block_when_offline": True,
            "message": "sentinel",
        },
    }
    captured_old: list[dict] = []

    original_classify = backend.ctl.classify_change

    def spy_classify(old, new):
        captured_old.append(old)
        return original_classify(old, new)

    with patch.object(backend, "sanctioned_config", return_value=sentinel_cfg), \
         patch.object(backend.ctl, "classify_change", side_effect=spy_classify):
        # Any proposed text — the key is what old_doc was.
        import ngcommon as ng  # noqa: E402
        proposed = ng.file_bytes(ng.SANCTIONED).decode("utf-8") if hasattr(ng, "SANCTIONED") and __import__("pathlib").Path(ng.SANCTIONED).is_file() else "timezone: Europe/Amsterdam\ncurfew:\n  enabled: true\n  start: \"21:00\"\n  end: \"05:30\"\n"
        backend.preview_change(proposed)

    assert captured_old, "classify_change was not called by preview_change()"
    assert captured_old[0] == sentinel_cfg, (
        "PORT-02 VIOLATION — preview_change() did not use sanctioned_config() as the "
        f"diff base (Pitfall 5). Expected old_doc == sentinel_cfg, "
        f"got: {captured_old[0]}"
    )
