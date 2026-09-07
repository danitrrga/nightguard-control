#!/usr/bin/env python3
"""nightguard_ctl.py — the single sanctioned writer/signer for the Linux nightguard.

Run as root (via `sudo`); the key is root:root 0600 so a non-root invocation cannot
read it and refuses. The guard (guard.py) and watchdog (nightguard_watchdog.py) only
READ the key and REVERT to the sanctioned snapshot; re-signing is exclusively this
CLI's job. Every mutation runs under the .nightguard.lock fcntl flock and writes in
the crash-safe order from the Rust commit.rs (RULE-06):

    1. config.sanctioned.yaml   (the revert target)        -- FIRST
    2. guard.json               (re-signed: config_hmac=HMAC(NEW), state_hmac A3)
    3. config.yaml              (the LIVE file)             -- LAST  (chowned back to the user)

so any crash converges to OLD or NEW, never a forged/partial middle.

`commit` enforces the weekly-token quota in-process (RULE-01/02/04), mirroring the Rust
classify.rs/quota.rs: one edit session = at most one token; any field that LOOSENS costs
1 token and requires weekly_spent < 3 (else refused with "available again Monday");
all-tighten/neutral is free; all-noop writes nothing. After writing config.yaml it is
chowned back to $SUDO_UID:$SUDO_GID (D-5) so the user can hand-edit + the watchdog revert.

Subcommands:
    init                 create a 32-byte .guardkey (0600) if absent; sign current config
    verify               recompute config_hmac/state_hmac; report match/mismatch
    show                 print guard.json state + live/sanctioned config hashes
    commit --from FILE   quota'd commit: classify sanctioned-vs-FILE, charge a token on a
                         loosen, then sanctioned->guard.json->config (chown-back).
    commit --from FILE --rebaseline
                         no-token sanctioned re-baseline (admin policy reset; preserves quota).
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ngcommon as ng

LOOSEN, TIGHTEN, NOOP = "loosen", "tighten", "noop"
WEEKLY_TOKENS = 3
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# (label, key path, kind) — mirrors crates/mutation-engine/src/classify.rs FIELD_TABLE.
FIELD_TABLE = [
    ("curfew.enabled", ["curfew", "enabled"], "bool"),
    ("curfew.allow_commands", ["curfew", "allow_commands"], "list_add"),
    ("curfew.block_when_offline", ["curfew", "block_when_offline"], "bool"),
    ("clock_protection.enabled", ["clock_protection", "enabled"], "bool"),
    ("clock_protection.max_offset_minutes", ["clock_protection", "max_offset_minutes"], "num"),
    ("watchdog.enabled", ["watchdog", "enabled"], "bool"),
    ("watchdog.check_interval_seconds", ["watchdog", "check_interval_seconds"], "num"),
    ("blocking.browser_extension.enabled", ["blocking", "browser_extension", "enabled"], "bool"),
    ("blocking.native_apps.enabled", ["blocking", "native_apps", "enabled"], "bool"),
    ("blocking.native_apps.blacklist", ["blocking", "native_apps", "blacklist"], "list_remove"),
    # Allowlist mode permits only what is named, so it is strictly stricter than
    # blocklist mode: switching to it tightens, switching away loosens.
    ("blocking.native_apps.mode", ["blocking", "native_apps", "mode"], "mode"),
    # Adding an app to the allowlist permits MORE, so the polarity is the mirror
    # of the blacklist's.
    ("blocking.native_apps.allowlist", ["blocking", "native_apps", "allowlist"], "list_add"),
    ("blocking.native_apps.block_games", ["blocking", "native_apps", "block_games"], "bool"),
    # Removing a blocked site during curfew is a loosening, exactly like removing
    # an app from the blacklist.
    ("blocking.browser_extension.blocked_urls",
     ["blocking", "browser_extension", "blocked_urls"], "list_remove"),
    ("timezone", ["timezone"], "any"),
]


# ----- canonical write -------------------------------------------------------

def canonicalize(raw):
    """trust-kernel canon.rs: UTF-8, no BOM, LF, exactly one trailing newline."""
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return (text.rstrip("\n") + "\n").encode("utf-8")


def _atomic_write_bytes(path, data):
    tmp = path + ".tmp"
    f = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(f, data)
        os.fsync(f)
    finally:
        os.close(f)
    os.replace(tmp, path)
    try:
        dfd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass


class _Lock:
    def __enter__(self):
        import fcntl
        self._fcntl = fcntl
        os.makedirs(ng.NIGHTGUARD_DIR, exist_ok=True)
        self._fh = open(ng.LOCKFILE, "a+")
        fcntl.flock(self._fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        self._fcntl.flock(self._fh, self._fcntl.LOCK_UN)
        self._fh.close()


# ----- classifier (port of classify.rs) --------------------------------------

def _read_field(doc, keys):
    """Nested lookup into a yaml_load'd dict; absent/structural-absent -> None (A2)."""
    cur = doc
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _parse_hhmm(s):
    try:
        h, m = str(s).split(":")
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    if 0 <= h < 24 and 0 <= m < 60:
        return h * 60 + m
    return None


def _locked_mask(start_min, end_min):
    mask = [False] * 1440
    if start_min == end_min:
        return mask
    if end_min > start_min:
        for m in range(start_min, end_min):
            mask[m] = True
    else:
        for m in range(start_min, 1440):
            mask[m] = True
        for m in range(0, end_min):
            mask[m] = True
    return mask


def _mask_direction(old, new):
    unlocked_any = any(old[m] and not new[m] for m in range(1440))
    locked_any = any((not old[m]) and new[m] for m in range(1440))
    if unlocked_any:
        return LOOSEN
    if locked_any:
        return TIGHTEN
    return NOOP


def _compare_lists(old, new, add_loosens):
    old_set = list(old or [])
    new_set = list(new or [])
    added = any(e not in old_set for e in new_set)
    removed = any(e not in new_set for e in old_set)
    if add_loosens:
        return LOOSEN if added else (TIGHTEN if removed else NOOP)
    return LOOSEN if removed else (TIGHTEN if added else NOOP)


def _schedule_mask(value):
    if isinstance(value, str) and value.strip().lower() == "off":
        return [False] * 1440
    try:
        s, e = str(value).split("-")
    except (ValueError, AttributeError):
        return None
    sm, em = _parse_hhmm(s.strip()), _parse_hhmm(e.strip())
    if sm is None or em is None:
        return None
    return _locked_mask(sm, em)


def _in_window(now_min, start_min, end_min):
    """True when ``now_min`` falls in [start, end), wrapping past midnight.

    A window whose start equals its end is zero minutes wide, not twenty-four
    hours wide — the safe reading for a permission window.
    """
    if start_min == end_min:
        return False
    if start_min < end_min:
        return start_min <= now_min < end_min
    return now_min >= start_min or now_min < end_min


def _edit_locked_mask(start_min, end_min):
    """The minutes in which editing is FORBIDDEN, as a 1440-slot mask.

    ``_locked_mask`` models the curfew, where the window is the locked part. The
    edit window has the opposite polarity: the window is the part that is *open*.
    Inverting here lets ``_mask_direction`` judge both with the same locked-set
    model, so widening the edit window reads as a loosening exactly the way
    shortening the curfew does.
    """
    return [not m for m in _locked_mask(start_min, end_min)]


def _read_edit_window(doc):
    """The ``edit_window`` block as a plain dict, or None when absent."""
    block = _read_field(doc, ["edit_window"])
    if not isinstance(block, dict):
        return None
    return {
        "enabled": block.get("enabled"),
        "start": block.get("start"),
        "end": block.get("end"),
    }


def effective_edit_window(old_doc, new_doc):
    """The edit window that governs THIS commit: the sanctioned one.

    Deliberately ignores ``new_doc``. Resolving the window from the proposal
    would let a single commit widen the window and then be judged by the widened
    version — the change would authorise itself. The user is bound by the window
    he signed while his judgement was good, and relaxing it is itself a
    loosening that must pass the old window first.
    """
    return _read_edit_window(old_doc)


def _classify_edit_window(old_doc, new_doc):
    """Direction for the ``edit_window`` block as a whole.

    One classifier entry rather than three (enabled/start/end) because every
    editable field is a new bypass vector, and the three are only ever meaningful
    together. Presence is part of the comparison: deleting the block is the
    cheapest imaginable bypass, so it must cost the same as disabling it.
    """
    old, new = _read_edit_window(old_doc), _read_edit_window(new_doc)
    if old is None and new is None:
        return NOOP
    if old is None:
        return TIGHTEN          # adding the restriction
    if new is None:
        return LOOSEN           # removing it entirely
    dirs = [_classify_field("bool", old.get("enabled"), new.get("enabled"))]
    bounds = [_parse_hhmm(old.get("start")), _parse_hhmm(old.get("end")),
              _parse_hhmm(new.get("start")), _parse_hhmm(new.get("end"))]
    if None not in bounds:
        os_, oe, ns, ne = bounds
        dirs.append(_mask_direction(_edit_locked_mask(os_, oe), _edit_locked_mask(ns, ne)))
    if LOOSEN in dirs:
        return LOOSEN
    if TIGHTEN in dirs:
        return TIGHTEN
    return NOOP


def _classify_field(kind, old, new):
    if old is None or new is None:
        return NOOP
    if old == new:
        return NOOP
    if kind == "bool":
        if old is True and new is False:
            return LOOSEN
        if old is False and new is True:
            return TIGHTEN
        return NOOP
    if kind == "num":
        try:
            o, n = int(old), int(new)
        except (ValueError, TypeError):
            return NOOP
        return LOOSEN if n > o else (TIGHTEN if n < o else NOOP)
    if kind == "list_add":
        return _compare_lists(old, new, True)
    if kind == "list_remove":
        return _compare_lists(old, new, False)
    if kind == "schedule":
        om, nm = _schedule_mask(old), _schedule_mask(new)
        return _mask_direction(om, nm) if (om is not None and nm is not None) else NOOP
    if kind == "mode":
        o, n = str(old).strip().lower(), str(new).strip().lower()
        if o == n:
            return NOOP
        # Anything that is not the strict mode is treated as the permissive one,
        # so a typo cannot be classified as a free tightening.
        o_strict, n_strict = (o == "allowlist"), (n == "allowlist")
        if o_strict and not n_strict:
            return LOOSEN
        if n_strict and not o_strict:
            return TIGHTEN
        return NOOP
    if kind == "any":
        return LOOSEN
    return NOOP


def classify_change(old_doc, new_doc):
    """Return [(label, direction)] for every spec-table field + the curfew window + schedule."""
    out = []
    for label, keys, kind in FIELD_TABLE:
        out.append((label, _classify_field(kind, _read_field(old_doc, keys), _read_field(new_doc, keys))))
    # curfew window (start+end) judged jointly by the locked-set model.
    def win(doc):
        s = _parse_hhmm(_read_field(doc, ["curfew", "start"]))
        e = _parse_hhmm(_read_field(doc, ["curfew", "end"]))
        return (s, e)
    os_, oe = win(old_doc)
    ns, ne = win(new_doc)
    if None not in (os_, oe, ns, ne):
        out.append(("curfew.window", _mask_direction(_locked_mask(os_, oe), _locked_mask(ns, ne))))
    else:
        out.append(("curfew.window", NOOP))
    out.append(("edit_window", _classify_edit_window(old_doc, new_doc)))
    for day in WEEKDAYS:
        keys = ["curfew", "schedule", day]
        out.append(("curfew.schedule." + day,
                    _classify_field("schedule", _read_field(old_doc, keys), _read_field(new_doc, keys))))
    return out


def is_loosening(dirs):
    return any(d == LOOSEN for _, d in dirs)


# ----- quota (port of quota.rs / week.rs) ------------------------------------

def _current_week_monday(tzname):
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(tzname or "Europe/Amsterdam"))
    except Exception:
        now = datetime.now()
    monday = now.date() - timedelta(days=now.weekday())
    return monday.isoformat()


def verified_now_minutes(sanctioned_doc):
    """Minute-of-day in the SANCTIONED config's timezone, from verified true time.

    Two sources are deliberately NOT used. The system clock is not consulted
    directly: ``guard.true_unix()`` resolves time over SNTP with a
    monotonic-anchored cache, so moving the wall clock cannot fake the hour. And
    the timezone comes from the signed config rather than /etc/localtime or $TZ,
    because ``sudo -l`` on this box grants a passwordless
    ``timedatectl set-timezone`` — reading the system zone would turn that entry
    into a one-command shift of the edit window.

    Returns None when true time cannot be resolved, which the caller treats as a
    refusal rather than a pass.
    """
    try:
        import guard
    except Exception:
        return None
    try:
        ts, _source = guard.true_unix()
        if ts is None:
            return None
        local = guard.localize(sanctioned_doc or {}, ts)
        return local.hour * 60 + local.minute
    except Exception:
        return None


def _edit_window_refusal(edit_window, now_minutes):
    """Why this loosening is refused right now, or None if the clock allows it.

    Only ever consulted for loosening changes: tightening the pact is allowed at
    any hour, which is the same asymmetry that makes only loosening cost a token.
    """
    if not edit_window or not edit_window.get("enabled"):
        return None
    start = _parse_hhmm(edit_window.get("start"))
    end = _parse_hhmm(edit_window.get("end"))
    if start is None or end is None:
        return ("the edit window is malformed (start=%r end=%r); refusing to loosen "
                "until it is a valid HH:MM range" % (edit_window.get("start"), edit_window.get("end")))
    if now_minutes is None:
        # Fail closed, matching the guard's block_when_offline posture. An
        # unverifiable clock is exactly the state an attacker would engineer.
        return ("cannot verify the time; loosening is refused until the clock is confirmed "
                "(the edit window is %s-%s)" % (edit_window.get("start"), edit_window.get("end")))
    if not _in_window(now_minutes, start, end):
        return ("outside the edit window (%s-%s); loosening is refused until then"
                % (edit_window.get("start"), edit_window.get("end")))
    return None


def quota_decide(dirs, state, tzname, edit_window=None, now_minutes=None):
    """Mirror quota.rs decide(): lazy week reset, then the commit rule.

    ``edit_window`` and ``now_minutes`` add the clock gate. They default to None
    so a three-argument call keeps its old meaning — ``tokens_left()`` passes
    empty dirs and only wants the lazy-reset counter, and the ungated form is
    what a config without an ``edit_window`` block gets.

    ``now_minutes`` is the minute-of-day in the SIGNED config's timezone, and the
    caller is responsible for deriving it from verified time. It is passed in
    rather than read here because the two callers need different clocks: the root
    signer resolves live true time, while the pre-auth preview must never issue a
    synchronous network query.
    """
    cur_monday = _current_week_monday(tzname)
    anchor = state.get("week_anchor") or ""
    should_reset = (anchor == "" or anchor < cur_monday)  # ISO dates compare lexically
    effective_spent = 0 if should_reset else int(state.get("weekly_spent", 0) or 0)
    week_anchor = cur_monday
    if all(d == NOOP for _, d in dirs):
        return dict(allowed=True, reason=None, costs_token=False, is_noop=True,
                    effective_spent=effective_spent, week_anchor=week_anchor)
    if not is_loosening(dirs):
        return dict(allowed=True, reason=None, costs_token=False, is_noop=False,
                    effective_spent=effective_spent, week_anchor=week_anchor)
    refusal = _edit_window_refusal(edit_window, now_minutes)
    if refusal is not None:
        return dict(allowed=False, is_noop=False, costs_token=False,
                    effective_spent=effective_spent, week_anchor=week_anchor,
                    reason=refusal)
    if effective_spent < WEEKLY_TOKENS:
        return dict(allowed=True, reason=None, costs_token=True, is_noop=False,
                    effective_spent=effective_spent, week_anchor=week_anchor)
    return dict(allowed=False, is_noop=False, costs_token=False,
                effective_spent=effective_spent, week_anchor=week_anchor,
                reason="weekly loosen quota exhausted (%d/%d used); available again Monday"
                       % (WEEKLY_TOKENS, WEEKLY_TOKENS))


# ----- state build + commit --------------------------------------------------

def _sign_state(key, new_config_hmac, prev, weekly_spent, week_anchor, ledger):
    state = {
        "config_hmac": new_config_hmac,
        "state_hmac": "",
        "weekly_spent": weekly_spent,
        "week_anchor": week_anchor,
        "ledger": ledger,
        "grace": prev.get("grace", None),
    }
    state["state_hmac"] = ng.state_hmac(key, state)
    return state


def _chown_back_config():
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if uid and gid:
        try:
            os.chown(ng.CONFIG, int(uid), int(gid))
        except OSError as e:
            print("warn: could not chown config.yaml back to the user: %s" % e, file=sys.stderr)


def _write_commit(key, canonical, prev, weekly_spent, week_anchor, ledger, audit_event, audit_detail):
    import json
    new_hmac = ng.hmac_hex(key, canonical)
    with _Lock():
        _atomic_write_bytes(ng.SANCTIONED, canonical)
        state = _sign_state(key, new_hmac, prev, weekly_spent, week_anchor, ledger)
        _atomic_write_bytes(ng.STATE, (json.dumps(state, indent=2) + "\n").encode("utf-8"))
        _atomic_write_bytes(ng.CONFIG, canonical)
        _chown_back_config()
        ng.append_audit(key, audit_event, audit_detail)
    return new_hmac


def cmd_commit(args):
    import time
    key = ng.read_key()
    if key is None:
        print("ERROR: cannot read .guardkey — run as root via `sudo`. Refusing (wrote nothing).",
              file=sys.stderr)
        return 2
    with open(args.from_path, "rb") as fh:
        canonical = canonicalize(fh.read())
    prev = ng.load_state()

    if args.rebaseline:
        # The re-baseline shortcut writes a new sanctioned config with NO
        # classification and NO token charge, and it is reachable through the
        # sudoers wildcard (`nightguard_ctl.py commit *`). Left ungated it is a
        # complete bypass of the edit window: any config, any hour, free. It is
        # therefore held to the window as if it were the broadest possible
        # loosening, because that is exactly what it can install.
        try:
            sanctioned_doc = ng.yaml_load(ng.file_bytes(ng.SANCTIONED).decode("utf-8"))
        except OSError:
            sanctioned_doc = {}
        window = effective_edit_window(sanctioned_doc, sanctioned_doc)
        refusal = _edit_window_refusal(window, verified_now_minutes(sanctioned_doc))
        if refusal is not None:
            print("REFUSED (re-baseline): %s" % refusal, file=sys.stderr)
            return 1
        new_hmac = _write_commit(key, canonical, prev,
                                 prev.get("weekly_spent", 0), prev.get("week_anchor", ""),
                                 prev.get("ledger", []),
                                 "re-baseline", "sanctioned reset (no token)")
        print("re-baselined (no token): config_hmac=%s" % new_hmac)
        return 0

    # Quota'd commit: classify sanctioned (current) -> proposed.
    try:
        old_doc = ng.yaml_load(ng.file_bytes(ng.SANCTIONED).decode("utf-8"))
    except OSError:
        old_doc = {}
    new_doc = ng.yaml_load(canonical.decode("utf-8"))
    tzname = new_doc.get("timezone") or old_doc.get("timezone") or "Europe/Amsterdam"
    dirs = classify_change(old_doc, new_doc)
    window = effective_edit_window(old_doc, new_doc)
    decision = quota_decide(dirs, prev, tzname, edit_window=window,
                            now_minutes=verified_now_minutes(old_doc))
    loosened = [lbl for lbl, d in dirs if d == LOOSEN]
    direction = "loosen" if is_loosening(dirs) else ("noop" if decision["is_noop"] else "tighten")

    if not decision["allowed"]:
        print("REFUSED (%s): %s" % (direction, decision["reason"]), file=sys.stderr)
        return 1
    if decision["is_noop"]:
        print("no-op: proposed config is identical to sanctioned; nothing written.")
        return 0

    weekly_spent = decision["effective_spent"] + (1 if decision["costs_token"] else 0)
    ledger = list(prev.get("ledger", []))
    if decision["costs_token"]:
        ledger.append({"ntp_timestamp": int(time.time()), "fields": loosened})
    detail = "direction=%s costs_token=%s loosened=%s spent=%d/%d" % (
        direction, decision["costs_token"], ",".join(loosened) or "-", weekly_spent, WEEKLY_TOKENS)
    new_hmac = _write_commit(key, canonical, prev, weekly_spent, decision["week_anchor"], ledger,
                             "commit", detail)
    print("committed (%s%s): config_hmac=%s | tokens %d/%d used" % (
        direction, " -1 token" if decision["costs_token"] else ", free",
        new_hmac, weekly_spent, WEEKLY_TOKENS))
    return 0


def cmd_verify(args):
    key = ng.read_key()
    state = ng.load_state()
    stored_cfg = state.get("config_hmac")
    if key is None:
        print("key unreadable (run via sudo for full verify). guard.json present:", bool(state))
        return 2
    live = ng.config_hmac(key, ng.CONFIG)
    sanc = ng.config_hmac(key, ng.SANCTIONED) if os.path.exists(ng.SANCTIONED) else None
    chain_ok, brk = ng.verify_chain(key)
    cfg_ok, sanc_ok = live == stored_cfg, sanc == stored_cfg
    state_ok = ng.state_hmac(key, state) == state.get("state_hmac")
    print("config.yaml      hmac == guard.json :", cfg_ok)
    print("config.sanctioned hmac == guard.json:", sanc_ok)
    print("state_hmac       == guard.json      :", state_ok)
    print("audit chain      verifies           :", chain_ok, "(break_index=%d)" % brk)
    print("weekly tokens used                  : %s/%d" % (state.get("weekly_spent"), WEEKLY_TOKENS))
    return 0 if (cfg_ok and sanc_ok and state_ok and chain_ok) else 1


def cmd_show(args):
    import json
    key = ng.read_key()
    print(json.dumps(ng.load_state(), indent=2))
    if key is not None:
        print("# live config_hmac     :", ng.config_hmac(key, ng.CONFIG))
        if os.path.exists(ng.SANCTIONED):
            print("# sanctioned config_hmac:", ng.config_hmac(key, ng.SANCTIONED))
    else:
        print("# (key unreadable as this user — run via sudo for hashes)")
    return 0


# The window the migration installs when a config predates this feature. 05:30 is
# the curfew's end (the hour the house reopens); 14:00 is early enough that an
# evening impulse cannot reach it. Both are editable afterwards, at a token's cost.
EDIT_WINDOW_DEFAULT_START = "05:30"
EDIT_WINDOW_DEFAULT_END = "14:00"

EDIT_WINDOW_BLOCK = """
# When the curfew may be WEAKENED. Outside this window a loosening commit is
# refused before the weekly token is even considered; tightening is always
# allowed, at any hour. This exists because a weekly quota limits how often the
# pact is weakened but not when, and the hour the user's judgement is worst is
# exactly when he reaches for the token.
edit_window:
  enabled: true
  start: "%s"
  end: "%s"
""" % (EDIT_WINDOW_DEFAULT_START, EDIT_WINDOW_DEFAULT_END)


# New keys for the app blocker, added to blocks that already exist. Values are the
# conservative ones: blocklist mode (allowlist would kill the desktop on a config
# the user has not reviewed) and an empty site list, so the migration changes no
# behaviour by itself. The user turns each on from the TUI afterwards, at the
# usual cost.
NATIVE_APPS_KEYS = [
    "    # blocklist: end only the apps named below. allowlist: end everything",
    "    # EXCEPT those named — stricter, and it will close your terminals.",
    "    mode: blocklist",
    "    # Auto-detect newly installed games (Steam, Heroic, any .desktop entry",
    "    # declaring Categories=Game) so a new install is covered without an edit.",
    "    block_games: false",
    "    allowlist:",
    "      - zen-bin",
    "      - foot",
]

BROWSER_KEYS = [
    "    # Sites blocked during curfew, via the root-owned managed browser policy.",
    "    # Webapps (Discord, the calendar, the todo list) share ONE chromium",
    "    # process, so they cannot be separated by ending a process — only by URL.",
    "    blocked_urls: []",
]


def _append_to_block(text, parent_line, new_lines):
    """Insert lines at the end of an existing YAML block, preserving layout.

    Line-oriented on purpose. The config is human-written, carries comments, and
    is read by a deliberately minimal parser shared with the guard; a real YAML
    round-trip would reformat it and change the bytes the HMAC signs for no
    reason. Returns the text unchanged if the parent block is not found.
    """
    lines = text.split("\n")
    try:
        start = lines.index(parent_line)
    except ValueError:
        return text
    indent = len(parent_line) - len(parent_line.lstrip())
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        end += 1
    # Step back over trailing blank lines so the insert lands inside the block.
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[:end] + new_lines + lines[end:])


def cmd_ensure_config(args):
    """Bring an older config up to the current schema, then re-sign it once.

    Three migrations, each independently idempotent: the edit_window block, the
    app blocker's new keys, and the browser policy's site list. Without them the
    new features ship inert -- the gate reads its window from the SANCTIONED
    config, so a config with no block is ungated by design for back-compat.

    Both the live and sanctioned copies are written, because writing only the
    live one would have the watchdog revert it within 60 seconds.

    Root only, and it re-signs without classifying, so it is deliberately NOT in
    the sudoers file: it runs from deploy.sh, which the user authorises with a
    password. Every key it adds is at its most conservative value, so the
    migration itself changes no behaviour.
    """
    key = ng.read_key()
    if key is None:
        print("ERROR: cannot read .guardkey — run as root. Refusing (wrote nothing).",
              file=sys.stderr)
        return 2
    try:
        live = ng.file_bytes(ng.CONFIG).decode("utf-8")
    except OSError:
        print("ERROR: no config.yaml to migrate", file=sys.stderr)
        return 2

    doc = ng.yaml_load(live)
    updated, added = live, []

    if _read_edit_window(doc) is None:
        updated = updated.rstrip("\n") + "\n" + EDIT_WINDOW_BLOCK
        added.append("edit_window %s-%s" % (EDIT_WINDOW_DEFAULT_START, EDIT_WINDOW_DEFAULT_END))

    native = _read_field(doc, ["blocking", "native_apps"]) or {}
    if isinstance(native, dict) and "mode" not in native:
        updated = _append_to_block(updated, "  native_apps:", NATIVE_APPS_KEYS)
        added.append("native_apps.mode/allowlist/block_games")

    browser = _read_field(doc, ["blocking", "browser_extension"]) or {}
    if isinstance(browser, dict) and "blocked_urls" not in browser:
        updated = _append_to_block(updated, "  browser_extension:", BROWSER_KEYS)
        added.append("browser_extension.blocked_urls")

    if not added:
        print("config already current; nothing to do.")
        return 0

    canonical = canonicalize(updated.encode("utf-8"))
    reparsed = ng.yaml_load(canonical.decode("utf-8"))

    # Refuse rather than write a config the guard's own parser reads differently
    # from what was intended. A silently mis-parsed config is worse than an
    # un-migrated one: the guard would act on it.
    problems = []
    if _read_edit_window(reparsed) is None:
        problems.append("edit_window did not parse back")
    if (_read_field(reparsed, ["blocking", "native_apps", "mode"]) or "") != "blocklist":
        problems.append("native_apps.mode did not parse back")
    for keys, before in ((["curfew", "start"], _read_field(doc, ["curfew", "start"])),
                         (["curfew", "end"], _read_field(doc, ["curfew", "end"])),
                         (["blocking", "browser_extension", "extension_id"],
                          _read_field(doc, ["blocking", "browser_extension", "extension_id"])),
                         (["blocking", "native_apps", "blacklist"],
                          _read_field(doc, ["blocking", "native_apps", "blacklist"]))):
        if _read_field(reparsed, keys) != before:
            problems.append("%s changed value" % ".".join(keys))
    if problems:
        print("ERROR: migration would corrupt the config (%s); wrote nothing."
              % "; ".join(problems), file=sys.stderr)
        return 2

    prev = ng.load_state()
    new_hmac = _write_commit(key, canonical, prev,
                             prev.get("weekly_spent", 0), prev.get("week_anchor", ""),
                             prev.get("ledger", []),
                             "migrate", "added %s (no token)" % ", ".join(added))
    print("migrated (%s): config_hmac=%s" % (", ".join(added), new_hmac))
    return 0


def cmd_init(args):
    import json
    if ng.read_key() is not None:
        print("key already present")
    else:
        ng.write_key(os.urandom(32))
        print("created 32-byte .guardkey (0600)")
    key = ng.read_key()
    if not os.path.exists(ng.CONFIG):
        print("ERROR: no config.yaml to sign", file=sys.stderr)
        return 2
    with open(ng.CONFIG, "rb") as fh:
        canonical = canonicalize(fh.read())
    prev = ng.load_state()
    _write_commit(key, canonical, prev, prev.get("weekly_spent", 0), prev.get("week_anchor", ""),
                  prev.get("ledger", []), "init", "signed current config")
    print("signed.")
    return 0


def main():
    p = argparse.ArgumentParser(prog="nightguard_ctl", description="Nightguard control CLI (root signer).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("ensure-config")
    sub.add_parser("verify")
    sub.add_parser("show")
    c = sub.add_parser("commit")
    c.add_argument("--from", dest="from_path", required=True, help="config file to commit")
    c.add_argument("--rebaseline", action="store_true",
                   help="no-token sanctioned reset (admin) instead of a quota'd commit")
    args = p.parse_args()
    return {"init": cmd_init, "verify": cmd_verify, "show": cmd_show, "commit": cmd_commit,
            "ensure-config": cmd_ensure_config}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
