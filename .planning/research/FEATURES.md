# Feature Research

**Domain:** Self-binding / commitment-device / focus-lock tool (single-operator, local, Windows)
**Researched:** 2026-06-04
**Confidence:** MEDIUM-HIGH (Cold Turkey, Freedom, SelfControl, AppBlock, Beeminder, One Sec, Forest all corroborated by official docs + reviews; UX-trap claims cross-sourced. Domain is well-documented but most evidence is product docs/reviews rather than controlled studies, except One Sec which has a PNAS paper.)

> Scope note: the core mechanics (auto-revert, 3 tokens/week, +8 grace, HMAC/DPAPI) are **locked**. This file does not re-litigate them. It maps how the proven tools in this category implement the *surrounding* UX so the roadmap doesn't miss table-stakes or fall into known traps, and it pressure-tests the locked decisions against what the category has learned.

---

## The category's central lesson

Every durable tool in this space (Cold Turkey, SelfControl, Freedom Locked Mode, Beeminder, AppBlock Strict Mode) converges on one principle:

> **The friction must live somewhere the impulsive self cannot reach in the moment.** Trust comes from the user *knowing* they can't quietly undo it, not from a setting they could toggle.

The failure mode is universal too: the escape hatch becomes the default. Freedom's own docs admit Locked Mode is defeated by simply quitting the app; SelfControl's whole reputation rests on the block surviving quit/restart/uninstall. Nightguard's auto-revert-on-hook-fire is the *correct* architecture for this — enforcement lives in always-firing hooks, not the app (design-spec already states this). The research below mostly validates that choice and details the UX layer around it.

---

## Feature Landscape

### Table Stakes (Users Expect These — missing = the tool fails its purpose)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Enforcement survives the app being closed/killed** | The #1 trust differentiator in the category. Freedom is criticized precisely because quitting kills the block; SelfControl is praised because nothing short of waiting works. | — (already in spec) | Nightguard's hooks-not-app architecture is *exactly* the right call. Surface this to the user as a promise: "closing this app does not weaken anything." |
| **Tamper is detected AND silently corrected, not just logged** | Users of self-binding tools expect the system to win the fight, not narrate it. A log nobody reads is not enforcement. | — (already in spec) | Auto-revert-to-sanctioned is the strongest version of this. The silent revert ("the sneaky edit vanishes") is psychologically ideal — impulse-self gets no dialog to argue with. |
| **Clock-tampering cannot widen/end a lock early** | This is a *known, named bypass* across the category — SelfControl issue #28, Cold Turkey blocks the Time & Language settings panel for this exact reason. Users who've used other tools will test it. | — (NTP already in spec) | Nightguard's NTP-true-time boxing of both curfew and grace is table-stakes-correct. Cold Turkey's approach (block the settings panel) is the brute-force alternative; NTP-verification is cleaner and doesn't require admin fights. **Flag: must degrade gracefully when NTP unreachable** — spec's `block_when_offline` fail-closed is the right default. |
| **Clear current status: locked / open, and when it next changes** | Every tool shows this. Without "when does this end?" the user feels trapped rather than bound, which breeds bypass attempts. | LOW (in spec: status hero + countdown) | The countdown is the single most important calming element — see Q3 below. |
| **The block is *legible*: user can see exactly what is and isn't blocked, and the schedule** | Opaque blocks erode trust; users start suspecting the tool is broken and look for the off switch. | LOW | The edit panel doubles as the "what's enforced" view. Read-only schedule visibility on the main screen is worth considering. |
| **Honest about its own limits** | Sophisticated self-binders know admin = breakable. Tools that overpromise ("unbreakable!") lose trust when bypassed once. | — (spec already states this) | The spec's "friction past the impulse threshold, not a literal vault" framing is the mature, correct stance. Consider surfacing it in-app once (e.g., onboarding/about) so the user's rested-self sets correct expectations. |
| **A limited emergency/grace path that exists** | Tools *without* any grace get uninstalled in the first genuine emergency, taking the whole boundary with them. Locked, Bloom, AppBlock all ship emergency exits *on purpose*. | — (+8 grace in spec) | The presence of grace is itself table-stakes for retention. The *design* of it is the differentiator — see Q2. |

### Differentiators (where Nightguard competes / its identity)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Asymmetric cost: tightening free+instant, loosening rate-limited** | This is the category's gold-standard move (Beeminder's entire model) and Nightguard's core value. Most consumer blockers are symmetric on/off; the asymmetry is what makes a *pact* bind. | MEDIUM (direction classifier, in spec) | See Q4. Beeminder validates this is the right mechanic. Nightguard's per-field tighten/loosen classifier is more granular than Beeminder's single dial — a genuine differentiator, but also the riskiest correctness surface (PITFALLS territory). |
| **Weekly loosening *budget* (3 tokens) rather than per-event delay** | Beeminder uses a time-delay (akrasia horizon); Nightguard uses a scarcity-budget. Both bind; the budget is more legible ("I have 2 left this week") and creates natural pacing. | LOW-MEDIUM (in spec) | Budget + scarcity is well-supported by the scarcity-UX literature: visible limited resource drives deliberate use. The 3-dot meter is a good fit (see Q3). |
| **Timed grace (8 min) that auto-re-locks, vs a full unlock** | Most emergency exits fully unblock until the user re-enables. A *timed* window that re-locks itself removes the "forgot to turn it back on" failure mode entirely. | MEDIUM (NTP boxing, in spec) | This is genuinely better than Locked/Bloom's "burn one exit, fully open" model. The auto-re-lock is the standout feature — emphasize it. |
| **Grace doesn't draw from the same pool as loosening** | Two independent limits (daily grace vs weekly tokens) means a genuine 8-min need doesn't cost a structural loosening. Separates "I need to peek" from "I want to move the boundary." | — (in spec) | Correct separation. Keep them visually distinct on the main screen so they read as different things. |
| **Single sanctioned editor + signed state** | The "one door" model (Cold Turkey's locked-settings, SelfControl's no-UI-while-running) made strong here via HMAC. Hand-edit = silently reverted. | — (in spec) | Differentiator vs consumer tools that just hide a button; here the raw file itself is defended. |

### Anti-Features (commonly built in this category, deliberately excluded here)

| Feature | Why Requested / Why Tools Add It | Why Problematic Here | Alternative |
|---------|----------------------------------|----------------------|-------------|
| **Accounts / login / cloud sync** | Consumer tools need it for multi-device + monetization. | Single-operator local tool. An account is an attack surface and a remote off-switch; cloud sync means the impulsive self could loosen from another device. Adds backend, auth, privacy burden for zero value. | Local-only, DPAPI-bound to this Windows user. (Already out of scope — keep it there.) |
| **Streaks / XP / forest / gamified rewards** | Forest-style loss-aversion is the most-copied retention mechanic in the category. | Cross-sourced trap: "the most copied and most abused feature." Streaks-that-break-and-fail-forever are a psychological trap; novelty fades in 4–6 weeks. Gamification serves *engagement/retention* (a business metric) — Nightguard has no retention problem, it has a self-control problem. Reward loops would also create perverse incentive to "game" the budget. | The token meter + countdown already provide enough feedback. Let the *boundary holding* be the reward. Resist any "you've stayed locked N days!" creep. |
| **Social / accountability partner / referee** | StickK and Beeminder use social stakes (a referee, public commitment) because external observation increases adherence. | Explicitly out of scope (single-operator). Adds another person, another integration, and a relationship to manage. The auto-revert already provides the "external" enforcer role without a human. | The hooks *are* the impartial referee. No human needed. |
| **Financial stakes / anti-charity pledges** | Beeminder/StickK's strongest binding lever (lose money on failure). | Out of category for a local config tool; introduces payments, a third party, real-world consequences disproportionate to "loosened my curfew." | Token scarcity is the stake. Running out of tokens *is* the cost. |
| **Configurable everything (general settings editor)** | Power users always ask for it; "while you're in there, let me edit X." | Explicitly out of scope. Every editable field is a new direction-classifier case and a new bypass vector. The classifier table (12 fields) is already the surface to defend. | Editor edits *only* the curfew config. Anything else is a different tool. |
| **An in-app "disable everything / I'm sure" master override** | Feels safe to add; "what if I really need to turn it all off?" | This *is* the escape hatch the whole category warns about. An always-available master off-switch makes the impulse-self's job trivial and voids the core value. | There is no master off. Disabling curfew is a *loosening* edit → costs a token, rate-limited. That's the whole point. |
| **Notifications / nagging reminders / "you've been locked for X"** | Engagement tools push to stay top-of-mind. | Nagging breeds resentment and bypass; the tool should be invisible until summoned. The hooks enforce silently; the app is opened on demand. | Status lives in the app when opened, plus the hook's block message at the moment of friction. No background nagging. |
| **Multiple difficulty profiles / quick presets ("weekend mode")** | Convenience; lets user swap rule sets fast. | A fast path to a looser ruleset is a loosening shortcut that dodges per-field cost accounting. Presets become the new escape hatch. | Per-field edits through the classifier. Day-of-week schedule already lives *inside* the config (and loosening a day costs a token). |

---

## Q1 — What makes users actually trust an enforcement tool and not bypass it

Cross-tool synthesis (Cold Turkey, SelfControl, Freedom, AppBlock):

1. **Enforcement must outlive the app.** SelfControl's reputation = block survives quit/restart/uninstall. Freedom's reputation problem = quit kills it. *Nightguard's always-firing hooks satisfy this.* Make the promise explicit in-app.
2. **The defended artifact is the real config, not a UI state.** Cold Turkey locks the *settings panel and uninstaller*; Nightguard signs and reverts the *file itself*. Defending the artifact (not just hiding a button) is what sophisticated users trust.
3. **Silent correction beats argument.** Auto-revert with no dialog gives impulse-self nothing to negotiate with. A confirm-dialog is a button to click; a silent revert is a wall.
4. **Honesty about limits builds *more* trust, not less.** Tools that claim "unbreakable" lose credibility on first bypass. The spec's stated "raise friction past the threshold" framing is the correct, durable posture.
5. **The one-door principle.** All sanctioned change flows through a single signed path; everything else fails closed. Reduces the user's own surface for self-sabotage.

**Roadmap implication:** an early phase should make the *trust promises* visible and verifiable (status truthfully reflects hook reality; tamper visibly reverts). If the UI ever shows "locked" while a hand-edit actually loosened things, trust collapses permanently.

## Q2 — Grace / emergency unlock without it becoming the default escape hatch

The category has *converged* on a small set of friction patterns. Nightguard's +8 already uses two of the strongest (hard cap, auto-expiry). Patterns observed:

| Pattern | Who uses it | How it keeps grace honest |
|---------|-------------|---------------------------|
| **Hard cap on uses** | Locked (3 total), Bloom (3 + 1/month), Nightguard (1/day) | Scarcity forces "is this real?" Nightguard's 1/day is stricter than peers — strong. |
| **Auto-expiry / timed window** | Nightguard (8 min, NTP-boxed) | The standout. No "forgot to re-lock" failure. Most tools fully unblock; timed re-lock is better. |
| **Escalating friction on repeat use** | AppBlock (first time = questions; later = retype a specific string) | Worth considering for v1.x: make the *second* same-day attempt (which is denied anyway) explain *why*, and make grace activation require a deliberate confirm so it's never a fat-finger. |
| **Type-a-phrase / multi-step confirm** | AppBlock Strict Mode, generic blockers | A single deliberate confirm before the 8-min window starts. Don't over-engineer — one intentional click + a "starts now, re-locks at HH:MM:SS" confirmation is enough given the daily cap already does the heavy lifting. |
| **Cooldown / delay before grace activates** | One Sec (10s breath), Beeminder (akrasia horizon) | One Sec's PNAS-backed finding: a short delay + an explicit *dismiss* option cuts follow-through ~36%. Consider a brief (a few seconds) "are you sure — this is your one grace today" pause before the window opens. The delay itself is the intervention. |

**Recommended grace UX (enriching the locked +8):**
- Button **lit only during an active lock** (already specced — correct; an always-available grace button invites use).
- One deliberate confirm that states the consequence: *"Uses your one grace for today. Opens for 8 min, then re-locks at 23:41:12."* (true NTP time shown).
- Optional short pre-delay (One Sec pattern) — the pause is where impulse dies. **Complexity: LOW. High behavioral payoff.**
- After use, the button shows **"Grace used — back tomorrow"** with the next-availability time, so it reads as spent-resource not broken-button.

**Anti-pattern to avoid:** making grace *extendable* ("+8 more"). The moment grace can chain, it's a full unlock. The auto-re-lock must be inviolable (NTP-guard-side, which the spec already does).

## Q3 — Status / countdown / allowances: motivating, not nagging

Principles drawn from scarcity-UX literature + the token-meter convention:

- **Countdown reframes a lock from "trapped" to "almost there."** A visible "opens in 6h 12m" is calming; absence of it breeds bypass anxiety. Make the countdown the hero element (spec does).
- **Show remaining as a discrete, depletable resource.** The 3-dot token meter is ideal: discrete dots read as "scarce and spendable," far better than a percentage bar or a running counter. Filled = available, `--token-empty #2a3146` = spent. Scarcity-UX: a *visibly limited* resource drives deliberate use, not anxiety, *as long as* refill timing is shown.
- **Always pair "spent" with "refills."** "1 token left · refills Mon" turns scarcity into a plan rather than a loss. Never show a depleted state without the recovery date — that reads as punishment.
- **Two independent meters, visually distinct.** Weekly tokens (3 dots) and daily grace (single KPI/badge) must not look like the same pool, or the user mis-models their own budget. Spec separates them — keep them spatially apart.
- **Status reflects *true* enforced reality, not the app's wish.** If hooks say locked, the app says locked. Any drift = trust death (see Q1).
- **No background notifications.** Status is pull (open the app) + the hook's block message at the friction moment. The tool is invisible until summoned.

**Avoid:** progress-bar "streak" framing, celebratory toasts, "you've resisted N times!" — that's gamification creep (anti-feature) and turns a quiet boundary into an engagement product.

## Q4 — Asymmetric controls (easy to tighten, hard to loosen): who and how

**Beeminder is the canonical example** and validates Nightguard's core. Its model:

- **Tightening (harder goal) takes effect immediately.** Loosening (easier goal, lower pledge, breaks, quitting) is delayed **one week** (the "akrasia horizon" / commitment dial). Rationale: you only need to bind yourself for the horizon of "immediate" (~1 week per their ice-cream-vs-vegetables study).
- **Presentation makes asymmetry feel like flexibility, not jail:** "You *can* make it easier — starting next week, when you're thinking rationally. You just can't do it Right Now, dammit." This framing is the key UX insight: the restriction is on *timing*, the freedom is preserved, so the rested-self doesn't feel cheated.

**How Nightguard's asymmetry compares / should present:**
- Nightguard uses **scarcity (3 tokens/week)** instead of Beeminder's **time-delay (1 week)**. Both are valid commitment levers. Tokens are *more legible* in the moment ("I have 1 left") and allow *some* immediate loosening (good for genuine needs), where Beeminder allows none for a week. Reasonable tradeoff for a personal tool.
- **Tightening must be conspicuously frictionless+free+instant** — this is the emotional reward that makes the pact feel fair. The live per-field "⬆ tightening — free" feedback (spec) is exactly right; lean into it visually (green, instant, no confirm).
- **Loosening must show its price *before* commit** — "⬇ loosening — costs 1 token (1 left)" and disable commit at 0 with the refill date (spec). Borrow Beeminder's framing on the disabled state: *not* "denied," but "available again Monday." Reframes the wall as a wait.
- **Borrow Beeminder's "you'll thank yourself" framing** for the disabled-at-zero case rather than a hard error. The rested-self set this limit; the message should speak *for* them to the impulse-self.

**Differentiator:** Nightguard's *per-field* direction classification is finer-grained than Beeminder's single dial. That's a real edge (you can tighten one field while the commit stays free) but it's the **highest-risk correctness surface** — a misclassified loosen-as-tighten is a silent bypass. Flag heavily for PITFALLS / testing (the spec already lists classifier unit tests — good).

## Q5 — Anti-features given single-operator local tool

Covered in the Anti-Features table above. The throughline: **anything that adds a remote, a person, an account, a reward loop, or a fast-path preset is a new escape hatch or a new attack surface, and this tool's value is precisely the *absence* of escape hatches.** The discipline is to keep the surface tiny: one config, one door, two limits, one quiet status screen.

---

## Feature Dependencies

```
HMAC signing key (DPAPI)
    └──required by──> Signed config + signed guard.json state
                          └──required by──> Auto-revert integrity guard
                          └──required by──> Direction classifier commit (re-sign on write)
                                                └──required by──> Token budget enforcement
                                                └──required by──> Daily grace enforcement

NTP true-time
    └──required by──> Grace window boxing (8 min, can't be widened by clock edit)
    └──required by──> Curfew lock timing (clock-tamper resistance)
    └──required by──> Weekly reset anchor (Monday 00:00 truth)

Status/countdown UI ──reflects──> Hook-enforced reality (NOT app state)   [trust-critical edge]

Direction classifier ──gates──> Token spend ──displayed by──> 3-dot meter
Grace ──displayed by──> separate KPI/badge   [must NOT share the token pool visually]
```

### Dependency Notes

- **Everything binds on the shared HMAC key.** If Rust and PowerShell can't verify the *same* signature, neither auto-revert nor fail-closed quota works. This is the linchpin — earliest phase.
- **NTP underpins all three time-based features** (lock, grace, weekly reset). A single robust true-time source serves all; build once, reuse. Fail-closed when unreachable.
- **Status UI depends on reading the *hook-enforced* truth, not app-local state** — this is a trust-critical edge, not just a wiring detail. If they can diverge, the product's core promise breaks.
- **Grace and tokens are independent** by design — do not let one implementation accidentally couple them (e.g., shared counter, shared reset). Different cadence (daily vs weekly), different pool.

---

## MVP Definition

### Launch With (v1) — the core guarantee must hold

- [ ] Shared HMAC key (DPAPI) verifiable by both Rust app and PowerShell guard — *nothing works without this.*
- [ ] Auto-revert integrity guard (hand-edit → silent revert to sanctioned; both-tampered → strict default) — *the core value.*
- [ ] Direction classifier (per-field tighten/loosen/noop) + one-token-per-loosening-commit rule — *the asymmetry.*
- [ ] Weekly 3-token budget, Monday 00:00 Europe/Amsterdam reset — *the scarcity lever.*
- [ ] Once-daily 8-min NTP-boxed grace with auto-re-lock, lit only during active lock — *the honest escape valve.*
- [ ] Status hero: locked/open + true countdown; 3-dot token meter (filled/empty + refill date); separate grace KPI.
- [ ] Edit panel: live per-field tighten(free)/loosen(costs token) feedback; commit disabled at 0 tokens with refill date.
- [ ] Fail-closed on invalid state HMAC (weekly_spent=3, grace=used) until app re-syncs.
- [ ] One in-app honest-limits statement (sets correct expectations once).

### Add After Validation (v1.x) — once the core is trusted

- [ ] One Sec-style brief pre-delay + deliberate confirm on grace activation (the pause is the intervention). *Trigger: if grace gets used reflexively.*
- [ ] Escalating-friction explanation on repeat grace attempts (AppBlock pattern). *Trigger: if denied attempts cluster.*
- [ ] Beeminder-style "available again Monday" framing on the disabled-commit state (reframe wall as wait). *Low cost — could even be v1.*
- [ ] Compact weekly ledger view (already YAGNI-gated in spec). *Trigger: if the user wants to audit their own loosening history.*

### Future Consideration (v2+) — only if a real need appears

- [ ] Read-only schedule visualization on the main screen (what's enforced, at a glance). *Defer: edit panel already shows it.*
- [ ] (Explicitly NOT planned: accounts, sync, social, streaks, financial stakes, master-off, presets — see Anti-Features.)

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Shared HMAC / DPAPI key | HIGH | MEDIUM | P1 |
| Auto-revert integrity guard | HIGH | MEDIUM | P1 |
| Direction classifier + 1-token rule | HIGH | MEDIUM-HIGH | P1 |
| Weekly token budget + Monday reset | HIGH | LOW-MEDIUM | P1 |
| NTP-boxed daily grace + auto-re-lock | HIGH | MEDIUM | P1 |
| Status hero + countdown | HIGH | LOW | P1 |
| 3-dot token meter + refill date | HIGH | LOW | P1 |
| Live per-field tighten/loosen feedback | MEDIUM-HIGH | LOW | P1 |
| Fail-closed on bad state HMAC | HIGH | LOW | P1 |
| Honest-limits in-app statement | MEDIUM | LOW | P1 |
| Grace pre-delay + deliberate confirm | MEDIUM | LOW | P2 |
| "Available again Monday" reframing | MEDIUM | LOW | P2 |
| Weekly ledger view | LOW-MEDIUM | LOW | P3 |
| Read-only schedule on main screen | LOW | LOW | P3 |

---

## Competitor Feature Analysis

| Feature | Cold Turkey / SelfControl | Freedom | Beeminder | One Sec / AppBlock / Locked | Nightguard's Approach |
|---------|---------------------------|---------|-----------|------------------------------|------------------------|
| Survives app close | Yes (OS-level / no UI while running) | **No** (quit kills it) | N/A (server-side) | Varies | **Yes** — always-firing hooks |
| Clock-tamper resistance | Cold Turkey blocks Time settings | Limited | Server time | Limited | **NTP true-time** for lock + grace + reset |
| Asymmetric tighten/loosen | No (symmetric on/off) | No | **Yes (1-week akrasia horizon)** | No | **Yes — per-field classifier + token cost** |
| Loosening limit | Timer / random password | Locked Mode session | Time-delayed | Emergency-use cap | **3 tokens/week** |
| Emergency / grace | None (that's the point) | None | N/A | **3 total / 3+1mo / questions** | **1/day, 8-min, NTP-boxed, auto-re-lock** |
| Status/countdown | Yes | Yes | Goal graph + "eep" days | Minimal | **Hero countdown + dual meters** |
| Gamification | None | None | Optional pledges (money) | Some | **None (deliberate anti-feature)** |
| Account/cloud | Local | Cloud account | Cloud account | Cloud | **Local-only, DPAPI-bound** |

---

## Sources

- Cold Turkey Blocker — official user guide & Frozen/Locked behavior: https://getcoldturkey.com/support/user-guide/ ; review: https://productivitystack.io/guides/cold-turkey-blocker-guide/ (HIGH for mechanics; locking, settings-panel block, uninstall block)
- SelfControl — bypass via clock change (known issue #28): https://github.com/SelfControlApp/selfcontrol/issues/28 ; FAQ: https://github.com/selfcontrolapp/selfcontrol/wiki/faq (HIGH — confirms clock-tamper is a category-wide bypass)
- Freedom Locked Mode (and its quit-kills-block limitation): https://support.freedom.to/en/articles/1802927-locked-mode (HIGH — validates hooks-not-app architecture)
- Beeminder akrasia horizon / commitment dial / asymmetric loosening: https://help.beeminder.com/article/45-what-is-the-akrasia-horizon ; https://blog.beeminder.com/dial/ ; https://blog.beeminder.com/flexbind/ (HIGH — canonical asymmetric-control model & framing)
- One Sec — friction/delay/dismiss mechanism, PNAS study (57% fewer opens, 36% dismiss): https://www.pnas.org/doi/10.1073/pnas.2213114120 ; https://one-sec.app/blog/how-one-sec-works/ (HIGH for the delay-as-intervention finding)
- AppBlock Strict Mode emergency flow (escalating friction, retype-string): https://appblock.app/blocked-by-strict-mode-extension/ ; https://appblock.app/what-should-i-do-if-i-am-blocked/ (MEDIUM-HIGH)
- Locked / Bloom emergency-exit caps (3 total / 3+1/month): https://nowlocked.com/products/locked-tag ; https://bloom.inc/ (MEDIUM)
- Forest gamification & the streak-trap critique ("most copied and most abused," novelty fades 4–6 wks): https://trophy.so/blog/forest-gamification-case-study ; https://goodux.appcues.com/blog/forests-gamified-focus (MEDIUM — anti-feature evidence)
- Scarcity UX & commitment-device principles: https://impactwealth.org/the-ux-of-scarcity-how-limited-time-offers-can-drive-action-in-financial-products/ ; https://www.habitweekly.com/commitment-device-database (MEDIUM)

---
*Feature research for: self-binding / commitment-device focus-lock tool (single-operator, local, Windows)*
*Researched: 2026-06-04*
