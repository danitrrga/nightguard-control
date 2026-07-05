---
status: fixing
trigger: "When I hit commit in the Nightguard TUI launched from walker, the change doesn't take effect and the window renders mostly empty / freezes."
created: 2026-07-05
updated: 2026-07-05
slug: commit-freeze-launcher-sudo
root_cause: "commit() ran sudo synchronously ON the Textual event loop, and the sudo password prompt had no usable input: (1) the inline prompt needed App.suspend() which is broken in the walker-launched Wayland float; (2) the sudo -A GUI askpass hung because `walker -x -I` never returns (exit 124). Either way subprocess.run blocked the event loop forever = permanent UI freeze."
fix: "Run the exact `sudo … commit` inside a freshly-spawned terminal (xdg-terminal-exec -e sh -c) so the password prompt has a native TTY; capture the exit code/output via temp .rc/.out files. Run it in a Textual thread worker so the event loop is never blocked. Removes App.suspend() and all GUI-askpass dependency."
---

# Debug: commit freezes in launcher-spawned window

## Symptoms

- **Expected:** Staging a loosen edit and pressing `y` to commit signs + writes the config (spends a token) and returns to the TUI; the Waybar module refreshes.
- **Actual:** The commit "doesn't take effect" and the launched floating window shows a near-empty dark screen with a small bordered box in the top-left; it appears frozen.
- **Error messages:** None surfaced to the user (no traceback).
- **Timeline:** Was human-approved during Phase 12 live verification (step 5, commit-refresh). Now freezes. Likely NOT a true regression — see Evidence (sudo cred caching).
- **Reproduction:** Launch "Nightguard Control" from walker (`.desktop` → `xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui`), edit (`e`) → stage a loosen → press `y`.
- **Screenshot:** near-empty slate window, small rounded-border box top-left (the suspended terminal state).

## Current Focus

- **hypothesis:** On `y`, `EditScreen.action_do_commit` runs `with self.app.suspend(): backend.commit(...)`, which invokes `sudo /usr/bin/python3 .../nightguard_ctl.py commit --from <tmp>`. The sudoers entry for `commit` is **NOT** `NOPASSWD`, so `sudo` prompts for a password. In the walker-launched Alacritty float (a fresh terminal with no cached sudo creds), the inline password prompt during `App.suspend()` is not being completed → `sudo` hangs → the commit never lands. It "worked" at verification because sudo creds were cached then (no prompt).
- **next_action:** BLOCKED on human manual_test (checkpoint emitted). Code state re-confirmed; the fix branch is undecidable headlessly. Awaiting: launch from walker, stage a loosen, press `y`, then **type the sudo password blind + Enter** — does the commit complete? This splits the fix (invisible-but-working prompt → loud banner fix in `edit.py`; vs broken tty handoff → SUDO_ASKPASS GUI dialog, needs author sign-off).
- **test:** blind-type password on the frozen screen (delegated to human — checkpoint_type: manual_test).
- **expecting:** either "commit completes / token spent / returns to TUI" (prompt present but invisible) or "still frozen" (tty handoff broken).

## Evidence

- timestamp: 2026-07-05 — `command -v ngtui` → `/home/danitrrga/.local/bin/ngtui` (installed uv tool). `ngtui status --json` returns real data `{"text":"○ 3",...,"class":"outside_curfew"}` exit 0 — the key-less path + trust-stack resolution are healthy.
- timestamp: 2026-07-05 — Installed package **does** ship `app.tcss` (4017 bytes, matches repo) at `~/.local/share/uv/tools/ngtui/lib/python3.14/site-packages/ngtui/app.tcss`. CSS-missing theory ELIMINATED.
- timestamp: 2026-07-05 — Ran the **installed** `ngtui` under a controlled PTY at 110×32: renders FULLY (hero, status-word `success`, countdown, kv rows, panels, footer; keywords OPEN/tokens/curfew/grace present), no traceback. App itself is fine.
- timestamp: 2026-07-05 — Launched the **real** `.desktop` path (`xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui`) with `TEXTUAL_LOG`: Textual detected `Size(width=117, height=39)` and StatusScreen laid out fully. So the launched float renders CORRECTLY too (before commit). Terminal-size/SIGWINCH theory ELIMINATED.
- timestamp: 2026-07-05 — sudoers (`sudo -n -l`): `(root) /usr/bin/python3 /home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_ctl.py commit *, ...verify` — **no `NOPASSWD`** → commit prompts for a password (the intentional anti-impulse friction).
- timestamp: 2026-07-05 — `sudo -n true` → FAILS → creds NOT currently cached → a commit right now WILL prompt. Supports the "cached-at-verification, prompts-now" explanation.
- timestamp: 2026-07-05 — `backend.commit()` (`ngtui/ngtui/backend.py:185`): `subprocess.run(["sudo","/usr/bin/python3",CTL_SCRIPT,"commit","--from",tmp], stdout=subprocess.PIPE, text=True)` — stdout captured, **stderr left on the tty** (prompt), stdin inherited; wrapped by `with self.app.suspend()` in `EditScreen.action_do_commit` (`ngtui/ngtui/widgets/edit.py:202-213`).
- timestamp: 2026-07-05 — **MANUAL TEST RESULT (human):** launched from walker, staged a loosen, pressed `y`, typed the sudo password blind + Enter → **STILL FROZEN**, commit did not complete. This confirms the fix fork = the TTY handoff itself is broken (not merely an invisible prompt). Fix = GUI askpass, NOT a terminal banner.
- timestamp: 2026-07-05 — Available GUI password tools on the box: `zenity`, `walker` (has `-x/--password` + `-I/--inputonly` dmenu mode — omarchy-native), `systemd-ask-password`. Plan: a SUDO_ASKPASS helper that reads the password via a masked GUI prompt; `backend.commit()` calls `sudo -A …` and no longer needs `App.suspend()`.
- timestamp: 2026-07-05 — Re-confirmed the exact code state before delegating the interactive test. `backend.py:185-197`: `subprocess.run` sets ONLY `stdout=subprocess.PIPE` + `text=True`; stdin/stderr are inherited (TTY). Docstring (`backend.py:175-179`) states stderr is *intentionally* left on the TTY so the sudo prompt reaches the user (Pitfall 3). `edit.py:207-209`: comment "Release the TTY so sudo's password/fingerprint prompt is inline (D-08)" then `with self.app.suspend(): res = backend.commit(...)`. So the design INTENT is an inline prompt; the bug is that in the walker float it is not visibly reaching the user. This is exactly the fork the manual test resolves — no further headless observation can distinguish "invisible prompt" from "broken tty handoff".

- timestamp: 2026-07-05 — **The sudo -A askpass fix DID NOT work — same freeze.** Probes: `walker -x -I -p probe` (empty stdin) → exit 124 (HANGS, returns nothing), so `sudo -A` waits on it forever. `action_do_commit` calls `backend.commit()` SYNCHRONOUSLY on the event loop → the hang froze the whole UI. The "empty box" screenshot is the dead event loop, not a password prompt. walker gapplication-service IS running (pid 1320) — walker's dmenu/password mode is simply the wrong askpass tool.
- timestamp: 2026-07-05 — **Validated the reliable mechanism end-to-end:** `xdg-terminal-exec -e sh -c '<cmd> > out; echo $? > rc'` spawns a real terminal, runs the command, and the exit code + output are captured via temp files (verified with a plain echo AND with `sudo -n … verify` → rc=1, "sudo: a password is required"). A real terminal gives sudo a working TTY prompt — the one thing that reliably works. Reworked commit() to use it, in a Textual `@work(thread=True)` worker so the event loop can never block. 79 tests pass.

## Eliminated

- hypothesis: Missing `app.tcss` in the installed wheel → unstyled tiny render. ELIMINATED — file is present and identical to repo.
- hypothesis: Terminal-size / SIGWINCH race in the launched float gives Textual a tiny size. ELIMINATED — real launched window reports 117×39 and lays out fully.
- hypothesis: Trust-stack unreachable in the launched env → degraded StatusScreen. ELIMINATED — status path returns real data; launched render is full.

## Key files

- `ngtui/ngtui/widgets/edit.py` — `EditScreen.action_do_commit` (`with app.suspend(): backend.commit(...)`), the confirm gate.
- `ngtui/ngtui/backend.py` — `commit()` sudo argv + subprocess handling.
- `packaging/omarchy/nightguard.desktop` — `xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui`.
- sudoers: `/etc/sudoers.d/*` (nightguard_ctl commit is password-required).

## Open fix decision (needs the interactive test above)

- **If blind-typing the password completes the commit** → prompt is present but invisible/unclear in the suspended float. Fix: show a loud "🔒 enter your sudo password in the terminal" state before/around the suspend so the user knows it's waiting (small change in `edit.py`).
- **If it stays frozen** → the tty handoff itself is broken for the launched terminal. Fix: route the password via `SUDO_ASKPASS` + a GUI dialog (rofi/walker/gtk askpass) so a launched app never depends on an invisible terminal prompt. Larger change; touches the "sudo = the friction" model → needs author sign-off.
