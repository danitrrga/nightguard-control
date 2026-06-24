# Phase 10: Linux App — omarchy TUI - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning

<domain>
## Phase Boundary

The **sole sanctioned curfew editor**, rebuilt for Linux as a **terminal/TUI thin-client** over the existing Python trust stack. It **reads** state via `nightguard_ctl.py show` (JSON: `weekly_spent`, `grace`, hmacs, `ledger`) and the guard verdict, and **signs allowed edits** by invoking `sudo nightguard_ctl.py commit --from <file>`. It holds **no key** and re-implements **no crypto** (PORT-02/03, ROOT-03).

**In scope:** a Textual TUI that displays lock status / countdown / token meter / grace (read-only), and lets the user edit a defined set of config fields with a tighten/loosen + token-cost preview, committing via sudo.
**Out of scope:** holding/handling the signing key, any second crypto stack, granting grace (display-only this phase), StayFree blocklist import (separate future phase), Tauri/GUI.
</domain>

<decisions>
## Implementation Decisions

### TUI stack & feel
- **D-01:** Build the TUI with **Textual**. Its CSS-like styling maps cleanly onto live aether colors; rich interactive widgets. Accepted as the heaviest dep in exchange for look/feel + theming ease.
- **D-02:** Aesthetic is **omarchy-native, minimal**. Not the Windows Moonlit Indigo palette — colors come from the live desktop theme (see Theming).

### Interaction model
- **D-03:** **Single-key command-driven**, keyboard-only (e.g. one keystroke per action: edit, quit, etc.). Matches PORT-01 "command-driven, minimal". No arrow-key menu navigation as the primary model.

### Live theming (aether)
- **D-04:** Colors come from **aether's theme output** (`~/.config/aether/theme`; `/usr/bin/aether` is the desktop theme generator. omarchy's `~/.config/omarchy/current/theme` is the broader desktop theme system — researcher to confirm which is the canonical color source on this box).
- **D-05:** Theming is **live-watched** — watch the theme output and **repaint the running TUI** when the desktop theme changes (not just read-once-at-launch).

### Edit + sudo commit flow
- **D-06:** **Preview before commit** — the TUI shows **tighten/loosen direction + token cost** BEFORE the sudo prompt (mirrors Windows UI-04 anti-impulse clarity).
- **D-07:** The preview is computed by **importing the Python classifier** (`guard.py` / `ngcommon.py` direction logic) directly — this reuses the single Python stack, needs **no key** and **no crypto** (classification ≠ signing), and requires **no control-CLI change**. (Do NOT add a `ctl --dry-run` for this.)
- **D-08:** On confirm, the TUI writes the proposed config to a temp file and runs **`sudo nightguard_ctl.py commit --from <temp>`**, surfacing the **password prompt inline** (no NOPASSWD — the prompt is intentional friction, Phase 7 D-4). Show the CLI's `REFUSED (<direction>): <reason>` on nonzero exit; show `committed … tokens N/3 used` on success.

### Editable scope
- **D-09:** Editable fields: **curfew window (`curfew.start`/`curfew.end`)**, **`curfew.allow_commands`**, **enabled toggles** (`curfew.enabled`, `clock_protection.enabled`, `watchdog.enabled`, `blocking.*.enabled`), and **blocking blacklists** (`blocking.native_apps.blacklist`, `browser_extension` settings).
- **D-10:** Read-only display: lock status, countdown, token meter + weekly reset, grace status/remaining, config/state hmacs, audit ledger. Messages (`message`/`tamper_message`/`offline_message`) and `timezone` are not part of the editable surface this phase.

### Grace
- **D-11:** **Display-only this phase.** The TUI shows grace status/remaining (Success Criterion 2), but does **not** grant grace. The control-CLI currently has **no grace-granting command** (`guard.py` only *reads* the grace window); wiring grant (a `ctl grace` command that root-signs the window into state + a TUI key) is a deferred follow-up.

### Claude's Discretion
- Exact Textual screen/layout composition, widget choices, and keybinding letters (researcher/planner to propose; single-key model per D-03).
- Which of aether vs omarchy is the canonical live-color source (D-04) — researcher to verify on this box and pick the stable one.
- How config edits are entered per field (inline field editor vs prompt) — within the single-key model.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Trust stack (the thin-client's backend — LifeOS, separate repo)
- `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_ctl.py` — the control-CLI the TUI shells to: subcommands `init` / `verify` / `show` (JSON state + hashes) / `commit --from <path> [--rebaseline]`. Sole signer; enforces the weekly token quota; needs root for the key.
- `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/guard.py` — `curfew_verdict(cfg, state)`, `decide()`, grace-window read logic (`window_start`/`window_end`). Source of the direction/verdict logic the TUI imports for preview (D-07).
- `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/ngcommon.py` — config/state load, HMAC, paths (`CONFIG`, `SANCTIONED`), `config_hmac`. The single HMAC implementation.
- `/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard/nightguard_watchdog.py` — root watchdog (context only; not modified this phase).
- Live `config.yaml` shape (the editable surface): `timezone`, `curfew{enabled,start,end,allow_commands,*_message,block_when_offline}`, `clock_protection`, `watchdog`, `blocking{browser_extension,native_apps.blacklist}`.

### Requirements & decisions
- `.planning/REQUIREMENTS.md` §"Linux App (Phase 10)" — PORT-01/02/03; §"Root Integrity Wall" — ROOT-03 (sign via sudo→control-CLI, sole signer, flock, quota).
- `.planning/ROADMAP.md` §"Phase 10" — goal, success criteria, open questions.
- `.planning/phases/07-root-integrity-wall/07-CONTEXT.md` — D-4 (sudo with password, no NOPASSWD) and the control-CLI signing model this phase builds on.
- `.planning/phases/REVIEWS.md` — the 2026-06-22 curation that set Tauri → omarchy TUI thin-client (one Python stack, one HMAC).

### Theming
- `/usr/bin/aether` (`--help`) — theme generator; output dir `~/.config/aether/theme`.
- `~/.config/omarchy/current/theme` — omarchy's active desktop theme (candidate canonical color source; verify in research).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `nightguard_ctl.py show` already emits structured JSON state — the TUI's read path is a subprocess call + JSON parse, no new backend.
- `guard.py`/`ngcommon.py` direction + config logic is importable Python — powers the edit preview (D-07) without touching the signer or the key.

### Established Patterns
- **One root key → one root watchdog → one signer (control-CLI behind sudo) → one config schema → one HMAC (Python)** — the TUI is strictly a client on top; it must not add a second crypto path.
- Sudo-with-password is the deliberate anti-impulse friction (ROOT-03 / Phase 7 D-4) — the TUI surfaces it, never bypasses it.

### Integration Points
- Read: `nightguard_ctl.py show` (+ guard verdict for lock status/countdown).
- Write: `sudo nightguard_ctl.py commit --from <temp config>`.
- Theme: aether/omarchy theme files → Textual color variables (live-watched).
</code_context>

<specifics>
## Specific Ideas

- Mirror the Windows app's read-only surface (UI-01/02/03 equivalents: lock + countdown, 3-token meter + reset, grace availability) but in a minimal single-key TUI.
- The edit preview must make the **token cost and tighten/loosen direction unmistakable before** the user authenticates — this is the core anti-impulse moment.
</specifics>

<deferred>
## Deferred Ideas

- **Grace granting** — a `nightguard_ctl.py grace` command (root-signs the grace window into state) + a single-key TUI action to restore the Windows "+8" feature on Linux. Out of scope this phase (display-only, D-11); candidate follow-up.
- **StayFree blocklist import** — Phase 9 found StayFree's curated lists are fully offline-recoverable from `~/.config/StayFree/config.db`; importing them into nightguard's own `blocking` config/enforcement is a strong candidate **new phase** (not this TUI phase).
- **`ctl --dry-run`** — considered for the preview path but rejected (D-07 imports the classifier instead); noted in case the signer ever needs a server-side preview.

### Reviewed Todos (not folded)
None — no pending todos matched this phase.
</deferred>

---

*Phase: 10-linux-app-omarchy-tui-was-tauri-port*
*Context gathered: 2026-06-24*
