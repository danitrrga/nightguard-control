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
_FF_EXT = "{30b15d56-b2fa-4cb2-98fd-7b5e26306483}"


@pytest.fixture
def only_chromium(monkeypatch):
    """Isolate the Chromium family from the Gecko one.

    ``desired_bodies`` covers both, so a test that monkeypatches POLICY_PATHS alone
    still picks up /etc/zen and /etc/firefox from the real machine. Clearing the Gecko
    map keeps the Chromium assertions about Chromium.
    """
    monkeypatch.setattr(wd, "MOZILLA_POLICY_TARGETS", {})


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


def test_a_stale_blocklist_is_detected_as_missing(tmp_path, monkeypatch, only_chromium):
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


def test_a_deleted_policy_is_detected_as_missing(tmp_path, monkeypatch, only_chromium):
    monkeypatch.setattr(wd, "POLICY_PATHS", [str(tmp_path / "gone.json")])
    assert wd._missing_policies(_cfg(), "locked") == [str(tmp_path / "gone.json")]


def test_restoring_writes_the_verdict_appropriate_body(tmp_path, monkeypatch, only_chromium):
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


# --- incognito, guest mode and safe mode -------------------------------------
# Every one of these starts a browser session the force-installed extension is not
# in. They are the difference between "cannot be switched off" and "cannot be
# switched off without opening a second window".

def test_incognito_and_guest_mode_are_closed_on_chromium():
    """Chromium has no policy to grant an extension incognito access -- ExtensionSettings
    carries no incognito key -- so removing incognito is the only enforcement there is.
    Guest mode is the quieter hole: a guest session carries no extensions at all."""
    body = json.loads(wd._policy_body(_EXT))
    assert body["IncognitoModeAvailability"] == 1
    assert body["BrowserGuestModeEnabled"] is False


def test_incognito_closure_can_be_turned_off_from_config():
    body = json.loads(wd._policy_body(_EXT, block_incognito=False))
    assert "IncognitoModeAvailability" not in body
    assert "BrowserGuestModeEnabled" not in body


# --- the Gecko (Zen, Firefox) policy -----------------------------------------

def test_the_gecko_policy_force_installs_from_amo(tmp_path):
    base = tmp_path / "policies.json"
    body = json.loads(wd._mozilla_policy_body(str(base), _FF_EXT, wd.FIREFOX_INSTALL_URL))
    entry = body["policies"]["ExtensionSettings"][_FF_EXT]
    assert entry["installation_mode"] == "force_installed"
    assert entry["install_url"] == wd.FIREFOX_INSTALL_URL


def test_the_gecko_policy_grants_private_browsing_instead_of_removing_it():
    """Chromium can only close incognito by deleting the feature; Gecko can hand the
    add-on the private window instead, so private browsing stays usable AND covered."""
    body = json.loads(wd._mozilla_policy_body("/nonexistent", _FF_EXT, "https://x/y.xpi"))
    assert body["policies"]["ExtensionSettings"][_FF_EXT]["private_browsing"] is True


def test_safe_mode_is_disabled():
    """Safe mode starts Gecko with every extension off, two clicks from the help menu."""
    body = json.loads(wd._mozilla_policy_body("/nonexistent", _FF_EXT, "https://x/y.xpi"))
    assert body["policies"]["DisableSafeMode"] is True


def test_the_vendors_own_policies_survive_the_overwrite(tmp_path):
    """/etc/<app>/policies/policies.json SHADOWS the install-directory file -- Gecko
    returns the system file and never reads the other one. Writing the lock without
    merging would silently drop Zen's DisableAppUpdate."""
    base = tmp_path / "policies.json"
    base.write_text(json.dumps({"policies": {"DisableAppUpdate": True,
                                             "DefaultSerialGuardSetting": 3}}),
                    encoding="utf-8")
    body = json.loads(wd._mozilla_policy_body(str(base), _FF_EXT, "https://x/y.xpi"))
    assert body["policies"]["DisableAppUpdate"] is True
    assert body["policies"]["DefaultSerialGuardSetting"] == 3
    assert _FF_EXT in body["policies"]["ExtensionSettings"]


def test_a_missing_base_document_still_produces_the_lock(tmp_path):
    """No vendor file is nothing to carry forward, not a reason to skip enforcement."""
    body = json.loads(wd._mozilla_policy_body(str(tmp_path / "absent.json"),
                                              _FF_EXT, "https://x/y.xpi"))
    assert _FF_EXT in body["policies"]["ExtensionSettings"]


def test_blocked_hosts_become_gecko_match_patterns():
    """Chromium takes a bare host; Gecko's WebsiteFilter wants a match pattern and
    silently drops anything else. One config list, two syntaxes."""
    body = json.loads(wd._mozilla_policy_body("/nonexistent", _FF_EXT, "https://x/y.xpi",
                                              ["discord.com", "*://old.reddit.com/*"]))
    assert body["policies"]["WebsiteFilter"]["Block"] == [
        "*://*.discord.com/*", "*://old.reddit.com/*"]


def test_gecko_blocked_sites_are_lifted_outside_the_curfew(tmp_path):
    cfg = _cfg(blocked_urls=["discord.com"])
    base = str(tmp_path / "absent.json")
    locked = json.loads(wd.desired_mozilla_policy(cfg, "locked", base))
    assert locked["policies"]["WebsiteFilter"]["Block"] == ["*://*.discord.com/*"]
    open_hours = json.loads(wd.desired_mozilla_policy(cfg, "outside_curfew", base))
    assert "WebsiteFilter" not in open_hours["policies"]
    assert _FF_EXT in open_hours["policies"]["ExtensionSettings"], \
        "the add-on is still force-installed"


def test_no_gecko_policy_is_written_when_browser_blocking_is_disabled():
    assert wd.desired_mozilla_policy(_cfg(enabled=False), "locked", "/nonexistent") is None


def test_a_browser_that_is_not_installed_gets_no_policy_file(tmp_path, monkeypatch):
    """An unread file that reports "restored" on every tick is noise, not enforcement."""
    monkeypatch.setattr(wd, "POLICY_PATHS", [])
    monkeypatch.setattr(wd, "MOZILLA_POLICY_TARGETS", {
        str(tmp_path / "etc/ghost/policies/policies.json"):
            str(tmp_path / "opt/ghost/distribution/policies.json"),
    })
    assert wd.desired_bodies(_cfg(), "locked") == {}


def test_an_installed_browser_gets_its_policy_file(tmp_path, monkeypatch):
    install = tmp_path / "opt/zen/distribution"
    install.mkdir(parents=True)
    target = str(tmp_path / "etc/zen/policies/policies.json")
    monkeypatch.setattr(wd, "POLICY_PATHS", [])
    monkeypatch.setattr(wd, "MOZILLA_POLICY_TARGETS",
                        {target: str(install / "policies.json")})

    want = wd.desired_bodies(_cfg(), "locked")
    assert list(want) == [target]
    assert wd._missing_policies(_cfg(), "locked") == [target], "absent file is missing"

    restored, failed = wd._restore_policies(_cfg(), [target], "locked")
    assert restored == [target] and failed == []
    assert wd._missing_policies(_cfg(), "locked") == [], "and correct once written"
    assert _FF_EXT in open(target, encoding="utf-8").read()


def test_a_hand_edited_gecko_policy_is_detected_and_rewritten(tmp_path, monkeypatch):
    """The whole point: deleting the ExtensionSettings block must not survive a tick."""
    install = tmp_path / "opt/zen/distribution"
    install.mkdir(parents=True)
    target = tmp_path / "etc/zen/policies/policies.json"
    target.parent.mkdir(parents=True)
    monkeypatch.setattr(wd, "POLICY_PATHS", [])
    monkeypatch.setattr(wd, "MOZILLA_POLICY_TARGETS",
                        {str(target): str(install / "policies.json")})

    target.write_text(json.dumps({"policies": {}}), encoding="utf-8")
    assert wd._missing_policies(_cfg(), "locked") == [str(target)]
    wd._restore_policies(_cfg(), [str(target)], "locked")
    assert _FF_EXT in target.read_text(encoding="utf-8")


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
    monkeypatch.setattr(appblock, "ensure_jail", lambda path=None: False)
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
    monkeypatch.setattr(appblock, "ensure_jail", lambda path=None: False)
    horde = [
        appblock.Process(1000 + i, "/opt/app%d/app" % i,
                         "0::/user.slice/u/app.slice/app-%d.scope" % i)
        for i in range(wd.MAX_KILLS_PER_TICK)
    ]
    _stub_world(monkeypatch, "locked", horde)
    wd._enforce_apps(_cfg(native=_native(mode="allowlist")), {})
    assert len(kills) == wd.MAX_KILLS_PER_TICK


def test_a_process_that_exits_first_is_not_an_error(monkeypatch):
    """/proc entries go stale between the scan and the signal.

    Pinned on the SIGTERM fallback: on a box with no jail this is the path that
    runs, and a stale PID there must not read as a failure.
    """
    def _gone(pid, sig):
        raise ProcessLookupError(pid)

    monkeypatch.setattr(appblock, "ensure_jail", lambda path=None: False)
    monkeypatch.setattr(wd.os, "kill", _gone)
    _stub_world(monkeypatch, "locked", [_STEAM])
    parts = wd._enforce_apps(_cfg(native=_native()), {})
    assert not any("could not end" in p for p in parts)


def test_a_permission_error_is_reported_not_swallowed(monkeypatch):
    """Running the tick as the user rather than root must say so, loudly, instead
    of logging a clean tick while enforcing nothing."""
    def _denied(pid, sig):
        raise PermissionError("not root")

    monkeypatch.setattr(appblock, "ensure_jail", lambda path=None: False)
    monkeypatch.setattr(wd.os, "kill", _denied)
    _stub_world(monkeypatch, "locked", [_STEAM])
    parts = wd._enforce_apps(_cfg(native=_native()), {})
    assert any("could not end" in p for p in parts)


def test_the_compositor_survives_allowlist_mode_through_the_actuator(monkeypatch, kills):
    monkeypatch.setattr(appblock, "ensure_jail", lambda path=None: False)
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


# --- the jail ----------------------------------------------------------------
# Proven on this machine 2026-09-07: root creates a cgroup outside the subtree
# systemd delegates to uid 1000, the owner cannot migrate a process back out
# ("write error: Permission denied"), cannot unfreeze it and cannot rmdir it, and
# cgroup.kill ends the tree. These tests hold the wiring to that shape.

@pytest.fixture
def jail(tmp_path, monkeypatch):
    """A fake cgroup directory, so the wiring is testable without root."""
    path = tmp_path / "nightguard"
    path.mkdir()
    (path / "cgroup.procs").write_text("", encoding="utf-8")
    (path / "cgroup.kill").write_text("", encoding="utf-8")
    monkeypatch.setattr(appblock, "JAIL", str(path))
    return path


def test_a_blocked_app_is_jailed_and_the_tree_killed(monkeypatch, jail, kills):
    _stub_world(monkeypatch, "locked", [_STEAM])
    parts = wd._enforce_apps(_cfg(native=_native()), {})

    assert (jail / "cgroup.procs").read_text().strip() == "100"
    assert (jail / "cgroup.kill").read_text().strip() == "1"
    assert kills == [], "the jail replaces the signal loop, it does not add to it"
    assert any("jailed" in p for p in parts)


def test_the_jail_is_never_used_outside_the_curfew(monkeypatch, jail, kills):
    """Same gate as everything else: a clock jump at 3pm jails nothing."""
    _stub_world(monkeypatch, "clock_tamper", [_STEAM])
    assert wd._enforce_apps(_cfg(native=_native()), {}) == []
    assert (jail / "cgroup.procs").read_text() == ""
    assert (jail / "cgroup.kill").read_text() == ""


def test_the_kill_is_not_written_when_nothing_was_jailed(monkeypatch, jail):
    """Writing 1 to cgroup.kill on a jail holding leftovers from a previous tick
    would end processes this tick never decided to end."""
    def _gone(pid, path=None):
        raise ProcessLookupError(pid)

    monkeypatch.setattr(appblock, "jail_and_kill",
                        lambda pids, path=None: ([], [(p, "gone") for p in pids]))
    _stub_world(monkeypatch, "locked", [_STEAM])
    wd._enforce_apps(_cfg(native=_native()), {})
    assert (jail / "cgroup.kill").read_text() == ""


def test_a_stale_pid_is_not_reported_as_a_jail_failure(jail, monkeypatch):
    """A process that exits between the scan and the write is the outcome the
    tick wanted, not an error to log."""
    real_open = open

    def fake_open(path, *a, **k):
        if str(path).endswith("cgroup.procs"):
            raise ProcessLookupError(999)
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", fake_open)
    jailed, failed = appblock.jail_and_kill([999], str(jail))
    assert jailed == [] and failed == []


def test_the_fallback_says_so_instead_of_pretending(monkeypatch, kills):
    """A tick that cannot build the jail must not log as though the strong path
    ran -- the whole difference is whether the owner can undo it."""
    monkeypatch.setattr(appblock, "ensure_jail", lambda path=None: False)
    _stub_world(monkeypatch, "locked", [_STEAM])
    parts = wd._enforce_apps(_cfg(native=_native()), {})

    assert any("WEAK MODE" in p for p in parts)
    assert kills == [(100, wd.signal.SIGTERM)], "the fallback still ends the app"


def test_the_jail_lives_outside_the_delegated_subtree():
    """The containment rule only bites across a boundary the owner does not own.
    A jail under user@1000.service is one he can write his way out of."""
    assert "user.slice" not in appblock.JAIL
    assert "user@" not in appblock.JAIL
    assert appblock.JAIL.startswith("/sys/fs/cgroup/")


def test_ensure_jail_reports_failure_rather_than_raising(tmp_path, monkeypatch):
    """A non-root tick must degrade, not crash the whole watchdog run."""
    monkeypatch.setattr(appblock.os, "mkdir",
                        lambda *_a, **_k: (_ for _ in ()).throw(PermissionError("not root")))
    assert appblock.ensure_jail(str(tmp_path / "nope")) is False
