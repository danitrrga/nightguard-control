<!-- generated-by: gsd-doc-writer -->
# Configuration reference

Every key in `config.yaml`, what reads it, and what happens when it is wrong or
missing. Each row was written from the code that consumes the key, cited by
`path:line`.

## Where it lives and who owns it

| Path | Owner | Mode | What it is |
|---|---|---|---|
| `/var/lib/nightguard/` | `root:root` | `0755` | The instance directory. The boundary: rename and unlink are governed by the directory's mode, not the file's. |
| `/var/lib/nightguard/config.yaml` | the owner | `0644` | The live config. Yours to edit — and the one file the watchdog puts back. |
| `/var/lib/nightguard/config.sanctioned.yaml` | `root:root` | `0644` | The signed truth. The revert target and the diff base for every proposal. |
| `/var/lib/nightguard/guard.json` | `root:root` | `0644` | State: `config_hmac`, `state_hmac`, weekly tokens, week anchor, ledger, grace. |
| `/var/lib/nightguard/.guardkey` | `root:root` | `0600` | The 32-byte HMAC key. |

Modes and ownership are applied by `scripts/linux/deploy.sh:123-154`; the paths
themselves are defined in `scripts/linux/ngcommon.py:27,44-49`.

`config.yaml` is deliberately left user-writable — the revert model needs the hand
edit to be *possible* so the watchdog can be seen undoing it
(`scripts/linux/nightguard_ctl.py:494-506`).

**If you edit it by hand:** the watchdog's next tick recomputes
`HMAC(config.yaml)` and compares it against `guard.json.config_hmac`. On a
mismatch it copies `config.sanctioned.yaml` over your edit
(`scripts/linux/guard.py:210-242`, called from
`scripts/linux/nightguard_watchdog.py:390`). The tick runs every 60 seconds, so
the edit survives at most that long. If the sanctioned copy does not itself match
the stored HMAC, the guard writes a hard lockout instead — a 00:00–23:59 curfew
with `block_when_offline: true` (`scripts/linux/guard.py:36,240-242`).

### Instance override

`NIGHTGUARD_DIR` relocates the whole instance (`scripts/linux/ngcommon.py:39`).
It is for tests and fixtures. Pointing it away from `/var/lib/nightguard` (or the
legacy `~/.local/share/nightguard`) clears `IS_CANONICAL_INSTANCE`
(`ngcommon.py:43`), which re-enables the NTP test seam in
`scripts/linux/guard.py:113-116` — an instance that can be handed a fake time.
Production pins the variable in the systemd unit
(`scripts/linux/systemd/nightguard-watchdog.service:25`) and the sudoers rule pins
the signer's path, so a caller cannot repoint either.

### How the file is parsed

Not by a YAML library. `ngcommon.yaml_load` (`scripts/linux/ngcommon.py:156-204`)
is a minimal parser shared by the signer and the guard so both read identical
bytes identically. It handles nested maps by indent, `- item` scalar lists, and
scalars. It does not handle anchors, aliases, flow mappings, or multi-line
scalars. `#` starts a comment; a quoted scalar has its outer quotes stripped
(`ngcommon.py:207-222`).

---

## Key reference

Unless a row says otherwise, "absent" means the key is missing from the file
entirely.

### Top level

| Key | Type | Default when absent | What it does | Wrong or absent |
|---|---|---|---|---|
| `timezone` | IANA zone name | `Europe/Amsterdam` | The zone every hour in this file is read in, and the zone the weekly token reset is anchored to | An unresolvable name falls back to `Europe/Amsterdam`, then to UTC if `zoneinfo` is unavailable (`guard.py:274-285`). The signer reads the zone from the *signed* config, never `/etc/localtime` or `$TZ` (`nightguard_ctl.py:349-353`) |

### `curfew`

| Key | Type | Default when absent | What it does | Wrong or absent |
|---|---|---|---|---|
| `enabled` | bool | `true` | Master switch for the curfew window | `false` makes `in_curfew` always false, so nothing is ever locked (`guard.py:253-254`) |
| `start` | `"HH:MM"` | none | When the house closes | Unparseable **or absent** makes `in_curfew` return `True` — permanently locked (`guard.py:264-271`). `start` later than `end` wraps past midnight, the normal case (`guard.py:267-268`). `start == end` is a zero-minute window: never locked |
| `end` | `"HH:MM"` | none | When it opens again | Same as `start` |
| `allow_commands` | list of strings | — | **Nothing in this repository reads it.** The signer classifies it (`nightguard_ctl.py:48`) and the panel can edit it (`ngtui/ngtui/proposal.py:42`), but no enforcement code here consults it. Its consumer is the Claude Code hook adapter, which lives outside this repo | Absent or empty changes nothing here |
| `block_when_offline` | bool | `true` | Inside the curfew window with true time unresolvable, the verdict is `offline_blocked` rather than open | `false` opens the house whenever the network is down (`guard.py:329-330`) |
| `message` | string | — | **Read by nothing in this repository.** | See below |
| `tamper_message` | string | — | **Read by nothing in this repository.** | See below |
| `offline_message` | string | — | **Read by nothing in this repository.** | See below |

**On the three messages and `{start}` / `{end}`.** They appear in this repo only
as literals inside the hard-lockout config the guard *writes*
(`guard.py:36`) and in `config.example.yaml`. No code here reads them back, and
no code here performs the `{start}` / `{end}` substitution. The substitution was
specified for the Claude Code hook adapter — the component that turns a `deny`
verdict into a refusal a person reads — and that adapter is not part of this
repository. Set them if you run that adapter; on this repo alone they are inert
bytes that the HMAC still covers.

`curfew.schedule` — a per-weekday override, `off` or `"HH:MM-HH:MM"` or a
`{start, end}` map — **is read** by `guard.in_curfew` (`guard.py:258-263`) and
classified per day (`nightguard_ctl.py:321-324`), but it is absent from
`config.example.yaml`. It is not panel-editable.

### `clock_protection`

| Key | Type | Default when absent | What it does | Wrong or absent |
|---|---|---|---|---|
| `enabled` | bool | `true` | Compares verified true time against the system clock; a divergence is the `clock_tamper` verdict | `false` skips the curfew-side check (`guard.py:322-325`). It does **not** skip the signer's own check: `verified_now_minutes` cross-checks the clock before opening the edit window whatever this says (`nightguard_ctl.py:384-392`) |
| `max_offset_minutes` | int | `5` | Tolerance, in minutes, before the clock reads as tampered | Non-numeric falls back to 5 minutes in the signer (`nightguard_ctl.py:386-390`); `guard.py:324` casts with `int()` and will raise on garbage, which `curfew_verdict`'s caller turns into a fail-closed error verdict |

`clock_tamper` denies prompts and refuses edits. It deliberately does **not**
kill applications (`appblock.py:217-228`) — a clock jump at three in the
afternoon is a reason to refuse changes, not to close the desktop.

### `watchdog`

Read the caveat before this table.

| Key | Type | Default when absent | What it does | Wrong or absent |
|---|---|---|---|---|
| `enabled` | bool | — | **Nothing that enforces reads it.** The panel displays it (`ngtui/ngtui/panel.py:146-150`) and the signer classifies it (`nightguard_ctl.py:52`). Setting it `false` does not stop the timer | No effect on enforcement |
| `check_interval_seconds` | int | — | **Does not govern the cadence.** Displayed in the glance (`packaging/omarchy/plugins/danitrrga.nightguard/NightguardGlance.qml:595-596`) and classified as a number (`nightguard_ctl.py:53`) | No effect on enforcement |

**Which cadence actually governs: the systemd timer, not this key.** The tick
interval is `OnUnitActiveSec=60` in
`scripts/linux/systemd/nightguard-watchdog.timer:6`, with `OnBootSec=30` and
`AccuracySec=15`. `nightguard_watchdog.py` is a `Type=oneshot` unit that performs
exactly one tick per invocation and never reads the `watchdog` block at all.
Changing `check_interval_seconds` changes the number the panel shows and can cost
you a token (raising it classifies as a loosening), while the watchdog keeps
running every 60 seconds. Stopping it means stopping the timer, which asks for an
administrator password.

### `blocking.browser_extension`

| Key | Type | Default when absent | What it does | Wrong or absent |
|---|---|---|---|---|
| `enabled` | bool | `true` | Whether the root-owned browser policies are written and restored | `false` disables the whole block, including `blocked_urls` (`nightguard_watchdog.py:181-186`) |
| `extension_id` | string | none | The Chromium extension force-installed through the managed policy | **Empty or absent switches the entire block off** — `_browser_extension` returns `None`, so no policy file is written or restored, and `blocked_urls` has no effect either (`nightguard_watchdog.py:184-186`). Not panel-editable; see below |
| `blocked_urls` | list of hosts | `[]` | Sites closed during curfew, through that same policy. Applied **only** while the verdict is `locked` (`nightguard_watchdog.py:207,224`) | An empty list omits the key from the policy document. Hosts, not URLs: Chromium takes the bare host verbatim as `URLBlocklist`; Gecko needs a match pattern, so `_match_pattern` rewrites `discord.com` to `*://*.discord.com/*` and passes anything already carrying a scheme through untouched (`nightguard_watchdog.py:118-130`) |

Three more keys in this block are read by the code but are **not** in
`config.example.yaml`:

| Key | Default | Read at |
|---|---|---|
| `block_incognito` | `true` | `nightguard_watchdog.py:208` — sets `IncognitoModeAvailability: 1` and `BrowserGuestModeEnabled: false`, the two Chromium profiles that run without the force-installed extension |
| `firefox_extension_id` | `{30b15d56-b2fa-4cb2-98fd-7b5e26306483}` | `nightguard_watchdog.py:222` |
| `firefox_install_url` | the AMO `latest.xpi` redirect | `nightguard_watchdog.py:223` |

The Gecko defaults are constants rather than required config on purpose: the
config is HMAC-sanctioned, so requiring them would have made closing that hole
wait on a signed commit inside the edit window
(`nightguard_watchdog.py:211-218`).

### `blocking.native_apps`

| Key | Type | Default when absent | What it does | Wrong or absent |
|---|---|---|---|---|
| `enabled` | bool | **off** | Whether any process is ever signalled | Absent is falsy, so app blocking is off unless explicitly `true` (`appblock.py:230-231`, `nightguard_watchdog.py:334-335`) |
| `mode` | `blocklist` or `allowlist` | `blocklist` | Which list is consulted — see "The two modes" | Anything that is not exactly `allowlist` (stripped, lowercased) enforces as blocklist (`appblock.py:233,246`). The classifier treats any non-`allowlist` value as the permissive mode so a typo cannot be priced as a free tightening (`nightguard_ctl.py:291-298`) |
| `blacklist` | list of identities | `[]` | Ends only what is named. **Blocklist mode only** | Inert in allowlist mode |
| `allowlist` | list of identities | `[]` | Ends everything except what is named. **Allowlist mode only** | Inert in blocklist mode. Empty in allowlist mode means everything above the floor is ended |
| `block_games` | bool | **off** | Builds a catalog of installed games (Steam `appmanifest_*.acf`, Heroic `installed.json`, `.desktop` entries declaring `Categories=Game`) and adds them to the kill set in blocklist mode | Absent is falsy. In allowlist mode this flag still decides whether the catalog is built at all (`nightguard_watchdog.py:346`), and without it a game *title* in the allowlist cannot resolve to its install path (`appblock.py:176-184`) |

Two limits that config cannot reach:

- **The floor.** Compositor, shell, session plumbing, portals, and the terminal
  emulators are never signalled, whatever the lists say
  (`appblock.py:53-105,135-145`). In allowlist mode a missing floor entry would
  not degrade the feature, it would take down the desktop and with it the only
  route to the editor.
- **The cap.** If a tick's decision names more than 25 processes, nothing is
  killed and the log says why (`nightguard_watchdog.py:313,350-353`).

Processes are only ever ended on a `locked` verdict — never on `clock_tamper`,
never on `offline_blocked` (`appblock.py:227-228`).

### `edit_window`

| Key | Type | Default when absent | What it does | Wrong or absent |
|---|---|---|---|---|
| `enabled` | bool | — | Whether the hour gate applies to loosening commits | The whole block absent, or `enabled` falsy, means **no gate at all** — loosening is refused only by the weekly token count (`nightguard_ctl.py:404-406`) |
| `start` | `"HH:MM"` | none | Start of the window in which the curfew may be weakened | Unparseable start or end refuses **every** loosening until it is a valid range (`nightguard_ctl.py:407-411`) |
| `end` | `"HH:MM"` | none | End of it | Same. `start == end` is zero minutes wide, not twenty-four (`nightguard_ctl.py:186-196`) |

Two properties worth knowing:

- **The window that governs is the sanctioned one, never the proposal's**
  (`nightguard_ctl.py:223-232`). Resolving it from the file being committed would
  let a single commit widen the window and then be judged by the widened version.
- **An unverifiable clock refuses.** If true time cannot be resolved, or the
  resolved time disagrees with the system clock beyond
  `clock_protection.max_offset_minutes`, loosening is refused rather than allowed
  (`nightguard_ctl.py:384-392,415-419`).

---

## What the panel can edit, and what it cannot

`EDITABLE` in `ngtui/ngtui/proposal.py:37-71` is a closed set. A key not in it is
refused by `_apply_one`, loudly (`proposal.py:138-140`). The panel can only
propose what it was built to explain the cost of.

| Key | Kind | Legal ops |
|---|---|---|
| `curfew.enabled` | bool | `set` true/false |
| `curfew.start` | time | `set` `HH:MM` |
| `curfew.end` | time | `set` `HH:MM` |
| `curfew.allow_commands` | list | `add` / `remove` |
| `clock_protection.enabled` | bool | `set` |
| `watchdog.enabled` | bool | `set` |
| `edit_window.enabled` | bool | `set` |
| `edit_window.start` | time | `set` |
| `edit_window.end` | time | `set` |
| `blocking.native_apps.enabled` | bool | `set` |
| `blocking.native_apps.block_games` | bool | `set` |
| `blocking.native_apps.mode` | mode | `set` `blocklist` / `allowlist` |
| `blocking.native_apps.blacklist` | list | `add` / `remove` |
| `blocking.native_apps.allowlist` | list | `add` / `remove` |
| `blocking.browser_extension.enabled` | bool | `set` |
| `blocking.browser_extension.blocked_urls` | list | `add` / `remove` |

### The two deliberate exclusions

**`blocking.browser_extension.extension_id`** is absent on purpose
(`proposal.py:58-70`). The signer's `FIELD_TABLE` has no entry for it, so
`classify_change` returns no direction for it at all: a change would classify as
nothing, price as free, and be written anyway. Pointing the managed browser
policy at a different or non-existent extension is exactly how site blocking gets
switched off — an empty id disables the entire browser block, `blocked_urls`
included. "Free and unjudged" is the wrong answer for it twice over. Giving it a
direction means changing the signer's own table, which is an owner's decision,
not a side effect of a UI change.

**`timezone`** is not in the set either. It *is* classified — as `any`, meaning
every change is a loosening (`nightguard_ctl.py:68`, `:299-300`) — because the
zone decides what "23:00" means and what "Monday" means for the token reset. It
is not offered as a panel edit.

Everything outside `EDITABLE` — the three messages, `curfew.block_when_offline`,
`curfew.schedule`, `clock_protection.max_offset_minutes`,
`watchdog.check_interval_seconds`, `extension_id`, `timezone`, the undocumented
Gecko keys — is edited by hand and then re-signed by a root deploy. See "Editing
it safely".

---

## Price direction

Tightening is free and immediate, at any hour. Loosening spends one of three
weekly tokens (`nightguard_ctl.py:42`) and is refused outside the edit window
*before* the tokens are even considered (`nightguard_ctl.py:451-454`).

One commit is judged as a whole: if **any** field loosens, the whole commit costs
one token (`nightguard_ctl.py:328-329,439-461`). A commit where every field is
neutral writes nothing. A field missing from either document classifies as
neutral (`nightguard_ctl.py:264-265`).

### Editable keys

| Key | Loosens when | Tightens when |
|---|---|---|
| `curfew.enabled` | `true` → `false` | `false` → `true` |
| `curfew.start` / `curfew.end` | any minute that was locked becomes unlocked | minutes are added and none removed |
| `curfew.allow_commands` | an entry is added | an entry is removed |
| `clock_protection.enabled` | `true` → `false` | `false` → `true` |
| `watchdog.enabled` | `true` → `false` | `false` → `true` |
| `edit_window.*` | the window widens, is disabled, or the block is deleted | it narrows, is enabled, or the block is added |
| `blocking.native_apps.enabled` | `true` → `false` | `false` → `true` |
| `blocking.native_apps.block_games` | `true` → `false` | `false` → `true` |
| `blocking.native_apps.mode` | `allowlist` → `blocklist` | `blocklist` → `allowlist` |
| `blocking.native_apps.blacklist` | an entry is removed | an entry is added |
| `blocking.native_apps.allowlist` | an entry is added | an entry is removed |
| `blocking.browser_extension.enabled` | `true` → `false` | `false` → `true` |
| `blocking.browser_extension.blocked_urls` | an entry is removed | an entry is added |

`curfew.start` and `curfew.end` are not judged separately. They are rendered as a
1440-minute locked-set mask and compared: any minute that loses its lock is a
loosening, even in a change that locks more minutes elsewhere
(`nightguard_ctl.py:138-160,309-319`). `edit_window` is one classifier entry
rather than three, with the opposite polarity — its window is the part that is
*open*, so it is inverted before the same mask comparison
(`nightguard_ctl.py:199-208,235-260`). Deleting the block entirely costs the same
as disabling it, because that is the cheapest imaginable bypass.

### Classified but not panel-editable

| Key | Loosens when |
|---|---|
| `curfew.block_when_offline` | `true` → `false` |
| `curfew.schedule.<day>` | the day is set `off`, starts later, or ends earlier |
| `clock_protection.max_offset_minutes` | the number increases |
| `watchdog.check_interval_seconds` | the number increases |
| `timezone` | any change at all |

---

## The two modes

`blocking.native_apps.mode` decides which of the two lists is consulted. The
other is inert.

**`blocklist`** — end only what is named in `blacklist`, and (with
`block_games: true`) anything under an auto-detected game install. `allowlist` is
never read. Everything not named keeps running.

**`allowlist`** — end everything EXCEPT what is named in `allowlist`. `blacklist`
is never read. This includes your terminal unless it is listed, your browser
unless it is listed, and every editor, player and chat client you own. Put your
terminal in the allowlist *before* you switch, not after.

The floor (`appblock.py:53-105`) is the only thing standing between allowlist
mode and a dead desktop: the compositor, the Omarchy shell, the session bus,
PipeWire, the portals and the common terminal emulators survive whatever the list
says. A process whose `/proc/PID/exe` cannot be read is never killed either —
refusing to end what cannot be identified is the safe direction
(`appblock.py:241-245`).

---

## What an identity is

The exact basename of `/proc/PID/exe`. Never `comm`, never a substring.

`read_processes` reads `exe` by `os.readlink("/proc/<pid>/exe")` and strips a
trailing `" (deleted)"` so copying-then-deleting a binary does not defeat path
matching (`appblock.py:473-503`). `matches_identity` compares
`os.path.basename(proc.exe) == identity` — equality, not containment
(`appblock.py:154-184`). A bare name is never substring-matched: `portal` would
otherwise hit `xdg-desktop-portal`, which breaks every file picker on the desktop
while the thing you meant keeps running.

`comm` is deliberately absent from the `Process` class
(`appblock.py:108-133`) so no caller can grow a dependency on it.
`prctl(PR_SET_NAME)` renames a running process to anything, which was proven on
this machine by renaming a Python process while `exe` and cgroup stayed truthful.

An entry may also be:

- **an absolute path** — matched as an exact `exe`, or as a path prefix, which is
  how Proton- and JVM-hosted games are caught (`appblock.py:167-173`);
- **a game title** — resolved against the auto-detected catalog to an install
  path prefix, so `Rocket League` matches a Wine process whose `exe` is the Proton
  loader (`appblock.py:176-184`). Requires `block_games: true`, which is what
  builds the catalog.

**Web apps cannot be separated this way.** Discord, a calendar, a todo list and a
board are all `--app=` windows of ONE Chromium process. Ending that process to
block one of them takes all of them, and takes any allowlisted one with it
(`appblock.py:26-29`, `nightguard_watchdog.py:92-97`). Their identity is the
address, not the executable, so they belong in
`blocking.browser_extension.blocked_urls` as hosts — a root-owned managed policy
lever the user cannot pull.

---

## Validation rules

The panel validates before it composes a proposal, so the message reaches a
person rather than arriving later as a signer refusal — or, worse, as a silently
mis-parsed config the guard then acts on (`ngtui/ngtui/proposal.py:115-121`).

### List entries — `validate_entry` (`proposal.py:93-112`)

Refused:

| Rule | Why |
|---|---|
| leading or trailing whitespace | the value would not round-trip through the parser |
| empty | |
| longer than 256 characters | |
| contains `#`, `:`, `"` or `'` | `#` opens a comment, `:` opens a mapping, and the quotes are stripped back off on read (`ngcommon.py:208-209`), so a value containing one does not survive a round trip |
| contains a control character or `\x7f` | |

One more rule sits outside the table because its character set contains a pipe.
An entry may not **begin** with any of the sixteen characters in
`_FORBIDDEN_FIRST_CHARS` (`proposal.py:90`): hyphen, hash, ampersand, asterisk,
exclamation mark, vertical bar, greater-than, percent, at sign, backtick,
question mark, comma, and the four bracket and brace characters. They are
ordinary mid-scalar and YAML indicators in the first column of a value.

Accented characters are allowed on purpose: the config is UTF-8 and the parser
reads it as UTF-8, so refusing `Pokémon` would be inventing a limit.

One consequence worth stating: because `:` is forbidden, a `blocked_urls` entry
entered through the panel cannot carry a scheme. Enter bare hosts. The watchdog
turns them into the right shape for each browser family
(`nightguard_watchdog.py:118-130`).

Absolute paths are fine — `/` is not a forbidden first character.

### Times — `validate_time` (`proposal.py:115-130`)

A time is exactly two colon-separated all-digit parts, hour `0-23`, minute
`0-59`. It is normalised to zero-padded `HH:MM` on the way out, so `7:5` becomes
`07:05`. Anything else raises.

This is refused locally because the signer's `_parse_hhmm` returns `None` on a
malformed time and the edit-window gate reads that as "no window"
(`nightguard_ctl.py:127-135`). A malformed time must be caught where a person
sees it, rather than becoming a curfew that quietly does nothing.

---

## Editing it safely

### Normally: through the panel

Click the shield in the bar, or open **Nightguard** from the launcher. The panel
stages edits, prices them, and hands the result to the root signer through
polkit. It never writes the config itself.

The same path without the GUI:

```bash
ngtui propose --ops-json '[{"key":"blocking.native_apps.blacklist","op":"add","value":"steam"}]'
ngtui commit --from /tmp/ngtui-proposal-XXXX.yaml
```

`propose` is unprivileged and write-free: it reads the sanctioned config, applies
the ops, writes the result to a `0600` temp file and returns both the path and
the price, so the cost is on screen before any authentication dialog appears
(`ngtui/ngtui/__main__.py:451-498`). `commit` runs `pkexec` against the root
signer and passes its stdout, stderr and exit code back verbatim
(`ngtui/ngtui/__main__.py:501-529`, `ngtui/ngtui/backend.py:238-266`).

### By hand: only before the first signature

On a first install, `deploy.sh` seeds `config.yaml` from `config.example.yaml`
and signs it at the end of the run (`deploy.sh:142-149`, `:315-321`). Edit it
first, then run the deploy — until `init` has run there is no signature and
nothing to revert to.

After that, a hand edit is reverted on the next tick. To keep one, re-sign it:

```bash
# Priced: classified against the sanctioned copy, costs a token if it loosens,
# refused outside the edit window. This is the sudoers-permitted path (password required).
sudo /usr/bin/python3 /usr/local/lib/nightguard/nightguard_ctl.py \
    commit --from /var/lib/nightguard/config.yaml

# Unpriced re-baseline: no classification, no token — but still held to the edit
# window, because it can install any config at all.
sudo /usr/bin/python3 /usr/local/lib/nightguard/nightguard_ctl.py \
    commit --from /var/lib/nightguard/config.yaml --rebaseline
```

Both are reachable through `/etc/sudoers.d/nightguard`, which scopes the owner to
`nightguard_ctl.py commit *` and `verify` at the deployed root-owned path, with
**no** `NOPASSWD` — the password prompt is the friction
(`scripts/linux/nightguard.sudoers:21-25`). The re-baseline shortcut is gated by
the edit window precisely because that wildcard reaches it
(`nightguard_ctl.py:572-586`).

`nightguard_ctl.py init` also re-signs whatever `config.yaml` currently says, with
no classification and no edit-window gate (`nightguard_ctl.py:815-834`). It is
deliberately **not** in the sudoers file: it needs the root password directly.
`ensure-config`, the schema migration, is excluded for the same reason
(`nightguard_ctl.py:734-746`).

Check the result:

```bash
sudo /usr/bin/python3 /usr/local/lib/nightguard/nightguard_ctl.py verify
tail -1 /var/lib/nightguard/watchdog.log
```

### Your editor must write in place

`/var/lib/nightguard` is `root:root 0755`. An editor that saves by writing a temp
file and renaming it over the original needs write permission on the
**directory**, not the file, so it will fail
(`deploy.sh:138-141`, `ngcommon.py:22-26`). This affects `sed -i`, and `vim`
unless you `:set backupcopy=yes`. Edit in place, or use the sanctioned path.
