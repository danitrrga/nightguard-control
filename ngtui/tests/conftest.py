"""pytest fixtures/bootstrap for the ngtui headless tests.

Importing ``ngtui.widgets.status`` transitively imports ``ngtui.backend``, which on
import inserts the live LifeOS trust stack onto ``sys.path`` and imports it. The
stack paths are env-overridable; set the author-instance defaults here before
collection so the helper tests import cleanly on this box. theme.py tests need none
of this (theme.py imports only stdlib + textual), but setting the vars is harmless.
"""
from __future__ import annotations

import os

os.environ.setdefault(
    "NIGHTGUARD_STACK_DIR", "/home/danitrrga/dev/Projects/nightguard-control/scripts/linux"
)
os.environ.setdefault(
    "NIGHTGUARD_DIR", "/home/danitrrga/.local/share/nightguard"
)

import json  # noqa: E402

import pytest  # noqa: E402

# --- Phase 11 status fixtures -------------------------------------------------
# The status core (Plan 11-01) is read-only and key-less. Its tests need a
# crafted data dir (guard.json + config.sanctioned.yaml) and a deterministic
# verdict. The trust-stack path constants (``ng.STATE`` / ``ng.SANCTIONED`` /
# guard's ``TIMECACHE``) are frozen at import from the env, so re-pointing them
# is done by monkeypatching the module attributes — setting the env after import
# would not move the already-resolved paths.
#
# Verdict determinism: the guard's ``true_unix()`` honours the
# NIGHTGUARD_TEST_NTP_OVERRIDE=1 + NIGHTGUARD_NTP_OVERRIDE_UNIX seam, returning
# the supplied epoch with source "override" (no SNTP/HTTP, no clock-tamper
# branch). The curfew window in the crafted config is 20:45–05:30
# Europe/Amsterdam, so:
#   _LOCKED_UNIX  = 2026-06-24 23:00 Amsterdam -> inside curfew  -> "locked"
#   _OUTSIDE_UNIX = 2026-06-24 12:00 Amsterdam -> outside curfew -> "outside_curfew"
_LOCKED_UNIX = 1782334800
_OUTSIDE_UNIX = 1782295200

# A minimal sanctioned config mirroring the live curfew shape (20:45–05:30).
_SANCTIONED_YAML = (
    "timezone: Europe/Amsterdam\n"
    "\n"
    "curfew:\n"
    '  enabled: true\n'
    '  start: "20:45"\n'
    '  end: "05:30"\n'
    "  block_when_offline: true\n"
    "\n"
    "clock_protection:\n"
    "  enabled: true\n"
    "  max_offset_minutes: 5\n"
)

_GUARD_JSON = {
    "config_hmac": "deadbeef",
    "state_hmac": "deadbeef",
    "weekly_spent": 1,
    "week_anchor": "2026-06-22",
    "ledger": [
        {"ntp_timestamp": 1782211095, "fields": ["curfew.allow_commands"]}
    ],
    "grace": None,
}


def _point_stack_at(monkeypatch, data_dir, *, override_unix):
    """Re-point the imported trust stack at ``data_dir`` and pin true-time.

    Imported here (not at module top) so collecting tests that never use these
    fixtures does not force the backend import early.
    """
    from ngtui import backend  # noqa: E402  (defers trust-stack import)

    ng = backend.ng
    guard = backend.guard

    state_path = data_dir / "guard.json"
    sanctioned_path = data_dir / "config.sanctioned.yaml"
    config_path = data_dir / "config.yaml"
    timecache_path = data_dir / ".timecache"

    monkeypatch.setattr(ng, "NIGHTGUARD_DIR", str(data_dir), raising=False)
    monkeypatch.setattr(ng, "STATE", str(state_path), raising=False)
    monkeypatch.setattr(ng, "SANCTIONED", str(sanctioned_path), raising=False)
    monkeypatch.setattr(ng, "CONFIG", str(config_path), raising=False)
    monkeypatch.setattr(guard, "TIMECACHE", str(timecache_path), raising=False)
    monkeypatch.setenv("NIGHTGUARD_DIR", str(data_dir))

    # Deterministic, network-free true-time via the documented override seam.
    monkeypatch.setenv("NIGHTGUARD_TEST_NTP_OVERRIDE", "1")
    monkeypatch.setenv("NIGHTGUARD_NTP_OVERRIDE_UNIX", str(override_unix))


def _write_data_dir(data_dir, *, write_files):
    if write_files:
        (data_dir / "config.sanctioned.yaml").write_text(
            _SANCTIONED_YAML, encoding="utf-8"
        )
        (data_dir / "config.yaml").write_text(_SANCTIONED_YAML, encoding="utf-8")
        (data_dir / "guard.json").write_text(
            json.dumps(_GUARD_JSON), encoding="utf-8"
        )


@pytest.fixture
def ng_data_dir(tmp_path, monkeypatch):
    """A populated, locked-verdict data dir (guard.json + sanctioned config).

    Writes a crafted ``guard.json`` (weekly_spent/week_anchor/ledger/grace) and a
    ``config.sanctioned.yaml`` into ``tmp_path``, re-points the trust stack at it,
    and pins true-time inside the curfew window so ``live_verdict`` is "locked".
    Returns the ``pathlib.Path`` to the data dir.
    """
    _write_data_dir(tmp_path, write_files=True)
    _point_stack_at(monkeypatch, tmp_path, override_unix=_LOCKED_UNIX)
    return tmp_path


@pytest.fixture
def ng_data_dir_outside(tmp_path, monkeypatch):
    """A populated data dir pinned OUTSIDE the curfew window -> "outside_curfew"."""
    _write_data_dir(tmp_path, write_files=True)
    _point_stack_at(monkeypatch, tmp_path, override_unix=_OUTSIDE_UNIX)
    return tmp_path


@pytest.fixture
def ng_data_dir_empty(tmp_path, monkeypatch):
    """An EMPTY data dir — no guard.json, no sanctioned config.

    Backend reads degrade to ``{}`` (load_state -> {}, sanctioned_config -> {}).
    True-time is pinned inside the curfew window so an empty/uninitialized dir
    renders "locked", never "unavailable" (Pitfall 3). Returns the dir Path.
    """
    _write_data_dir(tmp_path, write_files=False)
    _point_stack_at(monkeypatch, tmp_path, override_unix=_LOCKED_UNIX)
    return tmp_path


@pytest.fixture
def read_key_explodes(monkeypatch):
    """Make any ``read_key`` call raise — proves the status path is key-less.

    Patches ``read_key`` on every module that re-exports ngcommon
    (ng / guard.ng / ctl.ng) so a stray read from any of them is caught.
    """
    from ngtui import backend  # noqa: E402

    def _boom(*_a, **_k):
        raise AssertionError("read_key() called on the key-less status path (DESK-02)")

    monkeypatch.setattr(backend.ng, "read_key", _boom, raising=False)
    monkeypatch.setattr(backend.guard.ng, "read_key", _boom, raising=False)
    monkeypatch.setattr(backend.ctl.ng, "read_key", _boom, raising=False)
    return _boom


# --- Phase 12.1 UI fixtures ---------------------------------------------------
# Nine test files in phase 12.1 need to build the real app against a theme that
# is NOT the live desktop theme. `~/.local/state/omarchy/current/theme/` is
# outside the repo and `omarchy-theme-set` rewrites it wholesale at any moment,
# so a control that read it would be asserting against a moving target and would
# go red when the author changed themes (T-12.1-02). These fixtures write a
# paired colors.toml + shell.toml into tmp_path and repoint
# `ngtui.theme.OMARCHY_THEME_DIRS` at it — same shape as the trust-stack group
# above (build a tmp dir, monkeypatch the module constant, return the path), and
# the same shape `test_theme_sync.py:158-207` already uses for the pure theme
# tests. Nothing here writes to ~/.local/state/omarchy/.
#
# Two variants over one writer, mirroring ng_data_dir/_outside/_empty:
#   pinned=False  the generated shape — what 25 of the 27 installed themes get
#                 from /usr/share/omarchy/default/themed/shell.toml.tpl
#   pinned=True   the city-783 shape — one of the only two themes that ship
#                 their own shell.toml, and the one that deviates hardest

# Periphery's real palette, read from ~/.config/omarchy/themes/periphery/colors.toml.
# Named keys only, no terminal-slot keys — that is the shape almost every installed
# theme ships, and it is the shape that makes the colour-role control fail today:
# the shipped loader's chains find no slot key and collapse error/success/warning
# onto accent (#7fc9c4), so verdict colour carries no information.
_FIXTURE_COLORS = (
    'mode = "dark"\n'
    'accent = "#7fc9c4"\n'
    'background = "#060f12"\n'
    'foreground = "#a9c0bf"\n'
    'red = "#d4644a"\n'
    'green = "#7fae8e"\n'
    'yellow = "#c9a06a"\n'
    'hyprland_active_border = "rgba(7fc9c4ee) rgba(68a5a2ee) 45deg"\n'
)

# city-783's real palette, read from ~/.config/omarchy/themes/city-783/colors.toml.
# Kept distinct from the generated variant's so a test cannot pass by reading the
# wrong fixture: nothing here is #7fc9c4.
_FIXTURE_COLORS_PINNED = (
    'mode = "dark"\n'
    'accent = "#ad2222"\n'
    'background = "#181a1f"\n'
    'foreground = "#b9bec6"\n'
    'red = "#e53939"\n'
    'green = "#dce0e6"\n'
    'yellow = "#9e1a1a"\n'
)

# The generated shell.toml. Structure verbatim from the omarchy template
# (/usr/share/omarchy/default/themed/shell.toml.tpl) with ONE value changed.
#
# `normal-fill-alpha = 0.42` is deliberately not a value any real theme ships.
# It is read by test_token_pipeline's control 2, which asserts
# `row.styles.background.a == 0.42`: a build that consumes the theme's
# [controls] block lands on 0.42, and a build that ignores it falls back to
# theme.STYLE_DEFAULTS["control_fill_alpha"] = 0.04. Distinctive on purpose —
# against the live 0.04 the two outcomes would be indistinguishable from a
# rounding difference, and control 2 could pass without the pipeline existing.
#
# On *-color and the word `foreground`: the template writes `"{{ foreground }}"`,
# the generated file on this box carries the substituted hex, and Style.qml
# resolves the bare word against colors.toml. The fixture writes the word in
# [controls] so the word-resolution path has coverage, and resolved hexes in
# [popups]/[tooltip] so the rest of the file matches a real generated one. The
# pinned variant covers per-rung hex.
_FIXTURE_SHELL_GENERATED = """[hyprland]
active-border = "rgba(7fc9c4ee) rgba(68a5a2ee) 45deg"

[controls]
normal-color        = "foreground"
normal-fill-alpha   = 0.42
normal-border       = "foreground"
normal-border-width = 1
normal-border-alpha = 0.4

hover-cursor-color        = "foreground"
hover-cursor-fill-alpha   = 0.08
hover-cursor-border       = "foreground"
hover-cursor-border-width = 1
hover-cursor-border-alpha = 0.25

focus-color        = "foreground"
focus-fill-alpha   = 0.08
focus-border       = "foreground"
focus-border-width = 1
focus-border-alpha = 0.25

selected-color        = "foreground"
selected-fill-alpha   = 0.18
selected-border       = "foreground"
selected-border-width = 0
selected-border-alpha = 1.0

pressed-fill-alpha   = 0.22
selection-fill-alpha = 0.35

[spacing]
scale = 1.0
scale-with-font = true

[font]
base-size = 12

[popups]
background       = "#060f12"
background-alpha = 1.0
text             = "#a9c0bf"
border           = "hyprland.active-border"
border-alpha     = 1.0

[tooltip]
background       = "#060f12"
background-alpha = 0.97
text             = "#a9c0bf"
border           = "hyprland.active-border-foreground"
border-alpha     = 1.0
"""

# The pinned shell.toml — city-783's own file, read from
# ~/.config/omarchy/themes/city-783/shell.toml. Three deviations are the point of
# this variant, and each has an assertion waiting for it:
#   * per-rung colours that are NOT the palette foreground (#b9bec6):
#     focus-color and selected-color are #eceff2, so a pipeline that hardcodes
#     "the colour is always foreground" is caught.
#   * focus-border-width = 2 — the clamp target. A character grid has no sub-cell
#     borders and D-05 forbids a state growing the box, so the pipeline must clamp
#     2 to 1 rather than reflow the row.
#   * focus-border / selected-border are 10-stop Hyprland gradients, which
#     _resolve_border() must keep rejecting rather than half-painting.
# Also faithful: [tooltip] references hyprland.active-border-foreground, which
# city-783 never defines — the missing-key fallback path.
_FIXTURE_SHELL_PINNED = """[hyprland]
active-border = "#ad2222 #ad2222 #ad2222 #ad2222 #eceff2 #ad2222 #ad2222 #ad2222 #ad2222 #ad2222 35deg"

[controls]
normal-color        = "#b9bec6"
normal-fill-alpha   = 0.04
normal-border       = "#b9bec6"
normal-border-width = 1
normal-border-alpha = 0.4

hover-cursor-color        = "#b9bec6"
hover-cursor-fill-alpha   = 0.08
hover-cursor-border       = "#b9bec6"
hover-cursor-border-width = 1
hover-cursor-border-alpha = 0.25

focus-color        = "#eceff2"
focus-fill-alpha   = 0.10
focus-border       = "#ad2222 #ad2222 #ad2222 #ad2222 #eceff2 #ad2222 #ad2222 #ad2222 #ad2222 #ad2222 35deg"
focus-border-width = 2
focus-border-alpha = 1.0

selected-color        = "#eceff2"
selected-fill-alpha   = 0.16
selected-border       = "#ad2222 #ad2222 #ad2222 #ad2222 #eceff2 #ad2222 #ad2222 #ad2222 #ad2222 #ad2222 35deg"
selected-border-width = "0 0 1 0"
selected-border-alpha = 1.0

pressed-fill-alpha   = 0.22
selection-fill-alpha = 0.35

[spacing]
scale = 1.0
scale-with-font = true

[font]
base-size = 12

[popups]
background       = "#20232a"
background-alpha = 0.98
text             = "#b9bec6"
border           = "hyprland.active-border"
border-alpha     = 1.0

[tooltip]
background       = "#20232a"
background-alpha = 0.97
text             = "#b9bec6"
border           = "hyprland.active-border-foreground"
border-alpha     = 1.0
"""


def _write_theme_dir(root, *, pinned):
    """Write a paired colors.toml + shell.toml into ``root`` and return it.

    One writer, two variants, rather than a parametrised fixture — same reason
    ``_write_data_dir(write_files=...)`` is one helper behind three fixtures: the
    test names then say which desktop theme shape they are asserting against.
    """
    root.mkdir(parents=True, exist_ok=True)
    colors = _FIXTURE_COLORS_PINNED if pinned else _FIXTURE_COLORS
    shell = _FIXTURE_SHELL_PINNED if pinned else _FIXTURE_SHELL_GENERATED
    (root / "colors.toml").write_text(colors, encoding="utf-8")
    (root / "shell.toml").write_text(shell, encoding="utf-8")
    return root


def _point_theme_at(monkeypatch, directory):
    """Re-point the theme loader at ``directory``.

    ``monkeypatch.setattr`` on the module attribute, not ``setenv``: theme.py has
    no env seam, ``OMARCHY_THEME_DIRS`` is a module-level tuple consulted by
    ``theme_dir()`` on every call, and a fixture that set an env var would leave
    the loader reading the live desktop theme while looking like it had not.
    """
    from ngtui import theme  # noqa: E402  (defers the theme import off pure tests)

    monkeypatch.setattr(theme, "OMARCHY_THEME_DIRS", (str(directory),), raising=False)


@pytest.fixture
def omarchy_theme_dir(tmp_path, monkeypatch):
    """A fixture desktop theme in the GENERATED shape, with the loader pointed at it.

    Returns the theme directory (the one holding colors.toml/shell.toml) so
    ``mutate_theme`` can rewrite it mid-test.
    """
    directory = _write_theme_dir(tmp_path / "theme", pinned=False)
    _point_theme_at(monkeypatch, directory)
    return directory


@pytest.fixture
def omarchy_theme_pinned_dir(tmp_path, monkeypatch):
    """A fixture desktop theme in the city-783 shape (per-rung colours, width 2,
    gradient borders), with the loader pointed at it."""
    directory = _write_theme_dir(tmp_path / "theme", pinned=True)
    _point_theme_at(monkeypatch, directory)
    return directory


def _toml_scalar(value):
    """Render a Python value as the TOML scalar the fixture files use."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return '"%s"' % value


@pytest.fixture
def mutate_theme():
    """Factory: ``mutate_theme(root, "controls", focus_fill_alpha=0.9)``.

    Rewrites the named section of ``root/shell.toml`` in place and bumps the
    file's mtime, so a running app's theme poll sees a change. Control 3 (the
    live-restyle path) uses this to move a border style between repaints.

    Keyword names are converted underscore -> hyphen (``focus_fill_alpha`` ->
    ``focus-fill-alpha``): the TOML keys are hyphenated and a Python keyword
    cannot be.

    The mtime bump is not optional. ``ThemeWatch`` compares ``st_mtime``, and a
    rewrite this fast can land on the same timestamp as the fixture write — the
    poll would then report no change and the restyle assertion would fail with
    the pipeline working. ``test_theme.py:125-127`` bumps it explicitly for the
    same reason; the +5 here matches that.
    """

    def _mutate(root, section, **tokens):
        path = root / "shell.toml"
        lines = path.read_text(encoding="utf-8").splitlines()

        header = "[%s]" % section
        start = None
        for index, line in enumerate(lines):
            if line.strip() == header:
                start = index
                break
        # Vacuity guard, same job as test_deploy_completeness.py's `assert match`:
        # a mutation that silently matched no section would leave the file at its
        # original values and let a restyle test pass by asserting on a change
        # that never happened.
        assert start is not None, "shell.toml has no %s section to mutate" % header

        end = len(lines)
        for index in range(start + 1, len(lines)):
            if lines[index].lstrip().startswith("["):
                end = index
                break

        block = lines[start + 1:end]
        for name, value in tokens.items():
            key = name.replace("_", "-")
            rendered = "%s = %s" % (key, _toml_scalar(value))
            for index, line in enumerate(block):
                if line.split("=")[0].strip() == key:
                    block[index] = rendered
                    break
            else:
                block.append(rendered)
        lines[start + 1:end] = block
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        stat = os.stat(path)
        os.utime(path, (stat.st_atime + 5, stat.st_mtime + 5))
        return path

    return _mutate


@pytest.fixture
def probe_app():
    """Factory: ``probe_app(rows=5)`` -> a real NightguardApp showing a probe screen.

    It is a subclass of the real ``NightguardApp``, not a fresh ``App``, because
    the three controls that use it assert on things only the real app has: its
    ``get_css_variables()``, its ``app.tcss``, and its ``_apply_omarchy_theme()``.
    A hand-built App would let all three pass while the shipped app stayed
    unstyled. What it replaces is only the composition: ``on_mount`` pushes a bare
    Screen of ``rows`` focusable rows instead of ``StatusScreen``, because the
    final dashboard composition does not exist at this wave.

    The probe row is defined here rather than imported: the shared-cursor widget
    module this phase will add does not exist yet, and a fixture that imported it
    would make every later test file uncollectable until it lands.

    Trust boundary (T-12.1-01): the probe never reaches the editor. ``action_edit``
    and ``action_refresh`` are overridden to raise rather than push EditScreen or
    StatusScreen, so a stray key press in a Pilot test cannot route a UI control
    into the commit path or into a live guard.json read. Same shape as
    ``read_key_explodes`` above — make the forbidden path loud instead of trusting
    that no test presses the key.
    """
    from textual import events  # noqa: E402
    from textual.app import App  # noqa: E402  (defers the UI import off pure tests)
    from textual.screen import Screen  # noqa: E402
    from textual.widgets import Static  # noqa: E402

    from ngtui import app as ngtui_app  # noqa: E402
    from ngtui.app import NightguardApp  # noqa: E402  (transitively imports the stack)

    class _ProbeRow(Static, can_focus=True):
        """A focusable row carrying the cursor. `on_enter` -> `focus()` is the
        shared-cursor mechanism itself (one cursor for pointer and keyboard), so
        the probe must have it or control 5 measures nothing."""

        def on_enter(self) -> None:
            self.focus()

    class _ProbeScreen(Screen):
        def __init__(self, rows: int) -> None:
            self._rows = rows
            super().__init__()

        def compose(self):
            for index in range(self._rows):
                yield _ProbeRow(
                    "probe row %d" % index, id="r%d" % index, classes="ctl"
                )

    class _ProbeApp(NightguardApp):
        # Absolute, and derived from ngtui.app's own location rather than typed.
        # Textual resolves a relative CSS_PATH against the directory of the module
        # where the App subclass is DEFINED, not where it is inherited from — a
        # probe subclass declared in tests/ inherits the literal "app.tcss" and
        # resolves it to tests/app.tcss, which does not exist:
        #   StylesheetError: unable to read CSS file '…/ngtui/tests/app.tcss'
        # Measured, not anticipated: the first build of this fixture died on it.
        # Pinning it here is also what keeps the probe honest — the controls that
        # use it assert on the real shipped stylesheet.
        CSS_PATH = os.path.join(
            os.path.dirname(os.path.abspath(ngtui_app.__file__)), "app.tcss"
        )

        def __init__(self, rows: int) -> None:
            # Assigned before super().__init__(): App.__init__ can reach
            # get_css_variables(), and state it reads must already exist by then
            # (RESEARCH Pitfall 3).
            self._probe_rows = rows
            super().__init__()

        def on_mount(self, event: events.Mount) -> None:
            # prevent_default() is load-bearing, not defensive. Textual dispatches
            # a message to the handler of EVERY class in the MRO
            # (message_pump.py:758 `for cls in self.__class__.__mro__`), so
            # defining on_mount here does not REPLACE NightguardApp.on_mount — both
            # run, subclass first. Measured: the screen stack came out
            # [Screen(_default), _ProbeScreen(), StatusScreen()] and every
            # `app.query(".ctl")` returned 0, because the base handler pushed the
            # real StatusScreen on top of the probe. Every control using this
            # fixture would have been silently asserting against StatusScreen —
            # and StatusScreen reads live guard state, which is the boundary
            # T-12.1-01 exists to hold. prevent_default() sets
            # `_no_default_action`, and the dispatch loop breaks on it before
            # reaching the base class (message.py:131-140).
            event.prevent_default()
            self._apply_omarchy_theme()
            self.push_screen(_ProbeScreen(self._probe_rows))
            self.set_interval(1.0, self._tick)

        def action_edit(self) -> None:
            raise AssertionError(
                "probe_app routed into EditScreen — the commit path is not reachable "
                "from a UI control test (T-12.1-01)"
            )

        def action_refresh(self) -> None:
            raise AssertionError(
                "probe_app routed into StatusScreen — a UI control test must not read "
                "live guard state (T-12.1-01)"
            )

    def _factory(rows: int = 5) -> App:
        return _ProbeApp(rows)

    return _factory
