"""status.py — the read-only StatusScreen (D-10) and its pure display helpers.

This is the authoritative *read* surface: lock status, countdown, token meter +
weekly reset, grace, config/state hmacs, and the audit ledger — every value sourced
from the guard verdict and the signed state (``backend``), never app-local curfew
math (T-10-05). The TUI holds no key and recomputes no HMAC (PORT-03); displayed
hmacs come verbatim from ``state`` and are truncated for layout (T-10-08).

The load-bearing logic lives in PURE helpers (``verdict_display``, ``token_meter``,
``ledger_rows``, ``tracked``, ``verdict_caption``, ``verdict_meta``,
``duration_words``) so it unit-tests headless without a running App; the Textual
widgets only compose those helpers. Colour is applied via ``$``-variable role
classes defined in ``app.tcss`` — no hardcoded hex (D-04, omarchy-native).

**The composition is a device frame, not a stack of boxes** (UI-SPEC §7.1). One
root ``#frame`` carries four per-edge hairlines and a 2-column inner gutter; every
region below it is separated by a ``Rule`` keyline and one blank row, and **no
region draws its own outline**. That is what replaces the six drawn rectangles this
screen used to have, and it is why nothing else here needs a box.

**Exactly one region is flexible** — the audit ledger, ``height: 1fr``, the screen's
only scroller. Everything else is a fixed row height, which is what makes UI-SPEC
§7.2's 46-row budget checkable rather than hopeful.

**No framework chrome** (D-16, OD-2). Textual's ``Header`` and ``Footer`` are both
gone. The bindings the Footer used to print are unaffected — they are owned by
``NightguardApp`` and by this screen, and the Footer only *rendered* the legend.
Discoverability moves to the ``help`` chip, which opens Textual's own ``HelpPanel``.
No bracket hint appears anywhere on this composition.

**Every changeable value is a ``ControlRow``** built from ``home_controls()``'s
16-stop registry, in the registry's order, which is also the cursor order (UIX-03,
UI-SPEC §8.6). The registry is the single source of both what a row says and where
the cursor goes; this module composes it and routes its two messages, and decides
nothing about what may be edited.

Accessibility (UI-SPEC "no color alone"): every status carries glyph + word +
colour together, so meaning survives a monochrome terminal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dataclasses import replace

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Digits, Rule, Static

from ngtui import backend
from ngtui.backend import WEEKLY_TOKENS  # signer's constant (WR-03), never a local literal
from ngtui.theme import theme_name
from ngtui.widgets.controlrow import ControlRow, home_controls, read_dotted
from ngtui.widgets.hero import DayRamp, window_allows

# Verdict string -> (glyph, word, colour_role, caption). Glyph + word + colour are
# always present together (UI-SPEC Accessibility). Colour role is a $-variable name.
_VERDICT_MAP: dict[str, tuple[str, str, str, str]] = {
    "locked": ("●", "LOCKED", "error", ""),
    "outside_curfew": ("○", "OPEN", "success", ""),
    "grace_active": ("◐", "GRACE", "accent", ""),
    "clock_tamper": ("●", "LOCKED", "error", "clock tamper detected — locked"),
    "offline_blocked": (
        "●",
        "LOCKED",
        "error",
        "time unverified — guard keeps the house closed",
    ),
}


# --- pure helpers (headless-testable) ----------------------------------------


def verdict_display(verdict: str) -> tuple[str, str, str, str]:
    """Map a guard verdict string to ``(glyph, word, colour_role, caption)``.

    Unknown verdicts fail closed to LOCKED (never optimistically OPEN — T-10-05).
    The caption for ``locked`` ("curfew until HH:MM") is filled in by the widget,
    which has the config; tamper/offline carry their fixed captions here.
    """
    return _VERDICT_MAP.get(verdict, _VERDICT_MAP["locked"])


def _next_monday(week_anchor: str) -> str:
    """The upcoming Monday the weekly tokens reset on, as ``YYYY-MM-DD``.

    ``week_anchor`` is the current week's Monday (``ngcommon`` STATE_FIELDS); the
    reset is the following Monday (anchor + 7 days). Falls back to today's week if
    the anchor is missing/garbled, so the caption never crashes the read surface.
    """
    try:
        anchor = datetime.strptime(week_anchor, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        today = datetime.now().date()
        anchor = today - timedelta(days=today.weekday())
    return (anchor + timedelta(days=7)).isoformat()


def token_meter(tokens_left: int, week_monday: str) -> str:
    """Render the 3-glyph token meter + reset caption.

    ``tokens_left`` filled ``●`` glyphs then ``WEEKLY_TOKENS - tokens_left`` hollow
    ``○`` glyphs (filled = available, hollow = spent), space-separated, followed by
    the caption ``N of 3 left · resets Mon YYYY-MM-DD``. The meter reads as
    filled-vs-hollow even with no colour (UI-SPEC Accessibility).
    """
    left = max(0, min(WEEKLY_TOKENS, tokens_left))
    glyphs = ["●"] * left + ["○"] * (WEEKLY_TOKENS - left)
    meter = " ".join(glyphs)
    return f"{meter}   {left} of {WEEKLY_TOKENS} left · resets Mon {week_monday}"


def _ledger_date(ntp_timestamp) -> str:
    """Format a ledger entry's NTP unix timestamp as ``YYYY-MM-DD HH:MM`` (UTC)."""
    try:
        dt = datetime.fromtimestamp(int(ntp_timestamp), tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        return "????-??-?? ??:??"


def ledger_rows(state: dict) -> list[str] | str:
    """Render the audit ledger as read-only rows, or the empty-state string.

    Empty/absent ``state["ledger"]`` → ``"no audit entries yet"``. Otherwise one
    row per entry: ``"<date>   <comma-joined field labels>"`` from the stored
    ``{ntp_timestamp, fields}`` entries (built by the signer's ``cmd_commit``).
    Most-recent-first.
    """
    ledger = state.get("ledger") or []
    if not ledger:
        return "no audit entries yet"
    rows: list[str] = []
    for entry in reversed(ledger):
        date = _ledger_date(entry.get("ntp_timestamp"))
        fields = ", ".join(entry.get("fields", []) or []) or "(no fields)"
        rows.append(f"{date}   {fields}")
    return rows


#: UI-SPEC §10.1's six section labels, and the ONLY strings on this surface that
#: carry tracking. Tracking is emulated by interleaving spaces because Textual has
#: no ``letter_spacing`` property (enumerated on the installed package), and it
#: costs ``2n - 1`` cells — which is affordable on six short labels and nowhere
#: else. Held as a tuple so the row budget's "six tracked labels" is countable.
SECTION_LABELS = (
    "THE DAY",
    "STATE",
    "THIS WEEK",
    "BLOCKING",
    "INTEGRITY",
    "AUDIT LEDGER",
)


def tracked(label: str) -> str:
    """A section label with one space of tracking. Section labels only (UI-SPEC §5).

    Letters within a word are separated by one space and words by two, so
    ``AUDIT LEDGER`` reads as two words rather than one long run — which is what
    single-spacing everything would produce. Costs ``2n - 1`` cells per word.
    """
    return "  ".join(" ".join(word) for word in label.split())


def duration_words(seconds: int) -> str:
    """``7H 38M`` / ``18M 32S`` — the meta line's duration, uppercase (UI-SPEC §10.2).

    Two units, never three: the contract's own examples are ``7H 38M REMAINING``
    and ``18M 32S REMAINING``, so hours suppress seconds and minutes show them.
    A non-positive duration is ``0M``, not a negative — the guard decides when a
    window closes, and a countdown that ran past zero must not claim negative time.
    """
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return "%dH %dM" % (hours, minutes)
    return "%dM %dS" % (minutes, secs)


def verdict_caption(verdict: str, fixed: str, curfew_end: str, window_open: bool) -> str:
    """The verdict's caption, exactly UI-SPEC §10.2's table.

    ``fixed`` is whatever ``verdict_display`` already carries — the tamper and
    offline captions, which are properties of the verdict and not of the config.
    When it is set it wins, unchanged. The other three are filled here because they
    need the config (``curfew_end``) or the signed edit window (``window_open``),
    which the map deliberately does not have.

    An unknown verdict falls through to the ``locked`` caption, matching
    ``verdict_display``'s own fail-closed default: the two must not disagree about
    what state the screen is in.
    """
    if fixed:
        return fixed
    if verdict == "outside_curfew":
        return "the clock window is open" if window_open else "house open, window shut"
    if verdict == "grace_active":
        return "daily bypass running"
    return "curfew until %s" % curfew_end if curfew_end else ""


def verdict_meta(
    verdict: str,
    *,
    remaining_seconds: int | None = None,
    curfew_start: str = "",
    window_end: str = "",
    window_open: bool = False,
) -> str:
    """The uppercase meta line that travels with the verdict (UI-SPEC §10.2).

    Glyph, word, role, caption and this line are one unit — the contract lists them
    in one row of one table for that reason, and a surface that shows four of the
    five is a surface where one channel can quietly disagree with the rest.

    Pure: every input is handed in. ``remaining_seconds`` is ``None`` when the
    screen could not compute one, and the line then drops the duration rather than
    printing a guess.
    """
    if verdict == "clock_tamper":
        return "CLOCK TAMPER · LOCKED"
    if verdict == "offline_blocked":
        return "TIME UNVERIFIED · LOCKED"
    if verdict == "grace_active":
        if remaining_seconds is None:
            return "GRACE · RUNNING"
        return "GRACE · %s REMAINING" % duration_words(remaining_seconds)
    if verdict == "outside_curfew":
        if window_open and window_end:
            return "OPEN · MAY WEAKEN UNTIL %s" % window_end
        if curfew_start:
            return "OPEN · CURFEW STARTS %s" % curfew_start
        return "OPEN"
    # locked, and every unknown verdict — fail closed, same as verdict_display.
    if remaining_seconds is None:
        return "CURFEW · LOCKED"
    return "CURFEW · %s REMAINING" % duration_words(remaining_seconds)


def header_meta(theme: str, tz: str, clock: str) -> str:
    """``{theme} · {signed tz} · {HH:MM}`` — UI-SPEC §10.1's header right.

    The timezone is the **signed** one, read from the sanctioned config, never the
    system's. A screen that printed the box's timezone beside a curfew the signer
    evaluates in another one would be describing a different day than the guard is.

    An unreadable theme name degrades to the two remaining segments rather than to
    an empty one — the separator carries no information on its own.
    """
    return " · ".join(part for part in (theme, tz, clock) if part)


# --- Textual widgets (compose the pure helpers) ------------------------------


class StatusScreen(Screen):
    """The read-only home surface (D-10).

    Pulls every value from ``backend`` (verdict + signed state + lazy-reset token
    count); applies colour via ``$``-variable role classes from ``app.tcss``. The
    countdown ``Static#countdown`` is the ONLY cell the app refreshes on the 1s
    tick — ``refresh_countdown()`` updates it without re-rendering the status word
    (UI-SPEC: avoid flicker / false reflow). Handles the not-initialized case with
    a full-screen message rather than a broken hero.
    """

    BINDINGS = [
        ("e", "edit", "Edit a field"),
        ("r", "refresh", "Refresh"),
        ("l", "ledger", "Ledger"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """The 46-row budget of UI-SPEC §7.2, composed top-down.

        Read order matters and is not incidental: every value is pulled from
        ``backend`` **once, here**, and handed down to the regions. Nothing below
        re-reads the guard, so no two cells on one paint can disagree about the
        verdict (T-12.1-24), and no region can cache a value across a repaint —
        ``action_refresh`` replaces the whole screen rather than patching it.
        """
        state = backend.read_state()
        cfg = backend.sanctioned_config()

        if not state or not cfg:
            # Not initialized (guard.json / sanctioned config absent). A full-screen
            # message rather than a frame around a hero with nothing in it.
            yield Static(
                "nightguard is not initialized on this machine",
                id="not-initialized",
            )
            yield Static("run nightguard_ctl.py init", classes="dim hint")
            return

        paint = self._read(cfg, state)

        with Container(id="frame"):
            yield from self._header(paint)                      # row 2
            yield Rule()                                        # row 3
            yield Static("", classes="blank")                   # row 4
            yield from self._section("THE DAY", paint["caption"])  # row 5
            yield Static("", classes="blank")                   # row 6

            # Rows 7-10 — the hero. Four rows of one instrument, the last of them
            # the reserved read-out, so hovering it costs no reflow (UIX-05). It is
            # never dropped by any degradation class: it is the screen's one idea.
            yield DayRamp(
                cfg=cfg,
                window=paint["window"],
                now_minutes=paint["now_minutes"],
                id="ctl-ramp",
            )
            yield Static("", classes="blank")                   # row 11

            yield from self._band(paint)                        # rows 12-17
            yield Static("", classes="blank")                   # row 18

            yield Rule()                                        # row 19
            yield from self._blocking(paint)                    # rows 20-29
            yield Static("", classes="blank")                   # row 30

            yield Rule()                                        # row 31
            yield from self._integrity(paint)                   # rows 32-33
            yield Static("", classes="blank")                   # row 34

            yield from self._ledger(paint)                      # rows 35-42
            yield Static("", classes="blank")                   # row 43

            yield from self._chips(paint)                       # row 44

            # Row 45. Verbatim, and load-bearing: the TUI cannot verify an HMAC and
            # holds no key, so every verdict on this screen is advisory. The line
            # says which side of that boundary the reader is on.
            yield Static(
                "status reflects what the guard will enforce", classes="dim advisory"
            )

    #: UI-SPEC §8.6 stops 4-11 — the eight blocking rows, in cursor order. Named
    #: rather than sliced out of the registry by index: a slice silently renders
    #: the wrong eight the day a stop is inserted, and this list going stale is a
    #: KeyError at compose instead.
    BLOCKING_KEYS = (
        "app-blocking",
        "mode",
        "blocked-apps",
        "always-allowed",
        "game-blocking",
        "site-blocking",
        "blocked-sites",
        "enforcement",
    )

    #: UI-SPEC §8.6 stops 12-16 — the chip strip, in cursor order.
    CHIP_KEYS = (
        "chip-edit",
        "chip-ledger",
        "chip-refresh",
        "chip-help",
        "chip-quit",
    )

    def _blocking(self, paint: dict) -> ComposeResult:
        """Rows 20-29. The label, a blank, then the eight blocking rows.

        Rendered straight from the registry, so what a row *says* and where the
        cursor *goes* have one source. Four of the eight carry a refusal instead of
        a route and state it on the row — the refusal is the contract's copy and is
        not paraphrased here.

        The read-only notice on the right is **counted from the registry**, not
        typed. A typed "4 of these" goes stale the moment 12.2 turns one refusal
        into a route, and it goes stale silently.
        """
        controls = paint["controls"]
        refused = sum(1 for key in self.BLOCKING_KEYS if controls[key].is_refused)
        yield from self._section(
            "BLOCKING", "%d of these are read-only" % refused, role="dim"
        )
        yield Static("", classes="blank")
        for key in self.BLOCKING_KEYS:
            yield ControlRow(controls[key])

    def _integrity(self, paint: dict) -> ComposeResult:
        """Rows 32-33. The label with the watchdog time, and the truncated hmacs.

        The hmacs are non-secret and come verbatim from ``state``; the TUI holds no
        key and recomputes nothing (PORT-03, T-10-08). They are truncated for
        layout only.

        ``watchdog`` degrades to ``never`` when the fact was not read, matching what
        the ``enforcement`` row's own detail says — one degradation, rendered the
        same in both places. ``never`` is also the fail-closed direction: with no
        record of a tick, the honest claim is that none was seen.
        """
        facts = paint["facts"]
        yield from self._section(
            "INTEGRITY", "watchdog %s" % (facts.get("watchdog") or "never"), role="dim"
        )
        yield Static(self._integrity_text(paint["state"]), id="integrity", classes="dim")

    def _ledger(self, paint: dict) -> ComposeResult:
        """Rows 35-42. The label, then the screen's ONLY ``1fr`` region and scroller.

        Fixed rows total 39, so at 135 x 46 the ledger gets 7 against a stated
        minimum of 4. **Those three rows of slack are the seam for 12.2** — it needs
        a hairline, one more row and a blank, and it takes them from here with the
        budget still holding at 4.

        Nothing is drawn for edits that cannot be staged yet. A permanent row saying
        the tray is empty would be a claim that a tray exists, and on this surface in
        this phase it does not (T-12.1-27).

        ``ledger_rows`` is the carried-forward pure helper and is the EMPTINESS
        signal here — it returns a string for empty and a list otherwise. The copy
        the surface shows for empty is UI-SPEC §10.6's two lines, not the helper's
        one-line sentinel, because the helper's exact output is pinned by
        ``tests/test_status.py`` and is not the contract's wording.
        """
        yield from self._section("AUDIT LEDGER")
        with VerticalScroll(id="ledger"):
            rows = ledger_rows(paint["state"])
            if isinstance(rows, str):
                yield Static("no commit has been signed yet", classes="dim")
                yield Static(
                    "every accepted change lands here with its hour", classes="dim"
                )
            else:
                for row in rows:
                    yield Static(row)

    def _chips(self, paint: dict) -> ComposeResult:
        """Row 44. Five chips, generated from the registry, exactly one of them filled.

        ``edit`` is the primary and inverts to ``$background`` on ``$foreground`` —
        **not** to the accent. The accent reserve is a closed two-item list and a
        chip is not on it.

        Each chip carries the name of an action that already exists on the app.
        This plan adds none: ``edit`` opens the existing ``EditScreen``, whose
        confirm gate before a signed commit is untouched (T-12.1-25).
        """
        controls = paint["controls"]
        with Horizontal(id="chips"):
            for key in self.CHIP_KEYS:
                yield ControlRow(controls[key])

    # --- the two messages a row may post ---

    async def on_control_row_activated(self, message: ControlRow.Activated) -> None:
        """A reachable control was activated. Route it; decide nothing.

        A chip runs its named action through the app's own action dispatch, so the
        chip and the key binding reach one implementation rather than two.

        A **routed row** opens the existing editor. It does not yet open it *on* its
        field: ``EditScreen.__init__`` takes no argument, and giving it one is new
        editing capability in a file this plan does not own. The route rides on the
        stop and is what 12.2 will hand over; carrying it unused is the seam, and it
        is deliberately not routed around here.
        """
        control = message.model
        if control.action:
            await self.app.run_action(control.action)
            return
        if control.route:
            await self.app.run_action("edit")

    def on_control_row_refused(self, message: ControlRow.Refused) -> None:
        """A frozen control was activated. Surface the reason and stop.

        The reason is already ON the row — a refusal the user has to hover to find
        is a refusal he does not have at the moment he is deciding whether the app
        is lying to him. This repeats it where the pointer just was, because a click
        that appears to do nothing is indistinguishable from a broken control.

        Nothing here decides anything. What refuses a weakening is the signer.
        """
        if message.reason:
            self.app.notify(message.reason, severity="warning")

    # --- the read, done once ---

    def _read(self, cfg: dict, state: dict) -> dict:
        """Every value the composition needs, read from ``backend`` in one place.

        Returned as a plain dict rather than kept on the screen. A region that
        reached back into ``backend`` for its own copy is how a token count and a
        verdict rendered in the same frame end up describing different moments.
        """
        verdict = backend.live_verdict(cfg, state)
        glyph, word, role, fixed = verdict_display(verdict)
        window = backend.edit_window()
        now_minutes = backend.cache_only_now_minutes(cfg)
        window_open = (
            window_allows(now_minutes, window) if now_minutes is not None else False
        )
        curfew = cfg.get("curfew") or {}
        remaining = self._remaining_seconds(verdict, cfg, state)
        facts = self._machine_facts(cfg)
        controls = {
            control.key: control for control in home_controls(cfg, facts)
        }
        return {
            "cfg": cfg,
            "state": state,
            "facts": facts,
            "verdict": verdict,
            "glyph": glyph,
            "word": word,
            "role": role,
            "window": window,
            "now_minutes": now_minutes,
            "window_open": window_open,
            "remaining": remaining,
            "controls": controls,
            "caption": verdict_caption(
                verdict, fixed, curfew.get("end") or "", window_open
            ),
            "meta": verdict_meta(
                verdict,
                remaining_seconds=remaining,
                curfew_start=curfew.get("start") or "",
                window_end=(window or {}).get("end") or "",
                window_open=window_open,
            ),
        }

    def _machine_facts(self, cfg: dict) -> dict:
        """What the machine knows that the config does not — as far as it is READ.

        ``home_controls(cfg, facts)`` takes nine optional keys: ``enforcement``,
        ``watchdog``, ``games``, ``game_blocking``, ``browsers``,
        ``policy_restored``, ``blocked_sites``, ``always_allowed`` and
        ``unmatched_apps``. Exactly **one** of them has a read in this phase.

        ``blocked_sites`` is not a machine fact at all — it is
        ``blocking.browser_extension.blocked_urls``, a signed config key
        (``nightguard_ctl.py`` FIELD_TABLE), so it is read from the config the
        caller already has.

        The other eight have **no reader**, and this plan's stop condition forbids
        adding one to ``backend.py``. They are therefore left unsupplied, and
        ``home_controls`` degrades each to its own documented honest default: an
        empty list reads as the finding it is, and ``enforcement`` falls to
        ``WEAK``. That default is deliberately pessimistic — claiming STRONG on an
        unread fact is the one direction this product may never fail in.

        **What is NOT done here, on purpose:** the ``WEAK MODE`` alarm tag in the
        header is raised only when ``enforcement`` was actually supplied and read
        weak, never by the unread default. "Enforcement is weak" and "enforcement
        was not read" are different claims, and only the first earns an alarm — an
        alarm that is always on is an alarm nobody reads on the night it is true.
        """
        return {
            "blocked_sites": read_dotted(cfg, "blocking.browser_extension.blocked_urls")
            or [],
        }

    # --- the regions ---

    def _header(self, paint: dict) -> ComposeResult:
        """Row 2. Wordmark + the accent dot, the meta, and the alarm tag if it applies.

        ``theme_name()`` is called **here, at paint time**, and is deliberately not
        cached on the screen. ``omarchy-theme-set`` writes ``theme.name`` about
        440 ms *after* it renames the theme directory, so a watcher that fires on
        the theme files can read the previous name — and then keep showing it
        forever, because it has already consumed the event. Re-reading on every
        paint is what makes that self-healing rather than sticky.
        """
        with Horizontal(id="header"):
            yield Static("󰂲 NIGHTGUARD", id="wordmark")
            # Accent reserve item (a), one of exactly two permitted places.
            yield Static("●", id="wordmark-dot")
            yield Static(
                header_meta(
                    theme_name(),
                    # The SIGNED timezone, straight off the config this paint
                    # already read — not `backend._tzname` (a private) and not the
                    # system's. The guard evaluates the curfew in this zone; a
                    # header printing another one would describe a different day.
                    str((paint["cfg"] or {}).get("timezone") or ""),
                    datetime.now().strftime("%H:%M"),
                ),
                id="header-meta",
            )
            if self._weak_mode(paint):
                yield Static(" WEAK MODE ", id="weak-tag")

    @staticmethod
    def _weak_mode(paint: dict) -> bool:
        """Is the enforcement mode KNOWN to be weak? Unread is not weak (see above)."""
        facts = paint.get("facts") or {}
        return str(facts.get("enforcement", "")).upper() == "WEAK"

    def _section(self, label: str, right: str = "", role: str = "dim") -> ComposeResult:
        """One section-label row: the tracked label left, its caption right.

        The six labels in :data:`SECTION_LABELS` are the only tracked strings on the
        surface; :func:`tracked` is called here so no caller can track anything else
        by accident.
        """
        assert label in SECTION_LABELS, (
            "%r is not one of the six tracked section labels — tracking is permitted "
            "for those only (UI-SPEC §5)" % label
        )
        with Horizontal(classes="section"):
            yield Static(tracked(label), classes="section-label")
            yield Static(right, classes="section-right %s" % role)

    def _band(self, paint: dict) -> ComposeResult:
        """Rows 12-17. ``S T A T E`` | keyline | ``T H I S  W E E K``, split 62 | 1 | 1fr.

        The two stops that live in the band — ``curfew`` (stop 2) and ``may weaken``
        (stop 3) — are rendered as ``ControlRow``s from the registry, so the whole
        row is the click target and the cursor walks them in registry order like
        every other control (UIX-03).

        Their **detail** cells are filled here, with ``dataclasses.replace``. The
        registry is pure and has no verdict, no clock and no remaining time; the
        contract's ``CURFEW · 7H 38M REMAINING`` meta line and the window's
        ``open now`` / ``shut now`` are exactly that. Key, order, route and refusal
        are untouched, so the 12.2 seam is unaffected.
        """
        state = paint["state"]
        controls = paint["controls"]

        with Horizontal(id="band"):
            with Vertical(id="state-col"):
                yield from self._section("STATE")
                with Horizontal(classes="kv-row verdict-row"):
                    # Glyph, word, colour and caption travel together, always.
                    yield Static(
                        "%s %s" % (paint["glyph"], paint["word"]),
                        id="status-word",
                        classes=paint["role"],
                    )
                    yield Static(paint["caption"], classes="dim", id="hero-caption")
                # The screen's one `display`-mass element, and the THIN set: a
                # `text-style: bold` here switches Textual to DIGITS3X3_BOLD, which
                # reads as terminal art rather than as the desktop this imitates.
                # Its character set includes `:`, so HH:MM:SS is safe.
                yield Digits(
                    self._countdown_text(), id="countdown", classes=paint["role"]
                )
                yield ControlRow(
                    replace(controls["curfew"], detail=paint["meta"])
                )

            yield Rule(orientation="vertical")

            with Vertical(id="week-col"):
                yield from self._section("THIS WEEK")
                with Horizontal(classes="kv-row"):
                    yield Static("tokens", classes="kv-label")
                    yield Static(
                        token_meter(
                            backend.tokens_left(),
                            _next_monday(state.get("week_anchor", "")),
                        ),
                        classes="kv-value",
                    )
                yield ControlRow(
                    replace(
                        controls["may-weaken"],
                        detail="open now" if paint["window_open"] else "shut now",
                        detail_role="success" if paint["window_open"] else "error",
                    )
                )
                with Horizontal(classes="kv-row"):
                    yield Static("grace", classes="kv-label")
                    yield Static(self._grace_text(state), classes="kv-value dim")
                yield Static("", classes="blank")

    # --- countdown (the only tick-refreshed cell) ---

    def _remaining_seconds(self, verdict: str, cfg: dict, state: dict) -> int | None:
        """Seconds left on whatever boundary this verdict is counting down to.

        ONE source for both the ``Digits`` countdown and the meta line's
        ``7H 38M REMAINING``. They are two renderings of one number, and computing
        it twice is how they come to disagree by a second and read as a glitch.

        ``None`` when there is nothing to count — an open house is not counting
        down to anything, and neither is a boundary that could not be parsed.
        """
        if verdict == "grace_active":
            grace = state.get("grace") or {}
            return self._seconds_to(grace.get("window_end"))
        if verdict in ("locked", "clock_tamper", "offline_blocked"):
            return self._seconds_to_hhmm((cfg.get("curfew") or {}).get("end"))
        return None

    @staticmethod
    def _hhmmss(seconds: int | None) -> str:
        """``HH:MM:SS`` for the ``Digits`` cell — always three fields, never two.

        Digits renders at a fixed cell width per glyph, so a countdown that dropped
        the hours field at 59:59 would change the element's WIDTH mid-tick. The
        reserved shape is what keeps the one tick-refreshed cell from reflowing its
        neighbours (UIX-05).
        """
        if seconds is None:
            return ""
        seconds = max(0, int(seconds))
        hours, rest = divmod(seconds, 3600)
        minutes, secs = divmod(rest, 60)
        return "%02d:%02d:%02d" % (hours, minutes, secs)

    def _countdown_text(self) -> str:
        """The countdown cell's text. Recomputed each tick; the status word is not."""
        state = backend.read_state()
        cfg = backend.sanctioned_config()
        if not state or not cfg:
            return ""
        verdict = backend.live_verdict(cfg, state)
        return self._hhmmss(self._remaining_seconds(verdict, cfg, state))

    def _seconds_to(self, when) -> int | None:
        """Seconds remaining to an ISO/epoch boundary, ``None`` when unreadable."""
        if not when:
            return None
        try:
            if isinstance(when, (int, float)):
                target = datetime.fromtimestamp(when, tz=timezone.utc)
                now = datetime.now(tz=timezone.utc)
            else:
                target = datetime.fromisoformat(str(when))
                now = datetime.now(tz=target.tzinfo)
        except (ValueError, TypeError, OSError):
            return None
        return max(0, int((target - now).total_seconds()))

    def _seconds_to_hhmm(self, end_hhmm) -> int | None:
        """Seconds to the next occurrence of a ``HH:MM`` curfew-end wall time."""
        if not end_hhmm:
            return None
        try:
            eh, em = (int(x) for x in str(end_hhmm).split(":"))
        except (ValueError, TypeError):
            return None
        now = datetime.now()
        target = now.replace(hour=eh, minute=em, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return max(0, int((target - now).total_seconds()))

    def refresh_countdown(self) -> None:
        """Update ONLY the countdown cell (called from the app's 1s tick).

        The status word, meter, and panels are deliberately NOT re-rendered here —
        they only change on an explicit refresh (UI-SPEC: countdown is the only
        1s-refreshed cell).
        """
        try:
            # Queried WITHOUT a type: the cell is a `Digits`, and pinning the type
            # here would turn a composition change into a silent `except Exception`
            # rather than a visible one.
            self.query_one("#countdown").update(self._countdown_text())
        except Exception:
            # Not-initialized screen has no countdown cell — nothing to tick.
            pass

    def toggle_ledger(self) -> None:
        """Expand ↔ collapse the ledger panel (the only collapsible region)."""
        try:
            panel = self.query_one("#ledger", VerticalScroll)
        except Exception:
            return
        panel.toggle_class("collapsed")

    # --- caption / value builders ---

    def _grace_text(self, state: dict) -> str:
        """GRACE row text. Only claims "active" while the window is still open (WR-05).

        The signer writes ``state["grace"]`` when grace is activated and leaves it in
        place (with ``window_end``) until the next daily reset, so a truthy dict does
        NOT imply an open window. Cross-reference ``window_end`` against now(UTC); once
        it is in the past the window is used, not active.
        """
        grace = state.get("grace")
        if not grace:
            return "grace unavailable today"
        end = grace.get("window_end")
        if end is not None:
            try:
                target = datetime.fromtimestamp(float(end), tz=timezone.utc)
                if target <= datetime.now(tz=timezone.utc):
                    return "grace used today"
            except (ValueError, TypeError, OSError):
                pass
        return "◐ grace active"

    def _integrity_text(self, state: dict) -> str:
        return (
            f"config_hmac  {_truncate_hmac(state.get('config_hmac', ''))}"
            f"      state_hmac  {_truncate_hmac(state.get('state_hmac', ''))}"
        )


def _truncate_hmac(h: str) -> str:
    """Truncate a hex hmac for layout (display-only, non-secret — T-10-08)."""
    if not h:
        return "—"
    if len(h) <= 12:
        return h
    return f"{h[:8]}…{h[-4:]}"
