# Sketch Manifest

## Design Direction

The terminal UI should read as the same product as the finished quickshell bar
panel, without copying its patterns — and it should read as a **normal modern
tool**, not as terminal art. The reference is what DHH is actually building in
Omarchy 4 ("Quattro"): typography and space before chrome, one idea per screen,
nothing decorative that does not inform. Concretely that means the live Quattro
shell kit (`PanelHero`, `PanelSectionHeader`, `PanelSeparator`, the `Style` state
tokens) translated to a character grid, not traced from it.

Two things the screen must do that the current one does not: let you **see the
cycle** — where you are in the day, how much is left, what a change costs — and
give **blocking** a real surface. Blocking is the half of the product that ends
applications, and it has no interface at all today.

Hard constraints carried into every sketch:

- No fixed hex anywhere. Colour, spacing, type scale and corner radius come from
  the live desktop theme (`shell.toml` + `colors.toml` + `hyprctl
  decoration:rounding`). The Moonlit Indigo palette stays retired.
- 135 × 46 cells — the sanctioned floating window at the live terminal font.
- The trust path is not visual scope: the signer, the inline `sudo` under
  `App.suspend()`, the direction classifier, and the refusal to accept a weakening
  keystroke outside the window are untouched.

## Reference Points

- The project's own quickshell bar panel — finished, liked, not to be changed:
  `packaging/omarchy/plugins/danitrrga.nightguard/{BarWidget,NightguardPanel}.qml`
- The live Quattro shell kit, read for its vocabulary:
  `/usr/share/omarchy/shell/Ui/` + `/usr/share/omarchy/shell/Commons/Style.qml`
- The live theme (dos-moos, "Muted Sage"):
  `~/.local/state/omarchy/current/theme/{colors,shell}.toml`
- Daniel's taste library (`forge/design/taste/`) — web and desktop, so it informs
  rather than decides. It holds three families, not five: `minimalist-ui`
  (space and type do the grouping, no card chrome), `industrial-brutalist-ui`
  (drawn grid, exactly one alarm colour under ~5% coverage, extreme type contrast),
  and `high-end-visual-design` — whose own file rules it out here ("fails for
  dashboards, settings, any screen someone opens forty times a day").
  The anti-slop catalogue applies throughout, notably: no card containers around
  things that are not cards, one accent with one job, no emoji as icons, real
  content rather than placeholders.

## Sketches

| # | Name | Design Question | Winner | Tags |
|---|------|----------------|--------|------|
| 001 | tui-direction | What shape lets you see the cycle rather than read it off a list, and where does blocking live on it? | **E · tile grid** — chosen, with "less terminal" as the note | layout, tui, textual, omarchy-quattro, blocking |
| 002 | tiles-less-terminal | The tile grid is right — what exactly makes it still read as a terminal, and which lever removes it? | — | layout, tui, textual, omarchy-quattro, blocking, refinement |

## What the stack can actually draw

Checked against the installed `textual 8.2.7`, not from memory — this is the
material the design contract gets to spend:

- **`Digits`** — large figures in thin box strokes (`╭─╮`) or bold (`┏━┓`). Replaces
  the hand-rolled half-block figures, which were heavier and more terminal-looking
  than the built-in.
- **`border: hkey`** (`▔`/`▁`) and **`border: vkey`** (`▏`/`▕`) — one eighth of a
  cell, so a genuine hairline, with no box around it.
- **`border-left: tall`** (`▊`) — a solid accent spine. **`border: panel`** (`▊█▎`) —
  a filled title bar. **`border: blank`** — space that draws nothing.
- **`keyline: thin | heavy | double`** — lines between grid children only.
- **`background: $accent`** on a fixed-width widget, and colour alpha
  (`$foreground 18%`) — which is how a meter or a band becomes a *surface* instead
  of a run of `█` glyphs. This is the single biggest lever away from "terminal".
- Also in reach and unused so far: `hatch`, `background-tint`, `text-opacity`,
  `border-title`, `Rule`, `Sparkline`, `ProgressBar`.

## The functional gap these sketches sit on top of

Blocking is deployed and load-bearing (root-owned cgroup jail, blocklist and
allowlist modes, game auto-detection, a managed browser policy the watchdog restores
every tick). The signer classifies eight blocking config keys
(`scripts/linux/nightguard_ctl.py:44-66`); the only sanctioned editor exposes four
(`ngtui/ngtui/widgets/edit.py:216`).

Unreachable today, and therefore frozen — a hand edit to `config.yaml` gets reverted
by the watchdog: the **site list** (empty, so no site is blocked), the
**blocklist ↔ allowlist mode** (implemented and tested), **game blocking** (off,
with three titles installed), and the **allowlist**. Separately, `discord` has sat in
the native blacklist since June and matches nothing — it is a chromium webapp sharing
one process with the calendar, the todo list and the portal.

Every sketch shows that state honestly. Whether those keys also become *editable* is
an open scope decision, not a visual one.
