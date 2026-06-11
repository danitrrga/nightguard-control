# Nightguard Control — UI/UX Polish (Phase 6) Design Spec

**Date:** 2026-06-11
**Status:** Approved direction (decisions locked via brainstorming); status-first execution authorized to run autonomously.
**Scope:** Aesthetic + UX layer ONLY. The Rust backend, IPC command signatures, guard, and all logic are **untouched**. This re-skins and recomposes the frontend (`src/index.html`, `src/styles.css`, `src/main.ts` render layer) so it reads as a 2026 industry-leading desktop app (Linear / Raycast / Vercel caliber).

## Problem (why the current UI fails)

A single 64px countdown floating dead-center on near-black, everything stacked beneath it. Flat (no depth/elevation/layering), austere (hairlines "instead of cards"), and information-poor (countdown + 3 dots + button). Wastes the window; reads as unfinished/AI-default rather than minimal-by-intent.

## Locked decisions

- **Direction:** A — "Moonlit Command Center." Layered, composed, premium dark app. Hero = a **circular night-arc ring** (curfew window drawn as an arc, a moon marker at "now", the live countdown centered inside). Around it, a real composition (token economy, week schedule strip, guard-health) instead of a void.
- **Intensity:** **Subtle / restrained.** Depth + composition + refined color/type win; motion is minimal and calm (200–300ms ease transitions, a gentle ring sweep). NO animated gradients, NO heavy glow, NO spring/shader maximalism. Calm enough for 20:45 at night.
- **Type:** Modern sans — **Inter** (variable or 400/500/600), bundled locally (no CDN, T-04-16). Countdown uses Inter with `font-variant-numeric: tabular-nums`. (Geist is an acceptable swap if Inter bundling is problematic.)
- **Tonight's scope:** Full **status-first** redesign — shell chrome + status/home view to a polished, reviewable state. Edit view + any net-new modules (schedule strip, activity) are a follow-up pass. Backend untouched.

## Visual system (evolves Moonlit Indigo, keeps the brand)

Keep the indigo identity; add the depth + warmth the flat palette lacks.

- **Surfaces (layered, not flat):** `--bg #0b0d13` (deepest field) → `--surface-1 #12151f` (panels) → `--surface-2 #181c28` (raised/hover) → `--border #242a38` hairline + `--border-strong #2e3547`. Panels get subtle elevation: `--shadow-sm 0 1px 2px rgba(0,0,0,.4)`, `--shadow-md 0 8px 24px -8px rgba(0,0,0,.55)`, and a 1px top inner highlight (`inset 0 1px 0 rgba(255,255,255,.04)`) for the "lit from above" premium feel.
- **Text:** `--text #e8eaf0`, `--text-dim #9aa1b4`, `--text-faint #6b7186`.
- **Accent (moonlit indigo):** `--accent #7aa2ff`, `--accent-soft rgba(122,162,255,.14)` (fills/tints), `--accent-ring rgba(122,162,255,.35)`. Restrained glow: a single soft `--accent-glow 0 0 24px rgba(122,162,255,.20)` reserved for the active ring only.
- **Warn (amber):** `--warn #f0a35e`, `--warn-soft rgba(240,163,94,.14)` for loosen/fail-closed.
- **Status semantics:** LOCKED = indigo/cool; OPEN = a calm green-leaning `--ok #6fcf97` (new) so the at-a-glance state isn't monochrome; grace = amber. Used sparingly (the ring + status pill).
- **Radius:** `--r-sm 8px`, `--r-md 12px`, `--r-lg 16px`, `--r-pill 999px`. **Spacing:** keep the 8pt scale.
- **Type scale (Inter):** display 56–72px/600 tabular (countdown), h1 22/600, h2 17/600, body 15/400, label 13/500 (caps tracking .04em for section labels), mono-ish caption 12/500.

## Layout / composition (the fix for "floating in a void")

Replace the single centered column with a **composed home**:

- **Shell:** keep the 56px left rail but make it feel intentional — Inter, crisper icons, an active-item indigo pill background (`--accent-soft`) + left accent bar, a small brand moon mark at top, settings/edit at bottom. Subtle right hairline + `--surface-1` backing.
- **Main = a centered content stack with real structure**, max-width ~600px, vertically rhythmic (not dead-centered in the void):
  1. **Header row:** a **status pill** (● LOCKED / ○ OPEN / ◐ GRACE with the semantic color + soft tint) on the left, and a small **guard-health** chip on the right (e.g. "Guard ✓ · synced" / time-source). Gives the screen a top edge and context.
  2. **Hero: the night-arc ring.** An SVG ring (~280px) where the curfew window (20:45→05:30) is drawn as a colored arc segment over a faint full-circle track; a small **moon marker** sits at the current-time angle; the **countdown** (Display, tabular) + the status word/"next lock at 20:45" caption sit centered inside. LOCKED → the *remaining-curfew* portion fills accent; OPEN → a thin accent tick shows where the next lock falls. This is the centerpiece: beautiful AND genuinely informative (you see the night at a glance).
  3. **Token economy panel** (`--surface-1`, elevated, `--r-md`): the 3 weekly tokens rendered as refined segments/pills (filled = accent with the soft glow, spent = faint), with "3 of 3 · resets Mon Jun 15" and the grace line. The `+8 grace` becomes a proper secondary button inside this panel, enabled only when locked + grace available.
  4. (Follow-up) a slim **week schedule strip** + **recent activity** — speced but not required tonight.
- **No more bare centered text.** Everything sits in deliberate groups with elevation and alignment.

## Motion (restrained)

- Ring countdown second-tick: only the inner digits update (no layout reflow); the arc sweeps smoothly on minute boundaries.
- Hover/focus: 150–200ms color/elevation transitions on rail items + buttons. Focus-visible rings (`--accent-ring`) for a11y.
- View switch (status↔edit): a 200ms cross-fade/translate. Nothing flashy.
- Respect `prefers-reduced-motion`.

## Constraints / invariants (must hold)

- Vanilla TS + Vite + hand CSS, **no UI framework, no icon package** (inline SVG only). Fonts bundled locally, no runtime CDN.
- Render strictly from the existing `get_state` DTO (state_verified, maximal_lockout, lock/boundary_kind, weekly_spent/tokens, grace, NO_UPCOMING_LOCK sentinel). `!state_verified || maximal_lockout` → the whole view drops to a calm "State unverified — fully locked" warm-tone treatment (never optimistic). No new IPC; no optimistic state mutation (re-render only from returned DTOs).
- Tabular numerals on every number; the 1s tick never reflows.
- Tauri v2 / Windows WebView2 (Chromium-based — modern CSS is fine: `color-mix`, conic/SVG, `:focus-visible`, container queries OK).
- Accessibility: keep aria-live status region, aria-labels, 40px min hit targets, visible focus.

## Execution plan (tonight, autonomous)

1. Bundle Inter woff2 locally into `src/assets/`; swap `@font-face`.
2. Rewrite `styles.css` to the layered token system + composed layout + ring + panels (replace the flat single-column rules).
3. Update `index.html` structure: header row (status pill + health chip), SVG night-arc hero with centered countdown, token-economy panel; keep all existing element IDs the JS binds to (or update `main.ts` bindings in lockstep).
4. Update `main.ts` render layer to drive the ring geometry (arc path + moon marker angle from lock/boundary + now) and the new pill/panel, reading only the existing DTO fields. No backend calls added.
5. Keep `tauri dev` hot-reloading; verify `tsc` + `vite build` clean; cargo untouched.
6. Commit as Phase 6 work. Leave edit-view polish + schedule/activity modules as a documented follow-up.

## Out of scope tonight

Edit-view visual overhaul, week schedule strip, activity/audit feed, settings screen. Speced above; deferred to the next pass for review.
