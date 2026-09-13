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
                "start_minutes": -1, "end_minutes": -1,
                "detail": "no edit window configured"}
    start = _hhmm_to_minutes(block.get("start"))
    end = _hhmm_to_minutes(block.get("end"))
    start_text = str(block.get("start") or "").strip('"')
    end_text = str(block.get("end") or "").strip('"')

    if not block.get("enabled"):
        return {"configured": True, "open": True, "start": start_text, "end": end_text,
                "start_minutes": start if start is not None else -1,
                "end_minutes": end if end is not None else -1,
                "detail": "disabled — the curfew can be weakened at any hour"}
    if start is None or end is None:
        return {"configured": True, "open": False, "start": -1, "end": -1,
                "start_minutes": -1, "end_minutes": -1,
                "detail": "malformed — weakening refused until it is a valid range"}
    if now_minutes is None:
        return {"configured": True, "open": False, "start": start_text, "end": end_text,
                "start_minutes": start, "end_minutes": end,
                "detail": "time unverified — weakening refused"}
    if _in_window(now_minutes, start, end):
        return {"configured": True, "open": True, "start": start_text, "end": end_text,
                "start_minutes": start, "end_minutes": end,
                "detail": "open until %s" % end_text}
    return {"configured": True, "open": False, "start": start_text, "end": end_text,
            "start_minutes": start, "end_minutes": end,
            "detail": "closed — opens at %s" % start_text}


def curfew_view(cfg):
    """The curfew band, as minutes, for the panel's day strip.

    The panel draws a 24-hour bar with the curfew shaded and the edit window
    marked, which is the one picture that answers "when am I locked and when may
    I change it" without reading a word. That needs the bounds as numbers, not as
    the "HH:MM" strings the rest of the payload carries.
    """
    curfew = (cfg or {}).get("curfew") or {}
    start = _hhmm_to_minutes(curfew.get("start"))
    end = _hhmm_to_minutes(curfew.get("end"))
    return {
        "enabled": bool(curfew.get("enabled")),
        "start": str(curfew.get("start") or "").strip('"'),
        "end": str(curfew.get("end") or "").strip('"'),
        "start_minutes": start if start is not None else -1,
        "end_minutes": end if end is not None else -1,
    }


def blocking_view(cfg, resolution=None):
    """What the curfew blocks, named and -- where known -- resolved.

    This used to emit counts only, to keep the list of what a person blocks
    themselves from off a screen a passer-by can read. The owner weighed that
    against a panel that says "2" and cannot tell him WHICH two, and chose
    names: a count cannot show that an entry matches nothing, and an entry that
    matches nothing is a pact that silently is not kept.

    ``resolution`` maps an entry to ``{"state": ..., "label": ...}`` and is
    computed outside this pure function (see ``__main__._app_resolution``).
    ``state`` is what this machine answers with -- "running", "installed" or
    "unmatched". ``label`` is the human name of the desktop entry that resolves
    to the same binary, when exactly one does, so the panel can say "Steam"
    while the config still says "steam". An entry absent from the map, or a
    ``resolution`` of None, reports ``None`` for both: not read is not the same
    as fine, and the panel draws it as an em dash rather than guessing in
    either direction.
    """
    blocking = (cfg or {}).get("blocking") or {}
    native = blocking.get("native_apps") or {}
    browser = blocking.get("browser_extension") or {}
    mode = str(native.get("mode") or "blocklist").strip().lower()
    if mode != "allowlist":
        mode = "blocklist"
    listed = native.get("allowlist") if mode == "allowlist" else native.get("blacklist")
    names = [str(e).strip() for e in (listed or []) if str(e).strip()]
    urls = [str(u).strip() for u in (browser.get("blocked_urls") or []) if str(u).strip()]
    return {
        "apps_enabled": bool(native.get("enabled")),
        "mode": mode,
        "games": bool(native.get("block_games")),
        "apps": len(listed or []),
        "entries": [
            {
                "name": n,
                "label": ((resolution or {}).get(n) or {}).get("label"),
                "state": ((resolution or {}).get(n) or {}).get("state"),
            }
            for n in names
        ],
        "sites_enabled": bool(browser.get("enabled")),
        "sites": len(browser.get("blocked_urls") or []),
        "site_entries": urls,
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


def _rgb(value):
    text = str(value or "").lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) < 6:
        return None
    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _luminance(value):
    """Relative luminance, as defined for the WCAG contrast ratio."""
    rgb = _rgb(value)
    if rgb is None:
        return None
    channels = []
    for raw in rgb:
        c = raw / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """Contrast ratio between two colours, or None if either is unreadable."""
    la, lb = _luminance(a), _luminance(b)
    if la is None or lb is None:
        return None
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _dimmer_than(candidates, foreground, background, floor=2.0):
    """The most legible candidate that is still dimmer than the body text.

    Chosen by measurement rather than by name, because the palette's names
    describe absolute lightness, not contrast. ``light_foreground`` is genuinely
    the lighter of the two foregrounds — which on tokyo-night and osaka-jade
    makes it *brighter* than the body text and therefore the opposite of muted,
    while on everforest it happens to be dimmer and on a light theme like
    flexoki-light it is dimmer again for the opposite reason. One fixed order
    cannot be right for all of them; measuring is right for all of them.
    """
    body = contrast(foreground, background)
    if body is None:
        return None
    best, best_ratio = None, None
    for value in candidates:
        ratio = contrast(value, background)
        if ratio is None or ratio < floor or ratio >= body:
            continue
        if best_ratio is None or ratio > best_ratio:
            best, best_ratio = value, ratio
    return best


def theme_view(tokens):
    """Map the desktop palette onto the roles the panel paints with.

    Every role falls back individually: a theme that ships a partial colors.toml
    should lose one colour, not the whole palette.

    Roles that are a straight rename are picked by name. ``muted`` is not one of
    those — see ``_dimmer_than`` — so it is measured against the background and
    the body text, which is what makes one rule serve both light and dark themes.
    """
    tokens = tokens or {}

    def pick(*names):
        for name in names:
            value = tokens.get(name)
            if isinstance(value, str) and value.startswith("#") and _rgb(value):
                return value
        return None

    background = pick("background", "dark_background")
    foreground = pick("foreground", "bright_foreground")

    candidates = [c for c in (pick("light_foreground"), pick("dark_foreground"),
                              pick("muted"), pick("selection")) if c]
    muted = _dimmer_than(candidates, foreground, background)

    view = {
        "background": background,
        "surface": pick("lighter_background", "selection"),
        "foreground": foreground,
        # Never invisible: a palette with no dimmer tone reads body text instead
        # of something that disappears into the background.
        "muted": muted or foreground,
        "accent": pick("accent", "blue", "cyan"),
        "ok": pick("green", "bright_green"),
        "warn": pick("yellow", "bright_yellow"),
        "alert": pick("red", "bright_red"),
    }
    return {k: (v or THEME_FALLBACK[k]) for k, v in view.items()}


# Omarchy's own structural defaults, mirrored from shell/Commons/Style.qml so an
# Omarchy 3 box (which ships no shell.toml) still renders in the family style
# rather than falling back to something invented.
STYLE_FALLBACK = {
    "mode": "dark",
    "name": "",
    "popup_background": "#2d353b",
    "popup_text": "#d3c6aa",
    "popup_border": "#7fbbb3",
    "popup_background_alpha": 1.0,
    "control_border": "#d3c6aa",
    "control_fill_alpha": 0.04,
    "control_border_alpha": 0.4,
    "control_border_width": 1,
    "font_base": 12,
    "spacing_scale": 1.0,
    "spacing_scale_with_font": True,
}


# Style tokens that are plain text rather than colours. Everything else in
# STYLE_FALLBACK that is a string is a hex value and is validated as one.
_STYLE_TEXT_KEYS = frozenset({"mode", "name"})


def style_view(tokens):
    """The structural tokens the panel is built from, each with its own fallback.

    Colour alone did not make the panel look native. What carries the family
    resemblance is the rest: a hairline border at 40% over a 4% fill instead of a
    lighter solid card, a 2px popup border in the compositor's active-border
    colour, and a spacing/type scale derived from one base font size.

    Corner radius is deliberately not here. It mirrors Hyprland's
    ``decoration:rounding`` -- a live compositor value, not a theme file -- so the
    panel asks hyprctl for it and gets sharp corners on a box configured for them.
    """
    tokens = tokens or {}
    out = {}
    for key, fallback in STYLE_FALLBACK.items():
        value = tokens.get(key)
        if isinstance(fallback, bool):
            out[key] = bool(value) if isinstance(value, bool) else fallback
        elif key in _STYLE_TEXT_KEYS:
            # Plain strings, not colours. Validating these as hex silently
            # dropped every light theme's "light" back to the "dark" default.
            out[key] = value if isinstance(value, str) and value.strip() else fallback
        elif isinstance(fallback, str):
            out[key] = value if isinstance(value, str) and value.startswith("#") else fallback
        else:
            try:
                out[key] = type(fallback)(value)
            except (TypeError, ValueError):
                out[key] = fallback
    return out


def build(verdict, tokens_left, cfg, state, now_minutes=None, warnings=None,
          theme_tokens=None, style_tokens=None, app_resolution=None):
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
        "curfew": curfew_view(cfg),
        # -1 when the clock could not be verified: the strip then draws no "now"
        # marker rather than putting one at midnight.
        "now_minutes": now_minutes if now_minutes is not None else -1,
        "blocking": blocking_view(cfg, app_resolution),
        "warnings": list(warnings or []),
        "theme": theme_view(theme_tokens),
        "style": style_view(style_tokens),
    }


UNAVAILABLE = {
    "verdict": "unavailable",
    "word": "UNAVAILABLE",
    "glyph": "○",
    "tokens_left": 0,
    "tokens_total": 0,
    "week_anchor": "",
    "edit_window": {"configured": False, "open": False, "start": None, "end": None,
                    "start_minutes": -1, "end_minutes": -1,
                    "detail": "the guard could not be reached"},
    "curfew": {"enabled": False, "start": "", "end": "",
               "start_minutes": -1, "end_minutes": -1},
    "now_minutes": -1,
    "blocking": {"apps_enabled": False, "mode": "blocklist", "games": False, "apps": 0,
                 "entries": [], "sites_enabled": False, "sites": 0, "site_entries": []},
    "warnings": ["the trust stack could not be read"],
    "theme": dict(THEME_FALLBACK),
    "style": dict(STYLE_FALLBACK),
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
