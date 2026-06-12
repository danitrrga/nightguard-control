---
quick_id: 260612-fhu
slug: polish-edit-view
title: Polish the edit view (sole sanctioned editor) — Ceramic Night
date: 2026-06-12
status: complete
commit: 03a57e9
---

# Quick Task 260612-fhu — Summary

De-slopped the curfew editor (the last unfinished UI surface) to match the
"Ceramic Night" status-view redesign. Render/IPC contract preserved; no backend,
classify, or commit changes.

## What shipped

- **Brand-bar on the edit view** — crescent-in-ring mark + serif "Nightguard"
  wordmark, reusing the status view's `.brand-bar`/`.mark`/`.wordmark` so the two
  views share chrome and switching no longer feels like two different apps.
- **Weekly-token budget chip** (3 dots + "N of 3 left"), fed live from the same
  re-verified `StateDto` via a new `renderEditBudget()` called from `render()`.
  Grounds the "costs 1 token" feedback while editing.
- **Toggle switch** for "Curfew enabled" (label + hint) replacing the bare
  accent-color checkbox. The `#field-enabled` input is preserved (visually
  hidden, styled track/thumb) so `composeNewYaml()` still reads `.checked`.
- **Time range** — start/end presented as "Locks at → Opens at" with a center
  arrow, uppercase micro-labels, mono inputs, feedback under each field.
- **Editor head** — eyebrow "Sole sanctioned editor", title "Curfew schedule",
  signed-edits subtitle (reinforces the product's core value).
- **Commit affordance** — primary bone button; amber when the pending diff
  loosens (existing `#commit-btn.loosen`); muted surface when gated at 0 tokens.

## Files

- `src/index.html` — restructured `#edit-view` (brand-bar, head, toggle row,
  time range, commit footer); IDs `field-enabled/start/end`, `fb-curfew.*`,
  `edit-reason`, `commit-btn` all preserved.
- `src/styles.css` — replaced the edit-view block: `.budget-chip`/`.budget-dots`,
  `.edit-head`/`.edit-sub`/`.edit-rule`, `.edit-row`/`.row-label`/`.row-hint`,
  `.switch`/`.switch-track`/`.switch-thumb`, `.time-range`/`.time-field`/
  `.time-arrow`, `.edit-foot`, primary `#commit-btn` (+ disabled).
- `src/main.ts` — `editBudgetDotsEl`/`editBudgetTextEl` handles +
  `renderEditBudget(s)`; called from `render()`, reset to "—" in `renderEmpty()`.

## Scope decision

"Schedule fields" = presenting the three classifier-backed fields
(`enabled`/`start`/`end`) as a coherent schedule. Per-day overrides were **not**
added — the backend `classify_change`/`commit_change` path only handles those
three, so per-day editing would need new backend support and risk the working
guard. Out of scope for a polish task.

## Verification

- `npm run build` (tsc + vite) — green, 0 errors. CSS 11.05 kB, JS 12.17 kB.
- Render contract preserved (controller-referenced element IDs unchanged).
- No `src-tauri/` changes — backend, classifier, commit ordering untouched.

## Not verified (visual)

Live in-window appearance not screenshotted this session (no `tauri dev` launch
to avoid blocking before the user's class). Build-green + ID-preserving edits
make regression risk low; user to eyeball the running app.
