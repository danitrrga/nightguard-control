#!/usr/bin/env python3
"""nightguard_watchdog.py — Linux revert-watchdog (systemd --user oneshot, 60s timer).

One tick per invocation. The cadence is the systemd timer's (OnUnitActiveSec=60),
NOT config.yaml's watchdog.check_interval_seconds -- this is a oneshot and never reads
that key. The key is carried in the payload as configuration, and no surface may
present it as the cadence.
  1. verify config integrity; revert config.yaml -> config.sanctioned.yaml on HMAC
     mismatch (skipped while the control CLI holds .nightguard.lock mid-commit).
  2. verify the root-managed browser policies still force-install the StayFree
     extension id from blocking.browser_extension.extension_id.
  3. append one local-time tick line to watchdog.log.

The curfew verdict itself is guard.py (fired by the Claude Code hook). This watchdog
only protects config integrity + browser-policy presence between fires; it never
signs (re-signing is nightguard_ctl.py's job — it reuses guard.verify_and_revert,
which only ever copies the sanctioned snapshot or writes the hard lockout).
"""
import json
import os
import pwd
import signal
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ngcommon as ng
import guard
import appblock

# The watchdog runs as root, so $HOME is root's. The game catalogue lives in the
# owner's home, and that owner is whoever owns config.yaml -- the one file deploy.sh
# deliberately leaves user-owned so a hand edit stays possible and revertible.
def _owner_home():
    try:
        return pwd.getpwuid(os.stat(ng.CONFIG).st_uid).pw_dir
    except (OSError, KeyError):
        return os.path.expanduser("~")


HOME = _owner_home()

LOG = os.path.join(ng.NIGHTGUARD_DIR, "watchdog.log")

# --- the two browser-policy families -----------------------------------------
# Chromium and Gecko read completely different documents from completely different
# places, and until 2026-09-12 only the Chromium half was ever enforced. The Gecko
# half existed as a staged file (/var/lib/nightguard/policies/firefox-policies.json)
# that nothing read, nothing deployed and nothing restored, so on Zen -- the browser
# actually used all day -- StayFree was a plain add-on the owner could switch off in
# two clicks. It was found switched off.
POLICY_PATHS = [
    "/etc/chromium/policies/managed/nightguard.json",
    "/etc/brave/policies/managed/nightguard.json",
    "/etc/opt/chrome/policies/managed/nightguard.json",
]

# Gecko target -> the install-directory policies.json it shadows.
#
# Firefox forks look for <SysConfD>/policies/policies.json FIRST and, when it exists,
# never read the one in the install directory (EnterprisePoliciesParent
# _getLocalConfigurationFile: the system file returns early). SysConfD on Linux is
# /etc/<MOZ_APP_NAME>, verified for both builds on this box: Zen reports
# MOZ_APP_NAME "zen" with MOZ_SYSTEM_POLICIES true, Firefox reports "firefox" with
# MOZ_SYSTEM_POLICIES true. So writing /etc/zen/policies/policies.json would silently
# drop Zen's own DisableAppUpdate unless the base document is merged in -- which is
# what the value half of this mapping is for. Reading the base every tick also means
# a package update that changes it propagates instead of being frozen at deploy time.
MOZILLA_POLICY_TARGETS = {
    "/etc/zen/policies/policies.json": "/opt/zen-browser-bin/distribution/policies.json",
    "/etc/firefox/policies/policies.json": "/usr/lib/firefox/distribution/policies.json",
}

# StayFree on AMO. A different add-on id from the Chrome Web Store build, and a
# different install channel, which is exactly why the Chromium-only forcelist never
# covered Zen. Verified against the AMO API for guid {30b15d56-...}: slug "stayfree",
# so the /latest.xpi redirect is stable across releases.
FIREFOX_EXTENSION_ID = "{30b15d56-b2fa-4cb2-98fd-7b5e26306483}"
FIREFOX_INSTALL_URL = (
    "https://addons.mozilla.org/firefox/downloads/latest/stayfree/latest.xpi"
)


def _log(msg):
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (ts, msg))


def _policy_body(ext, blocked_urls=(), block_incognito=True):
    """The canonical Chromium managed-policy document. config.yaml's extension_id is the
single source of truth, so the file on disk is always regenerated from it rather than
from a separate template that could drift.

``blocked_urls`` is how Discord and the rest of the distracting web are blocked, and
it lives here rather than in the process killer for a structural reason: on this box
Discord, the calendar, the todo list and EL PORTAL are all ``--app=`` windows of ONE
chromium process. Ending that process to block Discord would take the whole allowlist
with it. A managed URL blocklist separates them, and these policy files are already
root-owned and restored by this watchdog, so the lever is one the user cannot pull.

``block_incognito`` closes the two ways a Chromium profile runs WITHOUT the
force-installed extension. Incognito is the obvious one: an extension has no incognito
access until the user ticks a per-extension box, and Chromium exposes no policy to tick
it -- ``ExtensionSettings`` has no incognito key -- so the only enforcement available is
to remove incognito itself (IncognitoModeAvailability 1 = disabled). Guest mode is the
quieter one: a guest session starts with no extensions at all and no per-extension
toggle to lose, so leaving it enabled would leave a one-click clean browser behind.
"""
    policy = {"ExtensionInstallForcelist": [
        "%s;https://clients2.google.com/service/update2/crx" % ext]}
    if block_incognito:
        policy["IncognitoModeAvailability"] = 1
        policy["BrowserGuestModeEnabled"] = False
    urls = [u for u in (blocked_urls or []) if u]
    if urls:
        policy["URLBlocklist"] = list(urls)
    return json.dumps(policy, indent=2) + "\n"


def _match_pattern(url):
    """A Chromium URLBlocklist entry as a Gecko WebsiteFilter match pattern.

    The two policies take different syntaxes for the same intent, so one config list
    cannot be handed to both verbatim: Chromium accepts a bare host ("discord.com"),
    Gecko's WebsiteFilter wants a match pattern ("*://*.discord.com/*") and silently
    drops an entry it cannot parse. Anything that already looks like a pattern (it
    carries a scheme) is passed through untouched.
    """
    if "://" in url:
        return url
    host = url.lstrip(".")
    return "*://*.%s/*" % host


def _mozilla_base(base_path):
    """The install-directory policies.json this target shadows, as a policies dict.

    Missing or unparseable is not a reason to skip enforcement -- it only means there
    is nothing of the vendor's to carry forward, so the extension lock still gets
    written on top of an empty base.
    """
    try:
        with open(base_path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    policies = doc.get("policies")
    return dict(policies) if isinstance(policies, dict) else {}


def _mozilla_policy_body(base_path, ext, install_url, blocked_urls=()):
    """The canonical Gecko policies.json for Zen and Firefox.

    ``private_browsing`` is the Gecko answer to the hole Chromium can only close by
    removing incognito: Extension.sys.mjs _setupStartupPermissions reads
    Services.policies.getExtensionSettings(id).private_browsing and grants or revokes
    internal:privateBrowsingAllowed from it, so the add-on runs in private windows and
    the about:addons toggle stops being the owner's to flip. It is absent from this
    build's policies-schema.json, but the schema does not describe concrete extension
    ids at all (it declares only the literal "*" property and no patternProperties), so
    PolicySchemaValidator passes an id's settings object through unvalidated and
    unstripped. Private browsing therefore stays available and covered, rather than
    being switched off wholesale the way Chromium's incognito has to be.

    DisableSafeMode is the Gecko equivalent of the guest-mode hole: safe mode starts
    the browser with every extension off, and it is two clicks from the help menu.
    """
    policies = _mozilla_base(base_path)
    policies["ExtensionSettings"] = {
        ext: {
            "installation_mode": "force_installed",
            "install_url": install_url,
            "private_browsing": True,
        }
    }
    policies["DisableSafeMode"] = True
    urls = [_match_pattern(u) for u in (blocked_urls or []) if u]
    if urls:
        policies["WebsiteFilter"] = {"Block": urls, "Exceptions": []}
    return json.dumps({"policies": policies}, indent=2) + "\n"


def _browser_extension(cfg):
    """The browser_extension config block, or None when browser blocking is off."""
    be = (cfg.get("blocking") or {}).get("browser_extension") or {}
    if not be.get("extension_id") or not be.get("enabled", True):
        return None
    return be


def desired_policy(cfg, verdict):
    """The Chromium policy body that should be on disk right now, or None when
    unconfigured.

    The URL blocklist is applied ONLY while the curfew verdict is ``locked``, for the
    same reason the process killer is: a clock-tamper or offline verdict is a reason
    to refuse changes, not a reason to cut the user off from the web in the middle of
    the afternoon. Outside the curfew the file is rewritten without the blocklist, so
    the browser lifts it on its next policy read.

    The extension lock and the incognito/guest closures are NOT verdict-dependent:
    they are the always-on floor, and StayFree's own schedule decides what is blocked
    when. That is the whole point of force-installing it rather than blocking sites
    from here.
    """
    be = _browser_extension(cfg)
    if be is None:
        return None
    urls = be.get("blocked_urls") if verdict == appblock.LOCKED else []
    return _policy_body(be["extension_id"], urls, be.get("block_incognito", True))


def desired_mozilla_policy(cfg, verdict, base_path):
    """The Gecko policies.json body for one target, or None when unconfigured.

    The add-on id and install URL default to the constants above rather than being
    required in config.yaml. config.yaml is HMAC-sanctioned, so requiring them would
    have made closing this hole wait on a signed commit inside the edit window; the
    defaults make the Gecko lock arrive with the code, and config can still override.
    """
    be = _browser_extension(cfg)
    if be is None:
        return None
    ext = be.get("firefox_extension_id") or FIREFOX_EXTENSION_ID
    url = be.get("firefox_install_url") or FIREFOX_INSTALL_URL
    urls = be.get("blocked_urls") if verdict == appblock.LOCKED else []
    return _mozilla_policy_body(base_path, ext, url, urls)


def desired_bodies(cfg, verdict=None):
    """Every policy file this box should have right now, as {path: body}.

    A Gecko target whose browser is not installed is left out entirely: writing
    /etc/zen/policies/policies.json on a machine with no Zen would be an unread file
    that still reports "restored" every time it is recreated.
    """
    want = {}
    chromium = desired_policy(cfg, verdict)
    if chromium is not None:
        for path in POLICY_PATHS:
            want[path] = chromium
    for path, base in MOZILLA_POLICY_TARGETS.items():
        if not os.path.isdir(os.path.dirname(os.path.dirname(base))):
            continue
        body = desired_mozilla_policy(cfg, verdict, base)
        if body is not None:
            want[path] = body
    return want


def _missing_policies(cfg, verdict=None):
    """Policy files whose contents differ from what the config and verdict require.

    Compares the WHOLE desired document rather than just looking for the extension
    id. The blocklist half changes as the curfew opens and closes, so an id-only
    check would leave a stale blocklist in place all day -- or, worse, leave the
    curfew's blocklist absent all night because the id was still present.
    """
    missing = []
    for p, want in desired_bodies(cfg, verdict).items():
        try:
            with open(p, encoding="utf-8") as fh:
                data = fh.read()
        except OSError:
            missing.append(p)
            continue
        if data != want:
            missing.append(p)
    return missing


def _restore_policies(cfg, paths, verdict=None):
    """Rewrite the managed-policy files the browser reads. Logging a missing policy was
never enforcement: both dirs were world-writable and both files user-owned, so `rm` removed
the browser block with no password and the watchdog only recorded that it had happened.
Returns (restored, failed) path lists. Runs as root; the dirs are root:root 0755 after
deploy, so only this process can write them."""
    restored, failed = [], []
    want = desired_bodies(cfg, verdict)
    for p in paths:
        body = want.get(p)
        if body is None:
            failed.append(p)
            continue
        try:
            d = os.path.dirname(p)
            os.makedirs(d, exist_ok=True)
            try:
                os.chown(d, 0, 0)
                os.chmod(d, 0o755)
            except OSError:
                pass  # not root (dry run as the user) -- content still correct
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(body)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, 0o644)
            try:
                os.chown(tmp, 0, 0)
            except OSError:
                pass  # not root (dry run as the user) — content still correct
            os.replace(tmp, p)
            restored.append(p)
        except OSError:
            failed.append(p)
    return restored, failed



# A safety valve on the decision, not a policy knob. decide_kills is pure and
# tested, but it is also the one place where an inverted comparison would return
# "every process on the machine". Refusing to act on an implausibly large set turns
# that class of bug into a loud log line instead of a dead desktop.
MAX_KILLS_PER_TICK = 25


def _enforce_apps(cfg, state):
    """Signal the processes the curfew forbids. The ONLY side-effecting half.

    Everything that decides lives in appblock and is unit-tested; this function
    reads the world, asks for a decision, sanity-checks its size, and sends
    signals. Keeping it this thin is deliberate: it is the part that cannot be
    verified without root, so it must be small enough to review by eye.

    Enforcement is a root-owned jail cgroup, proven on this machine: the owner
    cannot migrate a process back out of it, cannot unfreeze it and cannot remove
    it, and cgroup.kill ends the tree in one write while dealing with concurrent
    forks. A PID signal loop loses a process that forks between the scan and the
    signal; this does not.

    SIGTERM remains as the fallback for a box where the jail cannot be created --
    a non-root tick, or a kernel without cgroup.kill. It is weaker, and the log
    says so rather than implying the strong path ran.
    """
    native = (cfg.get("blocking") or {}).get("native_apps") or {}
    if not native.get("enabled"):
        return []
    try:
        verdict = guard.curfew_verdict(cfg, state)
    except Exception:
        # An unresolvable verdict is not a locked verdict. Fail towards doing
        # nothing: the curfew's other layers still stand.
        return ["app enforcement skipped: verdict unavailable"]
    if verdict != appblock.LOCKED:
        return []

    catalog = appblock.build_catalog(HOME) if native.get("block_games") else []
    victims = appblock.decide_kills(verdict, cfg, appblock.read_processes(), catalog)
    if not victims:
        return []
    if len(victims) > MAX_KILLS_PER_TICK:
        return ["REFUSED to enforce: %d processes matched, over the %d cap — "
                "config or classifier is wrong, killed nothing"
                % (len(victims), MAX_KILLS_PER_TICK)]

    names = {p.pid: (os.path.basename(p.exe) or "?") for p in victims}
    parts = []

    if appblock.ensure_jail():
        jailed, failed = appblock.jail_and_kill([p.pid for p in victims])
        if jailed:
            parts.append("ENDED during curfew (jailed): "
                         + ", ".join("%s(%d)" % (names.get(pid, "?"), pid) for pid in jailed))
        if failed:
            parts.append("could not jail: "
                         + ", ".join("%s: %s" % (who, why) for who, why in failed))
        return parts

    # Fallback: no jail available (not root, or no cgroup.kill). Say so — a
    # silent downgrade would read as the strong path having run.
    parts.append("WEAK MODE: no jail cgroup, falling back to SIGTERM")
    ended, refused = [], []
    for proc in victims:
        try:
            os.kill(proc.pid, signal.SIGTERM)
            ended.append("%s(%d)" % (names.get(proc.pid, "?"), proc.pid))
        except ProcessLookupError:
            pass  # already gone between the scan and the signal
        except OSError as exc:
            refused.append("%s(%d): %s" % (names.get(proc.pid, "?"), proc.pid, exc))
    if ended:
        parts.append("ENDED during curfew: " + ", ".join(ended))
    if refused:
        parts.append("could not end: " + ", ".join(refused))
    return parts


def tick():
    key = ng.read_key()
    state = ng.load_state()
    reverted, fail_closed = guard.verify_and_revert(key, state)
    try:
        cfg = ng.yaml_load(ng.file_bytes(ng.CONFIG).decode("utf-8"))
    except Exception:
        cfg = {}
    try:
        verdict = guard.curfew_verdict(cfg, state)
    except Exception:
        verdict = None
    missing = _missing_policies(cfg, verdict)
    restored, failed = _restore_policies(cfg, missing, verdict) if missing else ([], [])

    parts = []
    if reverted:
        parts.append("REVERTED config.yaml -> " + ("HARD LOCKOUT" if fail_closed else "sanctioned"))
    if guard.last_revert_suppressed:
        # Never let a suppressed revert read as a clean tick: that silence was the whole
        # value of holding the lock.
        parts.append("SUPPRESSED: config mismatch NOT reverted, commit lock held "
                     "(expires after %ds)" % guard.LOCK_SUPPRESS_MAX_SECS)
    if key is None:
        parts.append("NO KEY: integrity unverifiable (not running as root?)")
    if restored:
        parts.append("RESTORED browser policies: " + ", ".join(restored))
    if failed:
        parts.append("FAILED to restore browser policies: " + ", ".join(failed))
    parts.extend(_enforce_apps(cfg, state))
    _log("tick: " + ("; ".join(parts) if parts else "ok"))


if __name__ == "__main__":
    tick()
