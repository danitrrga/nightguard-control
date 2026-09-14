<!-- GSD:project-start source:PROJECT.md -->
## Project

**Nightguard Control**

A Linux desktop surface — an omarchy-shell (Quickshell/QML) plugin — that is the
**single sanctioned editor** for a
"nightguard" curfew configuration — a self-binding ("anti-me") discipline tool. It
rate-limits how often you can *weaken* your own curfew, grants a small once-daily timed
bypass, and pairs with a guard hook that **auto-reverts any out-of-band hand edits** to
the config. The repo is the clean, publishable product; the author runs a personal
instance wired into his LifeOS (see Context).

**Core Value:** A late-night, impulsive version of the user **cannot quietly loosen their own curfew** —
loosening costs a limited weekly token, and editing the raw config by hand silently
reverts. Everything else is secondary to that guarantee holding.

### Constraints

- **Tech stack (live)**: omarchy-shell plugin in QML (the panel, the workshop), a
  dependency-free Python CLI (`ngtui`) behind it, and a root Python signer
  (`nightguard_ctl.py`) as the sole writer. Authorisation is `pkexec`/polkit.
- **Platform**: Linux / Omarchy 4 / Hyprland.
- **Retired and removed**: the Windows Tauri/Rust tree and the `ngtui` Textual
  terminal app. They are not in this branch; `archive/windows-tauri` holds them
  whole. Anything anywhere describing Tauri, DPAPI or PowerShell is about that.
- **Security**: HMAC-SHA256 over config + state; the 32-byte key is a root-owned
  `0600` file under `/var/lib/nightguard`, in a root-owned directory — rename and
  unlink are governed by the directory's mode, which is why the directory matters
  more than the file. Atomic writes; fail-closed on tamper.
- **Design**: the shell's own kit and the user's live theme. No fixed hex anywhere
  in the QML — colours come from `Color`/`Style` and a test refuses a literal.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

The whole of it. There is no build step, no package manager at runtime, and no
third-party library in the trust path.

| Piece | Where | What it is |
|---|---|---|
| The signer | `scripts/linux/nightguard_ctl.py` -> `/usr/local/lib/nightguard` | Root Python. The only writer of `config.yaml` and the only thing that holds the key. Classifies a change as tightening or loosening, prices it, signs. Reached through `pkexec`; returns 0/1/2. |
| The guard | `scripts/linux/guard.py`, `appblock.py` | Reads the verdict and enforces it. Blocking matches the exact basename of `/proc/PID/exe` — never `comm`, never a substring. |
| The watchdog | `scripts/linux/nightguard_watchdog.py` + a root systemd timer | Reverts hand edits every 60 s and keeps the browser policy in place. Stopping it needs admin auth (`polkit/00-nightguard.rules`, `AUTH_ADMIN`, no caching). |
| The minimal YAML | `scripts/linux/ngcommon.py` | A hand-written parser. Deliberate: a real emitter would rewrite the bytes the signature covers. |
| The CLI | `ngtui/` | Dependency-free Python, installed as a `uv tool` snapshot. Five head-less subcommands the panel runs: `status`, `panel`, `apps`, `propose`, `commit`. Every one exits 0 with a single JSON line. |
| The panel | `packaging/omarchy/plugins/danitrrga.nightguard/*.qml` | An Omarchy 4 (Quickshell) plugin. A bar dropdown and a window; the window lands on the glance. It never writes — it stages, prices, and hands a proposal to the signer. |
| The deploy | `scripts/linux/deploy.sh` | One root command, idempotent, does everything. The repo is not what runs: this is. |

Hard rules that are not style:

- **Never emit YAML.** Edits are line edits (`ngtui/ngtui/lineedit.py`) that keep
  comments, order and whitespace. A re-emitted file changes the bytes the signer
  HMACs, which reads as tampering.
- **`pkexec` sets `PKEXEC_UID`, never `SUDO_UID`.** Exit 126 means the dialog was
  dismissed, 127 means not authorised. Neither is a failure of the change.
- **`config.yaml` stays user-owned on purpose.** The revert model needs the hand
  edit to be possible so the watchdog can undo it — and the watchdog derives the
  owner's home from it, so a root-owned config silently empties the game catalog.
- **Blocking identity is the executable basename.** Web apps all run as the same
  browser process, so their identity is the address and they go to the site list.
- **The tests are the contract.** `cd ngtui && uv run --with pytest python -m pytest -q`.

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->


<!-- BEGIN LIFEOS-SYSTEM-POINTER (managed by sync_system_doc.py) -->

## Shared agent-config system

This project's MCP servers, skills, plugins, and memory are governed by a **shared system rooted in forge** (`/home/danitrrga/dev/Projects/forge`). Generated files here (`.claude/settings.local.json`, `~/.claude.json`) are **overwritten on every SessionStart** — do not hand-edit them. `.mcp.json` is NOT one of them: nothing generates it, so it is yours to maintain and it will never be corrected.

**Before changing any MCP server, skill, plugin, secret, or memory store, read [`.claude/AGENT-SYSTEM.md`](.claude/AGENT-SYSTEM.md)** — it explains what to edit in forge `config/` and which generator to run. Editing the wrong file silently breaks across sessions.
<!-- END LIFEOS-SYSTEM-POINTER -->
