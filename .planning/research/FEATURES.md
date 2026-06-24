# Feature Research

> **This file has two sections.**
> - **Part A (v2.1 · Desktop Integration)** — the current milestone: launcher + Waybar + icon + autostart + AUR packaging around the existing `ngtui` TUI. *Researched 2026-06-24.*
> - **Part B (v1.0/v2.0 · Core commitment-device mechanics)** — prior research on the self-binding mechanics themselves (auto-revert, tokens, grace, asymmetry). Kept as the canonical anti-feature / trust reference; the v2.1 work must not violate it. *Researched 2026-06-04.*

---
---

# Part A — v2.1 Desktop Integration

**Domain:** Desktop integration (omarchy/Hyprland + Waybar + wofi/walker) for an existing Python Textual TUI — `ngtui`, a self-binding curfew tool.
**Researched:** 2026-06-24
**Confidence:** HIGH (Waybar / `.desktop` / Hyprland-window-rule / AUR mechanics are documented and verified; the only MEDIUM items are subjective "what users expect from a TUI-as-app" judgments)

> **Scope guard:** This milestone adds *desktop wrapping* around an already-built TUI. It builds **zero new editing/commit capability**. The TUI's `EditScreen` + inline-sudo commit (10-UI-SPEC) remains the *only* path that can change the config. Every feature below is launcher / indicator / packaging plumbing. The load-bearing rule throughout — restated from Part B's central lesson at the desktop layer: **no Waybar or launcher surface may loosen the curfew or bypass the sudo + cost-preview friction. The bar is a *window*, never a *lever*.**

## Feature Landscape

### Table Stakes (Users Expect These)

A "terminal app that feels like an app" and a "glanceable bar indicator" are assumed to have these. Missing = the integration feels half-done.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Global `ngtui` command** (`uv tool install`) | A launcher/Waybar/`.desktop` Exec line needs a real binary on `$PATH`, not `python -m ngtui` from a dev venv | MEDIUM | `uv tool install` builds an isolated venv + shims `~/.local/bin/ngtui`. Must resolve `NIGHTGUARD_STACK_DIR`/`NIGHTGUARD_DIR` defaults *without* the dev `env …` prelude (PROJECT line 152). Dependency: a `[project.scripts]` entry point in `ngtui`. |
| **`.desktop` launcher entry** | App must appear in wofi/walker like any GUI app; selecting it opens the TUI | LOW | `Exec=<omarchy-terminal> --class ngtui-float -e ngtui`. `Terminal=false` (we own the terminal via `-e`, not XDG's terminal handler). `Icon=nightguard`. Installs to `/usr/share/applications/` (AUR) or `~/.local/share/applications/` (manual). |
| **Floating, centered, sized window** | A TUI launched as an app should pop as a tidy floating panel, not steal a tiled slot or open fullscreen | LOW | Hyprland `windowrulev2 = float / center / size W H, class:ngtui-float`. The `--class` flag on the terminal is the join key. This is THE thing that makes a TUI "feel like an app." (verified: Hyprland Window Rules wiki, omarchy #1775) |
| **Custom brand icon in hicolor** | Launcher + Waybar both reference an icon by name; project mandates own-brand, no borrowed logos | MEDIUM | Ship an SVG (scalable) + a couple of PNG sizes to `…/icons/hicolor/{scalable,48x48,…}/apps/nightguard.{svg,png}`. Run `gtk-update-icon-cache` in the AUR `.install` hook. Icon design is the only net-new creative asset. |
| **Waybar module showing the icon** | The milestone explicitly wants a nightguard presence in the bar | LOW | `custom/nightguard` module. Even a static icon + left-click-to-open is a complete table-stakes version. |
| **Left-click opens the TUI** | Universal Waybar idiom: primary click = open the thing | LOW | `"on-click": "<terminal> --class ngtui-float -e ngtui"` — reuse the exact launch command from `.desktop` (factor into one shared script). |
| **Right-click menu of actions** | Secondary click = context menu is the Waybar convention (`on-click-right`) | MEDIUM | `"on-click-right": "ngtui-menu"` → a wofi/walker `dmenu` list. Contents specified below. Complexity is in *what's safe to put in it*, not the wiring. |
| **README install path** | A publishable repo needs a documented "how do I run this" | LOW | Must honestly document the root-owned trust-stack prerequisite (see packaging differentiator). |

### Differentiators (Competitive Advantage)

Features that make this integration genuinely good and reinforce the Core Value — glanceability that *strengthens* the bind, never an escape.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Live lock glyph in the bar** | A glanceable `●/◐/○` curfew state, always in peripheral vision — the discipline tool is *present*, not hidden behind a launch | MEDIUM | `return-type:"json"` → `{"text":"● 04:13","class":"locked","tooltip":"…"}`. Source: `backend.live_verdict(cfg,state)` (key-less, already exists). Reuse the exact glyph vocab from 10-UI-SPEC (`● LOCKED` / `◐ GRACE` / `○ OPEN`). |
| **Color-by-state via CSS class** | Red when locked, accent when grace, dim/green when open — instant state read without parsing text | LOW | Emit `class` (`locked`/`grace`/`open`/`tamper`/`offline`); style in Waybar `style.css`. Mirror 10-UI-SPEC's role→color mapping (error/accent/success) so bar and TUI agree. |
| **Token count in the bar / tooltip** | The scarcest resource (3 weekly loosen tokens) is what the user most wants to glance at — "do I even have a token left to spend tonight?" Glanceable scarcity *deters* (see Part B Q3) | LOW | `backend.tokens_left()` (exists). Render as `● ● ○` or `2/3` in `text` or `tooltip`. |
| **Rich tooltip (hover = full status)** | Hover gives the whole picture (countdown, tokens, grace, reset date) without opening anything — a read-only mini-StatusScreen | LOW | Multi-line `tooltip` from the same `live_verdict` read. |
| **Signal-driven refresh (not 1s polling)** | The guard/verdict shouldn't be hammered every second; refresh the bar *after* a commit or grace use, plus a slow safety interval | MEDIUM | Waybar `"signal": N` + `"interval": 30/60`. After the TUI commits, it (or the CLI) runs `pkill -SIGRTMIN+N waybar` to repaint instantly. Verified (waybar-custom(5)): a signal module runs once at startup, then only on signal/interval. Clean "live but not chatty" pattern. |
| **Live countdown in the bar** | Shows time-until-unlock at a glance during a lock | MEDIUM | Tension with signal-driven refresh: a precise 1s countdown means `interval:1` (re-reads state each tick). Compromise: coarse countdown (`● <2h12m`) on the 30–60s interval, OR a self-looping script that computes countdown *locally* from a cached unlock-time and re-reads verdict only on signal. Recommend coarse. |
| **Honest AUR packaging that declares the trust-stack dependency** | The hard, differentiating problem: the app is a *thin client over a separate root-owned Python trust stack* a random AUR user won't have. A package that fails loudly + explains beats one that silently can't sign | HIGH | The AUR `PKGBUILD` installs only the TUI + launcher + icon. The trust stack (`ngcommon`/`guard`/`nightguard_ctl` + root key + systemd watchdog) is a prerequisite, not bundleable. Options below. This is the real engineering of the milestone. |
| **"Not initialized" graceful degradation** | An installer who hasn't set up the root stack should get a clear "nightguard is not initialized — run `nightguard_ctl init`" (already in 10-UI-SPEC) in BOTH the TUI and the bar (dim `○ —` / "uninit"), never a crash | MEDIUM | Reuses the TUI's existing not-initialized state; the Waybar script must handle the same absence (no `guard.json`/config) without spewing errors into the bar. |

### Anti-Features (Commonly Requested, Often Problematic)

These look convenient but **undermine the self-binding Core Value** — the product exists so a late-night impulsive self *cannot quietly loosen the curfew*. A frictionless bar surface is exactly the escape hatch Part B warns about, relocated to the desktop layer.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **"Loosen curfew" / "extend by N" quick-action in the right-click menu** | Convenience — "just let me push it 30 min from the bar" | This IS the impulsive escape hatch the product blocks. Any loosen MUST pass the EditScreen → cost-preview → `sudo` friction (10-UI-SPEC D-06/D-08). A bar one-click loosen deletes the entire reason the app exists. | Right-click → "Open editor" launches the TUI's `EditScreen`. Loosening is *only* reachable behind the full anti-impulse gate. |
| **"Use grace (+8 min)" as a bare menu click** | One-tap convenience to unlock for 8 min | Grace is once-daily and consequential; a no-confirmation bar button trivializes it and invites impulsive taps. (10-UI-SPEC marks grace **display-only this phase, D-11** — not committable from the TUI yet, so a bar action would be ahead of the core.) | Show grace *status* (available / used / `MM:SS`) read-only in tooltip/menu. If grace-commit ever ships, route it through a confirm gate like loosen — never a bare click. |
| **Editing config directly from the Waybar menu** | Skip opening the app | The TUI is the *single sanctioned editor* with the classifier + sudo path; a second edit surface = a second thing to keep correct + a second bypass vector. | Menu's only edit affordance is "Open editor" → launches `ngtui` on `EditScreen`. |
| **Echoing HMACs / key material into the bar** | "Show integrity status in the bar" | The TUI deliberately holds no key and shows hmacs only truncated + advisory (PORT-03). Surfacing crypto state in a polled bar script widens exposure for no user benefit. | Bar shows the *verdict* (`live_verdict`, key-less), not hmac internals. Integrity detail stays in the TUI's dim panel. |
| **Backgrounding `ngtui` / a system-tray daemon to keep state "live"** | Make the bar instant + app always-resident | Adds a long-running user process to manage, duplicates the guard as source of truth, tempts holding state in memory. The root watchdog is the truth; the bar should be a thin read. | Stateless Waybar script reading `live_verdict` on interval/signal. The TUI launches fresh each time. |
| **Autostart that force-opens the TUI window every login** | "Keep the curfew front-and-center" | An auto-popping floating terminal every login is intrusive and trains the user to dismiss it (banner blindness — echoes Part B's "no nagging"). The Waybar module already provides the always-present surface. | Autostart the *Waybar module* (it's part of the bar config, present by default). TUI-window autostart should be **opt-in and off by default**. |
| **Notifications / nagging as curfew approaches** | "Warn me before lockout" | Scope creep into a notification system; becomes dismissible noise (Part B anti-feature). Not in the milestone. | Defer. The glanceable bar glyph already telegraphs an approaching lock. |

#### Right-click menu — recommended contents (all read-only or friction-preserving)

A wofi/walker `dmenu` list (`ngtui-menu` script). Every entry is either a read-only glance or a launch into the *already-gated* TUI:

| Entry | Action | Safe? |
|-------|--------|-------|
| `● LOCKED · 04:13 until 05:30` (status header) | Display only | ✅ read-only |
| `Tokens: ● ● ○  (2 of 3 · resets Mon)` | Display only | ✅ read-only |
| `Grace: unavailable today` (or `◐ active · MM:SS`) | Display only | ✅ read-only (display-only per D-11) |
| `Open status` | Launch `ngtui` (StatusScreen) | ✅ |
| `Open editor` | Launch `ngtui` → `EditScreen` | ✅ — loosening still behind cost-preview + sudo |
| `Refresh bar` | `pkill -SIGRTMIN+N waybar` | ✅ harmless |

> **Explicitly NOT in the menu:** any "loosen", "extend", "disable curfew", "use grace", or direct-edit action. Those exist *only* inside the TUI behind the D-06/D-08 gate.

## Feature Dependencies (v2.1)

```
[Global `ngtui` command (uv tool install + entry point)]
    └──requires──> [backend.live_verdict / tokens_left / read_state]  (already built, v2.0)
    └──enables──> [.desktop launcher]
    └──enables──> [Waybar left-click open]
    └──enables──> [Waybar right-click menu → Open editor/status]

[.desktop launcher] ──requires──> [Floating window rule (Hyprland --class)]
[.desktop launcher] ──requires──> [Custom brand icon in hicolor]

[Waybar module icon] ──requires──> [Custom brand icon in hicolor]
[Waybar live status] ──requires──> [a thin non-interactive status read of backend.live_verdict]
[Waybar color-by-state] ──requires──> [Waybar live status (json `class` field)]
[Signal-driven refresh] ──enhances──> [Waybar live status]   (TUI commit → pkill -SIGRTMIN+N)
[Live countdown] ──conflicts──> [Signal-driven-only refresh]  (countdown wants ~1s; resolve via coarse or local compute)

[AUR PKGBUILD] ──requires──> [Global command + .desktop + icon all installable to system paths]
[AUR PKGBUILD] ──depends-on (external)──> [root-owned Python trust stack]  (NOT shippable in the same package)
[Autostart (opt-in)] ──requires──> [.desktop launcher OR Waybar module in bar config]
```

### Dependency Notes

- **Everything requires the global `ngtui` command.** The launcher, both click handlers, and the menu all shell out to it — build it first.
- **Two consumers of `backend`:** the TUI (interactive) and the Waybar status script (one-shot read of `live_verdict`/`tokens_left`). Recommend adding a hidden non-interactive subcommand (`ngtui status --json`) so there's a single entry point rather than a second script importing `backend`.
- **Icon is a shared dependency** of launcher + Waybar module — install once, reference by name (`nightguard`).
- **Signal refresh enhances but isn't required by live status** — start with interval polling (30–60s); add the post-commit `pkill -SIGRTMIN+N waybar` as polish.
- **Live countdown conflicts with signal-only refresh** — a precise countdown needs frequent re-render. Resolve by computing it *locally* from a cached unlock timestamp (no guard read) and re-reading verdict only on signal/coarse interval. Recommend coarse.
- **AUR package cannot bundle the trust stack** — the root key + systemd system watchdog + sanctioned config are machine-specific, root-owned, security-sensitive. The package ships the client; the README/`.install` message points to trust-stack setup. Hard boundary, not a convenience.

## MVP Definition (v2.1)

### Launch With (v2.1 core)

The minimum that makes `ngtui` "a first-class omarchy desktop app."

- [ ] **Global `ngtui` command** via `uv tool install` + `[project.scripts]`, resolving stack-dir defaults without the dev env prelude — *nothing else works without it.*
- [ ] **`.desktop` launcher** opening `ngtui` in a floating/centered/sized terminal (`--class ngtui-float` + Hyprland rule) — appears in wofi/walker.
- [ ] **Custom brand icon** in hicolor (SVG + PNG), referenced by launcher and bar — mandated own-brand asset.
- [ ] **Waybar module** with the icon + **left-click opens the TUI** + **right-click menu** (read-only status + "Open status" / "Open editor") — the headline of the milestone.
- [ ] **Live lock glyph + color-by-state + token tooltip** from `live_verdict`/`tokens_left` (json `text`/`class`/`tooltip`) — the glanceable indicator; without it the module is just a launcher button.
- [ ] **README install path** honestly documenting the trust-stack prerequisite.

### Add After Validation (v2.1.x polish)

- [ ] **Signal-driven instant refresh** (`pkill -SIGRTMIN+N waybar` on commit) — *trigger: interval polling feels laggy after a commit.*
- [ ] **AUR `PKGBUILD`** + `.install` hook (icon cache) + a loud "trust stack required / run init" message — *trigger: ready to publish for non-author installs.*
- [ ] **Opt-in login autostart** (Waybar module autostarts by default via bar config; TUI-window autostart off by default) — *trigger: user wants the surface pinned on login.*
- [ ] **"Not initialized" graceful state in the Waybar script** (dim `○ —` not errors) — *trigger: first non-author / pre-init install test.*

### Future Consideration (v2.2+)

- [ ] **Coarse live countdown in bar text** — defer until refresh model (signal vs local-compute) is settled; cosmetic.
- [ ] **Grace as a (gated) action** rather than display-only — blocked on grace-commit landing in the TUI (D-11); must arrive with a confirm gate, never a bare click.
- [ ] **Curfew-approaching notification** — separate notification concern; out of this milestone.

## Feature Prioritization Matrix (v2.1)

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Global `ngtui` command (uv tool install + entry point) | HIGH | MEDIUM | P1 |
| `.desktop` launcher + floating window rule | HIGH | LOW | P1 |
| Custom brand icon (hicolor) | MEDIUM | MEDIUM | P1 |
| Waybar module + left-click open | HIGH | LOW | P1 |
| Waybar right-click status/actions menu | HIGH | MEDIUM | P1 |
| Live lock glyph + color-by-state + token tooltip | HIGH | MEDIUM | P1 |
| README honest install path | MEDIUM | LOW | P1 |
| Signal-driven refresh on commit | MEDIUM | MEDIUM | P2 |
| AUR PKGBUILD + trust-stack-aware install message | MEDIUM | HIGH | P2 |
| "Not initialized" graceful bar/TUI degradation | MEDIUM | MEDIUM | P2 |
| Opt-in login autostart | LOW | LOW | P2 |
| Coarse live countdown in bar | LOW | MEDIUM | P3 |
| Grace as a gated action | LOW (until D-11) | MEDIUM | P3 |
| Curfew-approaching notification | LOW | MEDIUM | P3 (out of scope) |

## Prior-Art / Idiomatic-Pattern Analysis (v2.1)

No direct competitor (bespoke tool), so the comparison is against *idiomatic patterns* for the two genres this milestone touches.

| Feature | Typical Waybar custom module (weather/vpn/updates) | Typical TUI-as-app (floating btop/yazi/email TUI) | Our Approach |
|---------|----------------------------------------------------|---------------------------------------------------|--------------|
| Display | json `text`+`class`+`tooltip`, polled on `interval` | n/a | json from `live_verdict`; coarse refresh + signal on commit |
| Left-click | toggle/run the underlying tool | n/a | open `ngtui` (StatusScreen) |
| Right-click | secondary action or `dmenu` menu | n/a | wofi menu — **read-only status + launch-into-gated-editor only** |
| Window behavior | n/a | `--class` + Hyprland float/center/size rule | identical pattern (`ngtui-float`) |
| Icon | Nerd Font glyph or themed icon | inherits terminal icon | **own-brand hicolor icon** (mandated, no borrowed logo) |
| Quick mutate-from-bar | common (toggle vpn, `mpc toggle`) | n/a | **deliberately forbidden** — would be an escape hatch; all mutation stays behind the TUI's sudo + cost gate |
| Packaging | dotfiles repo | AUR / `uv tool` / pipx | AUR PKGBUILD (client only) + `uv tool install`; trust stack is an external prereq |

> The single most important deviation from the idiomatic Waybar module: **normal modules let you mutate state with a click; this one must not.** That constraint *is* the product, restated at the desktop-integration layer.

## Sources (v2.1)

- [waybar-custom(5) — Arch manual pages](https://man.archlinux.org/man/waybar-custom.5.en) — HIGH — `on-click`/`on-click-right`/`on-click-middle`, `return-type:json` fields (`text`/`tooltip`/`class`/`percentage`), `interval`, `signal` (SIGRTMIN+N), `exec-on-event`.
- [Custom module click behavior — Alexays/Waybar #2166](https://github.com/Alexays/Waybar/issues/2166) — MEDIUM — real-world click-handler config patterns.
- [Window Rules — Hyprland Wiki](https://wiki.hypr.land/0.45.0/Configuring/Window-Rules/) — HIGH — `windowrulev2 float/center/size, class:…` for floating terminal windows.
- [Launching things into floating windows — basecamp/omarchy #1775](https://github.com/basecamp/omarchy/issues/1775) — MEDIUM — omarchy-specific floating-launch + `--class`.
- [Python package guidelines — ArchWiki](https://wiki.archlinux.org/title/Python_package_guidelines) — HIGH — PKGBUILD conventions for Python apps.
- [Arch User Repository — ArchWiki](https://wiki.archlinux.org/title/Arch_User_Repository) — HIGH — AUR publishing + `.install` hooks (`gtk-update-icon-cache`, hicolor).
- [uv: A Complete Guide](https://pydevtools.com/handbook/explanation/uv-complete-guide/) — MEDIUM — `uv tool install` isolated-app install model.
- `.planning/PROJECT.md` (v2.1 milestone, Core Value, Constraints) + `.planning/phases/10-…/10-UI-SPEC.md` (glyph/color vocab, anti-impulse gate, key-less `backend` API) — HIGH — internal contract the integration must match.

---
---

# Part B — v1.0 / v2.0 Core Commitment-Device Mechanics (prior research)

**Domain:** Self-binding / commitment-device / focus-lock tool (single-operator, local)
**Researched:** 2026-06-04
**Confidence:** MEDIUM-HIGH (Cold Turkey, Freedom, SelfControl, AppBlock, Beeminder, One Sec, Forest corroborated by official docs + reviews; UX-trap claims cross-sourced. Most evidence is product docs/reviews rather than controlled studies, except One Sec which has a PNAS paper.)

> Scope note: the core mechanics (auto-revert, 3 tokens/week, +8 grace, HMAC) are **locked**. This part does not re-litigate them. It maps how proven tools implement the *surrounding* UX so the roadmap doesn't miss table-stakes or fall into known traps. **The v2.1 desktop work (Part A) must respect every anti-feature below** — the bar/menu must not become the escape hatch this part repeatedly warns about.

---

## The category's central lesson

Every durable tool in this space (Cold Turkey, SelfControl, Freedom Locked Mode, Beeminder, AppBlock Strict Mode) converges on one principle:

> **The friction must live somewhere the impulsive self cannot reach in the moment.** Trust comes from the user *knowing* they can't quietly undo it, not from a setting they could toggle.

The failure mode is universal too: the escape hatch becomes the default. Freedom's own docs admit Locked Mode is defeated by simply quitting the app; SelfControl's whole reputation rests on the block surviving quit/restart/uninstall. Nightguard's enforcement-lives-in-the-root-guard architecture is the *correct* answer. The research below mostly validates that choice and details the UX layer around it.

---

## Feature Landscape

### Table Stakes (Users Expect These — missing = the tool fails its purpose)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Enforcement survives the app being closed/killed** | The #1 trust differentiator. Freedom is criticized because quitting kills the block; SelfControl is praised because nothing short of waiting works. | — (in spec) | Nightguard's enforcement-not-in-the-app architecture is exactly right. Surface it: "closing this app does not weaken anything." |
| **Tamper detected AND silently corrected, not just logged** | Users expect the system to win the fight, not narrate it. | — (in spec) | Auto-revert-to-sanctioned is the strongest version. Silent revert gives impulse-self nothing to argue with. |
| **Clock-tampering cannot widen/end a lock early** | A *known, named bypass* across the category (SelfControl #28; Cold Turkey blocks the Time settings panel). Users will test it. | — (NTP in spec) | NTP-true-time boxing is table-stakes-correct. Must degrade gracefully when NTP unreachable — fail-closed is the right default. |
| **Clear current status: locked/open, and when it next changes** | Every tool shows this. Without "when does this end?" the user feels trapped → bypass attempts. | LOW | The countdown is the single most important calming element. |
| **The block is *legible*** | Opaque blocks erode trust; users suspect the tool is broken and look for the off switch. | LOW | The edit panel doubles as the "what's enforced" view. |
| **Honest about its own limits** | Sophisticated self-binders know admin = breakable. Overpromising loses trust on first bypass. | — (in spec) | "Friction past the impulse threshold, not a literal vault" is the mature stance. |
| **A limited emergency/grace path that exists** | Tools *without* any grace get uninstalled in the first genuine emergency, taking the whole boundary with them. | — (+8 grace in spec) | Presence of grace is itself table-stakes for retention; the *design* is the differentiator. |

### Differentiators (where Nightguard competes)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Asymmetric cost: tightening free+instant, loosening rate-limited** | The category's gold-standard move (Beeminder's whole model) and Nightguard's core value. | MEDIUM (classifier) | Per-field classifier is finer-grained than Beeminder's single dial — a real edge, and the riskiest correctness surface. |
| **Weekly loosening *budget* (3 tokens) vs per-event delay** | More legible than a time-delay ("I have 2 left") and creates natural pacing. | LOW-MEDIUM | The 3-dot meter fits scarcity-UX: a visibly limited resource drives deliberate use. |
| **Timed grace (8 min) that auto-re-locks** | Removes the "forgot to turn it back on" failure mode entirely. | MEDIUM | Genuinely better than "burn one exit, fully open." |
| **Grace doesn't draw from the loosening pool** | A genuine 8-min need doesn't cost a structural loosening. | — | Keep them visually distinct on the status screen. |
| **Single sanctioned editor + signed state** | The "one door" model made strong via HMAC; hand-edit = silently reverted. | — | Defends the artifact itself, not just a hidden button. |

### Anti-Features (deliberately excluded — and the v2.1 surfaces must not reintroduce them)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Accounts / login / cloud sync** | Multi-device + monetization | Attack surface + remote off-switch; impulse-self could loosen from another device. | Local-only, root-bound to this machine/user. |
| **Streaks / XP / gamified rewards** | Most-copied retention mechanic | "Most copied and most abused." Serves engagement (a business metric) Nightguard doesn't have; creates incentive to game the budget. | Let the *boundary holding* be the reward. |
| **Social / accountability partner** | External observation aids adherence | Out of scope (single-operator); adds a person + integration. | The guard *is* the impartial referee. |
| **Financial stakes / anti-charity** | Strong binding lever | Out of category; payments + disproportionate consequences. | Token scarcity is the stake. |
| **Configurable everything (general settings editor)** | "While I'm in there…" | Every editable field = a new classifier case + bypass vector. | Edits *only* the curfew config. |
| **In-app "disable everything" master override** | "What if I really need to turn it all off?" | This *is* the escape hatch the category warns about. | No master off. Disabling curfew is a *loosening* edit → costs a token. |
| **Notifications / nagging reminders** | Stay top-of-mind | Breeds resentment + bypass; tool should be invisible until summoned. | Status lives in the app when opened + the hook's block message at the friction moment. |
| **Multiple difficulty profiles / quick presets ("weekend mode")** | Fast rule-set swap | A fast path to a looser ruleset dodges per-field cost accounting → new escape hatch. | Per-field edits through the classifier. |

---

## Q&A synthesis (condensed)

- **Q1 — Trust:** enforcement must outlive the app; defend the artifact not a UI state; silent correction beats argument; honesty about limits builds *more* trust; one-door principle. *Roadmap implication:* status must truthfully reflect guard reality — any drift kills trust permanently.
- **Q2 — Grace without becoming the default:** hard cap (1/day, stricter than peers) + auto-expiry (the standout) + a deliberate confirm stating the consequence + optional short pre-delay (One Sec PNAS pattern, ~36% dismiss). **Never make grace extendable** — chaining = full unlock.
- **Q3 — Status/countdown/allowances:** countdown reframes "trapped" → "almost there"; show remaining as discrete depletable dots; always pair "spent" with "refills Mon"; two visually distinct meters; status reflects *true* enforced reality; no background notifications.
- **Q4 — Asymmetry:** Beeminder is canonical. Tightening conspicuously free+instant+no-confirm; loosening shows its price *before* commit and disables at 0 with "available again Monday" framing (a wait, not a denial). Per-field classification is the edge *and* the highest-risk correctness surface.
- **Q5 — Anti-features:** anything adding a remote, a person, an account, a reward loop, or a fast-path preset is a new escape hatch or attack surface. Keep the surface tiny: one config, one door, two limits, one quiet status screen.

---

## Feature Dependencies (core mechanics)

```
HMAC signing key (now root-owned file, v2.0)
    └──required by──> Signed config + signed guard.json state
                          └──required by──> Auto-revert integrity guard (root watchdog)
                          └──required by──> Direction classifier commit (re-sign on write)
                                                └──required by──> Token budget enforcement
                                                └──required by──> Daily grace enforcement

NTP true-time
    └──required by──> Grace window boxing · Curfew lock timing · Weekly reset anchor

Status/countdown UI ──reflects──> Guard-enforced reality (NOT app state)   [trust-critical edge]
Direction classifier ──gates──> Token spend ──displayed by──> 3-dot meter
Grace ──displayed by──> separate badge   [must NOT share the token pool visually]
```

### Dependency Notes

- **Everything binds on the shared HMAC key** (v2.0: root-owned file, single Python stack — no more two-stack byte-parity). The earliest, linchpin concern.
- **NTP underpins all three time-based features** — build once, fail-closed when unreachable.
- **Status UI depends on reading the *guard-enforced* truth, not app-local state** — trust-critical edge.
- **Grace and tokens are independent** by design — different cadence, different pool; don't couple them.

---

## MVP Definition (core — shipped across v1.0/v2.0)

### Launch With (v1) — the core guarantee
- [x] Shared HMAC key verifiable by app + guard (v1.0 DPAPI; v2.0 root file).
- [x] Auto-revert integrity guard (hand-edit → silent revert).
- [x] Direction classifier + one-token-per-loosening-commit.
- [x] Weekly 3-token budget, Monday 00:00 reset.
- [x] Once-daily 8-min NTP-boxed grace with auto-re-lock.
- [x] Status hero + countdown; 3-dot meter; separate grace badge.
- [x] Edit panel: live per-field tighten(free)/loosen(costs token) feedback; commit disabled at 0.
- [x] Fail-closed on invalid state HMAC.
- [x] One honest-limits statement.

### Add After Validation (v1.x)
- [ ] One Sec-style brief pre-delay + deliberate confirm on grace activation.
- [ ] Escalating-friction explanation on repeat grace attempts.
- [ ] Beeminder-style "available again Monday" framing on disabled-commit (partially in 10-UI-SPEC).
- [ ] Compact weekly ledger view (now present in the TUI StatusScreen).

### Future Consideration (v2+)
- [ ] Read-only schedule visualization on the main screen.
- [ ] (Explicitly NOT planned: accounts, sync, social, streaks, financial stakes, master-off, presets.)

---

## Feature Prioritization Matrix (core)

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Shared HMAC / root key | HIGH | MEDIUM | P1 |
| Auto-revert integrity guard | HIGH | MEDIUM | P1 |
| Direction classifier + 1-token rule | HIGH | MEDIUM-HIGH | P1 |
| Weekly token budget + Monday reset | HIGH | LOW-MEDIUM | P1 |
| NTP-boxed daily grace + auto-re-lock | HIGH | MEDIUM | P1 |
| Status hero + countdown | HIGH | LOW | P1 |
| 3-dot token meter + refill date | HIGH | LOW | P1 |
| Live per-field tighten/loosen feedback | MEDIUM-HIGH | LOW | P1 |
| Fail-closed on bad state HMAC | HIGH | LOW | P1 |
| Honest-limits statement | MEDIUM | LOW | P1 |
| Grace pre-delay + deliberate confirm | MEDIUM | LOW | P2 |
| "Available again Monday" reframing | MEDIUM | LOW | P2 |
| Weekly ledger view | LOW-MEDIUM | LOW | P3 |
| Read-only schedule on main screen | LOW | LOW | P3 |

---

## Competitor Feature Analysis (core)

| Feature | Cold Turkey / SelfControl | Freedom | Beeminder | One Sec / AppBlock / Locked | Nightguard |
|---------|---------------------------|---------|-----------|------------------------------|------------|
| Survives app close | Yes | **No** | N/A (server) | Varies | **Yes** — root guard |
| Clock-tamper resistance | Blocks Time settings | Limited | Server time | Limited | **NTP true-time** |
| Asymmetric tighten/loosen | No | No | **Yes (akrasia horizon)** | No | **Yes — per-field classifier + token** |
| Loosening limit | Timer / password | Locked session | Time-delayed | Emergency cap | **3 tokens/week** |
| Emergency / grace | None | None | N/A | 3 total / 3+1mo / questions | **1/day, 8-min, NTP-boxed, auto-re-lock** |
| Status/countdown | Yes | Yes | Goal graph | Minimal | **Hero countdown + dual meters** |
| Gamification | None | None | Optional money pledges | Some | **None (deliberate)** |
| Account/cloud | Local | Cloud | Cloud | Cloud | **Local-only, root-bound** |

---

## Sources (core)

- Cold Turkey Blocker user guide: https://getcoldturkey.com/support/user-guide/ (HIGH)
- SelfControl clock-change bypass (issue #28): https://github.com/SelfControlApp/selfcontrol/issues/28 (HIGH)
- Freedom Locked Mode (quit-kills-block limitation): https://support.freedom.to/en/articles/1802927-locked-mode (HIGH)
- Beeminder akrasia horizon / commitment dial: https://help.beeminder.com/article/45-what-is-the-akrasia-horizon ; https://blog.beeminder.com/dial/ (HIGH)
- One Sec PNAS study (delay-as-intervention): https://www.pnas.org/doi/10.1073/pnas.2213114120 (HIGH)
- AppBlock Strict Mode emergency flow: https://appblock.app/blocked-by-strict-mode-extension/ (MEDIUM-HIGH)
- Locked / Bloom emergency-exit caps: https://nowlocked.com/products/locked-tag (MEDIUM)
- Forest gamification critique: https://goodux.appcues.com/blog/forests-gamified-focus (MEDIUM)
- Scarcity UX / commitment-device principles: https://www.habitweekly.com/commitment-device-database (MEDIUM)

---
*Part A (desktop integration) researched 2026-06-24 · Part B (core mechanics) researched 2026-06-04*
</content>
