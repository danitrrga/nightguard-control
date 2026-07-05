"""_run_sudo_pty: the PTY runner that lets PAM's interactive auth (fingerprint) work.

These exercise the real PTY machinery with harmless commands (no sudo): output capture,
exit-code propagation, cooperative cancel, and the timeout guard. The fingerprint touch
itself is hardware and human — covered by the argv/contract tests + manual verification.
"""
from __future__ import annotations

import threading
import time

from ngtui import backend


def test_captures_output_and_zero_rc():
    rc, out = backend._run_sudo_pty(["sh", "-c", "printf 'hello-from-pty'; exit 0"])
    assert rc == 0
    assert "hello-from-pty" in out


def test_propagates_nonzero_rc():
    rc, _out = backend._run_sudo_pty(["sh", "-c", "exit 7"])
    assert rc == 7


def test_cancel_event_aborts_with_130():
    ev = threading.Event()

    def cancel_soon():
        time.sleep(0.5)
        ev.set()

    t = threading.Thread(target=cancel_soon)
    t.start()
    start = time.monotonic()
    rc, _out = backend._run_sudo_pty(["sh", "-c", "sleep 30"], cancel_event=ev)
    t.join()
    assert rc == 130, "a cancelled authorisation must return 130"
    assert time.monotonic() - start < 5, "cancel must abort promptly, not wait out the child"


def test_timeout_returns_124():
    start = time.monotonic()
    rc, _out = backend._run_sudo_pty(["sh", "-c", "sleep 30"], timeout=0.6)
    assert rc == 124, "an unanswered prompt must time out to 124"
    assert time.monotonic() - start < 5, "timeout must fire near the deadline"


def test_status_cb_receives_streamed_output():
    seen = []
    backend._run_sudo_pty(
        ["sh", "-c", "printf 'touch-the-sensor'; exit 0"],
        status_cb=lambda text: seen.append(text),
    )
    assert any("touch-the-sensor" in s for s in seen), "status_cb must receive the live PTY text"
