"""panel.py — the read-only data behind the desktop panel.

Omarchy 4 replaced Waybar with quickshell, so the bar module this project used to
ship has no host any more. The replacement is a standalone quickshell panel, and
this module is everything it renders: a pure function from a verdict, a token
count and the signed config to a flat JSON-able dict.

Read-only is not a style choice here. The project's standing rule is that only
``backend.commit()` may change state, and that any privileged exec or
state-changing click handler from a bar widget is rejected by design. So the
panel is a window, never a lever: it shows what is true and points at the TUI for
anything that changes it.

Like ``status.py`` this computes no HMAC, reads no key, and fails closed -- an
unknown verdict reads as ``locked`` rather than as open.
"""
from __future__ import annotations

from ngtui import status as status_mod


def _hhmm_to_minutes(text):
    """Parse "HH:MM", or None when it is not one."""
    try:
        hours, minutes = str(text).strip().strip('"').split(":")
        h, m = int(hours), int(minutes)
    except (ValueError, AttributeError):
        return None
    if 0 <= h < 24 and 0 <= m < 60:
        return h * 60 + m
    return None


def _in_window(now_minutes, start, end):
    """Membership of [start, end), wrapping past midnight.

    Deliberately duplicated from the signer rather than imported: this module is
    display-only and must not become a second opinion on what the signer decides.
    The signer's copy is what actually gates a commit; a disagreement here shows
    the wrong hour in a panel, it does not let a change through.
    """
    if start == end:
        return False
    if start < end:
        return start <= now_minutes < end
    return now_minutes >= start or now_minutes < end


def edit_window_view(cfg, now_minutes):
    """Whether the curfew may be weakened right now, and when it may next be.

    ``now_minutes`` is None when true time could not be resolved, which reads as
    closed -- the same fail-closed posture the signer takes, so the panel never
    tells the user the window is open when the signer would refuse.
    """
    block = (cfg or {}).get("edit_window")
    if not isinstance(block, dict):
        return {"configured": False, "open": True, "start": None, "end": None,
                "detail": "no edit window configured"}
    start = _hhmm_to_minutes(block.get("start"))
    end = _hhmm_to_minutes(block.get("end"))
    start_text = str(block.get("start") or "").strip('"')
    end_text = str(block.get("end") or "").strip('"')

    if not block.get("enabled"):
        return {"configured": True, "open": True, "start": start_text, "end": end_text,
                "detail": "disabled — the curfew can be weakened at any hour"}
    if start is None or end is None:
        return {"configured": True, "open": False, "start": start_text, "end": end_text,
                "detail": "malformed — weakening refused until it is a valid range"}
    if now_minutes is None:
        return {"configured": True, "open": False, "start": start_text, "end": end_text,
                "detail": "time unverified — weakening refused"}
    if _in_window(now_minutes, start, end):
        return {"configured": True, "open": True, "start": start_text, "end": end_text,
                "detail": "open until %s" % end_text}
    return {"configured": True, "open": False, "start": start_text, "end": end_text,
            "detail": "closed — opens at %s" % start_text}


def blocking_view(cfg):
    """What the curfew blocks, counted rather than listed.

    Counts, not names: the panel sits on the desktop where anyone walking past
    can read it, and the list of what a person blocks themselves from is more
    personal than the fact that they do.
    """
    blocking = (cfg or {}).get("blocking") or {}
    native = blocking.get("native_apps") or {}
    browser = blocking.get("browser_extension") or {}
    mode = str(native.get("mode") or "blocklist").strip().lower()
    if mode != "allowlist":
        mode = "blocklist"
    listed = native.get("allowlist") if mode == "allowlist" else native.get("blacklist")
    return {
        "apps_enabled": bool(native.get("enabled")),
        "mode": mode,
        "games": bool(native.get("block_games")),
        "apps": len(listed or []),
        "sites_enabled": bool(browser.get("enabled")),
        "sites": len(browser.get("blocked_urls") or []),
    }


# Fallbacks used when the desktop theme cannot be read. Omarchy 4's own default
# palette, so an unreadable theme still looks like the desktop rather than like a
# debug screen.
THEME_FALLBACK = {
    "background": "#2d353b",
    "surface": "#343f44",
    "foreground": "#d3c6aa",
    "muted": "#859289",
    "accent": "#7fbbb3",
    "ok": "#a7c080",
    "warn": "#dbbc7f",
    "alert": "#e67e80",
}


def theme_view(tokens):
    """Map the desktop palette onto the roles the panel paints with.

    Every role falls back individually: a theme that ships a partial colors.toml
    should lose one colour, not the whole palette.
    """
    tokens = tokens or {}

    def pick(*names):
        for name in names:
            value = tokens.get(name)
            if isinstance(value, str) and value.startswith("#"):
                return value
        return None

    view = {
        "background": pick("background", "dark_background"),
        "surface": pick("lighter_background", "selection"),
        "foreground": pick("foreground", "bright_foreground"),
        "muted": pick("light_foreground", "muted", "dark_foreground"),
        "accent": pick("accent", "blue", "cyan"),
        "ok": pick("green", "bright_green"),
        "warn": pick("yellow", "bright_yellow"),
        "alert": pick("red", "bright_red"),
    }
    return {k: (v or THEME_FALLBACK[k]) for k, v in view.items()}


def build(verdict, tokens_left, cfg, state, now_minutes=None, warnings=None,
          theme_tokens=None):
    """The whole panel payload. Pure; every input is passed in."""
    from ngtui.backend import WEEKLY_TOKENS

    resolved = verdict if verdict in status_mod._VERDICT_CLASS else "locked"
    glyph, word = status_mod._VERDICT_LABEL[resolved]
    left = max(0, min(WEEKLY_TOKENS, int(tokens_left)))

    return {
        "verdict": resolved,
        "word": word,
        "glyph": glyph,
        "tokens_left": left,
        "tokens_total": WEEKLY_TOKENS,
        "week_anchor": str((state or {}).get("week_anchor") or ""),
        "edit_window": edit_window_view(cfg, now_minutes),
        "blocking": blocking_view(cfg),
        "warnings": list(warnings or []),
        "theme": theme_view(theme_tokens),
    }


UNAVAILABLE = {
    "verdict": "unavailable",
    "word": "UNAVAILABLE",
    "glyph": "○",
    "tokens_left": 0,
    "tokens_total": 0,
    "week_anchor": "",
    "edit_window": {"configured": False, "open": False, "start": None, "end": None,
                    "detail": "the guard could not be reached"},
    "blocking": {"apps_enabled": False, "mode": "blocklist", "games": False, "apps": 0,
                 "sites_enabled": False, "sites": 0},
    "warnings": ["the trust stack could not be read"],
    "theme": dict(THEME_FALLBACK),
}


# --- live warnings -----------------------------------------------------------

def empower_warning(group_line):
    """Warn when the owner has joined the group that neutralises the watchdog.

    ``run0 --empower`` adds a user to the ``empower`` group, after which every
    polkit action returns YES with no prompt -- including the manage-units action
    that the nightguard polkit rule raises to AUTH_ADMIN specifically so that
    stopping the watchdog costs an authentication. Membership silently undoes
    that, so the panel says so out loud.

    Takes the raw group line so the lookup stays out of this pure module.
    """
    if not group_line:
        return None
    try:
        members = group_line.split(":")[3]
    except IndexError:
        return None
    if not members.strip():
        return None
    return ("you are in the 'empower' group — the watchdog can be stopped "
            "without authenticating")
