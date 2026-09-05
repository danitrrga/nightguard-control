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


def _policy_body(ext):
    """The canonical managed-policy document. config.yaml's extension_id is the single
source of truth, so the file on disk is always regenerated from it rather than from a
separate template that could drift."""
    return json.dumps(
        {"ExtensionInstallForcelist": [
            "%s;https://clients2.google.com/service/update2/crx" % ext]},
        indent=2,
    ) + "\n"


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


def _restore_policies(cfg, paths):
    """Rewrite the managed-policy files the browser reads. Logging a missing policy was
never enforcement: both dirs were world-writable and both files user-owned, so `rm` removed
the browser block with no password and the watchdog only recorded that it had happened.
Returns (restored, failed) path lists. Runs as root; the dirs are root:root 0755 after
deploy, so only this process can write them."""
    be = (cfg.get("blocking") or {}).get("browser_extension") or {}
    ext = be.get("extension_id")
    restored, failed = [], []
    if not ext:
        return restored, list(paths)
    body = _policy_body(ext)
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


def tick():
    key = ng.read_key()
    state = ng.load_state()
    reverted, fail_closed = guard.verify_and_revert(key, state)
    try:
        cfg = ng.yaml_load(ng.file_bytes(ng.CONFIG).decode("utf-8"))
    except Exception:
        cfg = {}
    missing = _missing_policies(cfg)
    restored, failed = _restore_policies(cfg, missing) if missing else ([], [])

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
    _log("tick: " + ("; ".join(parts) if parts else "ok"))


if __name__ == "__main__":
    tick()
