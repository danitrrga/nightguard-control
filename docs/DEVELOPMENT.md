<!-- generated-by: gsd-doc-writer -->
# Development

For somebody changing the code. [ARCHITECTURE.md](ARCHITECTURE.md) explains what the pieces
are and why they sit where they do; this explains how to change them and get the change to
run.

One sentence governs everything below: **the repo is not what runs.**

## 1. The loop

```bash
# edit the repo
sudo scripts/linux/deploy.sh
# the change is live
```

`deploy.sh` is idempotent and does the whole install in one pass. Re-run it after every
change to the trust stack. It says so itself at `scripts/linux/deploy.sh:15-16`.

### Python: nothing you edit runs until you deploy

Root executes from `/usr/local/lib/nightguard`, never from your working tree.
`deploy.sh:98-104` installs six files there as `root:root 0644`:

```
ngcommon.py  guard.py  nightguard_ctl.py  nightguard_watchdog.py  appblock.py  verify_browser_lock.py
```

Editing `scripts/linux/guard.py` therefore changes nothing at all until a deploy — the
watchdog timer still runs the deployed copy, the polkit-authorised signer is still the
deployed copy (`ngtui/ngtui/backend.py:34`, `_DEFAULT_STACK_DIR = "/usr/local/lib/nightguard"`),
and the sudoers entry names that path too. This is not an inconvenience to be worked around:
the unit file used to `ExecStart` out of the working tree, which made a user-writable file
into root code executed every sixty seconds.

`ngtui` is the same shape for a different reason. The panel calls an absolute path,
`Quickshell.env("HOME") + "/.local/bin/ngtui"` (`BarWidget.qml:41`,
`NightguardWriter.qml:36`), and that is a symlink into a **`uv tool` snapshot** — a copy taken
at install time, not an editable install. See §5.

### QML: the exception, with limits

The plugin is installed into the owner's own directory, as the owner
(`deploy.sh:246-253`), and the shell watches it. `PluginRegistry.qml:636-650` runs

```
inotifywait -m -r -q -e close_write,create,delete,move --format %w%f ~/.config/omarchy/plugins
```

and any event under a plugin directory fires `localPluginChanged`, which (after a 150 ms
debounce, `shell.qml:60-64`) calls `reloadPlugins()`. That function
(`/usr/share/omarchy/shell/shell.qml:739-759`) unloads every plugin panel, service and bar
widget, calls `Qt.clearComponentCache()`, and rescans.

What the reload does **not** pick up:

| Change | Picked up by the plugin reload? | What you need |
|---|---|---|
| A `.qml` or `manifest.json` in `~/.config/omarchy/plugins/danitrrga.nightguard` | Yes | nothing |
| The same file **in the repo** | **No** — the watch is on the deployed directory only | `sudo scripts/linux/deploy.sh` |
| `scripts/linux/*.py` | No | `sudo scripts/linux/deploy.sh` |
| `ngtui/ngtui/*.py` | No | `uv tool install --force ./ngtui` (or a deploy) |
| The shell's own kit, `/usr/share/omarchy/shell/Ui/*.qml`, or `shell.qml` | **No** — Quickshell's file watcher is off (`QS_DISABLE_FILE_WATCHER=1`, `/usr/bin/omarchy-launch-shell`) | `omarchy-restart-shell` |

Also worth knowing before you reload: `unloadPanels()` (`shell.qml:533-539`) calls `hide(id)`
on every open panel. An open workshop window closes and its staged ops go with it.

Forcing a reload without touching a file:

```bash
omarchy-shell shell rescanPlugins     # IPC handler at shell.qml:890-892 -> reloadPlugins()
omarchy-restart-shell                 # kills and respawns the whole shell
```

Use `rescanPlugins` for plugin QML. Use `omarchy-restart-shell` when you changed nothing in
the plugin and the plugin still misbehaves — a stale singleton, a shell-kit change, or a
reload that left the widget unregistered.

### Seeing the error

The shell runs under `systemd-cat -t omarchy-shell`, so its log is the user journal:

```bash
journalctl --user -t omarchy-shell -f
```

A QML error appears **once**, quietly, at load, as a `console.warn` from
`loadPluginWidget` (`shell.qml:797-802`):

```
Plugin widget danitrrga.nightguard failed: <errorString>
```

There is no second chance and no on-screen symptom beyond a blank widget or a component that
"is not a type". If a surface went missing, the journal line from the moment it reloaded is
the only place the reason exists.

## 2. Layout of the tree

| Path | What lives there |
|---|---|
| `scripts/linux/` | The trust stack in source form — the signer, the guard library, the watchdog, the app blocker, the minimal YAML parser, plus `deploy.sh` and the sudoers template. Nothing here executes; `deploy.sh` installs it to `/usr/local/lib/nightguard`. |
| `scripts/linux/systemd/`, `scripts/linux/polkit/` | The watchdog unit and timer, and the rule that raises "stop the watchdog" to `AUTH_ADMIN`. Installed to `/etc/systemd/system` and `/etc/polkit-1/rules.d`. |
| `ngtui/ngtui/` | The unprivileged, dependency-free CLI the panel runs. `backend.py` is the only seam to the trust stack; `proposal.py`/`lineedit.py` compose edits; `panel.py`/`status.py`/`catalog.py`/`theme.py` shape what the surfaces read. |
| `ngtui/tests/` | The contract — 570 tests. See §9. |
| `packaging/omarchy/` | The shell plugin (`plugins/danitrrga.nightguard/*.qml` + `manifest.json`), the `.desktop` launcher entry, the icon, and a Hyprland window rule. |
| `docs/` | This file, `ARCHITECTURE.md`, `CONFIGURATION.md`, `browser-lock.md`. Files dated June 2026 (`design-spec.md`, `linux-port-brief.md`, `2026-06-04-nightguard-control-design.md`) describe the retired Windows product; they are records, not instructions. |
| `.planning/` | Phase artefacts, roadmap, requirements and session state for the GSD workflow. Not shipped, not read at runtime. |

## 3. The rules that are not style

Each of these has a reason and a place where it is enforced. Breaking one does not produce a
lint warning; it produces a tool that quietly stops binding.

### Never emit YAML

Edits are line edits. `ngtui/ngtui/lineedit.py:1-20` states the rule as a hard rule, and it
is the only place in the codebase allowed to turn a staged edit into bytes.

The signature covers the file's **bytes**, not its parsed values
(`ngcommon.config_hmac`, `scripts/linux/ngcommon.py:81-88`). Re-serialising through any YAML
library — pyyaml, ruamel, anything — reorders keys, drops comments and rewrites quoting. The
result parses to exactly the same values and hashes to a different digest, so the watchdog
sees the live config diverge from the signed one and reverts the user's own commit within
the minute. The signer's `canonicalize` (`nightguard_ctl.py:74-79`) only normalises BOM, line
endings and the trailing newline; it will not rescue a reformatted file.

Practically: if you need a new kind of edit, add it to `lineedit.py` as an operation that
touches only the addressed line, and leave every other byte identical. `_rebuild_scalar_line`
(`lineedit.py:122`) is the model — it preserves the indent, the key, the inline `# comment`
and the original quote style.

### Blocking identity is the exact basename of `/proc/PID/exe`

`matches_identity` (`scripts/linux/appblock.py:154-184`) is the only identity test, and a
bare entry matches `_basename(proc.exe) == identity` (line 174) — exact, never a substring,
never `comm`.

`comm` is absent from the `Process` class on purpose (`appblock.py:108-115`):
`prctl(PR_SET_NAME)` lets a process rename itself to anything its owner likes. Substring
matching is worse than useless in the other direction: `portal` would match
`xdg-desktop-portal`, and a root process ending that breaks every file picker on the desktop
while the webapp the user actually meant keeps running.

An entry beginning with `/` is matched as an exact path or a path **prefix**, which is how
Proton- and JVM-hosted games are reached — their `exe` is the loader, not the game.

### `pkexec` sets `PKEXEC_UID`, never `SUDO_UID`

If you write code that needs to know who is on the other side of an authorisation, read
`PKEXEC_UID` first. `_config_owner` does exactly that at `nightguard_ctl.py:515`:

```python
uid = os.environ.get("PKEXEC_UID") or os.environ.get("SUDO_UID")
```

An earlier `SUDO_UID`-only version silently stopped chowning `config.yaml` back to the user
the moment the panel started authorising through polkit instead of sudo — no error, no log
line, just a config the user could no longer hand-edit.

**126 and 127 are answers, not failures.** `pkexec` returns 126 when the user dismissed the
authentication dialog and 127 when they were not authorised or the program could not be run.
The signer's own codes are 0/1/2, so the two ranges do not overlap
(`backend.commit_proposal`, `ngtui/ngtui/backend.py:255-258`). That separation is the only
thing that lets the panel tell a user who *chose* to cancel apart from one who was refused —
`NightguardWriter.report` (`NightguardWriter.qml:239-278`) gives them two different sentences.
Never collapse a non-zero exit into "it failed".

### `config.yaml` stays user-owned on purpose

`deploy.sh:138-150` chowns it back to the owner on every run, and the signer chowns it back
after every write (`nightguard_ctl.py:529-543`). Two reasons, both in `_config_owner`'s
docstring (`nightguard_ctl.py:478-507`):

1. The product's claim is that a hand edit is **undone**, not blocked. A root-owned config
   would make the edit fail with a permission error — a different and weaker promise, and one
   that never exercises the revert path.
2. `nightguard_watchdog.py:31-39` derives the owner's home from `config.yaml`'s owner
   (`pwd.getpwuid(os.stat(ng.CONFIG).st_uid).pw_dir`), and that home is where the Steam and
   Heroic catalogs are read from. A root-owned config points the game catalog at `/root`,
   where there are no games, and game blocking silently stops covering anything.

The security boundary is the **directory**, not the file: `/var/lib/nightguard` is
`root:root 0755` (`deploy.sh:121-124`), because rename and unlink are governed by the
directory's mode (`ngcommon.py:22-26`). A side effect worth knowing while you develop
(`deploy.sh:139-141`): editors that save by writing a temp file and renaming it over the
original **cannot** write `config.yaml`, because that rename needs write permission on the
directory. In-place edits work.

### No fixed hex in the QML

Every colour comes from the shell's `Color` and `Style` singletons (`import qs.Commons`) so
the surface follows the user's live theme. There is no Nightguard palette.

Enforced by `ngtui/tests/test_no_fixed_hex.py:62` —
`test_no_literal_hex_in_any_of_the_plugin_qml` — which scans every `*.qml` in the plugin
directory, with comments stripped, for `#RGB`/`#RGBA`/`#RRGGBB`/`#RRGGBBAA`. Its companion,
`test_the_scan_catches_an_injected_hex` (line 76), is the control: it injects `#7aa2f7` — the
retired Moonlit Indigo accent — into an in-memory copy and asserts the scan finds it. The
first test also refuses to pass over an empty or renamed directory.

## 4. Working on the QML

Seven files in `packaging/omarchy/plugins/danitrrga.nightguard/`, all of them this plugin's
own:

| File | What it is |
|---|---|
| `BarWidget.qml` | The bar icon. Extends the shell kit's `BarWidget`. |
| `NightguardPanel.qml` | The dropdown the bar icon opens. |
| `NightguardWorkshop.qml` | The window — the `panel`-kind entry point. |
| `NightguardGlance.qml` | The workshop's landing view. |
| `NightguardClock.qml` | Headless. The single reading of the hours. |
| `DayDial.qml` | The single drawing of the 24-hour ring. |
| `NightguardWriter.qml` | The one write path; both editing surfaces instantiate it. |

### What comes from the shell kit

Everything else is `/usr/share/omarchy/shell/Ui/` (`import qs.Ui`) and
`/usr/share/omarchy/shell/Commons/` (`import qs.Commons`, for `Color`, `Style`, `Border`,
`Util`). In use today: `BarWidget`, `BarIconButton`, `Panel`, `PanelHero`,
`PanelSectionHeader`, `PanelSeparator`, `PanelActionButton`, `PanelKeyCatcher`, `Button`,
`TextField`, `Toggle`, `ToggleSwitch`, `ConfirmDialog`. Read the source of a component before
using it — it is on disk, and it is the only documentation there is.

`NightguardClock.qml` and `DayDial.qml` exist because the dropdown and the window each
computed the hours and each drew the ring, and the two copies immediately disagreed — one
rounding to hours, one to minutes. Do not re-inline either;
`ngtui/tests/test_qml_composition.py:29` and `:47` refuse a second implementation of the arc
or of `humanDuration`.

### Two traps that cost real time

**`PanelActionButton` has `iconText`, not `icon`.** The property is declared at
`/usr/share/omarchy/shell/Ui/PanelActionButton.qml:30` and rendered at line 74. An unknown
property in QML is a load-time error, so `icon:` takes the whole component down with a single
warn line in the journal. Both existing uses are correct
(`NightguardPanel.qml:637`, `NightguardWorkshop.qml:692`).

**`ToggleSwitch` emits `toggled()`, not `clicked()`.** The only signals it declares are
`toggled()` and `hovered(bool)` (`Ui/ToggleSwitch.qml:46-47`); the internal MouseArea's
`onClicked` is what re-emits `toggled()` (line 109). Writing `onClicked:` on a `ToggleSwitch`
is an error on a component that has no such signal. Note the sibling: `Ui/Toggle.qml:37` does
declare `clicked()` — the two are not interchangeable, and the plugin uses both.

### The layout trap

A wrapping `Text` inside an **anchored** `Row` grows what is drawn without growing the
`implicitHeight` the enclosing `Column` sums. The Column then reports a height smaller than
its own contents, and whatever sizes the popup from that number sizes it too small — with no
scrollbar to hint that anything was cut. Measured when it happened: the panel asked for 588
logical pixels against a cap that allowed 607, so it was never being clamped; it was
measuring itself wrong, and the sites card and both action buttons fell off the bottom.

The guard is `ngtui/tests/test_deploy_completeness.py:265`,
`test_no_wrapping_text_hides_its_height_from_the_layout`. It refuses two things across every
`*.qml` in the plugin:

- **any `description:` line at all** — `Toggle` lays its `description` out inside an anchored
  Row, so the caption must be a sibling `Text` the Column lays out itself;
- **any `wrapMode: Text.WordWrap` without an explicit `width:` above it**, inside the same
  `Text {` block. It walks backwards to the opening `Text {` rather than a fixed number of
  lines, because a multi-line `color: { ... }` switch sits happily in between and a short
  window read that as a missing width (it did, on the first run).

With an explicit width the Text resolves its own height before anything sums it, and the
class of bug cannot return.

## 5. The CLI

`ngtui` is a `uv tool` install — a **snapshot** of `ngtui/`, not an editable one:

```bash
uv tool install --force ./ngtui
```

`deploy.sh:205-232` runs exactly that, as the owner. It resolves `uv` via
`runuser -u "$OWNER" -- bash -lc 'command -v uv'` rather than root's `PATH`, because root's
`PATH` does not contain `~/.local/bin` and the check therefore always missed — the CLI went
un-reinstalled for a long time. That is not cosmetic: the CLI carries the pre-authentication
preview, so a stale copy shows "allowed, 1 token" for a change the new signer will refuse,
putting a password prompt in front of a refusal.

So: **a source change in `ngtui/ngtui/` needs `uv tool install --force ./ngtui` or a full
deploy before the panel sees it.** Running `python -m ngtui` from the repo exercises your
edit; the panel does not.

### The contract every subcommand keeps

Five subcommands, and each one **exits 0 with exactly one line of JSON on stdout**:

```
ngtui status --json           the bar icon's cheap poll
ngtui panel                   the whole desktop state
ngtui apps                    the blockable-app catalog
ngtui propose --ops-json ...  apply staged edits, price them, write nothing
ngtui commit --from <path>    pkexec -> the root signer
```

The reason is at `ngtui/ngtui/__main__.py:1-11`: the caller is a QML `Process`, which sees a
stream and an exit status and nothing more. A non-zero exit is indistinguishable from a
missing binary, a broken `PATH`, or a crash — so failure has to be reported **as data, inside
the JSON**, never as status. `_status` (`__main__.py:70-97`) is the shape to copy: the
`import ngtui.backend` is inside the try-block (it can raise `RuntimeError` at import on a
bad `NIGHTGUARD_STACK_DIR`), the except is broad on purpose, and every failure path collapses
to the fixed `UNAVAILABLE` object rather than a partial one — a partial panel reads as a true
one.

`ngtui commit` follows the same rule at the boundary that matters most: it always exits 0 and
returns the signer's own code *inside* the JSON (`__main__.py:501-511`).

A bare `ngtui` exits 2 with a sentence explaining that the terminal editor is retired
(`__main__.py:49-67`) — for stale `.desktop` files and muscle memory.

## 6. Changing what the signer will accept

Two lists, in two files, that must change together:

| List | File | Decides |
|---|---|---|
| `FIELD_TABLE` | `scripts/linux/nightguard_ctl.py:45-69` | Which keys the signer classifies, and with what polarity (`bool`, `num`, `list_add`, `list_remove`, `mode`, `any`) — i.e. what a change to that key *costs*. |
| `EDITABLE` | `ngtui/ngtui/proposal.py:37-71` | Which keys the panel may touch, and with what kind (so a list op on a boolean is refused rather than producing nonsense). |

Adding a field to the panel means adding it to **both**. Adding it to `EDITABLE` alone is the
dangerous direction.

The parity test is `ngtui/tests/test_parity.py:123`,
`test_every_editable_key_is_one_the_signer_classifies`. It imports `nightguard_ctl`, collects
every label in `FIELD_TABLE`, adds the keys the signer judges jointly rather than
individually (`curfew.start`/`curfew.end`/`curfew.window`, and the three `edit_window.*` keys
— see `_classify_edit_window`, `nightguard_ctl.py:235`), and asserts that nothing in
`EDITABLE` is left unclassified.

### The failure mode a mismatch produces

A key in `EDITABLE` with no entry in `FIELD_TABLE` gets **no direction** from
`classify_change`. `quota_decide` (`nightguard_ctl.py:424`) then sees nothing loosening,
allows the change for free, and `_write_commit` writes it. The cost line the user read was
honest about a classification that never happened.

That is not hypothetical. `blocking.browser_extension.extension_id` is deliberately absent
from `EDITABLE` — the comment at `proposal.py:56-70` says why, and
`test_parity.py:74` (`test_the_one_field_left_behind_is_one_the_signer_cannot_judge`) pins the
exception in place and will fail the moment the signer *does* learn a direction for it.
Pointing the managed browser policy at a different or non-existent extension is how site
blocking gets switched off entirely, and "free and unjudged" is the wrong answer for that
twice over.

Giving a key a direction changes what costs a weekly token. That is the owner's decision, not
a side effect of adding a control.

## 7. Things that are deliberately awkward

Do not smooth these out.

- **The password prompt on every commit.** `pkexec` caches nothing under
  `org.freedesktop.policykit.exec` — two back-to-back calls each open a fresh PAM session
  (`backend.py:243-247`). The friction is the anti-impulse mechanism, and it arrives for free.
- **The confirmation dialog starts on Cancel.** `selectedIndex: 0` at
  `NightguardPanel.qml:275` and `NightguardWorkshop.qml:1502`, against the kit's default of 1
  (`Ui/ConfirmDialog.qml:11`), because the default answer to "do you want to weaken this?" at
  two in the morning is no.
- **No single keystroke confirms.** In the dropdown, `PanelKeyCatcher`
  (`NightguardPanel.qml:282-312`) routes Esc to cancel and nothing at all to confirm; `a` is
  deliberately not bound. In the workshop, keys are forwarded to `ConfirmDialog.handleKey`
  (`NightguardWorkshop.qml:730-735`), where Enter on the default selection *cancels* — saying
  yes takes a Tab and then Enter, or a click. One unmodified keystroke that ends in an
  authorised write is the exact impulse the product exists to slow down.
- **The uninstall is not a script.** README.md:159-171 lists four commands to type. Removing
  the thing that stops you removing it should take more than one command at two in the
  morning.
- **The edit window refuses a loosening outside its hours, before the tokens are even
  consulted** (`_edit_window_refusal`, `nightguard_ctl.py:400-421`). A weekly allowance limits
  how *often* you give in, not *when*, and the hour your judgement is worst is the hour you
  reach for it. A malformed window and an unverifiable clock are both refusals too — fail
  closed, because an unverifiable clock is exactly the state an attacker would engineer.

## 8. Conventions

### Commits

Conventional prefix, then a subject that says what changed about the world rather than which
files moved:

```
fix: stop the panel being personal, and stop advertising a bypass that is not there
feat(panel): give Nightguard a landing screen, and stop drawing the hours twice
test(panel): a wrapped line the layout cannot see is a popup that lies about its height
```

Lowercase, no trailing full stop. Scopes in use: `panel`, `workshop`, `deploy`, `migration`,
`state`, and phase numbers for planning commits (`docs(12.2.1)`).

The body is the point, and it is long. Read `git log` for the shape. It explains **why**, names
the defect that existed rather than the feature that was added, records what was measured, and
ends with two things:

- a list of the guards added, **each proved able to fail** — see `4ce3f41`, which lists three
  and says how each was broken to check it;
- the suite result (`566 passed, 4 skipped`) and whether the plugin was redeployed.

A commit that corrects a claim in a doc says so, including when the author's own check was
worthless — `4ce3f41`'s body records that a grep for a personal path was piped through
`grep -v danitrrga.nightguard`, which deleted every matching line because that is the plugin
directory's name.

### A test that has never been seen to fail is not evidence

This is a standing rule, not a preference. Every guard gets a negative control, and the
control stays in the tree. `test_no_fixed_hex.py:76` is the worked example: it injects the
exact class of value the ban exists to keep out and asserts the scan catches it. Its docstring
says the reason in one line — "A scan that has never been seen to find anything is not
evidence."

When you add a check, break it once, record the failure message in the commit body, and leave
the control behind.

## 9. Running the tests

```bash
cd ngtui && uv run --with pytest python -m pytest -q
```

570 tests as of this writing. Configuration is in `ngtui/pyproject.toml`
(`pythonpath = ["."]`, `testpaths = ["tests"]`), so the in-tree `ngtui` package resolves
without an editable install.

**One thing you will hit on a fresh clone.** Several tests import the trust stack directly
(`import nightguard_ctl as ctl` in `test_parity.py:86` and `:127`), and the path comes from
`NIGHTGUARD_STACK_DIR`. `ngtui/tests/conftest.py:13-18` `setdefault`s it to a hardcoded author
path. If your clone is anywhere else, set it yourself:

```bash
cd ngtui
NIGHTGUARD_STACK_DIR="$(cd .. && pwd)/scripts/linux" \
  uv run --with pytest python -m pytest -q
```

Proved by pointing it elsewhere: `NIGHTGUARD_STACK_DIR=/nonexistent/elsewhere` turns
`test_parity.py` into `2 failed, 2 passed, 1 skipped` with
`ModuleNotFoundError: No module named 'nightguard_ctl'`.

Note which copy that variable selects. Pointed at `scripts/linux`, the suite tests **your
edit**. Pointed at `/usr/local/lib/nightguard` (the runtime default, `backend.py:34`), it
tests the deployed copy. Those are different files until you deploy, which is the whole of §1
restated as a test-runner flag.

### The proof that is not a unit test

```bash
python3 /usr/local/lib/nightguard/verify_browser_lock.py
```

Runs as you, no root needed. It starts each Gecko browser headless and reads back *which*
`policies.json` was actually used (`deploy.sh:338-341`). A policy file sitting in a directory
the browser ignores is what the previous setup had, and no amount of unit testing sees that.
