# Hardening session — 2026-09-07

12 commits on `plan/phase-02-mutation-engine`. Suite went from **87 passed, 3
skipped** to **386 passed, 3 skipped**.

## Deployed and verified live, 2026-09-07 20:13

The deploy ran clean: the terminal UI reinstalled, the bar widget installed, the
config migration reported itself already current (idempotent, as intended), and
the watchdog ticked ok.

Proved against the running stack at 20:14, with the window signed as 05:30-14:00:

| Attempt | Result |
|---|---|
| Push the curfew two hours later | refused, no fingerprint asked |
| Turn app blocking off | refused, no fingerprint asked |
| Widen the edit window itself | refused, no fingerprint asked |
| Pull the curfew ninety minutes earlier | allowed, free |

And the time-cache defence, proved on an isolated copy of the instance so the
live one was never touched: an honest cache resolves 20:14; a cache forged to
claim 10:00 resolves to nothing and the loosening is refused.

The cgroup jail was built and proved too — first as a standalone experiment, then
against the deployed actuator on a harmless process launched for the purpose:

    jail                    /sys/fs/cgroup/nightguard  (outside the delegated subtree)
    victim                  launched as the user, in session-c18.scope
    user moves it out       Permission denied
    user unfreezes it       Permission denied
    user removes the jail   Permission denied
    cgroup.kill             process dead, jail left empty and removable

Your `shell.json` was overwritten by `omarchy-refresh-shell` during this work and
restored from its backup — verified byte-identical, with your nightguard widget
and your clock settings intact.

## What shipped

### 1. Loosening the curfew is refused outside a clock window

Default **05:30–14:00**, configurable, editable from the terminal UI. Outside it,
any change that weakens the curfew is refused *before* the weekly token is
considered and *before* any fingerprint prompt. Tightening is allowed at any hour.
Inside the window a loosening still costs a token — the window is a second gate,
not a replacement.

The gate sits in the quota decision, which is the one function both the root
signer and the pre-auth preview call. That placement is what makes the refusal
visible before you authenticate rather than after.

Four bypasses closed on purpose:

- The window in force is read from the **sanctioned** config, so a commit that
  widens the window is not judged by its own new bounds.
- Deleting the `edit_window` block classifies as a loosening, not the free no-op a
  missing field would otherwise be.
- `commit --rebaseline` writes with no classification and no token charge and is
  reachable through the sudoers wildcard. It is now held to the window too.
- The hour is read in the **signed** timezone from the guard's verified time.
  `sudo -l` on this box grants a passwordless `timedatectl set-timezone`, so
  reading the system zone would have made the window shiftable with one command.

An unresolvable clock refuses the loosening rather than waving it through.

**A hole found after the first deploy, and closed.** The guard caches resolved
time to `/var/lib/nightguard/.timecache`, and that file is owned by you — the same
deliberate choice that keeps `config.yaml` hand-editable so the watchdog can
revert it. The cache is trusted when its boot id matches and its anchor is under
two minutes old, both of which you can satisfy. So at 02:00 you could have written
an entry claiming 10:00 and the gate would have believed it.

The curfew itself was never exposed: a poisoned cache disagrees with the system
clock and reads as tampering, which denies. The edit-window gate skipped that
comparison. It now makes it, so defeating the window needs the system clock moved
too — and that costs a password.

### 2. App blocking, in two modes, that fires only during curfew

You built this once and deleted it on 2026-06-23, because a clock jump at three in
the afternoon made the watchdog kill Steam and Discord in broad daylight. That bug
is now the first test in the file. Nothing is signalled unless the verdict is
exactly `locked`; a tampered or unverifiable clock is a reason to refuse config
changes, never a reason to end applications.

Enforcement is that jail, not a signal loop: apps are moved into a root-owned
cgroup you cannot escape and the tree is killed in one write. A per-process signal
loop loses anything that forks between the scan and the signal, which is what a
game launcher does when you close it. A tick that cannot build the jail falls back
to `SIGTERM` and logs `WEAK MODE`, because a silent downgrade would read as the
strong path having worked.

- **Blocklist mode** (default): end only the apps named.
- **Allowlist mode**: end everything except those named. A hardcoded floor that
  config cannot shrink protects the compositor, quickshell, the portals, pipewire,
  the keyring, and **terminals** — the control TUI launches inside one, so killing
  terminals would have made the curfew unappealable rather than merely strict.
- A cap of 25 processes per tick turns an inverted comparison into a log line
  instead of a dead desktop.

Identity comes from what the kernel owns. `comm` is forgeable — a python process
was renamed to `totally-not-ste` on this box while `exe` stayed truthful — so
matching is on `exe` and install-path prefixes. The cgroup scope name is also
useless as identity: Chromium, Spotify and Antigravity all get scopes named
`app-org.chromium.Chromium-<pid>.scope`.

Games are auto-detected from Steam appmanifests, Heroic's per-store installed
files, and any desktop entry declaring `Categories=Game`, matched by install path
so Proton- and JVM-hosted titles are caught. Rocket League is already there, via
Heroic at `~/Games/Heroic/rocketleague`. Steam's runtimes are filtered out.

**Discord is not a native app on this machine.** It is a chromium webapp sharing
one process with the calendar, the todo list and EL PORTAL — so ending that
process to block Discord would end your allowlist with it. Sites are blocked
instead by `URLBlocklist` in the managed browser policy, which the watchdog
already owns and restores, and which is lifted again outside the curfew. The
`discord` entry in your blacklist has never matched anything and never will.

Claude Code is a 215 MB compiled binary, not a node script. It is matched by its
install path, so blocking it does not take the MCP servers with it.

### 3. A read-only bar widget

Omarchy 4 replaced Waybar with quickshell, and `waybar` is not installed here at
all — so the bar module this project shipped has had no host since the upgrade,
and the refresh signal the TUI sends after every commit has been reaching nobody.

The replacement extends the bar widget you already had, so it opens on click and
behaves like the network and bluetooth panels beside it. A first attempt built a
standalone floating window instead; that was wrong and has been deleted. Being
integrated means living in the bar, and only a shell plugin can do that.

It is built entirely from the shell's own kit — `PanelHero`,
`PanelSectionHeader`, `PanelSeparator`, `Button` — so every colour, size and
margin comes from `Style` and `Color`. Nothing is styled by hand, which is what
makes a theme change repaint it for free and the corner radius follow whatever
Hyprland is set to.

It executes nothing privileged and changes no state. Only the signer may, and it
is reached through the terminal UI; a test asserts the file never mentions sudo,
pkexec, the signer or a commit. It shows counts, not names — it sits where anyone
walking past can read it.

It also warns if you ever end up in the `empower` group: `run0 --empower` makes
every polkit action return YES with no prompt, which silently undoes the rule that
makes stopping the watchdog cost an authentication. You are not in it today.

### 4. Three live bugs found and fixed

- **The TUI has not matched your desktop theme since the Omarchy 4 upgrade.** The
  loader read `~/.config/omarchy/current/theme/colors.toml`; that directory does
  not exist on v4. It now resolves to `~/.local/state/omarchy/…` and picks up
  your real palette.
- **The deploy would have broken the watchdog.** The installer copies a fixed list
  of files; the new blocker module was not on it, so the watchdog would have
  raised `ModuleNotFoundError` every 60 seconds and quietly stopped reverting hand
  edits while the timer still read as active. Fixed, and a test now asserts the
  closure so a module added later is caught by shape rather than by memory.
- **The deploy silently skipped updating the terminal UI.** It tested
  `command -v uv` against *root's* PATH, which does not contain your
  `~/.local/bin`, so it always missed and printed "skipping". That is how the
  machine ended up running a signer that enforced the edit window and a terminal
  UI that knew nothing about it — which would have put a fingerprint prompt in
  front of a refusal, breaking the one rule that says you always see the cost
  first. It now resolves `uv` as you, and says loudly what breaks if it cannot.

## What is NOT done, and why

- **Nobody has looked at the open panel.** The plugin validates, hot-reloads into
  the running shell and produces no QML errors — but its popup only exists once
  clicked, and screenshot capture does not work from an agent context here
  (`grim` hangs on its own). Click it and check.
- **Theme sync is verified by measurement, not by eye.** All 22 installed themes
  were run through the colour mapping and asserted for contrast in both light and
  dark. That proves the values are right; it does not prove the layout looks
  right.
- **App blocking and game blocking ship OFF.** The migration sets blocklist mode,
  games off, no blocked sites — it changes no behaviour by itself. Turning each on
  is your decision, made from the TUI at the usual cost. `blocking.native_apps.enabled`
  is already `true` in your config with `[steam, discord]`, so after deploying,
  Steam *will* be ended during curfew. Discord will not, for the reason above.

## Decisions waiting for you

- **Which sites to block.** `blocking.browser_extension.blocked_urls` is empty.
  Discord, YouTube and the rest go there, not in the app blacklist.
- **Whether to try allowlist mode.** It is implemented and tested, but it ends
  everything unnamed. The floor protects the desktop and your terminals; it will
  still close Obsidian, MATLAB, mpv, Zoom and every unnamed webapp.
- **Whether the jail cgroup is worth building.** It is the difference between "you
  have to think about it" and "you cannot do it without a password".

## Control record

Every safety property was proved able to fail before it was trusted:

| What was neutered | What failed |
|---|---|
| The edit window's hour comparison | 11 tests, including the pre-auth refusal |
| The kill gate, restored to its pre-revert form | 4 tests, including the clock-tamper one |
| The blocker module removed from the install list | 2 tests |

First failure message on the edit window, before any code existed:
`TypeError: quota_decide() got an unexpected keyword argument 'edit_window'`
(26 failed, 1 passed).

Two real bugs were found by tests during the work: the Steam runtime filter read
only the display name and missed `Steam Linux Runtime 3.0 (sniper)`, whose install
directory is `SteamLinuxRuntime_sniper`; and a local variable shadowed the new
theme path helper while referencing a deleted constant, so the no-argument call —
the only one the running app makes — was the sole broken caller.
