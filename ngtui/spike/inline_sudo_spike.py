"""Wave-0 spike (A2): does sudo's prompt appear inline after App.suspend()?

Runs the sudoers-allowed, READ-ONLY ``verify`` subcommand (never ``commit``) to
settle the runtime question before the screens are built: when the TUI releases
the TTY via ``App.suspend()``, does the sudo password / fingerprint prompt show
up inline, and is the exit code readable on resume?

Capture strategy under test: ``stdout=PIPE``, stderr LEFT ATTACHED to the TTY so
the prompt (and any error) is visible to the user. Press ``s`` to run it.
"""
from __future__ import annotations

import subprocess

from textual.app import App, ComposeResult
from textual.widgets import Footer, Static

CTL = "/home/danitrrga/dev/Projects/nightguard-control/scripts/linux/nightguard_ctl.py"


class SudoSpike(App):
    BINDINGS = [("s", "spike", "Run sudo verify"), ("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Static(
            "Press 's' to run `sudo nightguard_ctl.py verify` inline (read-only).",
            id="out",
        )
        yield Footer()

    def action_spike(self) -> None:
        with self.suspend():
            # stderr is NOT captured — it stays on the TTY so the sudo prompt shows.
            proc = subprocess.run(
                ["sudo", "/usr/bin/python3", CTL, "verify"],
                stdout=subprocess.PIPE,
                text=True,
            )
        lines = (proc.stdout or "").strip().splitlines()
        head = lines[0] if lines else "(no stdout)"
        self.query_one("#out", Static).update(
            f"verify returncode={proc.returncode}\nstdout[0]: {head}"
        )


def main() -> None:
    SudoSpike().run()


if __name__ == "__main__":
    main()
