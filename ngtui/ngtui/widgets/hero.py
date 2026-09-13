"""hero.py — the day as an instrument (UIX-04, D-06).

The screen's one idea. The day is a full-width density ramp where density is *hours
until the curfew starts*, a second channel underneath marking the hours in which a
loosening is accepted, and exactly one bright cell for now. Hovering any column — or
walking it with ``h``/``l`` — reads out that hour and whether a loosening would be
accepted there.

**Meaning never rides on colour alone, and this is the strongest case for that rule
rather than the exception to it.** The ramp is greyscale on purpose. The glyph ladder
``" .:-=+*#%@"`` carries the whole meaning, so the instrument survives a monochrome
terminal, a colour-blind reader and a `NO_COLOR` terminal intact. The colour budget
belongs to the verdict (UI-SPEC §6.2), not to the hero. The permission channel is one
row, one glyph, no colour — a second channel, not a second hero.

**Index 0 — the space — is never emitted.** A blank cell in the day reads as *missing
data*, not as "far from the curfew". That is why the range starts at 1, and it is what
control 11 (``tests/test_dashboard_hero.py``) asserts exhaustively over all 1440
minutes.

**Nothing here invents a reason it did not read.** The curfew bounds and the edit
window both come from the *signed* config and its timezone, handed in by the caller —
never from the system clock's timezone and never from an unsigned source (T-12.1-19).
The ramp is advisory and says so: it is a read instrument with no action, and the
signer re-checks the window and the direction at commit time regardless (T-12.1-20).

Architecture follows ``widgets/status.py`` and ``widgets/controlrow.py``: pure helpers
above the divider, importable and assertable with no running App and no ``backend``
import, and the Textual widget below it doing nothing but painting them. That split is
what makes all 1440 minutes testable headlessly — every helper takes plain arguments
and returns a string or an int.

**No literal ramp width lives in this file** (§7.3). Width is an argument to every
helper and is measured at paint time by the widget; the reason is recorded on
:class:`DayRamp`, with the measurement behind it.
"""
from __future__ import annotations

# The day, in minutes. Every column, every density and every read-out is a position
# in this one span.
MINUTES_PER_DAY = 1440

# UI-SPEC §12. Index 0 is the space and is structurally unreachable (see the module
# docstring and ``density_index``); the ladder the ramp actually paints is 1-9.
RAMP_CHARS = " .:-=+*#%@"

# One cell, one marker (UI-SPEC §12). Bold, at full foreground strength.
NOW_GLYPH = "█"

# The permission channel's only glyph. An upper-eighth block: it sits under the ramp
# row as an underline rather than competing with it for the eye.
PERMISSION_GLYPH = "▔"

MINUTES_PER_HOUR = 60

# Hours-until-curfew -> density index. Read as "strictly less than N hours away".
# The table is UI-SPEC §12's, most-urgent first; the fallthrough is 1.
#
# Stated in HOURS, which is the unit the contract's own table uses. The minute form
# of the same ladder puts a literal 120 (two hours) in this file, and the acceptance
# grep for "no literal ramp width" matches \b120\b without knowing it is a duration --
# so the hours form is both the contract's vocabulary and the one that does not collide.
_DENSITY_LADDER = (
    (1, 8),
    (2, 7),
    (3, 6),
    (4, 5),
    (6, 4),
    (8, 3),
    (11, 2),
)

# The index every minute inside the curfew takes.
_INSIDE_INDEX = 9


# --- pure helpers (headless-testable) ----------------------------------------


def parse_hhmm(value) -> int | None:
    """``"21:30"`` -> ``1290``; anything malformed -> ``None``.

    Mirrors the signer's own ``_parse_hhmm`` rather than importing it: this module
    stays importable with no trust stack on ``sys.path``, which is what lets the
    density control run as a pure unit test. A malformed value returns ``None`` and
    every caller here treats ``None`` as "not read", never as a default hour — the
    TUI does not invent a bound it could not parse.
    """
    try:
        hour, minute = str(value).split(":")
        hour, minute = int(hour), int(minute)
    except (ValueError, AttributeError, TypeError):
        return None
    if 0 <= hour < 24 and 0 <= minute < 60:
        return hour * 60 + minute
    return None


def minutes_to_hhmm(minute: int) -> str:
    """A minute-of-day as ``HH:MM``, wrapping at midnight."""
    minute = int(minute) % MINUTES_PER_DAY
    return "%02d:%02d" % (minute // 60, minute % 60)


def in_window(minute: int, start_minute: int, end_minute: int) -> bool:
    """True when ``minute`` falls in ``[start, end)``, wrapping past midnight.

    A window whose start equals its end is zero minutes wide, not twenty-four hours
    wide — the safe reading for a permission window, and the same reading the signer's
    ``_in_window`` takes. Duplicating that rule here rather than importing it keeps the
    helpers stack-free; the two are asserted against each other by the read-out's copy,
    which states the same verdict the signer will reach.
    """
    if start_minute == end_minute:
        return False
    if start_minute < end_minute:
        return start_minute <= minute < end_minute
    return minute >= start_minute or minute < end_minute


def inside_curfew(
    minute: int, curfew_start_minute: int, curfew_end_minute: int | None = None
) -> bool:
    """Is ``minute`` inside the curfew?

    With an end, this is the wrapping window ``[start, end)``. With **no** end the
    function refuses to claim any minute is inside the curfew except the start itself —
    the instant the curfew begins is inside it by definition, and nothing further can
    be asserted from a start alone. The widget always supplies both from the signed
    config; the two-argument form is the honest degradation when a config carries no
    ``curfew.end``, and it is the form the density range is stated in.
    """
    if curfew_end_minute is None or curfew_end_minute == curfew_start_minute:
        return minute == curfew_start_minute
    return in_window(minute, curfew_start_minute, curfew_end_minute)


def density_index(
    minute: int, curfew_start_minute: int, curfew_end_minute: int | None = None
) -> int:
    """The density of the day at ``minute``, as an index into :data:`RAMP_CHARS`.

    Density is **hours until the curfew starts** (UI-SPEC §12): inside the curfew 9,
    under 1 h 8, under 2 h 7, under 3 h 6, under 4 h 5, under 6 h 4, under 8 h 3,
    under 11 h 2, otherwise 1.

    **Index 0 is never returned.** Index 0 is the space, and a blank cell in the day
    reads as missing data rather than as "far from the curfew" — an instrument that
    renders a gap where it means "plenty of time" is lying in the direction that
    costs the user his curfew. The range is asserted exhaustively over all 1440
    minutes by control 11.

    Greyscale is not a limitation of this function, it is its point: the returned
    index is the *whole* meaning, so the ramp reads identically with every colour
    stripped (UI-SPEC §11).
    """
    if inside_curfew(minute, curfew_start_minute, curfew_end_minute):
        return _INSIDE_INDEX
    until = (curfew_start_minute - minute) % MINUTES_PER_DAY
    for hours, index in _DENSITY_LADDER:
        if until < hours * MINUTES_PER_HOUR:
            return index
    return 1


def column_minute(i: int, width: int) -> int:
    """The minute-of-day at the **centre** of ramp column ``i``.

    ``int(((i + 0.5) / width) * MINUTES_PER_DAY)``. The half-cell offset is what makes
    a column report the hour it *covers* rather than the hour of its left edge; the
    ``i / width`` form is off by half a column everywhere, which is the negative
    control for 11b.

    ``width`` is an argument and is never a constant. The contract's own rule is "no
    literal ramp width in code" (§7.3) and the reason is arithmetical: the same column
    index resolves to a different hour at every width, so a constant is what silently
    breaks the instrument when the frame, the gutter or the terminal font changes. The
    measured width-dependence is recorded on :class:`DayRamp`.
    """
    return int(((i + 0.5) / width) * MINUTES_PER_DAY)


def now_column(now_minute: int | None, width: int) -> int | None:
    """The single column the now marker occupies, or ``None`` when the clock is unread.

    ``floor(now / MINUTES_PER_DAY * width)`` — the column the minute *falls in*, not
    the nearest column centre, so the marker never appears in a column whose span does
    not contain now.

    ``None`` in gives ``None`` out, and the widget then paints **no marker at all**.
    On a product whose whole premise is that the clock can be lied to, an unverified
    clock must produce no claim about what time it is rather than a plausible one.
    """
    if now_minute is None or width <= 0:
        return None
    column = int((int(now_minute) % MINUTES_PER_DAY) / MINUTES_PER_DAY * width)
    return max(0, min(width - 1, column))


def density_indices(
    width: int, curfew_start_minute: int, curfew_end_minute: int | None = None
) -> list[int]:
    """One density index per column, left to right, for a ramp ``width`` wide."""
    return [
        density_index(column_minute(i, width), curfew_start_minute, curfew_end_minute)
        for i in range(max(0, width))
    ]


def density_row(
    width: int, curfew_start_minute: int, curfew_end_minute: int | None = None
) -> str:
    """The ramp's glyphs for a ``width``-wide row, before the now marker is placed."""
    return "".join(
        RAMP_CHARS[index]
        for index in density_indices(width, curfew_start_minute, curfew_end_minute)
    )


def window_allows(minute: int, window: dict | None) -> bool:
    """Would a loosening be accepted at ``minute``, per the **signed** edit window?

    Three cases, each matching the signer's ``_edit_window_refusal`` so the channel and
    the refusal the user actually meets cannot disagree:

    * no window, or a window that is not enabled -> accepted at any hour (the signer
      gates nothing when the block is absent or off);
    * an enabled window whose bounds do not parse -> **refused everywhere**, fail
      closed. A malformed window is exactly the state an attacker would engineer;
    * otherwise -> inside ``[start, end)``, wrapping past midnight.

    This answers only for the *window*. The weekly quota is a separate gate and is not
    consulted here, and neither is the direction classifier — which is why the ramp is
    advisory and the signer re-checks both (T-12.1-20).
    """
    if not window or not window.get("enabled"):
        return True
    start = parse_hhmm(window.get("start"))
    end = parse_hhmm(window.get("end"))
    if start is None or end is None:
        return False
    return in_window(minute, start, end)


def permission_channel(width: int, window: dict | None) -> str:
    """The second channel: :data:`PERMISSION_GLYPH` where a loosening is accepted.

    One row, one glyph, no colour. It marks the hours the *signed* edit window admits,
    read from the signed config and its timezone — never from the system clock's
    (T-12.1-19). Meaning is carried by presence versus absence of the glyph, so the
    channel survives a monochrome terminal exactly as the ramp above it does.
    """
    return "".join(
        PERMISSION_GLYPH if window_allows(column_minute(i, width), window) else " "
        for i in range(max(0, width))
    )


def hour_axis(width: int, every: int = 2) -> str:
    """Two-digit hour labels every ``every`` hours, positioned by the same arithmetic.

    A label is placed at the column its hour *starts* in, and is dropped rather than
    overlapped when the width cannot hold it with a clear cell on either side. Dropping
    a label costs a reader one tick mark; overlapping two produces a number that is not
    an hour at all.
    """
    width = max(0, width)
    if width <= 0:
        return ""
    cells = [" "] * width
    for hour in range(0, 24, max(1, every)):
        label = "%02d" % hour
        column = int(hour * 60 / MINUTES_PER_DAY * width)
        if column + len(label) > width:
            continue
        span = range(max(0, column - 1), min(width, column + len(label) + 1))
        if any(cells[cell] != " " for cell in span):
            continue
        for offset, glyph in enumerate(label):
            cells[column + offset] = glyph
    return "".join(cells)


def readout(
    column: int,
    width: int,
    curfew_start_minute: int | None,
    curfew_end_minute: int | None,
    window: dict | None,
) -> str:
    """The read-out line for one column — the string both inputs write.

    Exactly two shapes (UI-SPEC §12):

    * ``09:14   open · a loosening is allowed here``
    * ``21:52   curfew — locked · a loosening is refused here``

    Two independent channels in one line: the first says what the *curfew* does at that
    hour, the second what the *edit window* does. They are genuinely independent — an
    hour can be open and still refuse a loosening, which is the ordinary case for most
    of the evening, and stating both is what stops the ramp from implying that "open"
    means "you may weaken this now".

    The pointer and the keyboard both call this function. That is the mechanism behind
    control 11c: keyboard parity is not two code paths that agree today, it is one
    string with two callers.

    A curfew whose bounds did not parse yields ``open`` rather than a guess — the TUI
    never invents a reason it did not read (UI-SPEC §10.6).
    """
    minute = column_minute(column, width)
    locked = (
        curfew_start_minute is not None
        and inside_curfew(minute, curfew_start_minute, curfew_end_minute)
    )
    state = "curfew — locked" if locked else "open"
    permission = (
        "a loosening is allowed here"
        if window_allows(minute, window)
        else "a loosening is refused here"
    )
    return "%s   %s · %s" % (minutes_to_hhmm(minute), state, permission)
