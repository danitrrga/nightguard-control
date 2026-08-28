"""pytest fixtures/bootstrap for the ngtui headless tests.

Importing ``ngtui.widgets.status`` transitively imports ``ngtui.backend``, which on
import inserts the live LifeOS trust stack onto ``sys.path`` and imports it. The
stack paths are env-overridable; set the author-instance defaults here before
collection so the helper tests import cleanly on this box. theme.py tests need none
of this (theme.py imports only stdlib + textual), but setting the vars is harmless.
"""
from __future__ import annotations

import os

os.environ.setdefault(
    "NIGHTGUARD_STACK_DIR", "/home/danitrrga/dev/Projects/nightguard-control/scripts/linux"
)
os.environ.setdefault(
    "NIGHTGUARD_DIR", "/home/danitrrga/.local/share/nightguard"
)

import json  # noqa: E402

import pytest  # noqa: E402

# --- Phase 11 status fixtures -------------------------------------------------
# The status core (Plan 11-01) is read-only and key-less. Its tests need a
# crafted data dir (guard.json + config.sanctioned.yaml) and a deterministic
# verdict. The trust-stack path constants (``ng.STATE`` / ``ng.SANCTIONED`` /
# guard's ``TIMECACHE``) are frozen at import from the env, so re-pointing them
# is done by monkeypatching the module attributes — setting the env after import
# would not move the already-resolved paths.
#
# Verdict determinism: the guard's ``true_unix()`` honours the
# NIGHTGUARD_TEST_NTP_OVERRIDE=1 + NIGHTGUARD_NTP_OVERRIDE_UNIX seam, returning
# the supplied epoch with source "override" (no SNTP/HTTP, no clock-tamper
# branch). The curfew window in the crafted config is 20:45–05:30
# Europe/Amsterdam, so:
#   _LOCKED_UNIX  = 2026-06-24 23:00 Amsterdam -> inside curfew  -> "locked"
#   _OUTSIDE_UNIX = 2026-06-24 12:00 Amsterdam -> outside curfew -> "outside_curfew"
_LOCKED_UNIX = 1782334800
_OUTSIDE_UNIX = 1782295200

# A minimal sanctioned config mirroring the live curfew shape (20:45–05:30).
_SANCTIONED_YAML = (
    "timezone: Europe/Amsterdam\n"
    "\n"
    "curfew:\n"
    '  enabled: true\n'
    '  start: "20:45"\n'
    '  end: "05:30"\n'
    "  block_when_offline: true\n"
    "\n"
    "clock_protection:\n"
    "  enabled: true\n"
    "  max_offset_minutes: 5\n"
)

_GUARD_JSON = {
    "config_hmac": "deadbeef",
    "state_hmac": "deadbeef",
    "weekly_spent": 1,
    "week_anchor": "2026-06-22",
    "ledger": [
        {"ntp_timestamp": 1782211095, "fields": ["curfew.allow_commands"]}
    ],
    "grace": None,
}


def _point_stack_at(monkeypatch, data_dir, *, override_unix):
    """Re-point the imported trust stack at ``data_dir`` and pin true-time.

    Imported here (not at module top) so collecting tests that never use these
    fixtures does not force the backend import early.
    """
    from ngtui import backend  # noqa: E402  (defers trust-stack import)

    ng = backend.ng
    guard = backend.guard

    state_path = data_dir / "guard.json"
    sanctioned_path = data_dir / "config.sanctioned.yaml"
    config_path = data_dir / "config.yaml"
    timecache_path = data_dir / ".timecache"

    monkeypatch.setattr(ng, "NIGHTGUARD_DIR", str(data_dir), raising=False)
    monkeypatch.setattr(ng, "STATE", str(state_path), raising=False)
    monkeypatch.setattr(ng, "SANCTIONED", str(sanctioned_path), raising=False)
    monkeypatch.setattr(ng, "CONFIG", str(config_path), raising=False)
    monkeypatch.setattr(guard, "TIMECACHE", str(timecache_path), raising=False)
    monkeypatch.setenv("NIGHTGUARD_DIR", str(data_dir))

    # Deterministic, network-free true-time via the documented override seam.
    monkeypatch.setenv("NIGHTGUARD_TEST_NTP_OVERRIDE", "1")
    monkeypatch.setenv("NIGHTGUARD_NTP_OVERRIDE_UNIX", str(override_unix))


def _write_data_dir(data_dir, *, write_files):
    if write_files:
        (data_dir / "config.sanctioned.yaml").write_text(
            _SANCTIONED_YAML, encoding="utf-8"
        )
        (data_dir / "config.yaml").write_text(_SANCTIONED_YAML, encoding="utf-8")
        (data_dir / "guard.json").write_text(
            json.dumps(_GUARD_JSON), encoding="utf-8"
        )


@pytest.fixture
def ng_data_dir(tmp_path, monkeypatch):
    """A populated, locked-verdict data dir (guard.json + sanctioned config).

    Writes a crafted ``guard.json`` (weekly_spent/week_anchor/ledger/grace) and a
    ``config.sanctioned.yaml`` into ``tmp_path``, re-points the trust stack at it,
    and pins true-time inside the curfew window so ``live_verdict`` is "locked".
    Returns the ``pathlib.Path`` to the data dir.
    """
    _write_data_dir(tmp_path, write_files=True)
    _point_stack_at(monkeypatch, tmp_path, override_unix=_LOCKED_UNIX)
    return tmp_path


@pytest.fixture
def ng_data_dir_outside(tmp_path, monkeypatch):
    """A populated data dir pinned OUTSIDE the curfew window -> "outside_curfew"."""
    _write_data_dir(tmp_path, write_files=True)
    _point_stack_at(monkeypatch, tmp_path, override_unix=_OUTSIDE_UNIX)
    return tmp_path


@pytest.fixture
def ng_data_dir_empty(tmp_path, monkeypatch):
    """An EMPTY data dir — no guard.json, no sanctioned config.

    Backend reads degrade to ``{}`` (load_state -> {}, sanctioned_config -> {}).
    True-time is pinned inside the curfew window so an empty/uninitialized dir
    renders "locked", never "unavailable" (Pitfall 3). Returns the dir Path.
    """
    _write_data_dir(tmp_path, write_files=False)
    _point_stack_at(monkeypatch, tmp_path, override_unix=_LOCKED_UNIX)
    return tmp_path


@pytest.fixture
def read_key_explodes(monkeypatch):
    """Make any ``read_key`` call raise — proves the status path is key-less.

    Patches ``read_key`` on every module that re-exports ngcommon
    (ng / guard.ng / ctl.ng) so a stray read from any of them is caught.
    """
    from ngtui import backend  # noqa: E402

    def _boom(*_a, **_k):
        raise AssertionError("read_key() called on the key-less status path (DESK-02)")

    monkeypatch.setattr(backend.ng, "read_key", _boom, raising=False)
    monkeypatch.setattr(backend.guard.ng, "read_key", _boom, raising=False)
    monkeypatch.setattr(backend.ctl.ng, "read_key", _boom, raising=False)
    return _boom
