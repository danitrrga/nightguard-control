#!/usr/bin/env python3
"""nightguard_watchdog.py — Linux revert-watchdog (systemd --user oneshot, 60s timer).

One tick per invocation (the systemd timer fires this every check_interval_seconds):
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
POLICY_PATHS = [
    "/etc/chromium/policies/managed/nightguard.json",
    "/etc/brave/policies/managed/nightguard.json",
]


def _log(msg):
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (ts, msg))


def _policy_body(ext, blocked_urls=()):
    """The canonical managed-policy document. config.yaml's extension_id is the single
source of truth, so the file on disk is always regenerated from it rather than from a
separate template that could drift.

``blocked_urls`` is how Discord and the rest of the distracting web are blocked, and
it lives here rather than in the process killer for a structural reason: on this box
Discord, the calendar, the todo list and EL PORTAL are all ``--app=`` windows of ONE
chromium process. Ending that process to block Discord would take the whole allowlist
with it. A managed URL blocklist separates them, and these policy files are already
root-owned and restored by this watchdog, so the lever is one the user cannot pull.
"""
    policy = {"ExtensionInstallForcelist": [
        "%s;https://clients2.google.com/service/update2/crx" % ext]}
    urls = [u for u in (blocked_urls or []) if u]
    if urls:
        policy["URLBlocklist"] = list(urls)
    return json.dumps(policy, indent=2) + "\n"


def desired_policy(cfg, verdict):
    """The policy body that should be on disk right now, or None when unconfigured.

    The URL blocklist is applied ONLY while the curfew verdict is ``locked``, for the
    same reason the process killer is: a clock-tamper or offline verdict is a reason
    to refuse changes, not a reason to cut the user off from the web in the middle of
    the afternoon. Outside the curfew the file is rewritten without the blocklist, so
    the browser lifts it on its next policy read.
    """
    be = (cfg.get("blocking") or {}).get("browser_extension") or {}
    ext = be.get("extension_id")
    if not ext or not be.get("enabled", True):
        return None
    urls = be.get("blocked_urls") if verdict == appblock.LOCKED else []
    return _policy_body(ext, urls)


def _missing_policies(cfg, verdict=None):
    """Policy files whose contents differ from what the config and verdict require.

    Compares the WHOLE desired document rather than just looking for the extension
    id. The blocklist half changes as the curfew opens and closes, so an id-only
    check would leave a stale blocklist in place all day -- or, worse, leave the
    curfew's blocklist absent all night because the id was still present.
    """
    want = desired_policy(cfg, verdict)
    if want is None:
        return []
    missing = []
    for p in POLICY_PATHS:
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
    body = desired_policy(cfg, verdict)
    if body is None:
        return restored, list(paths)
    for p in paths:
        try:
            d = os.path.dirname(p)
            os.makedirs(d, exist_ok=True)
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

    SIGTERM, not SIGKILL. The research favours a root-owned jail cgroup with
    cgroup.kill, which is genuinely un-escapable and fork-race-proof; that needs a
    live root experiment this build has not been able to run, so the conservative
    signal ships first.
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

    ended, refused = [], []
    for proc in victims:
        try:
            os.kill(proc.pid, signal.SIGTERM)
            ended.append("%s(%d)" % (os.path.basename(proc.exe) or "?", proc.pid))
        except ProcessLookupError:
            pass  # already gone between the scan and the signal
        except OSError as exc:
            refused.append("%s(%d): %s" % (os.path.basename(proc.exe) or "?", proc.pid, exc))
    parts = []
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
