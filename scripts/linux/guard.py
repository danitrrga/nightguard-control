"""guard.py — Linux nightguard curfew guard (port of nightguard_guard.ps1).

Read-only verdict engine. Emits a JSON verdict on stdout and exits 0 (allow) or
1 (deny). The adapter translates that into the Claude Code hook contract.

Pipeline per fire:
  1. load HMAC key (soft mode if absent — curfew still evaluated, no integrity)
  2. verify config integrity; revert to config.sanctioned.yaml on mismatch
     (skipped while the control CLI holds .nightguard.lock mid-commit)
  3. verify guard.json state integrity; worst-case the state if tampered
  4. resolve verified true-time (NTP/HTTP, monotonic-anchored cache, test seam)
  5. clock-tamper check (|true - system| > max_offset)
  6. curfew window evaluation (per-day schedule, overnight wrap)
  7. daily grace window override -- honoured if the SIGNED state carries a grace
     record, but nothing in this build writes one. Inert; not a feature.
  8. append one HMAC-chained audit record
"""
import json
import os
import shutil
import struct
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ngcommon as ng

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

TIMECACHE = os.path.join(ng.NIGHTGUARD_DIR, ".timecache")
TIMECACHE_TTL = 120
NTP_SERVER = os.environ.get("NIGHTGUARD_NTP_SERVER", "pool.ntp.org")

HARD_LOCKOUT = 'timezone: Europe/Amsterdam\ncurfew:\n  enabled: true\n  start: "00:00"\n  end: "23:59"\n  allow_commands:\n    - "/shutdown"\n  block_when_offline: true\n  message: "Nightguard config integrity failure — locked down. Use the control CLI to repair."\n  tamper_message: "Nightguard config integrity failure — locked down."\n  offline_message: "Nightguard config integrity failure — locked down."\nclock_protection:\n  enabled: true\n  max_offset_minutes: 5\n'


def _boot_id():
    try:
        return open("/proc/sys/kernel/random/boot_id").read().strip()
    except OSError:
        return ""


def _sntp(server, timeout=2.0):
    import socket
    pkt = b'\x1b' + 47 * b'\x00'
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(pkt, (server, 123))
        data, _ = s.recvfrom(48)
    finally:
        s.close()
    secs = struct.unpack("!I", data[40:44])[0] - 2208988800
    return int(secs)


def _http_time(timeout=2.0):
    import email.utils
    import urllib.request
    req = urllib.request.Request("https://www.google.com", method="HEAD")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = r.headers.get("Date")
    return int(email.utils.parsedate_to_datetime(d).timestamp())


_TICK_OPEN = False  # True while a decide() tick is open (memo window active)
_TICK_TIME = None   # per-tick memo: (tnow|None, source) once true_unix resolves


def _begin_tick():
    """Open a memo window so true_unix() resolves at most once per decide()
call (curfew_verdict + decide()'s grace_remaining recompute share one result,
keeping a single true_unix() invocation). _end_tick() closes it."""
    global _TICK_OPEN, _TICK_TIME
    _TICK_OPEN = True
    _TICK_TIME = None


def _end_tick():
    global _TICK_OPEN, _TICK_TIME
    _TICK_OPEN = False
    _TICK_TIME = None


def true_unix():
    """Return (true_unix:int|None, source:str). Monotonic-anchored cache so a
later wall-clock change can't mask tampering, and so we don't hit the network
on every prompt. Test seam: NIGHTGUARD_TEST_NTP_OVERRIDE=1 + *_UNIX.

Within a decide() tick (between _begin_tick/_end_tick) the first result is
memoized so curfew_verdict and decide() share one resolution — at most one
true_unix() resolution per decide() call."""
    global _TICK_TIME
    if _TICK_OPEN and _TICK_TIME is not None:
        return _TICK_TIME

    def _store(result):
        global _TICK_TIME
        if _TICK_OPEN:
            _TICK_TIME = result
        return result

    # Test seam, DEAD IN PRODUCTION. The adversary is the user, so any env-gated seam is
    # attacker-controlled: `export NIGHTGUARD_TEST_NTP_OVERRIDE=1
    # NIGHTGUARD_NTP_OVERRIDE_UNIX=<daytime>` used to replace true time AND skip the
    # clock-tamper check (source == "override"), turning the curfew off with no password.
    # The gate is now the instance dir itself, which production pins and a caller cannot
    # repoint (the hook adapter honors NIGHTGUARD_DIR only under its own test seam, and the
    # sudoers rule pins the signer's path). Tests run against a fixture dir, so they keep it.
    if not ng.IS_CANONICAL_INSTANCE and os.environ.get("NIGHTGUARD_TEST_NTP_OVERRIDE") == "1":
        ov = os.environ.get("NIGHTGUARD_NTP_OVERRIDE_UNIX")
        if ov:
            return _store((int(ov), "override"))
    import time
    mono = time.monotonic()
    boot = _boot_id()
    try:
        with open(TIMECACHE, encoding="utf-8") as fh:
            c = json.load(fh)
        if c.get("boot_id") == boot and 0 <= mono - c["mono"] < TIMECACHE_TTL:
            return _store((int(c["true_unix"] + (mono - c["mono"])), "cache"))
    except (OSError, ValueError, KeyError):
        pass
    source, val = "offline", None
    for fn, name in ((lambda: _sntp(NTP_SERVER), "ntp"), (_http_time, "http")):
        try:
            val = fn()
            source = name
            break
        except Exception:
            continue
    if val is not None:
        try:
            with open(TIMECACHE, "w", encoding="utf-8") as fh:
                json.dump({"boot_id": boot, "true_unix": val, "mono": mono}, fh)
        except OSError:
            pass
    return _store((val, source))


# A real commit holds the lock for well under a second. Anything holding it longer is a
# crashed signer or an attempt to freeze the revert, so the suppression expires.
# Set by verify_and_revert() when the commit lock blocked a revert this call.
last_revert_suppressed = False
LOCK_SUPPRESS_MAX_SECS = 90
# Root-owned marker recording when the current run of lock-suppressed ticks began. The
# watchdog is a oneshot, so the age bound needs somewhere on disk to live.
SUPPRESS_MARKER = os.path.join(ng.NIGHTGUARD_DIR, ".lock_suppressed_since")


def app_holds_lock():
    """The control CLI holds an exclusive flock on .nightguard.lock while it
commits (writes sanctioned, then config, then re-signs state). If held, skip
revert this fire — the mismatch is a commit in progress, not tampering.

The lock file is root-owned 0600 (trust-wall hardening): an ordinary user process holding
`flock -x .nightguard.lock` used to freeze the revert indefinitely and silently, because
flock needs only an open descriptor and the file was user-owned. A user that cannot open it
cannot take it. If we cannot open it ourselves we report NOT held — the safe direction is to
revert, and a genuine commit runs as root and can always open it."""
    if not os.path.exists(ng.LOCKFILE):
        return False
    import fcntl
    try:
        fh = open(ng.LOCKFILE, "r")
    except OSError:
        return False
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fh, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        fh.close()


def _suppression_expired():
    """True once the lock has been suppressing a needed revert for longer than
LOCK_SUPPRESS_MAX_SECS. Starts the clock on first call of a suppressed run."""
    import time as _time
    now = _time.time()
    try:
        with open(SUPPRESS_MARKER, encoding="utf-8") as fh:
            since = float(fh.read().strip())
    except (OSError, ValueError):
        since = None
    if since is None or since > now:
        try:
            with open(SUPPRESS_MARKER, "w", encoding="utf-8") as fh:
                fh.write("%.3f" % now)
        except OSError:
            # Cannot record when suppression started, so cannot bound it. Refuse to
            # suppress rather than grant an unbounded freeze.
            return True
        return False
    return (now - since) > LOCK_SUPPRESS_MAX_SECS


def _clear_suppression_marker():
    try:
        os.remove(SUPPRESS_MARKER)
    except OSError:
        pass


def verify_and_revert(key, state):
    """Returns (reverted, fail_closed). Guard never signs — it only copies the
sanctioned snapshot or writes the hard lockout; re-signing is the CLI's job.

Sets module-global `last_revert_suppressed` when a needed revert was skipped because the
commit lock was held. The watchdog reads it so a suppressed tick is visible in the log
instead of appearing as a clean `tick: ok`."""
    global last_revert_suppressed
    last_revert_suppressed = False
    if key is None:
        return False, False
    stored = state.get("config_hmac", "")
    try:
        live = ng.config_hmac(key, ng.CONFIG)
    except OSError:
        live = None
    if live == stored and stored:
        _clear_suppression_marker()
        return False, False
    if app_holds_lock() and not _suppression_expired():
        last_revert_suppressed = True
        return False, False
    _clear_suppression_marker()
    if os.path.exists(ng.SANCTIONED):
        try:
            if ng.config_hmac(key, ng.SANCTIONED) == stored and stored:
                shutil.copyfile(ng.SANCTIONED, ng.CONFIG)
                return True, False
        except OSError:
            pass
    with open(ng.CONFIG, "w", encoding="utf-8") as fh:
        fh.write(HARD_LOCKOUT)
    return True, True


def _hhmm_to_min(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def in_curfew(cfg, true_dt):
    """true_dt is an aware datetime already in the config timezone."""
    cur = cfg.get("curfew") or {}
    if not cur.get("enabled", True):
        return False
    start_s, end_s = cur.get("start"), cur.get("end")
    dow = true_dt.strftime("%A").lower()
    sched = (cur.get("schedule") or {}).get(dow)
    if sched == "off":
        return False
    if isinstance(sched, str) and "-" in sched:
        start_s, end_s = sched.split("-", 1)
    elif isinstance(sched, dict):
        start_s, end_s = sched.get("start", start_s), sched.get("end", end_s)
    try:
        start_m, end_m = _hhmm_to_min(start_s), _hhmm_to_min(end_s)
        now_m = true_dt.hour * 60 + true_dt.minute
        if start_m > end_m:
            return now_m >= start_m or now_m < end_m
        return start_m <= now_m < end_m
    except Exception:
        return True


def localize(cfg, unix_ts):
    tzname = cfg.get("timezone") or "Europe/Amsterdam"
    tz = None
    if ZoneInfo is not None:
        try:
            tz = ZoneInfo(tzname)
        except Exception:
            try:
                tz = ZoneInfo("Europe/Amsterdam")
            except Exception:
                tz = timezone.utc
    return datetime.fromtimestamp(unix_ts, tz or timezone.utc)


def curfew_verdict(cfg, state):
    """Pure, side-effect-free curfew verdict (D-08/D-09).

    Returns ONE of: "locked", "grace_active", "outside_curfew",
    "clock_tamper", "offline_blocked".

    Reproduces decide()'s exact gating sequence (true-time -> clock tamper ->
    in_curfew -> block_when_offline -> grace window -> locked) but performs NO
    side effects: it triggers neither the config-revert path (no second revert)
    nor the HMAC audit-chain write (no duplicate audit). It takes NO signing
    parameter — integrity verification is the caller's job, and the caller is
    responsible for worst-casing `state` (passing grace=None) BEFORE calling.

    `cfg` is an already-parsed config dict; `state` an already-worst-cased
    state dict. Returns the verdict STRING only — grace_remaining_secs
    arithmetic stays decide()-local (C2). The watchdog kill gate FIRES on
    locked / clock_tamper / offline_blocked and SUPPRESSES on
    outside_curfew / grace_active.
    """
    import time
    cur = cfg.get("curfew") or {}
    clock = cfg.get("clock_protection") or {}
    # Resolve true-time at most once. If decide() already opened a tick, reuse its
    # shared memo (and leave it populated for decide's grace_remaining recompute).
    # If called standalone (08-02 watchdog), open a private tick so our single
    # true_unix() resolution is memoized and torn down cleanly afterward.
    own_tick = not _TICK_OPEN
    if own_tick:
        _begin_tick()
    try:
        tnow, source = true_unix()
        verified = tnow is not None
        if not verified:
            tnow = int(time.time())
        if verified and source != "override" and clock.get("enabled", True):
            offset = abs(tnow - int(time.time()))
            if offset > int(clock.get("max_offset_minutes", 5)) * 60:
                return "clock_tamper"
        true_dt = localize(cfg, tnow)
        if not in_curfew(cfg, true_dt):
            return "outside_curfew"
        if not verified and cur.get("block_when_offline", True):
            return "offline_blocked"
        grace = state.get("grace")
        if isinstance(grace, dict):
            try:
                same_day = grace.get("date") == true_dt.strftime("%Y-%m-%d")
                if same_day and int(grace["window_start"]) <= tnow < int(grace["window_end"]):
                    return "grace_active"
            except Exception:
                pass
        return "locked"
    finally:
        if own_tick:
            _end_tick()


def decide():
    key = ng.read_key()
    state = ng.load_state()
    state_valid = True
    if key is not None:
        stored = state.get("state_hmac", "")
        if not stored or ng.state_hmac(key, state) != stored:
            state_valid = False
            state = dict(state)
            state["weekly_spent"] = 3
            state["grace"] = None
    reverted, fail_closed = verify_and_revert(key, state)
    try:
        cfg = ng.yaml_load(ng.file_bytes(ng.CONFIG).decode("utf-8"))
    except Exception:
        cfg = ng.yaml_load(HARD_LOCKOUT)
        fail_closed = True
    # Curfew GATING math is defined ONCE in curfew_verdict (D-09). decide() maps
    # the returned verdict string back onto the existing _verdict() JSON + exit
    # contract; grace_remaining_secs stays decide()-local (C2). A per-tick memo
    # (_begin_tick) keeps true_unix() to one resolution across curfew_verdict and
    # the grace_remaining recompute below.
    import time
    _begin_tick()
    try:
        verdict = curfew_verdict(cfg, state)
        if verdict == "clock_tamper":
            return _verdict("deny", "clock tamper", 0, reverted, True, key, state_valid)
        if verdict == "outside_curfew":
            return _verdict("allow", "outside_curfew", 0, reverted, fail_closed, key, state_valid)
        if verdict == "offline_blocked":
            return _verdict("deny", "ntp unreachable", 0, reverted, True, key, state_valid)
        if verdict == "grace_active":
            # Reuse the SAME tnow curfew_verdict resolved (read the tick memo
            # directly — do NOT call true_unix() again; one invocation per tick).
            memo = _TICK_TIME
            tnow = memo[0] if (memo and memo[0] is not None) else int(time.time())
            remaining = 0
            grace = state.get("grace") if state_valid else None
            if isinstance(grace, dict):
                try:
                    remaining = int(grace["window_end"]) - tnow
                except Exception:
                    remaining = 0
            return _verdict("allow", "grace active", remaining, reverted, fail_closed, key, state_valid)
        return _verdict("deny", "curfew", 0, reverted, fail_closed, key, state_valid)
    finally:
        _end_tick()


def _verdict(decision, reason, grace_remaining, reverted, fail_closed, key, state_valid):
    broken, idx = False, -1
    if key is not None:
        ok, idx = ng.verify_chain(key)
        broken = not ok
        if broken:
            ng.append_audit(key, "chain-broken", "break_index=%d reason=tag mismatch" % idx)
        ng.append_audit(
            key, "guard-fire",
            "decision=%s reason=%s grace_remaining_secs=%d reverted=%s fail_closed=%s state_valid=%s"
            % (decision, reason, grace_remaining, reverted, fail_closed, state_valid))
    return {
        "decision": decision,
        "reason": reason,
        "grace_remaining_secs": grace_remaining,
        "reverted": reverted,
        "fail_closed": fail_closed,
        "audit_chain_broken": broken,
        "audit_chain_break_index": idx,
    }


def main():
    try:
        verdict = decide()
    except Exception as e:
        verdict = {
            "decision": "deny",
            "reason": "guard error: %s" % e,
            "grace_remaining_secs": 0,
            "reverted": False,
            "fail_closed": True,
            "audit_chain_broken": False,
            "audit_chain_break_index": -1,
        }
    print(json.dumps(verdict))
    sys.exit(0 if verdict["decision"] == "allow" else 1)


if __name__ == "__main__":
    main()
