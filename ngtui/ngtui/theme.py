"""theme.py — live omarchy desktop theme → Textual ``Theme`` + change detector.

The TUI is **omarchy-native** (D-02): it does not own a brand palette (the Windows
"Moonlit Indigo" hexes are superseded). Colours are sourced from the live desktop
theme at ``~/.config/omarchy/current/theme/colors.toml`` and parsed into a Textual
``Theme`` (D-04). The running TUI repaints when the desktop theme changes (D-05) —
``ThemeWatch`` is the stdlib mtime-poll primitive driven from the app's 1s tick.

Pure module: stdlib only (``tomllib``, ``json``, ``subprocess``, ``os``) plus
``textual.theme.Theme``, so the loader, the watcher and the whole structural-token
half of the pipeline are unit-testable headless (no App, no TTY). ``style_variables``
is the pure end of it: one dict in, one dict of strings out, no I/O at all.

Role map — per-role **pick chains**, first declared key wins (D-09). Measured over
all 27 installed themes: most declare ``red``/``green``/``yellow`` and no ANSI
``color1/2/3``, so a single-vocabulary map collapsed the three verdict colours into
one. See ``_theme_from_colors`` for the measurement and why the unreached rungs stay.
    accent                  -> Theme.primary + Theme.accent
    background              -> Theme.background
    foreground              -> Theme.foreground
    color1 red urgent       -> Theme.error
    color2 green            -> Theme.success
    color3 yellow orange    -> Theme.warning
    color0 lighter_background selection dark_background background -> Theme.surface
    lighter_background selection surface                           -> Theme.panel

If ``colors.toml`` is absent (some themes ship only ``alacritty.toml`` until
``omarchy-theme-set`` generates one — Pitfall 6) the loader falls back to
``alacritty.toml`` (``[colors.primary]`` + ``[colors.normal]``). On total failure
the caller keeps Textual's default theme rather than crashing (T-10-07, cosmetic).
"""
from __future__ import annotations

import json
import os
import subprocess
import tomllib

from textual.theme import Theme

# Live omarchy theme directories, newest layout first. Omarchy 4 moved the staged
# theme out of ~/.config into ~/.local/state; on a v4 box the old path does not
# exist at all, so a loader pinned to it silently falls through to Textual's
# default theme and the TUI stops matching the desktop. Both are probed so the
# same build works either side of that move.
OMARCHY_THEME_DIRS = (
    "~/.local/state/omarchy/current/theme",  # Omarchy 4
    "~/.config/omarchy/current/theme",       # Omarchy 3 and earlier
)


def theme_dir() -> str | None:
    """The live theme directory, or None when omarchy is not installed.

    Resolved on every call rather than cached at import: omarchy replaces
    ``current/theme`` wholesale on a theme change, and an upgrade can move the
    whole tree between the two locations under a running TUI.
    """
    for candidate in OMARCHY_THEME_DIRS:
        expanded = os.path.expanduser(candidate)
        if os.path.isdir(expanded):
            return expanded
    return None


def colors_path() -> str:
    """Path to the live ``colors.toml`` (the newest layout when none exists)."""
    directory = theme_dir() or os.path.expanduser(OMARCHY_THEME_DIRS[0])
    return os.path.join(directory, "colors.toml")


def alacritty_path() -> str:
    directory = theme_dir() or os.path.expanduser(OMARCHY_THEME_DIRS[0])
    return os.path.join(directory, "alacritty.toml")


def raw_tokens() -> dict:
    """The live theme's colour tokens, straight from ``colors.toml``.

    Separate from ``load_omarchy_theme`` because the desktop panel needs the
    values without Textual: the panel path is head-less and must not pay a UI
    framework's import cost to learn what colour the accent is. Returns {} when
    the theme cannot be read, so the caller can fall back rather than crash.
    """
    try:
        with open(colors_path(), "rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def shell_path() -> str:
    """Path to the live ``shell.toml`` (Omarchy 4's surface/style tokens)."""
    directory = theme_dir() or os.path.expanduser(OMARCHY_THEME_DIRS[0])
    return os.path.join(directory, "shell.toml")


def raw_shell() -> dict:
    """The live ``shell.toml``, or {} when absent (an Omarchy 3 box has none)."""
    try:
        with open(shell_path(), "rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


# Omarchy's own defaults, from shell/Commons/Style.qml. Used per-token when the
# theme does not pin a value, so a partial shell.toml loses one token rather than
# the whole style.
STYLE_DEFAULTS = {
    "popup_background": "#2d353b",
    "popup_text": "#d3c6aa",
    "popup_border": "#7fbbb3",
    "control_border": "#d3c6aa",
    "control_fill_alpha": 0.04,
    "control_border_alpha": 0.4,
    "control_border_width": 1,
    "font_base": 12,
    "spacing_scale": 1.0,
    "spacing_scale_with_font": True,
}


# The [controls] state ladder, in Style.qml's own order. Named once so the parser,
# the defaults table and the $ng-* namespace map cannot drift apart.
CONTROL_RUNGS = ("normal", "hover-cursor", "focus", "selected", "pressed")

# Which rung a rung inherits from when the theme pins nothing for it. Exactly the
# two the design contract (UI-SPEC §2.3) specifies: hover-cursor-color falls back
# to normal-color, and every focus-* token falls back to the *resolved*
# hover-cursor one -- so a theme that moves the cursor rung moves focus with it.
# `selected` and `pressed` are deliberately NOT in here: they carry their own
# constants below, because inheriting them from `normal` would flatten the ladder
# to one fill on any theme that pins only `normal`.
_RUNG_PARENT = {"hover-cursor": "normal", "focus": "hover-cursor"}

# Omarchy's own per-rung numeric defaults (shell/Commons/Style.qml), used per token
# so a partial shell.toml loses one rung's alpha rather than the whole ladder.
# `focus` is None on purpose -- see _RUNG_PARENT. `pressed`'s border row is not in
# UI-SPEC §2.3 (only its fill is); width 0 gives it the selected rung's shape,
# fill-only, which is the conservative reading rather than an invented border.
_RUNG_DEFAULTS = {
    "normal":       {"fill_alpha": 0.04, "border_alpha": 0.40, "border_width": 1},
    "hover-cursor": {"fill_alpha": 0.08, "border_alpha": 0.25, "border_width": 1},
    "focus":        None,
    "selected":     {"fill_alpha": 0.18, "border_alpha": 1.00, "border_width": 0},
    "pressed":      {"fill_alpha": 0.22, "border_alpha": 1.00, "border_width": 0},
}

# Quattro's own [spacing] defaults in px, read off the shipped template
# (/usr/share/omarchy/default/themed/shell.toml.tpl, every token commented out).
# A theme overriding four of them (dos-moos pins xs/md/control-padding-y/
# panel-padding) must lose only those four, which is why this is a table and not a
# scale factor. The px -> cell conversion is the consumer's job (UI-SPEC §4), not
# this parser's: the cell size is a function of the terminal, not of the theme.
SPACING_DEFAULTS = {
    "xxs": 2, "xs": 3, "sm": 4, "md": 6, "lg": 8, "xl": 10, "xxl": 12,
    "xxxl": 14, "huge": 18,
    "control-gap": 8, "control-padding-x": 10, "control-padding-y": 6,
    "input-padding-y": 7, "control-height": 28, "popup-row-height": 28,
    "row-gap": 8, "row-padding-x": 12, "label-gap": 4,
    "panel-gap": 14, "panel-padding": 18, "popup-padding": 14,
    "dropdown-width": 240, "searchable-dropdown-width": 260,
    "number-field-width": 120, "searchable-popup-min-height": 220,
}


def _color_word(value, colors):
    """Resolve a ``[controls]`` colour that is a *word* rather than a hex.

    ``Style.qml:70-75`` (``resolveStateColor`` at ``:115``) lets a ``*-color`` be
    the literal word ``foreground``, ``accent`` or ``urgent``, resolved against
    ``colors.toml``. This is not an edge case: omarchy's generated template writes
    **every** ``[controls]`` colour as ``{{ foreground }}``, and 26 of the 28
    installed themes get that generated file -- so the word is the common path and
    the hex is the exception (city-783, dos-moos).

    Any key the palette declares is accepted, not just those three: the rule is
    "not a hex, so look it up", and a word the palette does not declare returns
    ``None`` so the caller falls back. Returns ``None`` rather than raising, which
    is what keeps a junk value costing one token instead of the whole style.
    """
    text = str(value or "").strip()
    if text.startswith("#"):
        return text if len(text) in (4, 7, 9) else None
    candidate = str((colors or {}).get(text, "") or "").strip()
    if candidate.startswith("#") and len(candidate) in (4, 7, 9):
        return candidate
    return None


def _resolve_border(value, hyprland):
    """Resolve a border token, which may name a Hyprland-derived colour.

    shell.toml writes ``border = "hyprland.active-border"`` rather than a hex
    value, so popups stay aligned with the compositor's active-window border as
    the theme changes. A gradient string is rejected here: the panel paints a
    solid border and half a gradient is worse than the fallback.
    """
    text = str(value or "").strip()
    if text.startswith("hyprland."):
        text = str((hyprland or {}).get(text[len("hyprland."):], "") or "").strip()
    if text.startswith("#") and len(text) in (4, 7, 9):
        return text
    return None


NAME_PATH = "~/.local/state/omarchy/current/theme.name"


def theme_name() -> str:
    """The active theme's name, or "" when it cannot be read.

    Lives OUTSIDE ``current/theme``, which omarchy replaces wholesale on every
    theme change — so this path is stable and is rewritten on each switch. That
    makes it the one reliable change signal: a watch on it survives the directory
    swap that silently drops a watch on anything inside.
    """
    try:
        with open(os.path.expanduser(NAME_PATH), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def theme_mode(tokens=None) -> str:
    """"light" or "dark", as the theme declares itself.

    Five of the installed themes are light. The panel does not derive colours
    from this — it takes Omarchy's own generated surface tokens, which already
    carry the right contrast either way — but a consumer that wants to know
    which way round the world is should not have to guess from a hex value.
    """
    tokens = raw_tokens() if tokens is None else tokens
    return "light" if str((tokens or {}).get("mode", "")).strip().lower() == "light" else "dark"


def omarchy_style(shell: dict | None = None, colors: dict | None = None) -> dict:
    """The structural tokens Omarchy's own popups and controls are built from.

    Colour alone was not enough to make a third-party surface look native: the
    corner radius, the border weight, the translucent control fills and the
    spacing/type scale are what actually carry the family resemblance. Reading
    them here rather than hardcoding means a theme change moves the TUI too.

    ``shell`` / ``colors`` default to the live ``raw_shell()`` / ``raw_tokens()``.
    Passing them is the injection seam ``theme_mode(tokens=None)`` and
    ``load_omarchy_theme(path=None)`` already use in this file: it lets the whole
    structural half of the token pipeline be unit-tested against a fixture with no
    desktop theme on disk, while the zero-argument live behaviour every existing
    caller uses is unchanged.

    The surface colours are taken from the generated ``[popups]`` / ``[tooltip]``
    sections rather than derived from the palette, which is what makes light
    themes work without a second code path: omarchy has already decided what text
    colour reads on what background for that theme, in whichever mode, and this
    inherits that decision instead of re-making it.

    When ``shell.toml`` is absent (an Omarchy 3 box, or a half-staged theme) the
    surface tokens fall back to the palette's own background/foreground/accent —
    the same three omarchy generates them from — rather than to a fixed set,
    because a fixed set is a dark theme's set and would invert a light box. The
    fallback is **per token**: a partial ``shell.toml`` loses one token, never the
    whole style.

    **Sections deliberately NOT consumed**, so a later reader does not wire them
    "for completeness": ``[bar]``, ``[menu]``, ``[launcher]``, ``[lock]``,
    ``[polkit]``, ``[notifications]``, ``[image-picker]``. The TUI is not a bar, a
    menu or a lock screen.

    **Corner radius is here now, and it is the one value that is not a file
    read.** It mirrors Hyprland's ``decoration:rounding``, a live compositor value
    rather than a theme token, so ``hypr_rounding()`` asks hyprctl for it. That
    subprocess is why this function must be called once at construction and once
    per *detected* theme change — never per tick (T-12.1-07).
    """
    shell = raw_shell() if shell is None else shell
    colors = raw_tokens() if colors is None else colors
    popups = shell.get("popups") or {}
    tooltip = shell.get("tooltip") or {}
    controls = shell.get("controls") or shell.get("style") or {}
    hyprland = shell.get("hyprland") or {}
    spacing = shell.get("spacing") or {}
    font = shell.get("font") or {}

    def palette(key):
        value = str((colors or {}).get(key, "") or "").strip()
        return value if value.startswith("#") and len(value) in (4, 7, 9) else None

    # Fall back through the palette before the fixed defaults, so a missing
    # shell.toml still tracks the theme instead of pinning it to a dark one.
    derived = {
        "popup_background": palette("background"),
        "popup_text": palette("foreground"),
        "popup_border": palette("accent"),
        "control_border": palette("foreground"),
    }

    def hexval(section, key, fallback_key):
        value = str(section.get(key, "") or "").strip()
        if value.startswith("#") and len(value) in (4, 7, 9):
            return value
        return derived.get(fallback_key) or STYLE_DEFAULTS[fallback_key]

    def number(section, key, fallback_key):
        try:
            return float(section[key])
        except (KeyError, TypeError, ValueError):
            return STYLE_DEFAULTS[fallback_key]

    def rung_number(rung, suffix, fallback):
        """One ``[controls]`` number, falling back to an already-resolved value.

        Separate from ``number()`` because a rung's fallback is not always a
        constant: ``focus-*`` falls back to the *resolved* ``hover-cursor-*``,
        which is a value and not a ``STYLE_DEFAULTS`` key.
        """
        try:
            return float(controls["%s-%s" % (rung, suffix)])
        except (KeyError, TypeError, ValueError):
            return fallback

    # --- the [controls] state ladder -----------------------------------------
    # Resolved in CONTROL_RUNGS order so a rung can read its parent's *resolved*
    # value rather than re-deriving the chain (UI-SPEC §2.3).
    foreground = derived["control_border"] or STYLE_DEFAULTS["control_border"]
    ladder: dict[str, dict] = {}
    for rung in CONTROL_RUNGS:
        parent = ladder.get(_RUNG_PARENT.get(rung) or "")
        defaults = _RUNG_DEFAULTS[rung] or {}
        raw_border = controls.get("%s-border" % rung)

        color = (
            _color_word(controls.get("%s-color" % rung), colors)
            or (parent or {}).get("color")
            or foreground
        )
        # A *-border may be "hyprland.active-border" (dereferenced, gradient
        # rejected — _resolve_border), a word like "foreground" (the generated
        # template's shape), or absent entirely (dos-moos ships no *-border key
        # at all). Last resort is the rung's own colour, never a fixed hex.
        border = (
            _resolve_border(raw_border, hyprland)
            or _color_word(raw_border, colors)
            or (parent or {}).get("border")
            or color
        )
        fill_alpha = rung_number(
            rung, "fill-alpha",
            defaults.get("fill_alpha", (parent or {}).get("fill_alpha", 0.0)),
        )
        border_alpha = rung_number(
            rung, "border-alpha",
            defaults.get("border_alpha", (parent or {}).get("border_alpha", 0.0)),
        )
        # Clamped to one cell at the point it is read. A character grid has no
        # sub-cell borders and D-05 forbids a state growing the box, so city-783's
        # focus-border-width = 2 must become 1 rather than reflow the row.
        raw_width = rung_number(
            rung, "border-width",
            defaults.get("border_width", (parent or {}).get("border_width", 1)),
        )
        border_width = min(1, max(0, int(raw_width)))

        ladder[rung] = {
            "color": color,
            "border": border,
            "fill_alpha": fill_alpha,
            "border_alpha": border_alpha,
            "border_width": border_width,
        }

    style = {
        "mode": theme_mode(colors),
        "name": theme_name(),
        "popup_background": hexval(popups, "background", "popup_background"),
        "popup_text": hexval(popups, "text", "popup_text"),
        "popup_border": (_resolve_border(popups.get("border"), hyprland)
                         or derived["popup_border"] or STYLE_DEFAULTS["popup_border"]),
        "popup_background_alpha": number(popups, "background-alpha", "spacing_scale"),
        "tooltip_background": hexval(tooltip, "background", "popup_background"),
        "tooltip_text": hexval(tooltip, "text", "popup_text"),
        "tooltip_border": (_resolve_border(tooltip.get("border"), hyprland)
                           or derived["popup_border"] or STYLE_DEFAULTS["popup_border"]),
        "tooltip_background_alpha": number(tooltip, "background-alpha", "spacing_scale"),
        # The three legacy control_* keys panel.style_view reads. Sourced from the
        # resolved `normal` rung rather than re-parsed, so the bar panel and the
        # TUI can never disagree about what the normal rung is.
        "control_border": ladder["normal"]["border"],
        "control_fill_alpha": ladder["normal"]["fill_alpha"],
        "control_border_alpha": ladder["normal"]["border_alpha"],
        "control_border_width": ladder["normal"]["border_width"],
        "corner_radius": hypr_rounding(),
        "font_base": int(number(font, "base-size", "font_base")),
        "spacing_scale": number(spacing, "scale", "spacing_scale"),
        "spacing_scale_with_font": bool(
            spacing.get("scale-with-font", STYLE_DEFAULTS["spacing_scale_with_font"])
        ),
        # Text selection inside an Input — a control-wide token rather than a rung.
        "control_selection_fill_alpha": rung_number("selection", "fill-alpha", 0.35),
    }

    for rung, values in ladder.items():
        prefix = "control_%s" % rung.replace("-", "_")
        for field, value in values.items():
            style["%s_%s" % (prefix, field)] = value

    for token, default in SPACING_DEFAULTS.items():
        try:
            style["spacing_%s" % token.replace("-", "_")] = float(spacing[token])
        except (KeyError, TypeError, ValueError):
            style["spacing_%s" % token.replace("-", "_")] = float(default)

    return style


def hypr_rounding(timeout: float = 0.4) -> int:
    """Hyprland's live ``decoration:rounding``, or 0 when it cannot be asked.

    ``0`` is the safe default, not a guess: square is what the reference aesthetic
    wants and what this box reports. It selects the border-style *family*
    (UI-SPEC §9.2) — at 0 the hairline ``hkey``/``vkey``/``solid`` set, non-zero
    permits ``round``.

    **hyprctl writes its errors to STDOUT with a non-zero return code**, so the
    return code is checked *before* the JSON is parsed. Measured on this box:
    outside Hyprland, ``HYPRLAND_INSTANCE_SIGNATURE not set! (is hyprland
    running?)`` arrives on stdout with rc 1; a stale socket gives rc 4 on stdout.
    Parsing either without the rc check raises ``JSONDecodeError`` — but note what
    that does *not* prove. ``json.JSONDecodeError`` **is a ``ValueError``**, so the
    parse ``except`` below already catches it and the function still returns 0 with
    the rc check deleted (measured 2026-09-13). What the rc check actually buys is
    the case where a failure's stdout *parses*: a non-zero return code means the
    answer is untrustworthy even when it is well-formed JSON, which is T-12.1-08.
    ``test_hypr_rounding_fails_closed``'s mode 4 is the assertion that holds it —
    the other three modes stay green with the check removed.

    Never raises: every failure path returns 0. The exception tuples are the
    narrow ones the rest of this module uses rather than ``except Exception`` —
    that breadth is acceptable for a fire-and-forget side effect (``backend.py``'s
    waybar nudge), not for a value-returning function. Every measured failure mode
    returns in about 10 ms, so ``timeout`` is a ceiling rather than a cost — but
    call this from ``omarchy_style()`` only, which runs once at construction and
    once per *detected* theme change, never per tick (T-12.1-07).
    """
    try:
        out = subprocess.run(
            ["hyprctl", "getoption", "-j", "decoration:rounding"],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError):  # FileNotFoundError, TimeoutExpired
        return 0
    if out.returncode != 0:
        return 0
    try:
        return max(0, int(json.loads(out.stdout).get("int", 0)))
    except (ValueError, TypeError, AttributeError):  # JSONDecodeError is a ValueError
        return 0


# A shell.toml rung's name in the $ng-* namespace. `hover-cursor` is written
# `cursor` there (UI-SPEC §2.3: $ng-fill-cursor), and the TUI's pointer cursor and
# the desktop's hover are the same rung — one cursor, shared (UIX-02).
_RUNG_VARIABLE = {
    "normal": "normal",
    "hover-cursor": "cursor",
    "focus": "focus",
    "selected": "selected",
    "pressed": "pressed",
}

# The six surface variables: $-name -> (style key, STYLE_DEFAULTS key for the last
# resort). Written out rather than generated because UI-SPEC §2.3 is the only
# place these names exist, and the next plan's stylesheet references them by name:
# a variable missing here surfaces as `UnresolvedVariableError: reference to
# undefined variable '$ng-popup-border'` at stylesheet parse, which kills the app
# at compose rather than degrading.
_SURFACE_VARIABLES = (
    ("ng-popup-bg", "popup_background", "popup_background"),
    ("ng-popup-text", "popup_text", "popup_text"),
    ("ng-popup-border", "popup_border", "popup_border"),
    ("ng-tip-bg", "tooltip_background", "popup_background"),
    ("ng-tip-text", "tooltip_text", "popup_text"),
    ("ng-tip-border", "tooltip_border", "popup_border"),
)

# The border styles §9.2 permits. `panel` and `tall` are excluded on purpose:
# `panel` is banned outright (six filled strips on one screen), `tall` is unused
# in 12.1.
BORDER_STYLES = ("hkey", "vkey", "solid", "round")


def style_variables(style: dict) -> dict[str, str]:
    """The style dict → the ``$ng-*`` CSS variable map (UIX-01, the pure half).

    Pure: Textual-free, no file read, no subprocess. One dict in, one flat
    dict of **strings** out — the same shape as ``panel.style_view()``, which is
    the function this copies, including its per-key fallback discipline. Being
    pure is the point: everything the next plan wires into a running App through
    ``get_css_variables()`` is proved here without an App.

    **Alphas and border styles are emitted as bare tokens** (``"4%"``,
    ``"vkey"``, ``"0"``) because Textual substitutes variables at the *token*
    level — measured. So ``app.tcss`` writes
    ``background: $ng-color-normal $ng-fill-normal;`` and it resolves.

    **Colours are emitted resolved**, because two installed themes (city-783,
    dos-moos) pin per-state colours that are not the palette foreground. This is
    the one place the pipeline legitimately handles a hex: it *produces* one from
    the live theme at runtime, which is not the same thing as a hex written into
    ``app.tcss``.

    **Never emit a variable whose value is itself a ``$``-reference.**
    ``v["ng-fill"] = '$foreground 4%'`` fails with ``StylesheetParseError —
    Invalid value ('$foreground') for the background property``: substitution is
    not recursive at that point. That pitfall costs an afternoon, so it is the one
    thing control 3b asserts structurally.

    **The fixed-alpha roles need no variable at all** and are deliberately absent:
    ``$foreground 70%`` / ``50%`` / ``12%`` written directly in ``app.tcss``
    resolves ($ng-text-caption, $ng-text-quiet, $ng-rule). Textual's own
    ``HelpPanel`` stylesheet does exactly this. Do not add them here.

    Border widths are clamped again on the way out even though ``omarchy_style()``
    already clamped them: this function's input is an arbitrary dict, and the
    clamp is a contract of the variable (one cell, D-05) rather than of the parser.
    """
    style = style or {}

    def as_percent(value, fallback):
        try:
            alpha = float(value)
        except (TypeError, ValueError):
            alpha = fallback
        return "%d%%" % int(round(min(1.0, max(0.0, alpha)) * 100))

    def as_color(value, fallback):
        text = str(value or "").strip()
        if text.startswith("#") and len(text) in (4, 7, 9):
            return text
        return fallback

    def as_width(value, fallback):
        try:
            width = int(float(value))
        except (TypeError, ValueError):
            width = fallback
        return str(min(1, max(0, width)))

    variables: dict[str, str] = {}
    for rung, name in _RUNG_VARIABLE.items():
        key = "control_%s" % rung.replace("-", "_")
        defaults = _RUNG_DEFAULTS[rung] or _RUNG_DEFAULTS[_RUNG_PARENT[rung]]
        variables["ng-color-%s" % name] = as_color(
            style.get("%s_color" % key), STYLE_DEFAULTS["control_border"]
        )
        variables["ng-border-%s" % name] = as_color(
            style.get("%s_border" % key), STYLE_DEFAULTS["control_border"]
        )
        variables["ng-fill-%s" % name] = as_percent(
            style.get("%s_fill_alpha" % key), defaults["fill_alpha"]
        )
        variables["ng-border-%s-a" % name] = as_percent(
            style.get("%s_border_alpha" % key), defaults["border_alpha"]
        )
        variables["ng-border-%s-w" % name] = as_width(
            style.get("%s_border_width" % key), defaults["border_width"]
        )

    variables["ng-fill-selection"] = as_percent(
        style.get("control_selection_fill_alpha"), 0.35
    )

    for name, style_key, default_key in _SURFACE_VARIABLES:
        variables[name] = as_color(style.get(style_key), STYLE_DEFAULTS[default_key])

    try:
        radius = max(0, int(style.get("corner_radius", 0) or 0))
    except (TypeError, ValueError):
        radius = 0
    variables["ng-radius"] = str(radius)
    # The radius selects the family, not a hardcoded style (§9.2). At 0 the
    # hairline set; non-zero is the only case where `round` is permitted, and
    # softening halfway — a rounded border plus a hairline frame — is the hybrid
    # the reference explicitly calls a mistake.
    variables["ng-border-style"] = "hkey" if radius == 0 else "round"

    return variables


def _theme_from_colors(c: dict) -> Theme:
    """Build the omarchy ``Theme`` from a parsed ``colors.toml`` dict.

    **The bug this fixes (D-09).** Until now every role was a single
    ``c.get(key, c["accent"])`` over the ANSI key vocabulary only — ``color1`` /
    ``color2`` / ``color3``, falling back to ``accent``. Measured 2026-09-13 by
    loading every installed ``colors.toml`` through this loader: **25 of the 27
    installed themes collapsed ``error``, ``success``, ``warning`` and ``accent``
    to one colour**, because 25 of them declare ``red`` / ``green`` / ``yellow``
    and no ``color1/2/3`` at all. LOCKED, OPEN and GRACE therefore all painted the
    same hue. That inverts the product's accessibility contract — glyph, word and
    colour are supposed to travel together so a monochrome terminal loses nothing,
    and the colour channel was the monochrome one.

    The fix is ``pick()``: per-role chains, first declared key wins, so a theme
    that ships a partial palette loses one colour rather than the whole thing.

    **The later rungs are deliberate insurance, not dead code.** ``urgent``,
    ``orange``, ``selection`` and ``dark_background`` were reached by **none** of
    the 27 themes on this box — every one resolves at ``color1/2/3`` or
    ``red/green/yellow``, and ``surface`` at ``color0`` or ``lighter_background``.
    They are here for a theme that is not on this box. Do not delete them for
    being uncovered.

    ``primary``, ``background``, ``foreground`` and ``accent`` keep their direct
    reads: a ``KeyError`` here is what makes ``load_omarchy_theme`` fall through
    to ``alacritty.toml``, and a chain would swallow it.
    """

    def pick(*names):
        """First name whose value is a ``#``-prefixed colour that parses."""
        for name in names:
            value = c.get(name)
            if not isinstance(value, str):
                continue
            value = value.strip()
            if not value.startswith("#") or len(value) not in (4, 7, 9):
                continue
            try:
                int(value[1:], 16)
            except ValueError:
                continue
            return value
        return None

    accent = c["accent"]
    surface = pick(
        "color0", "lighter_background", "selection", "dark_background", "background"
    ) or c["background"]
    return Theme(
        name="omarchy",
        primary=accent,
        background=c["background"],
        foreground=c["foreground"],
        surface=surface,
        # panel's tail rung is the *resolved* surface, so it is never unset even
        # on a theme declaring neither key.
        panel=pick("lighter_background", "selection", "surface") or surface,
        accent=accent,
        success=pick("color2", "green") or accent,
        warning=pick("color3", "yellow", "orange") or accent,
        error=pick("color1", "red", "urgent") or accent,
        dark=True,
    )


def _theme_from_alacritty(a: dict) -> Theme:
    """Fallback: build the omarchy ``Theme`` from a parsed ``alacritty.toml`` dict.

    Maps the same roles: ``[colors.primary]`` background/foreground and
    ``[colors.normal]`` red/green/yellow (color1/2/3 analogues). The accent role has
    no direct alacritty key, so it borrows ``[colors.normal].blue`` (color4 ==
    omarchy ``accent`` on this box) and finally foreground as a last resort.
    """
    primary = a.get("colors", {}).get("primary", {})
    normal = a.get("colors", {}).get("normal", {})
    foreground = primary.get("foreground", "#d3c6aa")
    background = primary.get("background", "#000000")
    accent = normal.get("blue", foreground)
    # Reuse _theme_from_colors so the role mapping lives in exactly one place.
    return _theme_from_colors(
        {
            "accent": accent,
            "background": background,
            "foreground": foreground,
            "color0": background,
            "color1": normal.get("red", accent),
            "color2": normal.get("green", accent),
            "color3": normal.get("yellow", accent),
        }
    )


def load_omarchy_theme(path: str | None = None) -> Theme:
    """Parse the live omarchy theme into a Textual ``Theme`` named ``"omarchy"``.

    ``path`` overrides the default ``colors.toml`` location (tests pass a fixture).
    When ``colors.toml`` is absent, falls back to ``alacritty.toml`` in the same
    directory (Pitfall 6). Both formats are TOML.
    """
    resolved = path if path is not None else colors_path()
    try:
        with open(resolved, "rb") as fh:
            return _theme_from_colors(tomllib.load(fh))
    except (FileNotFoundError, IsADirectoryError, tomllib.TOMLDecodeError, KeyError):
        # Missing OR malformed (partial write during an atomic dir-swap, Pitfall 6)
        # OR missing a required colour key — fall back to alacritty.toml.
        pass

    # Fall back to alacritty.toml next to the (missing) colors.toml. A malformed
    # alacritty.toml raises TOMLDecodeError here; let it propagate so the app-level
    # handler keeps Textual's default theme rather than crashing (T-10-07).
    fallback = (
        alacritty_path()
        if path is None
        else os.path.join(os.path.dirname(resolved), "alacritty.toml")
    )
    with open(fallback, "rb") as fh:
        return _theme_from_alacritty(tomllib.load(fh))


class ThemeWatch:
    """Live-watch primitive for D-05 repaint-on-theme-change (stdlib mtime poll).

    Watches **both** theme files, ``colors.toml`` and ``shell.toml``. A theme can
    change one without the other — a re-theme that rewrites only the structural
    tokens is a real change the TUI must repaint for, and a watch on the palette
    alone would sleep through it. ``changed()`` re-stats both and returns ``True``
    iff either mtime moved, updating the stored pair so each change fires exactly
    once. Driven from the app's existing 1s tick — no new dependency.

    Missing files stat as 0.0 rather than raising, so an Omarchy 3 box (which ships
    no ``shell.toml``) watches the one file it has and the pair still works.
    """

    def __init__(self, path: str | None = None) -> None:
        self._fixed_path = path
        self._mtimes = self._stat()

    @property
    def path(self) -> str:
        """The ``colors.toml`` being watched.

        Re-resolved on every read, so a theme change that also moves the directory
        (an omarchy 3 to 4 upgrade under a running TUI) is still seen. An mtime
        poll by path is what makes that safe: unlike an inotify watch on the inner
        file, re-stat'ing follows the directory omarchy swapped in — which is the
        property that survives ``omarchy-theme-set`` doing
        ``rm -rf current/theme; mv next-theme current/theme``.

        Kept as the single-path accessor beside ``paths`` because two tests pin it
        by name, and because "which palette file am I on" is a question worth
        being able to ask.
        """
        return self._fixed_path if self._fixed_path is not None else colors_path()

    @property
    def paths(self) -> tuple[str, ...]:
        """Both watched files, re-resolved per read for the reason ``path`` gives.

        When a fixed path is given (tests), its ``shell.toml`` sibling is watched
        too — the two files always live in the same directory, which is precisely
        why omarchy can swap them atomically as one.
        """
        colors = self.path
        if self._fixed_path is None:
            return (colors, shell_path())
        return (colors, os.path.join(os.path.dirname(colors), "shell.toml"))

    def _stat(self) -> tuple[float, ...]:
        mtimes = []
        for path in self.paths:
            try:
                mtimes.append(os.stat(path).st_mtime)
            except OSError:
                mtimes.append(0.0)
        return tuple(mtimes)

    def changed(self) -> bool:
        m = self._stat()
        if m != self._mtimes:
            self._mtimes = m
            return True
        return False
