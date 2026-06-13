---
phase: quick-260613-opk
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src-tauri/tauri.conf.json
  - src/index.html
  - src/styles.css
  - src/main.ts
autonomous: true
requirements: [UI-POLISH-01]

must_haves:
  truths:
    - "Custom titlebar (drag-region, minimize/maximize/close buttons) renders at top; native OS chrome is gone"
    - "Wordmark 'Nightguard' + status pill appear in the titlebar, not in a brand-bar inside status-view or edit-view"
    - "Rail shows only nav items (no duplicate brand mark SVG)"
    - "Token caption renders on two lines: 'N of 3 tokens left' + 'Resets Mon DD Mon' — no mid-line wrap"
    - "Grace card caption uses short copy: 'Unavailable while open' / 'Available · once today' / 'Used today'"
    - "meter-divider element is absent from HTML and all JS references to it are removed"
    - "edit-budget chip lives in a flex row beside the eyebrow in edit-head, not inside a brand-bar"
    - "Window close/minimize/toggleMaximize wire to Tauri Window API buttons"
  artifacts:
    - path: "src-tauri/tauri.conf.json"
      provides: "decorations=false, shadow=true on main window"
      contains: "decorations"
    - path: "src/index.html"
      provides: "titlebar div with brand mark, wordmark, status-pill, tb-controls; no brand-bar in status-view or edit-view; no meter-divider"
      contains: "titlebar"
    - path: "src/styles.css"
      provides: "titlebar CSS, drag region, tb-controls no-drag, tb-btn hover, brand-bar removed"
      contains: "titlebar"
    - path: "src/main.ts"
      provides: "window control wiring; dividerEl removed; short grace copy"
      contains: "getCurrentWindow"
  key_links:
    - from: "src/main.ts"
      to: "@tauri-apps/api/window"
      via: "import { getCurrentWindow }"
      pattern: "getCurrentWindow"
    - from: "#titlebar .tb-btn#btn-close"
      to: "win.close()"
      via: "click listener in init()"
      pattern: "btn-close"
    - from: "#status-pill"
      to: "statusPillEl()"
      via: "document.getElementById('status-pill') — element moved to titlebar but same id"
      pattern: "status-pill"
---

<objective>
Add a custom OS-chrome titlebar (drag region + min/max/close) and consolidate the brand identity from three locations (rail brand mark, status-view brand-bar, edit-view brand-bar) into one titlebar. Clean up layout debris (meter-divider), tighten copy (token caption, grace caption), and relocate the edit-budget chip into the edit-head.

Purpose: The current layout is visually "sloppy" — the brand mark appears in two places simultaneously, the Windows native titlebar clashes with the Ceramic Night palette, and the token caption wraps at an awkward mid-line break. This plan delivers a single coherent chrome layer.

Output: Four edited files; no new files, no new npm packages.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md

Key invariants from codebase reading:
- `@tauri-apps/api/window` is already in node_modules (it ships with @tauri-apps/api ^2).
- `id="status-pill"` is queried by `statusPillEl()` in main.ts — element must keep that id after moving to the titlebar.
- `id="meter-divider"` is queried by `dividerEl()` on lines 69 and 359/407 of main.ts. Both usages must be deleted.
- `id="edit-budget"`, `id="edit-budget-dots"`, `id="edit-budget-text"` are queried by editBudgetDotsEl()/editBudgetTextEl() — elements must keep those ids after moving to edit-head.
- The Tauri v2 Window API: `import { getCurrentWindow } from "@tauri-apps/api/window"`, then `const win = getCurrentWindow()`. Methods: `win.minimize()`, `win.toggleMaximize()`, `win.close()`.
- tauri.conf.json window object is at `app.windows[0]`. Add `"decorations": false` and `"shadow": true` as sibling keys.
- CSS drag region for Tauri v2 frameless windows: set `data-tauri-drag-region` attribute on the titlebar div (Tauri v2 reads this attribute natively). Buttons inside it need `-webkit-app-region: no-drag` in CSS.
- Body currently has `overflow: hidden` and `height: 100%`. After adding the titlebar, body needs `display: flex; flex-direction: column` so `#shell` flexes into the remaining space below the titlebar.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Disable native decorations in tauri.conf.json</name>
  <files>src-tauri/tauri.conf.json</files>
  <action>
    In `app.windows[0]`, add two keys alongside the existing window properties:

    - `"decorations": false` — removes Windows native titlebar/chrome
    - `"shadow": true` — keeps the drop-shadow on the frameless window

    No other changes to this file.
  </action>
  <verify>
    <automated>node -e "const c=require('./src-tauri/tauri.conf.json'); const w=c.app.windows[0]; process.exit((w.decorations===false && w.shadow===true) ? 0 : 1)"</automated>
  </verify>
  <done>tauri.conf.json contains `"decorations": false` and `"shadow": true` inside the main window object.</done>
</task>

<task type="auto">
  <name>Task 2: Restructure HTML — titlebar, brand consolidation, layout cleanup</name>
  <files>src/index.html</files>
  <action>
    Apply all HTML structural changes in one pass:

    1. BEFORE `<div id="shell">`, insert a new titlebar div as the first child of `<body>`:

       ```
       <div id="titlebar" data-tauri-drag-region>
         <span class="tb-brand">
           <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
             <circle cx="12" cy="12" r="9.3" stroke-width="1.1" opacity="0.45" /><path d="M15.6 13a5 5 0 1 1-4.7-6.9A3.9 3.9 0 0 0 15.6 13Z" fill="currentColor" stroke="none" />
           </svg>
           <span class="wordmark">Nightguard</span>
         </span>
         <span id="status-pill" class="pill">—</span>
         <div class="tb-controls">
           <button type="button" id="btn-min" class="tb-btn" aria-label="Minimize" title="Minimize">
             <svg viewBox="0 0 10 1" aria-hidden="true"><rect width="10" height="1" fill="currentColor"/></svg>
           </button>
           <button type="button" id="btn-max" class="tb-btn" aria-label="Maximize" title="Maximize">
             <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true"><rect x=".5" y=".5" width="9" height="9"/></svg>
           </button>
           <button type="button" id="btn-close" class="tb-btn tb-close" aria-label="Close" title="Close">
             <svg viewBox="0 0 10 10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" aria-hidden="true"><path d="M1 1l8 8M9 1L1 9"/></svg>
           </button>
         </div>
       </div>
       ```

    2. In `#status-view`: remove the entire `<header class="brand-bar">…</header>` block (the one containing `.mark` SVG, `.wordmark`, and `#status-pill`). Note that `#status-pill` now lives in the titlebar — do NOT remove it from the titlebar.

    3. In `#status-view`: remove the `<hr id="meter-divider" />` line entirely.

    4. In `#edit-view`: remove the entire `<header class="brand-bar">…</header>` block (the one containing `.mark` SVG, `.wordmark`, and `#edit-budget`).

    5. In `#edit-view` inside `.edit-head`, add a flex row AFTER the `<p class="eyebrow">Sole sanctioned editor</p>` line but BEFORE the `<h2>` — insert a wrapper that puts the eyebrow and budget chip side-by-side. The simplest approach: wrap the eyebrow and chip together:

       Replace:
       ```
       <p class="eyebrow">Sole sanctioned editor</p>
       <h2 class="type-heading edit-title">Curfew schedule</h2>
       ```
       With:
       ```
       <div class="edit-head-top">
         <p class="eyebrow">Sole sanctioned editor</p>
         <span id="edit-budget" class="budget-chip" title="Weekly loosen tokens remaining">
           <span class="budget-dots" id="edit-budget-dots" aria-hidden="true"></span>
           <span id="edit-budget-text">—</span>
         </span>
       </div>
       <h2 class="type-heading edit-title">Curfew schedule</h2>
       ```

    6. In `#rail`: remove the `<span class="brand" aria-hidden="true">…</span>` block (the moon SVG inside the rail). The rail starts directly with the `<button id="rail-status">` nav item.
  </action>
  <verify>
    <automated>node -e "const fs=require('fs'); const h=fs.readFileSync('src/index.html','utf8'); const ok=h.includes('id=\"titlebar\"') && h.includes('data-tauri-drag-region') && h.includes('id=\"btn-close\"') && h.includes('id=\"status-pill\"') && !h.includes('meter-divider') && h.includes('edit-head-top') && !h.includes('class=\"brand\"'); process.exit(ok?0:1)"</automated>
  </verify>
  <done>
    - id="titlebar" with data-tauri-drag-region and three window control buttons exists before #shell
    - id="status-pill" lives inside #titlebar (not inside status-view)
    - brand-bar headers are absent from both status-view and edit-view
    - id="meter-divider" is absent from the HTML
    - id="edit-budget" / id="edit-budget-dots" / id="edit-budget-text" live inside .edit-head-top in edit-view
    - .brand span is absent from #rail
  </done>
</task>

<task type="auto">
  <name>Task 3: CSS + main.ts — titlebar styles, copy polish, dividerEl removal</name>
  <files>src/styles.css, src/main.ts</files>
  <action>
    ## src/styles.css

    1. Add `--titlebar-h: 36px` to `:root`.

    2. Change `body` layout: add `display: flex; flex-direction: column;` to the existing `body` rule (keep `background`, `color`, `font-family`, `-webkit-font-smoothing`, `text-rendering`, `overflow: hidden`).

    3. Add the titlebar block after the body rule:

       ```css
       #titlebar {
         flex: 0 0 var(--titlebar-h);
         height: var(--titlebar-h);
         display: flex;
         align-items: center;
         justify-content: space-between;
         padding: 0 var(--sp-sm) 0 var(--sp-md);
         background: var(--surface-1);
         border-bottom: 1px solid var(--border-subtle);
         position: relative;
         z-index: 10;
         user-select: none;
         -webkit-app-region: drag;
       }
       .tb-brand {
         display: inline-flex;
         align-items: center;
         gap: 8px;
         color: var(--brand);
       }
       .tb-brand svg {
         width: 18px;
         height: 18px;
         flex-shrink: 0;
       }
       .tb-brand .wordmark {
         font-size: 14px;
         color: var(--text);
       }
       .tb-controls {
         display: flex;
         align-items: center;
         gap: 2px;
         -webkit-app-region: no-drag;
       }
       .tb-btn {
         width: 32px;
         height: 32px;
         display: flex;
         align-items: center;
         justify-content: center;
         background: none;
         border: none;
         border-radius: var(--r-sm);
         color: var(--dim);
         cursor: pointer;
         padding: 0;
         transition: background 0.15s var(--ease), color 0.15s var(--ease);
       }
       .tb-btn svg {
         width: 10px;
         height: 10px;
         display: block;
       }
       .tb-btn:hover {
         background: var(--surface-hover);
         color: var(--text);
       }
       .tb-btn.tb-close:hover {
         background: var(--rose);
         color: #fff;
       }
       ```

    4. Change `#shell` to add `flex: 1 1 0; min-height: 0;` (keeping `position: relative; z-index: 1; display: flex;` and removing `height: 100%` since body is now the 100%-height flex column — shell grows into remaining space).

    5. Remove the `#rail .brand` and `#rail .brand svg` rule blocks entirely (the element is gone from HTML).

    6. Remove the `.brand-bar`, `.brand-bar .mark`, `.brand-bar .mark svg`, and `.wordmark` rule blocks. The `.wordmark` class is now only used inside `.tb-brand` where it needs only the font-size override (already in `.tb-brand .wordmark`).

    7. Add `.edit-head-top` rule for the eyebrow + budget chip flex row inside edit-head:

       ```css
       .edit-head-top {
         display: flex;
         align-items: center;
         justify-content: space-between;
         margin-bottom: 6px;
       }
       .edit-head-top .eyebrow {
         margin: 0;
       }
       ```

    8. Remove the `#meter-divider` rule block.

    ## src/main.ts

    1. Add the window API import at the top alongside the existing imports:
       `import { getCurrentWindow } from "@tauri-apps/api/window";`

    2. Remove the `dividerEl` accessor function (line 69: `const dividerEl = () => el<HTMLElement>("meter-divider");`).

    3. Remove the two usages of `dividerEl()`:
       - In `render()`: remove `dividerEl().style.display = "";` (currently at the bottom of the render function)
       - In `renderEmpty()`: remove `dividerEl().style.display = "none";`

    4. In `render()`, change the token caption from one `<p>` with a combined string to two separate lines:
       Replace:
       ```ts
       tokenCaptionEl().textContent = `${remaining} of 3 tokens · resets Monday ${fmtDate(s.next_reset_unix)}`;
       ```
       With:
       ```ts
       tokenCaptionEl().innerHTML = `${remaining} of 3 tokens left<br>Resets Mon ${fmtDate(s.next_reset_unix)}`;
       ```

    5. In `render()`, change the grace caption copy:
       Replace:
       ```ts
       if (!s.locked) {
         grace = "+8 unavailable (not locked)";
       } else if (s.grace_available_today) {
         grace = "+8 available today";
       } else {
         grace = "+8 used today";
       }
       ```
       With:
       ```ts
       if (!s.locked) {
         grace = "Unavailable while open";
       } else if (s.grace_available_today) {
         grace = "Available · once today";
       } else {
         grace = "Used today";
       }
       ```

    6. At the end of `init()`, wire the three window control buttons. Add after the `setInterval` call:
       ```ts
       const win = getCurrentWindow();
       document.getElementById("btn-min")?.addEventListener("click", () => void win.minimize());
       document.getElementById("btn-max")?.addEventListener("click", () => void win.toggleMaximize());
       document.getElementById("btn-close")?.addEventListener("click", () => void win.close());
       ```

    Ensure `tsc --noEmit` passes after all changes (run it if needed to check types).
  </action>
  <verify>
    <automated>cd "C:\Users\20252128\dev\Projects\nightguard-control" && node -e "const fs=require('fs'); const css=fs.readFileSync('src/styles.css','utf8'); const ts=fs.readFileSync('src/main.ts','utf8'); const ok=css.includes('--titlebar-h')&&css.includes('#titlebar')&&css.includes('tb-controls')&&css.includes('tb-btn.tb-close')&&css.includes('edit-head-top')&&!css.includes('meter-divider')&&!css.includes('brand-bar')&&ts.includes('getCurrentWindow')&&!ts.includes('dividerEl')&&ts.includes('toggleMaximize')&&ts.includes('Unavailable while open')&&ts.includes('Available · once today'); process.exit(ok?0:1)"</automated>
  </verify>
  <done>
    - CSS: --titlebar-h token present; #titlebar, .tb-controls, .tb-btn, .tb-btn.tb-close rules present; .brand-bar rules absent; #meter-divider rule absent; #shell has flex grow; .edit-head-top rule present
    - main.ts: getCurrentWindow imported; dividerEl accessor and both usages absent; window control listeners wired to btn-min/btn-max/btn-close; grace copy uses short strings; token caption uses innerHTML with line break
    - tsc compiles clean (no type errors from the getCurrentWindow import or innerHTML change)
  </done>
</task>

</tasks>

<verification>
After all three tasks complete, run a quick smoke check:

1. `npm run build` (or `npx tsc --noEmit` for type-only) — must succeed with no errors.
2. `tauri dev` — the window opens without a native OS titlebar; the custom titlebar shows the moon mark + "Nightguard" wordmark + the status pill + three control buttons.
3. Drag the titlebar — window moves. Click minimize/maximize/close — they work.
4. Status view: no brand-bar above the ring hero; token card shows two-line caption; grace card shows "Unavailable while open" (when unlocked).
5. Edit view: no brand-bar; the eyebrow "Sole sanctioned editor" and budget chip are on the same line inside edit-head.
6. Rail: no moon SVG above the nav items.
</verification>

<success_criteria>
- Native OS titlebar is gone; custom titlebar renders at 36px with drag-region semantics
- Brand identity (moon SVG + "Nightguard") appears ONCE — in the titlebar
- Status pill is in the titlebar and continues to update correctly from main.ts render()
- Token caption does not wrap mid-line; renders as "N of 3 tokens left / Resets Mon DD Mon" on two lines
- Grace card copy is concise (three variants: "Unavailable while open", "Available · once today", "Used today")
- No JavaScript errors from removed dividerEl references
- tsc and vite build pass clean
</success_criteria>

<output>
Create `.planning/quick/260613-opk-ui-polish-fix-layout-alignment-text-inco/260613-opk-SUMMARY.md` when done.
</output>
