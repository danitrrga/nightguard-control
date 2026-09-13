"""controlrow.py — the row model, the home-surface registry, and ``ControlRow``.

The home surface has exactly one cursor. Omarchy's own kit builds it out of two
pieces that must be kept in step by hand — ``hot = containsMouse || hasCursor``
in ``Ui/Button.qml`` plus a ``hovered(bool)`` signal that
``plugins/panels/monitor/Panel.qml`` binds to its keyboard cursor. In Textual the
cursor **is** focus, so ``on_enter`` calling ``self.focus()`` gives the same
guarantee with one model instead of two, and two models are how a pointer and a
keyboard end up disagreeing (D-02, UIX-02).

The anti-pattern this replaces is in this codebase already: ``EditScreen`` keeps an
integer index beside Textual focus and repaints a "focused" class from it
(``widgets/edit.py:508-517``). That index is a second cursor. It is not ported here,
and nothing in this module keeps position state of its own — the position lives in
Textual, or it does not exist.

Architecture follows ``widgets/status.py``: pure helpers above the divider,
importable and assertable with no running App, and Textual widgets below it that do
nothing but compose them. Control 6c runs entirely above the divider.

**Colour reaches this module as a role NAME, never a value** (D-12/UIX-06). A row
carries ``value_role`` / ``detail_role`` strings such as ``"error"``; the widget puts
them on as CSS classes and ``app.tcss`` decides what they paint. That is the
mechanism that makes the hex ban enforceable by a file scan, and this file is in
``tests/test_no_fixed_hex.py``'s glob.

**Meaning never rides on colour alone** (UI-SPEC §11). ``on``/``off`` is two cells,
reverse-video filled versus hollow, *plus* the word — reverse video is an attribute
rather than a colour, so it survives a monochrome terminal. A refused row drops its
value to the quiet channel **and** states the reason on the row. An empty list reads
as a gap, never as "nothing to show": ``no site is blocked`` in the alarm role with
the consequence spelled out beside it, because the list being empty *is* the finding.

**The seam this file exists to keep open.** Every stop is one immutable shape,
``(label, value, detail, route | refusal)``. A ``route`` is a dotted config key handed
to the existing edit surface; a ``refusal`` is a string. A stop has exactly one of the
two and never both — enforced in ``Control.__post_init__`` so it cannot be written
wrong, and asserted over the built registry so it cannot be *built* wrong. Those are
two layers and removing either one alone leaves an end-to-end check green, so
``tests/test_dashboard_rows.py`` asserts both. Phase 12.2's whole job on this surface
is turning four ``refusal``s into ``route``s: one field per row, with no change to this
widget, the paint ladder or the row budget.

**A refusal here is presentation, not enforcement** (T-12.1-15). The row says the
sanctioned editor cannot reach the key yet. What actually refuses a weakening is the
signer — its direction classifier and its edit window — and none of that is reachable
from this module. Nothing here decides whether a change is allowed, and nothing here
writes anything.

Route keys are read out of ``EDITABLE_FIELDS`` (``widgets/edit.py:216``) and validated
against it. This phase adds no editing capability: the set of editable fields is
exactly what it was, and a route that is not in that vocabulary is a construction
error rather than a silently dead row.
"""
from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.events import Click, Leave, MouseDown, MouseUp
from textual.message import Message
from textual.widgets import Static

from ngtui.widgets.edit import EDITABLE_FIELDS

# --- pure helpers (headless-testable) ----------------------------------------

#: The contract's verbatim copy for a key the sanctioned editor cannot reach yet
#: (UI-SPEC §10.6). One constant, so the four frozen rows cannot drift apart from
#: each other and 12.2 deletes one name rather than hunting four strings.
FROZEN_REFUSAL = "unreachable — the only sanctioned editor cannot change this yet"

#: The dotted-key vocabulary, READ from the edit surface and not extended.
ROUTE_VOCABULARY = frozenset(dotted for _label, dotted, _kind in EDITABLE_FIELDS)

#: How long a keyboard activation paints the pressed rung. Matches the fill
#: transition in ``app.tcss`` (120 ms, ``ColorAnimation { duration: 120 }``), so the
#: rung is visible for exactly as long as the cross-fade that reveals it.
PRESS_FLASH = 0.12


@dataclass(frozen=True)
class Control:
    """One stop on the home surface: ``(label, value, detail, route | refusal)``.

    Frozen because a stop is rebuilt on every paint rather than mutated — a row that
    caches its own value across a repaint is how a stale verdict survives a refresh
    (T-12.1-17).

    ``route`` and ``refusal`` are mutually exclusive and that is checked here, at the
    only place a stop can come into existence. ``kind`` is ``"row"`` or ``"chip"``;
    a stop with neither a route nor a refusal nor an action activates to nothing,
    which is the honest state for a read instrument (the ramp) and for machine state
    the config does not own (enforcement).
    """

    key: str
    label: str
    value: str = ""
    detail: str = ""
    route: str | None = None
    refusal: str | None = None
    value_role: str = ""
    detail_role: str = ""
    tooltip: str = ""
    action: str | None = None
    kind: str = "row"
    primary: bool = False
    selected: bool = False

    def __post_init__(self) -> None:
        if self.route and self.refusal:
            raise ValueError(
                "%s carries both a route (%s) and a refusal (%r) — the seam stays a "
                "one-field swap for 12.2 only while exactly one of the two is set"
                % (self.key, self.route, self.refusal)
            )
        if self.route and self.route not in ROUTE_VOCABULARY:
            raise ValueError(
                "%s routes to %r, which is not in the editable vocabulary %s — this "
                "phase reads that list and does not extend it, so a route outside it "
                "would render as reachable and then reach nothing"
                % (self.key, self.route, sorted(ROUTE_VOCABULARY))
            )

    @property
    def seam(self) -> tuple[str | None, str | None]:
        """``(route, refusal)`` — the whole seam as one tuple, for one comparison."""
        return (self.route, self.refusal)

    @property
    def is_refused(self) -> bool:
        return bool(self.refusal)


def switch_display(on: bool) -> str:
    """``on``/``off`` as two cells — filled versus hollow — plus the word.

    Reverse video, not colour: it is a terminal *attribute*, so the distinction
    survives a monochrome terminal and a colour-blind reader both, which is what
    UI-SPEC §11 asks of every state on this surface.
    """
    return "[reverse]  [/] on" if on else "▏▕ off"


def segmented_display(options: tuple[str, ...], chosen: str) -> str:
    """A segmented control: every option shown, the chosen one inverted.

    The unchosen option stays legible rather than being hidden, because the point of
    the ``mode`` row is that a stricter option exists and is not reachable yet.
    """
    cells = []
    for option in options:
        cells.append("[reverse] %s [/]" % option if option == chosen else option)
    return " ▏ ".join(cells)


def entry_list(items: list[str] | tuple[str, ...] | None, empty: str) -> str:
    """The items joined, or ``empty`` — never a dash and never "no items".

    An empty list is a finding, not an absence: the caller supplies the sentence that
    says what the emptiness *costs*, and the caller also pairs it with the alarm role.
    """
    values = [str(item) for item in (items or []) if str(item).strip()]
    return ", ".join(values) if values else empty


def entry_count(items: list[str] | tuple[str, ...] | None) -> str:
    """``N entries ▸`` — the right-hand count that says the row expands."""
    return "%d entries ▸" % len(items or [])


def read_dotted(cfg: dict, dotted: str):
    """Read a nested config value by dotted path; ``None`` when any segment is absent."""
    cursor = cfg
    for segment in dotted.split("."):
        if not isinstance(cursor, dict) or segment not in cursor:
            return None
        cursor = cursor[segment]
    return cursor


def _span(cfg: dict, start_key: str, end_key: str, absent: str) -> str:
    start = read_dotted(cfg, start_key)
    end = read_dotted(cfg, end_key)
    if not start or not end:
        return absent
    return "%s–%s" % (start, end)


_RAMP_TOOLTIP = (
    "density is hours until the curfew · the underline marks the hours a loosening "
    "is accepted · the bright cell is now"
)
_MODE_TOOLTIP = (
    "blocklist ends only the apps named.\n"
    "allowlist ends everything except them — stricter, and free."
)
_ALWAYS_ALLOWED_TOOLTIP = (
    "a floor protects the compositor, the shell, the portals, pipewire, the keyring "
    "and every terminal — config cannot shrink it."
)
_ENFORCEMENT_TOOLTIP = {
    "STRONG": (
        "apps are moved into a root-owned cgroup you cannot escape, and the tree is "
        "killed in one write."
    ),
    "WEAK": (
        "the jail cgroup could not be built, so the tick fell back to SIGTERM.\n"
        "anything that forks between the scan and the signal survives."
    ),
}
_GAME_TOOLTIP_HEAD = (
    "auto-detected from Steam appmanifests, Heroic's installed files and any desktop "
    "entry declaring Categories=Game, matched by install path."
)
_GAME_TOOLTIP_TAIL = "turning it ON is a tightening and is free."
# The one escalation on the surface, said before it happens rather than after.
_EDIT_CHIP_TOOLTIP = "runs the signer under sudo — the prompt appears inline"

_CHIPS: tuple[tuple[str, str, str, bool, str], ...] = (
    ("chip-edit", "edit", "edit", True, _EDIT_CHIP_TOOLTIP),
    ("chip-ledger", "ledger", "ledger", False, ""),
    ("chip-refresh", "refresh", "refresh", False, ""),
    ("chip-help", "help", "show_help_panel", False, ""),
    ("chip-quit", "quit", "quit", False, ""),
)


def _game_tooltip(games: list[str] | tuple[str, ...] | None) -> str:
    lines = [_GAME_TOOLTIP_HEAD, ""]
    for title in games or []:
        lines.append("  %s" % title)
    lines.append("")
    lines.append(_GAME_TOOLTIP_TAIL)
    return "\n".join(lines)


def home_controls(cfg: dict, facts: dict | None = None) -> tuple[Control, ...]:
    """The ordered control list for the home surface — 16 stops, 4 of them refused.

    Pure: ``cfg`` is the parsed sanctioned config and ``facts`` is what the machine
    knows that the config does not (enforcement mode, detected games, browser count,
    which blacklist entries match nothing). Both are read by the caller through
    ``backend``'s existing public reads and handed in, so this function is assertable
    with no App, no trust stack and no live guard state (T-12.1-01), and so no stop
    can cache a value across a repaint (T-12.1-17).

    The order is UI-SPEC §8.6's table and is the cursor order. Four stops — ``mode``,
    ``always allowed``, ``game blocking`` and ``blocked sites`` — carry a refusal
    instead of a route because the sanctioned editor cannot reach those keys yet. The
    ramp is a read instrument and ``enforcement`` is machine state, so both activate
    to nothing; neither is refused, because there is nothing there to refuse.
    """
    cfg = cfg or {}
    facts = facts or {}

    blacklist = read_dotted(cfg, "blocking.native_apps.blacklist") or []
    unmatched = [str(name) for name in (facts.get("unmatched_apps") or [])]
    always_allowed = list(facts.get("always_allowed") or [])
    games = list(facts.get("games") or [])
    blocked_sites = list(facts.get("blocked_sites") or [])
    enforcement = str(facts.get("enforcement") or "WEAK").upper()
    game_blocking_on = bool(facts.get("game_blocking"))

    apps_detail = "%s · %s" % (
        ", ".join("%s matches nothing" % name for name in unmatched),
        entry_count(blacklist),
    ) if unmatched else entry_count(blacklist)

    if game_blocking_on:
        game_value = "on · %d covered" % len(games)
        game_detail = "%d titles detected" % len(games)
        game_detail_role = ""
    else:
        game_value = "off"
        game_detail = "%d titles installed, covered by nothing" % len(games)
        game_detail_role = "error" if games else ""

    site_detail_bits = []
    if facts.get("policy_restored"):
        site_detail_bits.append("policy restored %s" % facts["policy_restored"])
    if facts.get("browsers") is not None:
        site_detail_bits.append("%d browsers" % int(facts["browsers"]))

    enforcement_detail = "%s · watchdog %s" % (
        "/sys/fs/cgroup/nightguard" if enforcement == "STRONG" else "SIGTERM fallback",
        facts.get("watchdog") or "never",
    )

    controls = (
        Control(
            key="ramp",
            label="the day ramp",
            tooltip=_RAMP_TOOLTIP,
        ),
        Control(
            key="curfew",
            label="curfew",
            value=_span(cfg, "curfew.start", "curfew.end", "unset"),
            route="curfew.start",
        ),
        Control(
            key="may-weaken",
            label="may weaken",
            value=_span(cfg, "edit_window.start", "edit_window.end", "unset"),
            route="edit_window.start",
        ),
        Control(
            key="app-blocking",
            label="app blocking",
            value=switch_display(bool(read_dotted(cfg, "blocking.native_apps.enabled"))),
            detail="ends the named apps while the curfew holds",
            route="blocking.native_apps.enabled",
        ),
        Control(
            key="mode",
            label="mode",
            value=segmented_display(("blocklist", "allowlist"), "blocklist"),
            detail="stricter option available",
            refusal=FROZEN_REFUSAL,
            tooltip=_MODE_TOOLTIP,
        ),
        Control(
            key="blocked-apps",
            label="blocked apps",
            value=entry_list(blacklist, "no app is blocked"),
            value_role="" if blacklist else "error",
            detail=apps_detail,
            detail_role="error" if unmatched else "",
            route="blocking.native_apps.blacklist",
        ),
        Control(
            key="always-allowed",
            label="always allowed",
            value=entry_list(always_allowed, "the floor only"),
            detail=entry_count(always_allowed),
            refusal=FROZEN_REFUSAL,
            tooltip=_ALWAYS_ALLOWED_TOOLTIP,
        ),
        Control(
            key="game-blocking",
            label="game blocking",
            value=game_value,
            detail=game_detail,
            detail_role=game_detail_role,
            refusal=FROZEN_REFUSAL,
            tooltip=_game_tooltip(games),
        ),
        Control(
            key="site-blocking",
            label="site blocking",
            value=switch_display(
                bool(read_dotted(cfg, "blocking.browser_extension.enabled"))
            ),
            detail=" · ".join(site_detail_bits),
            route="blocking.browser_extension.enabled",
        ),
        Control(
            key="blocked-sites",
            label="blocked sites",
            value=entry_list(blocked_sites, "no site is blocked"),
            value_role="" if blocked_sites else "error",
            detail="%s · the browser policy has nothing to enforce" % entry_count(
                blocked_sites
            ) if not blocked_sites else entry_count(blocked_sites),
            refusal=FROZEN_REFUSAL,
        ),
        Control(
            key="enforcement",
            label="enforcement",
            value="[reverse] %s [/]" % enforcement,
            detail=enforcement_detail,
            tooltip=_ENFORCEMENT_TOOLTIP.get(enforcement, _ENFORCEMENT_TOOLTIP["WEAK"]),
        ),
    ) + tuple(
        Control(
            key=key,
            label=label,
            kind="chip",
            action=action,
            primary=primary,
            tooltip=tooltip,
        )
        for key, label, action, primary, tooltip in _CHIPS
    )
    return controls


# --- Textual widgets (compose the pure helpers) ------------------------------


class ControlRow(Static, can_focus=True):
    """One control on the home surface. The whole row is the target, for both inputs.

    ``on_enter`` calls ``self.focus()``: the pointer moves the keyboard cursor, so the
    highlight the pointer paints and the one the keyboard walks are the same object.
    There is no index, no shadow position and nothing to keep in step (D-02, UIX-02).

    ``Enter`` and ``Space`` activate the row, which comes free with focus and mirrors
    ``onReturnPressed`` / ``onEnterPressed`` / ``onSpacePressed`` on every control in
    Omarchy's kit. Both bindings are ``show=False``: no bracket hint appears anywhere
    on this surface and no action may require a memorised key (UIX-03) —
    discoverability lives in the help chip.

    A click anywhere on the row activates it. The inner cells are plain ``Static``s
    and Textual's ``Click`` bubbles, so a click that lands on the right-hand detail
    still reaches the row. A dead region in a control the user believes is live is how
    a late-night user concludes the app is broken and reaches for the raw config
    instead (T-12.1-18).

    Right-click and double-click are **wired and unused** in 12.1 — noted as the kit
    does with ``PanelSlider.rightClicked()``, not invented. ``Click.button`` is 3 on
    right and ``Click.chain`` is 2 on double, both populated in textual 8.2.7.

    A refused row posts :class:`Refused` rather than :class:`Activated`, so a screen
    handler that opens the editor structurally cannot be reached by one of the four
    frozen keys. That is a seam, not a gate: what refuses a weakening is the signer.

    Size never changes with state (UIX-05/D-05). The reserved one-column spine is in
    ``app.tcss`` at every rung; nothing here sets a border, a width or a padding.
    """

    DEFAULT_CSS = """
    ControlRow { layout: horizontal; }
    """

    BINDINGS = [
        Binding("enter", "activate", "Activate", show=False),
        Binding("space", "activate", "Activate", show=False),
    ]

    class Activated(Message):
        """A reachable control was activated. Carries the stop, not a decision."""

        def __init__(self, row: "ControlRow", control: Control) -> None:
            self.row = row
            self.control = control
            super().__init__()

    class Refused(Message):
        """A frozen control was activated. The row states why; nothing else happens."""

        def __init__(self, row: "ControlRow", control: Control) -> None:
            self.row = row
            self.control = control
            self.reason = control.refusal or ""
            super().__init__()

    def __init__(self, control: Control, **kwargs) -> None:
        self.control = control
        kwargs.setdefault("id", "ctl-%s" % control.key)
        kwargs.setdefault("classes", self._classes_for(control))
        # A chip is its own label; a row composes three cells instead.
        super().__init__(control.label if control.kind == "chip" else "", **kwargs)

    @staticmethod
    def _classes_for(control: Control) -> str:
        classes = ["ctl"]
        if control.kind == "chip":
            classes.append("chip")
            if control.primary:
                classes.append("-primary")
        if control.selected:
            classes.append("-selected")
        if control.is_refused:
            classes.append("-refused")
        return " ".join(classes)

    @staticmethod
    def _cell_classes(base: str, role: str) -> str:
        return "%s %s" % (base, role) if role else base

    def _cells(self) -> list[Static]:
        control = self.control
        if control.kind == "chip":
            return []
        return [
            Static(control.label, classes="row-label"),
            Static(
                control.value,
                classes=self._cell_classes("row-value", control.value_role),
            ),
            Static(
                self._detail_text(),
                classes=self._cell_classes("row-detail", control.detail_role),
            ),
        ]

    def _detail_text(self) -> str:
        """A refused row states the reason ON the row, beside its own detail.

        The refusal is not carried by colour and not hidden behind a tooltip: a
        reason the user has to hover to find is a reason he does not have at the
        moment he is deciding whether the app is lying to him.
        """
        control = self.control
        if control.is_refused:
            return control.refusal or ""
        return control.detail

    def compose(self) -> ComposeResult:
        for cell in self._cells():
            yield cell

    def on_mount(self) -> None:
        if self.control.tooltip:
            self.tooltip = self.control.tooltip

    # --- the shared cursor ---

    def on_enter(self) -> None:
        """The pointer moves the keyboard cursor. This is the whole mechanism.

        Not "also highlight on hover" — the same cursor, moved. A second highlight
        kept beside focus is a second source of truth, and the two disagree the first
        time a key press and a mouse move race each other.
        """
        self.focus()

    def on_leave(self, event: Leave) -> None:
        """Leaving drops the pressed rung; the cursor stays where the pointer left it.

        A press abandoned by dragging off the row must not leave the row painted as
        held down for the rest of the session.
        """
        self.remove_class("-pressed")

    # --- activation ---

    def on_mouse_down(self, event: MouseDown) -> None:
        if event.button == 1:
            self.add_class("-pressed")

    def on_mouse_up(self, event: MouseUp) -> None:
        self.remove_class("-pressed")

    def on_click(self, event: Click) -> None:
        """The whole row is the click target, wherever inside it the click landed.

        Right-click (``button == 3``) and double-click (``chain == 2``) are read and
        deliberately do nothing in 12.1.
        """
        if event.button != 1:
            return
        if event.chain > 1:
            return
        self.activate()

    def action_activate(self) -> None:
        """Keyboard activation: paint the pressed rung, then do what a click does."""
        self.add_class("-pressed")
        self.set_timer(PRESS_FLASH, lambda: self.remove_class("-pressed"))
        self.activate()

    def activate(self) -> None:
        """Post the one message this row is allowed to post.

        Nothing is decided here and nothing is written here. A refused row surfaces
        its own refusal string and stops; every other row hands its stop to the screen,
        which owns the routing.
        """
        control = self.control
        if control.is_refused:
            self.post_message(self.Refused(self, control))
            return
        self.post_message(self.Activated(self, control))
