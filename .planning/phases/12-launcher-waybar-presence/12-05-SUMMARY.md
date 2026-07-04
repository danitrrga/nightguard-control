---
phase: 12-launcher-waybar-presence
plan: 05
subsystem: infra
tags: [installer, bash, waybar, hyprland, jsonc, freedesktop, hicolor, idempotent, pytest]

# Dependency graph
requires:
  - phase: 12-launcher-waybar-presence (Plan 03/04)
    provides: canonical omarchy artifacts (nightguard.desktop, icons/nightguard.svg, waybar/custom-nightguard.jsonc, waybar/style-nightguard.css, hypr/nightguard.windowrule.conf, bin/ngtui-menu)
provides:
  - "packaging/omarchy/install.sh — idempotent, backup-first, env-redirectable author-facing installer (D-07)"
  - "ngtui/tests/test_installer_idempotent.py — headless run-twice-no-dup + backup + comment-preservation + JSON-validity coverage"
  - "ngtui/tests/fixtures/{config.jsonc,hyprland.conf,style.css} — realistic minimal merge targets"
affects: [12-06 (live install run), 13 (publish path / PKGBUILD — DESK-06)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Marker-guarded, backup-first text merge into live JSONC (never a jq/JSON round-trip)"
    - "Env-redirectable installer target paths + NG_SKIP_RELOAD test seam for headless idempotency testing against fixtures"
    - "Structural safety net: strip-comments + JSON-parse assertion proves the text injection landed inside the array before the live run"

key-files:
  created:
    - packaging/omarchy/install.sh
    - ngtui/tests/test_installer_idempotent.py
    - ngtui/tests/fixtures/config.jsonc
    - ngtui/tests/fixtures/hyprland.conf
    - ngtui/tests/fixtures/style.css
  modified: []

key-decisions:
  - "Module object injected as the FIRST property (right after the root `{`), not before the final `}` as the plan text suggested — the Plan-04 snippet ends with a trailing comma `},` which is only JSON-valid as a non-terminal property. Head-injection satisfies the must-have that the post-merge config.jsonc still parses as strict JSON after comment stripping."
  - "config.jsonc idempotency uses two independent guards: the `>>> nightguard (managed)` marker for the module object, and a `^\\s*\"custom/nightguard\",\\s*$` regex for modules-center membership (the trailing-comma anchor distinguishes the array element from the `\"clock\": {` definition)."

patterns-established:
  - "Author-facing installer scope fence (D-08): merges into the author's OWN live configs only; the publish path (drop-in snippets never clobbering arbitrary users) is deferred to Phase 13."

requirements-completed: [DESK-03, DESK-04, BAR-01]

# Metrics
duration: 12min
completed: 2026-07-04
---

# Phase 12 Plan 05: Idempotent Author-Facing Installer Summary

**Backup-first, marker-guarded `install.sh` that text-merges the .desktop, hicolor icon, Waybar module+style, and Hyprland windowrule onto env-redirectable targets — proven run-twice-no-dup and JSONC-comment-safe headless against fixtures before it ever touches the live box.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-07-04
- **Tasks:** 2
- **Files modified:** 5 created

## Accomplishments
- `packaging/omarchy/install.sh`: `set -euo pipefail` installer reading all target paths from `NG_*` env vars (live defaults) with an `NG_SKIP_RELOAD` test seam. Marker-guarded, backup-first (`cp -a …bak.<epoch>`) merges; `config.jsonc` edited as TEXT (module head-inject + `modules-center` membership after the `"clock",` anchor) — never jq/JSON. Icon rasterize 16→512 + scalable SVG + `gtk-update-icon-cache -f -t`; `.desktop` + `ngtui-menu` install; reload skipped under the test seam.
- `test_installer_idempotent.py`: copies the three fixtures into `tmp_path`, redirects every `NG_*` target there, runs the installer twice, and asserts one managed block each, a backup per mutated file, `custom/nightguard` in `modules-center` exactly once, surviving `//` comments, and — the T-12-10 safety net — that the post-merge config strip-parses as JSON with `custom/nightguard` a real `modules-center` element. Plus a negative test proving that JSON-parse assertion is load-bearing.
- Full ngtui suite green at 73 (71 D-10 baseline + 2 new) — no regression.

## Task Commits

1. **Task 1: Author install.sh** — `35ddff7` (feat)
2. **Task 2: test_installer_idempotent.py + fixtures** — `6beb22f` (test)

## Files Created/Modified
- `packaging/omarchy/install.sh` - Idempotent, backup-first, env-redirectable author-facing installer (D-07)
- `ngtui/tests/test_installer_idempotent.py` - Run-twice-no-dup + backup + comment-preservation + JSON-validity coverage
- `ngtui/tests/fixtures/config.jsonc` - JSONC merge target (comments + `modules-center` array + root object)
- `ngtui/tests/fixtures/hyprland.conf` - Hyprland personal-section merge target
- `ngtui/tests/fixtures/style.css` - Waybar style merge target (`#custom-*` idiom)

## Decisions Made
- **Head-inject the module object, not before the final `}`.** The plan action text said to insert the module object "before the final top-level `}`". The fixed Plan-04 snippet (`waybar/custom-nightguard.jsonc`) ends with a trailing comma (`},`), which is only JSON-valid as a *non-terminal* property. Inserting it before the final brace would produce a trailing comma before `}` (and a missing comma after the previous property) → invalid strict JSON, failing the must-have "post-merge config.jsonc still parses as JSONC". Injecting it as the first property (right after the root `{`) makes the trailing comma a valid separator and keeps the file parseable. See Deviations.
- **Two independent idempotency guards for config.jsonc** — the shared `>>> nightguard (managed)` marker for the module object, and a distinct trailing-comma array-element regex for `modules-center` membership, so a re-run never double-inserts either edit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module object head-injected instead of before the final `}`**
- **Found during:** Task 1 (authoring the config.jsonc merge)
- **Issue:** The plan's action step (5) said to text-insert the module object "before the final top-level `}`". The Plan-04 module snippet is a fixed artifact ending with `},` (trailing comma). Inserting it as the last property before the final brace yields a trailing comma before `}` (invalid strict JSON) and a missing separator comma after the prior property — which would fail the plan's own hard must-have that the post-merge config.jsonc "still parses as JSONC … `json.loads` the remainder without error".
- **Fix:** Inject the module object as the FIRST property, immediately after the root `{` line. The snippet's trailing comma then correctly separates it from the original first property. `modules-center` membership is inserted after the `"clock",` anchor as specified.
- **Files modified:** packaging/omarchy/install.sh
- **Verification:** Idempotency test's structural-validity assertion (`json.loads` after comment strip, `custom/nightguard` ∈ `modules-center`) passes; a smoke run confirmed valid JSON and one block per file across two runs.
- **Committed in:** 35ddff7 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — correctness of the JSONC merge).
**Impact on plan:** Necessary to satisfy the plan's own structural-validity must-have; identical observable outcome (module defined + in `modules-center`, comments preserved, valid JSON). No scope creep.

## Issues Encountered
- A comment in `install.sh` initially contained the literal string `json.loads`, which tripped the plan's `! grep -Eq 'jq |json\.tool|json\.load'` no-round-trip gate (false positive on a comment). Reworded to "JSON parse" — the installer performs zero JSON round-trips.
- A pre-existing stray repo-root file named `-` (a PNG, timestamped 11:35 before this session) was left untouched per the sequential-executor instruction not to touch unrelated files.

## User Setup Required
None - no external service configuration required. (The live install run against the author's own desktop is Plan 06.)

## Next Phase Readiness
- The installer is proven idempotent, backup-first, and comment-safe headless — Plan 06 can run it against the live box with confidence. Execution-time prerequisites for the live run remain: `ngtui` on PATH (the installer's prereq guard enforces it), and the A1 (waybar SIGUSR2 picks up a new module) / A3 (hyprland auto-reload) checks.

---
*Phase: 12-launcher-waybar-presence*
*Completed: 2026-07-04*

## Self-Check: PASSED
- FOUND: packaging/omarchy/install.sh
- FOUND: ngtui/tests/test_installer_idempotent.py
- FOUND: ngtui/tests/fixtures/config.jsonc, hyprland.conf, style.css
- FOUND commit: 35ddff7 (Task 1)
- FOUND commit: 6beb22f (Task 2)
