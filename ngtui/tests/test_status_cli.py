"""Headless tests for the key-less `ngtui status` core (Plan 11-01, DESK-02).

These exercise the pure Waybar status builder (``ngtui.status``) and the
``backend.cache_only_verdict`` seam without a TTY, subprocess, or argv. The
load-bearing contract — key-less, fail-closed-to-locked, single-line jq-valid
JSON, and NO synchronous SNTP/HTTP query on the read path — must hold in pure
functions so Plan 02's ``__main__`` router is thin glue.

Importing ``ngtui.status`` / ``ngtui.backend`` pulls in the trust stack; the env
vars that point at the live stack are set in conftest.py before collection.
"""
from __future__ import annotations

import json
import time

from ngtui import backend
from ngtui import status


# --- the pure builder ---------------------------------------------------------


def test_status_json_shape():
    """``_shape`` returns exactly {text,tooltip,class} and json.dumps-es single-line."""
    obj = status._shape("locked", 2, {"week_anchor": "2026-06-22"})
    assert set(obj.keys()) == {"text", "tooltip", "class"}

    line = json.dumps(obj, separators=(",", ":"))
    assert "\n" not in line  # single-line: Waybar reads one object per line
    # round-trips through a strict JSON parse (jq-valid by construction).
    assert json.loads(line) == obj


def test_verdict_class_map():
    """All 5 verdicts map to their own class; UNKNOWN fails closed to 'locked'."""
    assert status._VERDICT_CLASS["locked"] == "locked"
    assert status._VERDICT_CLASS["grace_active"] == "grace_active"
    assert status._VERDICT_CLASS["outside_curfew"] == "outside_curfew"
    assert status._VERDICT_CLASS["clock_tamper"] == "clock_tamper"
    assert status._VERDICT_CLASS["offline_blocked"] == "offline_blocked"

    # Unknown verdict -> "locked" (never "unavailable", never "outside_curfew").
    assert status._VERDICT_CLASS.get("???", "locked") == "locked"
    assert status._shape("???", 3, {})["class"] == "locked"
    assert status._shape("???", 3, {})["class"] != "unavailable"
    assert status._shape("???", 3, {})["class"] != "outside_curfew"


def test_unavailable_object():
    """The module's UNAVAILABLE object is the fixed fail-closed except-branch object."""
    assert status.UNAVAILABLE == {"text": "○ —", "class": "unavailable"}
    line = json.dumps(status.UNAVAILABLE, separators=(",", ":"))
    assert "\n" not in line
    assert json.loads(line) == status.UNAVAILABLE


# --- empty data is LOCKED, not unavailable (Pitfall 3) ------------------------


def test_empty_data_is_locked_not_unavailable(ng_data_dir_empty):
    """An empty/uninitialized data dir renders 'locked', never 'unavailable'."""
    verdict = backend.live_verdict({}, {})
    assert verdict == "locked"
    assert backend.tokens_left() == 3

    obj = status._shape(verdict, backend.tokens_left(), {})
    assert obj["class"] == "locked"
    assert obj["class"] != "unavailable"


# --- the cache-only seam never blocks on the network (Pitfall 1 / T-11-04) ----


def test_status_no_blocking_ntp(ng_data_dir_empty, monkeypatch):
    """cache_only_verdict resolves WITHOUT a synchronous SNTP/HTTP query.

    The override seam is removed for this test so a forced-cold cache would
    normally fall through to ``_sntp``/``_http_time``. Those are swapped for
    record-and-raise stubs; the call must complete instantly (well under the
    real ~4s two-timeout block) and end in a fail-closed offline verdict.
    """
    # Drop the deterministic override so true_unix() must hit the fall-through.
    monkeypatch.delenv("NIGHTGUARD_TEST_NTP_OVERRIDE", raising=False)
    monkeypatch.delenv("NIGHTGUARD_NTP_OVERRIDE_UNIX", raising=False)

    calls = {"sntp": 0, "http": 0}

    def rec_sntp(*_a, **_k):
        calls["sntp"] += 1
        raise OSError("no network in test")

    def rec_http(*_a, **_k):
        calls["http"] += 1
        raise OSError("no network in test")

    monkeypatch.setattr(backend.guard, "_sntp", rec_sntp, raising=False)
    monkeypatch.setattr(backend.guard, "_http_time", rec_http, raising=False)

    cfg = backend.sanctioned_config()
    state = backend.read_state()

    t0 = time.monotonic()
    verdict = backend.cache_only_verdict(cfg, state)
    elapsed = time.monotonic() - t0

    assert verdict in {
        "locked",
        "grace_active",
        "outside_curfew",
        "clock_tamper",
        "offline_blocked",
    }
    # Cold cache + no verifiable time -> fail-closed offline (the wanted behaviour).
    assert verdict == "offline_blocked"
    # No blocking: instant-raise stubs, not the real 2s+2s timeouts.
    assert elapsed < 0.2, f"cache_only_verdict blocked for {elapsed:.2f}s"


# --- DESK-02: the status path never reads the key -----------------------------


def test_status_never_reads_key(ng_data_dir, read_key_explodes):
    """read_state / sanctioned_config / cache_only_verdict / tokens_left read no key."""
    # None of these should trigger a read_key() — the explode fixture asserts it.
    state = backend.read_state()
    cfg = backend.sanctioned_config()
    backend.cache_only_verdict(cfg, state)
    backend.tokens_left()
    # If we got here, zero read_key calls fired (the fixture would have raised).
    assert isinstance(state, dict)
