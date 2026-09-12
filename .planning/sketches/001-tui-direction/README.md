---
sketch: 001
name: tui-direction
question: "What shape should the ngtui home screen be, once it reads like an Omarchy 4 tool rather than a config file with a cursor — and where does blocking live in it?"
winner: "E"
tags: [layout, tui, textual, omarchy-quattro, blocking]
---

# Sketch 001: ngtui direction

> **Winner: E · Tile grid** — chosen 2026-09-12, with the note "me gusta mucho pero
> sin ser tan terminal". Refined in [sketch 002](../002-tiles-less-terminal/).

## Design Question

The TUI's home screen today is a vertical list of key/value rows and two bordered
panels. It shows the curfew verdict, a countdown, the token meter, grace, two
truncated HMACs and the ledger. It does **not** show anything about what the
curfew actually blocks, and it has no picture of the day at all.

Two questions, answered together because they are the same question:

1. What shape does a screen have that lets you *see the cycle* — where you are in
   the day, how long is left, and what a change would cost — instead of reading it
   off a list?
2. Where does **blocking** live on that screen? It is the half of the product with
   no interface, and it is the half that actually ends applications.

## Direction it is built in

Not "a terminal UI". The reference is the live Omarchy 4 ("Quattro") shell kit
itself, read out of `/usr/share/omarchy/shell/` — `PanelHero`,
`PanelSectionHeader`, `PanelSeparator`, the `Style` state tokens — translated to a
character grid rather than traced.

The translation that matters: Quattro's type scale (`caption 10 / body 12 /
title 14 / heading 16 / display 24`) cannot survive on a grid with one cell size.
It becomes **weight + case + dim + glyph mass**:

| Quattro | On the grid |
|---|---|
| `display` | 3-row half-block figures for the countdown |
| `title`, `heading` | bold |
| `caption` (`PanelHero.meta`: uppercase, letterSpacing 1.2, dim) | uppercase, letter-spaced, dim — verbatim |
| `normalFillFor` (foreground @ 4%) | `background: $foreground 4%` — Textual does alpha, so this is literal |
| `PanelSeparator` (foreground @ 12%) | a rule at 12% |
| `cornerRadius` = `hyprctl decoration:rounding` | `border: round` vs `border: solid` |

## Measured constraints these are drawn to

- **135 × 46 cells.** The sanctioned window is `size 875 600`
  (`packaging/omarchy/hypr/nightguard.windowrule.conf:8`) and the terminal font is
  CaskaydiaCove Nerd Font at 8pt → a 6.25 × 12.40 px cell. Every variant is laid
  out in `ch` and `lh` so a row that does not fit here does not fit there either.
- **Square corners.** `hyprctl getoption decoration:rounding` is `0` on this box,
  so every Quattro surface on screen is square — while `app.tcss` draws
  `border: round` everywhere. The mockups are square.
- **Nerd Font glyphs are available** (`omarchy font current` → CaskaydiaCove Nerd
  Font), so icons are fair game and do not need to be emoji.

## How to View

```
xdg-open .planning/sketches/001-tui-direction/index.html
```

Bottom-left cycles the five states the screen has to survive: **locked / open /
grace / clock tamper / weak mode**. Bottom-right switches theme and overlays the
character grid so you can check nothing is off-cell.

## Variants

- **A: Panel stack** — the bar panel grown into a window. Hero, section header,
  separator, rows, repeat. Nothing invented: if the shell has a component for it,
  this uses it. Cheapest to build, strongest coherence claim. *Risk: a list of rows
  is still not "seeing the cycle".*
- **B: Cycle dial** — the day as a 24-hour ring drawn on the grid, curfew as an arc
  with a visible end, now as a marker travelling it. Tokens and blocking ring it as
  satellites. *Risk: one big ornament that has to keep earning 21 rows.*
- **C: Two-column console** — the only variant that uses all 135 columns. Left is
  the pact (verdict, cycle, cost); right is enforcement (what is blocked right now,
  and what is not). *Risk: two columns is two ideas per screen.*
- **D: Day band** — the 24 hours flat across the window: curfew shaded, the
  may-weaken window marked, now a bright cursor on the line. The only shape that
  puts the curfew and the edit window in one picture. Stats hang underneath in
  three groups.
- **E: Tile grid** — Quattro control surfaces as tiles (4% fill, 30% border —
  what every button and field in the shell is made of). Verdict and blocking get
  the big tiles. *Risk: the slop catalogue's "card containers around things that
  are not cards" — a tile has to mean an object.*

## What to Look For

1. **Can you tell where you are in the day without reading a number?** That is the
   difference between A/E and B/C/D.
2. **Does blocking read as load-bearing or as a footnote?** Each variant gives it a
   different weight: a section (A), satellites (B), a whole column (C), one of three
   stat groups (D), a big tile (E).
3. **Does the countdown need the half-block figures at all,** or is bold enough?
   Toggle to `grace` — the countdown becomes seconds-live, and mass helps there more
   than in `locked`.
4. **Square corners against the rest of your desktop.** Every border here is square
   because Hyprland's rounding is 0. Compare against the bar panel next to it.
5. **`weak mode`.** When the jail cgroup cannot be built the enforcement is
   genuinely weaker. Check that each variant makes that *look* different rather than
   just saying it in a word.

## Content is real, not placeholder

Everything on screen is read off the live stack on this box (2026-09-12):

- curfew `21:30–05:30`, may-weaken window `05:30–14:00`, `Europe/Amsterdam`
  (`/var/lib/nightguard/config.yaml`)
- `weekly_spent: 2` → 1 token of 3; `grace: null`; 8 ledger entries with their real
  dates; the real truncated HMACs (`/var/lib/nightguard/guard.json`)
- blocking: apps on, `blocklist`, `[steam, discord]`; `block_games: false`;
  `blocked_urls: []`
- the three installed titles the game catalogue would find: Counter-Strike 2,
  Yu-Gi-Oh! Master Duel, Rocket League
- `tick: ok` every ~60s, and the browser-policy restore at 21:28
  (`/var/lib/nightguard/watchdog.log`)

## The finding these mockups are built around

Blocking is deployed and load-bearing — a root-owned cgroup jail, blocklist and
allowlist modes, game auto-detection, a managed browser policy the watchdog
restores every tick. The signer classifies every one of its config keys
(`scripts/linux/nightguard_ctl.py:44-66`).

The only sanctioned editor exposes four of them and not the other four
(`ngtui/ngtui/widgets/edit.py:216`). Missing: the site list, the
blocklist/allowlist mode, game blocking, and the allowlist. Since a hand edit to
`config.yaml` gets reverted by the watchdog, **those four are currently
unreachable** — which is why no site is blocked and why three installed games are
covered by nothing.

The mockups surface that state honestly instead of showing a list that reads like
protection. Whether the fields also become *editable* is a separate decision and a
scope question, not a visual one.
