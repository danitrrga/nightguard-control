"""The watchdog's two enforcement surfaces, and when each is allowed to fire.

The browser policy and the process killer block different things for a structural
reason. On this machine Discord, the calendar, the todo list and EL PORTAL are all
``--app=`` windows of a single chromium process, so ending that process to block
Discord would end the allowlist with it. Sites are therefore blocked by URL in the
root-owned managed policy, and only native applications are ever signalled.

Both are held to the same gate: the curfew verdict must be exactly ``locked``.
"""
from __future__ import annotations

import json

import pytest

from ngtui import backend  # noqa: F401  (puts the trust stack on sys.path)

import appblock
import nightguard_watchdog as wd


_EXT = "elfaihghhjjoknimpccccmkioofjjfkf"


def _cfg(blocked_urls=None, ext=_EXT, enabled=True, native=None):
    cfg = {
        "blocking": {
            "browser_extension": {
                "enabled": enabled,
                "extension_id": ext,
                "blocked_urls": blocked_urls if blocked_urls is not None else [],
            }
        }
    }
    if native is not None:
        cfg["blocking"]["native_apps"] = native
    return cfg


# --- the managed browser policy ----------------------------------------------

def test_the_policy_always_force_installs_the_extension():
    body = json.loads(wd._policy_body(_EXT))
    assert body["ExtensionInstallForcelist"] == [
        "%s;https://clients2.google.com/service/update2/crx" % _EXT
    ]


def test_blocked_sites_appear_only_while_the_curfew_is_locked():
    cfg = _cfg(blocked_urls=["discord.com", "youtube.com"])
    locked = json.loads(wd.desired_policy(cfg, "locked"))
    assert locked["URLBlocklist"] == ["discord.com", "youtube.com"]


@pytest.mark.parametrize("verdict", ["outside_curfew", "clock_tamper", "offline_blocked", "grace_active"])
def test_blocked_sites_are_lifted_outside_the_curfew(verdict):
    """A clock the guard cannot trust is a reason to refuse config changes, not a
    reason to cut the user off from the web in the middle of the afternoon."""
    cfg = _cfg(blocked_urls=["discord.com"])
    body = json.loads(wd.desired_policy(cfg, verdict))
    assert "URLBlocklist" not in body
    assert body["ExtensionInstallForcelist"], "the extension is still force-installed"


def test_no_policy_is_written_without_an_extension_id():
    assert wd.desired_policy(_cfg(ext=None), "locked") is None


def test_no_policy_is_written_when_browser_blocking_is_disabled():
    assert wd.desired_policy(_cfg(enabled=False), "locked") is None


def test_an_empty_blocklist_omits_the_key_entirely():
    """An empty URLBlocklist key is not the same as no key; keep the document
    identical to what a box with the feature unused would have."""
    body = json.loads(wd.desired_policy(_cfg(blocked_urls=[]), "locked"))
    assert "URLBlocklist" not in body


def test_a_stale_blocklist_is_detected_as_missing(tmp_path, monkeypatch):
    """The old check only looked for the extension id, so a policy left over from
    the night would have survived all day: the id was still present, so the file
    read as correct while it was still blocking Discord at noon."""
    path = tmp_path / "nightguard.json"
    path.write_text(wd.desired_policy(_cfg(blocked_urls=["discord.com"]), "locked"),
                    encoding="utf-8")
    monkeypatch.setattr(wd, "POLICY_PATHS", [str(path)])

    cfg = _cfg(blocked_urls=["discord.com"])
    assert wd._missing_policies(cfg, "locked") == []
    assert wd._missing_policies(cfg, "outside_curfew") == [str(path)]


def test_a_deleted_policy_is_detected_as_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(wd, "POLICY_PATHS", [str(tmp_path / "gone.json")])
    assert wd._missing_policies(_cfg(), "locked") == [str(tmp_path / "gone.json")]


def test_restoring_writes_the_verdict_appropriate_body(tmp_path, monkeypatch):
    path = tmp_path / "nightguard.json"
    monkeypatch.setattr(wd, "POLICY_PATHS", [str(path)])
    cfg = _cfg(blocked_urls=["discord.com"])

    restored, failed = wd._restore_policies(cfg, [str(path)], "locked")
    assert failed == [] and restored == [str(path)]
    assert "discord.com" in path.read_text(encoding="utf-8")

    restored, failed = wd._restore_policies(cfg, [str(path)], "outside_curfew")
    assert failed == []
    assert "discord.com" not in path.read_text(encoding="utf-8")
    assert _EXT in path.read_text(encoding="utf-8")


# --- the process killer ------------------------------------------------------

@pytest.fixture
def kills(monkeypatch):
    """Capture signals instead of sending them."""
    sent = []
    monkeypatch.setattr(wd.os, "kill", lambda pid, sig: sent.append((pid, sig)))
    return sent


def _native(enabled=True, mode="blocklist", blacklist=("steam",), block_games=False):
    return {
        "enabled": enabled,
        "mode": mode,
        "blacklist": list(blacklist),
        "allowlist": [],
        "block_games": block_games,
    }


def _stub_world(monkeypatch, verdict, processes):
    monkeypatch.setattr(wd.guard, "curfew_verdict", lambda cfg, state: verdict)
    monkeypatch.setattr(wd.appblock, "read_processes", lambda *a, **k: processes)


_STEAM = appblock.Process(
    100, "/usr/lib/steam/steam",
    "0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-Hyprland-steam.scope",
)


def test_a_blocked_app_is_signalled_during_the_curfew(monkeypatch, kills):
    _stub_world(monkeypatch, "locked", [_STEAM])
    parts = wd._enforce_apps(_cfg(native=_native()), {})
    assert kills == [(100, wd.signal.SIGTERM)]
    assert any("ENDED during curfew" in p for p in parts)


@pytest.mark.parametrize("verdict", ["clock_tamper", "offline_blocked", "outside_curfew", "grace_active"])
def test_no_process_is_signalled_outside_the_curfew(monkeypatch, kills, verdict):
    """The regression that retired the previous blocker, at the actuator this
    time rather than in the pure decision: a 3pm clock jump must send no signal."""
    _stub_world(monkeypatch, verdict, [_STEAM])
    assert wd._enforce_apps(_cfg(native=_native()), {}) == []
    assert kills == []


def test_nothing_is_signalled_when_native_blocking_is_disabled(monkeypatch, kills):
    _stub_world(monkeypatch, "locked", [_STEAM])
    assert wd._enforce_apps(_cfg(native=_native(enabled=False)), {}) == []
    assert kills == []


def test_nothing_is_signalled_when_the_verdict_cannot_be_resolved(monkeypatch, kills):
    """An unresolvable verdict is not a locked verdict."""
    def _boom(cfg, state):
        raise RuntimeError("no clock")

    monkeypatch.setattr(wd.guard, "curfew_verdict", _boom)
    monkeypatch.setattr(wd.appblock, "read_processes", lambda *a, **k: [_STEAM])
    parts = wd._enforce_apps(_cfg(native=_native()), {})
    assert kills == []
    assert any("verdict unavailable" in p for p in parts)


def test_an_implausibly_large_kill_set_is_refused(monkeypatch, kills):
    """The safety valve. decide_kills is tested, but an inverted comparison there
    would return every process on the machine, and allowlist mode makes that the
    default shape of a bug. Refusing turns a dead desktop into a log line."""
    horde = [
        appblock.Process(1000 + i, "/opt/app%d/app" % i,
                         "0::/user.slice/u/app.slice/app-%d.scope" % i)
        for i in range(wd.MAX_KILLS_PER_TICK + 1)
    ]
    _stub_world(monkeypatch, "locked", horde)
    parts = wd._enforce_apps(_cfg(native=_native(mode="allowlist")), {})
    assert kills == []
    assert any("REFUSED to enforce" in p for p in parts)


def test_a_kill_set_at_the_cap_is_still_carried_out(monkeypatch, kills):
    """The valve must not be so tight that ordinary enforcement trips it."""
    horde = [
        appblock.Process(1000 + i, "/opt/app%d/app" % i,
                         "0::/user.slice/u/app.slice/app-%d.scope" % i)
        for i in range(wd.MAX_KILLS_PER_TICK)
    ]
    _stub_world(monkeypatch, "locked", horde)
    wd._enforce_apps(_cfg(native=_native(mode="allowlist")), {})
    assert len(kills) == wd.MAX_KILLS_PER_TICK


def test_a_process_that_exits_first_is_not_an_error(monkeypatch):
    """/proc entries go stale between the scan and the signal."""
    def _gone(pid, sig):
        raise ProcessLookupError(pid)

    monkeypatch.setattr(wd.os, "kill", _gone)
    _stub_world(monkeypatch, "locked", [_STEAM])
    assert wd._enforce_apps(_cfg(native=_native()), {}) == []


def test_a_permission_error_is_reported_not_swallowed(monkeypatch):
    """Running the tick as the user rather than root must say so, loudly, instead
    of logging a clean tick while enforcing nothing."""
    def _denied(pid, sig):
        raise PermissionError("not root")

    monkeypatch.setattr(wd.os, "kill", _denied)
    _stub_world(monkeypatch, "locked", [_STEAM])
    parts = wd._enforce_apps(_cfg(native=_native()), {})
    assert any("could not end" in p for p in parts)


def test_the_compositor_survives_allowlist_mode_through_the_actuator(monkeypatch, kills):
    """The floor is enforced in the decision, but this asserts it end to end from
    the watchdog's own entry point, which is what actually runs as root."""
    desktop = [
        appblock.Process(1, "/usr/bin/Hyprland", "0::/user.slice/u/session.slice/wm.service"),
        appblock.Process(2, "/usr/bin/quickshell", "0::/user.slice/u/app.slice/bar.scope"),
        appblock.Process(3, "/usr/bin/foot", "0::/user.slice/u/app.slice/term.scope"),
    ]
    _stub_world(monkeypatch, "locked", desktop)
    wd._enforce_apps(_cfg(native=_native(mode="allowlist")), {})
    assert kills == []


def test_the_game_catalogue_is_only_built_when_games_are_blocked(monkeypatch, kills):
    """Scanning Steam and Heroic on every 60s tick for nothing is waste."""
    calls = []
    monkeypatch.setattr(wd.appblock, "build_catalog", lambda home: calls.append(home) or [])
    _stub_world(monkeypatch, "locked", [_STEAM])

    wd._enforce_apps(_cfg(native=_native(block_games=False)), {})
    assert calls == []

    wd._enforce_apps(_cfg(native=_native(block_games=True)), {})
    assert len(calls) == 1
