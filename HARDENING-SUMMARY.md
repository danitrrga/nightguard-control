# Hardening session — 2026-09-07

Five commits on `plan/phase-02-mutation-engine`. Suite went from **87 passed, 3
skipped** to **260 passed, 3 skipped**. Nothing is deployed: every change is in
the repo and reaches the machine only when you run the deploy command below.

## Run this when you are back

```
sudo /home/danitrrga/dev/Projects/nightguard-control/scripts/linux/deploy.sh
```

It installs the code, runs an idempotent config migration that adds the new
fields, installs the panel, and re-enables the watchdog timer. It re-signs once
during the migration, so `ngtui` will show a fresh config hash afterwards.

Then check the panel:

```
quickshell -p packaging/omarchy/quickshell/nightguard
```

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

### 2. App blocking, in two modes, that fires only during curfew

You built this once and deleted it on 2026-06-23, because a clock jump at three in
the afternoon made the watchdog kill Steam and Discord in broad daylight. That bug
is now the first test in the file. Nothing is signalled unless the verdict is
exactly `locked`; a tampered or unverifiable clock is a reason to refuse config
changes, never a reason to end applications.

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

### 3. A read-only desktop panel

Omarchy 4 replaced Waybar with quickshell, and `waybar` is not installed here at
all — so the bar module this project shipped has had no host since the upgrade,
and the refresh signal the TUI sends after every commit has been reaching nobody.

The replacement is a standalone quickshell process: a 380px card anchored
top-right, in the Omarchy 4 grammar rather than the 875×600 screen-centred window
v3 used. Colours resolve at runtime from the same `colors.toml` the desktop reads.
The font binds to the `monospace` alias, not a family, because you override the
system font. Omarchy's private brand glyphs are not used.

It has **no buttons**. Only the signer may change state, so this is a window and
everything actionable points at the terminal UI. It shows counts, not names —
it sits where anyone walking past can read it.

It also warns if you ever end up in the `empower` group: `run0 --empower` makes
every polkit action return YES with no prompt, which silently undoes the rule that
makes stopping the watchdog cost an authentication. You are not in it today.

### 4. Two live bugs found and fixed

- **The TUI has not matched your desktop theme since the Omarchy 4 upgrade.** The
  loader read `~/.config/omarchy/current/theme/colors.toml`; that directory does
  not exist on v4. It now resolves to `~/.local/state/omarchy/…` and picks up
  your real palette.
- **The deploy would have broken the watchdog.** The installer copies a fixed list
  of files; the new blocker module was not on it, so the watchdog would have
  raised `ModuleNotFoundError` every 60 seconds and quietly stopped reverting hand
  edits while the timer still read as active. Fixed, and a test now asserts the
  closure so a module added later is caught by shape rather than by memory.

## What is NOT done, and why

- **The killer has never run as root.** The decision is a pure, fully tested
  function; the actuator that sends the signal is deliberately thin, and it has
  not been executed with privileges. It sends `SIGTERM`. The research favours a
  root-owned jail cgroup with `cgroup.kill` — genuinely un-escapable by your user
  and fork-race-proof — but creating that cgroup needs a live root experiment this
  session could not run.
- **Nobody has looked at the panel.** The QML loads and instantiates cleanly under
  the live compositor, with no errors. Screenshot capture was unavailable here
  (`grim` hangs on its own in this context), so no pixels were inspected.
- **The panel is not wired into the omarchy installer.** That script is built
  around the Waybar module and its idempotency tests; rewriting it was not
  verifiable here. Run the panel by hand or bind it.
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
