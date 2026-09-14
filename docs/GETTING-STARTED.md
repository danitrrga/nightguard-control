<!-- generated-by: gsd-doc-writer -->
# Getting started

[The README](../README.md) has the three-line install. This is the long version: what to
decide before you run it, what the installer does while it runs, and how to check afterwards
that the thing is actually holding.

Read it in order. Step 1 is the one people skip and then cannot undo.

---

## 1. Before you install: decide your hours

`config.example.yaml` is what a fresh machine copies into `/var/lib/nightguard/config.yaml`,
and the deploy signs whatever it finds there. **Edit it before the first run.**

After that first signature you cannot change these by hand:

- The watchdog reverts the live config to the signed copy on its next tick, within 60 seconds.
- Re-running `deploy.sh` does **not** re-sign. The signing step is guarded by
  `FIRST_INSTALL`, which is set only when `/var/lib/nightguard` did not exist
  (`deploy.sh:107-126`, `deploy.sh:315-321`). Every later run skips it.

From then on, changes go through the panel, which prices them. That is the product, not a
limitation — but it means the *starting* hours are a decision you make with a text editor,
once, while you are calm.

The two blocks that matter:

```yaml
curfew:
  start: "23:00"        # when the house closes
  end: "07:00"          # when it opens again

edit_window:            # when the curfew may be WEAKENED
  enabled: true
  start: "07:00"
  end: "12:00"
```

Put the edit window somewhere in your morning. Outside it, a loosening change is refused
before the weekly token allowance is even consulted
(`nightguard_ctl.py:400-421`) — the allowance limits how *often* you give in, the window
limits *when*.

`timezone` is used for every hour in the file; it must be an IANA name.

Every other key is annotated in [`config.example.yaml`](../config.example.yaml) and
documented in [CONFIGURATION.md](CONFIGURATION.md). Two of them are deliberately outside the
panel's reach — see
[what the panel can edit, and what it cannot](CONFIGURATION.md#what-the-panel-can-edit-and-what-it-cannot)
before you assume you can change something later.

---

## 2. Prerequisites

| What | Why | How to check |
|---|---|---|
| Omarchy 4, Quickshell shell | The panel is a shell plugin; nothing else loads it | `command -v omarchy-shell` |
| `python3` **3.11 or newer** | The signer, watchdog and CLI (`ngtui/pyproject.toml`: `requires-python = ">=3.11"`) | `/usr/bin/python3 --version` |
| `polkit` | Every commit authenticates through `pkexec`; stopping the watchdog is raised to `AUTH_ADMIN` | `pkexec --version` |
| `systemd` | The watchdog is a system timer | `systemctl --version` |
| [`uv`](https://docs.astral.sh/uv/) | Installs `ngtui`, the CLI the panel runs | `command -v uv` |
| A network connection | Real time is resolved over SNTP/HTTP; an unverifiable clock fails closed | — |
| `librsvg` (optional) | `rsvg-convert` rasterizes the launcher icon | `command -v rsvg-convert` |

The signer runs under the absolute path `/usr/bin/python3` — that literal is pinned in the
sudoers alias and in the `pkexec` argv (`backend.py:250-257`). A `python3` that exists only
on your `PATH` is not enough.

### What degrades without `uv`

The deploy resolves `uv` **as the owner**, through `runuser -u "$OWNER" -- bash -lc
'command -v uv'` (`deploy.sh:219`), because root's `PATH` does not contain the owner's
`~/.local/bin`. If it still is not found, the script prints:

```
   !! uv not found even as <owner> — ngtui NOT updated.
      The panel will not show the cost or the edit-window refusal before
      authentication until you run: uv tool install --force ./ngtui
```

It does not abort. Everything else installs. What you lose is the pre-authentication
preview: the panel would put an authentication prompt in front of a change the signer is
about to refuse, and would show the wrong price. If the install succeeds it prints
`ngtui reinstalled (<path to uv>)` instead; if `uv` runs but the install fails, it tells you
the exact command to run yourself.

`rsvg-convert` is softer still: without it you get `!! rsvg-convert absent — the entry will
show a generic icon.` and a suggestion to `pacman -S librsvg` and re-run.

---

## 3. The install

```bash
git clone https://github.com/danitrrga/nightguard-control.git
cd nightguard-control
# edit config.example.yaml first — see step 1
sudo scripts/linux/deploy.sh
```

The script is re-runnable, and if it fails part-way a trap restarts
`nightguard-watchdog.timer` before exiting (`deploy.sh:85-93`), so a failed deploy never
leaves you unprotected.

### What the output looks like

Each stage prints a `== ... ==` banner. In order:

```
== installing for <owner> (<home>) ==
== validating sudoers BEFORE it lands in /etc ==
== stopping the watchdog timer for the move ==
== installing code -> /usr/local/lib/nightguard (root-owned, not writable by <owner>) ==
== instance data -> /var/lib/nightguard ==
== browser policy directories -> root:root 0755 ==
== gecko policy directories -> root:root 0755 ==
== systemd units ==
== polkit rule (admin auth required to stop the watchdog) ==
== sudoers ==
== reinstalling the ngtui CLI so it tracks these paths ==
== installing the shell plugin -> <home>/.config/omarchy/plugins/danitrrga.nightguard ==
== launcher entry + icons ==
== first install: creating the signing key and signing the config ==     <- first run only
== config schema: adding anything this build needs ==
== dry run: one watchdog tick against the deployed stack ==
== re-enabling the timer ==
== now prove the browsers actually read it (as <owner>, no root needed) ==
```

The Gecko section names each browser it skips (`skipping /etc/zen/policies —
/opt/zen-browser-bin is not installed`), because a policy directory for a browser you do not
have is not protection.

The dry run tails one line of `watchdog.log`, and `== re-enabling the timer ==` ends with
`systemctl is-active`, which should print `active`.

### If it cannot tell whose machine this is

Nightguard binds to one person: the one who gets the panel, the sudoers line, and ownership
of `config.yaml`. The script derives them from `NIGHTGUARD_OWNER`, then `SUDO_USER`, then
`PKEXEC_UID`, then — only on a machine with exactly one ordinary login account — that account
(`deploy.sh:27-39`). If none of those resolve it exits 1 with:

```
ERROR: cannot tell whose machine this is.

Nightguard binds to one person: they get the desktop panel, the sudoers line
that lets them sign a change, and ownership of config.yaml. Say who:

    sudo NIGHTGUARD_OWNER=yourname scripts/linux/deploy.sh
```

Do exactly that. On a multi-user box, or under `sudo -i`, you will hit this every time — set
`NIGHTGUARD_OWNER` and stop thinking about it.

---

## 4. What just landed on the machine

Modes are from the `install`/`chmod` lines in `deploy.sh`. "Owner" is the user resolved above.

| Path | Owner | Mode | What it is |
|---|---|---|---|
| `/usr/local/lib/nightguard/` | `root:root` | `0755` | The code that actually runs. Not the repo. |
| `/usr/local/lib/nightguard/*.py` | `root:root` | `0644` | `ngcommon`, `guard`, `nightguard_ctl`, `nightguard_watchdog`, `appblock`, `verify_browser_lock` |
| `/var/lib/nightguard/` | `root:root` | `0755` | The instance. Root-owned **because the directory governs rename and unlink** — a user-owned parent lets root-owned files be displaced. |
| `/var/lib/nightguard/.guardkey` | `root:root` | `0600` | The 32-byte HMAC key |
| `/var/lib/nightguard/.nightguard.lock` | `root:root` | `0600` | Commit lock |
| `/var/lib/nightguard/config.sanctioned.yaml` | `root:root` | `0644` | The signed truth, and the revert target |
| `/var/lib/nightguard/guard.json` | `root:root` | `0644` | State: config HMAC, weekly tokens, week anchor, audit chain |
| `/var/lib/nightguard/guard-audit.log`, `watchdog.log` | `root:root` | `0644` | The ledgers |
| `/var/lib/nightguard/config.yaml` | **owner** | `0644` | The live copy. Deliberately yours to edit — the revert model needs the hand edit to be *possible*. |
| `/var/lib/nightguard/.timecache` | **owner** | `0644` | Verified-time cache, written by the user-context guard |
| `/etc/systemd/system/nightguard-watchdog.{service,timer}` | `root:root` | `0644` | The watchdog: `OnBootSec=30`, `OnUnitActiveSec=60` |
| `/etc/polkit-1/rules.d/00-nightguard.rules` | `root:root` | `0644` (dir `0750`) | Raises stopping the watchdog to `AUTH_ADMIN` — no timestamp caching |
| `/etc/sudoers.d/nightguard` | `root:root` | `0440` | The owner's right to run the signer's `commit`/`verify`. No `NOPASSWD`. |
| `~/.config/omarchy/plugins/danitrrga.nightguard/` | **owner** | `0755`, files `0644` | The plugin. Installed as the owner on purpose: a root-owned file here would be a root-writable path inside your session. |
| `~/.local/share/applications/nightguard.desktop` | **owner** | `0644` | The launcher entry |
| `~/.local/share/icons/hicolor/*/apps/org.omarchy.nightguard.*` | **owner** | `0644` | The icon, rasterized at 16–512 plus the SVG |
| `~/.local/bin/ngtui` | **owner** | — | The CLI, a `uv tool` snapshot |

Browser policy directories are re-owned to `root:root 0755` where the browser is installed:
`/etc/chromium/policies/managed`, `/etc/brave/policies/managed`,
`/etc/opt/chrome/policies/managed`, `/etc/zen/policies`, `/etc/firefox/policies`.

Nothing root trusts is writable by you. [ARCHITECTURE.md § the trust
boundary](ARCHITECTURE.md#1-the-trust-boundary) explains why each of those lines is where it
is.

---

## 5. First look at the application

**The interface is in Spanish.** The config file, the logs and everything under the hood are
in English. English glosses of the view names are given once below and not repeated.

Two ways in, and they are two entry points of one plugin:

- **The shield in the bar.** Click it for the dropdown — a reading of the present: the
  verdict, the tokens left, the hours. It polls `ngtui status --json` and `ngtui panel` every
  30 seconds, every 5 while open. It reads and never writes.
- **"Nightguard" in the launcher.** Opens the window — the workshop — on the glance. It runs
  `omarchy-shell shell toggle danitrrga.nightguard {}`, the same command the bar icon uses.
  `toggle`, so pressing it again puts the window away instead of opening a second one.

The workshop has three views on a rail down the left
(`NightguardWorkshop.qml:827-831`):

| Rail label | English | What it is |
|---|---|---|
| **El vistazo** | the glance | The landing. Shows the **signed** state and nothing staged — the present, not a future. |
| **Qué muere** | what dies | Applications and sites. This is where you edit. Carries a count of everything currently listed. |
| **El horario** | the schedule | The curfew hours and the edit window, drawn as a 24-hour ring. |

---

## 6. Making your first change

Go to **Qué muere**. The screen is a picker on the left and your two lists on the right.

**1. Pick something.** The picker is built from `ngtui apps`, in four groups: what is
running, games, everything installed, and web apps. Each row shows the name you recognise and, under it, the
exact executable basename the enforcer can actually act on (`antigravity-ide`, `zen-bin`,
`steam`). You never have to guess that string. A filter box narrows by either. Click a row to
stage it; a listed row shows `✓` in front of its name. Clicking it again un-stages it — a
second click is you changing your mind, and it leaves nothing behind to sign.

Sites are the same picker, separate list. Their identity is the host, because web apps share
one browser process and ending a process cannot separate them.

**2. Read the footer.** As soon as anything is staged, the panel runs `ngtui propose` — which
writes nothing and asks the signer's own classifier what your edit *does*. Two lines appear at
the bottom:

- the count: `2 cambios sin aplicar` ("2 unapplied changes")
- the cost line, which is one of:

| Line | Means |
|---|---|
| `calculando el coste…` | the preview is still running |
| `1 cambio · refuerza · gratis` | **tightening.** Free, allowed at any hour. |
| `1 cambio · debilita · cuesta 1 ficha · te quedarán 1` | **loosening.** Costs one of three weekly tokens; the number is what will be left. |
| `1 cambio · sin efecto` | the config already says that |
| `✕ no se puede aplicar: <reason>` | refused — see below |
| `No se pudo calcular el coste. No se aplica nada hasta que se pueda.` | the preview failed; nothing will be applied |

Tightening and loosening are decided per field, not per screen. Adding an app to the
blacklist tightens. Removing one loosens. In allowlist mode the polarity flips, because
adding to an allowlist permits more. [ARCHITECTURE.md § the classifier and the
price](ARCHITECTURE.md#3-the-classifier-and-the-price) has the full table.

**3. Press Aplicar.** The button is disabled unless the preview arrived, parsed, and came back
allowed (`NightguardWriter.qml:63-66`). **An authentication dialog never appears for a change
the signer has already decided to refuse** — the reason sits next to the button instead.

A confirmation appears first, and it starts on *Cancelar*:

- loosening: *"Esto DEBILITA el pacto y gasta una de tus fichas de la semana. Hay que
  autorizarlo."*
- tightening: *"Esto refuerza el pacto y no gasta ficha. Hay que autorizarlo igualmente."*

**4. Authenticate.** Confirming runs `ngtui commit`, which execs
`pkexec /usr/bin/python3 /usr/local/lib/nightguard/nightguard_ctl.py commit --from <file>`.
Omarchy's own polkit agent owns the dialog. `pkexec` caches nothing under
`org.freedesktop.policykit.exec`, so **every** commit is a fresh authentication. That is the
friction, and it is deliberate.

### What comes back

`NightguardWriter.report` (`NightguardWriter.qml:242-281`) turns the exit code into one line.
The signer's own words are passed through verbatim — translating a refusal would put words in
the trust boundary's mouth.

| Code | Line | Means |
|---|---|---|
| 0 | `✓ aplicado — <signer output>` | Signed and written. The staged list clears and every surface re-reads. |
| 0, output starts `no-op` | `· sin cambios: la configuración ya era esa` | Nothing was written |
| 126 | `✕ cancelado — no se autorizó nada, no se ha escrito nada` | You dismissed the dialog |
| 127 | `✕ no autorizado — no se ha escrito nada` | polkit said no, or the program could not run |
| anything else | `✕ rechazado — <last line of stderr>` | The signer refused |

126 and 127 get different sentences on purpose: a person who *chose* to cancel must not be
told he was refused.

### What a refusal looks like, and why

Only loosening can be refused. Three reasons, verbatim from
`nightguard_ctl.py:400-460`:

- `outside the edit window (07:00-12:00); loosening is refused until then` — the clock gate.
  Checked **before** the token count, so being outside the window does not cost you a token.
- `weekly loosen quota exhausted (3/3 used); available again Monday` — you have spent the
  week's three. The counter resets on the Monday anchor.
- `cannot verify the time; loosening is refused until the clock is confirmed (the edit window
  is 07:00-12:00)` — real time could not be resolved. Fail-closed, matching
  `curfew.block_when_offline`: an unverifiable clock is exactly the state someone would
  engineer.

Tightening is never refused for any of these.

---

## 7. Verifying it works

All of these are read-only and none needs root.

### The CLI the panel runs

```bash
ngtui status --json
```

A healthy reading, outside curfew, two tokens spent-down:

```json
{"text":"○ 2","tooltip":"OPEN · 2 tokens left","class":"outside_curfew"}
```

```bash
ngtui panel
```

One JSON line. The fields to look at:

```json
{
  "verdict": "outside_curfew",
  "tokens_left": 2, "tokens_total": 3,
  "week_anchor": "2026-09-14",
  "edit_window": {"enabled": true, "open": false, "start": "05:30", "end": "14:00",
                  "detail": "closed — opens at 05:30"},
  "curfew": {"enabled": true, "start": "21:30", "end": "05:30"},
  "defences": {"clock_protection": {"enabled": true, "max_offset_minutes": 5},
               "watchdog": {"enabled": true, "check_interval_seconds": 60}},
  "now_minutes": 863,
  "warnings": []
}
```

Three things make that reading healthy:

- `now_minutes` is a real minute-of-day, **not `-1`**. `-1` means true time could not be
  resolved and every loosening is currently refused.
- `defences.watchdog.enabled` and `clock_protection.enabled` are `true`.
- `warnings` is empty. A non-empty one is the panel telling you something it cannot fix —
  most importantly, membership of a polkit-trusted group (`wheel`, or Omarchy's `empower`),
  which makes every authentication in this model free.

`ngtui` answers `status --json`, `panel`, `apps`, `propose` and `commit`, and nothing else.
Every one of them prints a single JSON line and exits 0, always — a non-zero exit from a
`Process` is indistinguishable from a missing binary, so failure is reported as data.

### The watchdog

```bash
systemctl status nightguard-watchdog.timer
```

```
● nightguard-watchdog.timer - Run the nightguard watchdog every minute (root system timer)
     Loaded: loaded (/etc/systemd/system/nightguard-watchdog.timer; enabled; preset: disabled)
     Active: active (waiting) since Mon 2026-09-14 09:27:36 CEST; 4h 53min ago
    Trigger: Mon 2026-09-14 14:21:07 CEST; 1s left
   Triggers: ● nightguard-watchdog.service
```

`enabled` and `active (waiting)` with a `Trigger` under a minute away. Anything else means
protection is off.

### The browser lock

```bash
python3 /usr/local/lib/nightguard/verify_browser_lock.py
```

This is the check that "it is configured" cannot substitute for. It does three things
(`verify_browser_lock.py:64-190`):

1. **File** — every policy file the watchdog should maintain is present, `root:root`, not
   group- or world-writable, sits in a root-owned directory, and is byte-identical to what
   the watchdog would write right now.
2. **Read** — each installed Gecko browser is started headless against a throwaway profile
   with the policy engine's debug logging on, and the path it reports reading must be the
   `/etc` one. A policy file in a directory the browser ignores is not enforcement, and this
   is the only check that catches it.
3. **Provenance** — each Chromium profile's record of the extension must read location `7`
   (`EXTERNAL_POLICY_DOWNLOAD`), which only a managed policy can set, and must not be
   disabled.

Locked:

```
== policy files ==
ok    /etc/brave/policies/managed/nightguard.json (root-owned, current)
ok    /etc/zen/policies/policies.json (root-owned, current)
== what the Gecko browsers actually read ==
ok    /usr/lib/firefox/firefox reads /etc/firefox/policies/policies.json
ok    /opt/zen-browser-bin/zen-bin reads /etc/zen/policies/policies.json
== chromium install provenance ==
ok    brave runs it as a force-installed extension

LOCKED: yes
```

Not locked — exit status 1, and each problem named:

```
LOCKED: NO — 1 problem(s)
  FAIL  /opt/zen-browser-bin/zen-bin: reads /usr/lib/zen/distribution/policies.json,
        not /etc/zen/policies/policies.json. A policy file in a place the browser
        ignores is not enforcement.
```

Other failures it will print: `owned by uid N gid N, must be root:root — the owner can
rewrite it`; `contents differ from what the watchdog would write`; `read no policies.json at
all — the lock is not applied in this browser`; `extension is DISABLED despite the
forcelist`. `skip` and `warn` lines are not failures: a browser that is not installed, or
one that has not started since the policy landed, has nothing to check yet.

The Gecko probes launch real browsers and can take up to 60 seconds each, so the whole run is
slow. It writes nothing to the instance.

---

## 8. When something is wrong

**The panel shows no reading, or "Detalle no disponible".**
The dropdown prints *"Detalle no disponible: el ngtui instalado no conoce «panel». Ejecuta el
despliegue."* The panel resolves the CLI at the absolute path `$HOME/.local/bin/ngtui` — the
shell does not inherit your login `PATH`. Check `ls -l ~/.local/bin/ngtui`, then `ngtui
panel` from a terminal. If the binary is missing or an old snapshot, re-run the deploy, or
`uv tool install --force ./ngtui` from the repo. This is also the symptom when `uv` was
missing during the install.

**The bar widget is blank, or the shell logs "is not a type".**
A `.qml` file is missing from `~/.config/omarchy/plugins/danitrrga.nightguard/`. The deploy
copies every `.qml` plus `manifest.json`; a half-populated directory half-loads with no other
symptom. Re-run the deploy — the shell hot-reloads a changed plugin on its own.

**The cost line says the time cannot be verified.**
`now_minutes` is `-1` and the edit window reads `time unverified — weakening refused`. The
preview deliberately never issues a network query — it reads `.timecache`, which has a
120-second TTL (`guard.py:34`) and is refreshed by the guard when it resolves real time. A
cold or stale cache, or being offline, reads as unverified and refuses every loosening.
Tightening still works. Check your network, then re-read the panel after a watchdog tick.

**The timer is not running.**
`systemctl status nightguard-watchdog.timer` shows `inactive` or `disabled`. Start it with
`sudo systemctl enable --now nightguard-watchdog.timer`. Re-running the deploy does this too,
and its failure trap restarts the timer even when the deploy itself fails. Note that stopping
it should have prompted for an administrator password every time; if it did not, you are in a
polkit-trusted group and that is a total bypass — the panel's `warnings` will say so.

**The config keeps reverting when you did not expect it.**
That is the watchdog doing its job: the live `config.yaml` no longer matches
`config.sanctioned.yaml`, so it is put back within 60 seconds. Every change has to go through
the panel. If you genuinely need to re-baseline — a mangled file, or one of the keys the
panel deliberately cannot reach — that is what the root password is for; see
[CONFIGURATION.md § editing it safely](CONFIGURATION.md#editing-it-safely).

**Your editor refuses to save `config.yaml`.**
`/var/lib/nightguard` is root-owned, and rename is governed by the *directory*, not the file.
Editors that save by writing a temp file and renaming it over the original will fail there.
Edit in place (`vim` with `set backupcopy=yes`, `nano`, `sed -i` will all need care) — or,
better, do not edit it at all.

**The launcher entry has a generic icon, or does not appear.**
`rsvg-convert` was absent during the deploy (`pacman -S librsvg`, then re-run), or the icon
and desktop caches were not refreshed. The deploy calls `gtk-update-icon-cache` and
`update-desktop-database`; both are non-fatal if missing, and the entry then appears at next
login.

---

## Where to go next

- [ARCHITECTURE.md](ARCHITECTURE.md) — the four processes, the trust boundary, one change end
  to end, and what this deliberately does not defend against.
- [CONFIGURATION.md](CONFIGURATION.md) — every key, what the panel may and may not touch, the
  price direction of each field, and how to edit the file safely.
- [browser-lock.md](browser-lock.md) — the site-blocking half in detail.
