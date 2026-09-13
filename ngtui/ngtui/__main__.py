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


# Launchers that stand in front of the real program. Their basename is the same
# for every entry that uses them, so mapping it to a name would label every
# webapp with whichever .desktop file happened to be read last.
_LAUNCHER_WRAPPERS = frozenset({
    "omarchy-launch-webapp", "omarchy-launch-or-focus", "omarchy-launch",
    "gtk-launch", "flatpak", "env", "sh", "bash",
})


def _desktop_labels():
    """Map an executable basename to the human name of its desktop entry.

    Only where exactly ONE entry claims that basename: two programs shipping
    the same binary name means the label would be a coin flip, and a wrong
    label on a kill list is worse than no label. Wrapper launchers are skipped
    entirely for the same reason -- they front many different programs.

    Best-effort by construction. An entry with no label reads as its raw
    identity, which is what the config actually holds anyway.
    """
    import glob
    import os

    claims = {}
    dirs = [
        "/usr/share/applications",
        os.path.expanduser("~/.local/share/applications"),
    ]
    for directory in dirs:
        for path in glob.glob(os.path.join(directory, "*.desktop")):
            name = ""
            executable = ""
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if line.startswith("[") and name and executable:
                            break  # past [Desktop Entry], into an action group
                        if not name and line.startswith("Name="):
                            name = line[5:].strip()
                        elif not executable and line.startswith("Exec="):
                            executable = line[5:].strip()
            except OSError:
                continue
            if not name or not executable:
                continue
            first = executable.split()[0] if executable.split() else ""
            base = os.path.basename(first)
            if not base or base in _LAUNCHER_WRAPPERS:
                continue
            claims.setdefault(base, set()).add(name)

    return {base: next(iter(names)) for base, names in claims.items() if len(names) == 1}


def _resolves_to_a_binary(entry):
    """Is there something on this machine an entry could name, even if idle?

    An absolute path is checked as written -- that is how Proton- and
    JVM-hosted games are named. A bare name is looked up on PATH, which is the
    same basename the watchdog compares against.
    """
    import os
    import shutil

    if entry.startswith("/"):
        return os.path.exists(entry)
    return bool(shutil.which(entry))


def _app_resolution(cfg):
    """What this machine actually answers to, for each configured app entry.

    Returns ``{entry: {"state": ..., "label": ...}}``, or None when it could
    not be computed at all. None is not a failure to report -- it is the
    honest state, and the panel draws it as an em dash. A wrong "matches
    nothing" is an accusation and a wrong silence is a false comfort, so
    guessing in either direction is worse than admitting the read did not
    happen.

    The match test is appblock's own ``matches_identity``, never a second copy
    of it. The panel must report what the watchdog would really kill; a parallel
    implementation would drift from the enforcer and start lying by degrees.
    ``appblock`` is importable because ``ngtui.backend`` has already put the
    pinned STACK_DIR on sys.path, and this is only ever called after it.
    """
    import os
    import shutil

    try:
        import appblock

        native = ((cfg or {}).get("blocking") or {}).get("native_apps") or {}
        mode = str(native.get("mode") or "blocklist").strip().lower()
        listed = native.get("allowlist") if mode == "allowlist" else native.get("blacklist")
        entries = [str(e).strip() for e in (listed or []) if str(e).strip()]
        if not entries:
            return {}

        processes = appblock.read_processes()
        catalog = appblock.build_catalog(os.path.expanduser("~"))
        catalog_names = {
            str(c.get("name", "")).strip().lower() for c in (catalog or [])
        }

        labels = _desktop_labels()

        out = {}
        for entry in entries:
            if any(appblock.matches_identity(p, entry, catalog) for p in processes):
                # The strongest thing that can be said: the watchdog would end
                # this one right now.
                state = "running"
            elif _resolves_to_a_binary(entry):
                state = "installed"
            elif entry.lower() in catalog_names:
                # A game known by title rather than by binary -- it resolves
                # through its install path, not through PATH.
                state = "installed"
            else:
                state = "unmatched"

            label = labels.get(os.path.basename(entry))
            # A label identical to the identity teaches the reader nothing and
            # costs a column, so it is dropped rather than duplicated.
            if label and label.strip().lower() == entry.strip().lower():
                label = None
            out[entry] = {"state": state, "label": label}
        return out
    except Exception:  # broad on purpose -- a panel that cannot resolve still draws
        return None


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
            style_tokens=_style_tokens(),
            app_resolution=_app_resolution(cfg),
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


def _style_tokens() -> dict:
    """Omarchy's structural tokens, or {} — never a raise on the panel path."""
    try:
        from ngtui import theme

        return theme.omarchy_style()
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
