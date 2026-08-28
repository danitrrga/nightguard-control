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
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ngcommon as ng
import guard

LOG = os.path.join(ng.NIGHTGUARD_DIR, "watchdog.log")
POLICY_PATHS = [
    "/etc/chromium/policies/managed/nightguard.json",
    "/etc/brave/policies/managed/nightguard.json",
]


def _log(msg):
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (ts, msg))


def _missing_policies(cfg):
    be = (cfg.get("blocking") or {}).get("browser_extension") or {}
    if not be.get("enabled", True):
        return []
    ext = be.get("extension_id")
    missing = []
    for p in POLICY_PATHS:
        try:
            with open(p, encoding="utf-8") as fh:
                data = fh.read()
        except OSError:
            missing.append(p)
            continue
        if ext and ext not in data:
            missing.append(p)
    return missing


def tick():
    key = ng.read_key()
    state = ng.load_state()
    reverted, fail_closed = guard.verify_and_revert(key, state)
    try:
        cfg = ng.yaml_load(ng.file_bytes(ng.CONFIG).decode("utf-8"))
    except Exception:
        cfg = {}
    missing = _missing_policies(cfg)

    parts = []
    if reverted:
        parts.append("REVERTED config.yaml -> " + ("HARD LOCKOUT" if fail_closed else "sanctioned"))
    if missing:
        parts.append("MISSING browser policies: " + ", ".join(missing))
    _log("tick: " + ("; ".join(parts) if parts else "ok"))


if __name__ == "__main__":
    tick()
