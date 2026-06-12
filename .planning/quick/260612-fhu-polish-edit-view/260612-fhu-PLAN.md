---
quick_id: 260612-fhu
slug: polish-edit-view
title: Polish the edit view (sole sanctioned editor) — Ceramic Night
date: 2026-06-12
status: in-progress
---

# Quick Task 260612-fhu: Polish the edit view

## Goal

De-slop the last unfinished UI surface — the curfew editor — to match the
"Ceramic Night" status-view redesign. Make it feel like an industry-leading
single-purpose editor (Linear/Raycast caliber) without touching the working
Rust backend or the classify/commit IPC contract.

## Scope decision

Backend `classify_change` / `commit_change` only handle `curfew.enabled`,
`curfew.start`, `curfew.end` (read/written by `setYamlField` on the visible
fields). "Schedule fields" therefore means **presenting those three as a
coherent schedule**, NOT adding per-day overrides — that would require new
backend classifier support and risk the working guard. Out of scope.

## What changes (3 files, render contract preserved)

Element IDs the controller depends on are kept verbatim: `field-enabled`,
`field-start`, `field-end`, `fb-curfew.enabled`, `fb-curfew.start`,
`fb-curfew.end`, `edit-reason`, `commit-btn`.

### Task 1 — `src/index.html`: restructure `#edit-view`
- Add a **brand-bar** mirroring the status view (crescent-in-ring mark +
  serif "Nightguard" wordmark) so switching views keeps the chrome consistent.
- Right side of the bar: a **weekly-token budget chip** (3 dots + "N of 3 left")
  so the cost of a loosen is grounded while editing.
- Editor head: eyebrow "Sole sanctioned editor", title "Curfew schedule",
  one-line subtitle ("Edits here are signed; hand-edits revert").
- "Curfew enabled" as a real **toggle switch** (label + hint), feedback below.
- Start/End as a **time range** ("Locks at" → "Opens at") with a center arrow.
- Commit footer: inline reason line + primary (bone) commit button.
- verify: `npm run build` compiles; IDs above still present.

### Task 2 — `src/styles.css`: replace the edit-view block
- New: `.budget-chip`/`.budget-dots`, `.edit-head`/`.edit-sub`, `.edit-rule`,
  `.edit-row`/`.row-label`/`.row-hint`, `.switch`/`.switch-track`/`.switch-thumb`,
  `.time-range`/`.time-field`/`.time-arrow`, `.edit-foot`, primary `#commit-btn`.
- Reuse existing `.brand-bar`/`.mark`/`.wordmark` tokens (auto-consistent).
- Keep `#commit-btn.loosen` (amber) and `.field-feedback.tighten/.loosen`.
- verify: visual — branded header, switch animates, range aligns, no glow.

### Task 3 — `src/main.ts`: token-budget chip wiring
- Add `editBudgetDotsEl` / `editBudgetTextEl` handles + `renderEditBudget(s)`.
- Call it from `render()` (live with every re-verified DTO) and reset to "—"
  in `renderEmpty()`. No change to classify/commit/showView logic.
- verify: `npm run build`; budget reflects `tokens_remaining`.

## Must-haves
- Edit view has a brand-bar consistent with the status view.
- Token budget visible while editing.
- Enabled is a toggle switch; start/end read as a labeled range.
- Build is green; classify/commit/grace still work (IDs unchanged).
- No backend / IPC changes.
