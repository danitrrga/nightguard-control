"""backend.py — the single seam between the TUI and the Python trust stack.

Import, never vendor: every classification / quota / verdict decision is computed
by the live LifeOS modules (`ngcommon`, `guard`, `nightguard_ctl`) so the TUI's
preview can never drift from the root signer (PORT-02). The TUI computes NO HMAC
and reads NO key — `ngcommon.read_key()` returns ``None`` for a non-root reader
and is never called here (PORT-03).
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile

# --- trust-stack import bootstrap (env-overridable for portability) ----------
# The published product must not hardcode the author's machine as the only path;
# the author's LifeOS instance sets NIGHTGUARD_STACK_DIR / NIGHTGUARD_DIR.
#
# Security (CR-02): STACK_DIR feeds BOTH sys.path (which ngcommon/guard/
# nightguard_ctl get imported) AND argv[2] of the sudo commit call. A poisoned
# NIGHTGUARD_STACK_DIR (malicious .bashrc / parent-process injection) could
# redirect the import chain and the script handed to sudo. We therefore resolve
# the env value to an absolute real path and PIN it: the directory must actually
# contain nightguard_ctl.py, otherwise we fail closed with a clear error rather
# than silently importing — and sudo-running — a substituted stack. The legit
# LifeOS override still works because it points at a dir that holds the script.
_DEFAULT_STACK_DIR = "/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard"


def _resolve_stack_dir() -> str:
    raw = os.environ.get("NIGHTGUARD_STACK_DIR", _DEFAULT_STACK_DIR)
    resolved = pathlib.Path(raw).resolve()
    ctl_path = resolved / "nightguard_ctl.py"
    if not ctl_path.is_file():
        raise RuntimeError(
            f"NIGHTGUARD_STACK_DIR resolves to {str(resolved)!r}, which does not "
            "contain nightguard_ctl.py. Refusing to import or sudo-run a stack from "
            "an unverified path. Set NIGHTGUARD_STACK_DIR to the real nightguard "
            "scripts directory (or unset it to use the default)."
        )
    return str(resolved)


STACK_DIR = _resolve_stack_dir()
# Absolute, validated path to the signer CLI — used as argv[2] in the sudo call
# so the path handed to sudo can never diverge from the pinned STACK_DIR.
CTL_SCRIPT = str(pathlib.Path(STACK_DIR) / "nightguard_ctl.py")
os.environ.setdefault(
    "NIGHTGUARD_DIR", "/home/danitrrga/dev/Projects/LifeOS/nightguard"
)
if STACK_DIR not in sys.path:
    sys.path.insert(0, STACK_DIR)

import ngcommon as ng  # noqa: E402  (import after sys.path bootstrap)
import guard  # noqa: E402
import nightguard_ctl as ctl  # noqa: E402

# Re-export the signer's weekly-token constant so display modules never duplicate
# the literal (WR-03): the token count shown in the confirm gate / meter is sourced
# from the same value the signer charges and cannot drift from it.
WEEKLY_TOKENS: int = ctl.WEEKLY_TOKENS

_DEFAULT_TZ = "Europe/Amsterdam"


def _tzname(cfg: dict | None = None) -> str:
    """Resolve the timezone for quota math from the sanctioned config."""
    if cfg is None:
        cfg = sanctioned_config()
    return cfg.get("timezone") or _DEFAULT_TZ


def read_state() -> dict:
    """Return the guard.json dict (key-less). ``{}`` when not initialized."""
    return ng.load_state()


def sanctioned_config() -> dict:
    """Parsed sanctioned config — the edit/diff base (Pitfall 5). ``{}`` if absent."""
    try:
        return ng.yaml_load(ng.file_bytes(ng.SANCTIONED).decode("utf-8"))
    except (FileNotFoundError, OSError):
        return {}


def sanctioned_text() -> str:
    """Raw decoded text of the sanctioned config.

    Wave 3 edits this text in place (format-preserving per-field line edits) so
    the bytes the HMAC signs are not disturbed by a YAML re-emit.
    """
    try:
        return ng.file_bytes(ng.SANCTIONED).decode("utf-8")
    except (FileNotFoundError, OSError):
        return ""


def live_verdict(cfg: dict, state: dict) -> str:
    """Advisory lock verdict from the guard — never local curfew math.

    One of: "locked" | "grace_active" | "outside_curfew" | "clock_tamper" |
    "offline_blocked". The root watchdog remains authoritative.
    """
    return guard.curfew_verdict(cfg, state)


def cache_only_verdict(cfg: dict, state: dict) -> str:
    """Resolve the lock verdict WITHOUT ever issuing a synchronous network query.

    The status read path (DESK-02 / Pitfall 1, T-11-04) must never hang the
    Waybar poll on a cold ``.timecache``: the guard's ``true_unix()`` falls
    through a cold cache to ``_sntp`` (2s) then ``_http_time`` (2s) — a ~4s block.
    We neutralize that by swapping both for instant-raising stubs for the
    duration of THIS call, so a cold cache falls straight through to
    ``(None, "offline")`` and ``curfew_verdict`` yields the fail-closed
    ``"offline_blocked"`` instead of blocking. A WARM cache still resolves
    normally (the stubs are only reached on the cold fall-through), so a
    freshly-validated machine shows its real locked/open/grace verdict.

    The neutralization lives entirely here — the root LifeOS ``guard.py`` trust
    stack is never edited. The stubs are restored in a ``finally`` so a later
    ``decide()`` (which legitimately wants live time) is unaffected.

    Returns one of the five ``live_verdict`` strings. Key-less, sudo-less,
    non-blocking by construction.
    """
    saved_sntp = guard._sntp
    saved_http = guard._http_time

    def _no_network(*_a, **_k):
        # Instant fail so true_unix()'s for-loop falls through to "offline".
        raise OSError("cache_only_verdict: synchronous network query suppressed")

    guard._sntp = _no_network
    guard._http_time = _no_network
    try:
        return guard.curfew_verdict(cfg, state)
    finally:
        guard._sntp = saved_sntp
        guard._http_time = saved_http


def preview_change(proposed_text: str) -> dict:
    """Direction labels + quota decision for a proposed edit.

    Computed by importing the CLI's own ``classify_change`` / ``quota_decide``
    (D-06 / D-07) — never a vendored classifier, so the preview is byte-faithful
    to what the signer will decide.
    """
    old_doc = sanctioned_config()
    new_doc = ng.yaml_load(proposed_text)
    dirs = ctl.classify_change(old_doc, new_doc)
    loosening = ctl.is_loosening(dirs)
    tzname = new_doc.get("timezone") or old_doc.get("timezone") or _DEFAULT_TZ
    decision = ctl.quota_decide(dirs, ng.load_state(), tzname)
    return {"dirs": dirs, "loosening": loosening, "decision": decision}


def tokens_left() -> int:
    """Remaining weekly loosen tokens after the lazy week reset (Pitfall 4).

    Uses empty dirs so ``quota_decide`` returns just the lazy-reset
    ``effective_spent`` rather than the stale raw ``weekly_spent``.
    """
    decision = ctl.quota_decide([], ng.load_state(), _tzname())
    return ctl.WEEKLY_TOKENS - decision["effective_spent"]


def commit(proposed_text: str, password: str) -> dict:
    """Sign + commit a proposed config via the sudoers CLI, password piped to ``sudo -S``.

    The password is collected by a masked in-TUI ``Input`` and fed to ``sudo -S`` on
    STDIN, so there is NO TTY prompt, no ``App.suspend()``, no GUI askpass, and no second
    terminal — every one of which failed or was clumsy in the walker-launched Wayland
    float (debug: commit-freeze-launcher-sudo). Because sudo never touches the terminal,
    it does not matter that Textual owns it.

    ``-S`` reads the password from stdin; ``-k`` forces real re-auth on every commit (the
    anti-impulse friction — the correct password is required each time, never a cached
    bypass); ``-p ''`` silences sudo's own prompt (the TUI shows it). The argv is the
    exact sudoers ``Cmnd_Alias`` shape; never ``shell=True``; the config CONTENT lives in
    ``tmp`` (a file), never on the command line. The caller runs this in a thread worker
    so the event loop never blocks.
    """
    fd, tmp = tempfile.mkstemp(suffix=".yaml")  # 0600, exclusive create
    try:
        with os.fdopen(fd, "w") as f:
            f.write(proposed_text)
        proc = subprocess.run(
            [
                "sudo",
                "-S",  # read the password from stdin (piped from the TUI), not the TTY
                "-k",  # invalidate any cached creds: always require the password (friction)
                "-p",
                "",  # empty prompt — the TUI presents the password field, not sudo
                "/usr/bin/python3",
                CTL_SCRIPT,  # validated absolute path (CR-02), the pinned sudoers shape
                "commit",
                "--from",
                tmp,
            ],
            input=(password or "") + "\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # BAR-04 / D-11: instant Waybar refresh, success-only + non-perturbing.
        # Only on a real success (returncode == 0) do we nudge the custom/nightguard
        # module (which declares "signal": 11) so the bar reflects a token spend the
        # instant it happens instead of on the next 30s poll. SIGRTMIN+11 is free
        # (live config uses 7/8/9/10). The push is fire-and-forget: check=False and a
        # swallow-all try/except so a missing pkill / absent waybar / any OSError can
        # NEVER flip the bar on a refused commit (T-12-02) nor propagate into or alter
        # the commit result (T-12-03) — the returned dict is built independently below.
        if proc.returncode == 0:
            try:
                subprocess.run(
                    ["pkill", "-RTMIN+11", "waybar"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass
        return {
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
