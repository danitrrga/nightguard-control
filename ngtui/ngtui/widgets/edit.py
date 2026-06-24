"""edit.py — the EditScreen: the anti-impulse editing half of the TUI.

This is the whole reason the product exists. The user edits the D-09 field set with
single-key navigation; each staged change shows its tighten/loosen direction and
token cost — computed by the signer's OWN classifier (``backend.preview_change`` →
``nightguard_ctl.classify_change``/``quota_decide``, D-06/D-07) — BEFORE any
authentication; a confirm gate states the consequence in one unmistakable line; and
only on the explicit ``y`` keystroke does the TUI ``suspend()`` and run
``sudo nightguard_ctl.py commit --from <temp>`` so sudo's password/fingerprint prompt
appears inline (D-08). The result line comes verbatim/returncode-keyed from the CLI.

Edits are composed as format-preserving per-field LINE edits on the sanctioned text
(``lineedit`` on ``backend.sanctioned_text()``) so the bytes the HMAC signs are not
disturbed (T-10-09 — NO YAML re-emit).

The load-bearing anti-impulse copy lives in PURE helpers (``preview_line``,
``confirm_copy``, ``result_line``) so it unit-tests headless; the Textual screens
only compose those helpers. Colour is applied via ``$``-variable role classes from
``app.tcss`` (no hardcoded hex, omarchy-native).

UI-SPEC deviation (intentional, REFUSED result): UI-SPEC "State & Feedback" says the
``REFUSED (...)`` line is shown verbatim from CLI stderr. This plan deliberately does
NOT meet that verbatim contract: ``backend.commit`` leaves stderr ATTACHED to the real
terminal during ``App.suspend()`` so sudo's password/fingerprint prompt (Pitfall 3) is
visible — which means the CLI's ``REFUSED (...)`` text appears NATIVELY on the terminal
during the suspend, not captured for re-rendering. On resume, ``result_line`` therefore
shows a returncode-driven ``$error`` indicator (pointing at the terminal output) plus a
re-read of state, rather than echoing stderr verbatim. The verbatim refusal text is
still seen by the user on the TTY; only its in-widget echo is replaced. This is the
correct tradeoff given the inline-auth requirement.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Header, Input, Label, Static

from ngtui import backend, lineedit

WEEKLY_TOKENS = 3


# --- pure copy helpers (headless-testable, load-bearing anti-impulse text) ----


def preview_line(direction: str, allowed: bool) -> tuple[str, str]:
    """Per-field preview string + colour role for a classifier direction.

    Drives every glyph/word/colour off the classifier result, never recomputed
    (D-06/D-07). Strings are verbatim from UI-SPEC "Anti-Impulse Edit Preview".
    A blocked loosen (``allowed == False``) surfaces the "available again Monday"
    line in ``$error``.
    """
    if direction == "tighten":
        return "▼ Tightens curfew · free", "accent"
    if direction == "loosen":
        if allowed:
            return "▲ Loosens curfew · costs 1 token", "warning"
        return (
            "▲ Loosens · BLOCKED — weekly tokens exhausted (3/3); "
            "available again Monday",
            "error",
        )
    # noop (and any unknown) → dim "no change".
    return "· no change", "text-muted"


def confirm_copy(decision: dict) -> tuple[str, str, bool]:
    """Confirm-gate line + colour role + whether commit is permitted.

    Returns ``(text, role, can_commit)``. The line states the consequence in one
    unmistakable sentence (UI-SPEC "Confirm gate"):
      - free tighten → no token language, ``$accent``;
      - loosen with tokens → explicit "costs 1 of 3 weekly tokens. After commit: N
        left.", ``$warning``;
      - loosen at 0 tokens → commit DISABLED, ``$error`` "available again Monday".
    ``N left`` is ``WEEKLY_TOKENS - (effective_spent + 1)`` (the token this loosen
    would spend), never an optimistic local guess beyond what the signer charges.
    """
    if not decision.get("allowed", False):
        return (
            "✕ Cannot commit: weekly loosen quota exhausted (3/3). "
            "Available again Monday.",
            "error",
            False,
        )
    if decision.get("costs_token", False):
        spent_after = int(decision.get("effective_spent", 0)) + 1
        left = max(0, WEEKLY_TOKENS - spent_after)
        return (
            f"▲ This change LOOSENS your curfew · costs 1 of 3 weekly tokens.  "
            f"After commit: {left} left.  Commit?  [y] yes  [n] no",
            "warning",
            True,
        )
    # Free tighten / multi-field tighten — no token language.
    return (
        "▼ This change TIGHTENS your curfew · free.  Commit?  [y] yes  [n] no",
        "accent",
        True,
    )


def result_line(returncode: int, stdout: str) -> tuple[str, str]:
    """Post-commit result line + colour role, from the CLI's actual exit/stdout.

    Never fabricated. exit 0 + "no-op" → muted; exit 0 (committed) → success,
    surfacing the CLI stdout verbatim with a ✓ marker; nonzero → ``$error``,
    returncode-keyed (stderr stayed on the TTY during the inline-sudo suspend, so
    the in-widget line points the user at the terminal output rather than echoing
    a captured REFUSED string — intentional UI-SPEC deviation, see module docstring).
    """
    out = (stdout or "").strip()
    if returncode == 0:
        if out.lower().startswith("no-op") or "no-op:" in out.lower():
            return f"· {out}" if out else "· no-op: nothing written.", "text-muted"
        return (f"✓ {out}" if out else "✓ committed."), "success"
    # Nonzero — refused / error. stderr is on the TTY above; key off the returncode.
    return (
        "✕ commit refused — see terminal output above; "
        "weekly tokens may be exhausted",
        "error",
    )


# --- editable field model (D-09) ---------------------------------------------

# (label, dotted_key, kind). The kind selects the line-edit op + the preview key.
# Labels mirror nightguard_ctl FIELD_TABLE so classify_change keys match directly.
_BOOL = "bool"
_TIME = "time"
_STR = "str"
_LIST = "list"

EDITABLE_FIELDS: list[tuple[str, str, str]] = [
    ("curfew.enabled", "curfew.enabled", _BOOL),
    ("curfew.start", "curfew.start", _TIME),
    ("curfew.end", "curfew.end", _TIME),
    ("curfew.allow_commands", "curfew.allow_commands", _LIST),
    ("clock_protection.enabled", "clock_protection.enabled", _BOOL),
    ("watchdog.enabled", "watchdog.enabled", _BOOL),
    ("blocking.browser_extension.enabled", "blocking.browser_extension.enabled", _BOOL),
    ("blocking.browser_extension.extension_id", "blocking.browser_extension.extension_id", _STR),
    ("blocking.native_apps.enabled", "blocking.native_apps.enabled", _BOOL),
    ("blocking.native_apps.blacklist", "blocking.native_apps.blacklist", _LIST),
]


def _read_dotted(cfg: dict, dotted_key: str):
    """Read a nested value from a parsed config dict by dotted path (``None`` if absent)."""
    cur = cfg
    for seg in dotted_key.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            return None
        cur = cur[seg]
    return cur


def _format_value(value, kind: str) -> str:
    """Human-readable current value for the field list."""
    if value is None:
        return "—"
    if kind == _BOOL:
        return "true" if value else "false"
    if kind == _LIST:
        items = value if isinstance(value, list) else []
        return ", ".join(str(i) for i in items) if items else "(empty)"
    return str(value)


# --- ConfirmScreen (modal gate, pushed on `c`) -------------------------------


class ConfirmScreen(ModalScreen):
    """The anti-impulse confirm gate. ``y`` is the ONLY thing that commits.

    Shows ``confirm_copy(decision)`` in one unmistakable line. On ``y`` (only when
    the decision permits), suspends the app and runs the real commit; on ``n``/
    ``Escape`` returns without committing. The token cost + direction were already
    visible on the EditScreen preview — this gate front-loads the consequence one
    more time before the (inline) sudo prompt, never after it.
    """

    BINDINGS = [
        ("y", "do_commit", "Yes, commit"),
        ("n", "cancel", "No"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, proposed_text: str, decision: dict) -> None:
        super().__init__()
        self._proposed_text = proposed_text
        self._decision = decision
        self._line, self._role, self._can_commit = confirm_copy(decision)

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Static(self._line, id="confirm-line", classes=self._role)
            if not self._can_commit:
                yield Static("[n] back", classes="dim")

    def action_do_commit(self) -> None:
        """The ``y`` path — the ONLY commit trigger. No-op when commit is disabled."""
        if not self._can_commit:
            self.app.bell()
            return
        # Release the TTY so sudo's password/fingerprint prompt is inline (D-08).
        with self.app.suspend():
            res = backend.commit(self._proposed_text)
        # Hand the result back to the EditScreen, which re-reads state (no optimism).
        self.dismiss(res)

    def action_cancel(self) -> None:
        self.dismiss(None)


# --- EditScreen ---------------------------------------------------------------


class EditScreen(Screen):
    """The editable surface (D-09) + anti-impulse preview (D-06) + inline commit (D-08).

    Renders the D-09 editable fields as a vertical list with their current SANCTIONED
    values (the diff base, Pitfall 5). ``j``/``k`` move focus; ``Enter`` begins an
    inline edit of the focused field; ``Space`` toggles a focused boolean; ``c`` opens
    the confirm gate (then inline-sudo commit); ``u`` discards staged edits; ``Escape``
    returns to StatusScreen (warning if staged edits pending).

    Each staged edit re-composes the proposed text via ``lineedit`` on
    ``backend.sanctioned_text()``, calls ``backend.preview_change``, and renders the
    per-field ``preview_line(...)`` from the classifier's direction + ``decision.allowed``
    — BEFORE any commit. The classifier is never recomputed locally.
    """

    BINDINGS = [
        ("j", "field_next", "Down"),
        ("k", "field_prev", "Up"),
        ("enter", "edit_field", "Edit"),
        ("space", "toggle", "Toggle bool"),
        ("c", "commit", "Commit"),
        ("u", "undo", "Discard edits"),
        ("escape", "back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._base_cfg = backend.sanctioned_config()
        self._base_text = backend.sanctioned_text()
        # Staged edits: dotted_key -> ("set"|"toggle"|"list_add"|"list_remove", value).
        # We re-derive the proposed TEXT from base_text by replaying staged edits in
        # order, so the line-edit transforms always start from the signed bytes.
        self._staged: list[tuple[str, str, str]] = []  # (op, dotted_key, value)
        self._focus = 0

    # --- compose ---

    def compose(self) -> ComposeResult:
        yield Header()
        if not self._base_cfg or not self._base_text:
            yield Static(
                "nightguard is not initialized on this machine", id="not-initialized"
            )
            yield Static("run nightguard_ctl.py init", classes="dim hint")
            yield Footer()
            return
        with VerticalScroll(id="edit-fields"):
            for i, (label, dotted, kind) in enumerate(EDITABLE_FIELDS):
                value = _read_dotted(self._base_cfg, dotted)
                with Horizontal(classes="edit-row"):
                    yield Static(label, classes="edit-label", id=f"label-{i}")
                    yield Static(
                        _format_value(value, kind), classes="edit-value", id=f"value-{i}"
                    )
        # The per-field preview line — the load-bearing anti-impulse signal.
        yield Static("", id="edit-preview")
        yield Static("", id="edit-status", classes="dim")
        yield Footer()

    def on_mount(self) -> None:
        self._highlight_focus()

    # --- focus navigation ---

    def _highlight_focus(self) -> None:
        for i in range(len(EDITABLE_FIELDS)):
            try:
                self.query_one(f"#label-{i}", Static).set_class(
                    i == self._focus, "focused"
                )
            except Exception:
                pass

    def action_field_next(self) -> None:
        self._focus = (self._focus + 1) % len(EDITABLE_FIELDS)
        self._highlight_focus()

    def action_field_prev(self) -> None:
        self._focus = (self._focus - 1) % len(EDITABLE_FIELDS)
        self._highlight_focus()

    # --- staging + preview ---

    def _proposed_text(self) -> str:
        """Replay staged edits over the sanctioned base text (no YAML emit)."""
        text = self._base_text
        for op, dotted, value in self._staged:
            if op == "set":
                text = lineedit.set_scalar(text, dotted, value)
            elif op == "toggle":
                text = lineedit.toggle_bool(text, dotted, value == "true")
            elif op == "list_add":
                text = lineedit.list_add(text, dotted, value)
            elif op == "list_remove":
                text = lineedit.list_remove(text, dotted, value)
        return text

    def _stage(self, op: str, dotted: str, value: str) -> None:
        self._staged.append((op, dotted, value))
        self._refresh_preview()
        self._refresh_value_cells()

    def _refresh_value_cells(self) -> None:
        """Repaint the current-value column from the staged proposed config."""
        try:
            proposed = backend_yaml_load(self._proposed_text())
        except Exception:
            return
        for i, (_label, dotted, kind) in enumerate(EDITABLE_FIELDS):
            try:
                self.query_one(f"#value-{i}", Static).update(
                    _format_value(_read_dotted(proposed, dotted), kind)
                )
            except Exception:
                pass

    def _refresh_preview(self) -> None:
        """Recompute + render the per-field anti-impulse preview (D-06/D-07).

        The classifier (``backend.preview_change`` → ``classify_change``/
        ``quota_decide``) is the single source of the direction + cost; this method
        only renders it. Shown for the dominant staged direction (loosen wins, since
        it is the cost-bearing path the user must see).
        """
        try:
            preview = backend.preview_change(self._proposed_text())
        except Exception:
            return
        dirs = preview.get("dirs", [])
        allowed = preview.get("decision", {}).get("allowed", True)
        # Pick the most consequential direction to surface: loosen > tighten > noop.
        directions = [d for _label, d in dirs]
        if "loosen" in directions:
            shown = "loosen"
        elif "tighten" in directions:
            shown = "tighten"
        else:
            shown = "noop"
        text, role = preview_line(shown, allowed)
        cell = self.query_one("#edit-preview", Static)
        cell.update(text)
        cell.set_classes(role)

    # --- edit actions ---

    def action_toggle(self) -> None:
        """``Space`` toggles the focused boolean field."""
        label, dotted, kind = EDITABLE_FIELDS[self._focus]
        if kind != _BOOL:
            self.app.bell()
            return
        # Toggle relative to the current proposed value.
        try:
            cur = _read_dotted(backend_yaml_load(self._proposed_text()), dotted)
        except Exception:
            cur = _read_dotted(self._base_cfg, dotted)
        self._stage("toggle", dotted, "false" if cur else "true")

    def action_edit_field(self) -> None:
        """``Enter`` begins an inline edit of the focused field.

        Time/string fields open a masked/free-text ``Input``; booleans toggle; list
        fields open a single-line add ``Input`` (one entry per Enter — the lighter
        list editor; ``d`` deletes the last entry).
        """
        label, dotted, kind = EDITABLE_FIELDS[self._focus]
        if kind == _BOOL:
            self.action_toggle()
            return
        if kind in (_TIME, _STR):
            placeholder = "HH:MM" if kind == _TIME else "value"
            self.app.push_screen(
                _InlineInput(label, placeholder), self._on_inline_value
            )
            self._pending = (op_for_kind(kind), dotted, kind)
            return
        if kind == _LIST:
            self.app.push_screen(
                _InlineInput(f"{label} — add entry", "entry"), self._on_inline_value
            )
            self._pending = ("list_add", dotted, kind)
            return

    def _on_inline_value(self, value: str | None) -> None:
        if value is None or value == "":
            return
        op, dotted, kind = self._pending
        if kind == _TIME and not _valid_hhmm(value):
            self.query_one("#edit-status", Static).update(
                f"✕ rejected: '{value}' is not HH:MM"
            )
            return
        self._stage(op, dotted, value)

    def action_undo(self) -> None:
        """``u`` discards all staged edits (with a [y/n] confirm)."""
        if not self._staged:
            return
        self.app.push_screen(
            _ConfirmDiscard(), self._on_discard
        )

    def _on_discard(self, discard: bool | None) -> None:
        if discard:
            self._staged.clear()
            self._refresh_preview()
            self._refresh_value_cells()
            self.query_one("#edit-status", Static).update("staged edits discarded")

    def action_commit(self) -> None:
        """``c`` opens the confirm gate for the staged change (preview-before-auth)."""
        if not self._staged:
            self.query_one("#edit-status", Static).update("no staged edits to commit")
            return
        try:
            proposed = self._proposed_text()
            preview = backend.preview_change(proposed)
        except Exception as e:  # malformed edit — never reach sudo
            self.query_one("#edit-status", Static).update(f"✕ cannot preview: {e}")
            return
        self.app.push_screen(
            ConfirmScreen(proposed, preview["decision"]), self._on_commit_result
        )

    def _on_commit_result(self, res: dict | None) -> None:
        """After the confirm gate: render the CLI result + re-read state (no optimism)."""
        if res is None:
            return  # cancelled — nothing committed
        text, role = result_line(res.get("returncode", 1), res.get("stdout", ""))
        cell = self.query_one("#edit-status", Static)
        cell.update(text)
        cell.set_classes(role)
        # Committed (or attempted) — re-read sanctioned base + clear staged edits so
        # the screen reflects what the signer actually wrote (re-read, never optimism).
        self._base_cfg = backend.sanctioned_config()
        self._base_text = backend.sanctioned_text()
        self._staged.clear()
        self._refresh_value_cells()
        self._refresh_preview()

    def action_back(self) -> None:
        """``Escape`` returns to StatusScreen, gating on a discard confirm if needed.

        With staged edits pending, push the explicit discard-confirm modal rather
        than silently clearing the stage (WR-01): losing staged work — possibly a
        loosen the user meant to review — must require an unmistakable confirmation.
        """
        if self._staged:
            self.app.push_screen(_ConfirmDiscard(), self._on_back_discard)
            return
        self.app.pop_screen()

    def _on_back_discard(self, discard: bool | None) -> None:
        """Discard-confirm result for the Escape path: only leave on explicit yes."""
        if discard:
            self._staged.clear()
            self.app.pop_screen()
        # else (n / Escape): stay on EditScreen with staged edits intact.


# --- small modal helpers ------------------------------------------------------


class _InlineInput(ModalScreen):
    """A one-line inline ``Input`` modal; dismisses with the entered string (or None)."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, prompt: str, placeholder: str) -> None:
        super().__init__()
        self._prompt = prompt
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="inline-box"):
            yield Label(self._prompt)
            yield Input(placeholder=self._placeholder, id="inline-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class _ConfirmDiscard(ModalScreen):
    """[y/n] gate for discarding staged edits (lighter than the loosen-commit gate)."""

    BINDINGS = [
        ("y", "yes", "Yes"),
        ("n", "no", "No"),
        ("escape", "no", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Static("Discard all staged edits?  [y] yes  [n] no")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


# --- tiny utilities -----------------------------------------------------------


def op_for_kind(kind: str) -> str:
    """The line-edit op a scalar/time/string edit stages."""
    return "set"


def _valid_hhmm(value: str) -> bool:
    try:
        h, m = (int(x) for x in str(value).split(":"))
    except (ValueError, TypeError):
        return False
    return 0 <= h <= 23 and 0 <= m <= 59


def backend_yaml_load(text: str) -> dict:
    """Parse proposed text via the live ngcommon parser (re-exported for the screen)."""
    return backend.ng.yaml_load(text)
