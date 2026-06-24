# Pitfalls Research

**Domain:** Desktop/Waybar integration of a Python Textual TUI-with-inline-sudo on Arch/CachyOS + Hyprland + omarchy (global install, `.desktop` floating-terminal launch, Waybar module, AUR packaging)
**Researched:** 2026-06-24
**Confidence:** HIGH (app-specific facts read from `ngtui/ngtui/backend.py`; Hyprland/Waybar/uv behavior verified against current upstream docs)

> **Two load-bearing risks frame this entire file:**
> 1. **The inline-sudo commit needs a real TTY.** `backend.commit()` shells `sudo … nightguard_ctl.py commit` with **stderr intentionally left attached to the TTY** (so the sudo password / fingerprint prompt and any `REFUSED` line reach the user), wrapped by the TUI in `App.suspend()`. Any launch path that does **not** provide a real interactive terminal (`Terminal=false` with no `-e`, a `Terminal=true` entry on a system with no XDG terminal handler, a Waybar `exec` with no terminal, a detached spawn) **silently breaks the core editing flow** — the prompt has nowhere to go and the commit either hangs or fails.
> 2. **A launcher / Waybar quick-action must never become an escape hatch.** The entire product value is that an impulsive late-night user *cannot quietly loosen the curfew* without the `sudo` friction. Every shortcut we add (Waybar left/right-click, autostart, `.desktop`) must route loosening **through the same `sudo`-gated commit**. A "quick +8" or "quick unlock" button on the bar, or any status-reader accidentally wired with privilege, **defeats the self-binding guarantee**.

---

## Critical Pitfalls

### Pitfall 1: Launching the TUI without a real TTY (the inline-sudo commit breaks)

**What goes wrong:**
The TUI opens, the user edits, hits commit — and the sudo prompt never appears (or `sudo` errors `no tty present and no askpass program specified`, or the commit hangs forever). The core editing flow is dead even though the TUI itself "ran."

**Why it happens:**
`backend.commit()` deliberately does **not** capture stderr and relies on `App.suspend()` handing a real interactive TTY to `sudo`. A `.desktop` `Exec=` that runs the bare `ngtui` script (no terminal), a `Terminal=true` entry on a system with **no registered XDG terminal handler** (common on omarchy/Hyprland — there is no Debian-style `x-terminal-emulator` alias), a Waybar `on-click` that runs `ngtui` directly, or any `hyprctl dispatch exec ngtui` without a terminal — all start the Python process with stdin/stdout/stderr pointed at a pipe or `/dev/null`, not a PTY. `sudo` then has nowhere to prompt.

**How to avoid:**
- **Always launch inside a real terminal emulator:** `Exec=<omarchy-terminal> -e ngtui` (e.g. `alacritty -e ngtui`, `ghostty -e ngtui`, or whatever omarchy ships as default). Never `Exec=ngtui`.
- Set `Terminal=false` in the `.desktop` file **because you supply your own terminal** via `-e`. (`Terminal=true` delegates to an XDG terminal handler that may not exist on Hyprland — fragile.)
- Waybar `on-click` must spawn the same terminal wrapper, not the bare command: `on-click = "<terminal> -e ngtui"`.
- Add a **startup self-check**: if `sys.stdin.isatty()` is false, print a clear error ("ngtui must be run in an interactive terminal; sudo commit requires a TTY") and exit non-zero, rather than failing mysteriously at commit time.
- Confirm the sudoers `Cmnd_Alias` matches the exact argv (`/usr/bin/python3` + absolute `CTL_SCRIPT` + `commit`), and that `sudo` is not configured to suppress the prompt.

**Warning signs:**
`sudo: no tty present and no askpass program specified` in any log; commit "does nothing"; the app hangs on commit; the password prompt flashes and the terminal closes.

**Phase to address:** **Phase: `.desktop` floating-terminal launcher** (land a TTY self-check early so every later launch path inherits it).

---

### Pitfall 2: A Waybar/launcher quick-action becomes a curfew escape hatch (self-binding broken)

**What goes wrong:**
To make the bar "convenient," a contributor adds a Waybar `on-click-right` that runs `nightguard_ctl … +8` or a quick-loosen directly, or wires the status reader with `sudo`/`pkexec` so it "just works." Now the impulsive user can loosen the curfew (or burn the daily +8) from the bar **without the sudo friction** — the exact thing the product exists to prevent.

**Why it happens:**
Desktop-integration convenience pressure collides with the security model. The status reader genuinely needs to read `guard.json` and the config, which *feels* like it might need privilege — and the easy fix (give it `sudo`) is catastrophic.

**How to avoid:**
- **Hard invariant: only `backend.commit()` (the `sudo … nightguard_ctl.py commit` path) may change state.** Waybar and the launcher may only *open the TUI* or *display read-only status*. No bar action mutates the curfew.
- The Waybar status reader must be **key-less and unprivileged** — it reads `guard.json` / sanctioned config via the same code path `backend.read_state()` / `sanctioned_config()` use (no `ngcommon.read_key()`, never `sudo`). The watchdog remains authoritative; the bar is advisory display only.
- `on-click` opens the TUI; `on-click-right` shows a **read-only** status/actions popover (a menu that *opens the TUI* for any action, not one that performs the action). No "+8" or "unlock" button on the bar.
- Treat this as a **review gate**: any PR adding a privileged Waybar exec, an askpass helper, or a state-changing click handler is rejected by design.

**Warning signs:**
A Waybar config line containing `sudo`, `pkexec`, `nightguard_ctl`, `commit`, or `+8`; a status script that reads or needs the `.guardkey`; the ability to loosen the curfew without a password prompt.

**Phase to address:** **Phase: Waybar module** (and called out as an explicit non-goal/anti-feature across the whole milestone).

---

### Pitfall 3: Hyprland float window-rule doesn't match (TUI opens tiled, not floating)

**What goes wrong:**
The `.desktop` entry opens the terminal, but it tiles into the layout instead of floating as a centered curfew dialog. Or the rule works for one terminal and silently stops after a terminal upgrade.

**Why it happens:**
Hyprland evaluates `float`/`size`/`center` **once at window creation**, matching against **`initialClass` / `initialTitle`** — not the live `class`/`title`. Terminals frequently **change their title** after launch (to the running command/cwd), so a rule keyed on `title:` matches the post-change title and fails. Matching on the terminal's generic class (e.g. `Alacritty`) floats *every* terminal, not just ngtui.

**How to avoid:**
- Launch the terminal with an **app-id / class override** unique to ngtui, e.g. `alacritty --class ngtui-float -e ngtui` or `ghostty --class=ngtui-float -e ngtui` (kitty: `--class`). Hyprland sees this as `initialClass`.
- Write the rule against the stable initial value:
  `windowrulev2 = float, class:^(ngtui-float)$`
  `windowrulev2 = center, class:^(ngtui-float)$`
  `windowrulev2 = size 90 80%, class:^(ngtui-float)$` (or fixed px).
- **Do not match on `title:`** — terminal titles drift; the rule will miss.
- Verify with `hyprctl clients` while the window is open to read its real `class`/`initialClass`.
- Be aware of Hyprland version regressions (open issues exist where `float`/`size` rules stopped applying to some apps after updates) — keep the rule simple and re-test after Hyprland upgrades.

**Warning signs:**
`hyprctl clients` shows a generic class (`Alacritty`) instead of `ngtui-float`; the window tiles; every terminal you open floats; the rule worked then broke after a terminal/Hyprland update.

**Phase to address:** **Phase: `.desktop` floating-terminal launcher.**

---

### Pitfall 4: Global install can't resolve the external LifeOS trust stack (import fail-closed)

**What goes wrong:**
`uv tool install` (or `pipx`) succeeds, `ngtui` is on `PATH`, but on launch it raises the `_resolve_stack_dir()` `RuntimeError` ("NIGHTGUARD_STACK_DIR … does not contain nightguard_ctl.py") or `ImportError: ngcommon`. The app is installed but won't start — for the author if paths moved, and for *any other user* who lacks the LifeOS stack entirely.

**Why it happens:**
`backend.py` imports the trust stack via `sys.path.insert(STACK_DIR)`, where `STACK_DIR` defaults to the **hardcoded author absolute path** `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard` (env-overridable via `NIGHTGUARD_STACK_DIR`). `uv tool` / `pipx` install into an **isolated venv** that bundles only `textual` — it deliberately does **not** see system or LifeOS packages. The trust stack is *not* a pip dependency; it's resolved at runtime by path. So a global install carries the *client* but not the *stack*, and a fresh user has neither the stack nor the author's directory layout. (This is correct-by-design fail-closed behavior per CR-02 — but it surfaces as a startup crash if not handled.)

**How to avoid:**
- **Make the env contract explicit and first-class.** The `.desktop` `Exec` and the Waybar wrapper must set `NIGHTGUARD_STACK_DIR` / `NIGHTGUARD_DIR` (or rely on a documented system default), not assume the dev-shell env. The current run command (`env NIGHTGUARD_STACK_DIR=… NIGHTGUARD_DIR=… python -m ngtui`) must be reproduced by the launcher — `uv tool`/`.desktop`/Waybar do **not** inherit your interactive shell's exports.
- **Fail loud and actionable at startup**, not at commit: the existing `RuntimeError` is good — surface it in the terminal with the install-doc hint; don't let it crash a detached process silently.
- For the **published product**: document the trust-stack dependency prominently; the AUR `PKGBUILD` must either guide installing the stack or detect its absence and print a setup message. Do **not** vendor the stack into the package (PORT-02: the TUI must import the *live* signer, never a copy that can drift).
- Consider a small `ngtui doctor` subcommand that checks: TTY present, `NIGHTGUARD_STACK_DIR` resolves + contains `nightguard_ctl.py`, sudoers rule present, `/usr/bin/python3` exists.

**Warning signs:**
`RuntimeError: NIGHTGUARD_STACK_DIR resolves to … does not contain nightguard_ctl.py`; `ModuleNotFoundError: ngcommon`; "works in my dev shell, fails from the launcher"; works for author, crashes for any other user.

**Phase to address:** **Phase: Global install (`uv tool`)** — establish the env contract and `doctor` check here; reinforce in **Phase: AUR packaging**.

---

### Pitfall 5: `python -m ngtui` (dev) and the installed `ngtui` script diverge

**What goes wrong:**
Everything works via `python -m ngtui` from the dev venv, but the installed `ngtui` console-script behaves differently — different Python, different `sys.path`, different env, the trust-stack import fails or a different version loads.

**Why it happens:**
`python -m ngtui` runs `ngtui/__main__:main` with the **dev venv's interpreter and the dev shell's exported env** (which includes the `NIGHTGUARD_*` vars from the documented run command). The installed `ngtui = ngtui.__main__:main` console script runs under the **uv-tool isolated interpreter** with a **clean env** (no inherited exports) and a different `sys.path`. The hardcoded-default `STACK_DIR` happens to resolve for the author either way (same absolute path), masking the divergence — until env-dependent behavior (`NIGHTGUARD_DIR`, TZ, terminal) differs.

**How to avoid:**
- Treat the **installed `ngtui` script as the source of truth**; test *that*, not `python -m ngtui`, in every integration phase.
- Pin the env in the launcher (Pitfall 4), so the installed script gets the same `NIGHTGUARD_*` the dev shell provided.
- Keep `__main__:main` the single entry for both modes so logic can't fork.
- In the manual test matrix, exercise both `python -m ngtui` (dev) **and** the installed `ngtui` (prod) and assert identical startup behavior.

**Warning signs:**
"Works with `python -m` but not the installed command"; the installed script picks a different config/stack path; `which ngtui` points at `~/.local/bin` but behavior differs from the venv.

**Phase to address:** **Phase: Global install (`uv tool`).**

---

### Pitfall 6: Waybar custom module blocks the bar / wrong JSON / stale status

**What goes wrong:**
The whole Waybar freezes periodically; the module shows nothing or raw text where styled output was expected; `on-click-right` doesn't fire; or the status is stale (shows "locked" after grace activated).

**Why it happens:**
- **Blocking:** an `interval` `exec` script that itself spawns `sudo`, does network I/O (NTP), or runs long **blocks the bar** for its duration — Waybar runs custom `exec` synchronously per tick.
- **Wrong return-type/JSON:** with `return-type = "json"` the script must emit a **single-line** JSON object (`{"text":…,"tooltip":…,"class":…}`); a multi-line, trailing-comma, or non-JSON payload renders blank or as literal text. Without `return-type`, Waybar expects i3blocks newline-separated `text\ntooltip\nclass`.
- **Click not firing:** `on-click-right` typos, or reliance on `exec-on-event` semantics (Waybar warns there's "no guarantee exec runs after the on-* command finishes").
- **Stale:** too-long `interval` with no `signal` to force-refresh after a commit; or unbuffered output not flushed for a self-looping script.

**How to avoid:**
- Make the status `exec` **fast, read-only, key-less, non-blocking**: read `guard.json` + config locally (no `sudo`, no synchronous NTP — reuse the cached `live_verdict` value the TUI already computes). Keep `interval` modest (e.g. 10–30s), not 1s.
- Emit **strict single-line JSON** with `return-type = "json"`; validate with `… | jq .`. Set a `class` so CSS can theme locked/grace/clear states with the omarchy palette.
- Use a **`signal`** so the TUI can push an immediate refresh after a commit (`pkill -RTMIN+N waybar`) instead of waiting for the poll — kills staleness right after a state change.
- Wire `on-click` / `on-click-right` to the **terminal wrapper** (Pitfall 1) and test both buttons explicitly.
- If the reader ever needs more than a tick, make it a **self-looping** script (omit `interval`, loop + sleep, flush stdout) so it can't stall the bar.

**Warning signs:**
Bar visibly stutters on the module's interval; module blank or shows raw `{"text"...`; `jq` rejects the output; right-click does nothing; status lags real state by the full interval; any `sudo`/NTP call inside the exec.

**Phase to address:** **Phase: Waybar module.**

---

### Pitfall 7: Brand icon doesn't show (wrong hicolor path / stale cache)

**What goes wrong:**
The `.desktop` entry appears in wofi/walker and the Waybar module renders, but with a generic/missing icon instead of the own-brand nightguard icon.

**Why it happens:**
- Icon installed to the wrong place or wrong name — must be `…/icons/hicolor/<size>/apps/<icon-name>.png` (or `…/scalable/apps/<name>.svg`), and the `.desktop` `Icon=` must reference the **bare name** (`Icon=ngtui`), not a path/extension.
- **GTK icon cache not refreshed** after install: `gtk-update-icon-cache` not run on the hicolor dir, or the `.desktop` not picked up because `update-desktop-database` wasn't run.
- For Waybar, the bar uses a **font glyph / CSS** or a separate image path — a hicolor PNG won't automatically appear in the bar; that's a different mechanism (Nerd Font glyph or `image` module).

**How to avoid:**
- Install to the spec path with a matching name; reference `Icon=ngtui` (bare).
- Run `gtk-update-icon-cache -f -t /usr/share/icons/hicolor` and `update-desktop-database` after install (the AUR `PKGBUILD` should do this in `post_install`/`post_upgrade`).
- For Waybar, decide the icon mechanism explicitly: a Nerd Font glyph in `format`/`text` (themeable via the palette) is simplest; an image needs the right module + path. Don't assume the hicolor PNG carries over.
- Provide both a scalable SVG and at least one sized PNG (e.g. 48/256) for launcher fidelity.

**Warning signs:**
Generic cog/placeholder icon in wofi/walker; icon shows after a relogin but not immediately (cache); icon works for the author's manual copy but not from the package.

**Phase to address:** **Phase: Custom brand icon** (cache-refresh hooks reinforced in **Phase: AUR packaging**).

---

### Pitfall 8: AUR packaging mis-models the python runtime and the external stack

**What goes wrong:**
The `PKGBUILD` either bundles a private Python/venv that drifts from system Python (so the `sudo` argv `/usr/bin/python3` mismatches the env the TUI runs under), vendors the LifeOS stack (violating PORT-02, can silently drift from the live signer), installs files with wrong ownership/permissions, or assumes every installer has the author's LifeOS layout.

**Why it happens:**
`uv tool`/`pipx` apps don't map cleanly to Arch packaging conventions (system site-packages vs isolated venv); the trust stack is a runtime *path* dependency, not a pip dep; and the security model has strict ownership rules (root-owned `.guardkey`/sanctioned config 0600) that a naive package install can violate.

**How to avoid:**
- **Never vendor the trust stack** in the package — it must import the *live* signer (PORT-02). Document the stack as an external prerequisite and detect its absence at startup (Pitfall 4).
- Be explicit about Python: the `sudo` commit hardcodes `/usr/bin/python3` (the sudoers `Cmnd_Alias` shape, T-10-03). The *signer* must run under system `/usr/bin/python3`; the *TUI* may run under an isolated env, but the two must not be conflated. Package the TUI so it doesn't shadow or require a different python for the commit argv.
- **Package only the client.** Don't ship or touch the root-owned key/config from the package; those are provisioned by the trust-stack setup, root-owned, outside the package's file manifest. The package installs user-space files (script, `.desktop`, icon, Waybar example) — never anything 0600 root.
- Run `gtk-update-icon-cache` / `update-desktop-database` in install hooks (Pitfall 7).
- Document the sudoers rule install as a manual, reviewed step — **do not** auto-write sudoers from a `PKGBUILD` (security + it's the anti-impulse friction).

**Warning signs:**
`PKGBUILD` copies `nightguard_ctl.py`/`ngcommon.py` into the package; the package writes anything under root ownership or 0600; the commit argv's `/usr/bin/python3` differs from the interpreter the stack expects; install assumes `/home/danitrrga/...`.

**Phase to address:** **Phase: AUR packaging.**

---

### Pitfall 9: Autostart re-introduces the no-TTY problem (and shouldn't auto-open the editor)

**What goes wrong:**
A login autostart entry launches `ngtui` headless/detached (no terminal) — reviving Pitfall 1 — or auto-opens the full sanctioned editor every login (annoying, and the editor is a privileged-commit surface that shouldn't pop unprompted).

**Why it happens:**
Autostart `.desktop` / Hyprland `exec-once` run **without a terminal and without the interactive shell env**. Copying the launcher `Exec` naively drops the terminal wrapper or the `NIGHTGUARD_*` env.

**How to avoid:**
- If autostart is offered, autostart only the **read-only Waybar status surface**, not the editor TUI. The editor opens on demand via the launcher/click (with its terminal + env).
- If an autostarted TUI is genuinely wanted, it must still use the full `<terminal> -e ngtui` + env wrapper (Pitfall 1 + 4).
- Prefer Hyprland `exec-once = waybar` (status only) over auto-opening the editor.

**Warning signs:**
Login spawns a sudo prompt with nowhere to type; the editor pops every login; autostart entry lacks the terminal wrapper or `NIGHTGUARD_*` env.

**Phase to address:** **Phase: Autostart / login pin.**

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode author paths in the `.desktop`/Waybar `Exec` (skip env contract) | Launcher "just works" for the author today | Breaks for any other user; masks `python -m` vs installed divergence (Pitfall 5) | Author-only personal instance, *if* the published path is env-driven and documented |
| Match the Hyprland float rule on the generic terminal class | One-line rule, no `--class` flag | Floats every terminal; brittle across terminal/Hyprland updates | Never — use a unique `--class ngtui-float` |
| Waybar status reader shells `sudo`/NTP to be "accurate" | Live, authoritative-looking status | Blocks the bar; risks privilege creep → escape hatch (Pitfall 2) | Never — key-less, cached, non-blocking only |
| Vendor the LifeOS stack into the package to avoid the dependency | Self-contained install | Drifts from the live signer (violates PORT-02); preview lies | Never |
| Auto-write the sudoers rule from the `PKGBUILD` | One-step setup | Removes the reviewed friction; security footgun | Never — manual, documented, reviewed step |
| `Terminal=true` instead of explicit `<terminal> -e` | Shorter `.desktop` | No XDG terminal handler on Hyprland → no TTY → Pitfall 1 | Never on this platform |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `.desktop` ↔ Hyprland | `Exec=ngtui` / `Terminal=true` (no real terminal) | `Exec=<terminal> --class ngtui-float -e ngtui`, `Terminal=false` |
| Hyprland window rule | `title:` match (terminal title drifts) | `class:^(ngtui-float)$` (matches `initialClass`); verify via `hyprctl clients` |
| Waybar custom exec | Multi-line/invalid JSON; blocking `sudo`/NTP in exec | Single-line JSON (`return-type=json`, validate with `jq`); read-only, cached, `signal` for instant refresh |
| `uv tool` / `pipx` | Assuming the isolated venv sees the LifeOS stack or shell env | Resolve stack via `NIGHTGUARD_STACK_DIR` set *in the launcher*; fail loud at startup; `ngtui doctor` |
| `sudo` from launcher | Detached/no-TTY spawn; capturing stderr | Wrap in `App.suspend()`; leave stderr on the TTY; always run inside a real terminal |
| Icon theme | Wrong hicolor path/name; cache not refreshed | `…/hicolor/<size>/apps/ngtui.png`, `Icon=ngtui`, run `gtk-update-icon-cache` + `update-desktop-database` |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Waybar/launcher action mutates curfew without `sudo` | **Defeats the self-binding core value** — impulsive loosen with no friction | Only `backend.commit()` mutates; bar/launcher only open the TUI or show read-only status |
| Status reader granted `sudo`/`pkexec`/key access | Privilege creep; reader could forge/sign | Reader is key-less, unprivileged; never calls `ngcommon.read_key()` |
| Poisoned `NIGHTGUARD_STACK_DIR` redirects import + sudo argv | Malicious stack imported and **sudo-run** | Already mitigated: `_resolve_stack_dir()` pins an absolute realpath that must contain `nightguard_ctl.py`; keep launcher env trusted, don't widen it |
| `PKGBUILD` writes the root-owned key/config or sudoers | Breaks the root integrity boundary; removes friction | Package user-space only; key/config provisioned root-owned by the stack setup; sudoers is a manual reviewed step |
| Capturing the commit's stderr to "clean up" the UI | Hides the password/`REFUSED` prompt → silent failure | Leave stderr attached to the TTY (current behavior) |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Mysterious commit failure (no TTY) | User thinks the app is broken | Startup TTY self-check with a clear message; always launch in a terminal |
| Stale Waybar status after a commit | Bar contradicts reality (shows locked after grace) | `signal`-based refresh pushed by the TUI post-commit |
| Editor auto-opens every login | Annoyance; privileged surface pops unprompted | Autostart status only; editor on demand |
| Generic icon in launcher | Looks unbranded/unfinished | Correct hicolor install + cache refresh, bare `Icon=` name |
| Terminal closes instantly on launch | Looks like nothing happened | Ensure `-e ngtui` keeps the terminal alive for the TUI's lifetime; test the close-on-exit behavior of the chosen terminal |

## "Looks Done But Isn't" Checklist

- [ ] **`.desktop` launch:** opens, but **does the sudo commit actually prompt and succeed?** Verify a real loosen-with-token commit end-to-end from the launcher, not just that the TUI rendered.
- [ ] **Float rule:** window floats — verify via `hyprctl clients` that it matched `class:ngtui-float` and not by accident; confirm other terminals still tile.
- [ ] **Global install:** `ngtui` on PATH — but test the **installed script** (not `python -m`) with a **clean env** to confirm the stack resolves.
- [ ] **Waybar module:** shows status — validate the JSON with `jq`, confirm `on-click`/`on-click-right` both fire, and confirm the exec does **no** `sudo`/NTP and never blocks the bar.
- [ ] **Self-binding:** confirm **no** bar/launcher path can loosen the curfew without the sudo prompt (the load-bearing check).
- [ ] **Icon:** appears immediately after install (cache refreshed), not only after relogin.
- [ ] **AUR package:** installs **no** root-owned/0600 files and does **not** vendor `nightguard_ctl.py`/`ngcommon.py`.
- [ ] **Fresh-user story:** on a machine without the LifeOS stack, the app fails **loudly and actionably** at startup, not cryptically at commit.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| No-TTY commit failure | LOW | Switch `.desktop`/Waybar `Exec` to `<terminal> -e ngtui`; add startup `isatty()` check |
| Float rule not matching | LOW | Add `--class ngtui-float`; rewrite rule as `class:^(ngtui-float)$`; verify with `hyprctl clients` |
| Stack not resolving on install | LOW–MEDIUM | Set `NIGHTGUARD_*` in launcher; document prereq; add `ngtui doctor`; the existing `RuntimeError` already fails closed |
| Waybar blocking/invalid JSON | LOW | Make reader read-only+cached, emit single-line JSON, add `signal` refresh |
| Self-binding escape hatch shipped | HIGH | Revert the action immediately; treat as a security regression; audit all bar/launcher exec lines for `sudo`/`commit`/`+8` |
| Icon not showing | LOW | Fix hicolor path/name; run `gtk-update-icon-cache -f` + `update-desktop-database` |
| Package vendored the stack | MEDIUM | Remove vendored copies; switch to runtime import of the live stack; re-test preview-vs-signer parity |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. No-TTY inline-sudo break | `.desktop` floating-terminal launcher | End-to-end commit (with token spend) succeeds from the launcher; `isatty()` self-check present |
| 2. Quick-action escape hatch | Waybar module (+ milestone-wide non-goal) | No bar/launcher path loosens curfew without sudo; grep configs for `sudo`/`commit`/`+8` |
| 3. Float rule mismatch | `.desktop` floating-terminal launcher | `hyprctl clients` shows `ngtui-float`; other terminals tile |
| 4. Stack not resolving (global install) | Global install (`uv tool`) | Installed script with clean env resolves stack; `ngtui doctor` passes; fresh-user fails loudly |
| 5. `python -m` vs installed divergence | Global install (`uv tool`) | Test matrix runs both; identical startup behavior |
| 6. Waybar blocking/JSON/stale | Waybar module | `jq`-valid single-line JSON; no `sudo`/NTP in exec; `signal` refresh after commit |
| 7. Icon not showing | Custom brand icon | Icon appears immediately post-install; cache hooks run |
| 8. AUR runtime/stack/ownership | AUR packaging | No vendored stack; no root/0600 files in manifest; `/usr/bin/python3` argv intact |
| 9. Autostart revives no-TTY / auto-editor | Autostart / login pin | Autostart launches status only, or full terminal+env wrapper; no unprompted editor |

## Sources

- `ngtui/ngtui/backend.py` (read 2026-06-24) — `commit()` leaves stderr on the TTY, relies on `App.suspend()`; `_resolve_stack_dir()` pins realpath; sudo argv `[/usr/bin/python3, CTL_SCRIPT, commit, --from, tmp]`; PORT-02/03, CR-02, T-10-03. **HIGH**
- `.planning/PROJECT.md` — Core Value (self-binding), v2.1 Active scope (uv tool / .desktop floating terminal / Waybar left+right click / hicolor icon / autostart / AUR), `sudo` = anti-impulse friction. **HIGH**
- `.planning/milestones/v2.0-MILESTONE-AUDIT.md` — committed `guard.curfew_verdict` (B1), descoped native-kill, browser-policy softness (prior gotchas). **HIGH**
- Hyprland Wiki — Window Rules: static rules evaluated once at creation, match `initialClass`/`initialTitle`; cannot float on post-creation title change. `https://wiki.hypr.land/Configuring/Basics/Window-Rules/`. **HIGH**
- Hyprland issues #5744 (initialTitle matching), #8901 / #12808 (float/size rule regressions for some apps). **MEDIUM** (version-specific; confirms fragility)
- Waybar Wiki — Module: Custom: `return-type=json` single-line `{text,tooltip,class,…}`; `interval`/`signal`/`exec-on-event`; `on-click-right`; self-looping vs interval; flush stdout. `https://github.com/Alexays/Waybar/wiki/Module:-Custom`. **HIGH**
- astral.sh uv docs + Arch forum — `uv tool` installs an isolated venv with the console script on PATH; isolated env does not see external packages. `https://docs.astral.sh/uv/`, `https://bbs.archlinux.org/viewtopic.php?id=306879`. **MEDIUM**

---
*Pitfalls research for: desktop/Waybar integration of a Python Textual TUI-with-inline-sudo on Hyprland/omarchy*
*Researched: 2026-06-24*
