---
sketch: 004
name: native-dashboard
question: "If this is a generation change, the interaction has to change too — what does a pointer-first, Omarchy-native mini dashboard look like, and how do the four frozen keys become controls?"
winner: null
tags: [interaction, pointer, tui, textual, omarchy-quattro, blocking, editing, tokens]
---

# Sketch 004: native dashboard

## Design Question

The previous rounds settled how it *looks*. The note was that it still reads like the
old Nightguard — because the aesthetic changed and **the way you interact with it did
not**. It was still a keyboard-only screen with bracket hints.

So: what does a pointer-first Omarchy-native mini dashboard behave like, and what
happens to the four config keys that are classified by the signer but absent from the
only sanctioned editor?

This sketch is **live**. Hover the rows, click them, then move the same highlight with
`j`/`k` or the arrows without touching the mouse. `Enter`/`Space` activate. `Escape`
goes back.

## What was read, not assumed

Omarchy 4's own panels, in `/usr/share/omarchy/shell/`:
`plugins/panels/{monitor,audio,network,bluetooth,clock,power,weather,…}/Panel.qml`
and the kit in `Ui/{Button,Toggle,ToggleSwitch,PanelSlider,ButtonGroup,PanelHero,
ConfirmDialog}.qml`.

The behavioural contract those files establish, and where each part landed here:

| Omarchy's pattern | Evidence | Here |
|---|---|---|
| **One cursor shared by keyboard and mouse.** `hot = containsMouse \|\| hasCursor`, and each control emits `hovered(bool)` so the panel moves its *keyboard* cursor on mouse-enter — the two can never disagree | `Ui/Button.qml`, and `panels/monitor/Panel.qml`'s "Cursor model shared by keyboard and mouse" | every row goes through one `ctl()`; `mouseenter` moves the cursor, `j`/`k` moves the same one |
| Paint priority: pressed > focus > hover/cursor > selected > active > idle, each with its own fill and border alpha from `[controls]` | `Ui/Button.qml` `color:` and `borderSpec:` ladders | the same ladder, same alphas (0.04 / 0.10 / 0.18 / 0.10) |
| **The whole row is the click target**; the switch is presentation only and holds no state | `Ui/Toggle.qml` — "the row owns the click, so the switch is presentation only here" | clicking anywhere on a row stages it |
| **Reserve the largest border any state can paint**, so hover never relayouts a neighbour | `Ui/Button.qml` `_reservedBorder*` | border width is constant across states; only its colour changes |
| Right-click is a secondary action on the same target | `Ui/PanelSlider.qml` `rightClicked()` | wired on `ctl()`, unused so far — noted rather than invented |
| Colour transition 100–120 ms; tooltip delay 400 ms | `ColorAnimation { duration: 120 }`, `ToolTip { delay: 400 }` | identical |
| `Return` / `Enter` / `Space` activate; `Tab` focus | `Keys.on*Pressed` on every control | identical |
| Switch shape follows the theme: pill on rounded, **square on sharp** | `Ui/Toggle.qml` `rounded: Style.cornerRadius > 0` | square, because `hyprctl decoration:rounding` is 0 here |
| A panel is a list of named **sections**, and the cursor model knows which are visible and whether each is one row or a list | `panels/monitor/Panel.qml` `visibleSections` / `sectionIsSingleRow` | sections with a flat cursor order rebuilt per paint |
| Optimistic preview that does not snap back during the round trip | `panels/monitor/Panel.qml` `pendingBrightnessPercent` | staged values render immediately; the live value is what it is compared against |

All of it translates to Textual 8.2.7, verified against the installed package rather
than from memory: `transition` in CSS, `Widget.tooltip`, `Enter`/`Leave` events,
`Click.button` for right-click and `Click.chain` for double, mouse scroll, and the
widgets `Switch`, `Checkbox`, `Select`, `SelectionList`, `OptionList`, `Collapsible`,
`Input`, `Toast`, `DataTable`, `Digits`, `Rule`.

**The one thing that does not translate**: `cursorShape: Qt.PointingHandCursor`. A
terminal cannot change the pointer shape, so the hover fill has to carry the whole
affordance. That is the Linux/terminal ceiling on this, and it is the reason the hover
fill here is the theme's `hover-cursor` alpha rather than something subtler.

## The four frozen keys are now controls

The site list, the blocklist/allowlist mode, game blocking and the allowlist were
classified by the signer (`scripts/linux/nightguard_ctl.py:44-66`) and missing from the
editor (`ngtui/ngtui/widgets/edit.py:216`), so they could not be changed at all — a hand
edit to `config.yaml` is reverted by the watchdog.

Here they are: a switch row for each boolean, a segmented control for the mode, and a
list editor for each of the three lists. The list editor is a click-to-strike list plus
an add field, and every pending change carries its own direction and cost.

### What stops it being a config file with a cursor

The app knows things the config does not, and offers them:

- `discord` has sat in the app blocklist since June and **matches nothing** — it is a
  chromium webapp sharing one process with the calendar, the todo list and the portal.
  The row says so, and the site list offers `discord.com` as a suggestion, because that
  is the layer that can actually reach it.
- **Game blocking is not a bare boolean.** Its tooltip names the three titles the
  catalogue actually found on this machine (Counter-Strike 2 via `appmanifest_730`,
  Yu-Gi-Oh! Master Duel via `appmanifest_1449850`, Rocket League via Heroic) and says
  turning it on is a tightening, so free.
- The allowlist row explains the hardcoded floor — compositor, shell, portals, pipewire,
  keyring and **every terminal** — that config cannot shrink.
- Hovering any column of the day ramp reads out that hour and whether a loosening would
  be accepted there.
- Every refused control says **why**, on hover, before you touch it.

## The cost rule, and a consequence worth seeing

The rule set for this work: **one token per list touched, per commit.** Two lists in one
commit is two tokens. The clock window gates it, same as the curfew.

Implementing it uniformly produces this: adding `discord.com` to the site list is a
**tightening**, and under the uniform rule it still costs a token and is still refused
outside the window. So at 22:00, realising you should block a site, you cannot make the
pact stricter. That contradicts the rule the guard already applies everywhere else —
tightening is free and allowed at any hour.

Rather than silently pick one, the toolbar has a switch between the two:

| Rule | Behaviour | What it costs you |
|---|---|---|
| **every list edit** (as specified) | any list touched = 1 token, window required | you cannot tighten a list outside the window |
| **only loosenings** | 1 token + window only when the edit loosens (removing from a blocklist, adding to an allowlist); pure additions to a blocklist are free, any hour | a midnight "take steam off, put it back tomorrow" is two commits and only the first is charged — smaller loophole than it looks, but not zero |

Flip it in the toolbar and watch the staged tray and the refusal line change. This is the
one open decision in this sketch.

## How to View

```
xdg-open .planning/sketches/004-native-dashboard/index.html
```

Three views, and they navigate for real — the tabs and the in-screen chips both work.

- **Dashboard** — the day hero, state, the week, and blocking as eight control rows.
- **Editing a list** — the list editor, switchable between the three lists.
- **Staged & commit** — the tray, grouped into what costs a token and what is free,
  with the total against the week and the refusal stated before any authentication.

Bottom-left switches state. **`window open`** is the one where editing is permitted;
the rest show the screen read-only with the reason on every row. Bottom-right has the
cost-rule switch and the live row count against the 46 the window has.

## What to Look For

1. **Hover a row, then let go of the mouse and press `j`.** The highlight should continue
   from where the pointer left it, not jump to the top. That is the whole pattern.
2. **Nothing should shift when you hover.** If a row nudges its neighbour, the border
   reservation is wrong.
3. **`window open` versus the rest.** Read-only should look deliberate, not broken, and
   every row should say why on hover.
4. **Stage three things and go to the commit view.** Is the cost legible before you would
   ever reach a fingerprint prompt? That is the product's central rule.
5. **The cost-rule switch.** Stage only an addition to the site list, then flip it.
6. **Is this still the aesthetic from sketch 003?** Same frame, same greyscale ramp
   hero, same chips, same one accent dot, `Digits` unchanged. It should read as the same
   product with hands added, not as a new one.

## Untouched

The trust path. Nothing here changes the signer, the inline `sudo` under `App.suspend()`,
the direction classifier, or the refusal to accept a weakening keystroke outside the
window — the commit chip is *refused with its reason shown* rather than being allowed to
reach an authentication it would fail. The dashboard stages; only the signer commits.
