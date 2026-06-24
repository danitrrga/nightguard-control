"""backend.py — the single seam between the TUI and the Python trust stack.

Import, never vendor: every classification / quota / verdict decision is computed
by the live LifeOS modules (`ngcommon`, `guard`, `nightguard_ctl`) so the TUI's
preview can never drift from the root signer (PORT-02). The TUI computes NO HMAC
and reads NO key — `ngcommon.read_key()` returns ``None`` for a non-root reader
and is never called here (PORT-03).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

# --- trust-stack import bootstrap (env-overridable for portability) ----------
# The published product must not hardcode the author's machine as the only path;
# the author's LifeOS instance sets NIGHTGUARD_STACK_DIR / NIGHTGUARD_DIR.
STACK_DIR = os.environ.get(
    "NIGHTGUARD_STACK_DIR",
    "/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard",
)
os.environ.setdefault(
    "NIGHTGUARD_DIR", "/home/danitrrga/dev/Projects/LifeOS/nightguard"
)
if STACK_DIR not in sys.path:
    sys.path.insert(0, STACK_DIR)

import ngcommon as ng  # noqa: E402  (import after sys.path bootstrap)
import guard  # noqa: E402
import nightguard_ctl as ctl  # noqa: E402

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


def commit(proposed_text: str) -> dict:
    """Sign + commit a proposed config via the sudoers-mandated CLI argv.

    The caller wraps this in ``App.suspend()`` (Wave 3) so the TTY is released.
    stderr is intentionally NOT captured — it stays attached to the TTY so the
    sudo password / fingerprint prompt and any ``REFUSED`` line reach the user
    (Pitfall 3). The argv is the exact sudoers ``Cmnd_Alias`` shape; never
    ``shell=True``; argv[1] must be ``/usr/bin/python3`` and the script path
    absolute or sudoers will not match (T-10-03).
    """
    fd, tmp = tempfile.mkstemp(suffix=".yaml")  # 0600, exclusive create
    try:
        with os.fdopen(fd, "w") as f:
            f.write(proposed_text)
        proc = subprocess.run(
            [
                "sudo",
                "/usr/bin/python3",
                os.path.join(STACK_DIR, "nightguard_ctl.py"),
                "commit",
                "--from",
                tmp,
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        return {"returncode": proc.returncode, "stdout": (proc.stdout or "").strip()}
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
