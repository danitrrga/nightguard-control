# Deferred items — phase 12.1

Out-of-scope discoveries. Logged, not fixed (executor scope boundary: only issues
directly caused by the current task's changes are auto-fixed).

---

## ~~Control 2 is flaky~~ — RESOLVED in plan 12.1-07

`test_token_pipeline.py::test_controls_fill_alpha_reaches_the_row`

**Closed 2026-09-13** by plan 12.1-07 (authorized scope item A). 30/30 consecutive
passes after the fix, against 17/20 before it. Two corrections to the diagnosis below,
both measured — see `12.1-07-SUMMARY.md`:

1. **It was the CURSOR read, not the idle one.** Every captured failure was on
   `rows[0]` (0.42 -> 0.08, the rung the focused row fades TO), not on
   `rows[1].styles.background`. `rows[1]` is idle and is never animated.
2. **Textual's own wait helpers do not fix it.** `Animator.start()` sets both
   `_idle_event` and `_complete_event` unconditionally and runs AFTER the first
   `_animate`, so `pilot.wait_for_animation()` and
   `pilot.wait_for_scheduled_animations()` both return immediately for the first
   animation of an app's life. Measured 23/30 with `wait_for_scheduled_animations`.

The record below is kept verbatim as it was written.

---

### Original entry

**Found during:** plan 12.1-06, Task 3, on the post-task full-suite run.
**Owner:** plan 12.1-04 (the test is `tests/test_token_pipeline.py:203`).

**Measured.** Run in isolation, repeatedly:

```
$ for i in $(seq 10); do uv run --with pytest --with pytest-asyncio pytest -q tests/test_token_pipeline.py; done
3 passed / 3 passed / 1 failed / 1 failed / 3 passed
3 passed / 1 failed / 3 passed / 3 passed / 1 failed
```

**4 failures in 10 runs, with plan 06's two files removed from the tree entirely**
(`ngtui/widgets/hero.py` and `tests/test_dashboard_hero.py` moved out, then restored) —
so it is not caused by this plan and nothing in this plan is reachable from it.

**Cause (near-certain, and already recorded in this phase).** The assertion is

```python
idle = rows[1].styles.background
assert round(idle.a, 4) == 0.42
```

and `styles.background` is the **animated** value — plan 12.1-05's Issues Encountered
recorded reading 0.2037 for a rung whose settled alpha is 0.08, an intermediate frame of
the stylesheet's 120 ms fill cross-fade. `pilot.pause()` waits for the message queue, not
for the animator. Plan 04's control predates that finding, so it reads the rung without
settling past the transition; plan 05's ladder test derives a settle from `PRESS_FLASH`
for exactly this reason.

**Why it matters beyond one red.** Every plan in this phase carries "full suite: no new
red" as an acceptance criterion. A control that fails ~40 % of the time makes that
criterion unenforceable for plans 07, 08 and 09 — a spurious red is indistinguishable
from a real one at the moment it appears.

**Fix, when someone owns it:** settle past the fill transition before sampling, derived
from the transition's own duration rather than typed (plan 05's shape). Do **not** weaken
the 0.42 assertion — that value is the whole point of the fixture's
`normal-fill-alpha = 0.42`.

---

## The editor has no on-screen legend now — plan 12.1-08, Task 1

**Found during:** 12.1-08 Task 1, removing the framework chrome from `edit.py`.
**Owner:** phase 12.2 (it owns the edit flow) or a follow-up to 12.1.

The home surface traded the `Footer`'s key legend for the `help` chip plus an
`escape` that closes the panel. `EditScreen` has no chip strip, so after this plan
its seven bindings — `j` `k` `enter` `space` `c` (commit) `u` (discard) `escape`
(back) — have **no affordance on screen at all**. `c` and `u` are the consequential
ones and they are now undiscoverable.

**Measured:** `textual 8.2.7` binds nothing to `f1` by default. `App.BINDINGS` is
`ctrl+q` and `ctrl+c` only; `Screen.BINDINGS` is `tab`, `shift+tab` and
`ctrl+c,super+c`. So there is no free fallback — the legend is simply gone.

**Not fixed here, deliberately.** Plan 12.1-08 fences `edit.py` to "three `yield`
lines and one import" (T-12.1-31), and the obvious fix collides with the editor's
own semantics: `escape` is already this screen's *cancel*, so a help panel that
`escape` both closes and escapes out of is a rework of the edit flow. That is
12.2's subject, not this phase's.

**When someone owns it:** the shape that works on the home surface is a `help`
control plus `action_close_help`, with the panel's close bound to a key that is not
already cancel — or a one-line hint row inside the editor, which costs a row of the
edit screen's own budget and does not have the escape collision.

---

## The degradation classes cannot see a `split` panel — plan 12.1-08, Task 2

**Found during:** 12.1-08 Task 2, writing control 9's help-panel-open assertion.
**Owner:** unassigned. Below the sanctioned window; the shipped window is unaffected.

`StatusScreen.on_resize` keys on the **screen's** size. Mounting Textual's
`HelpPanel` does not resize the screen — `split: right` re-lays out inside it — so
the degradation triggers never see the ~45 columns the panel takes.

**Measured**, frame width with the help panel open:

```
terminal 135 -> frame 91 cols   (above the 80-col -narrow threshold: fine)
terminal 120 -> frame 81
terminal 110 -> frame 74        \
terminal 100 -> frame 67         |  below 80, and `-narrow` does not fire:
terminal  90 -> frame 60         |  #frame wears no class at any of these
terminal  80 -> frame 50        /
```

At the sanctioned 135 × 46 the panel leaves 91 columns, comfortably above the
threshold, so **nothing the windowrule pins is affected**. Below about 120 columns
the band stays side-by-side while its fixed 62-column left half no longer leaves
room for the right one, and `overflow-x: hidden` clips `THIS WEEK` rather than
stacking it. Vertically the frame still fits at every width measured
(`virtual == container == 44`, `max_scroll_y == 0`), so nothing scrolls or hides a
ledger row — this is a narrow-terminal cosmetic loss while a transient panel is
open.

**A second, separate observation from the same measurement:** below roughly 120
columns Textual's own `HelpPanel` places a `Static` at row **47**, one past the
window. That is a third-party widget we mount but do not lay out, which is why
control 9's widget-bottom scan is scoped to `#frame` and its descendants.

**When someone owns it:** the trigger has to move from the screen's size to the
frame's own, i.e. a resize seam on `#frame` rather than on the screen. That is a new
widget subclass or a `Resize` handler on the container, and it changes what the
"< 80 columns" in UI-SPEC §7.4 is measured against — so the contract's table needs
updating with it, not just the code.
