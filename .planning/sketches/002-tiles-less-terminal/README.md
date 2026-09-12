---
sketch: 002
name: tiles-less-terminal
question: "The tile grid is the right shape — what exactly makes it still read as a terminal, and which lever removes it?"
winner: null
tags: [layout, tui, textual, omarchy-quattro, blocking, refinement]
---

# Sketch 002: the tile grid, less terminal

## Design Question

The tile grid (sketch 001, variant E) is the chosen shape. It still reads as a
terminal. **Why**, and which single change fixes it?

Three candidate answers, one per variant, each testable by eye:

| Variant | Hypothesis | One thing it changes |
|---|---|---|
| E1 · No boxes | it is the **drawn rectangles** | outlines → one keyline grid, lines only between cells |
| E2 · Air | it is the **density** | half the facts, double the margins, no large figures at all |
| E3 · Solid chrome | it is that the chrome is **drawn rather than filled** | filled title bars + a solid accent spine |

The original E is kept as a fourth tab so the comparison is side by side rather
than from memory.

## What the investigation turned up

The previous mockups were reaching for glyph art that Textual 8.2.7 does not need.
Checked against the installed package, not from memory:

| Wanted | Actually available | Where |
|---|---|---|
| large countdown figures | **`Digits`** widget — thin box strokes `╭─╮╶─┐`, and a bold set `┏━┓╺━┓` | `textual/renderables/digits.py` (`DIGITS3X3`, `DIGITS3X3_BOLD`) |
| a real hairline, no box | **`border: hkey`** → `▔` / `▁`, one eighth of a cell (~1.5px), top and bottom only | `textual/_border.py` |
| a thin vertical rule | **`border: vkey`** → `▏` / `▕`, one eighth of a cell wide | same |
| a solid accent spine | **`border-left: tall`** → `▊` | same |
| a filled title bar | **`border: panel`** → `▊█▎`, solid top edge | same |
| lines between grid cells only | **`keyline: thin \| heavy \| double`** | `textual/css/constants.py` |
| a meter with no glyph texture | **`background: $accent`** on a fixed-width `Static`; alpha via `$foreground 18%` | Textual supports colour alpha in CSS |
| per-edge chrome | `border-left` / `border-top` are real properties | `textual/css/styles.py` |
| others in reach | `hatch`, `background-tint`, `text-opacity`, `border-title`, `Rule`, `Sparkline`, `ProgressBar` | — |

So the diagnosis: "too terminal" was **boxes** plus **glyph texture**
(`█▀▀█` figures, `●○○` pips, a `█▒─` band), and both have a native alternative.
Every meter and band in E1/E2/E3 is a **solid background fill over whole cells** —
which is why they stop looking like ASCII art and start looking like a surface.

The half-block figures of sketch 001 were, in hindsight, a worse reinvention of
`Digits` — heavier and more terminal-looking than the built-in.

## How to View

```
xdg-open .planning/sketches/002-tiles-less-terminal/index.html
```

Bottom-left cycles **locked / open / grace / clock tamper / weak mode**.
Bottom-right overlays the 135 × 46 character grid.

## Variants

- **E1: No boxes** — the six regions keep their positions and lose their outlines.
  One grid, `keyline: thin`, so a line exists only *between* cells. Thin `Digits`
  for the countdown. Tokens are three filled blocks; the day is a continuous filled
  band. Nearest thing in the taste library is Geist's hairline cell grid.
- **E2: Air** — same regions, half the content, four regions instead of six, two
  rows of padding, no rules inside anything, and **no large figures at all** — the
  countdown is bold text with wide tracking and space around it. This is the
  minimalist-editorial thesis tested honestly: if it reads here, the figures were
  never needed.
- **E3: Solid chrome** — every region gets a filled title bar the way a GUI window
  has one, and the state region carries a solid accent spine instead of a full
  outline. Bold `Digits`. Most ink, furthest from a terminal, busiest.
- **E (reference)** — sketch 001's version, unchanged.

## What to Look For

1. **Which one stops looking like a terminal?** That is the whole question. If two
   do, the cheaper one wins.
2. **Does E2 survive without the big figures?** If bold text plus space is enough,
   the countdown never needs a custom widget — and `grace` (where the seconds tick)
   is the state that will break the tie.
3. **E3's filled headers** — software, or decoration? A filled bar per region is
   six saturated strips on one screen; the anti-slop rule about one accent with one
   job is the thing at risk.
4. **The grid lines in E1 cost a whole cell.** Check they read as structure and not
   as leftover box.
5. **`weak mode` in all four.** When the jail cannot be built, enforcement really is
   weaker; each variant marks it differently (alarm dot, alarm-tinted header, a word).
6. Compare each against the bar panel open next to it. Same product?

## Content

Identical live data to sketch 001 — curfew `21:30–05:30`, may-weaken window
`05:30–14:00`, 1 token of 3, `grace: null`, the real ledger dates and truncated
HMACs, apps on in `blocklist` mode with `[steam, discord]`, games off with three
titles installed, zero sites blocked, `tick: ok`, policy restored 21:28.

Blocking keeps a full region in every variant, and keeps naming the two holes
(`discord` matches nothing; three installed games covered by nothing) rather than
showing a list that reads like protection.

## Still open

Whether the four unreachable blocking keys (the site list, blocklist ↔ allowlist
mode, game blocking, the allowlist) become **editable** as part of this work, or
stay read-only here and get their own phase. Read-only is what these mockups show.
