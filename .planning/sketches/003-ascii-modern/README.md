---
sketch: 003
name: ascii-modern
question: "E1 and E3 are both close — what does the ASCII-Magic reference actually change about them?"
winner: null
tags: [layout, tui, textual, industrial-brutalist-ui, ascii-magic, blocking, refinement]
---

# Sketch 003: ascii, modern

## Design Question

Sketch 002 left two candidates alive, E1 (keyline grid) and E3 (solid chrome),
with one note: **ascii style, but modern.** The named reference is the ASCII-Magic
entry in the taste library — `industrial-brutalist-ui` family,
`design/taste/entries/ascii-magic.md`, live site `ascii-magic.com/landing`.

So the question is not "which of the two" again. It is: what does that reference
concretely change about both of them?

## What was taken from the reference, mechanism by mechanism

Read from the entry's vocabulary and its screenshot, not from the mood.

| In the reference | Here |
|---|---|
| Square outline chips in one row, radius 0, **the selected one inverted to a bright border** — a control strip, not a nav | the action strip at the bottom; `▏label▕` in dim, with exactly **one filled** (the reference's white button) |
| **Hairline rules bracketing the viewport** left and right, framing the demo as a device | `▏` / `▕` columns down both sides plus `▔` / `▁` across — `border: vkey` / `hkey`, one eighth of a cell |
| Corner labels inside the frame ("Before", "After") — small, dim, no chrome | every section label: dim, uppercase, letter-spaced, **no heading bar and no box** |
| Near-black ground over ~80% of the area, **the whole colour budget on one subject** | ground is the theme background; the only coloured thing is the verdict word and its countdown |
| One warm accent, appearing **once**, as a dot | one accent dot beside the wordmark. Nothing else |
| Monospace display at 4× body; the headline **demonstrates the tool while stating it** | `Digits` for the countdown, and the day rendered as an ASCII ramp — the screen shows what the product does by doing it |
| A white filled primary button | one filled chip: `edit` |

Two guardrails from that family were being broken by sketches 001 and 002, and are
fixed here:

- **"Keep the accent under ~5% of pixels."** The day band was whole stretches of
  saturated red and yellow. It is now greyscale; accent coverage is a single dot
  plus one word, well under 1%.
- **"Never soften it halfway."** No radius anywhere (the compositor's rounding is 0
  regardless), no shadow, no filled header strips.

## The one thing that is genuinely ASCII art

The day is now a **density ramp** — ` .:-=+*#%@` — and it is the hero, full width:

```
@@@@@@@@@@@@@@@@@@@@@@@@@@@.........................:::::::::::::----------==========+++++*****#####%%%%%@█@@@@@@@@@@
                           ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
00       02        04        06        08        10        12       14        16        18        20        22
```

**Density is hours-until-curfew**, so the picture is information rather than
texture: saturated at `@` inside the curfew, dropping to `.` the moment it lifts at
05:30, then climbing back through `: - = + * # %` as the night returns — you can
feel 21:30 coming at 17:00 without reading a number. The thin `▔` underline is a
separate channel: the hours in which a loosening is even considered. One bright cell
is now.

Keeping it to one instrument is deliberate — the family's rule is "never stack two
hero materials", and the reference spends its entire colour budget on one subject
because of that. The ramp is greyscale for the same reason: density already carries
the meaning, so it does not need to spend colour it would then be competing with.

The third tab shows the ramp alone, at four widths and in all five states, so it can
be judged as an instrument rather than glimpsed as decoration.

## Everything else lost its glyph texture

Meters are **surfaces**, not characters: a fixed-width `Static` with a `background`
colour. `●○○` and `▬▬▬` are both gone. On/off is a reverse-video tag (`ON` / `OFF` /
`GAP`) rather than a coloured word, which is the reference's inverted-chip idea
applied inline.

## How to View

```
xdg-open .planning/sketches/003-ascii-modern/index.html
```

Bottom-left cycles **locked / open / grace / clock tamper / weak mode**.
Bottom-right shows a live **row count against the 46 the window has** — it turns red
on overflow, so the layout cannot quietly outgrow the real window. E1★ draws 43 of
46, E3★ draws 41.

## Variants

- **E1★ · keyline grid** — the no-boxes grid with the frame, the chip strip and the
  ramp as full-width hero. Two keyline-separated bands below it: state next to
  blocking, then the week next to the ledger.
- **E3★ · solid chrome** — same frame, same hero. The six filled title bars are
  gone; what carries "this is software" instead is a **solid spine** on the state
  region, an **inverted chip** for the one region that is shouting (weak mode moves
  into the header), and bold `Digits`. A fifth of the ink of the original E3.
- **the ramp, on its own** — the hero at 127 / 96 / 64 / 40 columns and in every
  state.

## What to Look For

1. **Does the ramp read as an instrument or as wallpaper?** If it is wallpaper the
   whole direction is wrong, and the third tab is where to decide that.
2. **Is the frame worth two columns and two rows?** It is the cheapest thing here
   and does the most for "this is an app, not a terminal" — or it is a gimmick.
3. **E1★ versus E3★ now that both have the same hero.** The difference has narrowed
   to how the state region is set off: a keyline, or a spine.
4. **The chip strip against `[e] edit`.** Chips are a control strip; bracket hints
   are a terminal convention.
5. **`grace`** — the one state where the countdown moves every second, and the only
   one that can justify `Digits` at all.
6. **`weak mode`** — in E3★ it takes over the header as an inverted chip; in E1★ it
   is a `GAP` tag in the blocking region. Which one would actually stop you.
7. **Against the bar panel.** Same product, or two products now?

## Unchanged

Live data throughout (curfew `21:30–05:30`, may-weaken window `05:30–14:00`, 1 token
of 3, real ledger dates and HMACs, apps on in `blocklist` with `[steam, discord]`,
games off with three titles installed, zero sites blocked). Blocking keeps a region
of its own and still names both holes.

## Still open

Whether the four unreachable blocking keys (the site list, blocklist ↔ allowlist
mode, game blocking, the allowlist) become editable in this work or in their own
phase. These mockups show them read-only.
