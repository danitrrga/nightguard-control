"""ngcommon.py — shared primitives for the Linux nightguard.

The guard (verify) and the control CLI (sign) MUST agree byte-for-byte on
canonicalization, so all of it lives here and is imported by both. Pure stdlib —
a fail-closed discipline tool must never die on a missing import.

Ported from the Windows PowerShell nightguard (HMAC-SHA256 config integrity,
sanctioned-revert, HMAC-chained audit log). DPAPI key storage is replaced by a
0600 raw key file (DPAPI CurrentUser scope was itself user-decryptable — the
tamper-resistance comes from the HMAC + sanctioned-revert + audit design, not key
secrecy).
"""
import hashlib
import hmac
import json
import os

_THIS = os.path.dirname(os.path.abspath(__file__))
# Fixed absolute path, never ~: nightguard_ctl.py runs under sudo (env_reset, HOME=/root)
# and the root watchdog must resolve the SAME instance dir as the user-side hook.
# Root-owned parent (Phase "trust-wall hardening"): a user-owned instance dir let the
# adversary — who is the user — rename the root-owned .guardkey / guard.json /
# config.sanctioned.yaml aside and drop in a self-consistent forged set, because rename and
# unlink are governed by the DIRECTORY's mode, not the file's. /var/lib/nightguard is
# root:root 0755; only config.yaml inside it stays user-writable (the revert model needs the
# hand edit to be possible so it can be undone).
ROOT_INSTANCE = "/var/lib/nightguard"
# Where this project kept its instance before the trust-wall hardening moved it
# to root-owned ground. Only ever read, only ever on the machine that has one --
# a fresh install creates ROOT_INSTANCE and never looks here. Derived rather
# than a literal home, which made every other machine carry one person's path.
LEGACY_INSTANCE = os.path.join(
    os.path.expanduser("~"), ".local", "share", "nightguard")
# Prefer the root-owned location; fall back to the legacy one only until deploy.sh has moved
# it. Safe to prefer unconditionally: /var/lib is root:root 0755, so the user can neither
# create nor shadow ROOT_INSTANCE — once it exists the fallback is unreachable.
DEFAULT_INSTANCE = ROOT_INSTANCE if os.path.isdir(ROOT_INSTANCE) else LEGACY_INSTANCE
_DEFAULT_INSTANCE = DEFAULT_INSTANCE  # back-compat alias
NIGHTGUARD_DIR = os.environ.get("NIGHTGUARD_DIR") or DEFAULT_INSTANCE
# True when this process is operating on a PRODUCTION instance — either location counts, so
# the seams stay dead across the migration. The test seams (the NTP time override) are dead
# whenever this holds, which is what stops them being used as a curfew bypass.
IS_CANONICAL_INSTANCE = os.path.abspath(NIGHTGUARD_DIR) in (ROOT_INSTANCE, LEGACY_INSTANCE)
CONFIG = os.path.join(NIGHTGUARD_DIR, "config.yaml")
SANCTIONED = os.path.join(NIGHTGUARD_DIR, "config.sanctioned.yaml")
STATE = os.path.join(NIGHTGUARD_DIR, "guard.json")
KEYFILE = os.path.join(NIGHTGUARD_DIR, ".guardkey")
LOCKFILE = os.path.join(NIGHTGUARD_DIR, ".nightguard.lock")
AUDIT = os.path.join(NIGHTGUARD_DIR, "guard-audit.log")

GENESIS = "0000000000000000000000000000000000000000000000000000000000000000"
STATE_FIELDS = ("config_hmac", "state_hmac", "weekly_spent", "week_anchor", "ledger", "grace")


def read_key():
    """Return the raw 32-byte HMAC key, or None if not initialized."""
    try:
        with open(KEYFILE, "rb") as fh:
            k = fh.read()
        if len(k) == 32:
            return k
        return None
    except OSError:
        return None


def write_key(key):
    os.makedirs(NIGHTGUARD_DIR, exist_ok=True)
    fd = os.open(KEYFILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    os.chmod(KEYFILE, 0o600)


def hmac_hex(key, data):
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def file_bytes(path):
    """Raw bytes of a file (the unit HMAC'd for config integrity)."""
    with open(path, "rb") as fh:
        return fh.read()


def config_hmac(key, path):
    return hmac_hex(key, file_bytes(path))


def load_state():
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def state_canonical_bytes(state):
    """Deterministic bytes the state_hmac is computed over: the state with
state_hmac blanked, compact JSON in fixed field order, one trailing \\n."""
    obj = {}
    for k in STATE_FIELDS:
        if k == "state_hmac":
            obj[k] = ""
        elif k in state:
            obj[k] = state[k]
    obj.setdefault("state_hmac", "")
    return (json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def state_hmac(key, state):
    return hmac_hex(key, state_canonical_bytes(state))


def _tag(key, prev_tag, payload):
    return hmac_hex(key, (prev_tag + payload).encode("utf-8"))


def _audit_lines():
    try:
        with open(AUDIT, encoding="utf-8") as fh:
            return [ln for ln in fh.read().splitlines() if ln]
    except OSError:
        return []


def verify_chain(key):
    """Return (ok, break_index). Absent log == genesis == ok. A present-but-
garbled chain reports the first broken record index."""
    prev = GENESIS
    for i, line in enumerate(_audit_lines()):
        if "|" not in line:
            return False, i
        payload, _, tag = line.rpartition("|")
        if _tag(key, prev, payload) != tag:
            return False, i
        prev = tag
    return True, -1


def append_audit(key, event, detail):
    """Append one HMAC-chained record: <ts>|<event>|<detail>|<tag>."""
    lines = _audit_lines()
    prev = lines[-1].rpartition("|")[2] if lines else GENESIS
    import datetime
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = f"{ts}|{event}|{detail}"
    tag = _tag(key, prev, payload)
    os.makedirs(NIGHTGUARD_DIR, exist_ok=True)
    with open(AUDIT, "a", encoding="utf-8") as fh:
        fh.write(payload + "|" + tag + "\n")
    return tag


def yaml_load(text):
    """Parse the fixed-shape nightguard config: nested maps by indent, `- ` list
items, scalars. Empty-value keys are disambiguated (map vs list vs null) by
looking at the next line's indent. No anchors/aliases/flow syntax. Scalar
list items only (the guard never needs the watchdog.apps map-list). Identical
for sign + verify because both import this one function."""
    lines = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    pos = [0]

    def indent_of(raw):
        return len(raw) - len(raw.lstrip(" "))

    def parse_block(min_indent):
        result = None
        while pos[0] < len(lines):
            raw = lines[pos[0]]
            ind = indent_of(raw)
            if ind < min_indent:
                return result
            line = raw.strip()
            if line.startswith("- "):
                if result is None:
                    result = []
                content = line[2:].strip()
                pos[0] += 1
                if ":" in content and content[0] not in ("'", '"'):
                    while pos[0] < len(lines) and indent_of(lines[pos[0]]) > ind and not lines[pos[0]].strip().startswith("- "):
                        pos[0] += 1
                    result.append(content)
                else:
                    result.append(_scalar(content))
            else:
                if result is None:
                    result = {}
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()
                pos[0] += 1
                if val == "":
                    nxt_ind = indent_of(lines[pos[0]]) if pos[0] < len(lines) else -1
                    if nxt_ind > ind or (pos[0] < len(lines) and lines[pos[0]].strip().startswith("- ") and nxt_ind >= ind):
                        result[key] = parse_block(ind + 1)
                    else:
                        result[key] = None
                else:
                    result[key] = _scalar(val)
        return result

    return parse_block(0) or {}


def _scalar(s):
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    if s == "[]":
        return []
    if s == "{}":
        return {}
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~", ""):
        return None
    try:
        return int(s)
    except ValueError:
        return s
