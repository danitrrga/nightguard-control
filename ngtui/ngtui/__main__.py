"""Console entry point + argv front-controller (`ngtui = ngtui.__main__:main`).

Routing:
  * ``ngtui status [--json]`` -> a head-less, key-less reader. It emits a single
    line of Waybar-shaped JSON to stdout and ALWAYS exits 0 — any failure (a bad
    trust-stack import, an OSError, a malformed config) is caught broadly and
    degraded to the fixed ``status.UNAVAILABLE`` object. It never imports
    ``textual``/``ngtui.app`` (the TUI cost is paid only on the bare branch).
  * bare ``ngtui`` (anything else) -> the interactive Textual TUI, behind a
    TTY loud-fail guard so a non-TTY launch (a Waybar exec, a pipe) fails with
    ``SystemExit(2)`` instead of spewing escape sequences.

Note on the trust-stack defaults: ``ngtui.backend``'s module-level bootstrap reads
``NIGHTGUARD_STACK_DIR`` / ``NIGHTGUARD_DIR`` from the environment and, when they
are unset, falls back to *hardcoded author paths* (``os.environ.setdefault`` to a
fixed LifeOS directory) — it does not unconditionally "set" them. A generic
default is a later-phase concern. ``import ngtui.backend`` can also raise
``RuntimeError`` at import time on a poisoned stack dir, which is exactly why the
status path imports it INSIDE its try-block (fail closed to ``unavailable``).
"""
from __future__ import annotations

import sys


def main() -> None:
    """Front-controller: route ``status`` head-less, everything else to the TUI."""
    argv = sys.argv[1:]
    if argv and argv[0] == "status":
        sys.exit(_status(argv[1:]))  # head-less; emits JSON, exits 0
    if argv and argv[0] == "panel":
        sys.exit(_panel(argv[1:]))   # head-less; emits JSON, exits 0
    _run_tui()  # bare `ngtui`


def _run_tui() -> None:
    """Launch the interactive Textual TUI, guarded on a real TTY (Pitfall 4).

    The TTY guard lives on THIS branch only — never a blanket check at the top of
    ``main()``, which would break the head-less ``status`` (run from a Waybar exec
    with no TTY). ``ngtui.app``/``textual`` is imported lazily, AFTER the guard, so
    the status path never pays textual's import cost.
    """
    if not sys.stdin.isatty():
        sys.stderr.write("ngtui must be run in a terminal (no TTY on stdin).\n")
        raise SystemExit(2)
    from ngtui.app import NightguardApp  # lazy: status never imports textual

    NightguardApp().run()


def _status(args: list[str]) -> int:
    """Emit the Waybar status object as one JSON line; ALWAYS return 0 (SC-3).

    Fail closed: ``import ngtui.backend`` is INSIDE the try-block (it raises
    ``RuntimeError`` at import on a bad ``NIGHTGUARD_STACK_DIR`` — Pitfall 2), and
    the except is broad on purpose. Any failure leaves ``obj`` as the fixed
    ``UNAVAILABLE`` object. The verdict is resolved via the non-blocking
    ``cache_only_verdict`` seam (Plan 01), never the network-touching live path
    — so a cold time cache can never hang the bar poll.
    """
    import json

    from ngtui import status

    obj = status.UNAVAILABLE
    try:
        import ngtui.backend as b  # CAN raise RuntimeError at import (bad STACK_DIR)

        state = b.read_state()
        cfg = b.sanctioned_config()
        verdict = b.cache_only_verdict(cfg, state)  # non-blocking, key-less (Plan 01)
        tokens = b.tokens_left()
        obj = status._shape(verdict, tokens, state)
    except Exception:  # broad on purpose — fail closed (SC-3)
        obj = status.UNAVAILABLE

    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    return 0  # ALWAYS exit 0 (SC-3)


def _panel(args: list[str]) -> int:
    """Emit the desktop panel payload as one JSON line; ALWAYS return 0.

    Same fail-closed contract as ``status``: the backend import is inside the
    try, the except is broad, and any failure emits the fixed UNAVAILABLE object
    rather than a partial one. The panel polls this, so a raise here would leave
    a blank rectangle on the desktop where the curfew state should be.

    The verdict and the clock both come from the non-blocking cache-only seams,
    never the live network path -- a cold cache must not stall a repaint.
    """
    import json

    from ngtui import panel

    obj = panel.UNAVAILABLE
    try:
        import ngtui.backend as b  # CAN raise RuntimeError at import (bad STACK_DIR)

        state = b.read_state()
        cfg = b.sanctioned_config()
        verdict = b.cache_only_verdict(cfg, state)
        obj = panel.build(
            verdict,
            b.tokens_left(),
            cfg,
            state,
            now_minutes=b.cache_only_now_minutes(cfg),
            warnings=_live_warnings(),
            theme_tokens=_theme_tokens(),
        )
    except Exception:  # broad on purpose — fail closed
        obj = panel.UNAVAILABLE

    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    return 0


def _theme_tokens() -> dict:
    """The desktop palette, or {} — never a raise on the panel path."""
    try:
        from ngtui import theme

        return theme.raw_tokens()
    except Exception:
        return {}


def _live_warnings() -> list[str]:
    """Machine-state warnings worth surfacing next to the curfew state.

    Never raises: a warning that crashes the panel is worse than an absent one.
    """
    from ngtui import panel

    warnings = []
    try:
        import grp

        entry = grp.getgrnam("empower")
        line = "empower:x:%d:%s" % (entry.gr_gid, ",".join(entry.gr_mem))
        message = panel.empower_warning(line)
        if message:
            warnings.append(message)
    except Exception:
        pass
    return warnings


if __name__ == "__main__":
    main()
