#!/usr/bin/env python3
"""verify_browser_lock.py — prove the browser extension lock is actually in force.

Written because it was not. Until 2026-09-12 the Gecko half of the lock existed only
as a staged file (/var/lib/nightguard/policies/firefox-policies.json) that no code
read, no deploy installed and no watchdog restored, while the browser in daily use is
Zen. The add-on was found switched off in the Zen profile with nothing to notice or
undo it. A policy that is never read fails silently and looks identical to one that
works, so "it is configured" is not evidence and this script exists to replace it.

Two checks, both runnable as the owner (no root needed):

  1. FILE   every policy file the watchdog should maintain is present, root-owned,
            not writable by the owner, and byte-identical to what the watchdog would
            write right now.
  2. READ   each Gecko browser is started headless against a throwaway profile with
            the policy engine's own debug logging on, and the path it reports reading
            must be the /etc one. This is the check that would have caught the
            original hole: it fails when the file is in a place the browser ignores.

The Chromium half has no equivalent read probe (no startup log names the policy file),
so it is covered by the file check plus the extension's own location marker in the
profile, which reads 7 (EXTERNAL_POLICY_DOWNLOAD) only when a managed policy installed
it.

Exit status 0 = locked, 1 = at least one check failed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ngcommon as ng
import nightguard_watchdog as wd

# Where each Gecko browser's binary lives, keyed by the policy file it must report.
GECKO_BINARIES = {
    "/etc/zen/policies/policies.json": "/opt/zen-browser-bin/zen-bin",
    "/etc/firefox/policies/policies.json": "/usr/lib/firefox/firefox",
}

# Chromium profiles to inspect for the extension's install location.
CHROMIUM_PROFILES = {
    "chromium": "~/.config/chromium/Default/Preferences",
    "brave": "~/.config/BraveSoftware/Brave-Browser/Default/Preferences",
    "chrome": "~/.config/google-chrome/Default/Preferences",
}
EXTERNAL_POLICY_DOWNLOAD = 7

PROBE_TIMEOUT_SECS = 60


def _load_config():
    try:
        return ng.yaml_load(ng.file_bytes(ng.CONFIG).decode("utf-8"))
    except Exception as exc:
        print("FAIL  cannot read %s: %s" % (ng.CONFIG, exc))
        return None


def check_files(cfg, verdict):
    """Every expected policy file: present, root-owned, owner-unwritable, current."""
    failures = []
    want = wd.desired_bodies(cfg, verdict)
    if not want:
        failures.append("no policy files are expected at all — browser blocking is "
                        "disabled or has no extension id in %s" % ng.CONFIG)
        return failures
    for path, body in sorted(want.items()):
        try:
            st = os.stat(path)
        except OSError as exc:
            failures.append("%s: %s" % (path, exc))
            continue
        if st.st_uid != 0 or st.st_gid != 0:
            failures.append("%s: owned by uid %d gid %d, must be root:root — the owner "
                            "can rewrite it" % (path, st.st_uid, st.st_gid))
        if st.st_mode & 0o022:
            failures.append("%s: mode %o is group- or world-writable" % (path, st.st_mode & 0o777))
        parent = os.path.dirname(path)
        pst = os.stat(parent)
        if pst.st_uid != 0:
            failures.append("%s: directory owned by uid %d — rename and unlink are "
                            "governed by the DIRECTORY, so the file can be displaced"
                            % (parent, pst.st_uid))
        with open(path, encoding="utf-8") as fh:
            on_disk = fh.read()
        if on_disk != body:
            failures.append("%s: contents differ from what the watchdog would write"
                            % path)
        else:
            print("ok    %s (root-owned, current)" % path)
    return failures


def probe_gecko(binary):
    """Start the browser headless and read back which policies.json it actually used.

    The policy engine logs its path at debug through ConsoleAPI. Getting that onto
    stdout needs THREE prefs, not one, and the missing third is silent: with only
    loglevel and devtools.console.stdout.chrome the run produces ~2.1KB of other
    console output and no policy line at all, which reads exactly like a browser that
    never looked for a policy file. browser.dom.window.dump.enabled is what actually
    lets ConsoleAPI reach the process's stdout. Measured on this box: without it,
    50s of runtime and no hit; with it, the path line every time.

    The profile is a throwaway: probing the real one would run the owner's session
    headless.
    """
    profile = tempfile.mkdtemp(prefix="nightguard-probe-")
    try:
        with open(os.path.join(profile, "user.js"), "w", encoding="utf-8") as fh:
            fh.write('user_pref("browser.policies.loglevel","debug");\n')
            fh.write('user_pref("devtools.console.stdout.chrome", true);\n')
            fh.write('user_pref("browser.dom.window.dump.enabled", true);\n')
        env = dict(os.environ, MOZ_HEADLESS="1")
        try:
            proc = subprocess.run(
                [binary, "--headless", "--no-remote", "--profile", profile, "about:blank"],
                env=env, capture_output=True, text=True, timeout=PROBE_TIMEOUT_SECS)
            out = proc.stdout + proc.stderr
        except subprocess.TimeoutExpired as exc:
            # Expected: about:blank never exits. The log we want is already printed.
            out = (exc.stdout or "") + (exc.stderr or "")
            if isinstance(out, bytes):
                out = out.decode("utf-8", "replace")
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    for line in out.splitlines():
        if "policies.json path =" in line:
            return line.split("=", 1)[1].strip()
    return None


def check_gecko_reads():
    """The check the original hole would have failed."""
    failures = []
    for expected, binary in sorted(GECKO_BINARIES.items()):
        if not os.path.exists(binary):
            print("skip  %s not installed" % binary)
            continue
        used = probe_gecko(binary)
        if used is None:
            failures.append("%s: read no policies.json at all — the lock is not "
                            "applied in this browser" % binary)
        elif used != expected:
            failures.append("%s: reads %s, not %s. A policy file in a place the "
                            "browser ignores is not enforcement."
                            % (binary, used, expected))
        else:
            print("ok    %s reads %s" % (binary, used))
    return failures


def check_chromium_install(cfg):
    """The extension's location marker, which only a managed policy can set."""
    failures = []
    be = (cfg.get("blocking") or {}).get("browser_extension") or {}
    ext = be.get("extension_id")
    if not ext:
        return ["no chromium extension id configured"]
    for name, path in sorted(CHROMIUM_PROFILES.items()):
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            print("skip  %s has no profile yet" % name)
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                prefs = json.load(fh)
        except (OSError, ValueError) as exc:
            failures.append("%s: cannot read %s (%s)" % (name, path, exc))
            continue
        entry = ((prefs.get("extensions") or {}).get("settings") or {}).get(ext)
        if entry is None:
            print("warn  %s has not started since the policy landed — nothing to check "
                  "yet" % name)
            continue
        if entry.get("location") != EXTERNAL_POLICY_DOWNLOAD:
            failures.append("%s: extension location is %r, not %d "
                            "(EXTERNAL_POLICY_DOWNLOAD) — it is a hand-installed copy "
                            "the owner can remove"
                            % (name, entry.get("location"), EXTERNAL_POLICY_DOWNLOAD))
        elif entry.get("state") == 0:
            failures.append("%s: extension is DISABLED despite the forcelist" % name)
        else:
            print("ok    %s runs it as a force-installed extension" % name)
    return failures


def main():
    cfg = _load_config()
    if cfg is None:
        return 1
    try:
        import guard
        verdict = guard.curfew_verdict(cfg, ng.load_state())
    except Exception:
        verdict = None

    failures = []
    print("== policy files ==")
    failures += check_files(cfg, verdict)
    print("== what the Gecko browsers actually read ==")
    failures += check_gecko_reads()
    print("== chromium install provenance ==")
    failures += check_chromium_install(cfg)

    print()
    if failures:
        print("LOCKED: NO — %d problem(s)" % len(failures))
        for f in failures:
            print("  FAIL  %s" % f)
        return 1
    print("LOCKED: yes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
