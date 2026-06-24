# Wave-0 Spike Notes

De-risking the two flagged runtime assumptions before the screens are built.

## A2 — Inline sudo capture strategy (suspend → sudo → resume)

**Chosen capture strategy:** `subprocess.run(argv, stdout=subprocess.PIPE, text=True)`
with **stderr left ATTACHED to the TTY** (not captured). Capturing stdout lets the
TUI read the CLI's verbatim success line; leaving stderr on the TTY is what makes
sudo's password / fingerprint prompt — and any `REFUSED`/`ERROR` line — appear
inline to the user while the app is suspended (Pitfall 3). The real `commit()`
seam in `backend.py` uses this exact strategy; the spike exercises it against the
harmless, sudoers-allowed read-only `verify` subcommand.

The commit call must be wrapped by the caller in `with app.suspend():` (Wave 3) so
the TTY is released to sudo; `App.suspend()` is the Textual primitive for this.

**Live result (A2): CONFIRMED.** Running the spike (`.venv/bin/python
spike/inline_sudo_spike.py`, press `s`) released the TTY via `App.suspend()`, the
sudo password/fingerprint prompt appeared **inline** in the suspended terminal,
and after authenticating the TUI resumed and displayed a **readable** `verify`
return code. The suspend → sudo → resume flow and the stdout-pipe/stderr-on-TTY
capture strategy are validated for the real `commit()` path in Wave 3.

## A3 — Live theme repaint approach

**Chosen approach:** re-register the same-named omarchy `Theme` (overwrite) and
reassign `App.theme` to force a repaint when the desktop theme changes. The live
watch is a stdlib `mtime` poll on the omarchy `current/theme/colors.toml` path,
ticked from the app's 1s interval (watchfiles deliberately NOT installed — lean
deps). This is exercised live in Wave 2's `theme.py`.

**Fallback** if reassigning `App.theme` does not repaint: toggle to a throwaway
theme then back, or `self.refresh(layout=True)`.
