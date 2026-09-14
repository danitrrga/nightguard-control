<!-- generated-by: gsd-doc-writer -->
# Testing

570 tests. They are not unit tests of functions. Almost every one of them is a guard against
a defect that was actually in this tree, and its docstring names that defect.

Measured 2026-09-14 on the author's box:

```
$ cd ngtui && uv run --with pytest python -m pytest -q
566 passed, 4 skipped in 3.58s
```

## Where the tests are, and why scanners miss them

They are in `ngtui/tests/`, next to the package they cover. The repository root has no
`tests/` directory, no `pyproject.toml`, no `setup.py`, no `Makefile`, no `package.json` and
no `.github/`. Every Python project marker in this repo lives one level down, in `ngtui/`.

A tool that looks for tests at the repository root finds nothing and reports "no tests". This
project's own `docs-init` detector did exactly that. It is wrong by 570.

```
nightguard-control/
  scripts/linux/              the trust stack — no tests of its own live here
  packaging/omarchy/plugins/  the QML — read as text by tests in ngtui/tests/
  ngtui/
    pyproject.toml            <- the only Python project file in the repo
    tests/                    <- the only test directory in the repo
```

`ngtui/pyproject.toml` pins `testpaths = ["tests"]` and `pythonpath = ["."]`, both relative to
`ngtui/`. That is why the suite must be run from `ngtui/` and not from the root — see below.

## Running them

```bash
cd ngtui && uv run --with pytest python -m pytest -q
```

One file, one test, and a substring filter:

```bash
cd ngtui
uv run --with pytest python -m pytest -q tests/test_lineedit.py
uv run --with pytest python -m pytest -q tests/test_lineedit.py::test_round_trip_changes_only_targeted_field
uv run --with pytest python -m pytest -q -k "window"        # 62 passed, 508 deselected
```

Add `-rs` to print the skip reasons, `-v` for one line per test, `-x` to stop at the first
failure.

### Running from the repository root does not work

```
$ uv run --with pytest python -m pytest -q
21 errors in 0.71s
```

`pythonpath = ["."]` resolves to the root, where there is no `ngtui` package to import. `cd
ngtui` first.

### The suite needs `textual`, and nothing declares it

`ngtui/pyproject.toml:6` says `dependencies = []` with the comment "nothing here needs
textual". `ngtui/ngtui/theme.py:39` does:

```python
from textual.theme import Theme
```

On the author's box the suite passes because `ngtui/.venv` still contains a leftover
`textual 8.2.7` from the retired terminal app. `uv.lock` does not mention it. On a fresh
clone the same command gives:

```
ERROR tests/test_theme.py
ERROR tests/test_theme_roles.py
ERROR tests/test_theme_sync.py
!!!!!!!!!!!!!!!!!!! Interrupted: 3 errors during collection !!!!!!!!!!!!!!!!!!!!
ModuleNotFoundError: No module named 'textual'
```

Those three files are 210 of the 570 tests. Until the dependency is declared or `theme.py`
stops importing Textual, a fresh clone runs:

```bash
cd ngtui && uv run --with pytest --with textual python -m pytest -q
```

## What the suite actually is

| File | Tests | What it defends |
| --- | ---: | --- |
| **The trust model** | | |
| `test_port03_no_crypto.py` | 3 | No file under `ngtui/ngtui/` imports `hmac`/`hashlib`, calls `read_key()`, or calls `digest`/`hexdigest`. The panel never holds the key. |
| `test_port02_commit_argv.py` | 6 | `commit()` builds exactly `sudo -k /usr/bin/python3 <abs ctl.py> commit --from <tmp>`: config passed as an absolute file path, never inline, no password anywhere in argv, temp file cleaned up. |
| `test_port02_preview_seam.py` | 4 | `preview_change` calls the *same function objects* as the live `nightguard_ctl`, so the preview cannot drift from the signer. 3 of the 4 are skipped — see below. |
| `test_backend_stackdir.py` | 4 | `_resolve_stack_dir` fails closed when `NIGHTGUARD_STACK_DIR` points at a directory without `nightguard_ctl.py`, rather than letting a substituted stack onto `sys.path` and into the sudo argv. |
| `test_run_sudo_pty.py` | 5 | The PTY runner exercised with harmless commands: output capture, exit-code propagation, cooperative cancel, timeout. |
| `test_backend_signal.py` | 5 | `commit()` fires the bar refresh once on success, never on failure, and a raising `pkill` is swallowed. |
| `test_commit_output_welding.py` | 6 | `\r` is a line terminator and the result line is sliced from its keyword, so sudo's session audit record cannot ride along on it. |
| `test_config_ownership.py` | 7 | `config.yaml` comes back to the user however root was obtained — `PKEXEC_UID` as well as `SUDO_UID` — and the owner is read *before* the write, not after. |
| `test_weekly_tokens_source.py` | 4 | The weekly token count has one source: `nightguard_ctl.WEEKLY_TOKENS`. No QML draws its pips from a literal. |
| **Format-preserving edits** | | |
| `test_lineedit.py` | 14 | Every per-field edit is a line edit on the sanctioned text, never a YAML re-emit. Two assertions per test: the edit re-parses through the live `ngcommon.yaml_load` to the expected value, and every other line is byte-identical. Includes the empty-list round trip: `[]` → one item → back to inline `[]`. |
| **The staged-edit vocabulary** | | |
| `test_proposal.py` | 24 | The editable key set is closed; a list entry is validated against a whitelist rather than escaped; a newline cannot smuggle a second entry; a failing op rolls the whole batch back. |
| `test_catalog.py` | 11 | The picker's list: only a process the panel actually read is `verified`; a webapp is never offered as an application; the floor never appears; an entry the config already names always appears even when nothing on the machine answers to it. |
| **The panel payload** | | |
| `test_panel.py` | 45 | The payload is read-only, fails closed to `locked` on an unknown verdict, and never reports the edit window open when the signer would refuse. |
| `test_write_cli.py` | 12 | `apps`, `propose`, `commit` always exit 0 and emit exactly one line of JSON with every failure inside the object. `commit` carries the signer's exit code inside the payload. `propose` writes nothing, so the price is on screen before polkit can be. |
| `test_status_cli.py` | 12 | The bar's cheap poll is key-less, fails closed to `locked`, emits single-line jq-valid JSON, and issues no synchronous SNTP/HTTP query. |
| **Parity — the retirement gate** | | |
| `test_parity.py` | 5 | The terminal editor's field table is a subset of `proposal.EDITABLE`; every editable key is one the signer's `FIELD_TABLE` classifies; the one field left behind (`blocking.browser_extension.extension_id`) is left behind because the signer has no direction for it. |
| **The deploy** | | |
| `test_deploy_completeness.py` | 18 | Everything the deployed stack imports is in `deploy.sh`'s install loop, closed transitively; the manifest's entry points exist; the plugin is installed as the owner, not root; the launcher entry exists and the retired terminal entry is cleared; every `.sh` with a shebang is `100755` *in the git index* (`core.filemode=false` here, so a chmod on disk never reaches git). |
| `test_first_install.py` | 12 | No install artefact carries the author's username; the sudoers owner is a substituted placeholder; nothing shipped grants a grace window and `CLAUDE.md` still says the bypass does not exist. |
| `test_installer_idempotent.py` | 4 | A re-run detects its own marker and does not duplicate; the file is backed up before the first edit; everything outside the managed block comes out byte-identical. |
| `test_config_migration.py` | 16 | The migration that makes the edit window non-inert, edited line-by-line so the bytes the HMAC signs do not move for no reason. |
| **The QML guards** (read the files as text; nothing executes QML) | | |
| `test_no_fixed_hex.py` | 2 | No literal hex anywhere in the plugin QML — every colour comes from the live theme as a role. The second test is the control, demonstrated able to fail. |
| `test_qml_composition.py` | 6 | The dial is drawn by exactly one file, the duration wording lives in exactly one file, the window lands on the glance, an unread defence is never drawn as switched off, and `open()` rejects a view name the window does not have. |
| `test_deploy_completeness.py` (3 of its 18) | — | Type resolution: every `Foo {` resolves to a plugin file, a shell-kit component, an inline component or a listed import. Layout measurement: no `Toggle` carries a `description` and every `wrapMode: Text.WordWrap` has an explicit `width` above it. Privilege: no QML names `pkexec`, `sudo`, `nightguard_ctl` or `/usr/bin/python3` outside a comment. |
| **The enforcement surfaces** | | |
| `test_appblock.py` | 43 | The kill decision and every way it must refuse to fire. |
| `test_watchdog_enforcement.py` | 45 | Sites are blocked by URL in the root-owned managed policy; only native applications are ever signalled; both gated on the verdict being exactly `locked`. |
| **The edit window** | | |
| `test_edit_window.py` | 27 | Loosening is refused outside the configured clock window, before the token is considered. The window in force is read from the *sanctioned* config, never the proposal, and removing or widening the block is itself a loosening. |
| `test_edit_window_seam.py` | 20 | The refusal reaches the user before he authenticates: the gate lives in `quota_decide`, which the pre-auth preview calls directly. No synchronous network query; a cold cache fails closed. |
| **The theme** | | |
| `test_theme_sync.py` | 143 | Every installed omarchy theme maps to a complete panel palette, with provenance: each role must be a colour the theme itself declares. Parametrised over the themes found on disk. |
| `test_theme_roles.py` | 55 | The same sweep for the Textual role mapping, plus a vacuity guard asserting both sweeps agree on what "installed" means. |
| `test_theme.py` | 12 | `colors.toml`/`alacritty.toml` → `Theme` + `ThemeWatch`, against tmp-dir fixtures. |
| | **570** | |

Read the module docstring before the code. Each one states the defect.

## The kind of test this project writes

Most of these are not tests of behaviour anybody designed. They are fences around a hole
somebody fell into. Five, quoted from their own docstrings:

**`test_appblock.py`** — the process killer.

> The previous native-app blocker was reverted in June 2026 after a review found it would
> SIGKILL Steam and Discord at three in the afternoon, because the clock-tamper check ran
> independently of the curfew window. The first test in this file is that regression.

**`test_deploy_completeness.py`** — a module that exists but is not installed.

> A module added to `scripts/linux/` but left out of deploy.sh's install loop is a silent,
> total failure: the watchdog is a systemd oneshot, so it would raise `ModuleNotFoundError` on
> every 60-second tick, log nothing useful, and quietly stop reverting hand edits. Nothing in
> the test suite would notice, because the suite imports from the working tree where the file
> exists. This caught exactly that: `appblock.py` was written, imported by the watchdog, and
> missing from the install list.

**`test_commit_output_welding.py`** — a bare carriage return.

> sudo's session audit record ended in a BARE carriage return, and the ANSI scrubber deleted
> every `\r` rather than treating it as a line break — so the record and the signer's result
> became one line. […] The TUI looked frozen.

**`test_config_ownership.py`** — the guard clause that was simply false.

> The old implementation read `SUDO_UID` and nothing else. The desktop panel authorises
> through polkit, and `pkexec` sets `PKEXEC_UID` and no `SUDO_UID` at all (man pkexec), so the
> guard clause was simply false and the chown never ran.

**`test_deploy_completeness.py:265`** — a popup that asked to be shorter than its contents.

> This is the defect that cut the sites card and both action buttons off the bottom of the
> panel with no scrollbar to hint they were there. […] Measured at the time: the panel asked
> for 588 logical pixels against a cap that allowed 607, so it was never being clamped — it
> was measuring itself wrong.

The house style follows from that: a test's docstring says **which defect it prevents**, not
what the function does. Several of them carry the measured number from the day it broke.

## The negative-control rule

A test that has never been seen to fail is not evidence. `test_port03_no_crypto.py` shipped
for its whole life scanning **zero files** — one `parent.parent` too many in the path — and
reported `3 passed` with `import hmac` sitting in a widget module. Its docstring records that.

So: before you trust a guard, arm the defect and watch it go red.

### Worked example

Arm the no-crypto guard, run it, read the message, restore.

```bash
cd /home/danitrrga/dev/Projects/nightguard-control/ngtui

# 1. arm — put the forbidden import in a module the scan covers
sed -i '1i import hmac' ngtui/panel.py

# 2. run
uv run --with pytest python -m pytest -q tests/test_port03_no_crypto.py
```

Measured output:

```
E       AssertionError: PORT-03 VIOLATION — ngtui source imports crypto module(s):
E         ngtui/ngtui/panel.py:1: import hmac
E       assert ['ngtui/ngtui... import hmac'] == []
1 failed, 2 passed
```

```bash
# 3. restore
sed -i '1d' ngtui/panel.py

# 4. confirm green again
uv run --with pytest python -m pytest -q tests/test_port03_no_crypto.py
# 3 passed in 0.10s
```

Three more, each verified to fail on the defect it names (2026-09-14, against a scratch copy
of the tree):

| Guard | Arm it with | Message |
| --- | --- | --- |
| `test_deploy_completeness.py::test_every_component_a_qml_file_instantiates_actually_resolves` | append `Item {\n  Bogus {\n  }\n}` to `NightguardGlance.qml` | `NightguardGlance.qml:NNN instantiates Bogus, which is neither a file in the plugin, a component in the shell kit, an inline component of this file, nor a listed imported type — it resolves to nothing` |
| `test_deploy_completeness.py::test_no_wrapping_text_hides_its_height_from_the_layout` | delete the `width:` line above any `wrapMode: Text.WordWrap` in `NightguardPanel.qml` | `wraps with no width above it — its height is unknowable until after layout, so whatever sums it sums the wrong number` |
| `test_deploy_completeness.py::test_no_qml_ever_builds_a_privileged_argv_itself` | append `property string x: "pkexec"` to `NightguardWriter.qml` | `NightguardWriter.qml names 'pkexec' — the privileged argv belongs in backend.py, which validates the stack directory before root ever runs it` |

### Guards that carry their own control

Some tests ship the negative control inside the file, so it runs on every invocation:

- **`test_no_fixed_hex.py:76` — `test_the_scan_catches_an_injected_hex`.** It appends
  `property color bad: "#7aa2f7"` — the retired Moonlit Indigo accent, exactly the class of
  value the ban exists to keep out — to an in-memory copy of a plugin file and asserts the scan
  finds it. Its own docstring: *"A scan that has never been seen to find anything is not
  evidence."*
- **`test_port03_no_crypto.py:53` — `_iter_py_files`.** Asserts the scan reached at least one
  file, and that the files it reached include the anchors (`__init__.py`, `backend.py`,
  `theme.py`, `panel.py`, `proposal.py`, `catalog.py`). Without it, a wrong path is green.
- **`test_theme_roles.py` — `test_this_sweep_sees_the_same_themes_the_panel_sweep_sees`.**
  Asserts themes were discovered at all *and* that this file's discovery helper agrees with
  `test_theme_sync.py`'s, so one mapping cannot be swept over 27 themes and the other over 3
  with both green.
- **`test_deploy_completeness.py:82` — `test_the_watchdog_really_does_import_the_blocker`.**
  Guards the closure check above it from passing vacuously if the import is dropped while the
  enforcement call stays.
- **`conftest.py:420`** — `mutate_theme` asserts the section it was asked to rewrite exists,
  so a restyle test cannot pass by asserting on a change that never happened.

Three of the QML scans have **no** such guard: `test_every_component_a_qml_file_instantiates_...`,
`test_no_qml_ever_builds_a_privileged_argv_itself` and
`test_no_wrapping_text_hides_its_height_from_the_layout` all `glob` the plugin directory and
pass over an empty result. Verified: renaming
`packaging/omarchy/plugins/danitrrga.nightguard` leaves all three green while ten of their
neighbours go red. They fail correctly on content; they do not notice being pointed at
nothing.

## What is NOT covered

**The QML is never executed.** All 11 QML guards read the `.qml` files as text — regex and
string matching. Nothing instantiates a component, renders a frame or measures a real layout.
`test_no_wrapping_text_hides_its_height_from_the_layout` enforces two *syntactic* rules that
make the height bug impossible; it does not measure a height. `qmllint` is not run either, and
`test_every_component_a_qml_file_instantiates_actually_resolves` says why: with no `qmldir` it
resolves no local types at all and returns 0 on a file that instantiates a name that does not
exist (checked, by renaming one).

**The root install path is never exercised.** No test runs `deploy.sh`. Every deploy test
reads the script as text and asserts about its contents — the install loop, the `runuser`, the
`install -m` modes, the `s/@NIGHTGUARD_OWNER@/$OWNER/` substitution. A real run needs a
password and a machine with no instance on it. `test_installer_idempotent.py` is the one
exception and it is the *author-facing* installer, not the deploy: it runs
`packaging/omarchy/install.sh` under `NG_HYPR_CONF` / `NG_ICON_BASE` / `NG_APPLICATIONS_DIR` /
`NG_BIN_DIR` / `NG_SKIP_RELOAD`, which redirect every write into `tmp_path` and suppress the
Hyprland reload.

**The browser policy lock is verified by a script, not by the suite.**
`scripts/linux/verify_browser_lock.py` (deployed to `/usr/local/lib/nightguard/`) is run by
hand. It does two things no unit test can: checks each policy file is present, root-owned, not
writable by the owner and byte-identical to what the watchdog would write right now; and
starts each Gecko browser headless against a throwaway profile with the policy engine's debug
logging on, asserting the path it reports reading is the `/etc` one. Exit 0 = locked. The
suite's `test_watchdog_enforcement.py` covers the *policy body* the watchdog would write — not
whether the browser reads it. That distinction is the whole reason the script exists: until
2026-09-12 the Gecko half was a staged file at `/var/lib/nightguard/policies/` that no code
read and no deploy installed.

**No coverage measurement, no CI.** `ngtui/pyproject.toml` configures no coverage threshold.
There is no `.github/`, no `.gitlab-ci.yml`, no CI of any kind. Nothing runs this suite except
a person typing the command.

### The four skipped tests

```
SKIPPED [1] tests/test_parity.py:55: the terminal editor is retired; the frozen copy is the record
SKIPPED [1] tests/test_port02_preview_seam.py:74:  Sanctioned config not present on this machine — live-stack test
SKIPPED [1] tests/test_port02_preview_seam.py:110: Sanctioned config not present on this machine — live-stack test
SKIPPED [1] tests/test_port02_preview_seam.py:142: Sanctioned config not present on this machine — live-stack test
```

**`test_parity.py::test_the_frozen_copy_still_matches_the_living_table`** skips because
`ngtui/ngtui/widgets/edit.py` no longer exists. That is by design and permanent: the terminal
app was deleted, and the frozen `TERMINAL_EDITOR_FIELDS` tuple in `test_parity.py:34-47` is now
the historical record the parity claim rests on. The other four tests in that file still run
against it.

**The three `test_port02_preview_seam.py` skips are not by design.** They skip when
`backend.sanctioned_text()` is empty. It is empty because `ngtui/tests/conftest.py:16-18`
pins `NIGHTGUARD_DIR` to `~/.local/share/nightguard` — the *legacy* instance path, which the
trust-wall hardening moved to `/var/lib/nightguard` and which no longer exists on this box.
The machine with a live instance is exactly the machine where these skip. Pointed at the real
instance:

```
$ NIGHTGUARD_DIR=/var/lib/nightguard uv run --with pytest python -m pytest -v tests/test_port02_preview_seam.py
test_preview_change_identical_text_is_noop                  PASSED
test_preview_change_uses_live_classify_change               PASSED
test_preview_change_uses_live_quota_decide                  FAILED
test_preview_change_diff_base_is_sanctioned_not_live_config PASSED
```

```
TypeError: spy_quota() got an unexpected keyword argument 'edit_window'
  ngtui/backend.py:216
```

The spy's signature is stale: `backend.preview_change` now passes `edit_window=` and
`now_minutes=` to `quota_decide`, and the test's stand-in does not accept them. The skip has
been hiding a broken test.

## Writing a new test

**Where it goes.** `ngtui/tests/test_<subject>.py`. One file per thing-defended, not per
module — `test_edit_window.py` and `test_edit_window_seam.py` are two files because the gate
and the seam that puts the gate in front of the user before he authenticates are two different
promises. There are no subdirectories and no test classes.

**Naming.** Test function names are sentences, in the present tense, about the property:

```
test_nothing_is_killed_unless_the_curfew_is_actually_locked
test_an_entry_the_config_names_always_appears
test_a_missing_defence_block_is_reported_as_unconfigured_not_as_on
test_the_owner_is_read_before_the_write_not_after
test_commit_never_composes_a_config_and_propose_never_signs_one
```

Not `test_kill_decision` or `test_config_owner`. The name states what must be true, so a
failure line in the summary is already the bug report. `test_..._not_...` and
`test_..._rather_than_...` are common and encouraged — they name the wrong answer as well as
the right one.

**The docstring standard.** A docstring says **which defect this test prevents**, not what the
function under test does. If the defect was measured, put the number in. If the defect is a
class of bug rather than a single incident, say what the class costs. Compare:

```python
# no
def test_theme_roles():
    """Checks that _theme_from_colors maps roles correctly."""

# yes
def test_every_installed_theme_resolves_its_roles_from_its_own_palette(name, path):
    """No Textual role may resolve to a colour from outside the theme.

    Provenance, not inequality: comparing against a known default cannot tell
    "fell back" from "this theme happens to use that colour". So every role must
    be a colour the theme itself declares.
    """
```

**Assertion messages.** Every assertion carries a message naming the consequence, not the
comparison. `assert offenders == [], "literal colour in the desktop surface; take it from the
theme instead:\n  " + ...`. Include the `file:line` of the offender where the test can compute
it.

**If it is a scan, give it a vacuity guard.** A test that walks a directory, a glob or a
config table must assert it reached something before it asserts anything about what it found,
and the assertion message must say the scan was vacuous. Three existing scans lack this; do
not add a fourth. `test_port03_no_crypto.py:53` is the pattern to copy.

**Then arm it.** Break the thing, run it, keep the failure message, restore. If you cannot
make it go red, it is not a test yet.

## The seams

Every seam that exists for testing is listed here, along with what stops it being a bypass.

| Seam | Read at | What it moves | Dead in production? |
| --- | --- | --- | --- |
| `NIGHTGUARD_DIR` | `scripts/linux/ngcommon.py:39` | The instance directory: config, sanctioned config, `guard.json`, `.guardkey`, audit log, lock. | No — it is the portability knob, not a test-only seam. It is also the *gate* on the seam below. |
| `NIGHTGUARD_STACK_DIR` | `ngtui/ngtui/backend.py:38` | Which copy of the trust stack is imported **and** which script goes into the privileged argv. | No, but pinned: `_resolve_stack_dir` (`backend.py:37-49`) resolves it to an absolute real path and refuses unless that directory actually contains `nightguard_ctl.py`. `CTL_SCRIPT` (`backend.py:54`) is derived from the validated value so the path handed to sudo can never diverge from it. `test_backend_stackdir.py` holds that. |
| `NIGHTGUARD_TEST_NTP_OVERRIDE` + `NIGHTGUARD_NTP_OVERRIDE_UNIX` | `scripts/linux/guard.py:114-117` | Replaces true time with a supplied epoch, source `"override"` — which also skips the clock-tamper branch. | **Yes.** Gated on `not ng.IS_CANONICAL_INSTANCE`. |
| `NIGHTGUARD_NTP_SERVER` | `scripts/linux/guard.py:35` | Which SNTP server is queried. | No. Not a bypass: the guard still requires an answer and still checks drift. |
| `NG_HYPR_CONF`, `NG_ICON_BASE`, `NG_APPLICATIONS_DIR`, `NG_BIN_DIR`, `NG_SKIP_RELOAD` | `packaging/omarchy/install.sh`, used at `test_installer_idempotent.py:34-42` | Redirect every write of the author-facing installer into a temp dir; suppress the prereq check and the Hyprland reload. | Irrelevant — the installer is unprivileged and touches no signed state. |
| `OMARCHY_PATH` | `test_deploy_completeness.py:170` | Where the shell kit's QML components are looked up for the type-resolution scan. | Test-only; reads nothing privileged. |
| `backend._run_sudo_pty` | `ngtui/ngtui/backend.py` | The PTY seam. Mocked by `test_port02_commit_argv.py` and `test_backend_signal.py` to capture argv and inject an exit code without ever calling sudo. | A Python attribute, not an env var — unreachable from outside the process. |
| `ngtui.theme.OMARCHY_THEME_DIRS` | `conftest.py:360-371` | Which theme directory the loader reads. Monkeypatched, deliberately **not** an env var — `theme.py` has no env seam, and a fixture that set one would leave the loader reading the live desktop theme while looking like it had not. | Same. |
| `read_key_explodes` fixture | `conftest.py:144` | Makes `read_key` raise on `ng`, `guard.ng` and `ctl.ng` so a stray read from any of them is caught on the key-less status path. | A fixture, not a seam into the product. |

### `IS_CANONICAL_INSTANCE`

```python
# scripts/linux/ngcommon.py:43
IS_CANONICAL_INSTANCE = os.path.abspath(NIGHTGUARD_DIR) in (ROOT_INSTANCE, LEGACY_INSTANCE)
```

`ROOT_INSTANCE` is `/var/lib/nightguard`; `LEGACY_INSTANCE` is
`~/.local/share/nightguard`. Both count, so the seams stay dead across the migration between
them.

What it protects against is stated in `guard.py:108-113`: the adversary is the user, so any
env-gated seam is attacker-controlled.

> `export NIGHTGUARD_TEST_NTP_OVERRIDE=1 NIGHTGUARD_NTP_OVERRIDE_UNIX=<daytime>` used to
> replace true time AND skip the clock-tamper check (source == "override"), turning the curfew
> off with no password.

The gate is now the instance directory itself. To use the override against the real curfew you
would have to point the guard at the real instance — and then `IS_CANONICAL_INSTANCE` is true
and the seam is dead. Point it anywhere else and the override works, but against a directory
with no signed state in it.

Measured:

```
$ cd scripts/linux
$ NIGHTGUARD_DIR=/var/lib/nightguard            python3 -c '...'  IS_CANONICAL_INSTANCE=True
$ NIGHTGUARD_DIR=~/.local/share/nightguard      python3 -c '...'  IS_CANONICAL_INSTANCE=True
$ NIGHTGUARD_DIR=/tmp/fake-instance             python3 -c '...'  IS_CANONICAL_INSTANCE=False
$ (unset)                                       python3 -c '...'  IS_CANONICAL_INSTANCE=True
```

The unset case is the one that matters: the panel, the signer and the watchdog all run with
`NIGHTGUARD_DIR` unset, resolve to `/var/lib/nightguard`, and the seam is dead.

The user *can* still set `NIGHTGUARD_DIR` to a directory he owns and run a whole fake
nightguard in it. That is not a hole the curfew needs to close — the enforcement that matters
(`nightguard_watchdog.service`, the sudoers rule, the polkit action) is pinned to absolute
paths by root-owned unit files, and none of it reads the user's environment.

## Two things to know before you trust a green run

**1. The suite tests the author's tree, not your checkout.** `conftest.py:13-15` and
`test_lineedit.py:24-26` both hardcode:

```python
os.environ.setdefault(
    "NIGHTGUARD_STACK_DIR", "/home/danitrrga/dev/Projects/nightguard-control/scripts/linux"
)
```

`setdefault`, so it only applies when the variable is unset — which it normally is. Proven by
running a full copy of this repo from `/tmp`: every test passed, and
`backend.ctl.__file__` was `/home/danitrrga/dev/Projects/nightguard-control/scripts/linux/nightguard_ctl.py`.
Editing `WEEKLY_TOKENS` in the copy changed nothing the tests saw. Anyone cloning this
elsewhere gets an import-time `RuntimeError` from `_resolve_stack_dir`, or — worse, on the
author's box — a green run that measured the wrong tree. Set `NIGHTGUARD_STACK_DIR` explicitly
when you are not the author.

**2. 210 tests are green about a code path that is dead in production.**
`test_theme_sync.py` (143), `test_theme_roles.py` (55) and `test_theme.py` (12) all sweep
`ngtui/ngtui/theme.py` across every installed omarchy theme, on the premise that "the panel
must follow whatever theme is active". They pass. But `theme.py:39` imports `textual`, which
is not a declared dependency, and the deployed `ngtui` tool's venv does not have it:

```
$ ~/.local/share/uv/tools/ngtui/bin/python -c "from ngtui import theme"
ModuleNotFoundError: No module named 'textual'
```

`ngtui/ngtui/__main__.py:318-334` wraps both callers in `except Exception: return {}`, so the
failure is silent, and `panel.build` fills the payload from `THEME_FALLBACK`
(`ngtui/ngtui/panel.py:217`, `:448`). Measured on the running system, with Tokyo Night active:

```
$ cat ~/.local/state/omarchy/current/theme/colors.toml   # accent = "#7aa2f7", background = "#1a1b26"
$ ngtui panel | jq -c .theme
{"background":"#2d353b","surface":"#343f44","foreground":"#d3c6aa","muted":"#859289",
 "accent":"#7fbbb3","ok":"#a7c080","warn":"#dbbc7f","alert":"#e67e80"}   # <- Everforest, the fallback
```

The 210 tests cannot catch it, because they call `theme.raw_tokens()` directly from a venv
that *does* have Textual. The surface is not visibly wrong only because no QML file reads
`detail.theme` or `detail.style` at all — the plugin takes its colours from the shell's own
`Color.` singleton (71 references across `DayDial.qml`, `NightguardWorkshop.qml`,
`NightguardGlance.qml`, `NightguardPanel.qml`), which is what `test_no_fixed_hex.py` actually
guards.

So `theme.py` and its 210 tests defend a payload field nothing consumes, computed by a module
the deployed product cannot import. That is the shape a test takes when it has outlived its
consumer, and it is the reason the rest of this file insists on arming a guard before
believing it.

For completeness: four of `conftest.py`'s eight fixtures — `probe_app` (`:465`),
`mutate_theme` (`:404`), `omarchy_theme_dir` (`:374`) and `omarchy_theme_pinned_dir` (`:386`),
about 250 of the file's 569 lines — are referenced by no test. They were written for the
Textual UI wave that was retired.
