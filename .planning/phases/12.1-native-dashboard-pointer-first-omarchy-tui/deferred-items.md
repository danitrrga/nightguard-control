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
