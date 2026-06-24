"""status.py — the read-only StatusScreen (D-10) and its pure display helpers.

This is the authoritative *read* surface: lock status, countdown, token meter +
weekly reset, grace, config/state hmacs, and the audit ledger — every value sourced
from the guard verdict and the signed state (``backend``), never app-local curfew
math (T-10-05). The TUI holds no key and recomputes no HMAC (PORT-03); displayed
hmacs come verbatim from ``state`` and are truncated for layout (T-10-08).

The load-bearing logic lives in PURE helpers (``verdict_display``, ``token_meter``,
``ledger_rows``) so it unit-tests headless without a running App; the Textual
widgets only compose those helpers. Colour is applied via ``$``-variable role
classes defined in ``app.tcss`` — no hardcoded hex (D-04, omarchy-native).

Accessibility (UI-SPEC "no color alone"): every status carries glyph + word +
colour together, so meaning survives a monochrome terminal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ngtui import backend

WEEKLY_TOKENS = 3

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
        yield Header()
        state = backend.read_state()
        cfg = backend.sanctioned_config()

        if not state or not cfg:
            # Not initialized (guard.json / sanctioned config absent).
            yield Static(
                "nightguard is not initialized on this machine",
                id="not-initialized",
            )
            yield Static("run nightguard_ctl.py init", classes="dim hint")
            yield Footer()
            return

        glyph, word, role, caption = verdict_display(
            backend.live_verdict(cfg, state)
        )

        with Container(id="hero"):
            yield Static(f"{glyph} {word}", id="status-word", classes=role)
            yield Static(self._countdown_text(), id="countdown")
            yield Static(self._hero_caption(cfg, caption), classes="dim", id="hero-caption")

        # Tokens + grace rows.
        with Horizontal(classes="kv-row"):
            yield Static("TOKENS", classes="kv-label")
            yield Static(
                token_meter(backend.tokens_left(), _next_monday(state.get("week_anchor", ""))),
                classes="kv-value",
            )
        with Horizontal(classes="kv-row"):
            yield Static("GRACE", classes="kv-label")
            yield Static(self._grace_text(state), classes="kv-value dim")

        # Integrity panel — non-secret hmacs, dim, truncated.
        with Container(id="integrity", classes="panel"):
            yield Static("integrity", classes="panel-title")
            yield Static(self._integrity_text(state), classes="dim")

        # Audit ledger — read-only, scrollable.
        with VerticalScroll(id="ledger", classes="panel"):
            yield Static("audit ledger", classes="panel-title")
            rows = ledger_rows(state)
            if isinstance(rows, str):
                yield Static(rows, classes="dim")
            else:
                for row in rows:
                    yield Static(row)

        # Advisory caption — the TUI cannot verify hmacs; verdict is advisory.
        yield Static(
            "status reflects what the guard will enforce", classes="dim advisory"
        )
        yield Footer()

    # --- countdown (the only tick-refreshed cell) ---

    def _countdown_text(self) -> str:
        """The hero countdown line. Recomputed each tick; the status word is not."""
        state = backend.read_state()
        cfg = backend.sanctioned_config()
        if not state or not cfg:
            return ""
        verdict = backend.live_verdict(cfg, state)
        if verdict == "grace_active":
            grace = state.get("grace") or {}
            end = grace.get("window_end")
            remaining = self._remaining_to(end)
            return f"{remaining} remaining" if remaining else ""
        if verdict in ("locked", "clock_tamper", "offline_blocked"):
            end = (cfg.get("curfew") or {}).get("end")
            remaining = self._remaining_to_hhmm(end)
            return remaining or ""
        return ""

    def _remaining_to(self, when) -> str:
        """MM:SS (or HH:MM:SS) remaining to an ISO/epoch boundary, "" if unknown."""
        if not when:
            return ""
        try:
            if isinstance(when, (int, float)):
                target = datetime.fromtimestamp(when, tz=timezone.utc)
                now = datetime.now(tz=timezone.utc)
            else:
                target = datetime.fromisoformat(str(when))
                now = datetime.now(tz=target.tzinfo)
        except (ValueError, TypeError, OSError):
            return ""
        delta = target - now
        secs = int(delta.total_seconds())
        if secs <= 0:
            return "00:00"
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def _remaining_to_hhmm(self, end_hhmm) -> str:
        """Countdown to the next occurrence of a ``HH:MM`` curfew-end wall time."""
        if not end_hhmm:
            return ""
        try:
            eh, em = (int(x) for x in str(end_hhmm).split(":"))
        except (ValueError, TypeError):
            return ""
        now = datetime.now()
        target = now.replace(hour=eh, minute=em, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        secs = int((target - now).total_seconds())
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def refresh_countdown(self) -> None:
        """Update ONLY the countdown cell (called from the app's 1s tick).

        The status word, meter, and panels are deliberately NOT re-rendered here —
        they only change on an explicit refresh (UI-SPEC: countdown is the only
        1s-refreshed cell).
        """
        try:
            self.query_one("#countdown", Static).update(self._countdown_text())
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

    def _hero_caption(self, cfg: dict, fixed_caption: str) -> str:
        if fixed_caption:
            return fixed_caption
        end = (cfg.get("curfew") or {}).get("end")
        return f"curfew until {end}" if end else ""

    def _grace_text(self, state: dict) -> str:
        grace = state.get("grace")
        if not grace:
            return "grace unavailable today"
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
