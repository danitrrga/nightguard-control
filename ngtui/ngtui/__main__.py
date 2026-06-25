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


if __name__ == "__main__":
    main()
