---
phase: 12-launcher-waybar-presence
verified: 2026-07-04T17:40:47Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
---

# Phase 12: Launcher + Waybar Presence Verification Report

**Phase Goal:** Nightguard appears as a first-class omarchy surface — a brand-iconed
`.desktop` entry that opens the TUI in a floating terminal, and a `custom/nightguard`
Waybar module showing live curfew status with left-click-open / right-click-read-only-menu
and instant post-commit refresh.
**Verified:** 2026-07-04T17:40:47Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `ngtui` resolves on PATH and answers `status --json` fail-closed (Plan 01 gate) | VERIFIED | `command -v ngtui` → `/home/danitrrga/.local/bin/ngtui`; live `ngtui status --json` → `{"text":"○ 3","tooltip":"OPEN · 3 tokens left","class":"outside_curfew"}`, exit 0 |
| 2 | A `.desktop` launcher opens `ngtui` in a floating terminal keyed on stable app_id (DESK-03) | VERIFIED | `packaging/omarchy/nightguard.desktop`: `Exec=xdg-terminal-exec --app-id=org.omarchy.ngtui -e ngtui`, `Terminal=false`, `Icon=org.omarchy.ngtui`; `desktop-file-validate` passes on the live installed copy. `hypr/nightguard.windowrule.conf` floats/centers/sizes on `match:class ^(org\.omarchy\.ngtui)$` — never title. Live `~/.config/hypr/hyprland.conf` contains the identical marker-guarded block. Human-verified live: window opened floating+centered, other terminals still tile (12-06-SUMMARY) |
| 3 | An own-brand icon (crescent-guard mark) is installed into hicolor and shown without relogin (DESK-04) | VERIFIED | `packaging/omarchy/icons/nightguard.svg` is byte-identical (content, only a comment differs) to `src/assets/logo.svg` — the canonical porcelain-crescent + cobalt-guard-arc brand mark (confirmed via `diff`, follow-up commit `8edba91`). Live `~/.local/share/icons/hicolor/{16x16,512x512}/apps/org.omarchy.ngtui.png` and `scalable/apps/org.omarchy.ngtui.svg` exist; live scalable SVG is byte-identical to the repo source (`diff` exit 0). Human-verified rendering in walker without relogin |
| 4 | `custom/nightguard` Waybar module shows live curfew status, class-colored, key-less (BAR-01) | VERIFIED | `packaging/omarchy/waybar/custom-nightguard.jsonc`: `"exec": "ngtui status --json"`, `"return-type": "json"`, no sudo/key in exec. `style-nightguard.css` styles all six emitted classes (`locked`/`clock_tamper`/`offline_blocked`=red, `grace_active`=amber, `outside_curfew`=green, `unavailable`=dim). Live `~/.config/waybar/config.jsonc` contains the identical marker-guarded module + is in `modules-center`; live `ngtui status --json` returns real, non-stubbed state (token count matches trust-stack state). Human-verified live rendering |
| 5 | Left-click opens/focuses the TUI; right-click shows a read-only menu with no loosening action (BAR-02/BAR-03) | VERIFIED | Module declares `"on-click": "omarchy-launch-or-focus-tui ngtui"` (reused system helper) and `"on-click-right": "ngtui-menu"`. `packaging/omarchy/bin/ngtui-menu` is executable, `bash -n` clean, only `case` branches are `"Open editor"`/`"Open status"` → `exec omarchy-launch-or-focus-tui ngtui`; every other selection is a no-op. No-loosen grep gate (non-comment lines) passes — no `loosen/token-spend/commit/use_grace/grace grant` verb anywhere. `ngtui-menu` present on live PATH (`~/.local/bin/ngtui-menu`). Human-verified: read-only menu, no lever, present live |
| 6 | The bar refreshes instantly after a successful commit via SIGRTMIN+11, never on a failed/refused commit, and never perturbed by a raising pkill (BAR-04) | VERIFIED | `ngtui/ngtui/backend.py::commit()` fires `pkill -RTMIN+11 waybar` (DEVNULL, `check=False`) strictly inside `if proc.returncode == 0`, wrapped in `try/except Exception: pass`; the returned `{returncode, stdout}` dict is built independently of the signal. `ngtui/tests/test_backend_signal.py` (4 tests: success-fires-once, failure-fires-none, raising-pkill-swallowed, result-shape-unchanged) — all pass. Module declares `"signal": 11` matching the emitted signal. Human-verified: a real loosen-with-token commit (sudo PTY intact) refreshed the bar instantly |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packaging/omarchy/nightguard.desktop` | DESK-03 launcher entry | VERIFIED | Contains `app-id=org.omarchy.ngtui`, `Terminal=false`, `Icon=org.omarchy.ngtui`, `-e ngtui`. Installed live + validates |
| `packaging/omarchy/hypr/nightguard.windowrule.conf` | float/center/size on stable app_id | VERIFIED | 3-line explicit rule, `match:class` only, marker-guarded. Present live, identical |
| `packaging/omarchy/waybar/custom-nightguard.jsonc` | BAR-01/02/03 module def | VERIFIED | `signal:11`, `exec: ngtui status --json`, `on-click`/`on-click-right` wired. Present live, identical, in `modules-center` |
| `packaging/omarchy/waybar/style-nightguard.css` | D-09 fixed semantic colors | VERIFIED | All 6 classes styled. Present live |
| `packaging/omarchy/bin/ngtui-menu` | BAR-03 read-only right-click menu | VERIFIED | `walker --dmenu`, open-only actions, executable (100755), no-loosen grep clean. On live PATH |
| `packaging/omarchy/icons/nightguard.svg` | canonical brand icon source | VERIFIED | Guard-arc + crescent mark, byte-identical (minus a comment) to `src/assets/logo.svg`. Rasterizes cleanly 16→512 (confirmed in 12-03-SUMMARY; live PNGs present and match) |
| `packaging/omarchy/install.sh` | D-07 idempotent backup-first installer | VERIFIED | `bash -n` clean; `cp -a` backup-first; no `jq`/`json.load` round-trip; `grep -qF` idempotency guard; ran successfully live (12/12 auto-verify) |
| `ngtui/tests/test_backend_signal.py` | BAR-04 unit coverage | VERIFIED | 4 tests, all passing |
| `ngtui/tests/test_installer_idempotent.py` | D-07 run-twice-no-dup + backup + comment-preservation coverage | VERIFIED | 3 tests, all passing (incl. inline-array live-shape regression test added in Plan 06) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `nightguard.desktop` Exec | Hyprland windowrule `match:class ^(org.omarchy.ngtui)$` | `xdg-terminal-exec --app-id` → Alacritty `--class` → Wayland app_id | WIRED | Confirmed live: `hyprctl clients` reported `class==org.omarchy.ngtui`, `floating:true` (human-verified, 12-06-SUMMARY) |
| `custom/nightguard` on-click / on-click-right | `omarchy-launch-or-focus-tui ngtui` / `ngtui-menu` | Waybar click handlers | WIRED | Both handlers present in the live module; both binaries resolve on PATH |
| `backend.commit()` success | Waybar `custom/nightguard` module | `pkill -RTMIN+11 waybar` → `"signal": 11` | WIRED | Signal number matches on both sides; unit-tested + human-verified live refresh |
| `ngtui status --json` | Waybar module `exec` | `"exec": "ngtui status --json"`, `"return-type": "json"` | WIRED | Live exec confirmed jq-valid, real (non-stub) trust-stack state |
| `install.sh` | live `config.jsonc`/`hyprland.conf`/`style.css` | marker-guard → `cp -a` backup → text inject | WIRED | Live markers present exactly once each; backup file exists (`config.jsonc.bak.1783158947`) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `custom/nightguard` module | `ngtui status --json` stdout | `ngtui/__main__.py::_status` → `backend.cache_only_verdict(cfg, state)` → real config/state files | Yes — live output token count (3) matches actual trust-stack state, not a hardcoded stub | FLOWING |
| `ngtui-menu` | same JSON object, parsed defensively | same status path | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `ngtui` resolves and answers | `command -v ngtui && ngtui status --json` | `/home/danitrrga/.local/bin/ngtui`; jq-valid JSON, exit 0 | PASS |
| ngtui full test suite green | `cd ngtui && uv run pytest -q` | 74 passed | PASS |
| Installer idempotency suite green | `cd ngtui && uv run pytest tests/test_installer_idempotent.py -v` | 3 passed | PASS |
| Installer syntax clean | `bash -n packaging/omarchy/install.sh` | exit 0 | PASS |
| `ngtui-menu` syntax clean | `bash -n packaging/omarchy/bin/ngtui-menu` | exit 0 | PASS |
| No-loosen invariant on menu | grep gate (non-comment lines) | no match — clean | PASS |
| Live markers/backups/icons/.desktop present | direct filesystem checks against the running desktop | all present, all identical to repo source | PASS |
| `.desktop` validity | `desktop-file-validate ~/.local/share/applications/nightguard.desktop` | valid | PASS |
| Live icon matches canonical brand mark | `diff` repo SVG vs live installed SVG vs `src/assets/logo.svg` | identical (content-wise) across all three | PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention exists in this repo and none is declared in the Phase 12 plans/summaries — this phase uses pytest + grep gates instead, all executed directly above. Step 7c: SKIPPED (no probe scripts declared or discovered).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DESK-03 | 12-01, 12-04, 12-05, 12-06 | `.desktop` opens ngtui in a floating terminal; floating enforced by Hyprland windowrule on stable app-id/class; inline-sudo commit still works | SATISFIED | Verified truths 1-2 above; live human-verify approved |
| DESK-04 | 12-03, 12-05, 12-06 | Custom own-brand icon (no borrowed logos) installed into hicolor theme, shown by launcher + Waybar | SATISFIED | Verified truth 3; icon confirmed to be the canonical guard-arc mark, not the earlier plain crescent |
| BAR-01 | 12-01, 12-04, 12-05 | `custom/nightguard` module shows live curfew status (lock glyph + tokens, colored by state), key-less, non-blocking, fail-closed | SATISFIED | Verified truth 4 |
| BAR-02 | 12-04 | Left-click opens/focuses the TUI | SATISFIED | Verified truth 5 |
| BAR-03 | 12-04 | Right-click shows a read-only menu (verdict, tokens left, grace remaining, open actions) — no loosening action | SATISFIED (see note) | Verified truth 5. Note: the literal "grace remaining" (a numeric countdown) is NOT part of the current `status.py` tooltip contract — this was an explicit, documented Phase-12 decision (D-10: "keep `status.py` as-built … minimal/zero change") to avoid perturbing the D-10 regression baseline. The menu surfaces the verdict word (e.g. "GRACE") + tokens-left via the tooltip; no numeric grace-time-remaining field exists anywhere in the current status object. This is a scope decision recorded in 12-CONTEXT.md, not an unimplemented gap — flagging as informational, not blocking |
| BAR-04 | 12-02, 12-04 | Bar refreshes instantly after a commit via signal push, not just polling | SATISFIED | Verified truth 6 |

No orphaned requirements: REQUIREMENTS.md maps DESK-03, DESK-04, BAR-01..04 to Phase 12 and all six are declared across the six plans' `requirements:` frontmatter. DESK-01/DESK-02 (Phase 11) and DESK-05/DESK-06 (Phase 13, explicitly deferred per D-08) are out of this phase's scope and correctly excluded.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `ngtui/ngtui/backend.py:129-142` | WR-01 (code review) | Private cross-repo global monkeypatching (`guard._sntp`/`guard._http_time`) with no drift guard | WARNING | Not Phase-12-introduced logic per se (non-blocking status seam), but no fail-loud guard if upstream renames — silent hang or crash risk on drift. Carried from code review, not blocking phase goal |
| `packaging/omarchy/install.sh:70,99` | WR-02 (code review) | Backup filename has 1-second granularity (`bak.$(date +%s)`) — sub-second re-run can clobber the pristine backup | WARNING | Narrow race window; does not affect normal single-run installer behavior confirmed live |
| `packaging/omarchy/install.sh:113,145,158,163` | WR-03 (code review) | Waybar-config merge anchors brittle for reasonable reformats of the live config (already hardened once in Plan 06 for the inline-array case) | WARNING | Author-facing only (D-08 scope fence) — blast radius small; already improved once during Plan 06 |
| `packaging/omarchy/bin/ngtui-menu:9,16-17` | WR-04 (code review) | `set -e` script aborts silently if `ngtui status --json` exits 0 with malformed JSON (double unguarded `python3 -c json.load` parses) | WARNING | Narrow edge case (status shim is proven fail-closed exit-0 valid-JSON today); would surface as "menu doesn't open" with no user-facing error if it ever occurred |

No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found in any file modified by this phase (grep across all 10 phase-modified files, zero matches). All four warnings above are carried directly from `12-REVIEW.md` (code review, not verifier-discovered) — they are robustness/coupling concerns, not correctness breaks, and the reviewer explicitly traced and confirmed the three security-sensitive surfaces (commit fail-safe, installer idempotency, menu read-only) hold. None of the four warnings block the phase goal: the launcher, icon, bar module, click surfaces, and signal refresh all function correctly as built and were independently confirmed both via automated checks (this verification) and live human walkthrough (12-06-SUMMARY).

### Human Verification Required

None outstanding. Plan 12-06 Task 2 was a blocking `checkpoint:human-verify` gate covering all five session-bound GUI behaviors (launch+float, bar render, left-click open, right-click read-only menu, instant commit refresh) and was explicitly APPROVED by the human on the live box per 12-06-SUMMARY.md. This verifier independently confirmed the codebase and live-filesystem artifacts backing each of those five behaviors exist, are wired correctly, and are non-stub (Levels 1-4 above) — these session-bound GUI behaviors themselves cannot be re-tested headless and are treated as human-verified PASS per this phase's verification notes.

### Gaps Summary

No gaps. All 6 observable truths verified, all 9 required artifacts pass all applicable levels (exists/substantive/wired/data-flowing), all 5 key links wired, all 6 phase requirement IDs (DESK-03, DESK-04, BAR-01, BAR-02, BAR-03, BAR-04) satisfied and correctly attributed in REQUIREMENTS.md with no orphaned IDs. The ngtui pytest baseline is green at 74 (matching the expected count). The live desktop artifacts (config.jsonc, hyprland.conf, style.css, icons, .desktop, ngtui-menu) were independently confirmed present, correctly marker-guarded, backed up, and byte-identical to their repo sources — corroborating rather than merely trusting the SUMMARY narrative. The one notable nuance (BAR-03's "grace remaining" wording vs. the tooltip's actual verdict-word-only content) is a documented, deliberate Phase-12 scope decision (D-10), not an unimplemented gap, and is noted as informational only.

The four code-review WARNINGs (WR-01..WR-04) are legitimate robustness/coupling concerns worth addressing but do not prevent the phase goal — "Nightguard appears as a first-class omarchy surface" — from being true today, both in the repo and on the live box.

---

_Verified: 2026-07-04T17:40:47Z_
_Verifier: Claude (gsd-verifier)_
